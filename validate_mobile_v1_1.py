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
