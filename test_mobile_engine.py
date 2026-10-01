import json, random
import mobile_engine

rng = random.Random(12345)
history = []
for draw in range(1, 181):
    nums = sorted(rng.sample(range(1, 46), 6))
    bonus = rng.choice([n for n in range(1, 46) if n not in nums])
    history.append({
        "draw": draw,
        "date": "2026-01-01",
        "numbers": nums,
        "bonus": bonus,
    })

history_json = json.dumps(history)
rec = json.loads(mobile_engine.recommend(
    history_json,
    "",
    json.dumps({"games": 5, "style": "표준"})
))
assert rec["targetDraw"] == 181
assert len(rec["games"]) == 5
assert len(rec["core"]) == 2
assert 9 <= len(rec["candidatePool"]) <= 16
assert all(len(g["numbers"]) == 6 for g in rec["games"])

research = json.loads(mobile_engine.quick_research(history_json, 20))
assert "weights" in research
assert abs(sum(research["weights"].values()) - 1.0) < 1e-8

print("MOBILE ENGINE TEST OK")
print("추천안:", rec["recommendationId"])
print("핵심:", rec["core"])
print("후보수:", len(rec["candidatePool"]))
print("확신도:", rec["confidence"])
print("연구:", research["message"])
