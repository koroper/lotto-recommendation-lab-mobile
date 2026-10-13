package com.lotto.lab.data

import org.json.JSONObject

enum class ReconcileStatus {
    VALID_MODERN,
    RECONCILED_LEGACY,
    RECONCILED_INCONSISTENT,
    CLEARED_ORPHAN_WEIGHTS,
    NOOP
}

data class ReconcileResult(
    val updatedResearchResult: String?,
    val updatedResearchWeights: String,
    val backupToSave: String?,
    val status: ReconcileStatus,
    val reason: String? = null
)

object ResearchStateReconciler {
    const val KEY_RESEARCH_RESULT = "research_result"
    const val KEY_RESEARCH_WEIGHTS = "research_weights"
    const val KEY_LEGACY_BACKUP = "legacy_research_backup"

    const val MSG_LEGACY_NOTICE =
        "이전 연구 기록은 새로운 검증 기준으로 확인되지 않았습니다. 연구를 다시 실행하면 최신 기준으로 적용 여부를 판단합니다."
    const val MSG_INCONSISTENT_NOTICE =
        "저장된 연구 데이터에 일관성 오류가 감지되어 기본 가중치를 유지합니다. 연구를 다시 실행해 주십시오."

    val MODEL_KEYS = setOf("long", "recent", "gap", "pair", "balance", "inverse")
    const val WEIGHT_EPSILON = 1e-9

    fun parseWeightVector(raw: String?): Map<String, Double>? {
        if (raw.isNullOrBlank()) return null
        return try {
            parseWeightVector(JSONObject(raw))
        } catch (_: Exception) {
            null
        }
    }

    fun parseWeightVector(obj: JSONObject?): Map<String, Double>? {
        if (obj == null) return null
        val keys = mutableSetOf<String>()
        val it = obj.keys()
        while (it.hasNext()) {
            keys.add(it.next())
        }
        // Exactly the 6 model keys: reject any extra or missing keys
        if (keys != MODEL_KEYS) return null

        val vector = mutableMapOf<String, Double>()
        var sum = 0.0
        for (key in MODEL_KEYS) {
            val rawVal = obj.opt(key) ?: return null
            if (rawVal !is Number) return null
            val d = rawVal.toDouble()
            if (!d.isFinite() || d < 0.0) return null
            vector[key] = d
            sum += d
        }
        if (Math.abs(sum - 1.0) >= WEIGHT_EPSILON) return null
        return vector
    }

    fun reconcile(
        rawResearch: String?,
        rawWeights: String?,
        existingBackup: String?
    ): ReconcileResult {
        // Case 1: research_result is null or blank
        if (rawResearch.isNullOrBlank()) {
            val weightsCleared = if (!rawWeights.isNullOrBlank()) "" else (rawWeights ?: "")
            val status = if (!rawWeights.isNullOrBlank()) ReconcileStatus.CLEARED_ORPHAN_WEIGHTS else ReconcileStatus.NOOP
            return ReconcileResult(
                updatedResearchResult = null,
                updatedResearchWeights = weightsCleared,
                backupToSave = null,
                status = status,
                reason = if (!rawWeights.isNullOrBlank()) "Orphan research_weights cleared" else null
            )
        }

        val o = try {
            JSONObject(rawResearch)
        } catch (_: Exception) {
            val backup = if (existingBackup == null) rawResearch else null
            return ReconcileResult(
                updatedResearchResult = "",
                updatedResearchWeights = "",
                backupToSave = backup,
                status = ReconcileStatus.RECONCILED_INCONSISTENT,
                reason = "Malformed research_result JSON"
            )
        }

        // Case 2: Explicitly marked legacy record
        if (o.optBoolean("isLegacyRecord", false)) {
            val updatedWeights = ""
            val updatedResult = if (o.optBoolean("promoted", false)) {
                JSONObject(rawResearch).apply {
                    put("promoted", false)
                    put("primaryReason", "재검증 필요")
                    put("message", MSG_LEGACY_NOTICE)
                }.toString()
            } else {
                rawResearch
            }
            return ReconcileResult(
                updatedResearchResult = updatedResult,
                updatedResearchWeights = updatedWeights,
                backupToSave = null,
                status = ReconcileStatus.VALID_MODERN
            )
        }

        // Check if legacy (missing required Policy B metadata keys)
        val hasPolicyBMeta = o.has("strongEvidencePassed") &&
                o.has("holdoutTotalMatchAdvantage") &&
                o.has("strongEvidenceThreshold")

        if (!hasPolicyBMeta) {
            val wasPromoted = o.optBoolean("promoted", false)
            val legacyReason = if (wasPromoted) {
                "재검증 필요"
            } else {
                if (o.has("primaryReason") && !o.isNull("primaryReason")) o.getString("primaryReason") else "최종 홀드아웃 미개선"
            }
            val legacyMessage = if (wasPromoted) {
                MSG_LEGACY_NOTICE
            } else {
                o.optString("message", "검증 기준을 충족하지 못해 기본 가중치를 유지합니다.")
            }

            val reconciled = JSONObject().apply {
                put("promoted", false)
                put("message", legacyMessage)
                put("weights", o.optJSONObject("weights") ?: JSONObject())
                put("testedDraws", o.optInt("testedDraws", 40))
                put("fullEqual", o.optDouble("fullEqual", 0.0))
                put("fullCandidate", o.optDouble("fullCandidate", 0.0))
                put("holdoutEqual", o.optDouble("holdoutEqual", 0.0))
                put("holdoutCandidate", o.optDouble("holdoutCandidate", 0.0))
                put("primaryReason", legacyReason)
                put("basePromotionPassed", o.optBoolean("basePromotionPassed", wasPromoted))
                put("candidateHoldoutTotalMatches", 0)
                put("equalHoldoutTotalMatches", 0)
                put("holdoutTotalMatchAdvantage", 0)
                put("strongEvidenceThreshold", 2)
                put("strongEvidencePassed", false)
                put("foldCount", 0)
                put("foldWins", 0)
                put("foldTies", 0)
                put("foldLosses", 0)
                put("meanFoldGain", 0.0)
                put("worstFoldGain", 0.0)
                put("finalHoldoutGain", 0.0)
                put("searchCandidateCount", 0)
                put("isLegacyRecord", true)
            }.toString()

            val backup = if (existingBackup == null) rawResearch else null
            return ReconcileResult(
                updatedResearchResult = reconciled,
                updatedResearchWeights = "",
                backupToSave = backup,
                status = ReconcileStatus.RECONCILED_LEGACY,
                reason = "Legacy record lacking Policy B evidence metadata"
            )
        }

        // Case 3: Modern Policy B record consistency check
        val inconsistencyReason = validateModernConsistency(o, rawWeights)
        if (inconsistencyReason != null) {
            val backup = if (existingBackup == null) rawResearch else null
            val reconciled = JSONObject().apply {
                put("promoted", false)
                put("message", MSG_INCONSISTENT_NOTICE)
                put("weights", o.optJSONObject("weights") ?: JSONObject())
                put("testedDraws", o.optInt("testedDraws", 40))
                put("fullEqual", o.optDouble("fullEqual", 0.0))
                put("fullCandidate", o.optDouble("fullCandidate", 0.0))
                put("holdoutEqual", o.optDouble("holdoutEqual", 0.0))
                put("holdoutCandidate", o.optDouble("holdoutCandidate", 0.0))
                put("primaryReason", "데이터 불일치 (재검증 필요)")
                put("basePromotionPassed", false)
                put("candidateHoldoutTotalMatches", 0)
                put("equalHoldoutTotalMatches", 0)
                put("holdoutTotalMatchAdvantage", 0)
                put("strongEvidenceThreshold", 2)
                put("strongEvidencePassed", false)
                put("foldCount", 0)
                put("foldWins", 0)
                put("foldTies", 0)
                put("foldLosses", 0)
                put("meanFoldGain", 0.0)
                put("worstFoldGain", 0.0)
                put("finalHoldoutGain", 0.0)
                put("searchCandidateCount", 0)
                put("isLegacyRecord", true)
            }.toString()

            return ReconcileResult(
                updatedResearchResult = reconciled,
                updatedResearchWeights = "",
                backupToSave = backup,
                status = ReconcileStatus.RECONCILED_INCONSISTENT,
                reason = inconsistencyReason
            )
        }

        // Valid Modern Record
        val promoted = o.getBoolean("promoted")
        val finalWeights = if (promoted) (rawWeights ?: "") else ""
        return ReconcileResult(
            updatedResearchResult = rawResearch,
            updatedResearchWeights = finalWeights,
            backupToSave = null,
            status = ReconcileStatus.VALID_MODERN
        )
    }

    fun validateModernConsistency(o: JSONObject, rawWeights: String?): String? {
        // 1. Strict metadata presence and types
        val rawPromoted = o.opt("promoted") ?: return "Missing promoted field"
        if (rawPromoted !is Boolean) return "promoted must be Boolean"
        val promoted = rawPromoted

        val rawBase = o.opt("basePromotionPassed") ?: return "Missing basePromotionPassed field"
        if (rawBase !is Boolean) return "basePromotionPassed must be Boolean"
        val basePromotionPassed = rawBase

        val rawStrong = o.opt("strongEvidencePassed") ?: return "Missing strongEvidencePassed field"
        if (rawStrong !is Boolean) return "strongEvidencePassed must be Boolean"
        val strongEvidencePassed = rawStrong

        val rawThreshold = o.opt("strongEvidenceThreshold") ?: return "Missing strongEvidenceThreshold field"
        if (rawThreshold !is Int) return "strongEvidenceThreshold must be Integer"
        if (rawThreshold != 2) return "strongEvidenceThreshold must be strictly 2, got $rawThreshold"

        val rawCandMatches = o.opt("candidateHoldoutTotalMatches") ?: return "Missing candidateHoldoutTotalMatches"
        if (rawCandMatches !is Int) return "candidateHoldoutTotalMatches must be Integer"
        val candMatches = rawCandMatches

        val rawEqMatches = o.opt("equalHoldoutTotalMatches") ?: return "Missing equalHoldoutTotalMatches"
        if (rawEqMatches !is Int) return "equalHoldoutTotalMatches must be Integer"
        val eqMatches = rawEqMatches

        val rawAdv = o.opt("holdoutTotalMatchAdvantage") ?: return "Missing holdoutTotalMatchAdvantage"
        if (rawAdv !is Int) return "holdoutTotalMatchAdvantage must be Integer"
        val adv = rawAdv

        val rawTested = o.opt("testedDraws") ?: return "Missing testedDraws"
        if (rawTested !is Int || rawTested < 0) return "testedDraws must be non-negative Integer, got $rawTested"
        if (promoted && (rawTested < 20 || rawTested > 60)) {
            return "promoted=true requires testedDraws in 20..60, got $rawTested"
        }

        if (candMatches < 0 || eqMatches < 0) {
            return "Negative match totals: cand=$candMatches, eq=$eqMatches"
        }

        // 2. Exact integer arithmetic for holdout totals
        if (candMatches - eqMatches != adv) {
            return "Advantage arithmetic mismatch: $candMatches - $eqMatches != $adv"
        }

        // 3. Logical consistency
        val expectedStrong = (adv >= 2)
        if (strongEvidencePassed != expectedStrong) {
            return "strongEvidencePassed ($strongEvidencePassed) != (advantage $adv >= 2)"
        }

        val expectedPromoted = (basePromotionPassed && strongEvidencePassed)
        if (promoted != expectedPromoted) {
            return "promoted ($promoted) != (base $basePromotionPassed && strong $strongEvidencePassed)"
        }

        // 4. Weight vector validations & parity
        val resultWeightsObj = o.optJSONObject("weights") ?: return "Missing weights object in research_result"
        val resultVector = parseWeightVector(resultWeightsObj)
            ?: return "Invalid weights object in research_result (missing keys, extra keys, non-finite, negative, or sum != 1.0)"

        if (promoted) {
            if (rawWeights.isNullOrBlank()) {
                return "promoted=true but active research_weights is blank"
            }
            val activeVector = parseWeightVector(rawWeights)
                ?: return "promoted=true but active research_weights is invalid (missing keys, extra keys, non-finite, negative, or sum != 1.0)"

            // Component-wise parity check within 1e-9
            for (key in MODEL_KEYS) {
                val diff = Math.abs(resultVector[key]!! - activeVector[key]!!)
                if (diff >= WEIGHT_EPSILON) {
                    return "Weight vector mismatch for key '$key': result=${resultVector[key]}, active=${activeVector[key]}, diff=$diff"
                }
            }
        } else {
            // HOLD: active weights must be empty
            if (!rawWeights.isNullOrBlank()) {
                return "promoted=false but active research_weights is non-empty"
            }
        }

        return null
    }
}
