#!/usr/bin/env python3
"""Refresh only a retained scene/replay background, preserving capture evidence.

No source routes, motion, policies, observations or native results are generated
or changed. The exact retained access artifact and frozen OSM geometry drive the
new raster. Prior presentation artifacts are archived; current digest manifests
record the bounded refresh separately from original native execution provenance.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile

import yaml


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, body):
    # Replacing, rather than writing through, also keeps staging hardlinks safe.
    temporary = path.with_name(path.name + '.refresh-tmp')
    temporary.write_text(json.dumps(body, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    os.replace(temporary, path)


def refresh_background(scene, replay, repo):
    scene, replay, repo = Path(scene).resolve(), Path(replay).resolve(), Path(repo).resolve()
    # Staging lives below replay.parent. A nested/identical scene could include
    # that staging directory in copytree and recursively copy itself. Resolving
    # paths first also catches directory aliases through symlinks.
    if scene.is_relative_to(replay) or replay.is_relative_to(scene):
        raise ValueError('Scene and replay directories must be distinct and non-overlapping')
    if repo.is_relative_to(scene) or repo.is_relative_to(replay):
        raise ValueError('Scene and replay directories must not contain the repository')
    builder = module_at('ump_background_builder', repo / 'tools/mapped_scene/build_mapped_scene.py')
    exporter = module_at('ump_background_exporter', repo / 'tools/mapped_scene/export_replay.py')
    server = module_at('ump_background_validator', repo / 'tools/replay_viewer/serve.py')
    server.validate_bundle(replay)
    manifest = json.loads((scene / 'scene_manifest.json').read_text())
    bundle = json.loads((replay / 'bundle.json').read_text())
    proof = json.loads((replay / 'capture-proof.json').read_text())
    if proof.get('status') != 'verified':
        raise ValueError('Only an already verified capture may receive a presentation refresh')
    required_files = {'bundle.json', 'private/config.yaml', 'private/native_source.json', *bundle.get('sha256', {})}
    if not isinstance(proof.get('files_sha256'), dict) or not required_files.issubset(proof['files_sha256']):
        raise ValueError('Original capture proof is missing required artifact digests')
    for name, expected in proof['files_sha256'].items():
        path = (replay / name).resolve()
        if not path.is_relative_to(replay) or not path.is_file() or digest(path) != expected:
            raise ValueError('Original capture digest mismatch: ' + name)
    cfg = yaml.safe_load((scene / 'config.yaml').read_text())
    if digest(scene / 'config.yaml') != digest(replay / 'private/config.yaml'):
        raise ValueError('Scene and retained native configurations differ')
    access_path = scene / 'building_access.json'
    if not access_path.is_file() or digest(access_path) != digest(replay / 'building_access.json'):
        raise ValueError('Refresh requires the exact scene/replay building access artifact')
    exporter.validate_scene_building_access(scene, cfg, access_path)
    if digest(scene / 'map_background.png') != digest(replay / 'map_background.png'):
        raise ValueError('Scene and retained replay backgrounds differ')
    _, _, layers, _, provenance = builder.load_source(repo)
    for field in ('compressed_source_sha256', 'source_geometry_sha256', 'coordinate_transform', 'map_builder_sha256'):
        if manifest.get(field) != provenance[field]:
            raise ValueError('Frozen source provenance differs: ' + field)
    access = json.loads(access_path.read_text())
    before_files = dict(proof['files_sha256'])
    old_background = digest(scene / 'map_background.png')
    before_manifest = digest(scene / 'scene_manifest.json')
    before_proof = digest(replay / 'capture-proof.json')
    with tempfile.TemporaryDirectory(prefix='ump-background-refresh-', dir=replay.parent) as temporary:
        staging = Path(temporary)
        image = staging / 'map_background.png'
        rendering = builder.draw_background(layers, image, access)
        new_background = digest(image)
        if new_background == old_background and manifest.get('background_rendering') == rendering:
            return {'status': 'unchanged', 'background_sha256': new_background}
        refresh_id = 'geometry-only-' + old_background[:12] + '-' + new_background[:12]
        scene_history = scene / 'presentation_history' / refresh_id
        replay_history = replay / 'private/presentation_history' / refresh_id
        if scene_history.exists() or replay_history.exists():
            raise ValueError('Refusing to replace prior presentation history')
        record = {'schema': 'ump.map-presentation-refresh.v1', 'id': refresh_id,
                  'at_utc': datetime.now(timezone.utc).isoformat(),
                  'scope': 'Raster presentation only: remove baked names, attribution glyphs and access debug/entrance marks. Native source, policies, observations, results and access geometry unchanged.',
                  'renderer_sha256': digest(repo / 'tools/mapped_scene/build_mapped_scene.py'),
                  'refresh_tool_sha256': digest(Path(__file__)),
                  'before': {'background_sha256': old_background, 'scene_manifest_sha256': before_manifest,
                             'capture_proof_sha256': before_proof, 'files_sha256': before_files},
                  'after': {'background_sha256': new_background},
                  'scene_archive': str(scene_history.relative_to(scene)),
                  'replay_archive': str(replay_history.relative_to(replay)),
                  'background_rendering': rendering}
        manifest['background_sha256'] = new_background
        manifest['background_rendering'] = rendering
        manifest.setdefault('presentation_refreshes', []).append(record)
        bundle['sha256']['map_background.png'] = new_background
        staged_scene, staged_replay = staging / 'scene', staging / 'replay'
        # Hardlink unchanged large motion files. Only os.replace changes staged
        # presentation files, never bytes in an original shared inode.
        shutil.copytree(scene, staged_scene, copy_function=os.link)
        shutil.copytree(replay, staged_replay, copy_function=os.link)
        for target in (staged_scene / 'map_background.png', staged_replay / 'map_background.png'):
            target.unlink()
            shutil.copyfile(image, target)
        write_json(staged_scene / 'scene_manifest.json', manifest)
        write_json(staged_replay / 'bundle.json', bundle)
        proof['files_sha256']['map_background.png'] = new_background
        proof['files_sha256']['bundle.json'] = digest(staged_replay / 'bundle.json')
        proof_record = {**record, 'after': {**record['after'],
                        'scene_manifest_sha256': digest(staged_scene / 'scene_manifest.json'),
                        'bundle_sha256': digest(staged_replay / 'bundle.json')}}
        proof.setdefault('presentation_refreshes', []).append(proof_record)
        write_json(staged_replay / 'capture-proof.json', proof)
        exporter.validate_scene_building_access(staged_scene, cfg, staged_scene / 'building_access.json')
        server.validate_bundle(staged_replay)
        for name, expected in proof['files_sha256'].items():
            if digest(staged_replay / name) != expected:
                raise ValueError('Staged capture digest mismatch: ' + name)
        scene_names = ('map_background.png', 'scene_manifest.json')
        replay_names = ('map_background.png', 'bundle.json', 'capture-proof.json')
        scene_history.mkdir(parents=True)
        replay_history.mkdir(parents=True)
        for root, archive, names in ((scene, scene_history, scene_names), (replay, replay_history, replay_names)):
            for name in names:
                shutil.copyfile(root / name, archive / name)
        try:
            for current, staged, names in ((scene, staged_scene, scene_names), (replay, staged_replay, replay_names)):
                for name in names:
                    os.replace(staged / name, current / name)
        except BaseException:
            # Preserve the prior coherent presentation if a replacement fails.
            for current, archive, names in ((scene, scene_history, scene_names), (replay, replay_history, replay_names)):
                for name in names:
                    shutil.copyfile(archive / name, current / name)
            raise
    return {'status': 'refreshed', 'id': refresh_id, 'before_background_sha256': old_background,
            'background_sha256': new_background, 'motion_and_result_files_unchanged': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene', required=True, type=Path)
    parser.add_argument('--replay', required=True, type=Path)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    print(json.dumps(refresh_background(args.scene, args.replay, args.repo)))


if __name__ == '__main__':
    main()
