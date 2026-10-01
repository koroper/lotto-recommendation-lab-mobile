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
