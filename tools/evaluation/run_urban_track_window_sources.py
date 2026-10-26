#!/usr/bin/env python3
"""Explicit observed-track-window import and prospective TEST capture.

A separate evaluation reuses ALL forty already assigned TRAIN/CAL captures without
rewriting their strict completed-episode verdicts. All thirty-two original TEST
slots remain prospective until the new evaluation's actual model/CAL lock. The
native source law, source binary, policies and dataset role seeds are unchanged.
Only the declared source-unit/quality contract is different. No legacy validator
fallback, resampling, trajectory repair or quality-based enrollment is permitted.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import fcntl
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import run_urban_privacy_sources as source
import track_window_source_validation as validation
import urban_privacy_split as split

ROOT = source.ROOT
PROFILE = validation.PROFILE
SCHEMA = validation.PROTOCOL_SCHEMA
LEDGER_SCHEMA = 'ump.observed-track-window-import-ledger.v1'
DEFAULT_EVALUATION_ID = 'urban-track-window-20261026-v1'
MIN_FREE_BYTES = 3 * 1024**3


def require(value, message):
    source.require(value, message)


def reference(path):
    path = source.fixture.safe_path(path, root=ROOT)
    return dict(path=str(path), sha256=source.sha(path))


def authenticated(reference_value):
    require(isinstance(reference_value, dict) and set(reference_value) == {'path', 'sha256'}, 'Invalid artifact reference')
    path = source.fixture.safe_path(Path(reference_value['path']), root=ROOT)
    require(source.sha(path) == reference_value['sha256'], 'Referenced artifact changed: ' + str(path))
    return path


def assignment_digest(manifest):
    return split.digest([{key: group[key] for key in ('group_id', 'split', 'seeds', 'target_slots')}
                         for group in manifest['groups']])


def _case(output, group, legacy):
    name = 'seed' + str(group['seeds']['source_generation'])
    common = dict(id=name, group_id=group['group_id'], split=group['split'], seed=group['seeds']['source_generation'])
    old = legacy[group['group_id']]
    require(all(old[key] == common[key] for key in common), 'Legacy role/seed/identity changed')
    if group['split'] != 'test':
        return dict(common, scene_directory=old['scene_directory'], replay_directory=old['replay_directory'],
                    origin='read_only_same_role_import', command=old['command'], audit_command=old['audit_command'])
    return dict(common, scene_directory=str(output/name/'scene'), replay_directory=str(output/name/'replay'),
                origin='prospective_test', command=source.command(output, common['seed']),
                audit_command=source.audit_command(output, common['seed']) + ['--profile', PROFILE])


def require_original_test_unseen(protocol):
    old = source.load(authenticated(protocol['legacy_source_protocol']))
    for row in old['cases']:
        if row['split'] == 'test':
            require(not Path(row['scene_directory']).parent.exists(), 'Original strict TEST source was already attempted')


def require_unseen_test(protocol):
    for row in protocol['cases']:
        if row['split'] == 'test':
            require(not Path(row['scene_directory']).parent.exists(), 'TEST source was already attempted')
    require_original_test_unseen(protocol)


def _windowed_import_audit(output, row, protocol):
    """New evidence lives here; an old failed audit is never overwritten."""
    directory = output/'import-audits'/row['group_id']; directory.mkdir(parents=True, mode=0o700)
    report = directory/'motion-audit.json'
    command = [sys.executable, str(validation.AUDITOR), '--scene', row['scene_directory'],
               '--replay', row['replay_directory'], '--output', str(report), '--profile', PROFILE]
    receipt = dict(command=command, status='failed', started_at=source.now())
    started = time.perf_counter()
    try:
        with (directory/'stdout.log').open('x') as stdout, (directory/'stderr.log').open('x') as stderr:
            result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    timeout=protocol['physical_audit_wall_budget_s'], umask=0o077)
        receipt.update(status='complete' if result.returncode == 0 else 'failed', returncode=result.returncode)
    except subprocess.TimeoutExpired:
        receipt.update(status='timeout')
    finally:
        receipt['elapsed_seconds'] = time.perf_counter()-started
        source.write(directory/'audit-execution.json', receipt)
    require(receipt['status'] == 'complete', 'New windowed physical audit failed; original evidence retained')
    return dict(report=reference(report), execution=reference(directory/'audit-execution.json'), command=command)


def prepare(freeze, legacy_directory, strict_study, original_auditor, output, *,
            original_primary=None, evaluation_id=DEFAULT_EVALUATION_ID):
    """Close legacy execution first, then import all40 in their original roles.

    Failed imports remain recorded. This function must finish before fitting and
    authenticates both old and new evidence rather than changing old gate rules.
    """
    freeze = source.fixture.safe_path(freeze, root=ROOT/'results')
    legacy_directory = source.fixture.safe_path(legacy_directory, root=ROOT/'results')
    strict_study = source.fixture.safe_path(strict_study, root=ROOT/'results')
    old = source.load(legacy_directory/'protocol.json')
    require(source.sha(legacy_directory/'protocol.json') == (legacy_directory/'protocol.sha256').read_text().strip(), 'Legacy source protocol changed')
    require(old['schema'] == 'ump.urban-primary-source-protocol.v1', 'Require original strict source protocol')
    require(Path(old['freeze_directory']) == freeze, 'Legacy dataset directory differs')
    manifest = source.load(freeze/'manifest.json'); split.validate_manifest(manifest)
    require(source.sha(freeze/'manifest.json') == old['manifest_sha256'], 'Original dataset manifest changed')
    for path, expected in old['frozen_manifest_files_sha256'].items():
        require(source.sha(path) == expected, 'Immutable original dataset artifact changed')
    strict_protocol_path = strict_study/'protocol.json'
    strict_protocol = source.load(strict_protocol_path)
    require(source.sha(strict_protocol_path) == (strict_study/'protocol.sha256').read_text().strip()
            and strict_protocol.get('schema') == 'ump.urban-primary-execution.v1'
            and strict_protocol.get('source_directory') == str(legacy_directory)
            and strict_protocol.get('source_protocol_sha256') == source.sha(legacy_directory/'protocol.json')
            and strict_protocol.get('freeze_directory') == str(freeze)
            and strict_protocol.get('manifest_sha256') == old['manifest_sha256'], 'Strict closure belongs to another dataset/source study')
    closure_path = strict_study/'driver-failed.json'
    closure = source.load(closure_path)
    require(closure.get('status') == 'failed_or_interrupted'
            and closure.get('completed') == ['source_train_cal'], 'Strict all40 source phase must close before amendment')
    gate = source.load(strict_study/'train-cal-driver-source-gate.json')
    require(gate.get('status') == 'failed' and gate.get('expected') == gate.get('observed') == 40,
            'Original strict all40 source gate not closed')
    require(not any((strict_study/'groups').iterdir()) and not (strict_study/'models.json').exists()
            and not (strict_study/'models-lock.json').exists(), 'Original strict evaluation already used mechanism/model data')
    original_auditor = source.fixture.safe_path(original_auditor, root=ROOT/'results')
    require(source.sha(original_auditor) == old['frozen_files_sha256'][str(validation.AUDITOR)], 'Original auditor bytes not authenticated')
    approved_archives = {str(validation.AUDITOR): reference(original_auditor)}
    primary_path = ROOT/'tools/evaluation/run_urban_privacy_primary.py'
    if original_primary is not None:
        original_primary = source.fixture.safe_path(original_primary, root=ROOT/'results')
        require(source.sha(original_primary) == old['frozen_files_sha256'][str(primary_path)], 'Original generic primitive bytes not authenticated')
        approved_archives[str(primary_path)] = reference(original_primary)
    # Only two reviewed, default-compatible hooks may differ from the old map:
    # explicit physical profile and pair-selector injection. Preserve old bytes.
    for name, expected in old['frozen_files_sha256'].items():
        if name not in approved_archives:
            require(source.sha(name) == expected, 'Unapproved original source dependency change: ' + name)
    old_cases = {row['group_id']: row for row in old['cases']}
    require(len(old_cases) == 72 and set(old_cases) == {g['group_id'] for g in manifest['groups']}, 'Legacy group family incomplete')
    for group in manifest['groups']:
        row = old_cases[group['group_id']]
        if group['split'] == 'test':
            require(not Path(row['scene_directory']).parent.exists(), 'Original TEST source has been attempted')
        else:
            require((Path(row['scene_directory']).parent/'private-source-summary.json').is_file(), 'All40 original attempts required')
    output = source.fixture.new_output(output)
    (output/'receipts').mkdir(mode=0o700)
    frozen = {name: source.sha(name) for name in old['frozen_files_sha256']}
    for path in sorted((ROOT/'tools/evaluation').glob('*.py')):
        frozen[str(path)] = source.sha(path)
    protocol = deepcopy(old)
    protocol.update(schema=SCHEMA, source_validation_profile=PROFILE, evaluation_id=evaluation_id,
        prepared_at=source.now(), output_directory=str(output), freeze_directory=str(freeze),
        dataset_manifest_sha256=old['manifest_sha256'], dataset_assignment_sha256=assignment_digest(manifest),
        # Legacy manifest_sha256 remains the DATASET namespace. New model locks
        # bind evaluation_manifest_sha256 separately; there is no circular hash.
        manifest_sha256=old['manifest_sha256'], frozen_files_sha256=frozen,
        cases=[_case(output, group, old_cases) for group in manifest['groups']],
        legacy_source_protocol=reference(legacy_directory/'protocol.json'), original_auditor=reference(original_auditor),
        original_dependency_archives=approved_archives,
        strict_study_protocol=reference(strict_protocol_path), strict_closure=reference(closure_path),
        strict_source_gate=reference(strict_study/'train-cal-driver-source-gate.json'),
        legacy_physical_audits={}, windowed_physical_audits={},
        source_unit='All recorded contributions of one operational track in [0,300000); unfinished movement is separate quality.',
        minimum_free_bytes=MIN_FREE_BYTES,
        scope='40 read-only same-role imports and32 prospective TEST captures; no repair, retry, replacement or quality selection.')
    require_unseen_test(protocol)
    # Decide evidence origin from the actual old audit. A successful legacy pass
    # keeps its original provenance. A missing/failed report gets NEW full physics
    # execution; that execution is not allowed to waive a hard physical failure.
    audit_errors = {}
    for row in protocol['cases']:
        if row['split'] == 'test': continue
        try:
            directory = Path(row['scene_directory']).parent
            proof_sha = source.sha(Path(row['replay_directory'])/'capture-proof.json')
            audit_path = directory/'motion-audit.json'; execution_path = directory/'audit-execution.json'
            audit = source.load(audit_path) if audit_path.is_file() else {}
            execution = source.load(execution_path) if execution_path.is_file() else {}
            if audit.get('status') == 'pass' and execution.get('status') == 'complete' and execution.get('returncode') == 0:
                protocol['legacy_physical_audits'][proof_sha] = dict(report=reference(audit_path), execution=reference(execution_path),
                    producer_protocol=protocol['legacy_source_protocol'], archived_auditor=protocol['original_auditor'])
            else:
                protocol['windowed_physical_audits'][proof_sha] = _windowed_import_audit(output, row, protocol)
        except Exception as error:
            audit_errors[row['group_id']] = str(error)
    ledger = dict(schema=LEDGER_SCHEMA, evaluation_id=evaluation_id, source_validation_profile=PROFILE,
        dataset_manifest_sha256=old['manifest_sha256'], dataset_assignment_sha256=protocol['dataset_assignment_sha256'],
        imported_count=40, prospective_test_count=32, cases=[])
    for row in protocol['cases']:
        if row['split'] == 'test': continue
        original_receipt_path = Path(row['scene_directory']).parent/'private-source-summary.json'
        item = {key: row[key] for key in ('id','group_id','split','seed','scene_directory','replay_directory','origin')}
        item.update(origin_strict_status=None, original_receipt=reference(original_receipt_path))
        try:
            origin = source.load(original_receipt_path)
            require(all(origin.get(key) == row[key] for key in ('id','group_id','seed','scene_directory','replay_directory')), 'Original receipt identity mismatch')
            require(origin.get('split',row['split'])==row['split'] and isinstance(origin.get('status'),str), 'Original receipt role/status mismatch')
            item['origin_strict_status'] = origin['status']
            require(row['group_id'] not in audit_errors, 'Physical evidence preparation failed: '+audit_errors.get(row['group_id'], ''))
            item.update(validation.validate_capture(row, protocol))
            data = source.load(Path(row['replay_directory'])/'observations.json')
            item['normalized_source_fingerprint_v2'] = split.normalized_fingerprint(data)
        except Exception as error:
            item.update(status='invalid', error=str(error))
        path = output/'receipts'/(row['group_id']+'.json'); source.write(path,item)
        ledger['cases'].append(dict(group_id=row['group_id'], split=row['split'], origin_strict_status=item['origin_strict_status'],
                                   status=item['status'], receipt=reference(path)))
        print('import_done group='+row['group_id']+' status='+item['status'], flush=True)
    ledger['status'] = 'verified' if all(item['status']=='verified' for item in ledger['cases']) else 'incomplete'
    source.write(output/'import-ledger.json', ledger)
    protocol['import_ledger'] = reference(output/'import-ledger.json')
    source.write(output/'protocol.json', protocol)
    source.fixture.write_new(output/'protocol.sha256', (source.sha(output/'protocol.json')+'\n').encode())
    snapshot(output, summarize(output, protocol, manifest, verify=False))
    return output


def read_protocol(output):
    output = source.fixture.safe_path(output, root=ROOT/'results')
    protocol = source.load(output/'protocol.json')
    require(source.sha(output/'protocol.json') == (output/'protocol.sha256').read_text().strip(), 'Windowed source protocol changed')
    require(protocol.get('schema') == SCHEMA and protocol.get('source_validation_profile') == PROFILE
            and protocol.get('output_directory') == str(output), 'Explicit windowed source schema/profile required')
    for path, expected in protocol['frozen_manifest_files_sha256'].items():
        require(source.sha(path) == expected, 'Original immutable dataset artifact changed')
    manifest = source.load(Path(protocol['freeze_directory'])/'manifest.json')
    split.validate_manifest(manifest)
    require(source.sha(Path(protocol['freeze_directory'])/'manifest.json') == protocol['dataset_manifest_sha256'] == protocol['manifest_sha256']
            and assignment_digest(manifest) == protocol['dataset_assignment_sha256'], 'Dataset assignment binding changed')
    old = source.load(authenticated(protocol['legacy_source_protocol']))
    require_original_test_unseen(protocol)
    for name, archive in protocol['original_dependency_archives'].items():
        require(source.sha(authenticated(archive)) == old['frozen_files_sha256'][name], 'Archived original dependency changed')
    expected = [_case(output,g,{c['group_id']:c for c in old['cases']}) for g in manifest['groups']]
    require(protocol['cases'] == expected, 'Windowed source paths/roles/seeds changed')
    strict_protocol=source.load(authenticated(protocol['strict_study_protocol']))
    require(strict_protocol.get('source_protocol_sha256')==protocol['legacy_source_protocol']['sha256']
            and strict_protocol.get('manifest_sha256')==protocol['dataset_manifest_sha256']
            and strict_protocol.get('freeze_directory')==protocol['freeze_directory'], 'Strict closure provenance differs')
    authenticated(protocol['strict_closure']); authenticated(protocol['strict_source_gate']); authenticated(protocol['original_auditor'])
    ledger = source.load(authenticated(protocol['import_ledger']))
    require(ledger.get('schema') == LEDGER_SCHEMA and ledger.get('evaluation_id') == protocol['evaluation_id']
            and ledger.get('source_validation_profile') == PROFILE
            and ledger.get('dataset_manifest_sha256') == protocol['dataset_manifest_sha256']
            and ledger.get('dataset_assignment_sha256') == protocol['dataset_assignment_sha256'], 'Import ledger belongs to another contract')
    expected_imports = [(g['group_id'], g['split']) for g in manifest['groups'] if g['split'] != 'test']
    require([(c['group_id'],c['split']) for c in ledger['cases']] == expected_imports
            and ledger.get('imported_count') == 40 and ledger.get('prospective_test_count') == 32, 'All40 same-role imports required')
    for item in ledger['cases']: authenticated(item['receipt'])
    required_dependencies=set(source.source_paths(Path(protocol['historical_scene'])))
    required_dependencies.update((ROOT/'tools/evaluation').glob('*.py'))
    required_dependencies.add(Path(protocol['simulator_path']))
    require({str(path) for path in required_dependencies} <= set(protocol['frozen_files_sha256']), 'Incomplete source/evaluation dependency freeze')
    source.frozen_check(protocol)
    return output, protocol, manifest


def summarize(output, protocol, manifest, *, verify=True):
    ledger = source.load(authenticated(protocol['import_ledger']))
    imports = {item['group_id']: item for item in ledger['cases']}
    cases=[]; seen={}
    excluded={item.get(key) for item in manifest['exclusions'] for key in
              ('observations_sha256','normalized_source_fingerprint','normalized_source_fingerprint_v2')}
    excluded_routes={item.get('planned_route_fingerprint') for item in manifest['exclusions']}
    for row in protocol['cases']:
        item = {key: row[key] for key in ('id','group_id','split','seed','scene_directory','replay_directory','origin')}
        reference_value = imports.get(row['group_id'],{}).get('receipt')
        path = authenticated(reference_value) if reference_value else output/row['id']/'private-source-summary.json'
        if not path.is_file():
            item['status']='interrupted' if path.parent.exists() else 'not_attempted'
        else:
            saved=source.load(path)
            require(all(saved.get(k)==row[k] for k in ('id','group_id','split','seed','scene_directory','replay_directory','origin')), 'Windowed receipt identity/role mismatch')
            item.update(saved)
            if item['status']=='verified':
                try:
                    if 'original_receipt' in item: authenticated(item['original_receipt'])
                    if verify:
                        actual=validation.validate_capture(row,protocol)
                        require(all(item.get(key)==value for key,value in actual.items()), 'Windowed receipt differs from actual capture')
                        data=source.load(Path(row['replay_directory'])/'observations.json')
                        require(split.normalized_fingerprint(data)==item['normalized_source_fingerprint_v2'], 'Source fingerprint changed')
                    require(not ({item['observations_sha256'], item['normalized_source_fingerprint'], item['normalized_source_fingerprint_v2']} & excluded)
                            and item['planned_route_fingerprint'] not in excluded_routes, 'Source overlaps historical/DEV exclusion')
                    for field in ('normalized_source_fingerprint_v2','planned_route_fingerprint'):
                        key=(field,item[field])
                        if key in seen:
                            item['status']='invalid_duplicate';seen[key]['status']='invalid_duplicate'
                        else: seen[key]=item
                except Exception as error: item.update(status='invalid',error=str(error))
        cases.append(item)
    return dict(schema='ump.observed-track-window-source-summary.v1', evaluation_id=protocol['evaluation_id'], source_validation_profile=PROFILE,
        manifest_sha256=protocol['manifest_sha256'], dataset_manifest_sha256=protocol['dataset_manifest_sha256'],
        planned_count=72, imported_count=40, prospective_test_count=32,
        attempted_count=sum(c['status']!='not_attempted' for c in cases), verified_count=sum(c['status']=='verified' for c in cases),
        by_split={name:dict(Counter(c['status'] for c in cases if c['split']==name)) for name in ('train','calibration','test')},
        status='verified' if all(c['status']=='verified' for c in cases) else 'incomplete', cases=cases)


def snapshot(output, summary):
    name='source-summary-'+source.now().replace(':','').replace('+','_')+'.json'
    source.write(output/name,summary)
    print('windowed_source_snapshot='+name+' verified='+str(summary['verified_count'])+'/72',flush=True)


def attempt(output, protocol, row):
    """One prospective native attempt; only validation differs from strict helper."""
    require(row['origin']=='prospective_test' and row['split']=='test', 'Only prospective TEST may generate a source')
    source.frozen_check(protocol)
    directory=output/row['id'];require(not directory.exists(),'No retry/overwrite of a TEST source');directory.mkdir(mode=0o700)
    source.write(directory/'attempt.json',dict(schema='ump.observed-track-window-source-attempt.v1',started_at=source.now(),
                 protocol_sha256=source.sha(output/'protocol.json'),command=row['command'],seed=row['seed']))
    started=time.perf_counter();receipt=dict(status='failed',started_at=source.now())
    try:
        with (directory/'stdout.log').open('x') as stdout,(directory/'stderr.log').open('x') as stderr:
            process=subprocess.Popen(row['command'],cwd=ROOT,stdout=stdout,stderr=stderr,start_new_session=True,umask=0o077)
            try:
                code=process.wait(timeout=protocol['process_wall_budget_s'])
                receipt.update(status='complete' if code==0 else 'failed',returncode=code)
            except subprocess.TimeoutExpired:
                source.stop_owned_group(process);receipt.update(status='timeout',returncode=process.returncode)
            except BaseException:
                source.stop_owned_group(process);receipt.update(status='interrupted',returncode=process.returncode);raise
    finally:
        receipt.update(elapsed_seconds=time.perf_counter()-started,finished_at=source.now());source.write(directory/'execution.json',receipt)
    item={key:row[key] for key in ('id','group_id','split','seed','scene_directory','replay_directory','origin')}
    item.update(status=receipt['status'],execution=receipt)
    if receipt['status']=='complete':
        try:
            source.frozen_check(protocol);source.run_physical_audit(output,protocol,row)
            item.update(validation.validate_capture(row,protocol))
            item['normalized_source_fingerprint_v2']=split.normalized_fingerprint(source.load(Path(row['replay_directory'])/'observations.json'))
        except Exception as error:item.update(status='invalid',error=str(error))
    source.write(directory/'private-source-summary.json',item)
    return item


def capture_test(output, evaluation_output, *, limit=None):
    import run_urban_track_window_primary as primary
    output,protocol,manifest=read_protocol(output)
    lock=primary.authenticate_test_gate(evaluation_output)
    require(lock.get('source_protocol_sha256')==source.sha(output/'protocol.json'), 'Model lock belongs to another source profile/protocol')
    summary=summarize(output,protocol,manifest)
    imports=[item for item in summary['cases'] if item['split']!='test']
    require(len(imports)==40 and all(item['status']=='verified' for item in imports), 'All40 hard-valid imports required before TEST')
    snapshot(output,summary);attempts=0
    for row in protocol['cases']:
        if row['split']!='test' or (output/row['id']).exists():continue
        if limit is not None and attempts>=limit:break
        require(shutil.disk_usage(output).free>=protocol['minimum_free_bytes'],'Less than3GiB free; stop before new TEST capture')
        require_original_test_unseen(protocol)
        current_lock=primary.authenticate_test_gate(evaluation_output)
        require(current_lock.get('source_protocol_sha256')==source.sha(output/'protocol.json'), 'Per-attempt model lock belongs to another source protocol')
        print('windowed_source_start group='+row['group_id'],flush=True)
        result=attempt(output,protocol,row);attempts+=1
        print('windowed_source_done group='+row['group_id']+' status='+result['status'],flush=True)
        snapshot(output,summarize(output,protocol,manifest,verify=False))
    snapshot(output,summarize(output,protocol,manifest))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',type=Path);action.add_argument('--capture-test',type=Path);action.add_argument('--verify',type=Path)
    parser.add_argument('--freeze',type=Path);parser.add_argument('--legacy-sources',type=Path);parser.add_argument('--strict-study',type=Path)
    parser.add_argument('--original-auditor',type=Path);parser.add_argument('--original-primary',type=Path);parser.add_argument('--evaluation',type=Path);parser.add_argument('--limit',type=int)
    args=parser.parse_args(argv)
    if args.prepare:
        require(all((args.freeze,args.legacy_sources,args.strict_study,args.original_auditor)), 'Prepare requires frozen dataset, legacy sources/closed study and original auditor')
        print(prepare(args.freeze,args.legacy_sources,args.strict_study,args.original_auditor,args.prepare,original_primary=args.original_primary));return
    output=args.capture_test or args.verify
    output=source.fixture.safe_path(output,root=ROOT/'results')
    descriptor=os.open(output/'.running.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.capture_test:
            require(args.evaluation is not None,'TEST requires new evaluation/model lock');capture_test(output,args.evaluation,limit=args.limit)
        else:
            output,protocol,manifest=read_protocol(output);snapshot(output,summarize(output,protocol,manifest))
    finally:os.close(descriptor)


if __name__=='__main__':
    signal.signal(signal.SIGTERM,source.terminate_requested)
    main()
