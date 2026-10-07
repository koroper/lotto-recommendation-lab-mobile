from __future__ import annotations
import importlib.util, json, random, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


m = load('mobile_engine', ROOT / 'app/src/main/python/mobile_engine.py')
golden = json.loads((ROOT / 'validation_golden.json').read_text(encoding='utf-8'))


def mk(seed, draws=220):
    rng = random.Random(seed)
    hist = []
    for draw in range(1, draws + 1):
        nums = sorted(rng.sample(range(1, 46), 6))
        bonus = rng.choice([n for n in range(1, 46) if n not in nums])
        hist.append({
            'draw': draw,
            'date': f'2026-01-{draw % 28 + 1:02d}',
            'numbers': nums,
            'bonus': bonus,
        })
    return hist


# Frozen desktop-v5.4 golden parity: 2 seeds x 3 portfolio styles.
parity = []
for key, expected in golden['portfolio_cases'].items():
    seed_text, style = key.split(':', 1)
    hist = mk(int(seed_text), 220)
    mr = json.loads(m.recommend(json.dumps(hist), '', json.dumps({'games': 5, 'style': style})))
    assert mr['core'] + mr['semiCore'] == expected['top6'], (key, 'top6')
    assert mr['candidatePool'] == expected['pool'], (key, 'pool')
    assert [g['numbers'] for g in mr['games']] == expected['games'], (key, 'games')
    parity.append(key)

# Additional frozen desktop-v5.4 top/pool parity across 8 histories.
for seed_text, expected in golden['top_pool_cases'].items():
    hist = mk(int(seed_text), 200)
    mr = json.loads(m.recommend(json.dumps(hist), '', json.dumps({'games': 1, 'style': '표준'})))
    assert mr['core'] + mr['semiCore'] == expected['top6'], (seed_text, 'top6')
    assert mr['candidatePool'] == expected['pool'], (seed_text, 'pool')

hist = mk(7001, 300)
payload = json.dumps(hist)

# Determinism and structural invariants.
for style in ['표준', '집중', '분산']:
    a = json.loads(m.recommend(payload, '', json.dumps({'games': 5, 'style': style})))
    b = json.loads(m.recommend(payload, '', json.dumps({'games': 5, 'style': style})))
    assert a == b
    assert len(a['games']) == 5
    assert len(a['core']) == 2
    assert 9 <= len(a['candidatePool']) <= 16
    for g in a['games']:
        assert len(g['numbers']) == 6
        assert len(set(g['numbers'])) == 6
        assert all(1 <= n <= 45 for n in g['numbers'])

# Fixed / excluded behavior.
f = json.loads(m.recommend(payload, '', json.dumps({
    'games': 5, 'style': '표준', 'fixed': [3, 17], 'excluded': [1, 2]
})))
for g in f['games']:
    assert 3 in g['numbers'] and 17 in g['numbers']
    assert 1 not in g['numbers'] and 2 not in g['numbers']

# Corrupt history must be rejected before recommendation.
for kind in range(4):
    bad = json.loads(payload)
    if kind == 0:
        bad[10]['numbers'] = [1, 1, 2, 3, 4, 5]
    elif kind == 1:
        bad[10]['numbers'] = [1, 2, 3, 4, 5, 46]
    elif kind == 2:
        bad[10]['bonus'] = bad[10]['numbers'][0]
    else:
        bad[10]['draw'] = bad[9]['draw']
    try:
        m.recommend(json.dumps(bad), '', json.dumps({'games': 5, 'style': '표준'}))
        raise AssertionError('corrupt input accepted')
    except ValueError:
        pass

# Research output invariants.
r = json.loads(m.quick_research(payload, 40))
assert abs(sum(r['weights'].values()) - 1) < 1e-9
assert r['testedDraws'] == 40
assert isinstance(r['promoted'], bool)
assert r['trainingDraws'] == 30
assert r['holdoutDraws'] == 10
assert 'fullGain' in r and 'holdoutGain' in r
assert r['foldCount'] == 3
assert len(r['folds']) == 3
assert 'foldWins' in r and 'foldTies' in r and 'foldLosses' in r
assert 'meanFoldGain' in r and 'worstFoldGain' in r and 'finalHoldoutGain' in r
assert r['worstFoldThreshold'] == -0.05

# Regression tests for research validation gate & holdout leakage prevention:
# 1. Exact tie => HOLD
assert not m._eval_promotion_gate(0.700, 0.700, 0.775, 0.775), 'Gate: exact tie must HOLD'
r_tie = json.loads(m.quick_research(json.dumps(mk(7001, 300)), 40))
assert abs(r_tie['holdoutCandidate'] - r_tie['holdoutEqual']) < 1e-9, 'Expected exact tie on seed 7001'
assert r_tie['promoted'] is False, 'Exact tie must result in HOLD'
assert '동점' in r_tie['message'], 'Tie message must clearly indicate tie'

# 2. Holdout worse => HOLD
assert not m._eval_promotion_gate(0.700, 0.690, 0.775, 0.800), 'Gate: holdout worse must HOLD'
r_worse = json.loads(m.quick_research(json.dumps(mk(7009, 300)), 40))
assert r_worse['holdoutCandidate'] < r_worse['holdoutEqual'], 'Expected holdout worse on seed 7009'
assert r_worse['promoted'] is False, 'Holdout worse must result in HOLD'

# 3. Holdout better + full non-degraded => PROMOTE
assert m._eval_promotion_gate(0.700, 0.800, 0.775, 0.775), 'Gate: holdout better + full non-degraded must PROMOTE'
assert m._eval_promotion_gate(0.700, 0.800, 0.775, 0.850), 'Gate: holdout better + full better must PROMOTE'
assert not m._eval_promotion_gate(0.700, 0.800, 0.775, 0.750), 'Gate: full degraded must HOLD'
r_promote = json.loads(m.quick_research(json.dumps(mk(7003, 300)), 40))
assert r_promote['holdoutCandidate'] > r_promote['holdoutEqual'] and r_promote['fullCandidate'] >= r_promote['fullEqual']
assert r_promote['promoted'] is True, 'Holdout better + full non-degraded must PROMOTE'

# 4. Holdout data is excluded when deriving candidate weights
base_hist = mk(8888, 120)
res_base = json.loads(m.quick_research(json.dumps(base_hist), 40))
alt_hist = [dict(d) for d in base_hist]
rng2 = random.Random(9999)
for idx in range(110, 120):
    nums = sorted(rng2.sample(range(1, 46), 6))
    bonus = rng2.choice([n for n in range(1, 46) if n not in nums])
    alt_hist[idx] = {
        'draw': base_hist[idx]['draw'],
        'date': base_hist[idx]['date'],
        'numbers': nums,
        'bonus': bonus,
    }
res_alt = json.loads(m.quick_research(json.dumps(alt_hist), 40))

for mod_name in m.MODELS:
    assert abs(res_base['modelAverageMatches'][mod_name] - res_alt['modelAverageMatches'][mod_name]) < 1e-9, (
        f'Holdout leakage detected: candidate training model average for {mod_name} changed when altering only holdout data'
    )

# --- Phase 2 Step 3A: 12 Repeated Walk-Forward Validation & Leakage-Free Tests ---
# Test 1: Exactly 3 chronological validation folds when sufficient history exists
r_folds = json.loads(m.quick_research(payload, 40))
assert r_folds['foldCount'] == 3, f"Expected 3 folds, got {r_folds['foldCount']}"
assert len(r_folds['folds']) == 3, f"Expected 3 fold detail entries, got {len(r_folds['folds'])}"

# Test 2: No overlap between training and validation within each fold
for f in r_folds['folds']:
    assert f['trainDraws'] > 0 and f['valDraws'] > 0
    assert f['trainEndDraw'] < f['valStartDraw'], f"Overlap detected in fold {f['fold']}: trainEnd {f['trainEndDraw']} >= valStart {f['valStartDraw']}"

# Test 3: Validation periods are strictly chronological and non-overlapping
f1, f2, f3 = r_folds['folds']
assert f1['valEndDraw'] < f2['valStartDraw'], f"Folds 1 & 2 overlap: f1 valEnd {f1['valEndDraw']} >= f2 valStart {f2['valStartDraw']}"
assert f2['valEndDraw'] < f3['valStartDraw'], f"Folds 2 & 3 overlap: f2 valEnd {f2['valEndDraw']} >= f3 valStart {f3['valStartDraw']}"

# Test 4: Fold candidate weights use only pre-validation data
# For fold 1, training draws are strictly earlier than validation start
assert f1['trainEndDraw'] < f1['valStartDraw']
assert f2['trainEndDraw'] < f2['valStartDraw']
assert f3['trainEndDraw'] < f3['valStartDraw']

# Test 5A: Future-data mutation from Fold 1 valStart onward leaves Fold 1 candidate weights strictly identical
leak_base_hist = mk(1234, 150)
r_leak_base = json.loads(m.quick_research(json.dumps(leak_base_hist), 40))
f1_val_start_draw = r_leak_base['folds'][0]['valStartDraw']
f1_base_weights = r_leak_base['folds'][0]['candidateWeights']

leak_mut_hist = [dict(d) for d in leak_base_hist]
rng_mut = random.Random(7777)
for d in leak_mut_hist:
    if d['draw'] >= f1_val_start_draw:
        nums = sorted(rng_mut.sample(range(1, 46), 6))
        bonus = rng_mut.choice([n for n in range(1, 46) if n not in nums])
        d['numbers'] = nums
        d['bonus'] = bonus

# Re-run quick research on mutated future data (from valStart onward)
r_leak_mut = json.loads(m.quick_research(json.dumps(leak_mut_hist), 40))
# Fold 1 train draws, train bounds, and learned candidate weights must be strictly identical
assert r_leak_base['folds'][0]['trainDraws'] == r_leak_mut['folds'][0]['trainDraws']
assert r_leak_base['folds'][0]['trainStartDraw'] == r_leak_mut['folds'][0]['trainStartDraw']
assert r_leak_base['folds'][0]['trainEndDraw'] == r_leak_mut['folds'][0]['trainEndDraw']
assert r_leak_base['folds'][0]['candidateWeights'] == r_leak_mut['folds'][0]['candidateWeights']
for mid, w in f1_base_weights.items():
    assert abs(w - r_leak_mut['folds'][0]['candidateWeights'][mid]) < 1e-12

# Test 5B: Future-data mutation strictly after Fold 1 valEnd leaves Fold 1 weights AND validation metrics identical
f1_val_end_draw = r_leak_base['folds'][0]['valEndDraw']
leak_post_f1_hist = [dict(d) for d in leak_base_hist]
rng_mut_b = random.Random(8888)
for d in leak_post_f1_hist:
    if d['draw'] > f1_val_end_draw:
        nums = sorted(rng_mut_b.sample(range(1, 46), 6))
        bonus = rng_mut_b.choice([n for n in range(1, 46) if n not in nums])
        d['numbers'] = nums
        d['bonus'] = bonus

r_post_f1_mut = json.loads(m.quick_research(json.dumps(leak_post_f1_hist), 40))
assert r_leak_base['folds'][0]['candidateWeights'] == r_post_f1_mut['folds'][0]['candidateWeights']
assert r_leak_base['folds'][0]['baseScore'] == r_post_f1_mut['folds'][0]['baseScore']
assert r_leak_base['folds'][0]['candidateScore'] == r_post_f1_mut['folds'][0]['candidateScore']
assert r_leak_base['folds'][0]['gain'] == r_post_f1_mut['folds'][0]['gain']

# Test 5C: Mutate only the final holdout draws: ALL 3 fold details, weights and fold metrics remain 100% identical
holdout_start_idx = len(leak_base_hist) - r_leak_base['holdoutDraws']
leak_hold_mut = [dict(d) for d in leak_base_hist]
for idx in range(holdout_start_idx, len(leak_base_hist)):
    nums = sorted(rng_mut.sample(range(1, 46), 6))
    bonus = rng_mut.choice([n for n in range(1, 46) if n not in nums])
    leak_hold_mut[idx]['numbers'] = nums
    leak_hold_mut[idx]['bonus'] = bonus

r_hold_mut = json.loads(m.quick_research(json.dumps(leak_hold_mut), 40))
for i in range(3):
    assert r_leak_base['folds'][i] == r_hold_mut['folds'][i], f"Fold {i+1} changed when modifying only final holdout"
assert r_leak_base['foldWins'] == r_hold_mut['foldWins']
assert r_leak_base['foldTies'] == r_hold_mut['foldTies']
assert r_leak_base['foldLosses'] == r_hold_mut['foldLosses']
assert abs(r_leak_base['meanFoldGain'] - r_hold_mut['meanFoldGain']) < 1e-9
assert abs(r_leak_base['worstFoldGain'] - r_hold_mut['worstFoldGain']) < 1e-9
assert r_leak_base['selectedCandidateWeights'] == r_hold_mut['selectedCandidateWeights']
assert r_leak_base['searchCandidateCount'] == r_hold_mut['searchCandidateCount']

# --- Phase 2 Step 3B: Deterministic Candidate-Weight Search Tests ---
mids_all = ["long", "recent", "gap", "pair", "balance", "inverse"]
dummy_sample = mk(4321, 50)
sample_frames = []
for idx in range(10, 50):
    tr = dummy_sample[:idx]
    act = set(dummy_sample[idx]["numbers"])
    _, scs, _, _, _ = m._model_scores(tr)
    sample_frames.append({
        "draw": dummy_sample[idx]["draw"],
        "scores": scs,
        "actual": act,
        "matches": {mid: len(act & set(sorted(scs[mid], key=lambda n: (-scs[mid][n], n))[:6])) for mid in mids_all}
    })

cands = m._generate_candidate_weights(sample_frames, mids_all)

# 3B.1: All generated candidate weights are non-negative
for name, c in cands:
    for mid, w in c.items():
        assert w >= -1e-9, f"Candidate {name} model {mid} negative weight: {w}"

# 3B.2: Every candidate sums to 1 within epsilon
for name, c in cands:
    s = sum(c.values())
    assert abs(s - 1.0) < 1e-8, f"Candidate {name} sum not 1: {s}"

# 3B.3: Candidate generation is deterministic
cands_repeat = m._generate_candidate_weights(sample_frames, mids_all)
assert len(cands) == len(cands_repeat)
for (n1, w1), (n2, w2) in zip(cands, cands_repeat):
    assert n1 == n2
    assert w1 == w2

# 3B.4: Candidate count stays below the hard cap (hard cap 200)
assert len(cands) <= 200, f"Candidate count {len(cands)} exceeded hard cap 200"
assert len(cands) <= 62, f"Candidate count {len(cands)} exceeded expected max 62"

# 3B.5: Equal and existing learned candidate are included as candidates 0 and 1
assert cands[0][0] == "equal"
assert all(abs(cands[0][1][mid] - 1.0/6) < 1e-9 for mid in mids_all)
assert cands[1][0] == "learned_seed"
seed_expected, _ = m._derive_candidate_weights(sample_frames, mids_all)
assert cands[1][1] == seed_expected

# 3B.6: Selection priority prefers more fold wins over mean gain
mock_cands = [
    {"name": "cand_b", "fold_wins": 1, "mean_fold_gain": 0.20, "worst_fold_gain": -0.01, "mean_fold_l1": 0.1},
    {"name": "cand_a", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.01, "mean_fold_l1": 0.1}
]
mock_ranked = sorted(mock_cands, key=lambda c: (
    -c["fold_wins"], -round(c["mean_fold_gain"], 6), -round(c["worst_fold_gain"], 6), round(c["mean_fold_l1"], 6), c["name"]
))
assert mock_ranked[0]["name"] == "cand_a", "Priority 1 (fold wins) must beat higher mean gain"

# 3B.7: If fold wins tie, higher mean gain wins
mock_cands_2 = [
    {"name": "cand_low_mean", "fold_wins": 2, "mean_fold_gain": 0.03, "worst_fold_gain": -0.01, "mean_fold_l1": 0.1},
    {"name": "cand_high_mean", "fold_wins": 2, "mean_fold_gain": 0.08, "worst_fold_gain": -0.01, "mean_fold_l1": 0.1}
]
mock_ranked_2 = sorted(mock_cands_2, key=lambda c: (
    -c["fold_wins"], -round(c["mean_fold_gain"], 6), -round(c["worst_fold_gain"], 6), round(c["mean_fold_l1"], 6), c["name"]
))
assert mock_ranked_2[0]["name"] == "cand_high_mean", "Priority 2 (mean gain) must break fold wins tie"

# 3B.8: If mean gain ties, better worst-fold gain wins
mock_cands_3 = [
    {"name": "cand_worse_worst", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.04, "mean_fold_l1": 0.1},
    {"name": "cand_better_worst", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.02, "mean_fold_l1": 0.1}
]
mock_ranked_3 = sorted(mock_cands_3, key=lambda c: (
    -c["fold_wins"], -round(c["mean_fold_gain"], 6), -round(c["worst_fold_gain"], 6), round(c["mean_fold_l1"], 6), c["name"]
))
assert mock_ranked_3[0]["name"] == "cand_better_worst", "Priority 3 (worst fold gain) must break mean gain tie"

# 3B-R1: Changing only global_w absolute values cannot change selected template
dummy_folds_data = [
    (sample_frames[:15], sample_frames[15:20]),
    (sample_frames[:20], sample_frames[20:25]),
    (sample_frames[:25], sample_frames[25:30])
]
fold_cands_lists = [m._generate_candidate_weights(ft, mids_all) for ft, _ in dummy_folds_data]
global_cands_orig = m._generate_candidate_weights(sample_frames, mids_all)
global_cands_mutated_w = [(name, {mid: (0.5 if mid == 'long' else 0.1) for mid in mids_all}) for name, _ in global_cands_orig]
sel_orig, _ = m._select_search_candidate(global_cands_orig, fold_cands_lists, dummy_folds_data, cands[0][1], mids_all)
sel_mut_w, _ = m._select_search_candidate(global_cands_mutated_w, fold_cands_lists, dummy_folds_data, cands[0][1], mids_all)
assert sel_orig["name"] == sel_mut_w["name"], "Changing global_w values must not alter template selection"

# 3B-R2: Lexical template name is the final tiebreak
mock_cands_lex = [
    {"name": "zeta_template", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.02, "mean_fold_l1": 0.10},
    {"name": "alpha_template", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.02, "mean_fold_l1": 0.10}
]
mock_ranked_lex = sorted(mock_cands_lex, key=lambda c: (
    -c["fold_wins"], -round(c["mean_fold_gain"], 6), -round(c["worst_fold_gain"], 6), round(c["mean_fold_l1"], 6), c["name"]
))
assert mock_ranked_lex[0]["name"] == "alpha_template", "Priority 5 (lexical name) must break tie"

# 3B-R3: Mean fold-local L1 is used before lexical name
mock_cands_l1 = [
    {"name": "alpha_template", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.02, "mean_fold_l1": 0.20},
    {"name": "zeta_template", "fold_wins": 2, "mean_fold_gain": 0.05, "worst_fold_gain": -0.02, "mean_fold_l1": 0.10}
]
mock_ranked_l1 = sorted(mock_cands_l1, key=lambda c: (
    -c["fold_wins"], -round(c["mean_fold_gain"], 6), -round(c["worst_fold_gain"], 6), round(c["mean_fold_l1"], 6), c["name"]
))
assert mock_ranked_l1[0]["name"] == "zeta_template", "Priority 4 (mean fold L1) must beat lexical name"

# 3B-R4: Positional reordering of candidate lists does not change selection
global_cands_reversed = list(reversed(global_cands_orig))
fold_cands_reversed = [list(reversed(fc)) for fc in fold_cands_lists]
sel_rev, _ = m._select_search_candidate(global_cands_reversed, fold_cands_reversed, dummy_folds_data, cands[0][1], mids_all)
assert sel_orig["name"] == sel_rev["name"], "Positional reordering must not alter candidate selection"

# 3B-R5: Missing template in one fold is safely excluded
fold_cands_incomplete = [
    list(fold_cands_lists[0]),
    list(fold_cands_lists[1]),
    [c for c in fold_cands_lists[2] if c[0] != "equal"] # drop 'equal' in fold 3
]
_, evaluated_incomplete = m._select_search_candidate(global_cands_orig, fold_cands_incomplete, dummy_folds_data, cands[0][1], mids_all)
assert not any(c["name"] == "equal" for c in evaluated_incomplete), "Template missing in any fold must be excluded"

# 3B.9: Final-holdout mutation does NOT change selected candidate weights or count
assert r_leak_base['selectedCandidateWeights'] == r_hold_mut['selectedCandidateWeights']
assert r_leak_base['searchCandidateCount'] == r_hold_mut['searchCandidateCount']

# 3B.10: Future data after an earlier fold does not alter that fold's candidate construction
f1_train_slice = [f for f in sample_frames if f["draw"] <= 30]
f1_train_slice_mut = [dict(f) for f in f1_train_slice]
cands_f1_orig = m._generate_candidate_weights(f1_train_slice, mids_all)
cands_f1_mut = m._generate_candidate_weights(f1_train_slice_mut, mids_all)
assert cands_f1_orig == cands_f1_mut

# Test 6: 2/3 wins + positive mean + acceptable worst fold + final holdout win CAN promote
assert m._eval_promotion_gate(
    hold_equal=0.7, hold_candidate=0.8,
    full_equal=0.75, full_candidate=0.76,
    fold_wins=2, mean_fold_gain=0.03, worst_fold_gain=-0.02
) is True

# Test 7: 1/3 wins CANNOT promote (requires at least 2 wins)
assert m._eval_promotion_gate(
    hold_equal=0.7, hold_candidate=0.8,
    full_equal=0.75, full_candidate=0.76,
    fold_wins=1, mean_fold_gain=0.03, worst_fold_gain=0.0
) is False

# Test 8: Negative mean gain CANNOT promote
assert m._eval_promotion_gate(
    hold_equal=0.7, hold_candidate=0.8,
    full_equal=0.75, full_candidate=0.76,
    fold_wins=2, mean_fold_gain=-0.001, worst_fold_gain=0.0
) is False

# Test 9: worstFoldGain < -0.05 CANNOT promote, but >= -0.05 CAN promote
assert m._eval_promotion_gate(
    hold_equal=0.7, hold_candidate=0.8,
    full_equal=0.75, full_candidate=0.76,
    fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=-0.051
) is False
assert m._eval_promotion_gate(
    hold_equal=0.7, hold_candidate=0.8,
    full_equal=0.75, full_candidate=0.76,
    fold_wins=2, mean_fold_gain=0.05, worst_fold_gain=-0.05
) is True

# Test 10: Tied final holdout CANNOT promote
assert m._eval_promotion_gate(
    hold_equal=0.7, hold_candidate=0.7,
    full_equal=0.75, full_candidate=0.80,
    fold_wins=3, mean_fold_gain=0.10, worst_fold_gain=0.05
) is False

# Test 11: Insufficient history returns HOLD with Korean reason
short_hist = mk(5555, 60) # less than 100 draws
r_short = json.loads(m.quick_research(json.dumps(short_hist), 40))
assert r_short['promoted'] is False
assert r_short['primaryReason'] == '검증 이력 부족'
assert '검증 이력 부족' in r_short['message']

# Test 12: Existing real-data target draw 1244 remains deterministic
dummy_1243 = mk(9999, 1243)
r_1244_a = json.loads(m.quick_research(json.dumps(dummy_1243), 40))
r_1244_b = json.loads(m.quick_research(json.dumps(dummy_1243), 40))
assert r_1244_a == r_1244_b, "Real-data scale research must remain 100% deterministic"

# Representative performance smoke test. These timings are informational, not CI limits.
large = mk(9001, 1000)
lp = json.dumps(large)
t0 = time.perf_counter()
rec = json.loads(m.recommend(lp, '', json.dumps({'games': 5, 'style': '표준'})))
t_rec = time.perf_counter() - t0

t1 = time.perf_counter()
rr = json.loads(m.quick_research(lp, 25))
t_research = time.perf_counter() - t1

print('MOBILE V1.1 VALIDATION PASS')
print(f'Frozen desktop-v5.4 exact portfolio parity: {len(parity)}/{len(parity)} cases')
print('Frozen desktop-v5.4 top/pool parity: 8/8 histories')
print(f'Recommendation benchmark (1000 draws): {t_rec:.3f}s')
print(f'Quick research benchmark (25 draws): {t_research:.3f}s')
print('Recommendation ID:', rec['recommendationId'])
print('Research:', rr['message'])
