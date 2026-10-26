"""Regression tests: opt-in one-variable experiment leaves normal recommendations intact."""
import json
import random
import unittest

from quality.portfolio_backtest import engine
from quality.pair_penalty_experiment import (
    BASELINE_PENALTY, CANDIDATE_PENALTY,
    _portfolio_for, evaluate_window, repeated_pairs,
)


def history_fixture(seed=400, draws=104):
    rng = random.Random(seed)
    result = []
    for draw in range(1, draws + 1):
        numbers = sorted(rng.sample(range(1, 46), 6))
        bonus = rng.choice([i for i in range(1, 46) if i not in numbers])
        result.append({
            "draw": draw,
            "numbers": numbers,
            "bonus": bonus,
            "date": "2026-01-01",
        })
    return result


class SinglePairPenaltyTests(unittest.TestCase):
    def test_original_app_result_exactly_equals_explicit_baseline_coefficient(self):
        data = json.dumps(history_fixture(), ensure_ascii=False)
        for games in (1, 5):
            default = json.loads(engine.recommend(
                data, "", json.dumps({"style": "표준", "games": games}, ensure_ascii=False)
            ))
            explicit_baseline = json.loads(engine.recommend(
                data, "", json.dumps({
                    "style": "표준",
                    "games": games,
                    "experimentPairPenalty": BASELINE_PENALTY
                }, ensure_ascii=False)
            ))
            self.assertEqual(default, explicit_baseline)
            self.assertEqual(default["targetDraw"], 105)

    def test_experiment_changes_only_the_pair_coefficient_objective(self):
        rows = [
            {"numbers": [1, 2, 3, 4, 5, 6], "score": 70.0},
            {"numbers": [1, 2, 7, 8, 9, 10], "score": 65.0},
        ]
        self.assertEqual(1, repeated_pairs([row["numbers"] for row in rows]))
        base = engine._portfolio_objective(rows, "표준")
        candidate = engine._portfolio_objective(
            rows, "표준", pair_penalty_override=CANDIDATE_PENALTY
        )
        self.assertAlmostEqual(base - candidate, CANDIDATE_PENALTY - BASELINE_PENALTY)

    def test_research_candidate_does_not_modify_number_scores_or_pools(self):
        data = json.dumps(history_fixture(141), ensure_ascii=False)
        base = json.loads(engine.recommend(
            data, "", json.dumps({"style": "표준", "games": 5}, ensure_ascii=False)
        ))
        candidate = json.loads(engine.recommend(
            data, "", json.dumps({
                "style": "표준", "games": 5,
                "experimentPairPenalty": CANDIDATE_PENALTY
            }, ensure_ascii=False)
        ))
        for key in ("core", "semiCore", "candidatePool", "confidence", "weights",
                    "modelTop", "latestDraw", "targetDraw"):
            self.assertEqual(base[key], candidate[key])
        self.assertEqual(5, len(candidate["games"]))
        self.assertEqual(5, len({tuple(g["numbers"]) for g in candidate["games"]}))

    def test_rejects_nonstandard_style_and_unbounded_experiment(self):
        data = json.dumps(history_fixture(), ensure_ascii=False)
        for style, value in (("분산", 1.5), ("표준", -1), ("표준", 4),
                             ("표준", float("nan"))):
            with self.assertRaises(ValueError):
                engine.recommend(
                    data, "", json.dumps({
                        "style": style, "games": 5,
                        "experimentPairPenalty": value,
                    }, ensure_ascii=False)
                )

    def test_future_draw_mutation_does_not_affect_previous_draw_result(self):
        rows = history_fixture(seed=902)
        first = evaluate_window(rows, "synthetic", 103, 104, games=5)
        changed = json.loads(json.dumps(rows))
        changed[-1]["numbers"] = [1, 2, 3, 4, 5, 6]
        second = evaluate_window(changed, "synthetic", 103, 104, games=5)
        # Evaluating draw 103 never observes draw 104 or later.
        self.assertEqual(first["drawDetails"][0], second["drawDetails"][0])
        self.assertEqual(first["baseline"]["evaluatedDraws"], 2)
        self.assertEqual(first["candidate"]["evaluatedDraws"], 2)
        self.assertEqual(first["gamesPerDraw"], 5)

    def test_candidate_tickets_are_deterministic(self):
        rows = history_fixture(991)
        a = _portfolio_for(rows[:-1], 5, candidate=True)
        b = _portfolio_for(rows[:-1], 5, candidate=True)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
