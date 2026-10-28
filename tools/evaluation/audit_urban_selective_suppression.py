#!/usr/bin/env python3
"""Independent arithmetic gates for the selective-contribution study.

No native execution, motion generation, model fitting or threshold retuning is
performed. Model-phase inspection reads locked TRAIN/CAL rows only. Utility
checks public arithmetic against separately audited retained-source accounting;
it does not claim a second physical/source-audit execution or bootstrap refit.
"""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

SCHEMA = 'ump.urban-selective-suppression-independent-audit.v1'
SPLITS = ('train', 'calibration', 'test')
REPRESENTATIONS = {'semantic111': ('features', 111), 'scalar31': ('scalar_features', 31)}
COUNT_FIELDS = ('input_observations', 'retained_observations',
                'selectively_suppressed_observations', 'whole_footprint_suppressed_observations')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode('ascii')).hexdigest()


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def load(path):
    with Path(path).open() as stream:
        return json.load(stream)


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def equal(actual, expected, path='value'):
    if finite(expected):
        require(finite(actual) and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-10),
                path + ' arithmetic differs')
    elif isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), path + ' keys differ')
        for key in expected:
            equal(actual[key], expected[key], path + '.' + str(key))
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), path + ' length differs')
        for index, value in enumerate(expected):
            equal(actual[index], value, path + '.' + str(index))
    else:
        require(actual == expected, path + ' differs')


def authenticated(ref):
    path = Path(ref['path'])
    require(path.is_file() and sha(path) == ref['sha256'], 'Referenced artifact changed: ' + str(path))
    return path


def relative(root, ref):
    root = Path(root).resolve()
    path = root / ref['path']
    require(not Path(ref['path']).is_absolute() and path.resolve().is_relative_to(root),
            'Artifact escapes recording directory')
    require(sha(path) == ref['sha256'], 'Recording artifact hash differs: ' + str(path))
    return path


def archive(root, ref):
    path = relative(root, ref)
    content = bytearray()
    checksum = hashlib.sha256()
    with gzip.open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
            content.extend(chunk)
            require(len(content) <= ref['uncompressed_bytes'], 'Archive exceeds declared original size')
    require(len(content) == ref['uncompressed_bytes']
            and checksum.hexdigest() == ref['uncompressed_sha256'], 'Archive round-trip differs')
    return json.loads(content)


def checked_rows(rows, groups, methods, *, allow_test=True):
    """Authenticate complete roles/worlds and source-independent controls."""
    roles = {g['group_id']: g['split'] for g in groups}
    require(len(roles) == len(groups), 'Duplicate source assignment')
    allowed = set(roles) if allow_test else {identity for identity, role in roles.items() if role != 'test'}
    seen, controls = set(), {}
    for row in rows:
        identity, method, world = row['group_id'], row['method_id'], row['world']
        require(identity in allowed and row['split'] == roles[identity], 'Source role or TEST boundary differs')
        require(method in methods and type(row['label']) is int
                and (world, row['label']) in (('IN', 1), ('OUT', 0)), 'Method/world/label differs')
        key = (identity, method, world)
        require(key not in seen, 'Duplicate source/method/world row')
        seen.add(key)
        for field, length in list(REPRESENTATIONS.values()) + [('auxiliary_features', 8)]:
            require(isinstance(row[field], list) and len(row[field]) == length
                    and all(finite(value) for value in row[field]), 'Predictor shape/value differs')
        source_control = (row['controls'], row['auxiliary_features'])
        pair = (identity, world)
        require(pair not in controls or controls[pair] == source_control, 'Method-dependent source control')
        controls[pair] = source_control
        require(row['controls']['prior_only'] == .5
                and row['controls']['no_output_features'] == [0.] * 111, 'Negative controls changed')
        digest(row)
    expected = {(identity, method, world) for identity in allowed for method in methods for world in ('IN', 'OUT')}
    require(seen == expected, 'Incomplete source/method/world matrix')
    for identity in allowed:
        inside, outside = controls[identity, 'IN'], controls[identity, 'OUT']
        require(inside[1] == outside[1] and inside[0]['no_output_features'] == outside[0]['no_output_features'],
                'IN/OUT auxiliary or no-output controls differ')
    return sorted(rows, key=lambda row: (SPLITS.index(row['split']), row['group_id'], row['method_id'], -row['label']))


def cohort(value, name):
    require(all(type(value.get(key)) is int and value[key] >= 0 for key in COUNT_FIELDS),
            name + ' invalid cohort counts')
    n, retained, selective, whole = (value[key] for key in COUNT_FIELDS)
    require(n == retained + selective + whole, name + ' cohort conservation differs')
    equal(value['retained_fraction'], retained / n if n else None, name + '.retained_fraction')
    equal(value['selectively_suppressed_fraction'], selective / n if n else None, name + '.selective_fraction')


def check_filtered_row(row, public, audit, data, config, *, include_queries=True):
    """Reconstruct full-input arithmetic without the maintained utility producer."""
    require(audit['status'] == 'verified' and audit.get('scalar', {}).get('valid', True) is True,
            'Missing independent retained-source audit')
    value, accounting = row['utility'], audit['source_accounting']
    require(value['source_accounting'] == accounting, 'Audited source cohorts/delay changed')
    original = Counter(r['type'] for batch in data['batches'] for r in batch['observations'])
    total = sum(original.values())
    cells = [(release, cell) for release in public['releases'] for cell in release['cells']]
    retained = sum(cell['observation_contributions'] for _, cell in cells)
    costs = {node['id']: node['loss'] for node in config['semantic_taxonomy']['nodes']}
    loss_terms = []
    for _, cell in cells:
        bins = cell['semantic']['categories']
        require(sum(item['observation_contributions'] for item in bins) == cell['observation_contributions'],
                'Public bin/cell counts differ')
        distortion = math.fsum(item['observation_contributions'] * costs[item['category_id']] for item in bins)
        equal(cell['semantic']['semantic_mean_loss'], distortion / cell['observation_contributions'], 'Public taxonomy loss')
        loss_terms.append(distortion)
    loss = math.fsum(loss_terms)
    cohort(accounting, 'input')
    require(accounting['input_observations'] == total and accounting['retained_observations'] == retained,
            'Public/source accounting differs')
    require(set(accounting['by_source_type']) == set(original), 'Source type cohort set differs')
    for kind, n in original.items():
        item = accounting['by_source_type'][kind]
        cohort(item, 'type.' + kind)
        require(item['input_observations'] == n, 'Original type denominator differs')
    for key in COUNT_FIELDS:
        require(sum(item[key] for item in accounting['by_source_type'].values()) == accounting[key],
                'Type totals differ: ' + key)
    region_map = {region['id']: region for region in config.get('policy_regions', [])}
    require(set(accounting['by_region']) == set(config['policy_tree']['regions']), 'Region cohort set differs')
    for identity, item in accounting['by_region'].items():
        region = region_map[identity]
        n = sum(region['x'] <= source['x'] < region['x'] + region['width']
                and region['y'] <= source['y'] < region['y'] + region['height']
                for batch in data['batches'] for source in batch['observations'])
        cohort(item, 'region.' + identity)
        require(item['input_observations'] == n, 'Original-position region denominator differs')
    expected = dict(input_observations=total, retained_observations=retained,
        retained_fraction=retained / total if total else None,
        full_input_J=(total - retained + loss) / total if total else None,
        full_input_semantic_loss=(total - retained + loss) / total if total else None,
        retained_semantic_loss=loss / retained if retained else None,
        published_cells=len(cells), published_policy_violations=0,
        selectively_suppressed_observations=accounting['selectively_suppressed_observations'],
        whole_footprint_suppressed_observations=accounting['whole_footprint_suppressed_observations'],
        selectively_suppressed_fraction_of_input=accounting['selectively_suppressed_observations'] / total if total else None,
        whole_footprint_suppressed_fraction_of_input=accounting['whole_footprint_suppressed_observations'] / total if total else None,
        logical_seal_delay_ms=accounting['observation_to_release_delay_ms'])
    for key, actual in expected.items():
        equal(value[key], actual, key)
    for key, function in (('mean_retained_cell_side_m', lambda release, cell: cell['width']),
                          ('mean_retained_interval_ms', lambda release, cell: release['end_ms'] - release['start_ms'])):
        expected_mean = (math.fsum(cell['observation_contributions'] * function(release, cell)
                                  for release, cell in cells) / retained if retained else None)
        equal(value[key], expected_mean, key)
    require(value['contribution_selection'] == 'policy_filtered'
            and value['original_gt_exact_queries'] == 'unavailable: filtered_population',
            'Filtered population/exact contract differs')
    equal(value['selective_suppression_root_cap'], config['policy_tree']['root']['semantic_suppression_fraction']['max'], 'Root cap')
    if include_queries:
        exact = value['query_exact']
        require(exact['status'] == 'unavailable' and exact['reason'] == 'filtered_population'
                and exact['original_source_exact_available'] is False and exact['answered_queries'] == 0
                and exact['scored_queries'] == 0 and exact['occupancy_mae'] is None,
                'Original occupancy exact claim in filtered product')
        exact = value['aligned_semantic_queries']['exact']
        require(exact['status'] == 'unavailable' and exact['reason'] == 'filtered_population',
                'Original category exact claim in filtered product')
        for summary in [exact['summary'], *exact['by_category'].values()]:
            require(summary['answered_query_count'] == summary['scored_query_count'] == 0
                    and summary['answered_only_mae'] is None
                    and summary['original_source_exact_available'] is False,
                    'Filtered source category is falsely certified exact')
        estimates = value['aligned_semantic_queries']['estimate']
        require(estimates['status'] == 'proxy_estimate', 'Unlabelled filtered count estimate')
        for summary in [estimates['summary'], *estimates['by_category'].values()]:
            n = summary['scored_query_count']
            equal(summary['answered_only_bias'], summary['signed_error_sum'] / n if n else None, 'Proxy bias')
            equal(summary['answered_only_mae'], summary['absolute_error_sum'] / n if n else None, 'Proxy MAE')
            require(abs(summary['signed_error_sum']) <= summary['absolute_error_sum'] + 1e-9, 'Bias exceeds absolute error')
    else:
        require(not any(key in value for key in ('query_exact', 'query_estimate', 'aligned_semantic_queries')),
                'Auxiliary dependency entered query workload')
    return len(expected) + 2 + len(original) + len(accounting['by_region'])


def numeric_paths(value, prefix=''):
    for key, child in value.items():
        name = prefix + key
        if isinstance(child, dict):
            yield from numeric_paths(child, name + '.')
        elif finite(child):
            yield name, child


def macro_utility(rows, methods, groups):
    output = {}
    expected = sum(group['split'] == 'test' for group in groups)
    for method in methods:
        output[method] = {}
        for world in ('IN', 'OUT'):
            selected = [row for row in rows if row['method_id'] == method and row['split'] == 'test' and row['world'] == world]
            values = defaultdict(list)
            for row in selected:
                for path, value in numeric_paths(row['utility']):
                    values[path].append(value)
            output[method][world] = dict(expected_recordings=expected, observed_recordings=len(selected),
                macro_means={path: dict(mean=math.fsum(items) / len(items), recordings=len(items))
                             for path, items in sorted(values.items())},
                scope='Equal recording weights; each world uses its own sampled input reference. No unobserved value filled with zero.')
    return output


def score(model, vector):
    require(len(vector) == len(model['weights']) == len(model['means']) == len(model['scales']), 'Model dimension differs')
    z = model['intercept'] + math.fsum(weight * ((value - mean) / scale)
        for value, weight, mean, scale in zip(vector, model['weights'], model['means'], model['scales']))
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    exponent = math.exp(z)
    return exponent / (1 + exponent)


def metrics(scores, labels, threshold):
    positives, negatives = sum(labels), len(labels) - sum(labels)
    tp = sum(label == 1 and value >= threshold for value, label in zip(scores, labels))
    fp = sum(label == 0 and value >= threshold for value, label in zip(scores, labels))
    tpr, fpr = tp / positives if positives else None, fp / negatives if negatives else None
    positive_scores = [value for value, label in zip(scores, labels) if label]
    negative_scores = [value for value, label in zip(scores, labels) if not label]
    auc = (math.fsum(1 if a > b else .5 if a == b else 0 for a in positive_scores for b in negative_scores)
           / (positives * negatives) if positives and negatives else None)
    return dict(roc_auc=auc, tpr=tpr, fpr=fpr,
        balanced_accuracy=(tpr + 1 - fpr) / 2 if tpr is not None and fpr is not None else None,
        advantage=tpr - fpr if tpr is not None and fpr is not None else None,
        precision_at_evaluation_prior=tp / (tp + fp) if tp + fp else None,
        evaluation_prior=positives / len(labels) if labels else None,
        positive_cases=positives, negative_cases=negatives, true_positive=tp, false_positive=fp,
        true_negative=negatives - fp, false_negative=positives - tp, threshold=threshold)


def check_fitted(fitted, rows, field, parameters):
    train = [row for row in rows if row['split'] == 'train']
    calibration = [row for row in rows if row['split'] == 'calibration']
    model = fitted['model']
    require(model is not None and model['training_rows'] == len(train)
            and model['l2'] == parameters['l2'] and 1 <= model['iterations'] <= parameters['max_iterations'],
            'Fit budget or TRAIN count differs')
    dimension = len(train[0][field])
    require(model['feature_count'] == dimension and len(model['weights']) == dimension, 'Fitted feature count differs')
    means = [math.fsum(row[field][i] for row in train) / len(train) for i in range(dimension)]
    scales = [math.sqrt(math.fsum((row[field][i] - means[i]) ** 2 for row in train) / len(train))
              for i in range(dimension)]
    scales = [value if value else 1. for value in scales]
    equal(model['means'], means, 'TRAIN means')
    equal(model['scales'], scales, 'TRAIN population scales')
    equal(model['training_prior'], sum(row['label'] for row in train) / len(train), 'TRAIN prior')
    objective = []
    for row in train:
        z = model['intercept'] + math.fsum(w * ((x - mean) / scale)
            for x, w, mean, scale in zip(row[field], model['weights'], means, scales))
        objective.append(max(z, 0) - z * row['label'] + math.log1p(math.exp(-abs(z))))
    objective = math.fsum(objective) / len(train) + model['l2'] / 2 * math.fsum(w * w for w in model['weights'])
    equal(model['training_objective'], objective, 'TRAIN regularized objective')
    if fitted['status'] == 'nonconverged':
        require(model['converged'] is False and fitted['calibration'] is None, 'Nonconverged fit supplies threshold')
        return
    require(fitted['status'] == 'locked' and model['converged'] is True, 'Fit lock status differs')
    scores = [score(model, row[field]) for row in calibration]
    labels = [row['label'] for row in calibration]
    thresholds = set(scores) | {math.nextafter(max(scores), math.inf)}
    options = [metrics(scores, labels, threshold) for threshold in thresholds]
    permitted = [option for option in options if option['fpr'] <= .1]
    best = max(permitted, key=lambda option: (option['tpr'], -option['fpr'], option['threshold']))
    require(fitted['calibration']['threshold'] == best['threshold'], 'CAL threshold differs, including boundary ULPs')
    equal(fitted['calibration']['calibration'], best, 'CAL operating point')
    equal(fitted['calibration']['target_fpr'], .1, 'CAL FPR target')
    equal(fitted['calibration']['negative_case_fpr_resolution'], 1 / sum(not label for label in labels), 'CAL resolution')


def check_model_bundle(models, training, original, groups, methods, base_ids, parameters):
    checked = checked_rows(training, groups, methods, allow_test=False)
    require(training == checked, 'Locked TRAIN/CAL row order differs')
    actual = deepcopy(models)
    claimed = actual.pop('prepared_sha256')
    require(digest(actual) == claimed, 'Model bundle digest differs')
    require(models['test_rows_seen'] == 0 and models['model_parameters'] == parameters
            and models['training_calibration_rows'] == len(training)
            and models['training_calibration_rows_sha256'] == digest(training), 'Fitting data/budget boundary differs')
    require(models['method_ids'] == methods and models['expected_method_ids'] == methods, 'Model method catalog differs')
    require(models['controls'] == original['controls'], 'Historical controls changed')
    require(all(models['attacks'][name] == original['attacks'][name] for name in base_ids), 'Historical model object changed')
    expected_groups = {split: [g['group_id'] for g in groups if g['split'] == split] for split in SPLITS}
    require(models['expected_groups'] == expected_groups, 'Model source assignments differ')
    require(models['training_group_ids'] == sorted(expected_groups['train'])
            and models['calibration_group_ids'] == sorted(expected_groups['calibration']), 'Model source IDs differ')
    flattened = [dict(method_id=method, representation=rep, **models['attacks'][method][rep])
                 for method in methods for rep in REPRESENTATIONS]
    require(models['models'] == flattened, 'Flat model catalog differs')
    for name in methods:
        if name not in base_ids:
            rows = [row for row in training if row['method_id'] == name]
            for rep, (field, _) in REPRESENTATIONS.items():
                check_fitted(models['attacks'][name][rep], rows, field, parameters)
    return dict(training_calibration_rows=len(training), test_rows_read=0,
                new_models=(len(methods) - len(base_ids)) * len(REPRESENTATIONS),
                old_models=len(base_ids) * len(REPRESENTATIONS), controls=len(models['controls']))


def check_assessment(assessed, models, rows, methods, groups):
    checked = checked_rows(rows, groups, methods)
    count = 0
    for method in methods:
        selected = [row for row in checked if row['method_id'] == method and row['split'] == 'test']
        for rep, (field, _) in REPRESENTATIONS.items():
            locked, actual = models['attacks'][method][rep], assessed['attacks'][method][rep]
            require(actual['locked_calibration'] == locked['calibration'], 'TEST changed locked threshold')
            if locked['status'] != 'locked':
                require(actual['status'] == locked['status'] and actual['metrics'] is None, 'Unavailable fit was scored')
                continue
            require(actual['status'] == 'evaluated' and actual['observed_test_rows'] == len(selected)
                    and actual['missing_test_rows'] == [], 'TEST assessment completeness differs')
            values = [score(locked['model'], row[field]) for row in selected]
            wanted = {(row['group_id'], row['label']): value for row, value in zip(selected, values)}
            got = {(item['group_id'], item['label']): item['score'] for item in actual['group_scores']}
            require(len(actual['group_scores']) == len(selected) and set(got) == set(wanted), 'TEST score matrix differs')
            for key in wanted:
                equal(got[key], wanted[key], 'TEST score')
            expected = metrics(values, [row['label'] for row in selected], locked['calibration']['threshold'])
            for key, value in expected.items():
                equal(actual['metrics'][key], value, 'TEST metric.' + key)
            count += len(values)
    return count


def _model_inputs(study):
    # Do not call runner.read_protocol/collect here: those load historical TEST
    # feature rows. Only role metadata, model objects and TRAIN/CAL rows are read.
    protocol_path = study / 'protocol.json'
    protocol = load(protocol_path)
    require(sha(protocol_path) == (study / 'protocol.sha256').read_text().strip(), 'Protocol digest differs')
    require(protocol['schema'] == 'ump.urban-selective-suppression-execution.v1', 'Wrong study protocol')
    require(protocol['workers'] == 6 and protocol['suppression_cap'] == .1
            and protocol['semantic_generalization'] == 'enabled'
            and protocol['group_counts'] == dict(train=24, calibration=16, test=32)
            and Counter(group['split'] for group in protocol['group_order']) == protocol['group_counts'],
            'Frozen study scope/source roles differ')
    root = Path(__file__).resolve().parents[2]
    for name, value in protocol['implementation_files_sha256'].items():
        require(sha(root / name) == value, 'Frozen implementation changed: ' + name)
    for key in ('history', 'contract', 'native_binary', 'original_native_binary', 'original_config'):
        authenticated(protocol[key])
    history = load(authenticated(protocol['history']))
    lock = load(study / 'models-lock.json')
    require(lock['schema'] == 'ump.urban-selective-suppression-model-lock.v1'
            and lock['status'] == 'locked_before_new_TEST_scoring'
            and lock['protocol'] == dict(path=str(protocol_path), sha256=sha(protocol_path))
            and lock['new_fit_count'] == 14 and lock['old_model_refits'] == lock['test_rows_seen_by_fitter'] == 0,
            'Model lock boundary differs')
    for key in ('models', 'data', 'utility_gate', 'fit_attempt', 'old_models', 'old_model_lock'):
        authenticated(lock[key])
    require(lock['old_models'] == history['bound_anchors']['supplement_models']
            and lock['old_model_lock'] == history['bound_anchors']['supplement_model_lock'], 'Old model lineage differs')
    training = load(authenticated(lock['data']))
    attempt = load(authenticated(lock['fit_attempt']))
    require(attempt['new_fit_count'] == 14 and attempt['test_rows_seen_by_fitter'] == 0
            and attempt['training_rows_sha256'] == digest(training)
            and attempt['model_parameters'] == protocol['model_parameters'], 'Fit attempt differs')
    methods = [method['id'] for method in protocol['method_catalog']]
    base = [method['id'] for method in protocol['method_catalog'] if not method['suppression_enabled']]
    return protocol, lock, training, load(authenticated(lock['models'])), load(authenticated(lock['old_models'])), methods, base


def audit_utility(study):
    import run_urban_selective_suppression as runner
    study, protocol, context = runner.read_protocol(study, verify_archives=True, verify_raw=True)
    # Reuse only the frozen metadata/archive authenticator, never its utility
    # arithmetic. This also binds new sidecars and every per-case receipt.
    bound_rows, _, bound_auxiliary = runner.collect(study, protocol, context, verify_archives=True)
    groups, methods = context['manifest']['groups'], [method['id'] for method in runner.METHODS]
    rows, auxiliary, native, regional, checks = [], [], 0, 0, 0
    for group in groups:
        directory = study / 'groups' / group['group_id']
        imported = context['history']['original_groups'][group['group_id']]
        runner.legacy.previous.validate_pair_import(directory, imported)
        summary = load(directory / 'summary.json')
        require(summary['status'] == 'verified' and summary['group_id'] == group['group_id']
                and summary['split'] == group['split'], 'Recording summary differs')
        expected_cases = {(method['id'], world) for method in runner.NATIVE_METHODS + (runner.NEW_METHODS[1],) for world in ('IN', 'OUT')}
        require(len(summary['cases']) == 20 and {(case['method_id'], case['world']) for case in summary['cases']} == expected_cases
                and all(case['status'] == 'verified' for case in summary['cases']), 'Case family incomplete')
        group_rows = load(relative(directory, summary['rows']))
        group_aux = load(relative(directory, summary['auxiliary_rows']))
        archives = load(relative(directory, summary['archives']))
        originals = {(row['world'], row['method_id']): row for row in context['all_historical_rows']
                     if row['group_id'] == group['group_id'] and row['method_id'] in runner.BASE_IDS}
        for row in group_rows:
            if row['method_id'] in runner.BASE_IDS:
                require(row == originals[row['world'], row['method_id']], 'Historical row object changed')
        for world in ('IN', 'OUT'):
            data = load(directory / ('in.json' if world == 'IN' else 'out.json'))
            world_rows = [row for row in group_rows + group_aux if row['world'] == world and row['method_id'] not in runner.BASE_IDS]
            for row in world_rows:
                name = row['method_id']
                public = archive(directory / world, archives[world][name + '-public.json'])
                private = archive(directory / world, archives[world][name + '-audit.json'])
                config = load(directory / world / (name + '-policy.json'))
                method = next(method for method in runner.NEW_METHODS + runner.AUXILIARY_METHODS if method['id'] == name)
                require(config == runner.variant_config(runner.load_ref(protocol['original_config']), method), 'Variant policy differs')
                is_auxiliary = method in runner.AUXILIARY_METHODS
                checks += check_filtered_row(row, public, private, data, config, include_queries=not is_auxiliary)
                if method['kind'] == 'regional_static': regional += 1
                else: native += 1
        rows.extend(group_rows)
        auxiliary.extend(group_aux)
    rows = checked_rows(rows, groups, methods)
    require(rows == checked_rows(bound_rows, groups, methods) and auxiliary == bound_auxiliary,
            'Authenticated row family differs')
    checked_rows(auxiliary, groups, [method['id'] for method in runner.AUXILIARY_METHODS])
    require(len(rows) == 2016 and len(auxiliary) == 432 and native == 1296 and regional == 144, 'Complete study counts differ')
    report = load(study / 'utility-report.json')
    equal(report['utility'], macro_utility(rows, methods, groups), 'Utility macro report')
    require(report['all_rows_sha256'] == digest(rows) and report['auxiliary_rows_sha256'] == digest(auxiliary)
            and report['mia_status'] == 'not_started', 'Utility gate row/MIA binding differs')
    return dict(recordings=len(groups), headline_rows=len(rows), auxiliary_rows=len(auxiliary),
                native_cases=native, regional_compositions=regional, arithmetic_checks=checks,
                rows_sha256=digest(rows), original_rows_preserved=1008, models_fitted=0,
                physical_source_audit_reexecutions=0)


def audit_models(study):
    protocol, lock, training, models, original, methods, base = _model_inputs(study)
    result = check_model_bundle(models, training, original, protocol['group_order'], methods, base, protocol['model_parameters'])
    result.update(model_lock_sha256=sha(study / 'models-lock.json'), models_fitted=0,
                  scope='TRAIN scaling/prior/objective, CAL threshold rule, old objects and controls; no TEST feature payload read.')
    return result


def audit_final(study):
    import run_urban_selective_suppression as runner
    study, protocol, context = runner.read_protocol(study, verify_archives=True, verify_raw=True)
    rows, _, _ = runner.collect(study, protocol, context, verify_archives=True)
    _, _, training, models, original, methods, base = _model_inputs(study)
    check_model_bundle(models, training, original, protocol['group_order'], methods, base, protocol['model_parameters'])
    report = load(study / 'final-report.json')
    require(report['original_primary_result_preserved'] is True, 'Primary preservation claim missing')
    require(all(report['analysis']['attacks'][name] == context['original_report']['analysis']['attacks'][name] for name in base)
            and report['analysis']['controls'] == context['original_report']['analysis']['controls']
            and report['analysis']['primary_contrast'] == context['original_primary'], 'Historical TEST result/control changed')
    scores = check_assessment(report['analysis'], models, rows, methods, protocol['group_order'])
    equal(report['utility'], macro_utility(rows, methods, protocol['group_order']), 'Final utility macro report')
    return dict(recordings=72, test_score_checks=scores, model_lock_sha256=sha(study / 'models-lock.json'),
                models_fitted=0, thresholds_retuned=0,
                scope='Independent locked logistic scores and pair-count ROC/fixed-threshold metrics. Bootstrap intervals and physical source auditing are not reexecuted.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', type=Path, required=True)
    parser.add_argument('--phase', choices=('utility', 'models', 'final'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    require(not args.output.exists(), 'Refuse to overwrite audit receipt')
    study = args.study.resolve()
    result = {'utility': audit_utility, 'models': audit_models, 'final': audit_final}[args.phase](study)
    receipt = dict(schema=SCHEMA, status='verified', phase=args.phase,
        completed_at=datetime.now(timezone.utc).isoformat(), study=str(study),
        protocol=dict(path=str(study / 'protocol.json'), sha256=sha(study / 'protocol.json')),
        auditor=dict(path=str(Path(__file__).resolve()), sha256=sha(__file__)), checks=result)
    with args.output.open('xb') as stream:
        stream.write((json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())
    print(json.dumps(dict(status='verified', phase=args.phase, checks=result), sort_keys=True))


if __name__ == '__main__':
    main()
