#!/usr/bin/env python3
"""Frozen TRAIN fitting, CAL thresholds and source-paired urban TEST assessment.

Inputs are already independently audited public feature rows. This layer never
accepts raw source IDs as predictors, changes model budgets, selects comparators,
flips score direction or substitutes incomplete/nonconverged models. Private row
receipts and source-group scores belong under ignored results/, not public Git.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import empirical_privacy as empirical
from urban_privacy_statistics import attack_metrics_with_intervals, paired_source_auc_difference

ROOT = Path(__file__).resolve().parents[2]
PRIMARY_FREEZE = ROOT / 'results/urban-privacy-primary-protocol-2026-10-25-v1/manifest.json'
SPLITS = ('train', 'calibration', 'test')
REPRESENTATIONS = {'semantic111': ('features', 111), 'scalar31': ('scalar_features', 31)}
AUXILIARY_FEATURE_NAMES = (
    'approved_sightings', 'minimum_time_fraction', 'maximum_time_fraction',
    'mean_time_fraction', 'mean_x_fraction', 'mean_y_fraction',
    'x_range_fraction', 'y_range_fraction')
MODEL_PARAMETERS = {'l2': .1, 'max_iterations': 500, 'tolerance': 1e-8}
CONTROL_NAMES = ('prior_only', 'auxiliary_only', 'no_output', 'unprotected')
MODEL_SCHEMA = 'ump.urban-privacy-analysis-models.v1'
REPORT_SCHEMA = 'ump.urban-privacy-analysis.v1'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False, ensure_ascii=True).encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def auxiliary_features(knowledge, coverage, end_ms):
    """Eight summaries of approved sightings only, never type, ID or source label."""
    require(isinstance(knowledge, list) and knowledge, 'Expected nonempty approved sightings')
    require(type(end_ms) is int and end_ms > 0, 'Invalid auxiliary horizon')
    require(isinstance(coverage, dict) and all(_finite(coverage.get(k)) for k in
            ('x', 'y', 'width', 'height')) and coverage['width'] > 0 and coverage['height'] > 0,
            'Invalid auxiliary coverage')
    times, xs, ys = [], [], []
    seen = set()
    for point in knowledge:
        require(isinstance(point, dict) and set(point) == {'observed_at_ms', 'x', 'y', 'cell_id'},
                'Auxiliary fields must contain only approved time/position/cell')
        t, x, y = point['observed_at_ms'], point['x'], point['y']
        require(type(t) is int and 0 < t < end_ms and _finite(x) and _finite(y), 'Invalid approved sighting')
        require(coverage['x'] <= x < coverage['x'] + coverage['width'] and
                coverage['y'] <= y < coverage['y'] + coverage['height'], 'Auxiliary position outside coverage')
        require(type(point['cell_id']) is int and point['cell_id'] > 0, 'Invalid auxiliary cell')
        require(t not in seen, 'Repeated auxiliary measurement time')
        seen.add(t); times.append(t); xs.append(x); ys.append(y)
    n = len(times)
    return [n, min(times) / end_ms, max(times) / end_ms, math.fsum(times) / n / end_ms,
            (math.fsum(xs) / n - coverage['x']) / coverage['width'],
            (math.fsum(ys) / n - coverage['y']) / coverage['height'],
            (max(xs) - min(xs)) / coverage['width'], (max(ys) - min(ys)) / coverage['height']]


def _defaults(expected_groups, method_ids):
    if expected_groups is None or method_ids is None:
        manifest = json.loads(PRIMARY_FREEZE.read_text())
        if expected_groups is None:
            expected_groups = {s: [r['group_id'] for r in manifest['groups'] if r['split'] == s] for s in SPLITS}
        if method_ids is None:
            method_ids = [r['id'] for r in manifest['design']['methods']]
    require(isinstance(expected_groups, dict) and set(expected_groups) == set(SPLITS), 'Declare every expected split')
    expected_groups = {s: sorted(expected_groups[s]) for s in SPLITS}
    all_groups = [g for s in SPLITS for g in expected_groups[s]]
    require(all(isinstance(g, str) and g for g in all_groups) and len(all_groups) == len(set(all_groups))
            and all(expected_groups[s] for s in SPLITS), 'Expected groups must be unique across nonempty splits')
    require(isinstance(method_ids, (list, tuple)) and method_ids and
            all(isinstance(m, str) and m for m in method_ids) and len(method_ids) == len(set(method_ids)),
            'Declare unique methods')
    return expected_groups, list(method_ids)


def _vector(values, count, name):
    require(isinstance(values, list) and len(values) == count and all(_finite(v) for v in values),
            'Invalid ' + name + ' vector')


def _checked_rows(rows, expected_groups, method_ids, *, allow_test):
    require(isinstance(rows, list), 'Rows must be a list')
    group_split = {g: s for s in SPLITS for g in expected_groups[s]}
    seen = set()
    result = []
    for row in rows:
        require(isinstance(row, dict), 'Invalid feature row')
        group, split, method = row.get('group_id'), row.get('split'), row.get('method_id')
        require(group in group_split and group_split[group] == split, 'Recording group differs from frozen split')
        require(allow_test or split != 'test', 'TEST rows are forbidden during model preparation')
        require(method in method_ids, 'Unregistered comparator')
        world, label = row.get('world'), row.get('label')
        require(type(label) is int and ((world == 'IN' and label == 1) or (world == 'OUT' and label == 0)),
                'Membership world/label mismatch')
        key = (group, method, world)
        require(key not in seen, 'Duplicate group/method/world row'); seen.add(key)
        for field, count in REPRESENTATIONS.values():
            _vector(row.get(field), count, field)
        _vector(row.get('auxiliary_features'), 8, 'auxiliary')
        control = row.get('controls')
        require(isinstance(control, dict), 'Missing attack controls')
        require(_finite(control.get('prior_only')) and control['prior_only'] == .5, 'Prior control must equal balanced prior')
        require(_finite(control.get('unprotected')) and 0 <= control['unprotected'] <= 1, 'Invalid unprotected score')
        _vector(control.get('no_output_features'), 111, 'no-output')
        require(all(v == 0 for v in control['no_output_features']), 'No-output feature vector must contain no release signal')
        require(isinstance(row.get('utility', {}), dict), 'Invalid utility record')
        # Reject serialized nonfinite values outside the predictor vectors as well.
        canonical(row)
        result.append(deepcopy(row))
    return sorted(result, key=lambda r: (SPLITS.index(r['split']), r['group_id'], r['method_id'], -r['label']))


def _control_rows(rows):
    """Collapse method duplicates; private method count cannot inflate control N."""
    by_world = {}
    for row in rows:
        key = (row['group_id'], row['world'])
        value = {k: deepcopy(row[k]) for k in ('group_id', 'split', 'world', 'label', 'auxiliary_features', 'controls')}
        require(key not in by_world or by_world[key] == value, 'Method-dependent source control or auxiliary vector')
        by_world[key] = value
    by_group = defaultdict(dict)
    for row in by_world.values():
        by_group[row['group_id']][row['world']] = row
    for pair in by_group.values():
        if set(pair) == {'IN', 'OUT'}:
            require(pair['IN']['auxiliary_features'] == pair['OUT']['auxiliary_features'],
                    'Auxiliary knowledge differs between worlds')
            require(pair['IN']['controls']['no_output_features'] == pair['OUT']['controls']['no_output_features'],
                    'No-output control differs between worlds')
    return sorted(by_world.values(), key=lambda r: (SPLITS.index(r['split']), r['group_id'], -r['label']))


def _missing(rows, expected_groups, splits):
    actual = {(r['group_id'], r['world']) for r in rows}
    return [{'group_id': g, 'split': s, 'world': w} for s in splits for g in expected_groups[s]
            for w in ('IN', 'OUT') if (g, w) not in actual]


def _fit(rows, vector, expected_groups):
    missing = _missing(rows, expected_groups, ('train', 'calibration'))
    if missing:
        return {'status': 'incomplete', 'missing': missing, 'model': None, 'calibration': None}
    train = [r for r in rows if r['split'] == 'train']
    calibration = [r for r in rows if r['split'] == 'calibration']
    model = empirical.fit_classifier([vector(r) for r in train], [r['label'] for r in train], **MODEL_PARAMETERS)
    if not model['converged']:
        return {'status': 'nonconverged', 'missing': [], 'model': model, 'calibration': None,
                'scope': 'Frozen fitting budget exhausted; model-dependent metrics remain NA; no retuning.'}
    scores = empirical.predict_scores(model, [vector(r) for r in calibration])
    fitted = empirical.calibrate_threshold(scores, [r['label'] for r in calibration], target_fpr=.1)
    return {'status': 'locked', 'missing': [], 'model': model, 'calibration': fitted}


def _direct(rows, key, expected_groups):
    missing = _missing(rows, expected_groups, ('train', 'calibration'))
    if missing:
        return {'status': 'incomplete', 'missing': missing, 'model': None, 'calibration': None}
    calibration = [r for r in rows if r['split'] == 'calibration']
    fitted = empirical.calibrate_threshold([r['controls'][key] for r in calibration],
                                         [r['label'] for r in calibration], target_fpr=.1)
    return {'status': 'locked', 'model': None, 'calibration': fitted, 'score_rule': key, 'missing': []}


def prepare_models(rows, *, expected_groups=None, method_ids=None):
    """Fit TRAIN only and lock CAL thresholds; reject even one primary TEST row.

    ``expected_groups`` maps train/calibration/test to recording IDs. Supplying
    smaller groups is intended for synthetic unit/DEV validation, not changing
    the primary study. Defaults authenticate the frozen 24/16/32 group matrix.
    """
    expected_groups, method_ids = _defaults(expected_groups, method_ids)
    checked = _checked_rows(rows, expected_groups, method_ids, allow_test=False)
    controls = _control_rows(checked)
    attacks = {}
    for method in method_ids:
        selected = [r for r in checked if r['method_id'] == method]
        attacks[method] = {name: _fit(selected, lambda row, f=field: row[f], expected_groups)
                           for name, (field, _) in REPRESENTATIONS.items()}
    control_models = {'auxiliary_only': _fit(controls, lambda r: r['auxiliary_features'], expected_groups),
                      'no_output': _fit(controls, lambda r: r['controls']['no_output_features'], expected_groups)}
    control_models.update({name: _direct(controls, name, expected_groups) for name in ('prior_only', 'unprotected')})
    result = {'schema': MODEL_SCHEMA, 'expected_groups': expected_groups, 'method_ids': method_ids,
              'model_parameters': deepcopy(MODEL_PARAMETERS), 'calibration_fpr_cap': .1,
              'training_calibration_rows_sha256': digest(checked), 'training_calibration_rows': len(checked),
              'test_rows_seen': 0, 'attacks': attacks, 'controls': control_models,
              'training_group_ids': sorted({r['group_id'] for r in checked if r['split'] == 'train'}),
              'calibration_group_ids': sorted({r['group_id'] for r in checked if r['split'] == 'calibration'}),
              'expected_method_ids': list(method_ids),
              'models': [dict(method_id=method, representation=representation, **deepcopy(attacks[method][representation]))
                         for method in method_ids for representation in REPRESENTATIONS],
              'auxiliary_feature_names': list(AUXILIARY_FEATURE_NAMES),
              'scope': 'TRAIN-only scaling/fits, CAL-only thresholds; no TEST-dependent direction, tuning or comparator selection.'}
    result['prepared_sha256'] = digest(result)
    return result


def validate_model_lock(prepared, rows, *, require_complete=True):
    """Authenticate actual paired TRAIN/CAL evidence without fitting any model.

    This is the pre-TEST gate: a list length alone cannot authenticate 22 unique
    comparator/representation models or 880 unique, correctly assigned rows.
    Nonconverged frozen fits are legitimate locked negative outcomes; missing
    source/method/world cases do not open the TEST generation gate.
    """
    require(isinstance(prepared, dict) and prepared.get('schema') == MODEL_SCHEMA, 'Invalid locked model bundle')
    original = deepcopy(prepared)
    claimed = original.pop('prepared_sha256', None)
    require(claimed == digest(original), 'Locked model/calibration bundle changed')
    require(original['model_parameters'] == MODEL_PARAMETERS and original['test_rows_seen'] == 0,
            'Frozen fitting protocol differs')
    expected, methods = _defaults(original['expected_groups'], original['method_ids'])
    checked = _checked_rows(rows, expected, methods, allow_test=False)
    _control_rows(checked)
    require(digest(checked) == original['training_calibration_rows_sha256'],
            'TRAIN/CAL rows differ from the locked fitting evidence')
    require(original['training_calibration_rows'] == len(checked), 'Locked fitting row count differs')
    require(original.get('expected_method_ids') == methods, 'Locked method family differs')
    require(original.get('training_group_ids') == sorted({r['group_id'] for r in checked if r['split'] == 'train'})
            and original.get('calibration_group_ids') == sorted({r['group_id'] for r in checked if r['split'] == 'calibration'}),
            'Locked actual source-group metadata differs')
    require(set(original['attacks']) == set(methods) and
            all(set(original['attacks'][m]) == set(REPRESENTATIONS) for m in methods), 'Locked attack family differs')
    flattened = [dict(method_id=m, representation=representation, **deepcopy(original['attacks'][m][representation]))
                 for m in methods for representation in REPRESENTATIONS]
    require(original.get('models') == flattened, 'Locked model list differs from actual attack family')
    require(set(original['controls']) == set(CONTROL_NAMES), 'Locked control family differs')
    if require_complete:
        for method in methods:
            require(not _missing([r for r in checked if r['method_id'] == method], expected, ('train', 'calibration')),
                    'TRAIN/CAL method/world pairs are incomplete')
        for fitted in [*original['models'], *original['controls'].values()]:
            require(fitted['status'] in ('locked', 'nonconverged'), 'Incomplete fits cannot open TEST gate')
            if fitted['model'] is not None:
                empirical._validate_model(fitted['model'])
                require(fitted['model']['l2'] == MODEL_PARAMETERS['l2'] and
                        fitted['model']['iterations'] <= MODEL_PARAMETERS['max_iterations'], 'Locked fitting budget differs')
            if fitted['status'] == 'nonconverged':
                require(fitted['model'] is not None and not fitted['model']['converged']
                        and fitted['calibration'] is None, 'Nonconverged fit cannot supply a threshold')
            else:
                require(fitted['model'] is None or fitted['model']['converged'], 'Unconverged model marked locked')
                require(isinstance(fitted['calibration'], dict) and fitted['calibration']['target_fpr'] == .1,
                        'Locked calibration protocol differs')
    return {'schema': 'ump.urban-privacy-model-lock-validation.v1', 'status': 'verified',
            'prepared_sha256': claimed, 'training_groups': len(original['training_group_ids']),
            'calibration_groups': len(original['calibration_group_ids']), 'models': len(original['models']),
            'test_rows_seen': 0, 'require_complete': require_complete}


def _scores(model, rows, vector):
    if model['model'] is None:
        return [r['controls'][model['score_rule']] for r in rows]
    return empirical.predict_scores(model['model'], [vector(r) for r in rows])


def _evaluate_one(model, rows, vector, expected_groups):
    selected = [r for r in rows if r['split'] == 'test']
    missing = _missing(selected, expected_groups, ('test',))
    status = model['status'] if model['status'] != 'locked' else 'incomplete' if missing else 'evaluated'
    report = {'status': status, 'expected_independent_test_groups': len(expected_groups['test']),
              'complete_test_groups': sum(all(any(r['group_id'] == g and r['world'] == w for r in selected)
                                          for w in ('IN', 'OUT')) for g in expected_groups['test']),
              'observed_test_rows': len(selected), 'missing_test_rows': missing,
              'metrics': None, 'group_scores': [], 'locked_calibration': model['calibration'],
              'fit_diagnostics': None if model['model'] is None else {k: model['model'][k] for k in
                   ('converged', 'iterations', 'training_rows', 'training_objective', 'feature_count')}}
    if status != 'evaluated':
        return report
    values = _scores(model, selected, vector)
    metrics = attack_metrics_with_intervals(values, [r['label'] for r in selected], model['calibration']['threshold'])
    report.update(metrics=metrics, group_scores=[{'group_id': r['group_id'], 'label': r['label'], 'score': s}
                                               for r, s in zip(selected, values)])
    return report


def _numeric_paths(value, prefix=''):
    for key, child in sorted(value.items()):
        name = prefix + key
        if isinstance(child, dict):
            yield from _numeric_paths(child, name + '.')
        elif _finite(child):
            yield name, child


def _utility(rows, expected_groups):
    """Descriptive equal-recording macro means, split by each world's own truth."""
    result = {}
    for world in ('IN', 'OUT'):
        selected = [r for r in rows if r['split'] == 'test' and r['world'] == world]
        values = defaultdict(list)
        for row in selected:
            for key, value in _numeric_paths(row.get('utility', {})):
                values[key].append(value)
        result[world] = {'expected_recordings': len(expected_groups['test']), 'observed_recordings': len(selected),
                         'macro_means': {key: {'mean': math.fsum(v) / len(v), 'recordings': len(v)}
                                         for key, v in sorted(values.items())},
                         'scope': 'Equal recording weights; each world uses its own sampled input reference. No unobserved value filled with zero.'}
    return result


def evaluate_models(prepared, rows):
    """Evaluate frozen models on untouched TEST, without refitting or recalibration."""
    require(isinstance(prepared, dict) and prepared.get('schema') == MODEL_SCHEMA, 'Invalid locked model bundle')
    original = deepcopy(prepared)
    claimed = original.pop('prepared_sha256', None)
    require(claimed == digest(original), 'Locked model/calibration bundle changed')
    require(original['model_parameters'] == MODEL_PARAMETERS and original['test_rows_seen'] == 0,
            'Frozen fitting protocol differs')
    expected, methods = _defaults(original['expected_groups'], original['method_ids'])
    checked = _checked_rows(rows, expected, methods, allow_test=True)
    training = [r for r in checked if r['split'] != 'test']
    require(digest(training) == original['training_calibration_rows_sha256'],
            'TRAIN/CAL rows differ from the locked fitting evidence')
    validate_model_lock(prepared, training, require_complete=False)
    controls = _control_rows(checked)
    attacks = {}
    for method in methods:
        selected = [r for r in checked if r['method_id'] == method]
        attacks[method] = {name: _evaluate_one(original['attacks'][method][name], selected,
                            lambda row, f=field: row[f], expected)
                           for name, (field, _) in REPRESENTATIONS.items()}
    evaluated_controls = {}
    for name in CONTROL_NAMES:
        vector = (lambda r: r['auxiliary_features']) if name == 'auxiliary_only' else (lambda r: r['controls']['no_output_features'])
        evaluated_controls[name] = _evaluate_one(original['controls'][name], controls, vector, expected)
    negative_checks = {}
    for name in ('prior_only', 'auxiliary_only', 'no_output'):
        row = evaluated_controls[name]
        if row['status'] != 'evaluated':
            negative_checks[name] = {'status': 'unavailable', 'reason': row['status']}
            continue
        pairs = defaultdict(dict)
        for value in row['group_scores']:
            pairs[value['group_id']][value['label']] = value['score']
        passed = all(p[0] == p[1] for p in pairs.values()) and row['metrics']['roc_auc'] == .5
        negative_checks[name] = {'status': 'pass' if passed else 'fail', 'identical_pair_scores': passed}
    positive = evaluated_controls['unprotected']
    positive_check = {'status': 'unavailable', 'reason': positive['status']}
    if positive['status'] == 'evaluated':
        pairs = defaultdict(dict)
        for value in positive['group_scores']:
            pairs[value['group_id']][value['label']] = value['score']
        monotone = all(p[1] >= p[0] for p in pairs.values())
        all_in = all(p[1] == 1 for p in pairs.values())
        discriminates = positive['metrics']['roc_auc'] > .5
        positive_check = {'status': 'pass' if monotone and all_in and discriminates else 'diagnostic_required',
                          'in_contains_all_approved_sightings': all_in, 'OUT_removal_monotone': monotone,
                          'auc_above_chance': discriminates,
                          'scope': 'Exact approved coordinate matches; coincident background can match OUT. Perfect AUC is not forced.'}
    primary = {'status': 'unavailable', 'metric': 'ROC_AUC', 'left': 'adaptive_semantic_first',
               'right': 'regional_static20', 'representations': {}}
    if primary['left'] in attacks and primary['right'] in attacks:
        for name in REPRESENTATIONS:
            left, right = attacks[primary['left']][name], attacks[primary['right']][name]
            if left['status'] == right['status'] == 'evaluated':
                primary['representations'][name] = paired_source_auc_difference(
                    left['group_scores'], right['group_scores'], replicates=1000, seed=20261025301)
            else:
                primary['representations'][name] = {'status': 'unavailable', 'left_status': left['status'], 'right_status': right['status']}
        primary['status'] = 'evaluated' if 'auc_difference' in primary['representations']['semantic111'] else 'unavailable'
    complete = all(v['status'] == 'evaluated' for r in attacks.values() for v in r.values())
    control_pass = all(v['status'] == 'pass' for v in negative_checks.values()) and positive_check['status'] == 'pass'
    return {'schema': REPORT_SCHEMA, 'status': 'complete' if complete and control_pass else 'incomplete_or_diagnostic',
            'prepared_sha256': claimed, 'all_rows_sha256': digest(checked), 'attacks': attacks,
            'controls': evaluated_controls, 'negative_control_checks': negative_checks,
            'positive_control_check': positive_check, 'primary_contrast': primary,
            'utility': {method: _utility([r for r in checked if r['method_id'] == method], expected) for method in methods},
            'interpretation_gate': 'controls_pass' if control_pass else 'diagnose_controls_before_interpreting_lower_attack_success',
            'scope': 'Bounded declared episode-contribution attack, final snapshot. Policy compliance is distinct from empirical privacy; no person-level, universal or online-delivery guarantee.',
            'uncertainty': '95% exact Clopper-Pearson rate intervals; paired TEST recording bootstrap1000 for AUC contrast conditional on fixed TRAIN models/CAL thresholds.'}
