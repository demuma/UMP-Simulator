#!/usr/bin/env python3
"""Append-only exploratory strategy comparison; unchanged hard regional policy.

Only execution strategy/secondary/release preferences differ. Original sources,
IN/OUT pairs, method outputs, models, controls and failure history stay immutable.
Run every utility/audit case before fitting the eight new MIA variants. Training
uses TRAIN only, thresholds CAL only, and scoring is a separately gated action.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/evaluation'))
import run_urban_track_window_diagnostic_repair as repair
import semantic_privacy as semantic

primary = repair.primary
source = primary.source
window = repair.window
analysis = primary.analysis
SCHEMA = 'ump.urban-strategy-supplement-execution.v1'
UTILITY_SCHEMA = 'ump.urban-strategy-supplement-utility.v1'
REPORT_SCHEMA = 'ump.urban-strategy-supplement-report.v1'
SIDECAR_SCHEMA = 'ump.urban-strategy-supplement-group.v1'
LOCK_SCHEMA = 'ump.urban-strategy-supplement-model-lock.v1'
PROFILE = repair.PROFILE
EXECUTION_KEYS = frozenset(('strategy', 'semantic_secondary_strategy', 'release_trigger'))
VARIANTS = (
    dict(id='adaptive_temporal_first', label='Temporal First', kind='native_adaptive',
         strategy='temporal_first', secondary_strategy=None, release_trigger='policy_satisfied'),
    dict(id='adaptive_spatial_first', label='Spatial First', kind='native_adaptive',
         strategy='spatial_first', secondary_strategy=None, release_trigger='policy_satisfied'),
    dict(id='adaptive_semantic_wait_temporal', label='Semantic First / wait / Temporal secondary', kind='native_adaptive',
         strategy='semantic_first', secondary_strategy='temporal_first', release_trigger='priority_satisfied'),
    dict(id='adaptive_semantic_wait_spatial', label='Semantic First / wait / Spatial secondary', kind='native_adaptive',
         strategy='semantic_first', secondary_strategy='spatial_first', release_trigger='priority_satisfied'),
)
CONTRASTS = (
    ('temporal_vs_regional20', 'adaptive_temporal_first', 'regional_static20', 20261026311),
    ('spatial_vs_regional20', 'adaptive_spatial_first', 'regional_static20', 20261026312),
    ('semantic_wait_temporal_vs_regional20', 'adaptive_semantic_wait_temporal', 'regional_static20', 20261026313),
    ('semantic_wait_spatial_vs_regional20', 'adaptive_semantic_wait_spatial', 'regional_static20', 20261026314),
    ('temporal_vs_spatial', 'adaptive_temporal_first', 'adaptive_spatial_first', 20261026315),
    ('semantic_wait_temporal_vs_immediate', 'adaptive_semantic_wait_temporal', 'adaptive_semantic_first', 20261026316),
    ('semantic_wait_spatial_vs_immediate', 'adaptive_semantic_wait_spatial', 'adaptive_semantic_first', 20261026317),
    ('semantic_wait_temporal_vs_semantic_wait_spatial', 'adaptive_semantic_wait_temporal', 'adaptive_semantic_wait_spatial', 20261026318),
)
DEFAULT_PARENT = ROOT/'results/urban-track-window-diagnostic-repair-execution-2026-10-26-v1'
ORIGINAL_PUBLICATION_COMMIT = '035a9e6344fe01a830c89ddc8352eaafd758e79f'
PUBLIC_SUMMARY = Path('docs/verification/urban-track-window-2026-10-26-v1/final-outcome/summary.json')
PUBLIC_LINEAGE = PUBLIC_SUMMARY.with_name('repair-lineage-public.json')
PUBLIC_BUNDLE = PUBLIC_SUMMARY.with_name('bundle-receipt.json')
FIT_OUTPUTS = ('mia-fit-attempt.json','mia-fit-failed.json','models.json','train-cal-rows.json','models-lock.json','final-report.json')


def require(value, message):
    primary.require(value, message)


def reference(path):
    return repair.reference(path)


def authenticated(value):
    return repair.authenticated(value)


def hard_policy(config):
    value = deepcopy(config)
    execution = value.get('policy_tree', {}).get('execution', {})
    for key in EXECUTION_KEYS:
        execution.pop(key, None)
    return value


def variant_config(base, method):
    require(method in VARIANTS, 'Unknown or altered supplementary method')
    result = deepcopy(base)
    execution = result['policy_tree']['execution']
    for key in EXECUTION_KEYS:
        execution.pop(key, None)
    execution['strategy'] = method['strategy']
    execution['release_trigger'] = method['release_trigger']
    if method['secondary_strategy'] is not None:
        execution['semantic_secondary_strategy'] = method['secondary_strategy']
    require(hard_policy(result) == hard_policy(base), 'Hard policy changed')
    return result


def validate_variant_config(base, config, method):
    require(config == variant_config(base, method), 'Unexpected execution/configuration delta')
    require(hard_policy(config) == hard_policy(base), 'Hard policy changed')


def authenticate_publication(parent):
    """Bind the existing completed result to its already published Git bytes."""
    refs = {}
    for relative in (PUBLIC_SUMMARY, PUBLIC_LINEAGE, PUBLIC_BUNDLE):
        committed = subprocess.check_output(['git','show',ORIGINAL_PUBLICATION_COMMIT+':'+relative.as_posix()],cwd=ROOT)
        require(primary.fixture.read_bytes(ROOT/relative) == committed, 'Original published artifact differs from committed bytes')
        refs[relative.name] = reference(ROOT/relative)
    public = source.load(ROOT/PUBLIC_SUMMARY)
    require(source.sha(Path(parent)/'final-report.json') == public['provenance']['private_report_sha256'], 'Original report differs from published result')
    require(source.load(Path(parent)/'repair-lineage-public.json') == source.load(ROOT/PUBLIC_LINEAGE), 'Original repair lineage differs from publication')
    return refs


def parent_context(parent, *, verify_archives=False, verify_raw=False):
    parent, rp, context, cases = repair.authenticate_test_gate(parent)
    if verify_raw:
        repair.authenticated_validation(parent, rp, context, verify_raw=True)
    rows, summaries = repair.collect_repair(parent, rp, context, cases, verify_archives=verify_archives)
    publication_refs = authenticate_publication(parent)
    report_path = parent/'final-report.json'
    report = source.load(report_path)
    require(report['schema'] == window.REPORT_SCHEMA and report['analysis']['status'] == 'complete'
            and report['analysis']['interpretation_gate'] == 'controls_pass'
            and len(summaries) == 72 and all(s['status'] == 'verified' for s in summaries)
            and len(rows) == 1584, 'Original completed family required')
    old_methods = [m['id'] for m in context['manifest']['design']['methods']]
    checked = analysis._checked_rows(rows, window.expected_groups(context['manifest']), old_methods, allow_test=True)
    require(analysis.digest(checked) == report['analysis']['all_rows_sha256'], 'Original final rows/report differ')
    context.update(parent_output=parent, repair_protocol=rp, cases=cases, original_rows=rows,
                   original_summaries=summaries, original_report=report, publication_refs=publication_refs)
    return context


def import_groups(context):
    result = {}
    for summary in context['original_summaries']:
        base = (Path(context['main']['output_directory']) if summary['split'] != 'test'
                else context['parent_output'])/'groups'/summary['group_id']
        names = ['summary.json', 'rows.json', 'pair.json', 'auxiliary.json', 'in.json', 'out.json', 'archive-receipt.json']
        names.append('window-evaluation-receipt.json' if summary['split'] != 'test' else 'diagnostic-repair-receipt.json')
        result[summary['group_id']] = dict(directory=str(base), split=summary['split'],
                                         files={name:reference(base/name) for name in names})
    require(len(result) == 72, 'All original pair families required')
    return result


def parent_refs(context):
    p = context['parent_output']; rp = context['repair_protocol']
    return dict(protocol=reference(p/'protocol.json'), validation_ledger=reference(p/'validation-ledger.json'),
                report=reference(p/'final-report.json'), repair_lineage=reference(p/'repair-lineage-public.json'),
                models_lock=rp['anchors']['model_lock'], models=rp['anchors']['models'],
                train_cal_rows=rp['anchors']['rows'], public_summary=context['publication_refs'][PUBLIC_SUMMARY.name],
                public_lineage=context['publication_refs'][PUBLIC_LINEAGE.name], public_bundle=context['publication_refs'][PUBLIC_BUNDLE.name])


def prepare(output, parent=DEFAULT_PARENT, *, contract):
    context = parent_context(parent)
    config_path = Path(context['main']['freeze_directory'])/'policy-local400.json'
    base = source.load(config_path)
    contract_ref = reference(contract)
    output = primary.fixture.new_output(output)
    (output/'groups').mkdir(mode=0o700); (output/'configs').mkdir(mode=0o700)
    configs = {}
    for method in VARIANTS:
        path = output/'configs'/(method['id']+'.json')
        primary.write(path, variant_config(base, method)); configs[method['id']] = reference(path)
    implementation = {str(q.relative_to(ROOT)):source.sha(q) for q in sorted((ROOT/'tools/evaluation').glob('*.py'))}
    for q in sorted((ROOT/'tools/mapped_scene').glob('*.py')):
        implementation[str(q.relative_to(ROOT))] = source.sha(q)
    p = dict(schema=SCHEMA, status='prepared_exploratory_supplement', supplement_id='urban-strategy-supplement-20261026-v1',
             evaluation_id=context['main']['evaluation_id'], prepared_at=source.now(), output_directory=str(output),
             parent_output=str(context['parent_output']), parent_references=parent_refs(context), imported_groups=import_groups(context),
             original_publication_commit=ORIGINAL_PUBLICATION_COMMIT,
             source_validation_profile=PROFILE, contract=contract_ref, variants=deepcopy(VARIANTS),
             contrasts=[dict(id=n,left=l,right=r,seed=s,replicates=1000,confidence_level=.95) for n,l,r,s in CONTRASTS],
             original_config=reference(config_path), hard_policy_sha256=analysis.digest(hard_policy(base)), variant_configs=configs,
             implementation_files_sha256=implementation, adapter=reference(Path(__file__)),
             tests=reference(Path(__file__).with_name('test_'+Path(__file__).name)),
             source_generation_allowed=False, original_artifact_changes_allowed=False,
             original_methods=context['manifest']['design']['methods'], availability=context['main']['availability'],
             freeze_directory=context['main']['freeze_directory'], native_binary_sha256=context['main']['native_binary_sha256'],
             native_wall_budget_s=context['main']['native_wall_budget_s'], audit_max_cells=context['main']['audit_max_cells'],
             minimum_free_bytes=context['main']['minimum_free_bytes'],
             group_counts={'train':24,'calibration':16,'test':32}, expected_new_streams=576, expected_imported_rows=1584,
             expected_all_rows=2160, expected_new_models=8,
             scope='Exploratory supplementary methods selected after original TEST results. Same inputs/pairs/hard policy. Utility/audits first, eight TRAIN-only fits/CAL locks last, then separate TEST scoring. Original study/22 models/controls unchanged; no new confirmatory claim.')
    primary.write(output/'protocol.json',p)
    primary.fixture.write_new(output/'protocol.sha256',(source.sha(output/'protocol.json')+'\n').encode())
    return output


def read_protocol(output):
    output = primary.fixture.safe_path(output,root=ROOT/'results')
    p = source.load(output/'protocol.json')
    require(p.get('schema') == SCHEMA and p.get('output_directory') == str(output)
            and source.sha(output/'protocol.json') == (output/'protocol.sha256').read_text().strip(), 'Supplement protocol differs')
    require(p['variants'] == list(VARIANTS) and p['contrasts'] == [dict(id=n,left=l,right=r,seed=s,replicates=1000,confidence_level=.95) for n,l,r,s in CONTRASTS], 'Supplement method/contrast declaration differs')
    for key in ('adapter','tests','contract','original_config'):
        authenticated(p[key])
    require(p['adapter'] == reference(Path(__file__)) and p['tests'] == reference(Path(__file__).with_name('test_'+Path(__file__).name)), 'Supplement implementation differs')
    for name, digest in p['implementation_files_sha256'].items():
        require(source.sha(ROOT/name) == digest, 'Frozen supplement dependency changed: '+name)
    require(p['source_generation_allowed'] is p['original_artifact_changes_allowed'] is False
            and p['original_publication_commit'] == ORIGINAL_PUBLICATION_COMMIT, 'Supplement scope changed')
    context = parent_context(Path(p['parent_output']))
    require(p['parent_references'] == parent_refs(context) and p['imported_groups'] == import_groups(context), 'Original imported evidence changed')
    require(p['original_methods'] == context['manifest']['design']['methods'], 'Original comparator family changed')
    base = source.load(authenticated(p['original_config']))
    require(p['hard_policy_sha256'] == analysis.digest(hard_policy(base)), 'Hard policy digest differs')
    require(set(p['variant_configs']) == {m['id'] for m in VARIANTS}, 'Variant configuration family differs')
    for method in VARIANTS:
        validate_variant_config(base, source.load(authenticated(p['variant_configs'][method['id']])), method)
    for name in ('availability','freeze_directory','native_binary_sha256','native_wall_budget_s','audit_max_cells','minimum_free_bytes'):
        require(p[name] == context['main'][name], 'Inherited runtime/availability differs: '+name)
    require(p['group_counts'] == {'train':24,'calibration':16,'test':32}
            and (p['expected_new_streams'],p['expected_imported_rows'],p['expected_all_rows'],p['expected_new_models']) == (576,1584,2160,8), 'Supplement denominator changed')
    return output,p,context


def validate_native(result, data, config, method):
    require(method in VARIANTS, 'Unknown supplementary method')
    require(result.get('schema') == 'ump.replay-result.v1' and result.get('mode') == method['strategy'], 'Native method mismatch')
    require(all(result.get('source',{}).get(k) == data[k] for k in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')), 'Native source/header mismatch')
    require(result['source'].get('application_id') == config['application_id'], 'Native application differs')
    q = result['parameters']
    require(q.get('coordination') == 'cell_local' and q.get('progress_step_ms') == 50 and q.get('progress_origin_ms') == 0, 'Adaptive coordination/clock differs')
    require(q.get('window_ms') == config['window_ms'] and q.get('max_window_ms') == config['temporal_adaptation']['max_window_ms']
            and q.get('extension_step_ms') == config['temporal_adaptation']['extension_step_ms']
            and q.get('min_depth') == config['spatial_selection']['min_depth'], 'Native adaptation bounds differ')
    if method['strategy'] == 'semantic_first':
        require(q.get('semantic_secondary_strategy') == method['secondary_strategy'] and q.get('release_trigger') == method['release_trigger'], 'Semantic priority/release differs')
    else:
        require('semantic_secondary_strategy' not in q and 'release_trigger' not in q, 'Plain TF/SF must not claim semantic-only metadata')
    total = primary.fixture.counts(data)['observations']
    require(result['input_observation_contributions'] == result['accounted_observation_contributions'] == total, 'Native observation conservation differs')


def run_case(directory, data_path, config, method, group, world, knowledge, protocol):
    """One fresh native/audit/public/utility case; also used on excluded DEV inputs.

    Caller supplies a fresh directory with the unchanged AggregationReplay binary.
    There is no fitting/scoring, source generation, overwrite or retry here.
    """
    require(world in ('IN','OUT') and method in VARIANTS, 'Invalid supplementary case')
    directory, data_path = Path(directory), Path(data_path)
    config = variant_config(config, method)
    if 'variant_configs' in protocol:
        require(config == source.load(authenticated(protocol['variant_configs'][method['id']])), 'Native variant config differs from freeze')
    name = method['id']; policy_path = directory/(name+'-policy.json')
    result_path = directory/(name+'.json'); execution = directory/(name+'-execution.json')
    require(not any((directory/(name+suffix)).exists() for suffix in ('-attempt.json','-execution.json','.json','-receipt.json')), 'Native case exists; no retry')
    primary.write(policy_path,config)
    command = primary.native_command(directory/'AggregationReplay', data_path, policy_path, result_path, method)
    frozen = {str(q):source.sha(q) for q in (data_path,directory/'AggregationReplay',policy_path)}
    if 'native_binary_sha256' in protocol:
        require(frozen[str(directory/'AggregationReplay')] == protocol['native_binary_sha256'], 'Native binary changed')
    primary.write(directory/(name+'-attempt.json'),dict(started_at=source.now(),command=command,wall_cap_s=protocol['native_wall_budget_s']))
    started = time.perf_counter(); receipt = dict(status='failed',command=command)
    try:
        completed = subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=protocol['native_wall_budget_s'],umask=0o077)
        receipt.update(status='complete' if completed.returncode == 0 else 'failed',returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr)
    except subprocess.TimeoutExpired:
        receipt.update(status='timeout')
    except BaseException as error:
        receipt.update(status='interrupted',error=str(error)); raise
    finally:
        receipt['seconds'] = time.perf_counter()-started; primary.write(execution,receipt)
    require(receipt['status'] == 'complete', 'Native failed or exceeded cap: '+name)
    primary.pilot.unchanged(frozen)
    data,result = source.load(data_path),source.load(result_path)
    validate_native(result,data,config,method)
    audit = primary.independent.audit(data,config,result,max_cells=protocol['audit_max_cells'])
    require(audit.get('status') == 'verified' and audit.get('scalar',{}).get('valid') is True, 'Independent hard-policy/source audit failed')
    public = semantic.export_public(result,config['semantic_taxonomy'],availability_model=primary.pilot.AVAILABILITY)
    forbidden = {data['run_id'],data['sensor_id']} | {r['id'] for b in data['batches'] for r in b['observations']}
    primary.pilot.public_contract(public,config,forbidden)
    primary.write(directory/(name+'-audit.json'),audit); primary.write(directory/(name+'-public.json'),public)
    row = primary.row_for(group,world,method,public,knowledge,data,audit,result)
    primary.write(directory/(name+'-row.json'),row); primary.pilot.unchanged(frozen)
    record = dict(method_id=name,world=world,status='verified',artifacts={q.name:primary.artifact(directory,q) for q in
        (result_path,directory/(name+'-audit.json'),directory/(name+'-public.json'),directory/(name+'-row.json'),execution,policy_path)},
        independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),native_seconds=receipt['seconds'])
    primary.write(directory/(name+'-receipt.json'),record)
    print('supplement_native_done group='+group['group_id']+' world='+world+' method='+name,flush=True)
    return record,row


def validate_pair_import(directory, imported):
    directory = Path(directory)
    for name in ('in.json','out.json','auxiliary.json','pair.json'):
        require(source.sha(directory/name) == imported['files'][name]['sha256'], 'Source/target/auxiliary pair differs: '+name)
        authenticated(imported['files'][name])
    pair = source.load(directory/'pair.json')
    require(pair['split'] == imported['split'] and source.sha(directory/'auxiliary.json') == pair['auxiliary_sha256'], 'Imported pair role/auxiliary digest differs')
    return pair


def process_group(output, p, context, group):
    directory = output/'groups'/group['group_id']; require(not directory.exists(), 'Group exists; no retry')
    directory.mkdir(mode=0o700)
    imported = p['imported_groups'][group['group_id']]
    primary.write(directory/'attempt.json',dict(group_id=group['group_id'],split=group['split'],started_at=source.now(),original_pair=imported['files']['pair.json']))
    for name in ('in.json','out.json','auxiliary.json','pair.json'):
        os.link(authenticated(imported['files'][name]),directory/name)
    pair = validate_pair_import(directory,imported)
    require(pair['group_id'] == group['group_id'] and pair['split'] == group['split'], 'Imported pair identity differs')
    primary.split.verify_actual_sources(context['manifest'],[pair],ROOT)
    knowledge = source.load(directory/'auxiliary.json'); base = source.load(authenticated(p['original_config']))
    rows,cases,archives = [],[],{}
    for world in ('IN','OUT'):
        work = directory/world; work.mkdir(mode=0o700)
        os.link(directory/('in.json' if world == 'IN' else 'out.json'),work/'input.json')
        os.link(ROOT/'simulator/build/AggregationReplay',work/'AggregationReplay')
        for method in VARIANTS:
            require(shutil.disk_usage(output).free >= p['minimum_free_bytes'], 'Insufficient free disk for new supplementary case')
            try:
                record,row = run_case(work,work/'input.json',base,method,group,world,knowledge,p); rows.append(row)
            except Exception as error:
                record = dict(method_id=method['id'],world=world,status='failed',error=str(error))
                primary.write(work/(method['id']+'-failed.json'),record)
            cases.append(record)
        archives[world] = {}
        for path in sorted(work.glob('*.json')):
            if path.name == 'input.json' or path.name.endswith(('-policy.json','-row.json','-execution.json','-receipt.json','-attempt.json','-failed.json')):
                continue
            archives[world][path.name] = primary.archive_file(path)
    primary.write(directory/'rows.json',rows); primary.write(directory/'archive-receipt.json',archives)
    original_summary = source.load(authenticated(imported['files']['summary.json']))
    summary = dict(group_id=group['group_id'],split=group['split'],status='verified' if len(rows) == 8 and len(cases) == 8 and all(c['status'] == 'verified' for c in cases) else 'incomplete',
                   pair=original_summary['pair'],cases=cases,rows=primary.artifact(directory,directory/'rows.json'),archives=primary.artifact(directory,directory/'archive-receipt.json'))
    primary.write(directory/'summary.json',summary)
    primary.write(directory/'supplement-receipt.json',dict(schema=SIDECAR_SCHEMA,protocol_sha256=source.sha(output/'protocol.json'),
        original_pair=imported['files']['pair.json'],source_pair_hashes={n:source.sha(directory/n) for n in ('in.json','out.json','auxiliary.json','pair.json')},
        summary_sha256=source.sha(directory/'summary.json'),rows_sha256=source.sha(directory/'rows.json')))
    return summary


def collect_new(output,p,context,*,verify_archives=False,require_complete=False):
    rows,summaries = primary.collect(output,context['manifest'],verify_archives=verify_archives)
    expected_ids = {m['id'] for m in VARIANTS}
    for summary in summaries:
        if summary['status'] in ('not_attempted','interrupted'):
            continue
        directory = output/'groups'/summary['group_id']; imported = p['imported_groups'][summary['group_id']]
        side = source.load(directory/'supplement-receipt.json'); pair = validate_pair_import(directory,imported)
        require(side['schema'] == SIDECAR_SCHEMA and side['protocol_sha256'] == source.sha(output/'protocol.json')
                and side['original_pair'] == imported['files']['pair.json']
                and side['source_pair_hashes'] == {n:source.sha(directory/n) for n in ('in.json','out.json','auxiliary.json','pair.json')}
                and side['summary_sha256'] == source.sha(directory/'summary.json') and side['rows_sha256'] == summary['rows']['sha256'], 'Supplement group binding differs')
        expected_cases = {(m,'IN') for m in expected_ids} | {(m,'OUT') for m in expected_ids}
        require(len(summary['cases']) == 8 and {(c['method_id'],c['world']) for c in summary['cases']} == expected_cases, 'Supplement group method/world matrix differs')
        for c in summary['cases']:
            if c['status'] == 'verified':
                require(c['independent_audit'] == dict(status='verified',scalar_valid=True,published_policy_violations=0), 'Supplement audit claim differs')
        require(summary['pair']['group_id'] == pair['group_id'] and summary['pair']['split'] == pair['split'], 'Supplement summary pair role differs')
    analysis._checked_rows(rows,window.expected_groups(context['manifest']),[m['id'] for m in VARIANTS],allow_test=True)
    if require_complete:
        require(len(rows) == 576 and len(summaries) == 72 and all(s['status'] == 'verified'
            and len(s.get('cases',[])) == 8 and all(c['status'] == 'verified' for c in s['cases'])
            for s in summaries), 'All72x4x2 verified supplementary streams required')
    return rows,summaries


def run_utility(output):
    output,p,context = read_protocol(output)
    require(not any((output/name).exists() for name in FIT_OUTPUTS), 'Utility generation cannot follow MIA fitting attempt')
    for group in context['manifest']['groups']:
        directory = output/'groups'/group['group_id']
        if directory.exists():
            require((directory/'summary.json').is_file(), 'Interrupted group cannot be retried or silently skipped')
            continue
        print('supplement_group_start '+group['group_id']+' '+group['split'],flush=True)
        summary = process_group(output,p,context,group)
        print('supplement_group_done '+group['group_id']+' status='+summary['status'],flush=True)
    return collect_new(output,p,context,require_complete=True)


def combined_rows_and_summaries(output,p,context,*,verify_archives=False):
    new_rows,new_summaries = collect_new(output,p,context,verify_archives=verify_archives,require_complete=True)
    old_by = {s['group_id']:s for s in context['original_summaries']}
    combined = []
    for summary in new_summaries:
        old = old_by[summary['group_id']]
        require(old['split'] == summary['split'] and old['pair'] == summary['pair'], 'New pair differs from original paired family')
        combined.append(dict(group_id=summary['group_id'],split=summary['split'],status='verified',pair=old['pair'],
            cases=old['cases']+summary['cases'],imported_original_summary=p['imported_groups'][summary['group_id']]['files']['summary.json'],
            new_summary=reference(output/'groups'/summary['group_id']/'summary.json')))
    rows = context['original_rows']+new_rows
    require(len(rows) == 2160 and all(len(s['cases']) == 30 for s in combined), 'Combined15-method matrix differs')
    return rows,combined


def percentile(values, fraction):
    require(bool(values), 'Empty percentile')
    ordered = sorted(values); point = (len(ordered)-1)*fraction; lower = int(point); upper = min(lower+1,len(ordered)-1)
    return ordered[lower]+(point-lower)*(ordered[upper]-ordered[lower])


def native_execution_summary(output,p,context):
    by_method = defaultdict(list); by_method_test = defaultdict(list)
    for summary in context['original_summaries']:
        directory = Path(p['imported_groups'][summary['group_id']]['directory'])
        for case in summary['cases']:
            if case['status'] != 'verified' or 'native_seconds' not in case:
                continue
            execution = directory/case['world']/(case['method_id']+'-execution.json')
            value = source.load(execution)
            require(value['status'] == 'complete' and value['returncode'] == 0 and value['seconds'] == case['native_seconds'], 'Imported native timing differs')
            by_method[case['method_id']].append(value['seconds'])
            if summary['split'] == 'test':by_method_test[case['method_id']].append(value['seconds'])
    for group in context['manifest']['groups']:
        directory = output/'groups'/group['group_id']
        summary = source.load(directory/'summary.json')
        for case in summary['cases']:
            value = source.load(directory/case['world']/(case['method_id']+'-execution.json'))
            require(value['status'] == 'complete' and value['returncode'] == 0 and value['seconds'] == case['native_seconds'], 'Supplement native timing differs')
            by_method[case['method_id']].append(value['seconds'])
            if summary['split'] == 'test':by_method_test[case['method_id']].append(value['seconds'])
    def aggregate(values):
        return {key:dict(runs=len(v),wall_seconds_mean=sum(v)/len(v),wall_seconds_p50=percentile(v,.5),
                         wall_seconds_p95=percentile(v,.95),wall_seconds_maximum=max(v)) for key,v in sorted(values.items())}
    return dict(imported_native_executions=1296,new_native_executions=576,total_native_executions=1872,
        imported_regional_streams=288,new_rows=576,old_rows=1584,total_rows=2160,native_policy_violations=0,
        by_method=aggregate(by_method),by_method_test=aggregate(by_method_test),
        scope='Native subprocess elapsed diagnostics include input validation/I/O; core_processing_ms is separately recorded. Old and new runs occurred at different times; neither throughput nor these samples certify live deadlines.')


def public_lineage(output,p,context,*,mia=False):
    refs = p['parent_references']
    return dict(supplement_protocol_sha256=source.sha(output/'protocol.json'),
        original_report_sha256=refs['report']['sha256'],original_models_sha256=refs['models']['sha256'],
        original_model_lock_sha256=refs['models_lock']['sha256'],original_rows_sha256=context['original_report']['analysis']['all_rows_sha256'],
        original_train_cal_rows_sha256=refs['train_cal_rows']['sha256'],repair_protocol_sha256=refs['protocol']['sha256'],
        validation_ledger_sha256=refs['validation_ledger']['sha256'],hard_policy_sha256=p['hard_policy_sha256'],original_config_sha256=p['original_config']['sha256'],
        hard_policy_unchanged=True,source_resimulations=0,source_replacements=0,original_model_refits=0,original_threshold_retunes=0,
        imported_groups=72,imported_method_world_rows=1584,new_method_world_rows=576,new_native_executions=576,
        old_locked_variants=22,new_attack_variants=8 if mia else 0,
        diagnostic_repair=source.load(authenticated(refs['repair_lineage'])),
        scope=p['scope'])


def report_base(output,p,context,rows,summaries):
    pairs = [s['pair'] for s in summaries]
    audit = primary.split.verify_actual_sources(context['manifest'],pairs,ROOT,require_complete=True); audit['status']='verified'
    return dict(**window._bindings(context['main']),source_protocol=context['repair_protocol']['anchors']['source_protocol'],
        import_ledger=context['main']['import_ledger'],implementation_sha256=source.sha(output/'protocol.json'),
        supplement_id=p['supplement_id'],method_catalog=deepcopy(p['original_methods'])+deepcopy(list(VARIANTS)),
        group_outcomes=summaries,source_split_audit=audit,source_quality=window.source_quality(context['cases'],context['manifest']),
        native_execution_summary=native_execution_summary(output,p,context),
        strategy_supplement=dict(protocol=reference(output/'protocol.json'),parent_references=p['parent_references'],
            public_lineage=public_lineage(output,p,context),hard_policy_unchanged=True,scope=p['scope']))


def utility_report(output):
    output,p,context = read_protocol(output)
    require(not any((output/name).exists() for name in FIT_OUTPUTS), 'Utility gate must precede MIA fitting attempt')
    require(not (output/'utility-report.json').exists(), 'Utility report exists; no overwrite')
    rows,summaries = combined_rows_and_summaries(output,p,context,verify_archives=True)
    value = dict(schema=UTILITY_SCHEMA,**report_base(output,p,context,rows,summaries),
        utility={m['id']:analysis._utility([r for r in rows if r['method_id'] == m['id']],window.expected_groups(context['manifest']))
                 for m in p['original_methods']+list(VARIANTS)},mia_status='not_started',
        new_rows_sha256=analysis.digest([r for r in rows if r['method_id'] in {m['id'] for m in VARIANTS}]))
    primary.write(output/'utility-report.json',value)
    return value


def combine_models(original,new_attacks,rows,expected_groups,method_ids):
    require(set(new_attacks) == {m['id'] for m in VARIANTS}, 'All four new attack families required')
    require(not set(new_attacks) & set(original['attacks']), 'Original model replacement forbidden')
    checked = analysis._checked_rows(rows,expected_groups,method_ids,allow_test=False)
    require(not any(r['split'] == 'test' for r in rows), 'TEST rows cannot fit/scaletrain')
    result = deepcopy(original)
    result.pop('prepared_sha256')
    result['attacks'].update(deepcopy(new_attacks))
    require(all(result['attacks'][m] == original['attacks'][m] for m in original['attacks'])
            and result['controls'] == original['controls'], 'Original fitted objects changed')
    result.update(method_ids=list(method_ids),expected_method_ids=list(method_ids),
        training_calibration_rows_sha256=analysis.digest(checked),training_calibration_rows=len(checked),
        training_group_ids=sorted({r['group_id'] for r in checked if r['split']=='train'}),
        calibration_group_ids=sorted({r['group_id'] for r in checked if r['split']=='calibration'}),
        expected_groups=deepcopy(expected_groups),test_rows_seen=0,
        models=[dict(method_id=m,representation=r,**deepcopy(result['attacks'][m][r])) for m in method_ids for r in analysis.REPRESENTATIONS],
        scope='Derived combined view: original22 attack/control objects preserved;8 new TRAIN-only fits/CAL thresholds; exploratory existing-TEST extension, no original refit.')
    result['prepared_sha256'] = analysis.digest(result)
    analysis.validate_model_lock(result,checked,require_complete=True)
    return result


def fit_mia(output):
    output,p,context = read_protocol(output)
    require(not any((output/name).exists() for name in FIT_OUTPUTS), 'No fitting retry or post-score fit')
    utility = source.load(output/'utility-report.json')
    require(utility['schema']==UTILITY_SCHEMA and utility['mia_status']=='not_started'
            and utility['strategy_supplement']['protocol']==reference(output/'protocol.json'), 'Completed utility gate required before MIA')
    rows,summaries = combined_rows_and_summaries(output,p,context)
    require(utility['new_rows_sha256']==analysis.digest([r for r in rows if r['method_id'] in {m['id'] for m in VARIANTS}]), 'Utility gate rows changed')
    training = [r for r in rows if r['split'] in ('train','calibration')]
    expected = window.expected_groups(context['manifest'])
    primary.write(output/'mia-fit-attempt.json',dict(schema='ump.urban-strategy-supplement-fit-attempt.v1',
        status='attempted',started_at=source.now(),protocol=reference(output/'protocol.json'),utility_gate=reference(output/'utility-report.json'),
        training_rows_sha256=analysis.digest(analysis._checked_rows(training,expected,[m['id'] for m in p['original_methods']+list(VARIANTS)],allow_test=False)),
        new_fit_count=8,test_rows_seen_by_fitter=0,model_parameters=deepcopy(analysis.MODEL_PARAMETERS)))
    attacks = {}; completed_fits = 0
    try:
        for method in VARIANTS:
            selected = [r for r in training if r['method_id']==method['id']]
            attacks[method['id']] = {}
            for name,(field,_) in analysis.REPRESENTATIONS.items():
                attacks[method['id']][name] = analysis._fit(selected,lambda row,f=field:row[f],expected)
                completed_fits += 1
        methods = [m['id'] for m in p['original_methods']+list(VARIANTS)]
        model = combine_models(context['models'],attacks,training,expected,methods)
    except Exception as error:
        primary.write(output/'mia-fit-failed.json',dict(status='failed',error=str(error),completed_fit_invocations=completed_fits,
            fit_attempt=reference(output/'mia-fit-attempt.json'),no_retry=True))
        raise
    primary.write(output/'train-cal-rows.json',training); primary.write(output/'models.json',model)
    lock = dict(schema=LOCK_SCHEMA,status='locked_before_supplement_TEST_scoring',created_at=source.now(),
        protocol=reference(output/'protocol.json'),utility_gate=reference(output/'utility-report.json'),
        models=reference(output/'models.json'),data=reference(output/'train-cal-rows.json'),new_fit_count=8,
        fit_attempt=reference(output/'mia-fit-attempt.json'),
        original_models=p['parent_references']['models'],original_model_lock=p['parent_references']['models_lock'],
        original_model_refits=0,original_threshold_retunes=0,training_groups=24,calibration_groups=16,test_rows_seen_by_fitter=0,
        test_sources_already_seen=True,scope=p['scope'])
    primary.write(output/'models-lock.json',lock)
    return lock


def authenticate_model_lock(output,p,context,training):
    lock = source.load(output/'models-lock.json')
    require(lock['schema']==LOCK_SCHEMA and lock['status']=='locked_before_supplement_TEST_scoring'
            and lock['protocol']==reference(output/'protocol.json') and lock['utility_gate']==reference(output/'utility-report.json')
            and lock['new_fit_count']==8 and lock['test_rows_seen_by_fitter']==0
            and lock['training_groups']==24 and lock['calibration_groups']==16 and lock['test_sources_already_seen'] is True
            and lock['fit_attempt']==reference(output/'mia-fit-attempt.json')
            and lock['original_models']==p['parent_references']['models'] and lock['original_model_lock']==p['parent_references']['models_lock']
            and lock['original_model_refits']==lock['original_threshold_retunes']==0, 'Supplement model-lock scope differs')
    attempt=source.load(authenticated(lock['fit_attempt']))
    require(attempt['schema']=='ump.urban-strategy-supplement-fit-attempt.v1' and attempt['status']=='attempted'
            and attempt['protocol']==reference(output/'protocol.json') and attempt['utility_gate']==reference(output/'utility-report.json')
            and attempt['new_fit_count']==8 and attempt['test_rows_seen_by_fitter']==0
            and attempt['model_parameters']==analysis.MODEL_PARAMETERS, 'Fit attempt binding differs')
    model=source.load(authenticated(lock['models'])); locked_rows=source.load(authenticated(lock['data']))
    require(attempt['training_rows_sha256']==analysis.digest(analysis._checked_rows(training,model['expected_groups'],model['method_ids'],allow_test=False)), 'Fit input rows differ from pre-fit attempt')
    require(analysis.digest(analysis._checked_rows(training,model['expected_groups'],model['method_ids'],allow_test=False))
            == analysis.digest(analysis._checked_rows(locked_rows,model['expected_groups'],model['method_ids'],allow_test=False)), 'Locked supplementary training rows differ')
    require(all(model['attacks'][m]==context['models']['attacks'][m] for m in context['models']['attacks'])
            and model['controls']==context['models']['controls'], 'Original model/control mutation forbidden')
    analysis.validate_model_lock(model,locked_rows,require_complete=True)
    return model


def exploratory_contrasts(assessed):
    result={}
    for name,left,right,seed in CONTRASTS:
        reps={}
        for rep in analysis.REPRESENTATIONS:
            a,b=assessed['attacks'][left][rep],assessed['attacks'][right][rep]
            reps[rep]=(analysis.paired_source_auc_difference(a['group_scores'],b['group_scores'],replicates=1000,seed=seed)
                       if a['status']==b['status']=='evaluated' else dict(status='unavailable',left_status=a['status'],right_status=b['status']))
        result[name]=dict(left=left,right=right,metric='ROC_AUC',representations=reps,
            scope='Exploratory paired recording comparison, conditional on fixed models; marginal intervals without multiplicity adjustment.')
    return result


def fully_verified_parent(p):
    context=parent_context(Path(p['parent_output']),verify_archives=True,verify_raw=True)
    require(parent_refs(context)==p['parent_references'] and import_groups(context)==p['imported_groups'],
            'Fully revalidated parent differs from frozen imports')
    return context


def assess_mia(output):
    output,p,context = read_protocol(output)
    context=fully_verified_parent(p)
    rows,summaries = combined_rows_and_summaries(output,p,context,verify_archives=True)
    training=[r for r in rows if r['split']!='test']
    models=authenticate_model_lock(output,p,context,training)
    assessed=analysis.evaluate_models(models,rows)
    old=context['original_report']['analysis']
    require(assessed['primary_contrast']==old['primary_contrast'], 'Original primary contrast changed')
    require(all(assessed['attacks'][m]==old['attacks'][m] for m in old['attacks'])
            and assessed['controls']==old['controls'], 'Original attack/control assessment changed')
    base=report_base(output,p,context,rows,summaries)
    base['strategy_supplement']['public_lineage']=public_lineage(output,p,context,mia=True)
    value=dict(schema=REPORT_SCHEMA,**base,analysis=assessed,exploratory_contrasts=exploratory_contrasts(assessed),
        original_primary_result_preserved=True,models_lock=reference(output/'models-lock.json'),
        final_verification=dict(original_full_raw_validations=72,original_archive_groups=72,new_archive_groups=72,
            physical_audit_reexecutions=0,scope='Final assessment repeats full raw-source validation against original physical proof chains and decompresses old/new archives; no physical audit or simulation is rerun.'))
    primary.write(output/'final-report.json',value)
    return value


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare','check','run-utility','utility-report','fit-mia','assess-mia'):
        action.add_argument('--'+name,type=Path)
    parser.add_argument('--parent-study',type=Path,default=DEFAULT_PARENT)
    parser.add_argument('--contract',type=Path)
    args=parser.parse_args(argv)
    if args.prepare:
        require(args.contract is not None,'Explicit supplementary protocol document required')
        print(prepare(args.prepare,args.parent_study,contract=args.contract));return
    output=args.check or args.run_utility or args.utility_report or args.fit_mia or args.assess_mia
    descriptor=os.open(output/'.strategy-execution.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.check:
            read_protocol(output);print('verified: supplementary methods, unchanged hard policy and imported original evidence')
        elif args.run_utility:run_utility(output)
        elif args.utility_report:utility_report(output)
        elif args.fit_mia:fit_mia(output)
        else:assess_mia(output)
    finally:os.close(descriptor)


if __name__=='__main__':
    main()
