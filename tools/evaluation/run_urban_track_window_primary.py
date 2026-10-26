#!/usr/bin/env python3
"""Explicit track-window evaluation over immutable dataset assignments.

Imports all40 same-role recordings, keeps quality outside predictors/enrollment,
uses unchanged primitive/math helpers, and binds a NEW evaluation/profile/ledger
before model locks and prospective TEST. Legacy end-to-end dispatch is not used.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import fcntl
import importlib
import inspect
import os
from pathlib import Path

import run_urban_privacy_primary as primary
import track_window_source_validation as validation

ROOT = primary.ROOT
PROFILE = validation.PROFILE
SCHEMA = 'ump.urban-track-window-execution.v1'
EVALUATION_SCHEMA = 'ump.urban-track-window-evaluation.v1'
SUPPLEMENT_SCHEMA = 'ump.urban-track-window-implementation.v1'
LOCK_SCHEMA = 'ump.urban-track-window-model-lock.v1'
REPORT_SCHEMA = 'ump.urban-track-window-report.v1'
SIDECAR_SCHEMA = 'ump.urban-track-window-group-evaluation.v1'
UNIT_VALIDATION_SCHEMA = 'ump.observed-track-window-unit-validation.v1'
DEV_VALIDATION_SCHEMA = 'ump.observed-track-window-dev-validation.v1'
REQUIRED_UNIT_MODULES = frozenset(('test_run_urban_track_window_primary','test_run_urban_track_window_sources',
    'test_track_window_source_validation','test_run_urban_privacy_primary','test_urban_privacy_analysis',
    'test_urban_privacy_statistics','test_urban_privacy_queries','test_report_urban_track_window_primary'))
CONTRACT_PATH = Path('docs/PRIVACY_TRACK_WINDOW_CONTRACT_2026-10-26.md')
UNCHANGED_BLOCKS = ('group_counts','targets_per_recording','conditions','methods','analysis_protocol','resource_limits')
WINDOW_SECRET = 'Inclusion of every recorded contribution of one original operational observation-track ID within[0,300000); not full episode completion, physical absence, person identity or all episodes of a person.'
WINDOW_AUXILIARY = 'Exact seeded retrospective sample over all recorded in-window observations of the selected operational track; auxiliary_selection role seed; identical bytes in IN and OUT.'
PROFILE_DEFINITION = {
    'source_validation_profile': PROFILE, 'source_protocol_schema': validation.PROTOCOL_SCHEMA,
    'protected_unit': 'Every recorded contribution of one original operational track ID in [0,300000).',
    'window_ms': [0, 300000], 'minimum_target_observations': 2,
    'auxiliary': 'Unchanged exact retrospective ceil(n/4) sampling over the full recorded in-window trace.',
    'quality': 'Active/pending/stalled and movement coverage are reported without cohort or target filtering.',
    'integrity': 'Full raw/GT/sensor/clock/identity and hard physical integrity remain required.',
}
NEW_FILES = tuple('tools/evaluation/' + name for name in (
    'run_urban_track_window_primary.py', 'test_run_urban_track_window_primary.py',
    'run_urban_track_window_sources.py', 'test_run_urban_track_window_sources.py',
    'track_window_source_validation.py', 'test_track_window_source_validation.py'))


def require(value, message):
    primary.require(value, message)


def sources():
    # Source TEST capture imports this module only at its explicit model gate.
    return importlib.import_module('run_urban_track_window_sources')


def reference(path):
    path = primary.fixture.safe_path(Path(path), root=ROOT)
    return dict(path=str(path), sha256=primary.source.sha(path))


def authenticated(value):
    require(isinstance(value, dict) and set(value) == {'path', 'sha256'}, 'Invalid artifact reference')
    path = primary.fixture.safe_path(Path(value['path']), root=ROOT)
    require(primary.source.sha(path) == value['sha256'], 'Referenced artifact changed: ' + str(path))
    return path


def assignment_digest(manifest):
    return primary.split.digest([{k: g[k] for k in ('group_id', 'split', 'seeds', 'target_slots')}
                                 for g in manifest['groups']])


def select_window_pair(data, source_sha, group):
    require(data.get('end_ms') == 300000, 'Track-window horizon differs')
    absent, knowledge, selection = primary.select_pair(data, source_sha, group)
    selection = deepcopy(selection)
    selection['eligible_observed_tracks'] = selection.pop('eligible_episodes')
    selection.update(source_validation_profile=PROFILE,
                     source_unit='All recorded contributions of the selected operational track in [0,300000).')
    return absent, knowledge, selection


def require_pair_injection():
    require('pair_selector' in inspect.signature(primary.process_group).parameters,
            'Reviewed explicit pair_selector hook must be applied after strict batch closure')


def expected_groups(manifest):
    return {role: sorted(g['group_id'] for g in manifest['groups'] if g['split'] == role)
            for role in ('train', 'calibration', 'test')}


def resolved_attack_protocol(design):
    value = deepcopy(design['attack_protocol'])
    value['secret'] = WINDOW_SECRET
    value['auxiliary']['acquisition'] = WINDOW_AUXILIARY
    return value


def scientific_block_hashes(design):
    return {name:primary.split.digest(design[name]) for name in UNCHANGED_BLOCKS}


def _source_contract(protocol, manifest):
    require(protocol.get('schema') == validation.PROTOCOL_SCHEMA
            and protocol.get('source_validation_profile') == PROFILE, 'Explicit windowed source schema/profile required')
    primary.split.identifier(protocol.get('evaluation_id'), 'evaluation ID')
    require(protocol.get('manifest_sha256') == protocol.get('dataset_manifest_sha256')
            and protocol.get('dataset_assignment_sha256') == assignment_digest(manifest), 'Dataset binding differs')
    ledger = primary.source.load(authenticated(protocol['import_ledger']))
    require(ledger.get('schema') == 'ump.observed-track-window-import-ledger.v1'
            and ledger.get('evaluation_id') == protocol['evaluation_id']
            and ledger.get('source_validation_profile') == PROFILE
            and ledger.get('dataset_manifest_sha256') == protocol['dataset_manifest_sha256']
            and ledger.get('dataset_assignment_sha256') == protocol['dataset_assignment_sha256'], 'Import ledger contract differs')
    wanted = [(g['group_id'], g['split']) for g in manifest['groups'] if g['split'] != 'test']
    require(ledger.get('imported_count') == 40 and ledger.get('prospective_test_count') == 32
            and [(c['group_id'], c['split']) for c in ledger.get('cases', [])] == wanted
            and ledger.get('status') == 'verified'
            and all(c['status'] == 'verified' for c in ledger['cases']), 'All40 hard-valid same-role imports required')
    return ledger


def _bindings(protocol):
    value = {k: protocol[k] for k in ('evaluation_id', 'source_validation_profile', 'source_profile_sha256',
        'dataset_manifest_sha256', 'dataset_assignment_sha256', 'evaluation_manifest_sha256',
        'source_protocol_sha256', 'import_ledger_sha256')}
    # Derived only after protocol.json is written: no circular hash field inside
    # the protocol, but every sidecar/supplement/model lock pins its exact bytes.
    value['execution_protocol_sha256'] = primary.source.sha(Path(protocol['output_directory'])/'protocol.json')
    return value


def prepare(freeze, source_directory, output):
    require_pair_injection()
    freeze = primary.fixture.safe_path(Path(freeze), root=ROOT/'results')
    checked = primary.split.verify_freeze(freeze)
    source_directory, sp, manifest = sources().read_protocol(source_directory)
    require(sp['dataset_manifest_sha256'] == checked['manifest_sha256']
            and Path(sp['freeze_directory']) == freeze, 'Source and original dataset differ')
    _source_contract(sp, manifest)
    sources().require_unseen_test(sp)
    output = primary.fixture.new_output(Path(output))
    (output/'groups').mkdir(mode=0o700)
    evaluation = dict(schema=EVALUATION_SCHEMA, evaluation_id=sp['evaluation_id'], source_validation_profile=PROFILE,
        dataset_manifest=reference(freeze/'manifest.json'), dataset_study_id=manifest['design']['study_id'],
        dataset_master_seed=manifest['design']['master_seed'], dataset_assignment_sha256=assignment_digest(manifest),
        source_protocol=reference(source_directory/'protocol.json'), import_ledger=deepcopy(sp['import_ledger']),
        profile_definition=deepcopy(PROFILE_DEFINITION), source_profile_sha256=primary.split.digest(PROFILE_DEFINITION),
        contract=reference(ROOT/CONTRACT_PATH), resolved_attack_protocol=resolved_attack_protocol(manifest['design']),
        unchanged_scientific_blocks=scientific_block_hashes(manifest['design']),
        declared_attack_deltas=['secret','auxiliary.acquisition'],
        group_counts=manifest['design']['group_counts'], same_role_imports=40, prospective_TEST_slots=32,
        scientific_protocol='Policy/method/features/fit/CAL/statistics/queries/availability unchanged; only the declared in-window unit/source profile differs.')
    primary.write(output/'evaluation-manifest.json', evaluation)
    files = set(primary.IMPLEMENTATION_FILES) | set(NEW_FILES)
    files.update(item['path'] for item in manifest['design']['generator']['evidence_files']
                 if item['path'].startswith('tools/evaluation/') and item['path'].endswith('.py'))
    protocol = dict(schema=SCHEMA, prepared_at=primary.source.now(), output_directory=str(output),
        freeze_directory=str(freeze), source_directory=str(source_directory), evaluation_id=sp['evaluation_id'],
        source_validation_profile=PROFILE, source_profile_sha256=evaluation['source_profile_sha256'],
        dataset_manifest_sha256=checked['manifest_sha256'], dataset_assignment_sha256=assignment_digest(manifest),
        evaluation_manifest_sha256=primary.source.sha(output/'evaluation-manifest.json'),
        source_protocol_sha256=primary.source.sha(source_directory/'protocol.json'), import_ledger=deepcopy(sp['import_ledger']),
        import_ledger_sha256=sp['import_ledger']['sha256'],
        implementation_files_sha256={name:primary.source.sha(ROOT/name) for name in sorted(files)},
        native_binary_sha256=primary.source.sha(ROOT/'simulator/build/AggregationReplay'),
        native_wall_budget_s=180, audit_max_cells=1000000, minimum_free_bytes=primary.sources.MIN_FREE_BYTES,
        availability='final_snapshot_at_horizon',
        failure_rule='One attempt, all40/all32 hard-integrity gates, no old-scope promotion, quality filtering, retries or replacement.',
        archival='Unchanged verified lossless archives; retain every failed/incomplete method outcome.')
    primary.write(output/'protocol.json', protocol)
    primary.fixture.write_new(output/'protocol.sha256',(primary.source.sha(output/'protocol.json')+'\n').encode())
    return output


def authenticate_protocol(output):
    output = primary.fixture.safe_path(Path(output), root=ROOT/'results')
    p = primary.source.load(output/'protocol.json')
    require(p.get('schema') == SCHEMA and p.get('output_directory') == str(output)
            and p.get('source_validation_profile') == PROFILE
            and primary.source.sha(output/'protocol.json') == (output/'protocol.sha256').read_text().strip(), 'Windowed execution protocol differs')
    require(primary.source.sha(output/'evaluation-manifest.json') == p['evaluation_manifest_sha256'], 'Evaluation manifest changed')
    evaluation = primary.source.load(output/'evaluation-manifest.json')
    require(evaluation.get('schema') == EVALUATION_SCHEMA and evaluation.get('evaluation_id') == p['evaluation_id']
            and evaluation.get('source_validation_profile') == PROFILE
            and evaluation.get('profile_definition') == PROFILE_DEFINITION
            and evaluation.get('source_profile_sha256') == p['source_profile_sha256'] == primary.split.digest(PROFILE_DEFINITION),
            'Evaluation/profile definition differs')
    _, sp, manifest = sources().read_protocol(Path(p['source_directory']))
    _source_contract(sp, manifest)
    authenticated(evaluation['contract'])
    require(evaluation['contract'] == reference(ROOT/CONTRACT_PATH)
            and evaluation.get('resolved_attack_protocol') == resolved_attack_protocol(manifest['design'])
            and evaluation.get('unchanged_scientific_blocks') == scientific_block_hashes(manifest['design'])
            and evaluation.get('declared_attack_deltas') == ['secret','auxiliary.acquisition'],
            'Evaluation scientific amendment differs from deterministic two-text delta')
    require(sp['evaluation_id'] == p['evaluation_id']
            and sp['dataset_manifest_sha256'] == p['dataset_manifest_sha256']
            and sp['dataset_assignment_sha256'] == p['dataset_assignment_sha256']
            and primary.source.sha(Path(p['source_directory'])/'protocol.json') == p['source_protocol_sha256']
            and sp['import_ledger'] == p['import_ledger']
            and sp['import_ledger']['sha256'] == p['import_ledger_sha256'], 'Source/evaluation/import binding differs')
    require(reference(authenticated(evaluation['dataset_manifest']))['sha256'] == p['dataset_manifest_sha256']
            and evaluation['source_protocol'] == reference(Path(p['source_directory'])/'protocol.json')
            and evaluation['import_ledger'] == p['import_ledger'], 'Evaluation artifact references differ')
    for name, expected in p['implementation_files_sha256'].items():
        require(primary.source.sha(ROOT/name) == expected, 'Windowed implementation changed: '+name)
    require(primary.source.sha(ROOT/'simulator/build/AggregationReplay') == p['native_binary_sha256'], 'Replay binary changed')
    return output, p, manifest


def cohort_gate(protocol, manifest, roles, *, verify_sources=True):
    source_dir, sp, actual_manifest = sources().read_protocol(Path(protocol['source_directory']))
    require(assignment_digest(actual_manifest) == assignment_digest(manifest), 'Source assignment differs')
    summary = sources().summarize(source_dir, sp, actual_manifest, verify=verify_sources)
    require(summary.get('evaluation_id') == protocol['evaluation_id']
            and summary.get('source_validation_profile') == PROFILE, 'Source summary has another evaluation/profile')
    wanted = {g['group_id'] for g in manifest['groups'] if g['split'] in roles}
    selected = [c for c in summary['cases'] if c['split'] in roles]
    require(len(selected) == len(wanted) and {c['group_id'] for c in selected} == wanted
            and all(c['status'] == 'verified' and c.get('validation_profile') == PROFILE for c in selected),
            'Incomplete hard-valid source family; no mechanism or fitting phase allowed')
    groups = {g['group_id']:g for g in manifest['groups']}
    for case in selected:
        group = groups[case['group_id']]
        require(case['split'] == group['split'] and case['seed'] == group['seeds']['source_generation'], 'Source role/seed changed')
    return summary


def _case_digest(case):
    return primary.split.digest({k:case[k] for k in ('group_id','split','seed','observations_sha256',
        'capture_proof_sha256','validation_profile','checks','movement_quality')})


def collect(output, protocol, manifest, source_summary, *, verify_archives=False):
    rows, summaries = primary.collect(output, manifest, verify_archives=verify_archives)
    cases = {c['group_id']:c for c in source_summary['cases']}
    for summary in summaries:
        directory = output/'groups'/summary['group_id']
        if not (directory/'summary.json').is_file():
            continue
        require((directory/'window-evaluation-receipt.json').is_file(), 'Windowed evaluation sidecar missing')
        side = primary.source.load(directory/'window-evaluation-receipt.json')
        require(side.get('schema') == SIDECAR_SCHEMA and side.get('binding') == _bindings(protocol)
                and side.get('group_id') == summary['group_id'] and side.get('split') == summary['split'], 'Old/wrong evaluation group sidecar')
        require(side['summary_sha256'] == primary.source.sha(directory/'summary.json')
                and side['rows_sha256'] == summary['rows']['sha256']
                and side['source_validation_sha256'] == _case_digest(cases[summary['group_id']]), 'Group/source/rows provenance differs')
    return rows, summaries


def run(output, roles, *, limit=None):
    output, p, manifest = authenticate_protocol(output)
    require(roles and set(roles) <= {'train','calibration','test'} and (limit is None or type(limit) is int and limit > 0), 'Declare valid splits/limit')
    require_pair_injection()
    if 'test' in roles:
        authenticate_test_gate(output)
    # A limited run cannot turn the declared40/32 family gate into a subset gate.
    gate_roles = ['train','calibration'] if set(roles) & {'train','calibration'} else []
    if 'test' in roles:gate_roles.append('test')
    source_summary = cohort_gate(p, manifest, gate_roles)
    by_group = {c['group_id']:c for c in source_summary['cases']}
    completed = 0
    for group in manifest['groups']:
        if group['split'] not in roles or (output/'groups'/group['group_id']).exists():continue
        if limit is not None and completed >= limit:break
        case = by_group[group['group_id']]
        summary = primary.process_group(output, p, manifest, group, case, pair_selector=select_window_pair)
        directory = output/'groups'/group['group_id']
        primary.write(directory/'window-evaluation-receipt.json', dict(schema=SIDECAR_SCHEMA, binding=_bindings(p),
            group_id=group['group_id'], split=group['split'], source_validation_sha256=_case_digest(case),
            summary_sha256=primary.source.sha(directory/'summary.json'), rows_sha256=summary['rows']['sha256']))
        completed += 1
    rows, summaries = collect(output, p, manifest, source_summary)
    primary.write(output/('execution-summary-'+primary.source.now().replace(':','').replace('+','_')+'.json'),
        dict(schema=SCHEMA,evaluation_id=p['evaluation_id'],source_validation_profile=PROFILE,
             groups=summaries,rows=len(rows),scope='Observed-track-window; all quality remains separate.'))


def validate_validation_receipt(value, kind, protocol):
    schema = UNIT_VALIDATION_SCHEMA if kind == 'unit' else DEV_VALIDATION_SCHEMA
    require(value.get('schema') == schema and value.get('status') == 'verified'
            and value.get('test_data_seen') is False and value.get('evaluation_id') == protocol['evaluation_id']
            and value.get('source_validation_profile') == PROFILE
            and value.get('actual_primary_model_fits') is False, 'Wrong or unverified windowed validation receipt')
    combined = {}
    for field in ('files_sha256','implementation_files_sha256','full_code_sha256'):
        mapping = value.get(field, {})
        require(isinstance(mapping,dict), 'Invalid validation code hash map')
        for name, expected in mapping.items():
            path = primary.fixture.safe_path(Path(name) if Path(name).is_absolute() else ROOT/name,root=ROOT)
            normalized = str(path.relative_to(ROOT))
            require(normalized not in combined or combined[normalized] == expected, 'Conflicting validation code hashes')
            require(primary.source.sha(path) == expected, 'Validation receipt has stale code: '+normalized)
            combined[normalized] = expected
    require(combined and all(combined.get(name) == expected for name,expected in protocol['implementation_files_sha256'].items()),
            'Validation receipt does not cover actual execution code')
    if kind == 'unit':
        require(type(value.get('tests')) is int and value['tests'] >= 177
                and all(value.get(key) == 0 for key in ('failures','errors','skipped','native_jobs'))
                and REQUIRED_UNIT_MODULES <= set(value.get('modules', [])), 'Unit validation coverage incomplete')
    else:
        new, retained = value.get('new_native_cases'), value.get('retained_native_cases')
        require(type(new) is int and type(retained) is int and min(new,retained) >= 0 and new+retained == 18
                and value.get('derived_cases') == 4 and value.get('recipient_streams') == 22
                and value.get('methods') == 11 and value.get('query_count_per_world') == 19200
                and value.get('native_binary_sha256') == protocol['native_binary_sha256']
                and all(value.get(key) is True for key in ('archive_roundtrip_authenticated','raw_policy_audits_recomputed',
                    'regional_transcripts_recomposed','rows_recomputed')), 'DEV validation coverage/binary/audit differs')


def authenticate_supplement(output, protocol):
    path = output/'implementation-supplement.json'
    value = primary.source.load(path)
    require(value.get('schema') == SUPPLEMENT_SCHEMA and value.get('status') == 'verified_before_test'
            and value.get('binding') == _bindings(protocol)
            and value.get('files_sha256') == protocol['implementation_files_sha256'], 'Wrong windowed implementation supplement')
    require(len(value.get('test_receipts', [])) == 2, 'One unit and one DEV validation receipt required')
    for kind,item in zip(('unit','dev'),value['test_receipts']):
        validate_validation_receipt(primary.source.load(authenticated(item)),kind,protocol)
    return value


def freeze_implementation(output, unit_receipt, dev_receipt):
    output, p, manifest = authenticate_protocol(output)
    _, sp, _ = sources().read_protocol(Path(p['source_directory']))
    sources().require_unseen_test(sp)
    require(not any((output/'groups'/g['group_id']).exists() for g in manifest['groups'] if g['split']=='test'), 'TEST mechanisms already attempted')
    receipts, checked = [], []
    for kind,path in zip(('unit','dev'),(unit_receipt,dev_receipt)):
        path = primary.fixture.safe_path(Path(path), root=ROOT/'results')
        validate_validation_receipt(primary.source.load(path),kind,p)
        checked.append(path)
    for path in checked:
        target = output/path.name
        primary.fixture.write_new(target, primary.fixture.read_bytes(path)); receipts.append(reference(target))
    supplement = dict(schema=SUPPLEMENT_SCHEMA,status='verified_before_test',binding=_bindings(p),
                      files_sha256=p['implementation_files_sha256'],test_receipts=receipts)
    primary.write(output/'implementation-supplement.json', supplement)
    return supplement


def lock_models(output):
    output, p, manifest = authenticate_protocol(output)
    authenticate_supplement(output, p)
    _, sp, _ = sources().read_protocol(Path(p['source_directory']))
    sources().require_unseen_test(sp)
    source_summary = cohort_gate(p, manifest, ['train','calibration'])
    rows, summaries = collect(output, p, manifest, source_summary, verify_archives=True)
    relevant = [r for r in rows if r['split'] in ('train','calibration')]
    families = [s for s in summaries if s['split'] in ('train','calibration')]
    require(len(families)==40 and all(s['status']=='verified' for s in families), 'All40 paired families required')
    audit = primary.split.verify_actual_sources(manifest,[s['pair'] for s in families],ROOT)
    primary.write(output/'train-cal-split-audit.json',audit)
    models = primary.analysis.prepare_models(relevant,expected_groups=expected_groups(manifest),
                    method_ids=[m['id'] for m in manifest['design']['methods']])
    primary.analysis.validate_model_lock(models,relevant,require_complete=True)
    primary.write(output/'train-cal-rows.json',relevant); primary.write(output/'models.json',models)
    lock = dict(schema=LOCK_SCHEMA,status='locked_before_test',**_bindings(p),
        implementation_sha256=primary.source.sha(output/'implementation-supplement.json'),
        implementation_files_sha256=p['implementation_files_sha256'],group_counts={'train':24,'calibration':16},test_rows_seen=0,
        models=reference(output/'models.json'),data=reference(output/'train-cal-rows.json'))
    primary.write(output/'models-lock.json',lock)
    authenticate_test_gate(output)
    return lock


def authenticate_test_gate(output):
    output, p, manifest = authenticate_protocol(output)
    supplement = authenticate_supplement(output,p)
    value = primary.source.load(output/'models-lock.json')
    require(value.get('schema') == LOCK_SCHEMA and value.get('status') == 'locked_before_test'
            and all(value.get(k)==v for k,v in _bindings(p).items())
            and value.get('implementation_sha256') == primary.source.sha(output/'implementation-supplement.json')
            and value.get('implementation_files_sha256') == supplement['files_sha256']
            and value.get('group_counts') == {'train':24,'calibration':16}
            and value.get('test_rows_seen') == 0, 'Old or wrong evaluation/profile/model lock')
    models = primary.source.load(authenticated(value['models']))
    rows = primary.source.load(authenticated(value['data']))
    wanted = expected_groups(manifest)
    require(models.get('training_group_ids') == wanted['train'] and models.get('calibration_group_ids') == wanted['calibration']
            and set(models.get('expected_method_ids',[])) == {m['id'] for m in manifest['design']['methods']}
            and len(models.get('models',[])) == 22, 'Locked actual source/method family differs')
    require(isinstance(rows,list) and len(rows)==880
            and {r['group_id'] for r in rows} == set(wanted['train']+wanted['calibration'])
            and all(r['split'] in ('train','calibration') for r in rows), 'Actual880 TRAIN/CAL rows required')
    # Full raw source/archive verification is done at lock creation and final
    # report. Repeated TEST-capture gates authenticate immutable receipt/code
    # bindings, all40 statuses, actual rows/sidecars and the actual model bundle.
    source_summary = cohort_gate(p,manifest,['train','calibration'],verify_sources=False)
    current_rows, summaries = collect(output,p,manifest,source_summary,verify_archives=False)
    require(primary.analysis.digest([r for r in current_rows if r['split'] in ('train','calibration')])
            == primary.analysis.digest(rows), 'Locked rows differ from current evaluated groups')
    primary.analysis.validate_model_lock(models,rows,require_complete=True)
    return value


def source_quality(cases, manifest):
    result = dict(source_validation_profile=PROFILE,quality_filters_enrollment=False,by_split={})
    for role in ('train','calibration','test'):
        selected = [c for c in cases if c['split']==role]
        planned = sum(g['split']==role for g in manifest['groups'])
        quality = [c['movement_quality'] for c in selected if isinstance(c.get('movement_quality'),dict) and c['movement_quality']]
        def count(getter):
            values = [getter(q) for q in quality]
            return sum(value>0 for value in values) if len(values)==planned and all(type(v) is int for v in values) else None
        result['by_split'][role] = dict(planned_sources=planned,verified_sources=sum(c['status']=='verified' for c in selected),
            quality_reports=len(quality),
            sources_with_active_at_horizon=count(lambda q:q.get('lifecycle_quality',{}).get('active_episodes_at_horizon')),
            sources_with_pending_at_horizon=count(lambda q:q.get('lifecycle_quality',{}).get('pending_episodes_at_horizon')),
            sources_with_reported_stalls=count(lambda q:q.get('motion_quality',{}).get('reported_diagnostics',{}).get('active_stalled_tracks')))
    return result


def report(output):
    output,p,manifest=authenticate_protocol(output)
    authenticate_test_gate(output)
    source_dir,sp,_=sources().read_protocol(Path(p['source_directory']))
    source_summary=sources().summarize(source_dir,sp,manifest,verify=True)
    rows,summaries=collect(output,p,manifest,source_summary,verify_archives=True)
    # Partial TEST mechanism output cannot be promoted if the full source gate failed.
    if any(r['split']=='test' for r in rows):cohort_gate(p,manifest,['test'])
    pairs=[s['pair'] for s in summaries if 'pair' in s]
    audit=primary.split.verify_actual_sources(manifest,pairs,ROOT,require_complete=len(pairs)==72)
    audit['status']='verified'
    assessed=primary.analysis.evaluate_models(primary.source.load(output/'models.json'),rows)
    assessed['scope']='Declared observed-track-window contribution membership, final snapshot; quality separately reported, no person-level/universal/online guarantee.'
    value=dict(schema=REPORT_SCHEMA,**_bindings(p),source_protocol=reference(source_dir/'protocol.json'),
        import_ledger=deepcopy(p['import_ledger']),implementation_sha256=primary.source.sha(output/'implementation-supplement.json'),
        group_outcomes=summaries,source_split_audit=audit,source_quality=source_quality(source_summary['cases'],manifest),analysis=assessed)
    primary.write(output/'final-report.json',value)
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',type=Path);action.add_argument('--run',type=Path)
    action.add_argument('--freeze-implementation',type=Path);action.add_argument('--lock-models',type=Path);action.add_argument('--report',type=Path)
    parser.add_argument('--freeze',type=Path);parser.add_argument('--sources',type=Path)
    parser.add_argument('--split',action='append',choices=('train','calibration','test'));parser.add_argument('--limit',type=int)
    parser.add_argument('--unit-receipt',type=Path);parser.add_argument('--dev-receipt',type=Path)
    args=parser.parse_args(argv)
    if args.prepare:
        require(args.freeze is not None and args.sources is not None,'Prepare requires original frozen dataset and explicit windowed sources')
        print(prepare(args.freeze,args.sources,args.prepare));return
    output=args.run or args.freeze_implementation or args.lock_models or args.report
    output=primary.fixture.safe_path(output,root=ROOT/'results')
    descriptor=os.open(output/'.execution.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.run:run(output,args.split,limit=args.limit)
        elif args.freeze_implementation:
            require(args.unit_receipt and args.dev_receipt,'Unit/DEV receipts required')
            freeze_implementation(output,args.unit_receipt,args.dev_receipt)
        elif args.lock_models:lock_models(output)
        else:report(output)
    finally:os.close(descriptor)


if __name__=='__main__':main()
