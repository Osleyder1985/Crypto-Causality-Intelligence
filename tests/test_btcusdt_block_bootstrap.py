import unittest

from scripts.research.btcusdt_block_bootstrap import benjamini_yekutieli, paired_block_bootstrap


class PairedBlockBootstrapTests(unittest.TestCase):
    def test_reports_reproducible_confidence_intervals_and_tests(self):
        actual = [0.02 if i % 3 else -0.01 for i in range(120)]
        baseline = [0.0] * len(actual)
        predicted = [value * 0.7 for value in actual]
        first = paired_block_bootstrap(actual, predicted, baseline, block_length=12, replicates=300, seed=7)
        second = paired_block_bootstrap(actual, predicted, baseline, block_length=12, replicates=300, seed=7)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "evaluated")
        self.assertGreater(first["confidence_intervals_95"]["mae_improvement"]["estimate"], 0)
        self.assertIn("p_value_one_sided", first["one_sided_superiority_tests"]["mae"])

    def test_preserves_pairing_and_does_not_claim_significance_for_no_gain(self):
        actual = [0.01 * ((i % 5) - 2) for i in range(120)]
        baseline = [0.0] * len(actual)
        result = paired_block_bootstrap(actual, baseline, baseline, block_length=12, replicates=300, seed=11)
        self.assertEqual(result["confidence_intervals_95"]["mae_improvement"]["estimate"], 0)
        self.assertEqual(result["one_sided_superiority_tests"]["mae"]["p_value_one_sided"], 1.0)

    def test_marks_sample_smaller_than_block_as_insufficient(self):
        result = paired_block_bootstrap([0.1] * 10, [0.0] * 10, [0.0] * 10, block_length=24)
        self.assertEqual(result["status"], "insufficient_observations_for_block_bootstrap")
        self.assertEqual(result["replicates"], 0)

    def test_benjamini_yekutieli_controls_adjusted_values_under_dependence(self):
        adjusted = benjamini_yekutieli([0.01, 0.04, 0.03])
        self.assertAlmostEqual(adjusted[0], 0.055)
        self.assertAlmostEqual(adjusted[1], 0.07333333333333333)
        self.assertAlmostEqual(adjusted[2], 0.07333333333333333)

    def test_benjamini_yekutieli_rejects_invalid_p_values(self):
        with self.assertRaisesRegex(ValueError, "within"):
            benjamini_yekutieli([1.2])

    def test_rejects_mismatched_or_nonfinite_series(self):
        with self.assertRaisesRegex(ValueError, "equal lengths"):
            paired_block_bootstrap([1.0], [], [0.0])
        with self.assertRaisesRegex(ValueError, "finite"):
            paired_block_bootstrap([float("nan")], [0.0], [0.0])


if __name__ == "__main__":
    unittest.main()
