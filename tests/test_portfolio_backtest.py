"""Portfolio benchmark regression tests: strict chronology, cost parity, reproducibility."""
import json
import random
import unittest

from quality.portfolio_backtest import (
    _random_tickets,
    _score_tickets,
    normalize_history,
    run_portfolio_benchmark,
    summarize,
)


def synthetic_history(draws=104, seed=5306):
    rng = random.Random(seed)
    return [
        {
            "draw": draw,
            "date": "2026-01-01",
            "numbers": sorted(rng.sample(range(1, 46), 6)),
            "bonus": 0,
        }
        for draw in range(1, draws + 1)
    ]


class PortfolioBenchmarkTests(unittest.TestCase):
    def test_normalizes_legacy_and_mirror_formats(self):
        history = synthetic_history(100)
        mirror = [
            {
                "draw_no": row["draw"],
                "date": "2026-01-01T00:00:00Z",
                "numbers": row["numbers"],
                "bonus_no": 0,
            } for row in history
        ]
        legacy = [
            {
                "drawNo": row["draw"],
                "date": row["date"],
                "numbers": row["numbers"],
                "bonusNo": 0,
            } for row in history
        ]
        self.assertEqual(normalize_history(mirror), normalize_history({"data": legacy}))
        self.assertEqual(history, normalize_history(history))

    def test_rejects_skipped_or_out_of_order_draw(self):
        data = synthetic_history()
        data[12]["draw"] = 14
        with self.assertRaises(ValueError):
            normalize_history(data)

    def test_rejects_duplicate_or_out_of_range_numbers(self):
        data = synthetic_history()
        data[11]["numbers"] = [1, 1, 3, 4, 5, 6]
        with self.assertRaises(ValueError):
            normalize_history(data)

    def test_scores_real_five_ticket_portfolio(self):
        actual = {"draw": 12, "numbers": [1, 2, 3, 4, 5, 6]}
        tickets = [
            [1, 2, 3, 7, 8, 9],
            [1, 2, 3, 4, 7, 9],
            [2, 3, 10, 11, 12, 13],
        ]
        w = _score_tickets(tickets, actual)
        self.assertEqual([3, 4, 2], w["matches"])
        self.assertEqual(2, w["tickets3Plus"])
        self.assertEqual(1, w["tickets4Plus"])
        self.assertEqual(4, w["bestMatches"])
        stats = summarize([w], 3)
        self.assertEqual(1, stats["drawsWithAny3Plus"])
        self.assertEqual(1, stats["drawsWithAny4Plus"])
        self.assertEqual(1.0, stats["evaluatedDraws"])

    def test_duplicate_tickets_fail(self):
        actual = {"draw": 12, "numbers": [1, 2, 3, 4, 5, 6]}
        with self.assertRaises(ValueError):
            _score_tickets([[1, 2, 3, 4, 5, 6]] * 2, actual)

    def test_random_baseline_is_deterministic_and_unique(self):
        a = _random_tickets(1247, 0, 5, 2045)
        self.assertEqual(a, _random_tickets(1247, 0, 5, 2045))
        self.assertEqual(5, len(a))
        self.assertEqual(5, len(set(a)))
        self.assertTrue(all(len(set(t)) == 6 and all(1 <= n <= 45 for n in t) for t in a))

    def test_chronological_evaluation_never_modifies_recommendations(self):
        hist = synthetic_history()
        report = run_portfolio_benchmark(hist, window=2, games=3, repetitions=3)
        self.assertEqual((103, 104), (
            report["evaluatedFirstDraw"], report["evaluatedLastDraw"]
        ))
        self.assertEqual(False, report["recommendationChanged"])
        self.assertEqual(3, report["games"])
        self.assertEqual(3, report["randomBaseline"]["repetitions"])
        self.assertEqual(2, report["styles"]["표준"]["evaluatedDraws"])
        self.assertEqual(2, report["styles"]["분산"]["evaluatedDraws"])
        self.assertEqual(2, len(report["perDraw"]["표준"]))
        self.assertEqual(hist[0]["numbers"], synthetic_history()[0]["numbers"])

        # Mutation of a *future* draw cannot affect the earlier draw's
        # generated tickets or evaluated outcome.
        changed = json.loads(json.dumps(hist))
        changed[-1]["numbers"] = [1, 2, 3, 4, 5, 6]
        new_report = run_portfolio_benchmark(changed, window=2, games=3, repetitions=3)
        for style in ("표준", "분산"):
            self.assertEqual(report["perDraw"][style][0], new_report["perDraw"][style][0])
        self.assertEqual(
            report["randomBaseline"]["seed"], new_report["randomBaseline"]["seed"]
        )

    def test_refuses_insufficient_training_history(self):
        with self.assertRaisesRegex(ValueError, "80 pre-target"):
            run_portfolio_benchmark(synthetic_history(81), window=2, games=5)

    def test_rejects_invalid_number_of_tickets(self):
        with self.assertRaisesRegex(ValueError, "games"):
            run_portfolio_benchmark(synthetic_history(), games=0)


if __name__ == "__main__":
    unittest.main()
