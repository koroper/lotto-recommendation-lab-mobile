from __future__ import annotations
import importlib.util, json, random, time, statistics, sys
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod
m=load('mobile_engine',ROOT/'app/src/main/python/mobile_engine.py')
d=load('desktop_core',ROOT/'validation_reference/lotto_core_v5_4.py')

def mk(seed,draws=220):
 rng=random.Random(seed); hist=[]; rows=[]
 for draw in range(1,draws+1):
  nums=sorted(rng.sample(range(1,46),6)); bonus=rng.choice([n for n in range(1,46) if n not in nums]); date=f'2026-01-{draw%28+1:02d}'
  hist.append({'draw':draw,'date':date,'numbers':nums,'bonus':bonus}); rows.append({'draw':draw,'date':date,**{f'n{i+1}':nums[i] for i in range(6)},'bonus':bonus})
 return hist,pd.DataFrame(rows)

# Exact parity: 2 seeds x 3 portfolio styles.
parity=[]
for seed in [5101,5102]:
 hist,df=mk(seed,220); eq={k:1/6 for k in d.모델목록}
 for style in ['표준','집중','분산']:
  dr=d.최종추천(df,pool_size=None,games=5,style=style,weights=eq,research_state=None)
  mr=json.loads(m.recommend(json.dumps(hist),'',json.dumps({'games':5,'style':style})))
  desktop_top=dr['최종번호'].head(6)['번호'].astype(int).tolist(); mobile_top=mr['core']+mr['semiCore']
  desktop_pool=list(map(int,dr['후보풀'])); mobile_pool=list(map(int,mr['candidatePool']))
  desktop_games=[tuple(map(int,x)) for x in dr['추천']['조합'].tolist()]; mobile_games=[tuple(map(int,g['numbers'])) for g in mr['games']]
  assert desktop_top==mobile_top,(seed,style,'top',desktop_top,mobile_top)
  assert desktop_pool==mobile_pool,(seed,style,'pool',desktop_pool,mobile_pool)
  assert desktop_games==mobile_games,(seed,style,'games',desktop_games,mobile_games)
  parity.append((seed,style))

# Additional top/pool parity across 8 histories, cheaper than beam portfolio.
for seed in range(5200,5208):
 hist,df=mk(seed,200); eq={k:1/6 for k in d.모델목록}
 models=d.모델별번호점수(df); final=d.앙상블번호점수(models,eq); pool,meta=d.후보풀(final,None)
 mr=json.loads(m.recommend(json.dumps(hist),'',json.dumps({'games':1,'style':'표준'})))
 assert final.head(6)['번호'].astype(int).tolist()==mr['core']+mr['semiCore']
 assert list(map(int,pool))==list(map(int,mr['candidatePool']))

hist,_=mk(7001,300); payload=json.dumps(hist)
# Determinism and structure.
for style in ['표준','집중','분산']:
 a=json.loads(m.recommend(payload,'',json.dumps({'games':5,'style':style}))); b=json.loads(m.recommend(payload,'',json.dumps({'games':5,'style':style})))
 assert a==b
 assert len(a['games'])==5 and len(a['core'])==2 and 9<=len(a['candidatePool'])<=16
 for g in a['games']:
  assert len(g['numbers'])==6 and len(set(g['numbers']))==6 and all(1<=n<=45 for n in g['numbers'])
# Fixed/excluded.
f=json.loads(m.recommend(payload,'',json.dumps({'games':5,'style':'표준','fixed':[3,17],'excluded':[1,2]})))
for g in f['games']:
 assert 3 in g['numbers'] and 17 in g['numbers'] and 1 not in g['numbers'] and 2 not in g['numbers']
# Corruption rejection.
for kind in range(4):
 bad=json.loads(payload)
 if kind==0: bad[10]['numbers']=[1,1,2,3,4,5]
 elif kind==1: bad[10]['numbers']=[1,2,3,4,5,46]
 elif kind==2: bad[10]['bonus']=bad[10]['numbers'][0]
 else: bad[10]['draw']=bad[9]['draw']
 try: m.recommend(json.dumps(bad),'',json.dumps({'games':5,'style':'표준'})); raise AssertionError('corrupt accepted')
 except ValueError: pass
# Research.
r=json.loads(m.quick_research(payload,40)); assert abs(sum(r['weights'].values())-1)<1e-9 and r['testedDraws']==40
# Performance representative history: recommendation 1000 draws, research 25 to cap CI time.
large,_=mk(9001,1000); lp=json.dumps(large)
t0=time.perf_counter(); rec=json.loads(m.recommend(lp,'',json.dumps({'games':5,'style':'표준'}))); t_rec=time.perf_counter()-t0
t1=time.perf_counter(); rr=json.loads(m.quick_research(lp,25)); t_research=time.perf_counter()-t1
print('MOBILE V1.1 VALIDATION PASS')
print(f'Exact desktop parity: {len(parity)}/{len(parity)} cases')
print('Additional top/pool parity: 8/8 histories')
print(f'Recommendation benchmark (1000 draws): {t_rec:.3f}s')
print(f'Quick research benchmark (25 draws): {t_research:.3f}s')
print('Recommendation ID:',rec['recommendationId'])
print('Research:',rr['message'])
