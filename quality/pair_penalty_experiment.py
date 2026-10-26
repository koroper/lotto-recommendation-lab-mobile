"""One-variable A/B replay: change only the standard portfolio's repeated-pair penalty.

Baseline pair penalty 0.75 -> candidate 1.50. All number scores,
candidate pools, ticket counts, beam widths and research weights stay fixed.
No in-app behavior or automatic parameter promotion changes.

Historical replay windows were registered in docs/PAIR_PENALTY_EXPERIMENT_PLAN.md
before running on actual lottery data. Once evaluated, treat them as inspected.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from quality.portfolio_backtest import _score_tickets, load_history, summarize, engine

BASELINE_PENALTY = 0.75
CANDIDATE_PENALTY = 1.50
WINDOWS = (
    ("early_replay", 1152, 1175),
    ("later_replay", 1200, 1223),
)


def repeated_pairs(tickets):
    counts = {}
    for ticket in tickets:
        for pair in itertools.combinations(sorted(ticket), 2):
            counts[pair] = counts.get(pair, 0) + 1
    return sum(max(0, count - 1) for count in counts.values())


def _portfolio_for(history_before_draw, games, candidate):
    config = {"games": games, "style": "표준"}
    if candidate:
        config["experimentPairPenalty"] = CANDIDATE_PENALTY
    rec = json.loads(engine.recommend(
        json.dumps(history_before_draw, ensure_ascii=False),
        "", json.dumps(config, ensure_ascii=False),
    ))
    return rec


def evaluate_window(history, name, first, last, games=5):
    if len(history) < last or history[last - 1]["draw"] != last:
        raise ValueError("Complete chronological history through draw " + str(last) + " required")
    baseline_weeks = []
    candidate_weeks = []
    baseline_pairs = 0
    candidate_pairs = 0
    changed_draws = 0
    all_recommendations = []
    for draw in range(first, last + 1):
        available = history[:draw - 1]
        actual = history[draw - 1]
        assert actual["draw"] == draw
        if len(available) < 80:
            raise ValueError("Insufficient pre-draw training history")
        base = _portfolio_for(available, games, candidate=False)
        trial = _portfolio_for(available, games, candidate=True)
        if base["targetDraw"] != draw or trial["targetDraw"] != draw:
            raise AssertionError("Target draw misalignment: " + str(draw))
        a = [row["numbers"] for row in base["games"]]
        b = [row["numbers"] for row in trial["games"]]
        if len(a) != games or len(b) != games:
            raise AssertionError("Ticket-count mismatch")
        baseline_weeks.append(_score_tickets(a, actual))
        candidate_weeks.append(_score_tickets(b, actual))
        pa = repeated_pairs(a)
        pb = repeated_pairs(b)
        baseline_pairs += pa
        candidate_pairs += pb
        if a != b:
            changed_draws += 1
        all_recommendations.append({
            "draw": draw,
            "baselineId": base["recommendationId"],
            "candidateId": trial["recommendationId"],
            "baselineBestMatches": baseline_weeks[-1]["bestMatches"],
            "candidateBestMatches": candidate_weeks[-1]["bestMatches"],
            "baselineRepeatedPairs": pa,
            "candidateRepeatedPairs": pb,
        })

    base_s = summarize(baseline_weeks, games)
    cand_s = summarize(candidate_weeks, games)
    keys = (
        "meanMatchesPerTicket",
        "meanBestMatchesPerDraw",
        "drawsWithAny3Plus",
        "drawsWithAny4Plus",
        "drawsWithAny5Plus",
        "drawsWithSix",
    )
    return {
        "name": name,
        "firstDraw": first,
        "lastDraw": last,
        "numberOfDraws": last - first + 1,
        "gamesPerDraw": games,
        "baseline": base_s,
        "candidate": cand_s,
        "pairedDeltaCandidateMinusBaseline": {
            k: round(cand_s[k] - base_s[k], 4) for k in keys
        },
        "baselineRepeatedPairs": baseline_pairs,
        "candidateRepeatedPairs": candidate_pairs,
        "changedRecommendationDraws": changed_draws,
        "drawDetails": all_recommendations,
    }


def run_experiment(history, games=5):
    if games != 5:
        raise ValueError("This preregistered experiment must use exactly 5 tickets/draw")
    # Immutable pre-registration windows; never select ranges in response to results.
    windows = [evaluate_window(history, name, start, end, games) for name, start, end in WINDOWS]
    full_baseline_pairs = sum(w["baselineRepeatedPairs"] for w in windows)
    full_candidate_pairs = sum(w["candidateRepeatedPairs"] for w in windows)
    if full_baseline_pairs > 0:
        reduction = round(100 * (1 - full_candidate_pairs / full_baseline_pairs), 2)
    else:
        reduction = 0.0
    return {
        "status": "HOLD_PROSPECTIVE_UNTESTED",
        "engineChangedForApp": False,
        "styles": "표준 only",
        "variable": "repeated pair penalty in portfolio objective",
        "baselinePenalty": BASELINE_PENALTY,
        "candidatePenalty": CANDIDATE_PENALTY,
        "games": games,
        "historyLatestDraw": history[-1]["draw"],
        "windows": windows,
        "repeatedPairReductionPercent": reduction,
        "evaluationNote": (
            "Historical A/B replay only, not future prediction proof. "
            "Candidate weights are not promoted, 1224..1247 was previously "
            "inspected, and future draws after 1247 remain unobserved."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    history = load_history(args.history)
    result = run_experiment(history)
    print(
        "PAIR_PENALTY_EXPERIMENT_RESULT=" +
        json.dumps({
            "status": result["status"],
            "baselinePenalty": result["baselinePenalty"],
            "candidatePenalty": result["candidatePenalty"],
            "repeatedPairReductionPercent": result["repeatedPairReductionPercent"],
            "windows": [
                {k: v for k, v in w.items() if k != "drawDetails"}
                for w in result["windows"]
            ],
        }, ensure_ascii=False)
    )
    if args.json_output:
        args.json_output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
