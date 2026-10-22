#!/usr/bin/env python3
"""Verify or restore the compact, synthetic UMP replay data package (stdlib only).

The manifest lists every archived byte stream. Restoration never executes
commands from historical manifests, follows archive links or replaces a target.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "ump.replay-data-package.v1"
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 4 * 1024 * 1024 * 1024
CHUNK = 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(CHUNK):
            digest.update(block)
    return digest.hexdigest()


def relative_path(value: str) -> str:
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or any(part in ("", ".", "..") for part in value.split("/"))
            or PurePosixPath(value).is_absolute()):
        raise ValueError("Archive paths must be ordinary relative POSIX filenames")
    return value


def no_symlink_parents(path: Path) -> None:
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError("Symlink paths are not accepted")


def load_manifest(package: Path) -> dict:
    no_symlink_parents(package.absolute())
    manifest_path = package / "manifest.json"
    no_symlink_parents(manifest_path.absolute())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema") != SCHEMA:
        raise ValueError("Unsupported replay data package schema")
    if not isinstance(manifest.get("archives"), list) or not manifest["archives"]:
        raise ValueError("Package requires archives")
    if not isinstance(manifest.get("files"), list) or not manifest["files"]:
        raise ValueError("Package requires a complete file inventory")
    archives = {}
    for archive in manifest["archives"]:
        name = archive.get("name", "")
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_-]+\.tar\.gz", name) or name in archives:
            raise ValueError("Invalid or duplicate archive name")
        archives[name] = archive
    paths = set()
    total = 0
    for item in manifest["files"]:
        path = relative_path(item.get("path"))
        size = item.get("bytes")
        if path in paths or item.get("archive") not in archives:
            raise ValueError("Duplicate file or unknown archive")
        if type(size) is not int or not 0 <= size <= MAX_FILE_BYTES:
            raise ValueError("Invalid or excessive member size")
        if not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256", "")):
            raise ValueError("Invalid member digest")
        total += size
        paths.add(path)
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Package exceeds the uncompressed size limit")
    for copy in manifest.get("copies", []):
        source, target = relative_path(copy.get("from")), relative_path(copy.get("to"))
        if source not in paths or target in paths:
            raise ValueError("Invalid canonical input copy")
        paths.add(target)
    for bundle in manifest.get("bundles", []):
        relative_path(bundle)
        if bundle + "/bundle.json" not in paths or bundle + "/observations.json" not in paths:
            raise ValueError("Incomplete restored viewer bundle")
    return manifest


def _walk_archive(package: Path, archive: dict, expected: dict, output: Path | None = None) -> None:
    path = package / archive["name"]
    no_symlink_parents(path.absolute())
    if not path.is_file() or path.stat().st_size != archive.get("bytes") or sha256(path) != archive.get("sha256"):
        raise ValueError("Archive integrity failure: " + archive["name"])
    seen = set()
    with tarfile.open(path, mode="r|gz") as tar:
        for member in tar:
            name = relative_path(member.name)
            if not member.isfile() or name in seen or name not in expected:
                raise ValueError("Unexpected, duplicate or nonregular archive member: " + name)
            item = expected[name]
            if member.size != item["bytes"]:
                raise ValueError("Archive member size mismatch: " + name)
            source = tar.extractfile(member)
            if source is None:
                raise ValueError("Unreadable archive member")
            destination = None
            if output is not None:
                target = output / name
                target.parent.mkdir(parents=True, exist_ok=True)
                destination = target.open("xb")
            digest = hashlib.sha256()
            try:
                while block := source.read(CHUNK):
                    digest.update(block)
                    if destination is not None:
                        destination.write(block)
            finally:
                if destination is not None:
                    destination.close()
            if digest.hexdigest() != item["sha256"]:
                raise ValueError("Archive member integrity failure: " + name)
            seen.add(name)
    if seen != set(expected) or len(seen) != archive.get("member_count"):
        raise ValueError("Missing archive member or incorrect member count")
    if sum(row["bytes"] for row in expected.values()) != archive.get("uncompressed_bytes"):
        raise ValueError("Incorrect uncompressed archive size")


def verify(package: Path) -> dict:
    package = Path(package)
    manifest = load_manifest(package)
    for archive in manifest["archives"]:
        expected = {item["path"]: item for item in manifest["files"] if item["archive"] == archive["name"]}
        _walk_archive(package, archive, expected)
    return {"schema": SCHEMA, "status": "verified", "archives": len(manifest["archives"]),
            "files": len(manifest["files"]), "compressed_bytes": sum(a["bytes"] for a in manifest["archives"]),
            "uncompressed_bytes": sum(f["bytes"] for f in manifest["files"]),
            "viewer_bundles": len(manifest.get("bundles", [])), "manifest_sha256": sha256(package / "manifest.json")}


def restore(package: Path, output: Path) -> dict:
    package, output = Path(package), Path(output).absolute()
    no_symlink_parents(output)
    if output.exists():
        raise FileExistsError("Restore destination already exists; choose a new directory")
    if not output.parent.is_dir():
        raise ValueError("Restore destination parent must already exist")
    report = verify(package)
    manifest = load_manifest(package)
    output.mkdir(mode=0o700)
    try:
        for archive in manifest["archives"]:
            expected = {item["path"]: item for item in manifest["files"] if item["archive"] == archive["name"]}
            _walk_archive(package, archive, expected, output)
        for copy in manifest.get("copies", []):
            target = output / copy["to"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with (output / copy["from"]).open("rb") as source, target.open("xb") as destination:
                shutil.copyfileobj(source, destination, CHUNK)
        report.update(status="restored", output=str(output), bundles=manifest.get("bundles", []),
                      canonical_input_copies=len(manifest.get("copies", [])))
        (output / "restore-manifest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except BaseException:
        shutil.rmtree(output)
        raise
    return report


def write_archive(path: Path, files: list[tuple[str, Path]]) -> tuple[dict, list[dict]]:
    """Build reproducible tar/gzip streams; used by the publication assembly."""
    inventory = []
    if path.exists():
        raise FileExistsError(path)
    with path.open("xb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0, compresslevel=6) as compressed:
        with tarfile.open(fileobj=compressed, mode="w|", format=tarfile.PAX_FORMAT) as tar:
            for name, source in sorted(files):
                relative_path(name)
                no_symlink_parents(source.absolute())
                if not source.is_file() or source.stat().st_size > MAX_FILE_BYTES:
                    raise ValueError("Invalid package source")
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = source.stat().st_size, 0o600, 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with source.open("rb") as stream:
                    tar.addfile(info, stream)
                inventory.append({"path": name, "archive": path.name, "bytes": info.size,
                                  "sha256": sha256(source)})
    archive = {"name": path.name, "bytes": path.stat().st_size, "sha256": sha256(path),
               "member_count": len(inventory), "uncompressed_bytes": sum(f["bytes"] for f in inventory)}
    return archive, inventory


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("verify", "restore"))
    parser.add_argument("--package", type=Path, default=ROOT / "data/replay-studies")
    parser.add_argument("--output", type=Path, help="New restore directory; existing targets are never replaced")
    args = parser.parse_args(argv)
    if args.operation == "restore" and args.output is None:
        parser.error("restore requires --output")
    if args.operation == "verify" and args.output is not None:
        parser.error("--output applies only to restore")
    try:
        result = verify(args.package) if args.operation == "verify" else restore(args.package, args.output)
    except (ValueError, OSError, tarfile.TarError, EOFError) as error:
        parser.exit(1, "Replay data error: " + str(error) + "\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
