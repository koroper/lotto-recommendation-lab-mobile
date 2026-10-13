"""
Phase 2 Step 3G - Focused Regression Tests (G1-G14)
Verification Part 1: Python Regression Suite & Target 1244 Verification
"""

import sys
import os
import json
import random
import urllib.request

# Ensure app/src/main/python is in path
sys.path.insert(0, os.path.abspath("app/src/main/python"))
import mobile_engine as m

EPSILON = 1e-9
EQUAL_WEIGHTS = {mid: 1.0 / 6.0 for mid in m.MODELS}


def make_synthetic_history(seed=1234, count=150):
    rng = random.Random(seed)
    hist = []
    for draw in range(1, count + 1):
        nums = sorted(rng.sample(range(1, 46), 6))
        bonus = rng.choice([n for n in range(1, 46) if n not in nums])
        hist.append({
            "draw": draw,
            "date": f"2026-01-{draw % 28 + 1:02d}",
            "numbers": nums,
            "bonus": bonus
        })
    return hist


def load_actual_lotto_history():
    url = "https://raw.githubusercontent.com/JunKwon91/lotto-data/main/data/lotto-history.json"
    with urllib.request.urlopen(url, timeout=15) as r:
        raw = json.loads(r.read().decode())["data"]
    capped = [d for d in raw if d["drawNo"] <= 1243]
    hist = [{
        "draw": d["drawNo"],
        "date": d.get("date", ""),
        "numbers": sorted(d["numbers"]),
        "bonus": d["bonusNo"]
    } for d in capped]
    hist.sort(key=lambda x: x["draw"])
    assert hist[-1]["draw"] == 1243, f"Expected latest draw 1243, got {hist[-1]['draw']}"
    return hist


def test_g1_base_promotion_gate_unchanged():
    print("Testing G1: Original Step 3A promotion gate remains unchanged...")
    # Verify signature and all 5 criteria
    # 1. Holdout better
    assert not m._eval_promotion_gate(0.70, 0.70, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # tie -> False
    assert not m._eval_promotion_gate(0.70, 0.69, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # worse -> False
    assert m._eval_promotion_gate(0.70, 0.71, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # better -> True

    # 2. Full non-degraded
    assert not m._eval_promotion_gate(0.70, 0.80, 0.75, 0.74, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # full degraded -> False
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # full equal -> True
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.76, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # full better -> True

    # 3. Fold wins ok (requires >= 2 wins)
    assert not m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=1, mean_fold_gain=0.05, worst_fold_gain=0.0)  # 1 win -> False
    assert not m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=0, mean_fold_gain=0.05, worst_fold_gain=0.0)  # 0 wins -> False
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0)  # 2 wins -> True
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=3, mean_fold_gain=0.05, worst_fold_gain=0.0)  # 3 wins -> True

    # 4. Mean gain ok (requires > 0)
    assert not m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.0, worst_fold_gain=0.0)  # zero -> False
    assert not m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=-0.01, worst_fold_gain=0.0)  # negative -> False
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.001, worst_fold_gain=0.0)  # positive -> True

    # 5. Worst fold ok (requires >= -0.05)
    assert not m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=-0.051)  # < -0.05 -> False
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=-0.050)  # == -0.05 -> True
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75, fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=-0.040)  # > -0.05 -> True

    # Backward compatibility when fold metrics are None
    assert m._eval_promotion_gate(0.70, 0.80, 0.75, 0.75) is True
    assert m._eval_promotion_gate(0.70, 0.70, 0.75, 0.75) is False
    print("  G1 PASS")


def test_g2_base_pass_adv_1_hold(actual_history):
    print("Testing G2: Base gate PASS + raw advantage 1 -> HOLD...")
    # 1. Gate function unit test
    assert m._eval_strong_evidence_action_gate(
        base_promoted=True,
        holdout_total_match_advantage=1,
        min_advantage=2
    ) is False, "Base pass + advantage 1 must HOLD"

    # 2. End-to-end on real target 1192 (known historical promotion with advantage +1)
    h_1192 = [d for d in actual_history if d["draw"] < 1192]
    r_1192 = json.loads(m.quick_research(json.dumps(h_1192), 40))
    assert r_1192["basePromotionPassed"] is True, "Target 1192 must pass base gate"
    assert r_1192["holdoutTotalMatchAdvantage"] == 1, f"Expected adv 1, got {r_1192['holdoutTotalMatchAdvantage']}"
    assert r_1192["strongEvidencePassed"] is False, "Target 1192 strong evidence must be False"
    assert r_1192["promoted"] is False, "Target 1192 final promoted must be False (HOLD)"
    print("  G2 PASS")


def test_g3_base_pass_adv_2_promote(actual_history):
    print("Testing G3: Base gate PASS + advantage 2 -> PROMOTE...")
    # 1. Gate function unit test
    assert m._eval_strong_evidence_action_gate(
        base_promoted=True,
        holdout_total_match_advantage=2,
        min_advantage=2
    ) is True, "Base pass + advantage 2 must PROMOTE"

    # 2. End-to-end on real target 1187 (known historical promotion with advantage +2)
    h_1187 = [d for d in actual_history if d["draw"] < 1187]
    r_1187 = json.loads(m.quick_research(json.dumps(h_1187), 40))
    assert r_1187["basePromotionPassed"] is True, "Target 1187 must pass base gate"
    assert r_1187["holdoutTotalMatchAdvantage"] == 2, f"Expected adv 2, got {r_1187['holdoutTotalMatchAdvantage']}"
    assert r_1187["strongEvidencePassed"] is True, "Target 1187 strong evidence must be True"
    assert r_1187["promoted"] is True, "Target 1187 final promoted must be True (PROMOTE)"
    print("  G3 PASS")


def test_g4_base_pass_adv_gt_2_promote():
    print("Testing G4: Base gate PASS + advantage > 2 -> PROMOTE...")
    for adv in [3, 4, 5, 10]:
        assert m._eval_strong_evidence_action_gate(
            base_promoted=True,
            holdout_total_match_advantage=adv,
            min_advantage=2
        ) is True, f"Base pass + advantage {adv} must PROMOTE"
    print("  G4 PASS")


def test_g5_base_fail_adv_ge_2_hold():
    print("Testing G5: Base gate FAIL + advantage >= 2 -> HOLD...")
    for adv in [2, 3, 5, 10]:
        assert m._eval_strong_evidence_action_gate(
            base_promoted=False,
            holdout_total_match_advantage=adv,
            min_advantage=2
        ) is False, f"Base fail + advantage {adv} must HOLD"
    print("  G5 PASS")


def test_g6_preserve_original_failure_reason():
    print("Testing G6: Preserve original failure reason when base gate fails...")
    # Case 1: insufficient history
    r_short = json.loads(m.quick_research(json.dumps(make_synthetic_history(seed=1, count=60)), 40))
    assert r_short["basePromotionPassed"] is False
    assert r_short["promoted"] is False
    assert r_short["primaryReason"] == "검증 이력 부족"
    assert "검증 이력 부족" in r_short["message"]

    # Case 2: holdout tie
    reason_tie = m._determine_primary_reason(
        has_sufficient_history=True,
        hold_equal=0.70, hold_candidate=0.70,
        full_equal=0.75, full_candidate=0.75,
        fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0
    )
    assert reason_tie == "최종 홀드아웃 미개선"

    # Case 3: holdout worse
    reason_worse = m._determine_primary_reason(
        has_sufficient_history=True,
        hold_equal=0.70, hold_candidate=0.60,
        full_equal=0.75, full_candidate=0.75,
        fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0
    )
    assert reason_worse == "최종 홀드아웃 미개선"

    # Case 4: repeated validation unstable (fold wins < 2)
    reason_unstable = m._determine_primary_reason(
        has_sufficient_history=True,
        hold_equal=0.70, hold_candidate=0.80,
        full_equal=0.75, full_candidate=0.75,
        fold_wins=1, mean_fold_gain=0.05, worst_fold_gain=0.0
    )
    assert reason_unstable == "반복 검증 불안정"

    # Case 5: worst fold degraded
    reason_worst = m._determine_primary_reason(
        has_sufficient_history=True,
        hold_equal=0.70, hold_candidate=0.80,
        full_equal=0.75, full_candidate=0.75,
        fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=-0.08
    )
    assert reason_worst == "일부 구간 성능 저하 과다"

    # Case 6: full degraded
    reason_full = m._determine_primary_reason(
        has_sufficient_history=True,
        hold_equal=0.70, hold_candidate=0.80,
        full_equal=0.75, full_candidate=0.70,
        fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=0.0
    )
    assert reason_full == "전체 성능 저하"
    print("  G6 PASS")


def test_g7_base_pass_adv_1_reason(actual_history):
    print("Testing G7: Base gate PASS + advantage 1 -> reason '홀드아웃 근거 부족'...")
    h_1192 = [d for d in actual_history if d["draw"] < 1192]
    r_1192 = json.loads(m.quick_research(json.dumps(h_1192), 40))
    assert r_1192["basePromotionPassed"] is True
    assert r_1192["holdoutTotalMatchAdvantage"] == 1
    assert r_1192["primaryReason"] == "홀드아웃 근거 부족"
    assert r_1192["message"] == "검증 기준은 통과했지만 홀드아웃 누적 우위가 적용 기준(+2)에 미달하여 기본 가중치를 유지합니다."
    print("  G7 PASS")


def test_g8_exact_integer_holdout_match_totals(actual_history):
    print("Testing G8: Exact integer holdout match totals, with correct subtraction...")
    for target in [1187, 1192, 1244]:
        h = [d for d in actual_history if d["draw"] < target]
        r = json.loads(m.quick_research(json.dumps(h), 40))
        assert type(r["candidateHoldoutTotalMatches"]) is int
        assert type(r["equalHoldoutTotalMatches"]) is int
        assert type(r["holdoutTotalMatchAdvantage"]) is int
        assert type(r["strongEvidenceThreshold"]) is int
        assert r["strongEvidenceThreshold"] == 2
        assert r["holdoutTotalMatchAdvantage"] == r["candidateHoldoutTotalMatches"] - r["equalHoldoutTotalMatches"]
    print("  G8 PASS")


def test_g9_raw_advantage_corresponds_to_average_gain(actual_history):
    print("Testing G9: Raw advantage +1 and +2 correspond to average holdout gains +0.1 and +0.2 for 10 frames...")
    # Target 1192: advantage +1 -> gain +0.1
    h_1192 = [d for d in actual_history if d["draw"] < 1192]
    r_1192 = json.loads(m.quick_research(json.dumps(h_1192), 40))
    assert r_1192["holdoutDraws"] == 10
    assert r_1192["holdoutTotalMatchAdvantage"] == 1
    assert abs(r_1192["finalHoldoutGain"] - 0.1) < 1e-9
    assert abs(r_1192["holdoutGain"] - 0.1) < 1e-9

    # Target 1187: advantage +2 -> gain +0.2
    h_1187 = [d for d in actual_history if d["draw"] < 1187]
    r_1187 = json.loads(m.quick_research(json.dumps(h_1187), 40))
    assert r_1187["holdoutDraws"] == 10
    assert r_1187["holdoutTotalMatchAdvantage"] == 2
    assert abs(r_1187["finalHoldoutGain"] - 0.2) < 1e-9
    assert abs(r_1187["holdoutGain"] - 0.2) < 1e-9
    print("  G9 PASS")


def test_g10_final_holdout_mutation_invariance():
    print("Testing G10: Internal final-holdout mutation must not alter selected template, candidate weights, fold metrics, or searchCandidateCount...")
    base_hist = make_synthetic_history(seed=4321, count=150)
    r_base = json.loads(m.quick_research(json.dumps(base_hist), 40))

    # Mutate only the final holdout 10 draws
    mut_hist = [dict(d) for d in base_hist]
    rng_mut = random.Random(9999)
    for idx in range(140, 150):
        nums = sorted(rng_mut.sample(range(1, 46), 6))
        bonus = rng_mut.choice([n for n in range(1, 46) if n not in nums])
        mut_hist[idx] = {
            "draw": base_hist[idx]["draw"],
            "date": base_hist[idx]["date"],
            "numbers": nums,
            "bonus": bonus
        }

    r_mut = json.loads(m.quick_research(json.dumps(mut_hist), 40))

    # Invariants
    assert r_base["selectedCandidateWeights"] == r_mut["selectedCandidateWeights"]
    assert r_base["searchCandidateCount"] == r_mut["searchCandidateCount"]
    assert r_base["searchMethod"] == r_mut["searchMethod"]
    assert r_base["foldWins"] == r_mut["foldWins"]
    assert r_base["foldTies"] == r_mut["foldTies"]
    assert r_base["foldLosses"] == r_mut["foldLosses"]
    assert abs(r_base["meanFoldGain"] - r_mut["meanFoldGain"]) < 1e-9
    assert abs(r_base["worstFoldGain"] - r_mut["worstFoldGain"]) < 1e-9
    for i in range(3):
        assert r_base["folds"][i] == r_mut["folds"][i]
    print("  G10 PASS")


def test_g11_fold_local_leakage_protections():
    print("Testing G11: Existing fold-local leakage protections remain valid...")
    # Test 11A: Mutation from Fold 1 valStart onward leaves Fold 1 candidate weights strictly identical
    leak_base_hist = make_synthetic_history(seed=1234, count=150)
    r_leak_base = json.loads(m.quick_research(json.dumps(leak_base_hist), 40))
    f1_val_start_draw = r_leak_base["folds"][0]["valStartDraw"]
    f1_base_weights = r_leak_base["folds"][0]["candidateWeights"]

    leak_mut_hist = [dict(d) for d in leak_base_hist]
    rng_mut = random.Random(7777)
    for d in leak_mut_hist:
        if d["draw"] >= f1_val_start_draw:
            nums = sorted(rng_mut.sample(range(1, 46), 6))
            bonus = rng_mut.choice([n for n in range(1, 46) if n not in nums])
            d["numbers"] = nums
            d["bonus"] = bonus

    r_leak_mut = json.loads(m.quick_research(json.dumps(leak_mut_hist), 40))
    assert r_leak_base["folds"][0]["trainDraws"] == r_leak_mut["folds"][0]["trainDraws"]
    assert r_leak_base["folds"][0]["trainStartDraw"] == r_leak_mut["folds"][0]["trainStartDraw"]
    assert r_leak_base["folds"][0]["trainEndDraw"] == r_leak_mut["folds"][0]["trainEndDraw"]
    assert r_leak_base["folds"][0]["candidateWeights"] == r_leak_mut["folds"][0]["candidateWeights"]
    for mid, w in f1_base_weights.items():
        assert abs(w - r_leak_mut["folds"][0]["candidateWeights"][mid]) < 1e-12

    # Test 11B: Mutation strictly after fold 1 valEnd leaves fold 1 weights identical
    f1_val_end_draw = r_leak_base["folds"][0]["valEndDraw"]
    leak_post_f1_hist = [dict(d) for d in leak_base_hist]
    rng_mut_b = random.Random(8888)
    for d in leak_post_f1_hist:
        if d["draw"] > f1_val_end_draw:
            nums = sorted(rng_mut_b.sample(range(1, 46), 6))
            bonus = rng_mut_b.choice([n for n in range(1, 46) if n not in nums])
            d["numbers"] = nums
            d["bonus"] = bonus

    r_post_f1_mut = json.loads(m.quick_research(json.dumps(leak_post_f1_hist), 40))
    assert r_leak_base["folds"][0]["candidateWeights"] == r_post_f1_mut["folds"][0]["candidateWeights"]

    # Test 11C: Candidate generation function depends purely on provided frames
    f1_slice = leak_base_hist[:len(leak_base_hist) - 10]
    frames_orig = [
        {
            "draw": d["draw"],
            "scores": {mid: {n: 1.0 for n in range(1, 46)} for mid in m.MODELS},
            "actual": set(d["numbers"]),
            "matches": {mid: len(set(d["numbers"]) & set(range(1, 7))) for mid in m.MODELS}
        }
        for d in f1_slice
    ]
    frames_mut = [dict(f) for f in frames_orig]
    cands_orig = m._generate_candidate_weights(frames_orig, m.MODELS)
    cands_mut = m._generate_candidate_weights(frames_mut, m.MODELS)
    assert cands_orig == cands_mut
    print("  G11 PASS")


def test_g12_hold_preserves_default_weights_and_baseline_recommendation(actual_history):
    print("Testing G12: Final HOLD preserves default weights and exact baseline recommendation identity...")
    # On target 1192 (HOLD under Step 3G)
    h_1192 = [d for d in actual_history if d["draw"] < 1192]
    h_json = json.dumps(h_1192)
    r_1192 = json.loads(m.quick_research(h_json, 40))
    assert r_1192["promoted"] is False
    assert r_1192["weights"] == EQUAL_WEIGHTS

    # Recommendation with empty weights vs research weights vs explicit equal weights
    rec_empty = json.loads(m.recommend(h_json, "", json.dumps({"games": 5, "style": "표준"})))
    rec_res = json.loads(m.recommend(h_json, json.dumps(r_1192["weights"]), json.dumps({"games": 5, "style": "표준"})))
    rec_equal = json.loads(m.recommend(h_json, json.dumps(EQUAL_WEIGHTS), json.dumps({"games": 5, "style": "표준"})))

    assert rec_empty["recommendationId"] == rec_res["recommendationId"] == rec_equal["recommendationId"]
    assert rec_empty["core"] == rec_res["core"] == rec_equal["core"]
    assert rec_empty["candidatePool"] == rec_res["candidatePool"] == rec_equal["candidatePool"]
    assert [g["numbers"] for g in rec_empty["games"]] == [g["numbers"] for g in rec_res["games"]] == [g["numbers"] for g in rec_equal["games"]]
    print("  G12 PASS")


def test_g13_promote_returns_exact_selected_candidate_weights(actual_history):
    print("Testing G13: Final PROMOTE returns exact selected candidate weights...")
    # On target 1187 (PROMOTE under Step 3G)
    h_1187 = [d for d in actual_history if d["draw"] < 1187]
    h_json = json.dumps(h_1187)
    r_1187 = json.loads(m.quick_research(h_json, 40))
    assert r_1187["promoted"] is True
    assert r_1187["weights"] == r_1187["selectedCandidateWeights"]
    assert abs(sum(r_1187["weights"].values()) - 1.0) < 1e-9
    assert r_1187["primaryReason"] is None
    assert r_1187["message"] == "빠른 연구 보정 가중치를 적용합니다."
    print("  G13 PASS")


def test_g14_target_1244_determinism(actual_history):
    print("Testing G14: Target 1244 remains deterministic on real data...")
    # Target 1244 uses history up to draw 1243 (1243 draws)
    h_json = json.dumps(actual_history)
    assert len(actual_history) == 1243
    assert actual_history[-1]["draw"] == 1243

    r1 = json.loads(m.quick_research(h_json, 40))
    r2 = json.loads(m.quick_research(h_json, 40))

    # Strict determinism
    assert r1 == r2, "Target 1244 research must be 100% deterministic"

    # Specific Target 1244 expectations
    assert r1["promoted"] is False, "Target 1244 must HOLD"
    assert r1["basePromotionPassed"] is False, "Target 1244 base gate must be False"
    assert r1["candidateHoldoutTotalMatches"] == 6, f"Expected 6 candidate matches, got {r1['candidateHoldoutTotalMatches']}"
    assert r1["equalHoldoutTotalMatches"] == 7, f"Expected 7 equal matches, got {r1['equalHoldoutTotalMatches']}"
    assert r1["holdoutTotalMatchAdvantage"] == -1, f"Expected advantage -1, got {r1['holdoutTotalMatchAdvantage']}"
    assert r1["strongEvidenceThreshold"] == 2
    assert r1["strongEvidencePassed"] is False
    assert r1["primaryReason"] == "최종 홀드아웃 미개선"
    assert r1["weights"] == EQUAL_WEIGHTS
    assert abs(r1["finalHoldoutGain"] - (-0.1)) < 1e-9

    # Recommendation for target 1244
    rec = json.loads(m.recommend(h_json, "", json.dumps({"games": 5, "style": "표준"})))
    assert rec["targetDraw"] == 1244
    assert len(rec["games"]) == 5
    print("  G14 PASS")


def main():
    print("==================================================")
    print("Phase 2 Step 3G - Focused Regression Suite (G1-G14)")
    print("==================================================")
    actual_history = load_actual_lotto_history()
    print(f"Loaded {len(actual_history)} actual Lotto draws (latest {actual_history[-1]['draw']})")

    test_g1_base_promotion_gate_unchanged()
    test_g2_base_pass_adv_1_hold(actual_history)
    test_g3_base_pass_adv_2_promote(actual_history)
    test_g4_base_pass_adv_gt_2_promote()
    test_g5_base_fail_adv_ge_2_hold()
    test_g6_preserve_original_failure_reason()
    test_g7_base_pass_adv_1_reason(actual_history)
    test_g8_exact_integer_holdout_match_totals(actual_history)
    test_g9_raw_advantage_corresponds_to_average_gain(actual_history)
    test_g10_final_holdout_mutation_invariance()
    test_g11_fold_local_leakage_protections()
    test_g12_hold_preserves_default_weights_and_baseline_recommendation(actual_history)
    test_g13_promote_returns_exact_selected_candidate_weights(actual_history)
    test_g14_target_1244_determinism(actual_history)

    print("==================================================")
    print("ALL TESTS G1-G14 PASSED PERFECTLY!")
    print("==================================================")


if __name__ == "__main__":
    main()
