"""Leakage-free, descriptive historical audit of the *actual five-ticket portfolio*.

This is an offline research tool, NOT a live prediction or model weight update.
Every ticket is generated from history strictly before the draw being evaluated.
It compares equal-weight standard/spread portfolios with reproducible random
five-ticket portfolios at identical ticket count and zero purchase cost assumptions.

Usage:
    python quality/portfolio_backtest.py --history lotto-history.json --window 24
    python quality/portfolio_backtest.py --history lotto-history.json --window 24 --json-output report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = PROJECT_ROOT / "app" / "src" / "main" / "python"
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
import mobile_engine as engine  # noqa: E402

STYLES = ("표준", "분산")
NUMBERS = tuple(range(1, 46))
MIN_TRAIN_DRAWS = 80


def normalize_history(raw):
    """Accept mobile engine rows, existing drawNo/data JSON, or snake_case mirror."""
    records = raw.get("data") if isinstance(raw, dict) else raw
    if not isinstance(records, list):
        raise ValueError("Expected an array of draw records or an object with data array")
    normalized = []
    for i, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raise ValueError("Draw record must be an object")
        draw = record.get("draw", record.get("drawNo", record.get("draw_no")))
        if draw is None or int(draw) != i:
            raise ValueError("Missing/duplicate/out-of-order draw at row " + str(i))
        nums = record.get("numbers", [])
        bonus = record.get("bonus", record.get("bonusNo", record.get("bonus_no", 0)))
        normalized.append({
            "draw": int(draw),
            "date": str(record.get("date", ""))[:10],
            "numbers": list(nums),
            "bonus": int(bonus),
        })
    # Reuse engine's canonical number, range and bonus validation.
    return engine._parse_history(json.dumps(normalized, ensure_ascii=False))


def load_history(path):
    return normalize_history(json.loads(Path(path).read_text(encoding="utf-8")))


def _score_tickets(tickets, actual):
    target = set(actual["numbers"])
    assert len(target) == 6
    seen = set()
    matches = []
    for ticket in tickets:
        numbers = tuple(sorted(ticket))
        if len(numbers) != 6 or len(set(numbers)) != 6 or not all(1 <= n <= 45 for n in numbers):
            raise ValueError("Invalid six-number ticket")
        if numbers in seen:
            raise ValueError("Duplicate portfolio ticket")
        seen.add(numbers)
        matches.append(len(set(numbers) & target))
    return {
        "draw": actual["draw"],
        "matches": matches,
        "bestMatches": max(matches),
        "tickets3Plus": sum(v >= 3 for v in matches),
        "tickets4Plus": sum(v >= 4 for v in matches),
        "tickets5Plus": sum(v >= 5 for v in matches),
        "tickets6": sum(v == 6 for v in matches),
    }


def _random_tickets(draw, repetition, games, seed):
    # Stable, reproducible randomness; never include winning numbers in the seed.
    raw_seed = hashlib.sha256(f"{seed}|{draw}|{repetition}".encode("ascii")).digest()
    rng = random.Random(int.from_bytes(raw_seed, "big"))
    tickets = set()
    while len(tickets) < games:
        tickets.add(tuple(sorted(rng.sample(NUMBERS, 6))))
    return sorted(tickets)


def summarize(weeks, games):
    if not weeks:
        raise ValueError("No evaluated weeks")
    return {
        "evaluatedDraws": len(weeks),
        "ticketsPerDraw": games,
        "meanMatchesPerTicket": round(
            sum(sum(w["matches"]) for w in weeks) / (len(weeks) * games), 4
        ),
        "meanBestMatchesPerDraw": round(
            sum(w["bestMatches"] for w in weeks) / len(weeks), 4
        ),
        "drawsWithAny3Plus": sum(w["tickets3Plus"] > 0 for w in weeks),
        "drawsWithAny4Plus": sum(w["tickets4Plus"] > 0 for w in weeks),
        "drawsWithAny5Plus": sum(w["tickets5Plus"] > 0 for w in weeks),
        "drawsWithSix": sum(w["tickets6"] > 0 for w in weeks),
    }


def run_portfolio_benchmark(history, window=24, games=5, repetitions=100, seed=2045):
    """Pure read-only benchmark; does not learn, promote or modify app state.

    The first evaluated draw's complete history is unavailable to the model.
    Only draws strictly before its target are passed into engine.recommend.
    """
    if not 1 <= games <= 10:
        raise ValueError("games must be 1..10")
    if not 1 <= window <= 120:
        raise ValueError("window must be 1..120")
    if not 1 <= repetitions <= 1000:
        raise ValueError("repetitions must be 1..1000")
    if len(history) - window < MIN_TRAIN_DRAWS:
        raise ValueError("At least 80 pre-target draws are required for every test draw")
    for i, item in enumerate(history, start=1):
        if item["draw"] != i:
            raise ValueError("History must have contiguous, chronological draw numbers")

    model_weeks = {style: [] for style in STYLES}
    random_weeks = [[] for _ in range(repetitions)]
    start = len(history) - window
    for target_idx in range(start, len(history)):
        actual = history[target_idx]
        # The ONLY features available are draws strictly before the target.
        available = json.dumps(history[:target_idx], ensure_ascii=False)
        for style in STYLES:
            rec = json.loads(engine.recommend(
                available, "", json.dumps({"games": games, "style": style}, ensure_ascii=False)
            ))
            if rec["targetDraw"] != actual["draw"]:
                raise AssertionError("Potential lookahead or misaligned draw")
            tickets = [row["numbers"] for row in rec["games"]]
            if len(tickets) != games:
                raise AssertionError("Engine returned incorrect ticket count")
            model_weeks[style].append(_score_tickets(tickets, actual))
        for repetition in range(repetitions):
            random_weeks[repetition].append(_score_tickets(
                _random_tickets(actual["draw"], repetition, games, seed), actual
            ))

    model = {s: summarize(model_weeks[s], games) for s in STYLES}
    random_summaries = [summarize(w, games) for w in random_weeks]
    measures = (
        "meanMatchesPerTicket", "meanBestMatchesPerDraw",
        "drawsWithAny3Plus", "drawsWithAny4Plus",
        "drawsWithAny5Plus", "drawsWithSix",
    )
    baseline = {
        "repetitions": repetitions,
        "seed": seed,
        "mean": {
            key: round(sum(b[key] for b in random_summaries) / repetitions, 4)
            for key in measures
        },
        "upper95Percentile": {
            key: sorted(b[key] for b in random_summaries)[math.ceil(0.95 * repetitions) - 1]
            for key in measures
        },
    }
    return {
        "status": "DESCRIPTIVE_ONLY",
        "recommendationChanged": False,
        "weights": "six-model equal (not re-fitted on evaluated draws)",
        "evaluatedFirstDraw": history[start]["draw"],
        "evaluatedLastDraw": history[-1]["draw"],
        "minTrainingDraws": start,
        "window": window,
        "games": games,
        "styles": model,
        "randomBaseline": baseline,
        "perDraw": model_weeks,
        "disclaimer": (
            "Lottery outcomes are random. All distinct 6/45 combinations have the "
            "same 1-in-8,145,060 jackpot probability. This is descriptive historical "
            "evidence, not proof of future predictive ability, and does not promote "
            "new weights or modify real purchase recommendations."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--history", type=Path, required=True,
                        help="JSON file (draw/data format), not the application's private DB")
    parser.add_argument("--window", type=int, default=24)
    parser.add_argument("--games", type=int, default=5)
    parser.add_argument("--repetitions", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2045)
    parser.add_argument("--json-output", type=Path, default=None)
    args = parser.parse_args()
    report = run_portfolio_benchmark(
        load_history(args.history), args.window, args.games, args.repetitions, args.seed
    )
    print(f"Historical portfolio audit: {report['evaluatedFirstDraw']}..{report['evaluatedLastDraw']}")
    print(f"Fixed {args.games} tickets per draw, no future-draw training, equal weights.")
    for name, stats in report["styles"].items():
        print(
            f"{name}: mean hits/ticket {stats['meanMatchesPerTicket']:.4f}, "
            f"weeks with >=3 matches {stats['drawsWithAny3Plus']}/{report['window']}, "
            f">=4 {stats['drawsWithAny4Plus']}/{report['window']}"
        )
    print("Random comparison (mean of replicates):", report["randomBaseline"]["mean"])
    print("HOLD: offline descriptive evaluation only; no model promotion or live score changes.")
    if args.json_output:
        args.json_output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print("Written:", args.json_output)


if __name__ == "__main__":
    main()
