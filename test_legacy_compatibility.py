"""
Phase 2 Step 3G - Legacy Research Compatibility Tests (L1-L8)
Validates safe legacy state reconciliation, migration ordering, idempotency,
and confirmed-ticket integrity.
"""

import sys
import os
import json
import sqlite3

# Ensure app/src/main/python is on python path
sys.path.insert(0, os.path.abspath("app/src/main/python"))
import mobile_engine as m

KEY_RESEARCH_RESULT = "research_result"
KEY_RESEARCH_WEIGHTS = "research_weights"
KEY_LEGACY_BACKUP = "legacy_research_backup"
MSG_LEGACY_NOTICE = "이전 연구 기록은 새로운 검증 기준으로 확인되지 않았습니다. 연구를 다시 실행하면 최신 기준으로 적용 여부를 판단합니다."

MODELS = ["long", "recent", "gap", "pair", "balance", "inverse"]
EQUAL = {mid: 1.0 / len(MODELS) for mid in MODELS}


class MockLottoDb:
    def __init__(self, db_path=":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS draws(
                    draw_no INTEGER PRIMARY KEY,
                    date TEXT NOT NULL,
                    n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                    n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
                    bonus INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS app_state(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recommendations(
                    draw_no INTEGER PRIMARY KEY,
                    recommendation_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    confirmed_at INTEGER NOT NULL
                );
            """)

    def save_state(self, key, value):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO app_state(key, value) VALUES(?, ?)",
                (key, value)
            )

    def load_state(self, key):
        cur = self.conn.cursor()
        cur.execute("SELECT value FROM app_state WHERE key=?", (key,))
        row = cur.fetchone()
        return row[0] if row else None

    def save_recommendation(self, draw, rec_id, payload_json, confirmed_at=1700000000):
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO recommendations(draw_no, recommendation_id, payload_json, confirmed_at) VALUES(?, ?, ?, ?)",
                (draw, rec_id, payload_json, confirmed_at)
            )

    def list_confirmed(self):
        cur = self.conn.cursor()
        cur.execute("SELECT draw_no, recommendation_id, payload_json, confirmed_at FROM recommendations ORDER BY draw_no DESC")
        return cur.fetchall()


class MockLottoRepository:
    """Exact replica of LottoRepository reconciliation and recommendation logic."""
    def __init__(self, db):
        self.db = db
        self.reconcile_legacy_research_state()

    def reconcile_legacy_research_state(self):
        raw_research = self.db.load_state(KEY_RESEARCH_RESULT)
        raw_weights = self.db.load_state(KEY_RESEARCH_WEIGHTS)

        # Case 1: research_result is missing or blank
        if not raw_research or not raw_research.strip():
            if raw_weights and raw_weights.strip():
                self.db.save_state(KEY_RESEARCH_WEIGHTS, "")
            return

        try:
            o = json.loads(raw_research)
        except Exception:
            if self.db.load_state(KEY_LEGACY_BACKUP) is None:
                self.db.save_state(KEY_LEGACY_BACKUP, raw_research)
            self.db.save_state(KEY_RESEARCH_WEIGHTS, "")
            self.db.save_state(KEY_RESEARCH_RESULT, "")
            return

        has_policy_b_meta = (
            "strongEvidencePassed" in o and
            "holdoutTotalMatchAdvantage" in o and
            "strongEvidenceThreshold" in o
        )

        if has_policy_b_meta:
            inconsistency = self.validate_modern_consistency(o, raw_weights)
            if inconsistency is None:
                promoted = o.get("promoted", False)
                if not promoted and raw_weights and raw_weights.strip():
                    self.db.save_state(KEY_RESEARCH_WEIGHTS, "")
                return

            # Inconsistent modern record
            if self.db.load_state(KEY_LEGACY_BACKUP) is None:
                self.db.save_state(KEY_LEGACY_BACKUP, raw_research)
            self.db.save_state(KEY_RESEARCH_WEIGHTS, "")
            reconciled = {
                "promoted": False,
                "message": "저장된 연구 데이터에 일관성 오류가 감지되어 기본 가중치를 유지합니다. 연구를 다시 실행해 주십시오.",
                "weights": o.get("weights", {}),
                "testedDraws": o.get("testedDraws", 40),
                "fullEqual": o.get("fullEqual", 0.0),
                "fullCandidate": o.get("fullCandidate", 0.0),
                "holdoutEqual": o.get("holdoutEqual", 0.0),
                "holdoutCandidate": o.get("holdoutCandidate", 0.0),
                "primaryReason": "데이터 불일치 (재검증 필요)",
                "basePromotionPassed": False,
                "candidateHoldoutTotalMatches": 0,
                "equalHoldoutTotalMatches": 0,
                "holdoutTotalMatchAdvantage": 0,
                "strongEvidenceThreshold": 2,
                "strongEvidencePassed": False,
                "isLegacyRecord": True
            }
            self.db.save_state(KEY_RESEARCH_RESULT, json.dumps(reconciled, ensure_ascii=False))
            return

        # Case 2: Legacy research record lacking Policy B metadata
        # 1. Preserve old research JSON in app_state backup key without overwriting existing
        if self.db.load_state(KEY_LEGACY_BACKUP) is None:
            self.db.save_state(KEY_LEGACY_BACKUP, raw_research)

        # 2. Invalidate active legacy research_weights
        self.db.save_state(KEY_RESEARCH_WEIGHTS, "")

        # 3. Reconcile research_result into safe HOLD state with notice
        was_promoted = o.get("promoted", False)
        legacy_reason = "재검증 필요" if was_promoted else o.get("primaryReason", "최종 홀드아웃 미개선")
        legacy_message = MSG_LEGACY_NOTICE if was_promoted else o.get("message", "검증 기준을 충족하지 못해 기본 가중치를 유지합니다.")

        reconciled = {
            "promoted": False,
            "message": legacy_message,
            "weights": o.get("weights", {}),
            "testedDraws": o.get("testedDraws", 40),
            "fullEqual": o.get("fullEqual", 0.0),
            "fullCandidate": o.get("fullCandidate", 0.0),
            "holdoutEqual": o.get("holdoutEqual", 0.0),
            "holdoutCandidate": o.get("holdoutCandidate", 0.0),
            "primaryReason": legacy_reason,
            "basePromotionPassed": o.get("basePromotionPassed", was_promoted),
            "candidateHoldoutTotalMatches": 0,
            "equalHoldoutTotalMatches": 0,
            "holdoutTotalMatchAdvantage": 0,
            "strongEvidenceThreshold": 2,
            "strongEvidencePassed": False,
            "isLegacyRecord": True
        }
        self.db.save_state(KEY_RESEARCH_RESULT, json.dumps(reconciled, ensure_ascii=False))

    def parse_weight_vector(self, raw_or_obj):
        if not raw_or_obj:
            return None
        if isinstance(raw_or_obj, str):
            try:
                obj = json.loads(raw_or_obj)
            except Exception:
                return None
        elif isinstance(raw_or_obj, dict):
            obj = raw_or_obj
        else:
            return None

        if set(obj.keys()) != set(MODELS):
            return None

        vec = {}
        s = 0.0
        for k in MODELS:
            v = obj[k]
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                return None
            if v < 0.0:
                return None
            vec[k] = float(v)
            s += float(v)

        if abs(s - 1.0) >= 1e-9:
            return None
        return vec

    def validate_modern_consistency(self, o, raw_weights):
        if "promoted" not in o or not isinstance(o["promoted"], bool):
            return "promoted must be boolean"
        promoted = o["promoted"]

        if "basePromotionPassed" not in o or not isinstance(o["basePromotionPassed"], bool):
            return "basePromotionPassed must be boolean"
        base_promotion_passed = o["basePromotionPassed"]

        if "strongEvidencePassed" not in o or not isinstance(o["strongEvidencePassed"], bool):
            return "strongEvidencePassed must be boolean"
        strong_evidence_passed = o["strongEvidencePassed"]

        threshold = o.get("strongEvidenceThreshold")
        if not isinstance(threshold, int) or isinstance(threshold, bool) or threshold != 2:
            return f"strongEvidenceThreshold must be strictly 2, got {threshold}"

        cand_matches = o.get("candidateHoldoutTotalMatches")
        if not isinstance(cand_matches, int) or isinstance(cand_matches, bool) or cand_matches < 0:
            return f"Invalid candidateHoldoutTotalMatches: {cand_matches}"

        eq_matches = o.get("equalHoldoutTotalMatches")
        if not isinstance(eq_matches, int) or isinstance(eq_matches, bool) or eq_matches < 0:
            return f"Invalid equalHoldoutTotalMatches: {eq_matches}"

        adv = o.get("holdoutTotalMatchAdvantage")
        if not isinstance(adv, int) or isinstance(adv, bool):
            return f"Invalid holdoutTotalMatchAdvantage: {adv}"

        if cand_matches - eq_matches != adv:
            return f"Advantage arithmetic mismatch: {cand_matches} - {eq_matches} != {adv}"

        expected_strong = (adv >= 2)
        if strong_evidence_passed != expected_strong:
            return f"strongEvidencePassed ({strong_evidence_passed}) != (adv {adv} >= 2)"

        expected_promoted = (base_promotion_passed and strong_evidence_passed)
        if promoted != expected_promoted:
            return f"promoted ({promoted}) != (base {base_promotion_passed} and strong {strong_evidence_passed})"

        res_vec = self.parse_weight_vector(o.get("weights"))
        if res_vec is None:
            return "Invalid weights in research_result"

        if promoted:
            if not raw_weights or not raw_weights.strip():
                return "promoted=true but active research_weights is blank"
            act_vec = self.parse_weight_vector(raw_weights)
            if act_vec is None:
                return "promoted=true but active research_weights is invalid"
            for k in MODELS:
                if abs(res_vec[k] - act_vec[k]) >= 1e-9:
                    return f"Weight vector mismatch for key {k}: {res_vec[k]} != {act_vec[k]}"
        else:
            if raw_weights and raw_weights.strip():
                return "promoted=false but active research_weights is non-empty"

        return None

    def recommend(self, history_json, games=5, style="표준"):
        self.reconcile_legacy_research_state()
        weights_json = self.db.load_state(KEY_RESEARCH_WEIGHTS) or ""
        return json.loads(m.recommend(
            history_json,
            weights_json,
            json.dumps({"games": games, "style": style})
        ))

    def saved_research(self):
        self.reconcile_legacy_research_state()
        raw = self.db.load_state(KEY_RESEARCH_RESULT)
        if not raw or not raw.strip():
            return None
        return json.loads(raw)


def test_l1_legacy_promoted_record():
    print("Testing L1: Legacy promoted record with active weights...")
    db = MockLottoDb()
    legacy_weights = {"long": 0.40, "recent": 0.12, "gap": 0.12, "pair": 0.12, "balance": 0.12, "inverse": 0.12}
    legacy_research = {
        "promoted": True,
        "message": "빠른 연구 보정 가중치를 적용합니다.",
        "weights": legacy_weights,
        "testedDraws": 40,
        "fullEqual": 0.775,
        "fullCandidate": 0.850,
        "holdoutEqual": 0.700,
        "holdoutCandidate": 0.800
        # No strongEvidencePassed, holdoutTotalMatchAdvantage, strongEvidenceThreshold
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(legacy_research))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(legacy_weights))

    repo = MockLottoRepository(db)

    # 1. Old record is archived in backup
    backup = db.load_state(KEY_LEGACY_BACKUP)
    assert backup is not None, "Backup must be created"
    assert json.loads(backup) == legacy_research

    # 2. Old weights are invalidated
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == "", "Legacy research_weights must be cleared"

    # 3. Restored state asks for revalidation
    saved = repo.saved_research()
    assert saved["promoted"] is False, "Must not be promoted"
    assert saved["isLegacyRecord"] is True
    assert saved["message"] == MSG_LEGACY_NOTICE
    assert saved["primaryReason"] == "재검증 필요"
    assert saved["strongEvidencePassed"] is False
    print("  L1 PASS")


def test_l2_legacy_hold_record():
    print("Testing L2: Legacy HOLD record safely restored...")
    db = MockLottoDb()
    legacy_hold = {
        "promoted": False,
        "message": "독립 홀드아웃 검증에서 개선이 없어 기본 가중치를 유지합니다.",
        "weights": EQUAL,
        "testedDraws": 40,
        "fullEqual": 0.775,
        "fullCandidate": 0.675,
        "holdoutEqual": 0.700,
        "holdoutCandidate": 0.600,
        "primaryReason": "최종 홀드아웃 미개선"
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(legacy_hold))
    db.save_state(KEY_RESEARCH_WEIGHTS, "")

    repo = MockLottoRepository(db)

    saved = repo.saved_research()
    assert saved["promoted"] is False
    assert saved["isLegacyRecord"] is True
    assert saved["primaryReason"] == "최종 홀드아웃 미개선"
    assert saved["strongEvidencePassed"] is False
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == ""
    print("  L2 PASS")


def test_l3_valid_new_promoted_record():
    print("Testing L3: Valid new-format promoted record remains active...")
    db = MockLottoDb()
    promoted_weights = {"long": 0.20, "recent": 0.20, "gap": 0.20, "pair": 0.15, "balance": 0.10, "inverse": 0.15}
    valid_research = {
        "promoted": True,
        "message": "빠른 연구 보정 가중치를 적용합니다.",
        "weights": promoted_weights,
        "testedDraws": 40,
        "fullEqual": 0.775,
        "fullCandidate": 0.850,
        "holdoutEqual": 0.700,
        "holdoutCandidate": 0.900,
        "basePromotionPassed": True,
        "candidateHoldoutTotalMatches": 9,
        "equalHoldoutTotalMatches": 7,
        "holdoutTotalMatchAdvantage": 2,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": True,
        "isLegacyRecord": False
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(valid_research))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(promoted_weights))

    repo = MockLottoRepository(db)

    # Backup should NOT be created
    assert db.load_state(KEY_LEGACY_BACKUP) is None, "Valid record must not create backup"
    # Weights must remain active
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == json.dumps(promoted_weights)

    saved = repo.saved_research()
    assert saved["promoted"] is True
    assert saved["strongEvidencePassed"] is True
    assert saved["isLegacyRecord"] is False
    print("  L3 PASS")


def test_l4_valid_new_hold_record():
    print("Testing L4: Valid new-format HOLD remains default...")
    db = MockLottoDb()
    valid_hold = {
        "promoted": False,
        "message": "검증 기준은 통과했지만 홀드아웃 누적 우위가 적용 기준(+2)에 미달하여 기본 가중치를 유지합니다.",
        "weights": EQUAL,
        "testedDraws": 40,
        "fullEqual": 0.775,
        "fullCandidate": 0.825,
        "holdoutEqual": 0.600,
        "holdoutCandidate": 0.700,
        "primaryReason": "홀드아웃 근거 부족",
        "basePromotionPassed": True,
        "candidateHoldoutTotalMatches": 7,
        "equalHoldoutTotalMatches": 6,
        "holdoutTotalMatchAdvantage": 1,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": False,
        "isLegacyRecord": False
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(valid_hold))
    db.save_state(KEY_RESEARCH_WEIGHTS, "")

    repo = MockLottoRepository(db)

    assert db.load_state(KEY_LEGACY_BACKUP) is None
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == ""

    saved = repo.saved_research()
    assert saved["promoted"] is False
    assert saved["strongEvidencePassed"] is False
    assert saved["primaryReason"] == "홀드아웃 근거 부족"
    assert saved["isLegacyRecord"] is False
    print("  L4 PASS")


def test_l5_idempotency():
    print("Testing L5: Idempotency of reconciliation...")
    db = MockLottoDb()
    legacy_research = {"promoted": True, "weights": {"long": 0.5, "recent": 0.1, "gap": 0.1, "pair": 0.1, "balance": 0.1, "inverse": 0.1}}
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(legacy_research))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(legacy_research["weights"]))

    # 1st run
    repo1 = MockLottoRepository(db)
    backup1 = db.load_state(KEY_LEGACY_BACKUP)
    result1 = db.load_state(KEY_RESEARCH_RESULT)

    # 2nd run
    repo2 = MockLottoRepository(db)
    backup2 = db.load_state(KEY_LEGACY_BACKUP)
    result2 = db.load_state(KEY_RESEARCH_RESULT)

    assert backup1 == backup2, "Backup must not be overwritten"
    assert result1 == result2, "Reconciled result must not be mutated"
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == ""
    print("  L5 PASS")


def test_l6_migration_ordering():
    print("Testing L6: Migration ordering - legacy weights neutralized BEFORE recommend()...")
    # Generate synthetic history
    hist = []
    for d in range(1, 150):
        hist.append({
            "draw": d,
            "date": "2026-01-01",
            "numbers": [(d * 7 + i) % 45 + 1 for i in range(6)],
            "bonus": (d * 7 + 10) % 45 + 1
        })
    hist_json = json.dumps(hist)

    # Compute baseline recommendation with no weights
    rec_baseline = json.loads(m.recommend(hist_json, "", json.dumps({"games": 5, "style": "표준"})))

    # Compute recommendation with heavily skewed weights
    skewed_weights = {"long": 0.90, "recent": 0.02, "gap": 0.02, "pair": 0.02, "balance": 0.02, "inverse": 0.02}
    rec_skewed = json.loads(m.recommend(hist_json, json.dumps(skewed_weights), json.dumps({"games": 5, "style": "표준"})))
    assert rec_baseline["recommendationId"] != rec_skewed["recommendationId"], "Skewed weights must alter recommendation"

    # Now simulate fresh repo launch with legacy skewed weights in DB
    db = MockLottoDb()
    db.save_state(KEY_RESEARCH_RESULT, json.dumps({"promoted": True, "weights": skewed_weights}))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(skewed_weights))

    # Without calling saved_research(), call recommend() FIRST as MainViewModel does!
    repo = MockLottoRepository(db)
    rec_first = repo.recommend(hist_json, games=5, style="표준")

    # MUST match baseline, NOT skewed!
    assert rec_first["recommendationId"] == rec_baseline["recommendationId"], (
        f"Recommendation must use baseline weights! Got {rec_first['recommendationId']} vs {rec_baseline['recommendationId']}"
    )
    assert [g["numbers"] for g in rec_first["games"]] == [g["numbers"] for g in rec_baseline["games"]]
    print("  L6 PASS")


def test_l7_fresh_research():
    print("Testing L7: Fresh research operates normally after legacy reconciliation...")
    db = MockLottoDb()
    db.save_state(KEY_RESEARCH_RESULT, json.dumps({"promoted": True, "weights": {"long": 0.5, "recent": 0.1, "gap": 0.1, "pair": 0.1, "balance": 0.1, "inverse": 0.1}}))
    db.save_state(KEY_RESEARCH_WEIGHTS, "some_old_weights")

    repo = MockLottoRepository(db)
    assert db.load_state(KEY_LEGACY_BACKUP) is not None

    # Now simulate user running fresh research in repo
    fresh_result = {
        "promoted": False,
        "message": "독립 홀드아웃 검증에서 동점으로 개선이 없어 기본 가중치를 유지합니다.",
        "weights": EQUAL,
        "testedDraws": 40,
        "fullEqual": 0.775,
        "fullCandidate": 0.775,
        "holdoutEqual": 0.700,
        "holdoutCandidate": 0.700,
        "primaryReason": "최종 홀드아웃 미개선",
        "basePromotionPassed": False,
        "candidateHoldoutTotalMatches": 7,
        "equalHoldoutTotalMatches": 7,
        "holdoutTotalMatchAdvantage": 0,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": False,
        "isLegacyRecord": False
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(fresh_result))
    db.save_state(KEY_RESEARCH_WEIGHTS, "")

    saved = repo.saved_research()
    assert saved["isLegacyRecord"] is False
    assert saved["primaryReason"] == "최종 홀드아웃 미개선"
    # Backup remains safe
    assert db.load_state(KEY_LEGACY_BACKUP) is not None
    print("  L7 PASS")


def test_l8_confirmed_ticket_integrity():
    print("Testing L8: Confirmed-ticket integrity across reconciliation...")
    db = MockLottoDb()
    # Save confirmed recommendation
    payload = json.dumps({
        "recommendationId": "1243-ABCDEF1234",
        "targetDraw": 1243,
        "games": [{"index": 1, "numbers": [1, 2, 3, 4, 5, 6], "score": 85.0}]
    })
    db.save_recommendation(1243, "1243-ABCDEF1234", payload, confirmed_at=1710000000)

    # Inject legacy research
    db.save_state(KEY_RESEARCH_RESULT, json.dumps({"promoted": True, "weights": EQUAL}))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(EQUAL))

    # Reconcile
    repo = MockLottoRepository(db)

    # Check confirmed records
    confirmed = db.list_confirmed()
    assert len(confirmed) == 1
    assert confirmed[0][0] == 1243
    assert confirmed[0][1] == "1243-ABCDEF1234"
    assert confirmed[0][2] == payload
    assert confirmed[0][3] == 1710000000
    print("  L8 PASS")


def test_l9_inconsistent_strong_evidence_false():
    print("Testing L9: Inconsistent modern record (promoted=true but strongEvidencePassed=false)...")
    db = MockLottoDb()
    inconsistent = {
        "promoted": True,  # Contradiction!
        "message": "연구 적용",
        "weights": EQUAL,
        "testedDraws": 40,
        "basePromotionPassed": True,
        "candidateHoldoutTotalMatches": 7,
        "equalHoldoutTotalMatches": 6,
        "holdoutTotalMatchAdvantage": 1,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": False
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(inconsistent))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(EQUAL))

    repo = MockLottoRepository(db)

    assert db.load_state(KEY_LEGACY_BACKUP) is not None, "Inconsistent record must be backed up"
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == "", "Inconsistent weights must be neutralized"

    saved = repo.saved_research()
    assert saved["promoted"] is False, "Must be neutralized to HOLD"
    assert saved["isLegacyRecord"] is True
    assert saved["primaryReason"] == "데이터 불일치 (재검증 필요)"
    print("  L9 PASS")


def test_l10_inconsistent_base_promotion_false():
    print("Testing L10: Inconsistent modern record (promoted=true but basePromotionPassed=false)...")
    db = MockLottoDb()
    inconsistent = {
        "promoted": True,  # Contradiction!
        "message": "연구 적용",
        "weights": EQUAL,
        "testedDraws": 40,
        "basePromotionPassed": False,
        "candidateHoldoutTotalMatches": 9,
        "equalHoldoutTotalMatches": 7,
        "holdoutTotalMatchAdvantage": 2,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": True
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(inconsistent))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(EQUAL))

    repo = MockLottoRepository(db)

    assert db.load_state(KEY_RESEARCH_WEIGHTS) == ""
    saved = repo.saved_research()
    assert saved["promoted"] is False
    assert saved["primaryReason"] == "데이터 불일치 (재검증 필요)"
    print("  L10 PASS")


def test_l11_inconsistent_match_totals_arithmetic():
    print("Testing L11: Inconsistent raw match totals vs advantage arithmetic...")
    db = MockLottoDb()
    inconsistent = {
        "promoted": True,
        "message": "연구 적용",
        "weights": EQUAL,
        "testedDraws": 40,
        "basePromotionPassed": True,
        "candidateHoldoutTotalMatches": 8,
        "equalHoldoutTotalMatches": 5,
        "holdoutTotalMatchAdvantage": 1,  # 8 - 5 = 3 != 1
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": True
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(inconsistent))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(EQUAL))

    repo = MockLottoRepository(db)

    assert db.load_state(KEY_RESEARCH_WEIGHTS) == ""
    saved = repo.saved_research()
    assert saved["promoted"] is False
    print("  L11 PASS")


def test_l12_inconsistent_weights_status():
    print("Testing L12: Inconsistent active weights status...")
    # 1. Promoted=True but active weights missing/blank
    db1 = MockLottoDb()
    promoted_rec = {
        "promoted": True,
        "message": "연구 적용",
        "weights": EQUAL,
        "testedDraws": 40,
        "basePromotionPassed": True,
        "candidateHoldoutTotalMatches": 9,
        "equalHoldoutTotalMatches": 7,
        "holdoutTotalMatchAdvantage": 2,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": True
    }
    db1.save_state(KEY_RESEARCH_RESULT, json.dumps(promoted_rec))
    db1.save_state(KEY_RESEARCH_WEIGHTS, "")  # Blank weights!

    repo1 = MockLottoRepository(db1)
    assert repo1.saved_research()["promoted"] is False

    # 2. Promoted=False but active weights non-empty in DB
    db2 = MockLottoDb()
    hold_rec = {
        "promoted": False,
        "message": "홀드",
        "weights": EQUAL,
        "testedDraws": 40,
        "primaryReason": "최종 홀드아웃 미개선",
        "basePromotionPassed": False,
        "candidateHoldoutTotalMatches": 6,
        "equalHoldoutTotalMatches": 7,
        "holdoutTotalMatchAdvantage": -1,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": False
    }
    db2.save_state(KEY_RESEARCH_RESULT, json.dumps(hold_rec))
    db2.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(EQUAL))  # Should not be non-empty for HOLD

    repo2 = MockLottoRepository(db2)
    assert db2.load_state(KEY_RESEARCH_WEIGHTS) == ""
    print("  L12 PASS")


def test_l13_corrupted_or_negative_data():
    print("Testing L13: Corrupted or negative match data safely caught...")
    db = MockLottoDb()
    corrupt = {
        "promoted": False,
        "weights": EQUAL,
        "testedDraws": 40,
        "candidateHoldoutTotalMatches": -1,  # Negative!
        "equalHoldoutTotalMatches": 5,
        "holdoutTotalMatchAdvantage": -6,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": False
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(corrupt))
    db.save_state(KEY_RESEARCH_WEIGHTS, "")

    repo = MockLottoRepository(db)
    saved = repo.saved_research()
    assert saved["promoted"] is False
    assert saved["primaryReason"] == "데이터 불일치 (재검증 필요)"
    print("  L13 PASS")


def test_l14_valid_modern_pipeline_and_preservation():
    print("Testing L14: Valid modern Policy B records preserved and confirmed tickets isolated...")
    db = MockLottoDb()
    valid_promoted = {
        "promoted": True,
        "message": "보정 적용",
        "weights": EQUAL,
        "testedDraws": 40,
        "basePromotionPassed": True,
        "candidateHoldoutTotalMatches": 10,
        "equalHoldoutTotalMatches": 7,
        "holdoutTotalMatchAdvantage": 3,
        "strongEvidenceThreshold": 2,
        "strongEvidencePassed": True,
        "isLegacyRecord": False
    }
    db.save_state(KEY_RESEARCH_RESULT, json.dumps(valid_promoted))
    db.save_state(KEY_RESEARCH_WEIGHTS, json.dumps(EQUAL))

    repo = MockLottoRepository(db)
    assert db.load_state(KEY_LEGACY_BACKUP) is None
    assert db.load_state(KEY_RESEARCH_WEIGHTS) == json.dumps(EQUAL)
    assert repo.saved_research()["promoted"] is True
    print("  L14 PASS")


def main():
    print("==================================================")
    print("LEGACY & MODERN INCONSISTENCY TESTS (L1-L14)")
    print("==================================================")
    test_l1_legacy_promoted_record()
    test_l2_legacy_hold_record()
    test_l3_valid_new_promoted_record()
    test_l4_valid_new_hold_record()
    test_l5_idempotency()
    test_l6_migration_ordering()
    test_l7_fresh_research()
    test_l8_confirmed_ticket_integrity()
    test_l9_inconsistent_strong_evidence_false()
    test_l10_inconsistent_base_promotion_false()
    test_l11_inconsistent_match_totals_arithmetic()
    test_l12_inconsistent_weights_status()
    test_l13_corrupted_or_negative_data()
    test_l14_valid_modern_pipeline_and_preservation()
    print("==================================================")
    print("ALL TESTS L1-L14 PASSED PERFECTLY!")
    print("==================================================")


if __name__ == "__main__":
    main()
