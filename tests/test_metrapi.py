import unittest

from gateway_mcp.services.metrapi import evaluate_gab


class MetrapiEvaluationTests(unittest.TestCase):
    def test_scores_gab_with_map_and_target_yield(self):
        result = evaluate_gab({"source":"cian","source_id":"1","price":120_000_000,"area_total":500,"description":"ГАБ. Арендатор. МАП 1 000 000 рублей","price_history":[]})
        self.assertEqual(result["gross_yield_calculated_pct"], 10.0)
        self.assertGreaterEqual(result["selection_score"], 11)

    def test_reject_signal_is_low_without_income(self):
        result = evaluate_gab({"source":"cian","source_id":"2","price":120_000_000,"description":"Доходная недвижимость"})
        self.assertLess(result["selection_score"], 5)


if __name__ == "__main__":
    unittest.main()
