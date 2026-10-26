#!/usr/bin/env python3
"""DRAFT explicit diagnostic-only lineage; never call old top-level authentication.

Only --prepare, --revalidate, --check, --run-test and --report exist. There is no
source generation, TRAIN/CAL execution, model fitting or model locking interface.
All mutating actions use new output paths and refuse overwrite/retry.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from collections import Counter
import fcntl
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/evaluation'))
import run_urban_track_window_primary as window
import run_urban_track_window_sources as sources
import track_window_source_validation as validation

primary = window.primary
source = primary.source
PROFILE = validation.PROFILE
SCHEMA = 'ump.urban-track-window-diagnostic-repair-execution.v1'
LEDGER_SCHEMA = 'ump.urban-track-window-diagnostic-repair-validation.v1'
SIDECAR_SCHEMA = 'ump.urban-track-window-diagnostic-repair-group.v1'
CLOSURE_SCHEMA = 'ump.urban-track-window-source-phase-closure.v1'
OLD_VALUE = b"len({p['building_id'] for p in portals.values()})"
NEW_VALUE = b"len({p['building_id'] for p in portals.values() if p.get('kind') != 'surface_access'})"
OLD_EXPR = b"'declared_building_count': " + OLD_VALUE
NEW_EXPR = b"'declared_building_count': " + NEW_VALUE
AUDITOR = validation.AUDITOR
DEFAULT_ANCHORS_PATH = ROOT/'results/urban-track-window-diagnostic-repair-2026-10-26/draft-input-bindings.json'


def require(value, message):
    primary.require(value, message)


def reference(path):
    return window.reference(path)


def authenticated(value):
    return window.authenticated(value)


def exact_diagnostic_delta(old, new):
    require(old.count(OLD_EXPR) == 1, 'Original declared_building_count field must occur exactly once')
    require(new == old.replace(OLD_EXPR, NEW_EXPR, 1), 'Only the approved declared_building_count field may change')


def verify_code_map(mapping, archived_auditor, corrected_sha):
    for name, expected in mapping.items():
        path = Path(name) if Path(name).is_absolute() else ROOT/name
        if path == AUDITOR:
            require(source.sha(archived_auditor) == expected and source.sha(path) == corrected_sha,
                    'Auditor archive/current correction hash differs')
        else:
            require(source.sha(path) == expected, 'Unapproved frozen dependency change: '+str(path))


def original_context(anchors, archived_auditor, corrected_sha):
    """Authenticate original bytes and approved exception; do not relabel old auth."""
    paths = {name:authenticated(value) for name,value in anchors.items() if isinstance(value,dict) and set(value)=={'path','sha256'}}
    p, sp = source.load(paths['execution_protocol']), source.load(paths['source_protocol'])
    manifest, evaluation = source.load(paths['dataset_manifest']), source.load(paths['evaluation_manifest'])
    old_output = Path(p['output_directory']); old_sources = Path(sp['output_directory'])
    require(p['schema'] == window.SCHEMA and sp['schema'] == validation.PROTOCOL_SCHEMA
            and p['source_validation_profile'] == sp['source_validation_profile'] == PROFILE, 'Original profile/schema differs')
    require(paths['execution_protocol'] == old_output/'protocol.json' and paths['source_protocol'] == old_sources/'protocol.json'
            and source.sha(paths['execution_protocol']) == (old_output/'protocol.sha256').read_text().strip()
            and source.sha(paths['source_protocol']) == (old_sources/'protocol.sha256').read_text().strip(), 'Original protocol/output binding differs')
    exact_diagnostic_delta(primary.fixture.read_bytes(archived_auditor), primary.fixture.read_bytes(AUDITOR))
    verify_code_map(sp['frozen_files_sha256'], archived_auditor, corrected_sha)
    verify_code_map(p['implementation_files_sha256'], archived_auditor, corrected_sha)
    require(source.environment()==sp['environment'], 'Frozen source validation environment changed')
    for name,expected in sp['frozen_manifest_files_sha256'].items():
        require(source.sha(name)==expected, 'Original dataset freeze artifact changed')
    primary.split.validate_manifest(manifest)
    require(source.sha(paths['dataset_manifest']) == p['dataset_manifest_sha256'] == sp['dataset_manifest_sha256'] == sp['manifest_sha256']
            and window.assignment_digest(manifest)==p['dataset_assignment_sha256']==sp['dataset_assignment_sha256'], 'Original dataset/assignments differ')
    require(p['source_protocol_sha256']==source.sha(paths['source_protocol'])
            and p['evaluation_manifest_sha256']==source.sha(paths['evaluation_manifest'])
            and evaluation['source_protocol']==anchors['source_protocol']
            and evaluation['dataset_manifest']==anchors['dataset_manifest']
            and evaluation['import_ledger']==p['import_ledger']==sp['import_ledger']==anchors['import_ledger'], 'Original lineage refs differ')
    window._source_contract(sp,manifest)
    require(evaluation['profile_definition']==window.PROFILE_DEFINITION
            and evaluation['source_profile_sha256']==primary.split.digest(window.PROFILE_DEFINITION)
            and evaluation['resolved_attack_protocol']==window.resolved_attack_protocol(manifest['design'])
            and evaluation['unchanged_scientific_blocks']==window.scientific_block_hashes(manifest['design'])
            and evaluation['declared_attack_deltas']==['secret','auxiliary.acquisition']
            and evaluation['contract']==anchors['contract'], 'Original scientific declaration differs')
    legacy=source.load(authenticated(sp['legacy_source_protocol']))
    for name,archive in sp['original_dependency_archives'].items():
        require(source.sha(authenticated(archive))==legacy['frozen_files_sha256'][name], 'Earlier archived original helper changed')
    for name in ('strict_closure','strict_source_gate','original_auditor'):authenticated(sp[name])
    strict=source.load(authenticated(sp['strict_study_protocol']))
    require(strict['source_protocol_sha256']==sp['legacy_source_protocol']['sha256']
            and strict['manifest_sha256']==sp['dataset_manifest_sha256'] and strict['freeze_directory']==sp['freeze_directory'], 'Earlier strict closure binding differs')
    legacy_cases={c['group_id']:c for c in legacy['cases']}
    require(sp['cases']==[sources._case(old_sources,g,legacy_cases) for g in manifest['groups']], 'Original source case paths/roles/seeds differ')
    sources.require_original_test_unseen(sp)
    supplement=source.load(paths['implementation_supplement'])
    require(supplement['schema']==window.SUPPLEMENT_SCHEMA and supplement['binding']==window._bindings(p)
            and supplement['files_sha256']==p['implementation_files_sha256'] and len(supplement['test_receipts'])==2,
            'Original supplement binding differs')
    for kind,ref in zip(('unit','dev'),supplement['test_receipts']):
        receipt=source.load(authenticated(ref))
        require(receipt['schema']==(window.UNIT_VALIDATION_SCHEMA if kind=='unit' else window.DEV_VALIDATION_SCHEMA)
                and receipt['status']=='verified' and receipt['evaluation_id']==p['evaluation_id']
                and receipt['source_validation_profile']==PROFILE and receipt['test_data_seen'] is False
                and receipt['actual_primary_model_fits'] is False, 'Original typed validation receipt differs')
        for field in ('files_sha256','implementation_files_sha256','full_code_sha256'):
            verify_code_map(receipt.get(field,{}),archived_auditor,corrected_sha)
    old_summary=sources.summarize(old_sources,sp,manifest,verify=False)
    rows,summaries=window.collect(old_output,p,manifest,old_summary,verify_archives=False)
    selected=[s for s in summaries if s['split']!='test']
    require(len(selected)==40 and all(s['status']=='verified' for s in selected)
            and all(not (old_output/'groups'/g['group_id']).exists() for g in manifest['groups'] if g['split']=='test'),
            'Original40 incomplete or original TEST mechanisms attempted')
    lock,models,locked_rows=(source.load(paths[k]) for k in ('model_lock','models','rows'))
    require(lock['schema']==window.LOCK_SCHEMA and lock['status']=='locked_before_test'
            and all(lock.get(k)==v for k,v in window._bindings(p).items())
            and lock['implementation_sha256']==source.sha(paths['implementation_supplement'])
            and lock['models']==anchors['models'] and lock['data']==anchors['rows']
            and lock['group_counts']=={'train':24,'calibration':16} and lock['test_rows_seen']==0, 'Original model lock differs')
    require(len(rows)==len(locked_rows)==880 and primary.analysis.digest(rows)==primary.analysis.digest(locked_rows), 'Original880 rows changed')
    expected=window.expected_groups(manifest)
    require(models['training_group_ids']==expected['train'] and models['calibration_group_ids']==expected['calibration']
            and len(models['models'])==22 and set(models['expected_method_ids'])=={m['id'] for m in manifest['design']['methods']}, 'Original model family differs')
    primary.analysis.validate_model_lock(models,locked_rows,require_complete=True)
    public,peer=(source.load(paths[k]) for k in ('public_model_lock','independent_model_audit'))
    require(public['models_lock_sha256']==peer['models_lock_sha256']==anchors['model_lock']['sha256']
            and public['models_artifact_sha256']==anchors['models']['sha256']
            and public['rows_artifact_sha256']==anchors['rows']['sha256']
            and peer['status']=='verified' and public['primary_test_rows_seen']==peer['primary_test_rows_seen']==0
            and public['test_sources_attempted']==peer['test_sources_attempted']==0, 'Original pre-TEST public/peer barrier differs')
    return dict(main=p,source=sp,manifest=manifest,old_summary=old_summary,rows=rows,summaries=selected,models=models,lock=lock)


def expected_diagnostic_failure(row, saved):
    if saved['status']=='verified':return
    directory=Path(row['scene_directory']).parent
    execution=source.load(directory/'audit-execution.json')
    stderr=primary.fixture.read_bytes(directory/'audit-stderr.log')
    require(saved.get('error')=='Independent physical audit failed or exceeded its finite wall cap'
            and execution.get('status')=='failed' and execution.get('returncode')==1
            and execution.get('command')==row['audit_command']
            and OLD_EXPR in stderr and stderr.rstrip().endswith(b"KeyError: 'building_id'"),
            'Original audit has an additional or different failure')


def driver_phase_closure(old_output, summary_ref):
    refs={name:reference(old_output/filename) for name,filename in (
        ('driver_failed','driver-failed.json'),('source_test_receipt','source_test-driver-receipt.json'),
        ('test_source_gate','test-driver-source-gate.json'))}
    failed,receipt,gate=(source.load(authenticated(refs[name])) for name in ('driver_failed','source_test_receipt','test_source_gate'))
    require(failed.get('status')=='failed_or_interrupted'
            and failed.get('completed')==['native_train_cal','lock_models','source_test']
            and failed.get('error')=='Full32 hard-valid TEST sources required; no available-case estimates', 'Original driver has not completed the expected source-gate failure')
    require(receipt.get('status')=='complete' and receipt.get('returncode')==0, 'Original source phase has not actually returned successfully')
    require(gate.get('schema')=='ump.observed-track-window-driver-source-gate.v1' and gate.get('status')=='failed'
            and gate.get('expected')==gate.get('observed')==32 and type(gate.get('verified')) is int and 0<=gate['verified']<32
            and gate.get('source_summary_sha256')==summary_ref['sha256'], 'Original failed32 source gate/final summary binding differs')
    require(not (old_output/'native_test-driver-start.json').exists()
            and not (old_output/'native_test-driver-receipt.json').exists(), 'Original TEST mechanism phase started')
    return refs


def validate_closure(closure, context):
    sp=context['source']; manifest=context['manifest']
    require(closure.get('schema')==CLOSURE_SCHEMA and closure.get('status')=='closed'
            and closure.get('source_protocol_sha256')==source.sha(Path(sp['output_directory'])/'protocol.json')
            and closure.get('attempted_test_count')==closure.get('capture_complete_test_count')==32
            and closure.get('test_mechanism_groups')==closure.get('test_model_evaluations')==0,
            'Original32 source phase must close before repair')
    require(closure.get('anchors_reference')==context['anchors_reference'], 'Closure anchors binding differs')
    authenticated(closure['anchors_reference'])
    require(closure.get('driver_phase_closure')==driver_phase_closure(Path(context['main']['output_directory']),closure['final_source_summary']), 'Original driver closure evidence changed')
    summary=source.load(authenticated(closure['final_source_summary']))
    require(summary.get('planned_count')==72 and len(summary.get('cases',[]))==72
            and {c['group_id'] for c in summary['cases']}=={g['group_id'] for g in manifest['groups']}, 'Closure summary omits source slots')
    old_receipts={}
    imports=source.load(authenticated(sp['import_ledger']))
    imported={r['group_id']:r['receipt'] for r in imports['cases']}
    for row in sp['cases']:
        path=authenticated(imported[row['group_id']]) if row['split']!='test' else Path(sp['output_directory'])/row['id']/'private-source-summary.json'
        saved=source.load(path)
        require(all(saved.get(k)==row[k] for k in ('id','group_id','split','seed','scene_directory','replay_directory','origin')), 'Original receipt identity differs')
        if row['split']=='test':
            execution=source.load(path.parent/'execution.json')
            require(execution['status']=='complete' and execution['returncode']==0
                    and saved['status'] in ('verified','invalid'), 'Source has an additional non-diagnostic failure')
            expected_diagnostic_failure(row,saved)
            proof=source.load(Path(row['replay_directory'])/'capture-proof.json')
            require(proof['status']=='verified' and proof['source_horizon_completed'] is True, 'Original source capture incomplete')
        old_receipts[row['group_id']]=reference(path)
    require(closure.get('original_source_inputs')==source_input_refs(context)
            and closure.get('original_source_receipts')==old_receipts, 'Closed original raw/proof/receipt bytes changed')
    return old_receipts


def source_input_refs(context):
    # Pin original proof/config bytes BEFORE corrected validation. Each proof
    # transitively binds the raw/private/observations/native-result source bytes.
    result={}
    for row in context['source']['cases']:
        scene,replay=Path(row['scene_directory']),Path(row['replay_directory'])
        proof_ref=reference(replay/'capture-proof.json');proof=source.load(authenticated(proof_ref))
        result[row['group_id']]=dict(capture_proof=proof_ref,config=reference(scene/'config.yaml'),
            scene_manifest=reference(scene/'scene_manifest.json'),execution=reference(scene/'execution.json'),
            capture_files_sha256=proof['files_sha256'],
            original_physical_attempt={name:reference(scene.parent/name) for name in
                ('motion-audit.json','audit-execution.json','audit-stdout.log','audit-stderr.log') if (scene.parent/name).is_file()})
    return result


def imported_group_refs(context):
    output=Path(context['main']['output_directory'])
    return [dict(group_id=s['group_id'],split=s['split'],files={name:reference(output/'groups'/s['group_id']/name)
        for name in ('summary.json','rows.json','window-evaluation-receipt.json','pair.json','archive-receipt.json')}) for s in context['summaries']]


def close_source_phase(path, final_summary, *, anchors_path=None):
    """After driver exit, BEFORE applying fix; authenticate old bytes normally.

    This is a one-time metadata receipt, not a simulation or validation rerun.
    The caller must first observe the original serial driver's actual exit.
    Old maintained auth ensures the correction has not already been applied.
    """
    anchors_ref=reference(anchors_path or DEFAULT_ANCHORS_PATH);anchors=source.load(authenticated(anchors_ref))
    for ref in anchors.values():authenticated(ref)
    old_main=Path(anchors['execution_protocol']['path']).parent
    window.authenticate_test_gate(old_main)
    old_source,sp,manifest=sources.read_protocol(Path(anchors['source_protocol']['path']).parent)
    require(all(not (old_main/'groups'/g['group_id']).exists() for g in manifest['groups'] if g['split']=='test')
            and not (old_main/'final-report.json').exists(), 'TEST mechanisms or report exist before repair')
    require(source.sha(AUDITOR)==sp['frozen_files_sha256'][str(AUDITOR)], 'Close and pin original inputs before applying diagnostic correction')
    summary_ref=reference(final_summary);saved=source.load(authenticated(summary_ref))
    actual=sources.summarize(old_source,sp,manifest,verify=False)
    require(saved==actual and actual['attempted_count']==72, 'Final original72 summary must match immutable receipts')
    context=dict(source=sp,manifest=manifest,main=source.load(authenticated(anchors['execution_protocol'])),anchors_reference=anchors_ref)
    imports=source.load(authenticated(sp['import_ledger']))
    receipts={item['group_id']:item['receipt'] for item in imports['cases']}
    receipts.update({row['group_id']:reference(old_source/row['id']/'private-source-summary.json') for row in sp['cases'] if row['split']=='test'})
    closure=dict(schema=CLOSURE_SCHEMA,status='closed',source_protocol_sha256=anchors['source_protocol']['sha256'],
        attempted_test_count=32,capture_complete_test_count=32,test_mechanism_groups=0,test_model_evaluations=0,
        final_source_summary=summary_ref,anchors_reference=anchors_ref,driver_phase_closure=driver_phase_closure(old_main,summary_ref),
        original_source_inputs=source_input_refs(context),original_source_receipts=receipts,
        closure_scope='Actual failed driver/source-phase return/failed32gate evidence; maintained original auth and all72 receipt/proof refs pinned before diagnostic correction.')
    validate_closure(closure,context)
    primary.write(path,closure)
    return closure


def authenticate_correction_tests(ref, corrected_sha, original_sha):
    path=authenticated(ref);value=source.load(path)
    require(value['schema']=='ump.surface-access-building-diagnostic-fix-tests.v1'
            and value['status']=='held_patch_verified_synthetically'
            and value['corrected_auditor_sha256']==corrected_sha and value['original_auditor_sha256']==original_sha
            and value['exact_one_line_diagnostic_replacement_verified'] is True
            and value['field_schema_profile_names_unchanged'] is True
            and value['physical_or_lifecycle_guard_changes']==value['model_fits']==value['native_jobs']==0
            and value['corrected_total_passing_tests']==56, 'Focused diagnostic correction evidence differs')
    for name,expected in value['files_sha256'].items():
        require(Path(name).name==name and source.sha(path.parent/name)==expected,'Focused correction evidence file changed')
    return value


def prepare(output, archived_auditor, closure_path, *, anchors_path=None,repair_id='urban-track-window-diagnostic-repair-20261026-v1'):
    anchors_ref=reference(anchors_path or DEFAULT_ANCHORS_PATH);anchors=source.load(authenticated(anchors_ref))
    archived_auditor=primary.fixture.safe_path(archived_auditor,root=ROOT/'results')
    context=original_context(anchors,archived_auditor,source.sha(AUDITOR))
    context['anchors_reference']=anchors_ref
    correction_tests=anchors['correction_tests']
    authenticate_correction_tests(correction_tests,source.sha(AUDITOR),source.sha(archived_auditor))
    closure_ref=reference(closure_path);old_receipts=validate_closure(source.load(authenticated(closure_ref)),context)
    output=primary.fixture.new_output(output);(output/'groups').mkdir(mode=0o700);(output/'validation').mkdir(mode=0o700)
    p=dict(schema=SCHEMA,status='prepared_after_source_phase_closure',repair_id=repair_id,evaluation_id=context['main']['evaluation_id'],
        source_validation_profile=PROFILE,output_directory=str(output),anchors=anchors,anchors_reference=anchors_ref,source_phase_closure=closure_ref,
        original_auditor=reference(archived_auditor),corrected_auditor=reference(AUDITOR),correction_tests=correction_tests,
        diagnostic_delta=dict(old=OLD_EXPR.decode(),new=NEW_EXPR.decode()),original_source_receipts=old_receipts,original_source_inputs=source_input_refs(context),
        imported_groups=imported_group_refs(context),adapter=reference(Path(__file__)),tests=reference(Path(__file__).with_name('test_'+Path(__file__).name)),
        freeze_directory=context['main']['freeze_directory'],native_wall_budget_s=context['main']['native_wall_budget_s'],
        audit_max_cells=context['main']['audit_max_cells'],minimum_free_bytes=context['main']['minimum_free_bytes'],
        native_binary_sha256=context['main']['native_binary_sha256'],availability=context['main']['availability'],
        source_generation_allowed=False,training_or_calibration_execution_allowed=False,model_fits_allowed=False,
        new_physical_audit_jobs=32,reused_legacy_physical_proofs=40,full_raw_validations=72,
        rules='All72 exact original inputs/full raw checks;40 authenticated unchanged legacy proofs and32 new corrected TEST physical audits; all32 TEST hard-valid before TEST mechanism. Original40 outputs/880 rows/22 models/CAL unchanged. No resimulation/replacement/selection/refit/tuning.')
    primary.write(output/'protocol.json',p);primary.fixture.write_new(output/'protocol.sha256',(source.sha(output/'protocol.json')+'\n').encode())
    return output


def read_protocol(output):
    output=primary.fixture.safe_path(output,root=ROOT/'results');p=source.load(output/'protocol.json')
    require(p.get('schema')==SCHEMA and p.get('output_directory')==str(output)
            and source.sha(output/'protocol.json')==(output/'protocol.sha256').read_text().strip(), 'Repair protocol differs')
    for name in ('adapter','tests','source_phase_closure','corrected_auditor','original_auditor'):authenticated(p[name])
    require(p['adapter']==reference(Path(__file__)) and p['diagnostic_delta']==dict(old=OLD_EXPR.decode(),new=NEW_EXPR.decode())
            and p['source_generation_allowed'] is p['training_or_calibration_execution_allowed'] is p['model_fits_allowed'] is False,
            'Repair scope/code differs')
    authenticate_correction_tests(p['correction_tests'],p['corrected_auditor']['sha256'],p['original_auditor']['sha256'])
    require(source.load(authenticated(p['anchors_reference']))==p['anchors'], 'Repair anchors file changed')
    require(p['tests']==reference(Path(__file__).with_name('test_'+Path(__file__).name)), 'Repair matching versioned tests differ')
    context=original_context(p['anchors'],authenticated(p['original_auditor']),p['corrected_auditor']['sha256'])
    context['anchors_reference']=p['anchors_reference']
    require(p['original_source_receipts']==validate_closure(source.load(authenticated(p['source_phase_closure'])),context)
            and p['imported_groups']==imported_group_refs(context)
            and p['original_source_inputs']==source_input_refs(context), 'Original receipts/source inputs/group outputs changed')
    for name in ('freeze_directory','native_wall_budget_s','audit_max_cells','minimum_free_bytes','native_binary_sha256','availability'):
        require(p[name]==context['main'][name], 'Runtime policy/budget changed: '+name)
    require(all(not (output/'groups'/g['group_id']).exists() for g in context['manifest']['groups'] if g['split']!='test'), 'Repair attempted TRAIN/CAL work')
    require((p['new_physical_audit_jobs'],p['reused_legacy_physical_proofs'],p['full_raw_validations'])==(32,40,72), 'Repair qualification plan changed')
    return output,p,context


def legacy_proof_refs(context):
    imported=[row for row in context['source']['cases'] if row['split'] in ('train','calibration')]
    proofs=context['source']['legacy_physical_audits']
    require(len(imported)==40 and len(proofs)==40, 'Exactly40 existing legacy physical proofs required')
    expected={source.sha(Path(row['replay_directory'])/'capture-proof.json') for row in imported}
    require(set(proofs)==expected, 'Unknown or missing imported legacy physical proof')
    for proof in proofs.values():
        require(set(proof)=={'report','execution','producer_protocol','archived_auditor'}, 'Incomplete imported legacy proof chain')
        for ref in proof.values():authenticated(ref)
    return deepcopy(proofs)


def physical_proof(view,case):
    key=case['capture_proof_sha256'];legacy=view['legacy_physical_audits'].get(key);windowed=view['windowed_physical_audits'].get(key)
    require((legacy is not None)!=(windowed is not None), 'Unknown or ambiguous physical proof')
    require((case['split']=='test' and windowed is not None) or (case['split'] in ('train','calibration') and legacy is not None), 'Physical proof origin differs from declared role')
    value=windowed if windowed is not None else legacy
    fields=('report','execution') if windowed is not None else ('report','execution','producer_protocol','archived_auditor')
    for name in fields:authenticated(value[name])
    return dict(origin='new_corrected_test_audit' if windowed is not None else 'authenticated_legacy_proof_reuse',proof=deepcopy(value))


def validation_view(protocol, context):
    """Explicit NEW producer view, never written over or called the old protocol."""
    view=deepcopy(context['source']);view['frozen_files_sha256'][str(AUDITOR)]=protocol['corrected_auditor']['sha256']
    view['legacy_physical_audits']=legacy_proof_refs(context);view['windowed_physical_audits']={}
    view['diagnostic_repair_producer']=dict(kind='derived_validation_view_not_original_protocol',
        repair_protocol=reference(Path(protocol['output_directory'])/'protocol.json'),original_source_protocol=protocol['anchors']['source_protocol'])
    output=Path(protocol['output_directory'])
    for row in view['cases']:
        if row['split']!='test':continue
        directory=output/'validation'/row['group_id'];audit=directory/'motion-audit.json'
        command=[sys.executable,str(AUDITOR),'--scene',row['scene_directory'],'--replay',row['replay_directory'],'--output',str(audit),'--profile',PROFILE]
        proof_sha=source.sha(Path(row['replay_directory'])/'capture-proof.json')
        view['windowed_physical_audits'][proof_sha]=dict(report=dict(path=str(audit),sha256=source.sha(audit)) if audit.is_file() else None,
            execution=dict(path=str(directory/'audit-execution.json'),sha256=source.sha(directory/'audit-execution.json')) if (directory/'audit-execution.json').is_file() else None,
            command=command)
    return view


def validate_family(cases, manifest):
    expected={g['group_id']:g for g in manifest['groups']}
    require(len(cases)==72 and {c['group_id'] for c in cases}==set(expected), 'All72 validation receipts required')
    excluded={x.get(k) for x in manifest['exclusions'] for k in ('observations_sha256','normalized_source_fingerprint','normalized_source_fingerprint_v2')}
    excluded_routes={x.get('planned_route_fingerprint') for x in manifest['exclusions']}
    seen={field:set() for field in ('normalized_source_fingerprint_v2','planned_route_fingerprint')}
    for case in cases:
        group=expected[case['group_id']]
        require(case['status']=='verified' and case['validation_profile']==PROFILE and case['split']==group['split']
                and case['seed']==group['seeds']['source_generation'], 'Hard validity/role/seed differs')
        require(not ({case['observations_sha256'],case['normalized_source_fingerprint'],case['normalized_source_fingerprint_v2']} & excluded)
                and case['planned_route_fingerprint'] not in excluded_routes, 'Historical/DEV source clone')
        for field in seen:
            require(case[field] not in seen[field], 'Duplicate source/route');seen[field].add(case[field])


def revalidate(output):
    output,p,context=read_protocol(output)
    require(not (output/'validation-ledger.json').exists() and not any((output/'groups').iterdir()), 'No validation retry or post-mechanism qualification')
    legacy=legacy_proof_refs(context)
    for row in context['source']['cases']:
        directory=output/'validation'/row['group_id'];require(not directory.exists(),'No physical-audit retry');directory.mkdir(mode=0o700)
        if row['split']!='test':
            proof_sha=source.sha(Path(row['replay_directory'])/'capture-proof.json')
            primary.write(directory/'reused-physical-proof.json',dict(origin='authenticated_legacy_proof_reuse',physical_audit_executed=False,proof=legacy[proof_sha]))
            continue
        audit=directory/'motion-audit.json';command=[sys.executable,str(AUDITOR),'--scene',row['scene_directory'],'--replay',row['replay_directory'],'--output',str(audit),'--profile',PROFILE]
        execution=dict(command=command,status='failed',returncode=None)
        try:
            with (directory/'stdout.log').open('x') as stdout,(directory/'stderr.log').open('x') as stderr:
                result=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr,timeout=context['source']['physical_audit_wall_budget_s'],check=False)
            execution.update(status='complete',returncode=result.returncode)
        except subprocess.TimeoutExpired:execution['status']='timeout'
        except Exception as error:execution.update(status='failed',error=str(error))
        primary.write(directory/'audit-execution.json',execution)
    view=validation_view(p,context);primary.write(output/'validation-producer-view.json',view)
    entries=[]
    for row in context['source']['cases']:
        item={k:row[k] for k in ('id','group_id','split','seed','scene_directory','replay_directory','origin')}
        item['original_receipt']=p['original_source_receipts'][row['group_id']]
        item['physical_proof_origin']='new_corrected_test_audit' if row['split']=='test' else 'authenticated_legacy_proof_reuse'
        if row['split']!='test':item['reused_physical_proof']=reference(output/'validation'/row['group_id']/'reused-physical-proof.json')
        try:
            item.update(validation.validate_capture(row,view))
            item['normalized_source_fingerprint_v2']=primary.split.normalized_fingerprint(source.load(Path(row['replay_directory'])/'observations.json'))
        except Exception as error:item.update(status='invalid',error=str(error))
        path=output/'validation'/row['group_id']/'receipt.json';primary.write(path,item)
        entries.append(dict(group_id=row['group_id'],split=row['split'],status=item['status'],receipt=reference(path)))
    ledger=dict(schema=LEDGER_SCHEMA,repair_protocol_sha256=source.sha(output/'protocol.json'),source_validation_profile=PROFILE,
                original_model_lock=p['anchors']['model_lock'],producer_view=reference(output/'validation-producer-view.json'),
                new_physical_audit_jobs=32,reused_legacy_physical_proofs=40,full_raw_validations=72,cases=entries,status='incomplete')
    cases=[source.load(authenticated(e['receipt'])) for e in entries]
    try:validate_family(cases,context['manifest']);ledger['status']='verified'
    except ValueError as error:ledger['error']=str(error)
    primary.write(output/'validation-ledger.json',ledger)
    return ledger


def authenticated_validation(output,p,context,*,verify_raw=False):
    ledger=source.load(output/'validation-ledger.json')
    require(ledger['schema']==LEDGER_SCHEMA and ledger['status']=='verified'
            and ledger['repair_protocol_sha256']==source.sha(output/'protocol.json')
            and ledger['source_validation_profile']==PROFILE and ledger['original_model_lock']==p['anchors']['model_lock']
            and (ledger['new_physical_audit_jobs'],ledger['reused_legacy_physical_proofs'],ledger['full_raw_validations'])==(32,40,72), 'Wrong/incomplete repair validation ledger')
    view=source.load(authenticated(ledger['producer_view']))
    require(view==validation_view(p,context), 'Repair validation producer view changed')
    cases=[]
    for entry in ledger['cases']:
        case=source.load(authenticated(entry['receipt']))
        require(case['group_id']==entry['group_id'] and case['split']==entry['split'] and case['status']==entry['status']
                and case['original_receipt']==p['original_source_receipts'][case['group_id']], 'Repair receipt provenance differs')
        authenticated(case['original_receipt'])
        evidence=physical_proof(view,case)
        require(case['physical_proof_origin']==evidence['origin'], 'Physical proof reuse/new-execution label differs')
        if case['split']!='test':
            reused=source.load(authenticated(case['reused_physical_proof']))
            require(reused==dict(origin=evidence['origin'],physical_audit_executed=False,proof=evidence['proof']), 'Imported physical proof record differs')
        if verify_raw:
            row=next(r for r in context['source']['cases'] if r['group_id']==case['group_id'])
            actual=validation.validate_capture(row,view)
            require(all(case.get(k)==v for k,v in actual.items()), 'Repair receipt differs from full current input verification')
        cases.append(case)
    validate_family(cases,context['manifest'])
    return cases


def bindings(output,p):
    return dict(repair_id=p['repair_id'],evaluation_id=p['evaluation_id'],source_validation_profile=PROFILE,
        repair_protocol_sha256=source.sha(output/'protocol.json'),validation_ledger_sha256=source.sha(output/'validation-ledger.json'),
        original_models_lock_sha256=p['anchors']['model_lock']['sha256'],original_models_sha256=p['anchors']['models']['sha256'],
        original_train_cal_rows_sha256=p['anchors']['rows']['sha256'],original_execution_protocol_sha256=p['anchors']['execution_protocol']['sha256'],
        dataset_manifest_sha256=p['anchors']['dataset_manifest']['sha256'])


def authenticate_test_gate(output):
    output,p,context=read_protocol(output)
    cases=authenticated_validation(output,p,context)
    require(len([c for c in cases if c['split']=='test'])==32, 'All32 TEST hard-valid sources required before any TEST mechanism')
    return output,p,context,cases


def run_test(output,*,limit=None):
    output,p,context,cases=authenticate_test_gate(output)
    require(limit is None or type(limit) is int and limit>0,'Invalid TEST limit');window.require_pair_injection()
    by_group={c['group_id']:c for c in cases};completed=0
    for group in context['manifest']['groups']:
        if group['split']!='test' or (output/'groups'/group['group_id']).exists():continue
        if limit is not None and completed>=limit:break
        summary=primary.process_group(output,p,context['manifest'],group,by_group[group['group_id']],pair_selector=window.select_window_pair)
        directory=output/'groups'/group['group_id']
        primary.write(directory/'diagnostic-repair-receipt.json',dict(schema=SIDECAR_SCHEMA,binding=bindings(output,p),
            group_id=group['group_id'],split='test',source_validation_sha256=window._case_digest(by_group[group['group_id']]),
            summary_sha256=source.sha(directory/'summary.json'),rows_sha256=summary['rows']['sha256']))
        completed+=1


def collect_repair(output,p,context,cases,*,verify_archives=False):
    old_rows,old_summaries=window.collect(Path(context['main']['output_directory']),context['main'],context['manifest'],context['old_summary'],verify_archives=verify_archives)
    rows,summaries=primary.collect(output,context['manifest'],verify_archives=verify_archives)
    require(all(r['split']=='test' for r in rows), 'New TRAIN/CAL rows forbidden')
    selected=[s for s in summaries if s['split']=='test'];by_group={c['group_id']:c for c in cases}
    for summary in selected:
        directory=output/'groups'/summary['group_id']
        if not (directory/'summary.json').is_file():continue
        side=source.load(directory/'diagnostic-repair-receipt.json')
        require(side['schema']==SIDECAR_SCHEMA and side['binding']==bindings(output,p)
                and side['group_id']==summary['group_id'] and side['split']=='test'
                and side['summary_sha256']==source.sha(directory/'summary.json') and side['rows_sha256']==summary['rows']['sha256']
                and side['source_validation_sha256']==window._case_digest(by_group[summary['group_id']]), 'Repair TEST sidecar differs')
    imported=[s for s in old_summaries if s['split'] in ('train','calibration')]
    require(len(imported)==40 and all(s['status']=='verified' for s in imported), 'Original40 group outputs incomplete')
    combined=imported+selected
    require(len(combined)==72 and len({s['group_id'] for s in combined})==72, 'Missing/duplicate merged group family')
    require(primary.analysis.digest(old_rows)==primary.analysis.digest(source.load(authenticated(p['anchors']['rows']))), 'Imported880 rows changed')
    return old_rows+rows,combined


def public_repair_lineage(output,p,context,cases):
    statuses=Counter(source.load(authenticated(ref))['status'] for group_id,ref in p['original_source_receipts'].items()
                     if next(g for g in context['manifest']['groups'] if g['group_id']==group_id)['split']=='test')
    return dict(schema='ump.urban-track-window-diagnostic-repair-public-lineage.v1',
        repair_id_sha256=primary.split.digest(p['repair_id']),source_validation_profile=PROFILE,
        repair_protocol_sha256=source.sha(output/'protocol.json'),validation_ledger_sha256=source.sha(output/'validation-ledger.json'),
        original_source_protocol_sha256=p['anchors']['source_protocol']['sha256'],
        original_execution_protocol_sha256=p['anchors']['execution_protocol']['sha256'],
        original_model_lock_sha256=p['anchors']['model_lock']['sha256'],original_models_sha256=p['anchors']['models']['sha256'],
        original_rows_sha256=p['anchors']['rows']['sha256'],original_auditor_sha256=p['original_auditor']['sha256'],
        corrected_auditor_sha256=p['corrected_auditor']['sha256'],source_binary_sha256=context['source']['simulator_sha256'],
        original_test_source_status_counts=dict(statuses),corrected_verified_sources=len(cases),
        same_role_sources=72,imported_mechanism_groups=40,imported_rows=880,locked_variants=22,
        new_physical_audit_jobs=32,reused_legacy_physical_proofs=40,full_raw_validations=72,
        source_resimulations=0,source_replacements=0,model_refits=0,threshold_retunes=0,
        scope='Metadata-only source qualification repair; old technical failures retained; this lineage packet must accompany numerical results.')


def report(output):
    output,p,context,cases=authenticate_test_gate(output)
    authenticated_validation(output,p,context,verify_raw=True)
    rows,summaries=collect_repair(output,p,context,cases,verify_archives=True)
    pairs=[s['pair'] for s in summaries if 'pair' in s]
    audit=primary.split.verify_actual_sources(context['manifest'],pairs,ROOT,require_complete=len(pairs)==72);audit['status']='verified'
    assessed=primary.analysis.evaluate_models(context['models'],rows)
    assessed['scope']='Unchanged locked observed-track-window attack; explicit diagnostic-only source-qualification repair lineage; no refit or retuning.'
    value=dict(schema=window.REPORT_SCHEMA,**window._bindings(context['main']),source_protocol=p['anchors']['source_protocol'],
        import_ledger=context['main']['import_ledger'],implementation_sha256=p['anchors']['implementation_supplement']['sha256'],
        group_outcomes=summaries,source_split_audit=audit,source_quality=window.source_quality(cases,context['manifest']),analysis=assessed,
        diagnostic_repair=dict(binding=bindings(output,p),original_source_phase_closure=p['source_phase_closure'],
            original_receipts=p['original_source_receipts'],imported_original_groups=p['imported_groups'],
            corrected_validation_ledger=reference(output/'validation-ledger.json'),old_failure_preserved=True,source_resimulations=0,model_refits=0))
    primary.write(output/'final-report.json',value)
    primary.write(output/'repair-lineage-public.json',public_repair_lineage(output,p,context,cases))
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);action=parser.add_mutually_exclusive_group(required=True)
    for name in ('close-sources','prepare','revalidate','check','run-test','report'):action.add_argument('--'+name,type=Path)
    parser.add_argument('--anchors',type=Path);parser.add_argument('--source-summary',type=Path);parser.add_argument('--original-auditor',type=Path);parser.add_argument('--closure',type=Path);parser.add_argument('--limit',type=int)
    args=parser.parse_args(argv)
    if args.close_sources:
        require(args.source_summary,'Retained final original source summary is required')
        close_source_phase(args.close_sources,args.source_summary,anchors_path=args.anchors);return
    if args.prepare:
        require(args.original_auditor and args.closure,'Archived original auditor and source-phase closure required')
        print(prepare(args.prepare,args.original_auditor,args.closure,anchors_path=args.anchors));return
    output=args.revalidate or args.check or args.run_test or args.report
    descriptor=os.open(output/'.repair-execution.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.revalidate:revalidate(output)
        elif args.check:authenticate_test_gate(output);print('verified: immutable model lock + all72 corrected source validations')
        elif args.run_test:run_test(output,limit=args.limit)
        else:report(output)
    finally:os.close(descriptor)


if __name__=='__main__':main()
