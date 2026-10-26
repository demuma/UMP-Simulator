#!/usr/bin/env python3
"""Serial, resumable P25.4 execution of the immutable urban risk/utility study.

Primary raw sources stay local. Every native case is attempted once; audited raw
results, audit and public transcripts are losslessly gzip archived after regional
composition. Compact private feature/utility rows drive TRAIN-only fitting, CAL
threshold locking and the untouched grouped TEST assessment. No source/helper,
policy, feature set or threshold is tuned against TEST outcomes.
"""
from __future__ import annotations
import argparse
from collections import Counter
from copy import deepcopy
import fcntl
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import empirical_privacy as scalar
import regional_public_transcript as regional
import run_local_policy_replay as independent
import run_urban_privacy_channel_pilot as pilot
import run_urban_privacy_primary_sources as sources
import run_urban_privacy_sources as source
import static_regional_schedule as static
import urban_privacy_analysis as analysis
import urban_privacy_fixture as fixture
import urban_privacy_queries as queries
import urban_privacy_split as split

ROOT = source.ROOT
SCHEMA = 'ump.urban-primary-execution.v1'
IMPLEMENTATION_FILES = tuple('tools/evaluation/' + name for name in (
    'run_urban_privacy_primary_sources.py', 'run_urban_privacy_primary.py',
    'urban_privacy_statistics.py', 'urban_privacy_queries.py', 'urban_privacy_analysis.py',
    'test_run_urban_privacy_primary_sources.py', 'test_run_urban_privacy_primary.py',
    'test_urban_privacy_statistics.py', 'test_urban_privacy_queries.py', 'test_urban_privacy_analysis.py'))


def require(condition, message):
    fixture.insist(condition, message)


def write(path, value):
    source.write(path, value)


def artifact(root, path):
    path = Path(path)
    return dict(path=str(path.relative_to(root)), sha256=source.sha(path))


def authenticate_protocol(output):
    output = fixture.safe_path(output, root=ROOT / 'results')
    protocol = source.load(output / 'protocol.json')
    require(protocol.get('schema') == SCHEMA and protocol.get('output_directory') == str(output), 'Wrong main execution protocol')
    require(source.sha(output / 'protocol.json') == fixture.read_bytes(output / 'protocol.sha256').decode().strip(), 'Execution protocol changed')
    split.verify_freeze(Path(protocol['freeze_directory']))
    for name, digest in protocol['existing_files_sha256'].items():
        require(source.sha(ROOT / name) == digest, 'Frozen source/helper changed: ' + name)
    for name, digest in protocol['implementation_files_sha256'].items():
        require(source.sha(ROOT / name) == digest, 'P25.4 implementation changed: ' + name)
    require(source.sha(Path(protocol['freeze_directory']) / 'manifest.json') == protocol['manifest_sha256'], 'Frozen design changed')
    return output, protocol, source.load(Path(protocol['freeze_directory']) / 'manifest.json')


def prepare(freeze, source_directory, output):
    freeze = fixture.safe_path(freeze, root=ROOT / 'results')
    verified = split.verify_freeze(freeze)
    source_directory, source_protocol, manifest = sources.read_protocol(source_directory)
    require(verified['manifest_sha256'] == source_protocol['manifest_sha256'], 'Source and main execution designs differ')
    output = fixture.new_output(output)
    (output / 'groups').mkdir(mode=0o700)
    existing = {row['path']: row['sha256'] for row in manifest['design']['generator']['evidence_files']}
    protocol = dict(schema=SCHEMA, prepared_at=source.now(), output_directory=str(output), freeze_directory=str(freeze),
                    manifest_sha256=verified['manifest_sha256'], source_directory=str(source_directory),
                    source_protocol_sha256=source.sha(source_directory / 'protocol.json'), existing_files_sha256=existing,
                    implementation_files_sha256={name: source.sha(ROOT / name) for name in IMPLEMENTATION_FILES},
                    native_binary_sha256=source.sha(ROOT / 'simulator/build/AggregationReplay'),
                    source_order=[row['group_id'] for row in manifest['groups']], native_wall_budget_s=180,
                    audit_max_cells=1000000, minimum_free_bytes=sources.MIN_FREE_BYTES,
                    archival='Lossless gzip per created result/audit/public file after all derived uses; retain raw SHA and verified archive SHA. No source motion or Mongo database is deleted.',
                    availability='final_snapshot_at_horizon', timing_scope='Operational replay elapsed diagnostics only; source/CPU/audit/IO overlap not a real-time benchmark.',
                    failure_rule='Never retry a native attempt or replace a source; missing/failed family remains explicit and model-dependent evidence may be NA.')
    write(output / 'protocol.json', protocol)
    fixture.write_new(output / 'protocol.sha256', (source.sha(output / 'protocol.json') + '\n').encode())
    return output


def select_pair(data, source_sha, group):
    types = {row['type'] for batch in data['batches'] for row in batch['observations']}
    traces = fixture.validate_replay(data, types)
    eligible = sorted(identity for identity, trace in traces.items() if len(trace) >= 2)
    require(bool(eligible), 'No eligible observed episode')
    target_seed = group['seeds']['target_selection']
    target = min(eligible, key=lambda identity: (fixture.digest(fixture.canonical(['target-v1', target_seed, source_sha, identity])), identity))
    aux_seed = group['seeds']['auxiliary_selection']
    ranked = sorted(traces[target], key=lambda point: (fixture.digest(fixture.canonical(['aux-v1', aux_seed, source_sha, target, point])), fixture.canonical(point)))
    knowledge = sorted(deepcopy(ranked[:max(1, (len(ranked)+3)//4)]), key=lambda point: point['observed_at_ms'])
    absent = deepcopy(data)
    for batch in absent['batches']:
        batch['observations'] = [row for row in batch['observations'] if row['id'] != target]
    require(fixture.counts(data)['observations'] - fixture.counts(absent)['observations'] == len(traces[target]), 'Pair removal count mismatch')
    return absent, knowledge, dict(target_id=target, eligible_episodes=len(eligible), target_observations=len(traces[target]),
                                   auxiliary_points=len(knowledge), target_role_seed=target_seed, auxiliary_role_seed=aux_seed)


def positive_control(data, knowledge):
    points = {(batch['observed_at_ms'], row['x'], row['y'], fixture.cell_id(row['x'], row['y'], data['coverage']))
              for batch in data['batches'] for row in batch['observations']}
    return sum((row['observed_at_ms'], row['x'], row['y'], row['cell_id']) in points for row in knowledge) / len(knowledge)


def native_command(binary, source_path, policy_path, result_path, method):
    mode = 'fixed' if method['kind'] == 'native_fixed' else method['strategy']
    command = [str(binary), '--input', str(source_path), '--config', str(policy_path), '--mode', mode,
               '--output', str(result_path), '--progress-step-ms', '50']
    if method['kind'] == 'native_fixed':
        command += ['--fixed-depth', str(method['fixed_depth']), '--fixed-window-ms', str(method['window_ms'])]
    return command


def validate_native(result, data, config, method):
    mode = 'fixed' if method['kind'] == 'native_fixed' else method['strategy']
    require(result.get('schema') == 'ump.replay-result.v1' and result.get('mode') == mode, 'Native method mismatch')
    require(all(result.get('source', {}).get(key) == data[key] for key in ('run_id','sensor_id','coverage','sampling_period_ms','end_ms')), 'Native source/header mismatch')
    require(result['source']['application_id'] == config['application_id'], 'Native application mismatch')
    parameters = result['parameters']
    require(parameters.get('progress_step_ms') == 50 and parameters.get('progress_origin_ms') == 0, 'Native progress clock changed')
    if mode == 'fixed':
        require(parameters.get('fixed_depth') == method['fixed_depth'] and parameters.get('window_ms') == method['window_ms']
                and parameters.get('coordination') == 'common_window', 'Fixed schedule differs')
    else:
        require(parameters.get('coordination') == 'cell_local', 'Adaptive coordination differs')
        require(parameters.get('semantic_secondary_strategy') == method['secondary_strategy']
                and parameters.get('release_trigger') == method['release_trigger'], 'Adaptive priority/release trigger differs')
    total = fixture.counts(data)['observations']
    require(result['input_observation_contributions'] == result['accounted_observation_contributions'] == total, 'Native accounting mismatch')


def native_utility(data, public, audit, result=None):
    total = fixture.counts(data)['observations']
    cells = [(release, cell) for release in public['releases'] for cell in release['cells']]
    kept = sum(cell['observation_contributions'] for _,cell in cells)
    loss = math.fsum(cell['observation_contributions'] * cell['semantic']['semantic_mean_loss'] for _,cell in cells)
    def mean(function):
        return math.fsum(cell['observation_contributions'] * function(release,cell) for release,cell in cells) / kept if kept else None
    accounting = audit.get('source_accounting', audit.get('stats', {}).get('source_accounting'))
    # Existing suppression-OFF audits expose source cohorts but not always
    # per-observation seal delays; derive these solely for private utility.
    delays = Counter()
    by_time = {batch['observed_at_ms']: batch['observations'] for batch in data['batches']}
    period = data['sampling_period_ms']; leaf = data['coverage']['leaf_depth']
    for release, cell in cells:
        for timestamp in range(max(period, ((release['start_ms'] + period - 1)//period)*period), release['end_ms'], period):
            count = sum(row['cell_id'] >> (2*(leaf-cell['depth'])) == cell['cell_id'] for row in by_time.get(timestamp, []))
            delays[release['sealed_at_ms']-timestamp] += count
    require(sum(delays.values()) == kept, 'Retained delay input accounting differs')
    application = queries.evaluate(data, public)
    return dict(input_observations=total, retained_observations=kept, retained_fraction=kept/total if total else None,
                full_input_J=(total-kept+loss)/total if total else None,
                full_input_semantic_loss=(total-kept+loss)/total if total else None,
                full_input_loss_definition='J=(N_input-N_retained+sum_retained taxonomy_loss)/N_input; semantic loss including unit omission cost, not another independent metric.',
                retained_semantic_loss=loss/kept if kept else None, mean_retained_cell_side_m=mean(lambda r,c:c['width']),
                mean_retained_interval_ms=mean(lambda r,c:r['end_ms']-r['start_ms']),
                logical_seal_delay_ms=static.delay_stats(delays), published_cells=len(cells),
                core_processing_ms=result.get('runtime',{}).get('processing_ms') if result is not None else None,
                query_exact=application['exact']['summary'], query_estimate=application['estimate']['summary'],
                published_policy_violations=0, source_accounting=accounting,
                runtime_scope='Native operational diagnostic; regional runtime unavailable; no wall-clock delivery claim.')


def row_for(group, world, method, public, knowledge, data, audit, result=None):
    features, checks = pilot.feature_check(public, knowledge)
    scalar_values = scalar.feature_vector(__import__('semantic_privacy')._scalar_projection(public), knowledge, include_geometry=True)
    require(len(features['values']) == 111 and len(scalar_values) == 31, 'Frozen feature dimensions differ')
    empty = deepcopy(public); empty['releases'] = []
    no_output, _ = pilot.feature_check(empty, knowledge)
    return dict(group_id=group['group_id'], split=group['split'], world=world, label=int(world=='IN'),
                method_id=method['id'], features=features['values'], scalar_features=scalar_values,
                auxiliary_features=analysis.auxiliary_features(knowledge, data['coverage'], data['end_ms']),
                controls=dict(prior_only=.5,unprotected=positive_control(data,knowledge),no_output_features=no_output['values']),
                utility=native_utility(data,public,audit,result), feature_checks=checks)


def run_native(directory, data_path, config, method, group, world, knowledge, protocol):
    import semantic_privacy as semantic
    name = method['id']; result_path = directory / (name + '.json'); execution = directory / (name + '-execution.json')
    if execution.exists():
        raise ValueError('Native attempt already exists; never retry: ' + name)
    command = native_command(directory/'AggregationReplay', data_path, directory/'policy.json', result_path, method)
    frozen = {str(path): source.sha(path) for path in (data_path, directory/'AggregationReplay', directory/'policy.json')}
    write(directory / (name + '-attempt.json'), dict(started_at=source.now(),command=command,wall_cap_s=protocol['native_wall_budget_s']))
    started = time.perf_counter()
    receipt = dict(status='failed', command=command)
    try:
        completed = subprocess.run(command,cwd=ROOT,text=True,capture_output=True,timeout=protocol['native_wall_budget_s'],umask=0o077)
        receipt.update(status='complete' if completed.returncode==0 else 'failed',returncode=completed.returncode,stdout=completed.stdout,stderr=completed.stderr)
    except subprocess.TimeoutExpired:
        receipt.update(status='timeout')
    except BaseException as error:
        receipt.update(status='interrupted',error=str(error)); raise
    finally:
        receipt['seconds']=time.perf_counter()-started; write(execution,receipt)
    require(receipt['status']=='complete','Native failed or exceeded cap: '+name)
    pilot.unchanged(frozen)
    data=source.load(data_path); result=source.load(result_path)
    validate_native(result,data,config,method)
    audited=deepcopy(config); audited['temporal_adaptation']['coordination']=result['parameters']['coordination']
    audit=independent.audit(data,audited,result,max_cells=protocol['audit_max_cells'])
    require(audit.get('status')=='verified' and audit.get('scalar',{}).get('valid') is True,'Independent policy/source audit failed')
    public=semantic.export_public(result,config['semantic_taxonomy'],availability_model=pilot.AVAILABILITY)
    forbidden={data['run_id'],data['sensor_id']} | {r['id'] for b in data['batches'] for r in b['observations']}
    pilot.public_contract(public,config,forbidden)
    write(directory/(name+'-audit.json'),audit); write(directory/(name+'-public.json'),public)
    row=row_for(group,world,method,public,knowledge,data,audit,result)
    write(directory/(name+'-row.json'),row)
    pilot.unchanged(frozen)
    record=dict(method_id=name,world=world,status='verified',artifacts={path.name:artifact(directory,path) for path in
                (result_path,directory/(name+'-audit.json'),directory/(name+'-public.json'),directory/(name+'-row.json'),execution)},
                independent_audit=dict(status='verified',scalar_valid=True,published_policy_violations=0),native_seconds=receipt['seconds'])
    write(directory/(name+'-receipt.json'),record)
    print(f"native_done group={group['group_id']} world={world} method={name} retained={row['utility']['retained_fraction']}",flush=True)
    return record,row


def compose(directory, config, method, group, world, knowledge, records):
    cases={}
    for window in static.WINDOWS:
        key=f"fixed{method['grid_side_m']}_{window}ms"
        require(records.get(key,{}).get('status')=='verified','Regional family has failed/missing component '+key)
        cases[str(window)]=dict(config=artifact(directory,directory/'policy.json'),result=artifact(directory,directory/(key+'.json')),
                                private_audit=artifact(directory,directory/(key+'-audit.json')),independent_audit=records[key]['independent_audit'])
    family=dict(schema=regional.FAMILY_SCHEMA,public_coverage=fixture.COVERAGE,sampling_period_ms=100,end_ms=300000,
                side_m=method['grid_side_m'],public_policy_id=config['policy_tree']['id'],method_alias=method['id'],
                source=artifact(directory,directory/'input.json'),native_binary=artifact(directory,directory/'AggregationReplay'),cases=cases)
    write(directory/(method['id']+'-family.json'),family)
    composed=regional.compose_family(directory,family,availability_model=pilot.AVAILABILITY)
    public=composed['public_transcript']; audit=composed['private_audit']
    data=source.load(directory/'input.json'); pilot.public_contract(public,config)
    row=row_for(group,world,method,public,knowledge,data,audit,None)
    require(row['utility']['retained_observations']==audit['stats']['retained_observation_contributions'],'Regional public/raw utility disagree')
    for suffix,value in (('-public.json',public),('-audit.json',audit),('-row.json',row)):
        write(directory/(method['id']+suffix),value)
    return dict(method_id=method['id'],world=world,status='verified',native_runtime=None),row


def archive_file(path):
    """Replace only this run's temporary artifact by a verified lossless copy."""
    expected=source.sha(path); target=path.with_name(path.name+'.gz')
    require(not target.exists(),'Refuse to overwrite archive')
    with path.open('rb') as incoming, target.open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6) as outgoing:
            shutil.copyfileobj(incoming,outgoing,1024*1024)
    target.chmod(0o600)
    check=hashlib.sha256()
    with gzip.open(target,'rb') as incoming:
        for chunk in iter(lambda:incoming.read(1024*1024),b''): check.update(chunk)
    require(check.hexdigest()==expected,'Archive round-trip hash mismatch')
    record=dict(path=target.name,sha256=source.sha(target),uncompressed_sha256=expected,uncompressed_bytes=path.stat().st_size)
    path.unlink()
    return record


def process_group(output, protocol, manifest, group, source_case, *, pair_selector=None):
    directory=output/'groups'/group['group_id']
    require(not directory.exists(),'Group exists; no retry/overwrite')
    directory.mkdir(mode=0o700)
    write(directory/'attempt.json',dict(group_id=group['group_id'],split=group['split'],started_at=source.now(),source=source_case['observations_sha256']))
    source_path=Path(source_case['replay_directory'])/'observations.json'
    require(source.sha(source_path)==source_case['observations_sha256'],'Source changed after authentication')
    present=source.load(source_path)
    absent,knowledge,target=(pair_selector or select_pair)(present,source.sha(source_path),group)
    os.link(source_path,directory/'in.json');write(directory/'out.json',absent);write(directory/'auxiliary.json',knowledge)
    pair=dict(group_id=group['group_id'],split=group['split'],source_generation_seed=group['seeds']['source_generation'],
              source=artifact(ROOT,directory/'in.json'),targets=[dict(target_slot='target-00',target_id=target['target_id'],out=artifact(ROOT,directory/'out.json'))])
    write(directory/'pair.json',dict(**pair,selection=target,auxiliary_sha256=source.sha(directory/'auxiliary.json')))
    # This gate runs before any recipient/native mechanism output exists.
    split.verify_actual_sources(manifest,[pair],ROOT)
    del present,absent
    config_path=Path(protocol['freeze_directory'])/'policy-local400.json'; config=source.load(config_path)
    native=[row for row in manifest['design']['methods'] if row['kind']!='regional_static']
    derived=[row for row in manifest['design']['methods'] if row['kind']=='regional_static']
    rows=[]; cases=[]; archives={}
    for world in ('IN','OUT'):
        work=directory/world;work.mkdir(mode=0o700)
        os.link(directory/('in.json' if world=='IN' else 'out.json'),work/'input.json')
        os.link(ROOT/'simulator/build/AggregationReplay',work/'AggregationReplay')
        fixture.write_new(work/'policy.json',fixture.read_bytes(config_path))
        records={}
        for method in native:
            require(shutil.disk_usage(output).free>=protocol['minimum_free_bytes'],'Less than 3 GiB free; no new native case')
            try:
                record,row=run_native(work,work/'input.json',config,method,group,world,knowledge,protocol)
                rows.append(row)
            except Exception as error:
                record=dict(method_id=method['id'],world=world,status='failed',error=str(error))
                write(work/(method['id']+'-failed.json'),record)
            records[method['id']]=record;cases.append(record)
        for method in derived:
            try:
                record,row=compose(work,config,method,group,world,knowledge,records);rows.append(row)
            except Exception as error:
                record=dict(method_id=method['id'],world=world,status='failed_dependency_or_audit',error=str(error))
            cases.append(record);write(work/(method['id']+'-receipt.json'),record)
        # All native files required by regional composition remain plain until
        # BOTH regional families have completed or recorded failure.
        archives[world]={}
        for path in sorted(work.glob('*.json')):
            if path.name in ('input.json','policy.json') or path.name.endswith(('-row.json','-execution.json','-receipt.json','-attempt.json','-failed.json')):
                continue
            archives[world][path.name]=archive_file(path)
    require(len(rows)<=22,'Unexpected method/world rows')
    write(directory/'rows.json',rows)
    write(directory/'archive-receipt.json',archives)
    summary=dict(group_id=group['group_id'],split=group['split'],status='verified' if len(rows)==22 and all(c['status']=='verified' for c in cases) else 'incomplete',
                 pair=pair,cases=cases,rows=artifact(directory,directory/'rows.json'),archives=artifact(directory,directory/'archive-receipt.json'))
    write(directory/'summary.json',summary)
    return summary


def verify_group_artifacts(directory, summary):
    archive_path = split.relative_file(directory, summary['archives'])
    archives = source.load(archive_path)
    for world, entries in archives.items():
        require(world in ('IN', 'OUT'), 'Unexpected archived world')
        work = directory / world
        for old_name, receipt in entries.items():
            require(Path(old_name).name == old_name and receipt['path'] == old_name + '.gz', 'Unsafe archive path')
            compressed = split.relative_file(work, {'path': receipt['path'], 'sha256': receipt['sha256']})
            digest = hashlib.sha256(); count = 0
            with gzip.open(compressed, 'rb') as stream:
                for chunk in iter(lambda: stream.read(1024*1024), b''):
                    count += len(chunk)
                    require(count <= fixture.MAX_FILE_BYTES, 'Archive exceeds per-artifact budget')
                    digest.update(chunk)
            require(digest.hexdigest() == receipt['uncompressed_sha256'] and count == receipt['uncompressed_bytes'],
                    'Archived original bytes changed')
    for case in summary['cases']:
        for name, reference in case.get('artifacts', {}).items():
            if name in archives.get(case['world'], {}):
                require(archives[case['world']][name]['uncompressed_sha256'] == reference['sha256'], 'Archive and native audit receipt disagree')
            else:
                split.relative_file(directory / case['world'], reference)


def collect(output,manifest,*,verify_archives=False):
    rows=[];summaries=[]
    for group in manifest['groups']:
        directory=output/'groups'/group['group_id'];path=directory/'summary.json'
        if path.is_file():
            summary=source.load(path)
            require(summary['group_id']==group['group_id'] and summary['split']==group['split'],'Group summary identity changed')
            row_path=split.relative_file(directory,summary['rows'])
            if verify_archives: verify_group_artifacts(directory, summary)
            group_rows = source.load(row_path)
            require(all(row['group_id'] == group['group_id'] and row['split'] == group['split'] for row in group_rows), 'Stored row source assignment differs')
            rows.extend(group_rows);summaries.append(summary)
        else:
            summaries.append(dict(group_id=group['group_id'],split=group['split'],status='interrupted' if directory.exists() else 'not_attempted'))
    return rows,summaries


def run(output,selected_splits,*,limit=None,implementation=None,model_lock=None):
    output,protocol,manifest=authenticate_protocol(output)
    if 'test' in selected_splits:
        sources.authenticate_test_gate(implementation,model_lock,protocol['manifest_sha256'])
    source_dir,source_protocol,_=sources.read_protocol(Path(protocol['source_directory']))
    require(source.sha(source_dir/'protocol.json')==protocol['source_protocol_sha256'],'Source capture protocol changed')
    source_summary=sources.summarize(source_dir,source_protocol,manifest)
    by_group={row['group_id']:row for row in source_summary['cases']}
    completed=0
    for group in manifest['groups']:
        if group['split'] not in selected_splits or (output/'groups'/group['group_id']).exists():continue
        if limit is not None and completed>=limit:break
        case=by_group[group['group_id']]
        if case['status']!='verified':
            print(f"group_unavailable group={group['group_id']} source_status={case['status']}",flush=True);continue
        print(f"group_start {group['group_id']} {group['split']}",flush=True)
        summary=process_group(output,protocol,manifest,group,case);completed+=1
        print(f"group_done {group['group_id']} status={summary['status']}",flush=True)
    rows,summaries=collect(output,manifest)
    snapshot='execution-summary-'+source.now().replace(':','').replace('+','_')+'.json'
    write(output/snapshot,dict(schema=SCHEMA,groups=summaries,rows=len(rows),planned_native_cases=1296,planned_recipient_streams=1584))


def freeze_implementation(output,unit_receipt,dev_receipt):
    output,protocol,manifest=authenticate_protocol(output)
    require(not any((output/'groups'/g['group_id']).exists() for g in manifest['groups'] if g['split']=='test'),'TEST already attempted')
    source_dir,sp,_=sources.read_protocol(Path(protocol['source_directory']))
    require(not any((source_dir/g['id']).exists() for g in sp['cases'] if g['split']=='test'),'TEST source already attempted')
    receipts=[]
    for path in (unit_receipt,dev_receipt):
        path=fixture.safe_path(path,root=ROOT/'results');value=source.load(path)
        require(value.get('status')=='verified' and value.get('test_data_seen') is False,'Unverified pre-TEST validation evidence')
        target=output/path.name;fixture.write_new(target,fixture.read_bytes(path));receipts.append(artifact(output,target))
    supplement=dict(schema='ump.urban-primary-implementation.v1',status='verified_before_test',created_at=source.now(),
                    freeze_directory=protocol['freeze_directory'],manifest_sha256=protocol['manifest_sha256'],
                    files_sha256=protocol['implementation_files_sha256'],test_receipts=receipts,
                    contract='No frozen analysis or native helper changed. Independent source capture; TRAIN-only fits; CAL-only thresholds; grouped TEST; exact queries and rates; all outcomes retained.',
                    archival=protocol['archival'])
    write(output/'implementation-supplement.json',supplement)
    return supplement


def lock_models(output):
    output,protocol,manifest=authenticate_protocol(output)
    supplement_path=output/'implementation-supplement.json';supplement=sources.authenticate_supplement(supplement_path,protocol['manifest_sha256'])
    source_dir,sp,_=sources.read_protocol(Path(protocol['source_directory']))
    require(not any((source_dir/g['id']).exists() for g in sp['cases'] if g['split']=='test'),'Lock models before TEST sources')
    rows,summaries=collect(output,manifest)
    relevant=[row for row in rows if row['split'] in ('train','calibration')]
    expected=[row for row in summaries if row['split'] in ('train','calibration')]
    require(all(row['status']=='verified' for row in expected) and len(expected)==40,'All 40 TRAIN/CAL recording families required before model lock')
    clone_audit = split.verify_actual_sources(manifest, [row['pair'] for row in expected], ROOT)
    write(output/'train-cal-split-audit.json', clone_audit)
    expected_groups = {role: sorted(row['group_id'] for row in manifest['groups'] if row['split'] == role)
                       for role in ('train', 'calibration', 'test')}
    method_ids = [row['id'] for row in manifest['design']['methods']]
    models=analysis.prepare_models(relevant, expected_groups=expected_groups, method_ids=method_ids)
    write(output/'train-cal-rows.json',relevant);write(output/'models.json',models)
    lock=dict(schema='ump.urban-primary-model-lock.v1',status='locked_before_test',created_at=source.now(),
              manifest_sha256=protocol['manifest_sha256'],implementation_sha256=source.sha(supplement_path),
              implementation_files_sha256=supplement['files_sha256'],group_counts={'train':24,'calibration':16},test_rows_seen=0,
              models=artifact(output,output/'models.json'),data=artifact(output,output/'train-cal-rows.json'))
    write(output/'models-lock.json',lock)
    sources.authenticate_test_gate(supplement_path,output/'models-lock.json',protocol['manifest_sha256'])
    return lock


def report(output):
    output,protocol,manifest=authenticate_protocol(output)
    sources.authenticate_test_gate(output/'implementation-supplement.json',output/'models-lock.json',protocol['manifest_sha256'])
    rows,summaries=collect(output,manifest,verify_archives=True)
    pairs=[s['pair'] for s in summaries if 'pair' in s]
    clone_audit=split.verify_actual_sources(manifest,pairs,ROOT,require_complete=len(pairs)==72)
    assessed=analysis.evaluate_models(source.load(output/'models.json'),rows)
    result=dict(schema='ump.urban-primary-report.v1',manifest_sha256=protocol['manifest_sha256'],
                implementation_sha256=source.sha(output/'implementation-supplement.json'),group_outcomes=summaries,
                source_split_audit=clone_audit,analysis=assessed)
    write(output/'final-report.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare',type=Path);action.add_argument('--run',type=Path)
    action.add_argument('--freeze-implementation',type=Path);action.add_argument('--lock-models',type=Path);action.add_argument('--report',type=Path)
    parser.add_argument('--freeze',type=Path);parser.add_argument('--sources',type=Path)
    parser.add_argument('--split',action='append',choices=('train','calibration','test'));parser.add_argument('--limit',type=int)
    parser.add_argument('--implementation',type=Path);parser.add_argument('--model-lock',type=Path)
    parser.add_argument('--unit-receipt',type=Path);parser.add_argument('--dev-receipt',type=Path)
    args=parser.parse_args(argv)
    if args.prepare:
        require(args.freeze is not None and args.sources is not None,'Prepare requires --freeze and --sources');print(prepare(args.freeze,args.sources,args.prepare));return
    out=args.run or args.freeze_implementation or args.lock_models or args.report
    out=fixture.safe_path(out,root=ROOT/'results')
    descriptor=os.open(out/'.execution.lock',os.O_WRONLY|os.O_CREAT|os.O_NOFOLLOW,0o600)
    try:
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:raise ValueError('Another execution runner owns this study') from error
        if args.run:
            require(args.split,'Declare --split explicitly');run(out,args.split,limit=args.limit,implementation=args.implementation,model_lock=args.model_lock)
        elif args.freeze_implementation:
            require(args.unit_receipt and args.dev_receipt,'Require unit and DEV receipts');freeze_implementation(out,args.unit_receipt,args.dev_receipt)
        elif args.lock_models:lock_models(out)
        else:report(out)
    finally:os.close(descriptor)


if __name__=='__main__':
    main()
