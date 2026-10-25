"""Independent binomial inversions and matched-source resampling regressions."""

from copy import deepcopy
from decimal import Decimal, localcontext
import math
import random
import unittest

from empirical_privacy import attack_metrics
from urban_privacy_statistics import (
    attack_metrics_with_intervals, clopper_pearson, paired_source_auc_difference,
)


def decimal_interval(successes, trials):
    """Independent 60-digit inversion of exact-combination binomial polynomials."""
    with localcontext() as context:
        context.prec = 60
        alpha = Decimal("0.025")

        def root(first, last, increasing):
            low, high = Decimal(0), Decimal(1)
            for _ in range(200):
                p = (low + high) / 2
                value = sum(Decimal(math.comb(trials, k)) * p ** k * (1-p) ** (trials-k)
                            for k in range(first, last+1))
                if (value < alpha) == increasing:
                    low = p
                else:
                    high = p
            return float((low+high)/2)

        return (0.0 if successes == 0 else root(successes, trials, True),
                1.0 if successes == trials else root(0, successes, False))


def rows(pairs):
    return [{"group_id": str(group), "label": label, "score": score}
            for group, (out_score, in_score) in enumerate(pairs)
            for label, score in ((0, out_score), (1, in_score))]


class ClopperPearsonTests(unittest.TestCase):
    def test_every_frozen_16_and_32_trial_count_matches_decimal_polynomials(self):
        for trials in (16, 32):
            for successes in range(trials+1):
                with self.subTest(trials=trials, successes=successes):
                    expected = decimal_interval(successes, trials)
                    actual = clopper_pearson(successes, trials)
                    self.assertAlmostEqual(actual["lower"], expected[0], delta=4e-14)
                    self.assertAlmostEqual(actual["upper"], expected[1], delta=4e-14)
                    self.assertLessEqual(actual["lower"], successes/trials)
                    self.assertGreaterEqual(actual["upper"], successes/trials)

    def test_zero_and_all_success_endpoints_are_not_degenerate(self):
        zero, full = clopper_pearson(0, 32), clopper_pearson(32, 32)
        self.assertEqual(zero["lower"], 0)
        self.assertEqual(full["upper"], 1)
        self.assertAlmostEqual(zero["upper"], 1-0.025**(1/32), places=15)
        self.assertAlmostEqual(zero["upper"], 0.10888116067935288, places=14)
        self.assertAlmostEqual(full["lower"], 1-zero["upper"], places=15)
        self.assertGreater(zero["upper"], .1)

    def test_zero_trials_are_unknown(self):
        result = clopper_pearson(0, 0)
        self.assertIsNone(result["estimate"])
        self.assertEqual((result["lower"], result["upper"]), (0, 1))

    def test_single_trial_and_confidence_are_exact(self):
        for confidence in (.8, .9, .95, .99):
            tail = (1-confidence)/2
            self.assertAlmostEqual(clopper_pearson(0, 1, confidence)["upper"], 1-tail)
            self.assertAlmostEqual(clopper_pearson(1, 1, confidence)["lower"], tail)

    def test_interval_symmetry_monotonicity_and_coverage(self):
        for n in (16, 32):
            intervals = [clopper_pearson(k, n) for k in range(n+1)]
            for k, interval in enumerate(intervals):
                self.assertAlmostEqual(interval["lower"], 1-intervals[n-k]["upper"], places=13)
                if k:
                    self.assertLess(intervals[k-1]["lower"], interval["lower"])
                    self.assertLess(intervals[k-1]["upper"], interval["upper"])
            for p in (.001, .01, .025, .05, .1, .2, .4, .5, .7, .9, .99, .999):
                coverage = math.fsum(math.comb(n,k)*p**k*(1-p)**(n-k)
                                    for k, ci in enumerate(intervals)
                                    if ci["lower"] <= p <= ci["upper"])
                self.assertGreaterEqual(coverage + 2e-14, .95)

    def test_larger_finite_counts_and_extreme_confidence(self):
        for k, n in ((0, 10000), (1, 10000), (499, 1000), (9999, 10000)):
            result = clopper_pearson(k, n, .9999)
            self.assertTrue(0 <= result["lower"] <= k/n <= result["upper"] <= 1)
        ci = clopper_pearson(0, 10000)
        self.assertAlmostEqual(ci["upper"], -math.expm1(math.log(.025)/10000), places=16)

    def test_invalid_counts_and_confidences_rejected(self):
        for k, n in ((True,32), (1,True), (-1,32), (33,32), (1,0), (1.0,32), (1,32.0)):
            with self.subTest(k=k,n=n), self.assertRaises(ValueError):
                clopper_pearson(k,n)
        for value in (True, None, "0.95", 0, 1, -1, float("nan"), float("inf")):
            with self.subTest(confidence=value), self.assertRaises(ValueError):
                clopper_pearson(1,32,value)

    def test_fixed_threshold_counts_and_ties_are_preserved(self):
        scores, labels, threshold = [.5, .7, .5, .2], [1,1,0,0], .5
        result = attack_metrics_with_intervals(scores, labels, threshold)
        plain = attack_metrics(scores, labels, threshold)
        self.assertEqual({key: result[key] for key in plain}, plain)
        self.assertEqual(result["tpr_interval"], clopper_pearson(2,2))
        self.assertEqual(result["fpr_interval"], clopper_pearson(1,2))
        result = attack_metrics_with_intervals([.1], [1], .5)
        self.assertIsNone(result["fpr"])
        self.assertIsNone(result["fpr_interval"]["estimate"])


class PairedBootstrapTests(unittest.TestCase):
    def test_constant_controls_ties_and_identical_methods_have_zero_difference(self):
        for pairs in (([.5,.5],)*4, ((.1,.9),(.3,.8),(.4,.6),(.6,.5))):
            sample = rows(pairs)
            result = paired_source_auc_difference(sample, sample, replicates=100)
            self.assertEqual(result["auc_difference"], 0)
            self.assertEqual(result["interval"], [0,0])
            self.assertEqual(result["independent_groups"], 4)

    def test_perfect_opposite_controls_keep_negative_direction(self):
        first = rows(((.9,.1),)*3)
        second = rows(((.1,.9),)*3)
        result = paired_source_auc_difference(first,second,replicates=20)
        self.assertEqual(result["auc_difference"], -1)
        self.assertEqual(result["interval"], [-1,-1])

    def test_independent_brute_force_resampling_matches_fixed_rng_and_percentile(self):
        left = rows(((.1,.9),(.8,.3),(.4,.5),(.5,.5)))
        right = rows(((.2,.8),(.2,.3),(.8,.5),(.4,.5)))
        result = paired_source_auc_difference(left,right,replicates=79,seed=456)
        # Independent AUC is the probability that a positive beats a negative.
        def auc(sequence):
            positive = [row["score"] for row in sequence if row["label"]]
            negative = [row["score"] for row in sequence if not row["label"]]
            return sum((p>n)+.5*(p==n) for p in positive for n in negative)/(len(positive)*len(negative))
        rng = random.Random(456)
        samples = []
        for _ in range(79):
            selected = [rng.choice(["0","1","2","3"]) for _ in range(4)]
            first = [row for group in selected for row in left if row["group_id"]==group]
            second = [row for group in selected for row in right if row["group_id"]==group]
            samples.append(auc(first)-auc(second))
        samples.sort()
        def quantile(q):
            position = 78*q
            a,b = math.floor(position),math.ceil(position)
            return samples[a]+(samples[b]-samples[a])*(position-a)
        self.assertEqual(result["auc_difference"],auc(left)-auc(right))
        self.assertAlmostEqual(result["interval"][0],quantile(.025),places=15)
        self.assertAlmostEqual(result["interval"][1],quantile(.975),places=15)

    def test_row_order_does_not_change_joint_source_draws_and_inputs_are_unchanged(self):
        left, right = rows(((.1,.9),(.8,.3),(.4,.5))),rows(((.2,.8),(.2,.3),(.8,.5)))
        originals = deepcopy((left,right))
        expected = paired_source_auc_difference(left,right,replicates=50,seed=67)
        self.assertEqual(expected,paired_source_auc_difference(left[::-1],right[::-1],replicates=50,seed=67))
        self.assertEqual((left,right),originals)

    def test_single_group_has_no_inferential_interval(self):
        sample = rows(((.1,.9),))
        result = paired_source_auc_difference(sample,sample)
        self.assertIsNone(result["interval"])
        self.assertEqual(result["replicates"],0)
        self.assertEqual(result["reason"],"insufficient_independent_groups")

    def test_rejects_incomplete_duplicate_cross_method_and_bad_predictions(self):
        valid = rows(((.1,.9),(.2,.8)))
        cases = [[], valid[:-1], valid+[valid[0]],
                 [dict(row,score=float("nan")) if i==0 else row for i,row in enumerate(valid)],
                 [dict(row,score=True) if i==0 else row for i,row in enumerate(valid)],
                 [dict(row,label=True) if i==0 else row for i,row in enumerate(valid)],
                 [dict(row,group_id="") if i==0 else row for i,row in enumerate(valid)]]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(ValueError):
                paired_source_auc_difference(case,valid,replicates=2)
        with self.assertRaises(ValueError):
            paired_source_auc_difference(valid,rows(((.1,.9),)),replicates=2)
        for option in ({"replicates":0},{"replicates":True},{"seed":True},{"confidence":1}):
            with self.subTest(option=option),self.assertRaises(ValueError):
                paired_source_auc_difference(valid,valid,**option)


if __name__ == "__main__":
    unittest.main()
