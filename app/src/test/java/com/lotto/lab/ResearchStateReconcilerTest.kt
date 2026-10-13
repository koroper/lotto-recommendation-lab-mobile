package com.lotto.lab

import com.lotto.lab.data.ReconcileStatus
import com.lotto.lab.data.ResearchStateReconciler
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ResearchStateReconcilerTest {

    private val validWeightsJson = """{"long":0.20,"recent":0.20,"gap":0.20,"pair":0.15,"balance":0.10,"inverse":0.15}"""
    private val exactEqualWeightsJson = JSONObject().apply {
        put("long", 1.0 / 6)
        put("recent", 1.0 / 6)
        put("gap", 1.0 / 6)
        put("pair", 1.0 / 6)
        put("balance", 1.0 / 6)
        put("inverse", 1.0 / 6)
    }.toString()

    private fun createBaseValidModernPromote(): JSONObject {
        return JSONObject().apply {
            put("promoted", true)
            put("message", "빠른 연구 보정 가중치를 적용합니다.")
            put("weights", JSONObject(validWeightsJson))
            put("testedDraws", 40)
            put("fullEqual", 0.775)
            put("fullCandidate", 0.850)
            put("holdoutEqual", 0.700)
            put("holdoutCandidate", 0.900)
            put("basePromotionPassed", true)
            put("candidateHoldoutTotalMatches", 9)
            put("equalHoldoutTotalMatches", 7)
            put("holdoutTotalMatchAdvantage", 2)
            put("strongEvidenceThreshold", 2)
            put("strongEvidencePassed", true)
            put("isLegacyRecord", false)
        }
    }

    private fun createBaseValidModernHold(): JSONObject {
        return JSONObject().apply {
            put("promoted", false)
            put("message", "기준 미달")
            put("weights", JSONObject(exactEqualWeightsJson))
            put("testedDraws", 40)
            put("fullEqual", 0.775)
            put("fullCandidate", 0.800)
            put("holdoutEqual", 0.700)
            put("holdoutCandidate", 0.700)
            put("primaryReason", "최종 홀드아웃 미개선")
            put("basePromotionPassed", false)
            put("candidateHoldoutTotalMatches", 7)
            put("equalHoldoutTotalMatches", 7)
            put("holdoutTotalMatchAdvantage", 0)
            put("strongEvidenceThreshold", 2)
            put("strongEvidencePassed", false)
            put("isLegacyRecord", false)
        }
    }

    @Test
    fun testValidStrongPromotion() {
        val valid = createBaseValidModernPromote().toString()
        val result = ResearchStateReconciler.reconcile(valid, validWeightsJson, null)
        assertEquals(ReconcileStatus.VALID_MODERN, result.status)
        assertEquals(validWeightsJson, result.updatedResearchWeights)
        assertNull(result.backupToSave)
    }

    @Test
    fun testValidModernHold() {
        val valid = createBaseValidModernHold().toString()
        val result = ResearchStateReconciler.reconcile(valid, "", null)
        assertEquals(ReconcileStatus.VALID_MODERN, result.status)
        assertEquals("", result.updatedResearchWeights)
        assertNull(result.backupToSave)
    }

    @Test
    fun testDifferentWeightVectorsBothSumToOne_neutralized() {
        // Both vectors sum to 1.0, but components differ
        val activeDifferentWeights = """{"long":0.25,"recent":0.15,"gap":0.20,"pair":0.15,"balance":0.10,"inverse":0.15}"""
        val record = createBaseValidModernPromote().toString()

        val result = ResearchStateReconciler.reconcile(record, activeDifferentWeights, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result.status)
        assertEquals("", result.updatedResearchWeights)
        assertEquals(record, result.backupToSave)
        assertTrue(result.reason!!.contains("Weight vector mismatch"))
    }

    @Test
    fun testReorderedJsonKeysWithIdenticalValues_accepted() {
        // Keys in completely reversed order
        val reorderedWeights = """{"inverse":0.15,"balance":0.10,"pair":0.15,"gap":0.20,"recent":0.20,"long":0.20}"""
        val record = createBaseValidModernPromote().toString()

        val result = ResearchStateReconciler.reconcile(record, reorderedWeights, null)
        assertEquals(ReconcileStatus.VALID_MODERN, result.status)
        assertEquals(reorderedWeights, result.updatedResearchWeights)
        assertNull(result.backupToSave)
    }

    @Test
    fun testMissingModelKey_rejected() {
        // Missing "inverse" key
        val incompleteWeights = """{"long":0.25,"recent":0.25,"gap":0.25,"pair":0.15,"balance":0.10}"""
        val record = createBaseValidModernPromote().apply {
            put("weights", JSONObject(incompleteWeights))
        }.toString()

        val result = ResearchStateReconciler.reconcile(record, incompleteWeights, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result.status)
        assertEquals("", result.updatedResearchWeights)
    }

    @Test
    fun testExtraModelKey_rejected() {
        // Extra key "extra"
        val extraWeights = """{"long":0.20,"recent":0.20,"gap":0.20,"pair":0.15,"balance":0.10,"inverse":0.15,"extra":0.0}"""
        val record = createBaseValidModernPromote().apply {
            put("weights", JSONObject(extraWeights))
        }.toString()

        val result = ResearchStateReconciler.reconcile(record, extraWeights, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result.status)
        assertEquals("", result.updatedResearchWeights)
    }

    @Test
    fun testWeightSum096And104_rejected() {
        // Sum 0.96
        val sum096 = """{"long":0.16,"recent":0.20,"gap":0.20,"pair":0.15,"balance":0.10,"inverse":0.15}"""
        val record096 = createBaseValidModernPromote().apply {
            put("weights", JSONObject(sum096))
        }.toString()
        val result096 = ResearchStateReconciler.reconcile(record096, sum096, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result096.status)

        // Sum 1.04
        val sum104 = """{"long":0.24,"recent":0.20,"gap":0.20,"pair":0.15,"balance":0.10,"inverse":0.15}"""
        val record104 = createBaseValidModernPromote().apply {
            put("weights", JSONObject(sum104))
        }.toString()
        val result104 = ResearchStateReconciler.reconcile(record104, sum104, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result104.status)
    }

    @Test
    fun testNonNumericAndNegativeWeights_rejected() {
        // String value instead of number
        val stringValWeights = """{"long":"0.20","recent":0.20,"gap":0.20,"pair":0.15,"balance":0.10,"inverse":0.15}"""
        val recordStr = createBaseValidModernPromote().apply {
            put("weights", JSONObject(stringValWeights))
        }.toString()
        val resultStr = ResearchStateReconciler.reconcile(recordStr, stringValWeights, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultStr.status)

        // Negative weight
        val negativeWeights = """{"long":-0.10,"recent":0.30,"gap":0.30,"pair":0.20,"balance":0.15,"inverse":0.15}"""
        val recordNeg = createBaseValidModernPromote().apply {
            put("weights", JSONObject(negativeWeights))
        }.toString()
        val resultNeg = ResearchStateReconciler.reconcile(recordNeg, negativeWeights, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultNeg.status)
    }

    @Test
    fun testIncorrectStrongEvidenceThreshold_rejected() {
        // Threshold = 1
        val record1 = createBaseValidModernPromote().apply {
            put("strongEvidenceThreshold", 1)
        }.toString()
        val result1 = ResearchStateReconciler.reconcile(record1, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result1.status)
        assertTrue(result1.reason!!.contains("strongEvidenceThreshold must be strictly 2"))

        // Threshold = 3
        val record3 = createBaseValidModernPromote().apply {
            put("strongEvidenceThreshold", 3)
        }.toString()
        val result3 = ResearchStateReconciler.reconcile(record3, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, result3.status)
        assertTrue(result3.reason!!.contains("strongEvidenceThreshold must be strictly 2"))
    }

    @Test
    fun testContradictoryStrongEvidencePassedFlag_rejected() {
        // Advantage = 1 but strongEvidencePassed = true
        val recordAdv1 = createBaseValidModernPromote().apply {
            put("candidateHoldoutTotalMatches", 8)
            put("equalHoldoutTotalMatches", 7)
            put("holdoutTotalMatchAdvantage", 1)
            put("strongEvidencePassed", true)
        }.toString()
        val resultAdv1 = ResearchStateReconciler.reconcile(recordAdv1, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultAdv1.status)

        // Advantage = 2 but strongEvidencePassed = false
        val recordAdv2 = createBaseValidModernPromote().apply {
            put("candidateHoldoutTotalMatches", 9)
            put("equalHoldoutTotalMatches", 7)
            put("holdoutTotalMatchAdvantage", 2)
            put("strongEvidencePassed", false)
            put("promoted", false)
        }.toString()
        val resultAdv2 = ResearchStateReconciler.reconcile(recordAdv2, "", null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultAdv2.status)
    }

    @Test
    fun testContradictoryPromotedAndBasePromotionPassed_rejected() {
        // basePromotionPassed = false, strongEvidencePassed = true, but promoted = true
        val recordBaseFalse = createBaseValidModernPromote().apply {
            put("basePromotionPassed", false)
            put("promoted", true)
        }.toString()
        val resultBaseFalse = ResearchStateReconciler.reconcile(recordBaseFalse, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultBaseFalse.status)

        // basePromotionPassed = true, strongEvidencePassed = true, but promoted = false
        val recordPromoteFalse = createBaseValidModernPromote().apply {
            put("basePromotionPassed", true)
            put("strongEvidencePassed", true)
            put("promoted", false)
        }.toString()
        val resultPromoteFalse = ResearchStateReconciler.reconcile(recordPromoteFalse, "", null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultPromoteFalse.status)
    }

    @Test
    fun testMissingOrWrongTypeRequiredMetadata_rejected() {
        // promoted is String instead of Boolean
        val recordWrongType = createBaseValidModernPromote().apply {
            put("promoted", "true")
        }.toString()
        val resultWrongType = ResearchStateReconciler.reconcile(recordWrongType, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultWrongType.status)

        // candidateHoldoutTotalMatches is String instead of Int
        val recordStrMatches = createBaseValidModernPromote().apply {
            put("candidateHoldoutTotalMatches", "9")
        }.toString()
        val resultStrMatches = ResearchStateReconciler.reconcile(recordStrMatches, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_INCONSISTENT, resultStrMatches.status)
    }

    @Test
    fun testSafeLegacyHoldAfterReconciliation() {
        val legacy = JSONObject().apply {
            put("promoted", true)
            put("weights", JSONObject(validWeightsJson))
        }.toString()

        val result = ResearchStateReconciler.reconcile(legacy, validWeightsJson, null)
        assertEquals(ReconcileStatus.RECONCILED_LEGACY, result.status)
        assertEquals("", result.updatedResearchWeights)
        assertNotNull(result.backupToSave)

        val reconciled = JSONObject(result.updatedResearchResult!!)
        assertFalse(reconciled.getBoolean("promoted"))
        assertTrue(reconciled.getBoolean("isLegacyRecord"))
        assertEquals("재검증 필요", reconciled.getString("primaryReason"))
    }

    @Test
    fun testIdempotentReconciliation() {
        val legacy = JSONObject().apply {
            put("promoted", true)
            put("weights", JSONObject(validWeightsJson))
        }.toString()

        val first = ResearchStateReconciler.reconcile(legacy, validWeightsJson, null)
        val backup = first.backupToSave!!
        val reconciled = first.updatedResearchResult!!

        val second = ResearchStateReconciler.reconcile(reconciled, "", backup)
        assertEquals(ReconcileStatus.VALID_MODERN, second.status)
        assertEquals("", second.updatedResearchWeights)
        assertNull(second.backupToSave)
    }

    @Test
    fun testReducedHistoryResearchSurvives_100_105_110_119() {
        // Histories 100, 105, 110, 119 correspond to testedDraws 20, 25, 30, 39
        val testedDrawsList = listOf(20, 25, 30, 39)
        for (tested in testedDrawsList) {
            val validRecord = createBaseValidModernPromote().apply {
                put("testedDraws", tested)
            }.toString()

            val result = ResearchStateReconciler.reconcile(validRecord, validWeightsJson, null)
            assertEquals("testedDraws $tested must be VALID_MODERN", ReconcileStatus.VALID_MODERN, result.status)
            assertEquals(validWeightsJson, result.updatedResearchWeights)
            assertNull(result.backupToSave)
        }
    }

    @Test
    fun testInsufficientHistoryHoldSurvives_lessThan100Draws() {
        // Insufficient history (< 100 draws, e.g. 60 or 80) returns promoted=false, primaryReason="검증 이력 부족"
        val insufficientHistoryHold = JSONObject().apply {
            put("promoted", false)
            put("message", "검증 이력 부족으로 기본 가중치를 유지합니다. (최소 100회 이상 필요)")
            put("weights", JSONObject(exactEqualWeightsJson))
            put("testedDraws", 85)
            put("fullEqual", 0.0)
            put("fullCandidate", 0.0)
            put("holdoutEqual", 0.0)
            put("holdoutCandidate", 0.0)
            put("primaryReason", "검증 이력 부족")
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
            put("isLegacyRecord", false)
        }.toString()

        val result = ResearchStateReconciler.reconcile(insufficientHistoryHold, "", null)
        assertEquals(ReconcileStatus.VALID_MODERN, result.status)
        assertEquals("", result.updatedResearchWeights)
        assertNull(result.backupToSave)
    }

    @Test
    fun testLegacyContradictoryPromotedTrue_neutralized() {
        // Record marked isLegacyRecord=true, but contradictory promoted=true
        val contradictoryLegacy = JSONObject().apply {
            put("promoted", true) // Contradiction on legacy!
            put("isLegacyRecord", true)
            put("message", "이전 연구")
            put("weights", JSONObject(validWeightsJson))
            put("testedDraws", 40)
            put("strongEvidencePassed", false)
            put("holdoutTotalMatchAdvantage", 0)
            put("strongEvidenceThreshold", 2)
        }.toString()

        val result = ResearchStateReconciler.reconcile(contradictoryLegacy, validWeightsJson, null)
        assertEquals(ReconcileStatus.VALID_MODERN, result.status)
        assertEquals("", result.updatedResearchWeights)

        val updated = JSONObject(result.updatedResearchResult!!)
        assertFalse("promoted must be corrected to false", updated.getBoolean("promoted"))
        assertEquals("재검증 필요", updated.getString("primaryReason"))
        assertEquals(ResearchStateReconciler.MSG_LEGACY_NOTICE, updated.getString("message"))
    }

    @Test
    fun testDirectKotlinRoundtrip_persistsAllDisplayedMetrics() {
        val original = JSONObject().apply {
            put("promoted", true)
            put("message", "보정 적용")
            put("weights", JSONObject(validWeightsJson))
            put("testedDraws", 40)
            put("fullEqual", 0.775)
            put("fullCandidate", 0.850)
            put("holdoutEqual", 0.700)
            put("holdoutCandidate", 0.900)
            put("basePromotionPassed", true)
            put("candidateHoldoutTotalMatches", 9)
            put("equalHoldoutTotalMatches", 7)
            put("holdoutTotalMatchAdvantage", 2)
            put("strongEvidenceThreshold", 2)
            put("strongEvidencePassed", true)
            put("foldCount", 3)
            put("foldWins", 2)
            put("foldTies", 1)
            put("foldLosses", 0)
            put("meanFoldGain", 0.075)
            put("worstFoldGain", 0.010)
            put("finalHoldoutGain", 0.200)
            put("searchCandidateCount", 12)
            put("selectedCandidateWeights", JSONObject(validWeightsJson))
            put("searchMethod", "deterministic_pairwise_local_search")
            put("isLegacyRecord", false)
        }

        val jsonStr = original.toString()
        val reconciled = ResearchStateReconciler.reconcile(jsonStr, validWeightsJson, null)
        assertEquals(ReconcileStatus.VALID_MODERN, reconciled.status)

        // Verify all metrics survive in reconciled result
        val parsed = JSONObject(reconciled.updatedResearchResult!!)
        assertEquals(3, parsed.getInt("foldCount"))
        assertEquals(2, parsed.getInt("foldWins"))
        assertEquals(1, parsed.getInt("foldTies"))
        assertEquals(0, parsed.getInt("foldLosses"))
        assertEquals(0.075, parsed.getDouble("meanFoldGain"), 1e-9)
        assertEquals(0.010, parsed.getDouble("worstFoldGain"), 1e-9)
        assertEquals(0.200, parsed.getDouble("finalHoldoutGain"), 1e-9)
        assertEquals(12, parsed.getInt("searchCandidateCount"))
        assertEquals("deterministic_pairwise_local_search", parsed.getString("searchMethod"))
        assertNotNull(parsed.getJSONObject("selectedCandidateWeights"))
    }
}
