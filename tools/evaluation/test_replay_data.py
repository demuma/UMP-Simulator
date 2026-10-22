"""Integrity, portability and destination-safety tests for replay publication."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import tarfile
import unittest

import replay_data as data


class ReplayDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        # macOS /var and /tmp aliases are intentionally resolved for safe fixtures.
        self.root = Path(self.temp.name).resolve()
        self.package = self.root / "package"
        self.package.mkdir()
        source = self.root / "source.json"
        source.write_bytes(b'{"frozen": "synthetic"}\n')
        bundle = self.root / "bundle.json"
        bundle.write_bytes(b'{}\n')
        self.spec = [("inputs/n200.json", source), ("moving/n200/bundle.json", bundle)]
        archive, files = data.write_archive(self.package / "sample.tar.gz", self.spec)
        self.manifest = {"schema": data.SCHEMA, "archives": [archive], "files": files,
                         "copies": [{"from": "inputs/n200.json", "to": "moving/n200/observations.json"}],
                         "bundles": ["moving/n200"]}
        self.save()

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.package / "manifest.json").write_text(json.dumps(self.manifest))

    def test_deterministic_archive_and_exact_restore_with_canonical_input_copy(self):
        other = self.root / "other"
        other.mkdir()
        archive, files = data.write_archive(other / "sample.tar.gz", list(reversed(self.spec)))
        self.assertEqual(archive, self.manifest["archives"][0])
        self.assertEqual(files, self.manifest["files"])
        self.assertEqual(data.verify(self.package)["files"], 2)
        target = self.root / "restored"
        result = data.restore(self.package, target)
        self.assertEqual(result["canonical_input_copies"], 1)
        for path, source in self.spec:
            self.assertEqual((target / path).read_bytes(), source.read_bytes())
        self.assertEqual((target / "moving/n200/observations.json").read_bytes(), self.spec[0][1].read_bytes())

    def test_corrupted_archive_or_member_digest_never_creates_target(self):
        archive = self.package / "sample.tar.gz"
        original = archive.read_bytes()
        archive.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        target = self.root / "restored"
        with self.assertRaisesRegex(ValueError, "Archive integrity"):
            data.restore(self.package, target)
        self.assertFalse(target.exists())
        archive.write_bytes(original)
        self.manifest["files"][0]["sha256"] = "0" * 64
        self.save()
        with self.assertRaisesRegex(ValueError, "member integrity"):
            data.restore(self.package, target)
        self.assertFalse(target.exists())

    def test_existing_destination_and_symlink_ancestors_are_rejected(self):
        target = self.root / "existing"
        target.mkdir()
        sentinel = target / "sentinel"
        sentinel.write_text("preserve")
        with self.assertRaises(FileExistsError):
            data.restore(self.package, target)
        self.assertEqual(sentinel.read_text(), "preserve")
        link = self.root / "linked"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            data.restore(self.package, link / "new")
        self.assertFalse((target / "new").exists())

    def test_manifest_traversal_and_duplicate_paths_are_rejected(self):
        for unsafe in ("../escape", "/absolute", "a/../escape", "a\\escape", "a//escape", "C:escape"):
            with self.subTest(unsafe=unsafe):
                original = self.manifest["files"][0]["path"]
                self.manifest["files"][0]["path"] = unsafe
                self.save()
                with self.assertRaises(ValueError):
                    data.verify(self.package)
                self.manifest["files"][0]["path"] = original
        self.manifest["files"].append(dict(self.manifest["files"][0]))
        self.save()
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            data.verify(self.package)

    def test_unlisted_members_missing_members_and_archive_links_are_rejected(self):
        path = self.package / "sample.tar.gz"
        for kind in ("unlisted", "missing", "symlink", "traversal"):
            with self.subTest(kind=kind):
                with tarfile.open(path, "w:gz") as archive:
                    if kind != "missing":
                        name = "../escape" if kind == "traversal" else "unexpected" if kind == "unlisted" else self.spec[0][0]
                        info = tarfile.TarInfo(name)
                        if kind == "symlink":
                            info.type, info.linkname = tarfile.SYMTYPE, "../../escape"
                            archive.addfile(info)
                        else:
                            info.size = 1
                            archive.addfile(info, io.BytesIO(b"x"))
                self.manifest["archives"][0].update(bytes=path.stat().st_size, sha256=data.sha256(path))
                self.save()
                with self.assertRaises(ValueError):
                    data.verify(self.package)
                self.assertFalse((self.root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
