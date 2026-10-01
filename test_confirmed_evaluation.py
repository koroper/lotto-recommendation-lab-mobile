import sqlite3
import json

# Mirror Korean Lotto 6/45 rules
def evaluate_game(numbers, winning, bonus):
    w_set = set(winning)
    n_set = set(numbers)
    matched = sorted(n_set & w_set)
    match_count = len(matched)
    has_bonus = bonus in n_set
    
    if match_count == 6:
        tier = "1등"
    elif match_count == 5 and has_bonus:
        tier = "2등"
    elif match_count == 5:
        tier = "3등"
    elif match_count == 4:
        tier = "4등"
    elif match_count == 3:
        tier = "5등"
    else:
        tier = "미당첨"
        
    return {
        "numbers": numbers,
        "matched": matched,
        "match_count": match_count,
        "has_bonus": has_bonus,
        "tier": tier
    }

def evaluate_draw(winning, bonus, games):
    order = {"1등": 1, "2등": 2, "3등": 3, "4등": 4, "5등": 5, "미당첨": 6}
    evals = [evaluate_game(g["numbers"], winning, bonus) for g in games]
    best_tier = min(evals, key=lambda x: order[x["tier"]])["tier"]
    best_match = max(x["match_count"] for x in evals)
    return {
        "winning": winning,
        "bonus": bonus,
        "games": evals,
        "best_tier": best_tier,
        "best_match": best_match
    }

# 1. Deterministic Tier Rule Tests
WINNING = [3, 11, 14, 18, 26, 34]
BONUS = 42

# Case 1: 6 main matches => 1등
g1 = evaluate_game([3, 11, 14, 18, 26, 34], WINNING, BONUS)
assert g1["match_count"] == 6 and g1["tier"] == "1등", f"Expected 1등, got {g1}"

# Case 2: 5 main + bonus => 2등
g2 = evaluate_game([3, 11, 14, 18, 26, 42], WINNING, BONUS)
assert g2["match_count"] == 5 and g2["has_bonus"] and g2["tier"] == "2등", f"Expected 2등, got {g2}"

# Case 3: 5 main only (no bonus) => 3등
g3 = evaluate_game([3, 11, 14, 18, 26, 45], WINNING, BONUS)
assert g3["match_count"] == 5 and not g3["has_bonus"] and g3["tier"] == "3등", f"Expected 3등, got {g3}"

# Case 4: 4 main => 4등 (with or without bonus)
g4a = evaluate_game([3, 11, 14, 18, 40, 45], WINNING, BONUS)
assert g4a["match_count"] == 4 and g4a["tier"] == "4등", f"Expected 4등, got {g4a}"
g4b = evaluate_game([3, 11, 14, 18, 42, 45], WINNING, BONUS)
assert g4b["match_count"] == 4 and g4b["has_bonus"] and g4b["tier"] == "4등", f"Expected 4등 with bonus, got {g4b}"

# Case 5: 3 main => 5등
g5 = evaluate_game([3, 11, 14, 39, 40, 45], WINNING, BONUS)
assert g5["match_count"] == 3 and g5["tier"] == "5등", f"Expected 5등, got {g5}"

# Case 6: 2 or fewer => 미당첨
g6_2 = evaluate_game([3, 11, 38, 39, 40, 45], WINNING, BONUS)
assert g6_2["match_count"] == 2 and g6_2["tier"] == "미당첨", f"Expected 미당첨 (2 matches), got {g6_2}"
g6_2b = evaluate_game([3, 11, 42, 39, 40, 45], WINNING, BONUS)
assert g6_2b["match_count"] == 2 and g6_2b["has_bonus"] and g6_2b["tier"] == "미당첨", f"Expected 미당첨 (2 + bonus), got {g6_2b}"
g6_0 = evaluate_game([1, 2, 4, 5, 6, 7], WINNING, BONUS)
assert g6_0["match_count"] == 0 and g6_0["tier"] == "미당첨", f"Expected 미당첨 (0 matches), got {g6_0}"

# 2. Draw-level summary evaluation
draw_eval = evaluate_draw(WINNING, BONUS, [
    {"index": 1, "numbers": [3, 11, 14, 18, 40, 45]}, # 4등 (4 matches)
    {"index": 2, "numbers": [3, 11, 14, 39, 40, 45]}, # 5등 (3 matches)
    {"index": 3, "numbers": [1, 2, 4, 5, 6, 7]},       # 미당첨 (0 matches)
])
assert draw_eval["best_tier"] == "4등"
assert draw_eval["best_match"] == 4

# 3. Database roundtrip & pending state validation
conn = sqlite3.connect(":memory:")
cur = conn.cursor()
cur.execute("""
    CREATE TABLE draws(
        draw_no INTEGER PRIMARY KEY,
        date TEXT NOT NULL,
        n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
        n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
        bonus INTEGER NOT NULL
    )
""")
cur.execute("""
    CREATE TABLE recommendations(
        draw_no INTEGER PRIMARY KEY,
        recommendation_id TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        confirmed_at INTEGER NOT NULL
    )
""")

# Insert past completed draw 1243
cur.execute("INSERT INTO draws VALUES (1243, '2026-09-26', 3, 11, 14, 18, 26, 34, 42)")

# Insert confirmed recommendation for draw 1243
payload_1243 = {
    "recommendationId": "1243-ABC12345",
    "targetDraw": 1243,
    "games": [
        {"index": 1, "numbers": [3, 11, 14, 18, 40, 45], "score": 85.0},
        {"index": 2, "numbers": [1, 2, 4, 5, 6, 7], "score": 80.0},
    ]
}
cur.execute("INSERT INTO recommendations VALUES (1243, '1243-ABC12345', ?, 1790000000000)", (json.dumps(payload_1243),))

# Insert confirmed recommendation for future target draw 1244 (NO draw result exists yet)
payload_1244 = {
    "recommendationId": "1244-0FE2C161BB",
    "targetDraw": 1244,
    "games": [
        {"index": 1, "numbers": [5, 12, 19, 23, 31, 44], "score": 88.0}
    ]
}
cur.execute("INSERT INTO recommendations VALUES (1244, '1244-0FE2C161BB', ?, 1790800000000)", (json.dumps(payload_1244),))

# Query draw 1244: winning numbers absent => must be pending (evaluation = None)
cur.execute("SELECT n1, n2, n3, n4, n5, n6, bonus FROM draws WHERE draw_no=1244")
r1244 = cur.fetchone()
assert r1244 is None, "Future draw 1244 must not have winning numbers"

# Query draw 1243: winning numbers present => evaluated correctly
cur.execute("SELECT n1, n2, n3, n4, n5, n6, bonus FROM draws WHERE draw_no=1243")
r1243 = cur.fetchone()
assert r1243 == (3, 11, 14, 18, 26, 34, 42)
eval_1243 = evaluate_draw(list(r1243[:6]), r1243[6], payload_1243["games"])
assert eval_1243["best_tier"] == "4등"
assert eval_1243["best_match"] == 4
assert eval_1243["games"][0]["tier"] == "4등"
assert eval_1243["games"][0]["matched"] == [3, 11, 14, 18]
assert eval_1243["games"][1]["tier"] == "미당첨"

# 4. Performance Dashboard Aggregator Parity Tests
def aggregate_performance(records, limit=None):
    pending = sum(1 for r in records if r.get("evaluation") is None)
    evaluated = [r for r in records if r.get("evaluation") is not None]
    evaluated.sort(key=lambda r: (r["draw"], r.get("confirmed_at", 0)), reverse=True)
    if limit is not None and limit > 0:
        windowed = evaluated[:limit]
    else:
        windowed = evaluated

    order = {"1등": 1, "2등": 2, "3등": 3, "4등": 4, "5등": 5, "미당첨": 6}
    tier_counts = {t: 0 for t in ["1등", "2등", "3등", "4등", "5등", "미당첨"]}
    for r in windowed:
        tier_counts[r["evaluation"]["best_tier"]] += 1

    if not windowed:
        return {
            "completed_draws": 0,
            "pending_draws": pending,
            "average_best_matches": None,
            "draws_with_3plus": 0,
            "draws_with_4plus": 0,
            "best_tier": None,
            "tier_counts": tier_counts
        }

    avg_best = sum(r["evaluation"]["best_match"] for r in windowed) / len(windowed)
    with_3plus = sum(1 for r in windowed if r["evaluation"]["best_match"] >= 3)
    with_4plus = sum(1 for r in windowed if r["evaluation"]["best_match"] >= 4)
    best_tier = min(windowed, key=lambda r: order[r["evaluation"]["best_tier"]])["evaluation"]["best_tier"]

    return {
        "completed_draws": len(windowed),
        "pending_draws": pending,
        "average_best_matches": avg_best,
        "draws_with_3plus": with_3plus,
        "draws_with_4plus": with_4plus,
        "best_tier": best_tier,
        "tier_counts": tier_counts
    }

# Test 1: Pending excluded from completed
records_sample = [
    {"draw": 1001, "confirmed_at": 1000, "evaluation": {"best_match": 4, "best_tier": "4등"}},
    {"draw": 1002, "confirmed_at": 2000, "evaluation": {"best_match": 3, "best_tier": "5등"}},
    {"draw": 1003, "confirmed_at": 3000, "evaluation": None},
    {"draw": 1004, "confirmed_at": 4000, "evaluation": None},
]
agg_all = aggregate_performance(records_sample, None)
assert agg_all["completed_draws"] == 2
assert agg_all["pending_draws"] == 2
assert abs(agg_all["average_best_matches"] - 3.5) < 1e-4
assert agg_all["draws_with_3plus"] == 2
assert agg_all["draws_with_4plus"] == 1
assert agg_all["best_tier"] == "4등"

# Test 2: Recent 10 window selects latest 10
fifteen_records = [
    {"draw": d, "confirmed_at": d * 1000, "evaluation": {"best_match": 1 if d <= 1005 else 5, "best_tier": "미당첨" if d <= 1005 else "3등"}}
    for d in range(1001, 1016)
]
agg_10 = aggregate_performance(fifteen_records, 10)
assert agg_10["completed_draws"] == 10
assert abs(agg_10["average_best_matches"] - 5.0) < 1e-4
assert agg_10["best_tier"] == "3등"
assert agg_10["tier_counts"]["3등"] == 10

# Test 3: Empty dataset
agg_empty = aggregate_performance([{"draw": 1001, "evaluation": None}], 10)
assert agg_empty["completed_draws"] == 0
assert agg_empty["pending_draws"] == 1
assert agg_empty["average_best_matches"] is None
assert agg_empty["best_tier"] is None

print("ALL EVALUATION, PERSISTENCE & AGGREGATOR TESTS PASSED")
