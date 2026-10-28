#!/usr/bin/env python3
"""Additive audit correction for canonical source-role metadata ordering.

The frozen fitter stores sorted source IDs per split; the original independent
model audit incorrectly expected manifest execution order. This adapter validates
exact role membership, counts and uniqueness, passes a sorted metadata COPY to
all unchanged frozen numerical checks, and records the distinction explicitly.
No fit, source replacement, protocol mutation or pre-lock TEST feature read occurs.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

import audit_urban_selective_suppression as frozen

SCHEMA = frozen.SCHEMA
ADDENDUM_SCHEMA = 'ump.urban-selective-suppression-source-order-addendum.v1'
EXPECTED_COUNTS = dict(train=24, calibration=16, test=32)
SPLITS = frozen.SPLITS


def canonical_groups(groups, *, expected_counts=None):
    """Validate roles first, then return copied metadata in canonical role order."""
    expected = EXPECTED_COUNTS if expected_counts is None else expected_counts
    frozen.require(isinstance(expected, dict) and set(expected) == set(SPLITS)
                   and all(type(n) is int and n > 0 for n in expected.values()),
                   'Invalid declared role counts')
    frozen.require(isinstance(groups, list), 'Source metadata must be a list')
    seen, counts = set(), Counter()
    for group in groups:
        frozen.require(isinstance(group, dict) and isinstance(group.get('group_id'), str)
                       and group['group_id'] and group.get('split') in SPLITS,
                       'Invalid source-role metadata')
        frozen.require(group['group_id'] not in seen, 'Source IDs must be unique and disjoint across roles')
        seen.add(group['group_id'])
        counts[group['split']] += 1
    frozen.require(dict(counts) == expected and len(groups) == sum(expected.values()),
                   'Source role counts differ')
    return sorted(deepcopy(groups), key=lambda group: (SPLITS.index(group['split']), group['group_id']))


def validate_membership(models, canonical):
    wanted = {role: [group['group_id'] for group in canonical if group['split'] == role] for role in SPLITS}
    actual = models.get('expected_groups')
    frozen.require(isinstance(actual, dict) and set(actual) == set(SPLITS), 'Model role keys differ')
    for role in SPLITS:
        values = actual[role]
        frozen.require(isinstance(values, list) and all(isinstance(value, str) for value in values)
                       and len(values) == len(set(values)) and set(values) == set(wanted[role]),
                       'Model source-role membership differs: ' + role)
    frozen.require(len({value for values in actual.values() for value in values}) == len(canonical),
                   'Model source roles overlap')
    return wanted


def check_model_bundle_addendum(models, training, original, groups, methods, base_ids,
                               parameters, *, expected_counts=None):
    canonical = canonical_groups(groups, expected_counts=expected_counts)
    validate_membership(models, canonical)
    # Do not patch the frozen module, models, rows, protocol or role assignments.
    # Its complete digest/scaling/objective/CAL/old-object checks run unchanged.
    return frozen.check_model_bundle(models, training, original, canonical, methods, base_ids, parameters)


def order_metadata(groups, models):
    canonical = canonical_groups(groups)
    wanted = validate_membership(models, canonical)
    manifest = {role: [group['group_id'] for group in groups if group['split'] == role] for role in SPLITS}
    return dict(source_recordings=len(groups), role_counts=EXPECTED_COUNTS,
                role_membership_sha256=frozen.digest(wanted),
                ordering_changed_splits=[role for role in SPLITS if manifest[role] != wanted[role]],
                source_membership_changed=False, source_roles_changed=False)


def audit_models(study):
    # Frozen _model_inputs reads only role metadata, fitted objects and locked
    # TRAIN/CAL rows. Avoid runner.read_protocol/collect and TEST row payloads.
    protocol, lock, training, models, original, methods, base = frozen._model_inputs(study)
    result = check_model_bundle_addendum(models, training, original, protocol['group_order'],
                                         methods, base, protocol['model_parameters'])
    result.update(model_lock_sha256=frozen.sha(study / 'models-lock.json'), models_fitted=0,
        scope='Original frozen TRAIN scaling/prior/objective, CAL choices, model/control and data checks, with canonical source-role metadata ordering only. No TEST feature payload read.')
    return result, order_metadata(protocol['group_order'], models)


def audit_final(study):
    # This phase is an explicit post-lock action; it is never called by models.
    import run_urban_selective_suppression as runner
    study, protocol, context = runner.read_protocol(study, verify_archives=True, verify_raw=True)
    rows, _, _ = runner.collect(study, protocol, context, verify_archives=True)
    _, _, training, models, original, methods, base = frozen._model_inputs(study)
    canonical = canonical_groups(protocol['group_order'])
    check_model_bundle_addendum(models, training, original, protocol['group_order'],
                               methods, base, protocol['model_parameters'])
    report = frozen.load(study / 'final-report.json')
    frozen.require(report['original_primary_result_preserved'] is True, 'Primary preservation claim missing')
    frozen.require(all(report['analysis']['attacks'][name] == context['original_report']['analysis']['attacks'][name] for name in base)
        and report['analysis']['controls'] == context['original_report']['analysis']['controls']
        and report['analysis']['primary_contrast'] == context['original_primary'], 'Historical TEST result/control changed')
    scores = frozen.check_assessment(report['analysis'], models, rows, methods, canonical)
    frozen.equal(report['utility'], frozen.macro_utility(rows, methods, canonical), 'Final utility macro report')
    return dict(recordings=72, test_score_checks=scores,
        model_lock_sha256=frozen.sha(study / 'models-lock.json'), models_fitted=0, thresholds_retuned=0,
        scope='Original independent locked-score and pair-count AUC/fixed-metric checks with canonical source-role metadata ordering. Bootstrap intervals and physical simulation are not independently reexecuted.'), order_metadata(protocol['group_order'], models)


def provenance(study, metadata, preserved):
    return dict(schema=ADDENDUM_SCHEMA,
        correction='Canonicalize source-role metadata list order to the frozen fitter convention; no membership, role, data, fitted object or metric changes.',
        rule='Exact unique/disjoint source membership and 24/16/32 counts are checked before sorting copied metadata by split and group_id.',
        original_frozen_v1_pass_claimed=False,
        frozen_model_bundle_checks_reused_without_modification=True,
        frozen_auditor=dict(path=str(Path(frozen.__file__).resolve()), sha256=frozen.sha(frozen.__file__)),
        addendum_auditor=dict(path=str(Path(__file__).resolve()), sha256=frozen.sha(__file__)),
        source_order_validation=metadata, preserved_artifacts=preserved,
        models_refitted=0, operating_choices_retuned=False, sources_replaced=False,
        independent_bootstrap_interval_reexecution=False, physical_simulation_reexecuted=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True, type=Path)
    parser.add_argument('--phase', required=True, choices=('models', 'final'))
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    frozen.require(not args.output.exists(), 'Refuse to overwrite addendum audit receipt')
    study = args.study.resolve()
    preserved_paths = [study / name for name in ('protocol.json', 'protocol.sha256', 'utility-report.json',
                                                'mia-fit-attempt.json', 'models-lock.json', 'models.json', 'train-cal-rows.json')]
    preserved_paths += [Path(frozen.__file__).resolve(), Path(__file__).resolve()]
    preserved = {str(path): frozen.sha(path) for path in preserved_paths}
    checks, metadata = {'models': audit_models, 'final': audit_final}[args.phase](study)
    frozen.require(all(frozen.sha(path) == value for path, value in preserved.items()),
                   'Frozen input changed during additive audit')
    receipt = dict(schema=SCHEMA, status='verified', phase=args.phase,
        completed_at=datetime.now(timezone.utc).isoformat(), study=str(study),
        protocol=dict(path=str(study / 'protocol.json'), sha256=frozen.sha(study / 'protocol.json')),
        auditor=dict(path=str(Path(__file__).resolve()), sha256=frozen.sha(__file__)), checks=checks,
        audit_addendum=provenance(study, metadata, preserved))
    with args.output.open('xb') as stream:
        stream.write((json.dumps(receipt, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())
    print(json.dumps(dict(status='verified', phase=args.phase, checks=checks,
                         addendum=ADDENDUM_SCHEMA), sort_keys=True))


if __name__ == '__main__':
    main()
