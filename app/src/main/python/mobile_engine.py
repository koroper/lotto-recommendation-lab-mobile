from __future__ import annotations

import hashlib
import itertools
import json
import math
import statistics


MODELS = {
    "long": "장기 빈도형",
    "recent": "최근 추세형",
    "gap": "미출현 간격형",
    "pair": "동반 출현형",
    "balance": "균형 혼합형",
    "inverse": "역추세 실험형",
}


def _norm(d):
    vals = list(d.values())
    lo, hi = min(vals), max(vals)
    if math.isclose(lo, hi):
        return {k: 50.0 for k in d}
    return {k: (v - lo) / (hi - lo) * 100.0 for k, v in d.items()}


def _variance(values):
    if not values:
        return 0.0
    m = sum(values) / len(values)
    return sum((x - m) ** 2 for x in values) / len(values)


def _chunks(seq, parts):
    n = len(seq)
    if n == 0:
        return []
    parts = max(1, min(parts, n))
    out = []
    for i in range(parts):
        a = round(i * n / parts)
        b = round((i + 1) * n / parts)
        if b > a:
            out.append(seq[a:b])
    return out


def _pearson(a, b):
    n = len(a)
    if n == 0:
        return 0.0
    ma, mb = sum(a) / n, sum(b) / n
    da = [x - ma for x in a]
    db = [x - mb for x in b]
    denom = math.sqrt(sum(x*x for x in da) * sum(y*y for y in db))
    return sum(x*y for x, y in zip(da, db)) / denom if denom else 0.0


def _parse_history(history_json):
    history = json.loads(history_json)
    if not isinstance(history, list):
        raise ValueError("당첨 데이터 형식이 올바르지 않습니다.")
    rows = []
    seen_draws = set()
    for r in history:
        draw = int(r["draw"])
        if draw in seen_draws:
            raise ValueError(f"중복 회차가 있습니다: {draw}")
        seen_draws.add(draw)
        nums = sorted(int(x) for x in r["numbers"])
        bonus = int(r.get("bonus", 0))
        if len(nums) != 6 or len(set(nums)) != 6:
            raise ValueError(f"{draw}회 당첨번호가 서로 다른 6개가 아닙니다.")
        if any(n < 1 or n > 45 for n in nums):
            raise ValueError(f"{draw}회 당첨번호가 1~45 범위를 벗어났습니다.")
        if bonus and (bonus < 1 or bonus > 45):
            raise ValueError(f"{draw}회 보너스 번호가 1~45 범위를 벗어났습니다.")
        if bonus and bonus in nums:
            raise ValueError(f"{draw}회 보너스 번호가 당첨번호와 중복됩니다.")
        rows.append({"draw":draw,"date":str(r.get("date","")),"numbers":nums,"bonus":bonus})
    rows.sort(key=lambda x:x["draw"])
    if len(rows)<60:
        raise ValueError("최소 60회 이상의 데이터가 필요합니다.")
    return rows


def _base_metrics(history):
    n_draws = len(history)
    occ = {n: [0] * n_draws for n in range(1, 46)}
    pair = {(a, b): 0 for a in range(1, 46) for b in range(a + 1, 46)}
    single = {n: 0 for n in range(1, 46)}

    for i, row in enumerate(history):
        nums = row["numbers"]
        for n in nums:
            occ[n][i] = 1
            single[n] += 1
        for a, b in itertools.combinations(nums, 2):
            pair[(a, b)] += 1

    raw = {}
    central_raw = {}
    for num in range(1, 46):
        seq = occ[num]
        hits = [i for i, v in enumerate(seq) if v]
        current_gap = n_draws - 1 - hits[-1] if hits else n_draws
        gaps = [b - a for a, b in zip(hits, hits[1:])]
        avg_gap = (sum(gaps) / len(gaps)) if gaps else float(n_draws)
        window = seq[-min(120, n_draws):]
        chunk_rates = [sum(c) / len(c) for c in _chunks(window, 12)]
        stability = -_variance(chunk_rates)

        long_freq = sum(seq) / n_draws
        r10 = sum(seq[-min(10, n_draws):]) / min(10, n_draws)
        r20 = sum(seq[-min(20, n_draws):]) / min(20, n_draws)
        r50 = sum(seq[-min(50, n_draws):]) / min(50, n_draws)
        gap_ratio = current_gap / max(avg_gap, 1.0)
        trend = r20 - long_freq

        lifts = []
        for other in range(1, 46):
            if other == num:
                continue
            a, b = sorted((num, other))
            observed = pair[(a, b)] + 1.0
            expected = ((single[num] + 1.0) * (single[other] + 1.0)) / (n_draws + 45.0)
            lifts.append(math.log(observed / max(expected, 1e-12)))
        central_raw[num] = sum(lifts) / len(lifts)

        raw[num] = {
            "long_freq": long_freq,
            "r10": r10,
            "r20": r20,
            "r50": r50,
            "current_gap": current_gap,
            "avg_gap": avg_gap,
            "gap_ratio": gap_ratio,
            "trend": trend,
            "stability": stability,
        }

    component_maps = {
        "long": _norm({n: raw[n]["long_freq"] for n in raw}),
        "r10": _norm({n: raw[n]["r10"] for n in raw}),
        "r20": _norm({n: raw[n]["r20"] for n in raw}),
        "r50": _norm({n: raw[n]["r50"] for n in raw}),
        "gap": _norm({n: raw[n]["gap_ratio"] for n in raw}),
        "trend": _norm({n: raw[n]["trend"] for n in raw}),
        "stability": _norm({n: raw[n]["stability"] for n in raw}),
        "pair": _norm(central_raw),
    }
    return raw, component_maps, pair, single


def _model_scores(history):
    raw, c, pair, single = _base_metrics(history)
    scores = {m: {} for m in MODELS}

    for n in range(1, 46):
        scores["long"][n] = c["long"][n] * .75 + c["stability"][n] * .25
        scores["recent"][n] = c["r20"][n] * .45 + c["r50"][n] * .25 + c["trend"][n] * .30
        scores["gap"][n] = c["gap"][n] * .70 + c["long"][n] * .15 + c["stability"][n] * .15
        scores["pair"][n] = c["pair"][n] * .65 + c["long"][n] * .20 + c["r50"][n] * .15
        scores["balance"][n] = (
            c["long"][n] * .22 + c["r20"][n] * .18 + c["r50"][n] * .14 +
            c["gap"][n] * .14 + c["trend"][n] * .12 + c["stability"][n] * .10 +
            c["pair"][n] * .10
        )
        scores["inverse"][n] = (100 - c["r20"][n]) * .45 + c["gap"][n] * .35 + c["stability"][n] * .20

    scores = {m: _norm(v) for m, v in scores.items()}
    ranks = {}
    for m, d in scores.items():
        ordered = sorted(d, key=lambda n: (-d[n], n))
        ranks[m] = {n: i + 1 for i, n in enumerate(ordered)}
    return raw, scores, ranks, pair, single


def _ensemble(scores, ranks, weights):
    mids = list(MODELS)
    total = sum(max(0.0, float(weights.get(m, 0.0))) for m in mids)
    if total <= 0:
        weights = {m: 1 / len(mids) for m in mids}
    else:
        weights = {m: max(0.0, float(weights.get(m, 0.0))) / total for m in mids}

    final = {
        n: sum(scores[m][n] * weights[m] for m in mids)
        for n in range(1, 46)
    }
    ordered = sorted(final, key=lambda n: (-final[n], n))
    final_rank = {n: i + 1 for i, n in enumerate(ordered)}
    top10_count = {n: sum(1 for m in mids if ranks[m][n] <= 10) for n in range(1, 46)}
    return final, final_rank, top10_count, weights


def _auto_pool(final, min_size=9, max_size=16, default=12):
    ordered = sorted(final, key=lambda n: (-final[n], n))
    vals = [final[n] for n in ordered]
    gaps = [vals[i] - vals[i + 1] for i in range(len(vals) - 1)]
    positive = [g for g in gaps[:max_size + 4] if g > 1e-9]
    median = statistics.median(positive) if positive else 1.0
    median = max(median, .15)
    best = None
    for size in range(min_size, max_size + 1):
        gap = gaps[size - 1]
        strength = gap / median
        objective = strength - .07 * abs(size - default)
        item = (objective, strength, gap, size)
        if best is None or item > best:
            best = item
    _, strength, gap, chosen = best
    if strength < 1.20:
        chosen = default
    return ordered[:chosen], chosen


def _pattern_stats(history):
    odd_counts, sums, consec_counts, band_counts = {}, [], {}, {}
    for row in history:
        nums = row["numbers"]
        odd = sum(n % 2 for n in nums)
        odd_counts[odd] = odd_counts.get(odd, 0) + 1
        sums.append(sum(nums))
        consec = sum(1 for a, b in zip(nums, nums[1:]) if b == a + 1)
        consec_counts[consec] = consec_counts.get(consec, 0) + 1
        bands = (
            sum(1 <= n <= 10 for n in nums),
            sum(11 <= n <= 20 for n in nums),
            sum(21 <= n <= 30 for n in nums),
            sum(31 <= n <= 40 for n in nums),
            sum(41 <= n <= 45 for n in nums),
        )
        band_counts[bands] = band_counts.get(bands, 0) + 1
    total = len(history)
    return {
        "odd": {k: v / total for k, v in odd_counts.items()},
        "consec": {k: v / total for k, v in consec_counts.items()},
        "bands": {k: v / total for k, v in band_counts.items()},
        "sum_mean": sum(sums) / len(sums),
        "sum_sd": statistics.pstdev(sums) or 1.0,
    }


def _combination_scores(history, pool, final_scores, pair_counts, single_counts):
    patterns = _pattern_stats(history)
    n_draws = len(history)
    rows = []

    for combo in itertools.combinations(pool, 6):
        avg_num = sum(final_scores[n] for n in combo) / 6
        affinities = []
        for a, b in itertools.combinations(combo, 2):
            x, y = sorted((a, b))
            observed = pair_counts[(x, y)] + 1.0
            expected = ((single_counts[a] + 1.0) * (single_counts[b] + 1.0)) / (n_draws + 45.0)
            affinities.append(math.log(observed / max(expected, 1e-12)))

        odd = sum(n % 2 for n in combo)
        total_sum = sum(combo)
        z = abs((total_sum - patterns["sum_mean"]) / patterns["sum_sd"])
        consec = sum(1 for a, b in zip(combo, combo[1:]) if b == a + 1)
        bands = (
            sum(1 <= n <= 10 for n in combo),
            sum(11 <= n <= 20 for n in combo),
            sum(21 <= n <= 30 for n in combo),
            sum(31 <= n <= 40 for n in combo),
            sum(41 <= n <= 45 for n in combo),
        )
        rows.append({
            "numbers": combo,
            "num": avg_num,
            "pair": sum(affinities) / len(affinities),
            "odd": patterns["odd"].get(odd, 0.0),
            "sum": math.exp(-0.5 * z * z),
            "consec": patterns["consec"].get(consec, 0.0),
            "bands": patterns["bands"].get(bands, 0.0),
        })

    for key in ["pair", "odd", "sum", "consec", "bands"]:
        norm = _norm({i: row[key] for i, row in enumerate(rows)})
        for i, row in enumerate(rows):
            row[key + "_score"] = norm[i]

    for row in rows:
        structure = (
            row["odd_score"] * .25 + row["sum_score"] * .30 +
            row["consec_score"] * .15 + row["bands_score"] * .30
        )
        row["score"] = row["num"] * .62 + row["pair_score"] * .10 + structure * .28

    rows.sort(key=lambda r: -r["score"])
    total = len(rows)
    for i, row in enumerate(rows):
        row["rank"] = i + 1
        row["total"] = total
        row["percentile"] = (i + 1) / total * 100.0
    return rows


def _portfolio_objective(rows, style="표준", core_numbers=None):
    if not rows: return -1e18
    combos=[tuple(map(int,r["numbers"])) for r in rows]
    scores=[float(r["score"]) for r in rows]
    core_numbers=set(int(x) for x in (core_numbers or []))
    number_counts={}; pair_counts={}; triple_counts={}
    for combo in combos:
        for n in combo: number_counts[n]=number_counts.get(n,0)+1
        for p in itertools.combinations(combo,2): pair_counts[p]=pair_counts.get(p,0)+1
        for t in itertools.combinations(combo,3): triple_counts[t]=triple_counts.get(t,0)+1
    unique_numbers=len(number_counts)
    repeated_pairs=sum(max(0,c-1) for c in pair_counts.values())
    repeated_triples=sum(max(0,c-1) for c in triple_counts.values())
    concentration=sum(max(0,c-3)**2 for c in number_counts.values())
    core_repeat=sum(number_counts.get(n,0) for n in core_numbers)
    avg_score=sum(scores)/len(scores)
    if style=="집중": w=dict(score=1.15,unique=.45,pair=.28,triple=.70,concentration=.15,core=1.10)
    elif style=="분산": w=dict(score=.92,unique=1.65,pair=1.30,triple=2.80,concentration=1.30,core=.30)
    else: w=dict(score=1.00,unique=1.00,pair=.75,triple=1.60,concentration=.70,core=.65)
    return avg_score*w["score"]+unique_numbers*w["unique"]-repeated_pairs*w["pair"]-repeated_triples*w["triple"]-concentration*w["concentration"]+core_repeat*w["core"]


def _portfolio(combos, games, style, core_numbers=None, candidate_limit=None, beam_width=None):
    if not combos: return []
    games=max(1,min(int(games),10)); total=len(combos)
    if candidate_limit is None: candidate_limit=180 if style=="분산" else 150
    if beam_width is None: beam_width=320 if games<=5 else 220
    quality_cap=max(games*6,int(math.ceil(total*.35)))
    effective_limit=max(games,min(int(candidate_limit),quality_cap,total))
    top_score=float(combos[0]["score"]); all_scores=[float(r["score"]) for r in combos]
    score_sd=statistics.stdev(all_scores) if len(all_scores)>=2 else 1.0; score_sd=max(score_sd,1.0)
    score_floor=top_score-max(8.0,.85*score_sd)
    cand=combos[:effective_limit]; filtered=[r for r in cand if float(r["score"])>=score_floor]
    if len(filtered)>=games: cand=filtered
    n=len(cand); games=min(games,n)
    beam=[]; max_first=max(1,n-games+1)
    for i in range(max_first): beam.append((_portfolio_objective([cand[i]],style,core_numbers),(i,)))
    beam=sorted(beam,key=lambda x:x[0],reverse=True)[:beam_width]
    for depth in range(1,games):
        expanded=[]; need_after=games-(depth+1); seen=set()
        for _,inds in beam:
            for j in range(inds[-1]+1,n-need_after):
                new_inds=inds+(j,)
                if new_inds in seen: continue
                seen.add(new_inds); rows=[cand[k] for k in new_inds]
                expanded.append((_portfolio_objective(rows,style,core_numbers),new_inds))
        if not expanded: break
        beam=sorted(expanded,key=lambda x:x[0],reverse=True)[:beam_width]
    if not beam: return []
    _,best_inds=max(beam,key=lambda x:x[0]); out=[cand[i] for i in best_inds]; out.sort(key=lambda r:-float(r["score"])); return out


def _confidence(final, ranks, top10_count, research_used):
    ordered = sorted(final, key=lambda n: (-final[n], n))
    top6 = ordered[:6]
    mids = list(MODELS)
    agreement = sum(top10_count[n] for n in top6) / (6 * len(mids)) * 100.0

    top_sets = {
        m: {n for n in range(1, 46) if ranks[m][n] <= 10}
        for m in mids
    }
    jac = []
    corr = []
    for i in range(len(mids)):
        for j in range(i + 1, len(mids)):
            a, b = top_sets[mids[i]], top_sets[mids[j]]
            jac.append(len(a & b) / len(a | b))
            seq_a = [ranks[mids[i]][n] for n in range(1, 46)]
            seq_b = [ranks[mids[j]][n] for n in range(1, 46)]
            corr.append(_pearson(seq_a, seq_b))
    overlap = (sum(jac) / len(jac) * 100.0) if jac else 50.0
    avg_corr = sum(corr) / len(corr) if corr else 0.0
    spearman_score = max(0.0, min(100.0, 35.0 + 65.0 * max(avg_corr, -0.54)))
    rank_consistency = overlap * .42 + spearman_score * .33 + agreement * .25

    vals = [final[n] for n in ordered]
    top_mean = sum(vals[:6]) / 6
    next_mean = sum(vals[6:12]) / 6
    sd = statistics.stdev(vals) if len(vals) >= 2 else 1.0
    sd = sd or 1.0
    z = (top_mean - next_mean) / sd
    separation = max(0.0, min(100.0, 50.0 + 38.0 * math.tanh(z)))
    research_score = 60.0 if research_used else 50.0
    score = agreement * .30 + rank_consistency * .30 + separation * .22 + research_score * .18

    if score >= 75:
        label = "높음"
    elif score >= 60:
        label = "양호"
    elif score >= 45:
        label = "보통"
    else:
        label = "낮음"
    return {
        "score": round(score, 1),
        "label": label,
        "agreement": round(agreement, 1),
        "rankConsistency": round(rank_consistency, 1),
        "separation": round(separation, 1),
    }


def recommend(history_json, weights_json="", config_json=""):
    history = _parse_history(history_json)
    config = json.loads(config_json) if config_json else {}
    fixed = sorted(set(int(x) for x in config.get("fixed", [])))
    excluded = set(int(x) for x in config.get("excluded", []))
    games = int(config.get("games", 5))
    style = str(config.get("style", "표준"))

    weights = json.loads(weights_json) if weights_json else {m: 1 / len(MODELS) for m in MODELS}
    raw, model_scores, ranks, pair, single = _model_scores(history)
    final, final_rank, top10_count, normalized_weights = _ensemble(model_scores, ranks, weights)

    auto_pool, auto_size = _auto_pool(final)
    pool_size = config.get("poolSize")
    if pool_size is None:
        base_pool = auto_pool
    else:
        size = max(6, min(18, int(pool_size)))
        base_pool = sorted(final, key=lambda n: (-final[n], n))[:size]

    pool = []
    for n in fixed:
        if n not in excluded and n not in pool:
            pool.append(n)
    for n in base_pool:
        if n not in excluded and n not in pool:
            pool.append(n)
    ordered_all = sorted(final, key=lambda n: (-final[n], n))
    for n in ordered_all:
        if len(pool) >= max(len(base_pool), 6):
            break
        if n not in excluded and n not in pool:
            pool.append(n)

    combos = _combination_scores(history, sorted(pool), final, pair, single)
    if fixed:
        fset = set(fixed)
        combos = [c for c in combos if fset.issubset(set(c["numbers"]))]
    core_numbers = ordered_all[:2]
    selected = _portfolio(combos, games, style, core_numbers=core_numbers)

    top6 = ordered_all[:6]
    counts = {}
    for game in selected:
        for n in game["numbers"]:
            counts[n] = counts.get(n, 0) + 1
    threshold = max(2, math.ceil(max(1, len(selected)) * .60))
    axis = [n for n in top6 if counts.get(n, 0) >= threshold]
    if not axis and top6:
        mx = max(counts.get(n, 0) for n in top6)
        axis = [n for n in top6 if counts.get(n, 0) == mx and mx >= 2][:2]

    confidence = _confidence(final, ranks, top10_count, bool(weights_json))
    target_draw = history[-1]["draw"] + 1
    games_payload = []
    for i, row in enumerate(selected):
        games_payload.append({
            "index": i + 1,
            "numbers": list(row["numbers"]),
            "score": round(row["score"], 2),
            "rank": row["rank"],
            "total": row["total"],
            "percentile": round(row["percentile"], 2),
        })

    raw_id = f"{target_draw}|" + "|".join("-".join(map(str, g["numbers"])) for g in games_payload)
    rec_id = f"{target_draw}-" + hashlib.sha256(raw_id.encode()).hexdigest()[:10].upper()

    return json.dumps({
        "latestDraw": history[-1]["draw"],
        "latestDate": history[-1]["date"],
        "targetDraw": target_draw,
        "recommendationId": rec_id,
        "games": games_payload,
        "core": top6[:2],
        "semiCore": top6[2:6],
        "axis": axis,
        "candidatePool": pool,
        "confidence": confidence,
        "weights": normalized_weights,
        "modelTop": {
            m: sorted(model_scores[m], key=lambda n: (-model_scores[m][n], n))[:10]
            for m in MODELS
        },
    }, ensure_ascii=False)


def _eval_promotion_gate(hold_equal, hold_candidate, full_equal, full_candidate, eps=1e-9):
    holdout_better = (hold_candidate - hold_equal) > eps
    full_non_degraded = (full_candidate - full_equal) >= -eps
    return bool(holdout_better and full_non_degraded)


def quick_research(history_json, test_draws=40):
    history = _parse_history(history_json)
    available = len(history) - 80
    if available < 20:
        raise ValueError("빠른 연구에는 최소 100회 이상의 데이터가 필요합니다.")
    test_draws = min(max(20, int(test_draws)), 60, available)
    start = len(history) - test_draws
    mids = list(MODELS)
    frames = []

    for idx in range(start, len(history)):
        train = history[:idx]
        actual = set(history[idx]["numbers"])
        _, scores, ranks, _, _ = _model_scores(train)
        frames.append({
            "scores": scores,
            "actual": actual,
            "matches": {
                m: len(actual & set(sorted(scores[m], key=lambda n: (-scores[m][n], n))[:6]))
                for m in mids
            }
        })

    # Chronologically split into approx 75% training-validation and 25% untouched holdout
    split = min(max(1, int(len(frames) * 0.75)), len(frames) - 1)
    train_frames = frames[:split]
    holdout = frames[split:]

    # Derive model_avg, learned weights, and candidate weights ONLY from train_frames
    model_avg = {
        m: sum(f["matches"][m] for f in train_frames) / len(train_frames)
        for m in mids
    }
    mean_avg = sum(model_avg.values()) / len(mids)
    exps = {m: math.exp((model_avg[m] - mean_avg) * 2.5) for m in mids}
    s = sum(exps.values())
    learned = {m: exps[m] / s for m in mids}
    equal = {m: 1.0 / len(mids) for m in mids}
    candidate = {m: 0.5 * learned[m] + 0.5 * equal[m] for m in mids}

    def ensemble_avg(part, weights):
        hits = []
        for f in part:
            combined = {
                n: sum(f["scores"][m][n] * weights[m] for m in mids)
                for n in range(1, 46)
            }
            top = sorted(combined, key=lambda n: (-combined[n], n))[:6]
            hits.append(len(f["actual"] & set(top)))
        return sum(hits) / len(hits) if hits else 0.0

    full_equal = ensemble_avg(frames, equal)
    full_candidate = ensemble_avg(frames, candidate)
    hold_equal = ensemble_avg(holdout, equal)
    hold_candidate = ensemble_avg(holdout, candidate)

    eps = 1e-9
    promoted = _eval_promotion_gate(hold_equal, hold_candidate, full_equal, full_candidate, eps)
    final_weights = candidate if promoted else equal

    full_gain = full_candidate - full_equal
    holdout_gain = hold_candidate - hold_equal

    if promoted:
        message = "빠른 연구 보정 가중치를 적용합니다."
    elif abs(hold_candidate - hold_equal) <= eps:
        message = "독립 홀드아웃 검증에서 동점으로 개선이 없어 기본 가중치를 유지합니다."
    elif hold_candidate < hold_equal:
        message = "독립 홀드아웃 검증에서 개선이 없어 기본 가중치를 유지합니다."
    else:
        message = "전체 기간 검증에서 성능이 저하되어 기본 가중치를 유지합니다."

    return json.dumps({
        "promoted": promoted,
        "message": message,
        "weights": final_weights,
        "modelAverageMatches": model_avg,
        "fullEqual": round(full_equal, 3),
        "fullCandidate": round(full_candidate, 3),
        "holdoutEqual": round(hold_equal, 3),
        "holdoutCandidate": round(hold_candidate, 3),
        "testedDraws": len(frames),
        "trainingDraws": len(train_frames),
        "holdoutDraws": len(holdout),
        "fullGain": round(full_gain, 4),
        "holdoutGain": round(holdout_gain, 4),
    }, ensure_ascii=False)
