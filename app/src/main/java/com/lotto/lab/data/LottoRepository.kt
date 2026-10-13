package com.lotto.lab.data

import android.content.Context
import com.lotto.lab.*
import com.lotto.lab.engine.EngineBridge
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class LottoRepository(context: Context) {
    private val db = LottoDb(context.applicationContext)
    private val dataUrl =
        "https://raw.githubusercontent.com/JunKwon91/lotto-data/main/data/lotto-history.json"

    suspend fun ensureData(): String = withContext(Dispatchers.IO) {
        val before = db.latestDraw()
        try {
            val payload = fetchPayload()
            validatePayload(payload)
            val data = payload.getJSONArray("data")
            var onlineLatest = 0
            for (i in 0 until data.length()) {
                onlineLatest = maxOf(onlineLatest, data.getJSONObject(i).getInt("drawNo"))
            }
            if (db.drawCount() == 0 || onlineLatest > before) {
                db.replaceHistory(payload)
                "최신 ${db.latestDraw()}회까지 업데이트 완료"
            } else {
                "최신 ${before}회 데이터 사용"
            }
        } catch (e: Exception) {
            if (db.drawCount() == 0) throw e
            "네트워크 업데이트 실패 · 저장된 ${before}회 데이터 사용"
        }
    }

    private fun validatePayload(payload: JSONObject) {
        val data = payload.optJSONArray("data") ?: throw IllegalStateException("당첨 데이터의 data 배열이 없습니다.")
        if (data.length() < 60) throw IllegalStateException("당첨 데이터가 너무 적습니다: ${data.length()}회")
        val seen = mutableSetOf<Int>()
        for (i in 0 until data.length()) {
            val item = data.getJSONObject(i); val draw = item.getInt("drawNo")
            if (!seen.add(draw)) throw IllegalStateException("중복 회차: ${draw}회")
            val nums = item.getJSONArray("numbers")
            if (nums.length()!=6) throw IllegalStateException("${draw}회 번호 개수가 6개가 아닙니다.")
            val set=mutableSetOf<Int>()
            for (j in 0 until 6) { val n=nums.getInt(j); if (n !in 1..45 || !set.add(n)) throw IllegalStateException("${draw}회 번호 데이터가 올바르지 않습니다.") }
            val bonus=item.getInt("bonusNo"); if (bonus !in 1..45 || bonus in set) throw IllegalStateException("${draw}회 보너스 번호가 올바르지 않습니다.")
        }
    }

    private fun fetchPayload(): JSONObject {
        val conn = URL(dataUrl).openConnection() as HttpURLConnection
        conn.connectTimeout = 15000
        conn.readTimeout = 25000
        conn.requestMethod = "GET"
        conn.setRequestProperty("User-Agent", "LottoLabMobile/1.0")
        return try {
            if (conn.responseCode !in 200..299) {
                throw IllegalStateException("데이터 서버 응답 ${conn.responseCode}")
            }
            val text = conn.inputStream.bufferedReader().use { it.readText() }
            JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }

    companion object {
        const val KEY_RESEARCH_RESULT = ResearchStateReconciler.KEY_RESEARCH_RESULT
        const val KEY_RESEARCH_WEIGHTS = ResearchStateReconciler.KEY_RESEARCH_WEIGHTS
        const val KEY_LEGACY_BACKUP = ResearchStateReconciler.KEY_LEGACY_BACKUP
        const val MSG_LEGACY_NOTICE = ResearchStateReconciler.MSG_LEGACY_NOTICE
    }

    init {
        reconcileLegacyResearchState()
    }

    fun reconcileLegacyResearchState() {
        val rawResearch = db.loadState(KEY_RESEARCH_RESULT)
        val rawWeights = db.loadState(KEY_RESEARCH_WEIGHTS)
        val existingBackup = db.loadState(KEY_LEGACY_BACKUP)

        val result = ResearchStateReconciler.reconcile(rawResearch, rawWeights, existingBackup)

        if (result.backupToSave != null) {
            db.saveState(KEY_LEGACY_BACKUP, result.backupToSave)
        }
        if (result.updatedResearchWeights != (rawWeights ?: "")) {
            db.saveState(KEY_RESEARCH_WEIGHTS, result.updatedResearchWeights)
        }
        if (result.updatedResearchResult != null && result.updatedResearchResult != rawResearch) {
            db.saveState(KEY_RESEARCH_RESULT, result.updatedResearchResult)
        }
    }

    suspend fun recommend(games: Int, style: String): RecommendationResult =
        withContext(Dispatchers.Default) {
            reconcileLegacyResearchState()
            EngineBridge.recommend(
                db.historyJson(),
                db.loadState(KEY_RESEARCH_WEIGHTS),
                games,
                style
            )
        }

    suspend fun runResearch(): ResearchResult = withContext(Dispatchers.Default) {
        val result = EngineBridge.quickResearch(db.historyJson(), 40)
        db.saveState(KEY_RESEARCH_RESULT, JSONObject().apply {
            put("promoted", result.promoted)
            put("message", result.message)
            put("weights", JSONObject(result.weightsJson))
            put("testedDraws", result.testedDraws)
            put("fullEqual", result.fullEqual)
            put("fullCandidate", result.fullCandidate)
            put("holdoutEqual", result.holdoutEqual)
            put("holdoutCandidate", result.holdoutCandidate)
            put("primaryReason", result.primaryReason)
            put("basePromotionPassed", result.basePromotionPassed)
            put("candidateHoldoutTotalMatches", result.candidateHoldoutTotalMatches)
            put("equalHoldoutTotalMatches", result.equalHoldoutTotalMatches)
            put("holdoutTotalMatchAdvantage", result.holdoutTotalMatchAdvantage)
            put("strongEvidenceThreshold", result.strongEvidenceThreshold)
            put("strongEvidencePassed", result.strongEvidencePassed)
            put("foldCount", result.foldCount)
            put("foldWins", result.foldWins)
            put("foldTies", result.foldTies)
            put("foldLosses", result.foldLosses)
            put("meanFoldGain", result.meanFoldGain)
            put("worstFoldGain", result.worstFoldGain)
            put("finalHoldoutGain", result.finalHoldoutGain)
            put("searchCandidateCount", result.searchCandidateCount)
            if (result.selectedCandidateWeightsJson != null) {
                put("selectedCandidateWeights", JSONObject(result.selectedCandidateWeightsJson))
            }
            if (result.searchMethod != null) {
                put("searchMethod", result.searchMethod)
            }
            put("isLegacyRecord", false)
        }.toString())
        if (result.promoted) db.saveState(KEY_RESEARCH_WEIGHTS, result.weightsJson)
        else db.saveState(KEY_RESEARCH_WEIGHTS, "")
        result
    }

    fun savedResearch(): ResearchResult? {
        reconcileLegacyResearchState()
        val raw = db.loadState(KEY_RESEARCH_RESULT) ?: return null
        if (raw.isBlank()) return null
        val o = JSONObject(raw)
        val isLegacy = o.optBoolean("isLegacyRecord", false)
        val promoted = if (isLegacy) false else o.getBoolean("promoted")
        return ResearchResult(
            promoted = promoted,
            message = o.getString("message"),
            weightsJson = o.getJSONObject("weights").toString(),
            testedDraws = o.getInt("testedDraws"),
            fullEqual = o.getDouble("fullEqual"),
            fullCandidate = o.getDouble("fullCandidate"),
            holdoutEqual = o.getDouble("holdoutEqual"),
            holdoutCandidate = o.getDouble("holdoutCandidate"),
            primaryReason = if (o.has("primaryReason") && !o.isNull("primaryReason")) o.getString("primaryReason") else null,
            basePromotionPassed = o.optBoolean("basePromotionPassed", o.optBoolean("promoted", false)),
            candidateHoldoutTotalMatches = o.optInt("candidateHoldoutTotalMatches", 0),
            equalHoldoutTotalMatches = o.optInt("equalHoldoutTotalMatches", 0),
            holdoutTotalMatchAdvantage = o.optInt("holdoutTotalMatchAdvantage", 0),
            strongEvidenceThreshold = o.optInt("strongEvidenceThreshold", 2),
            strongEvidencePassed = o.optBoolean("strongEvidencePassed", false),
            isLegacyRecord = isLegacy,
            foldCount = o.optInt("foldCount", 0),
            foldWins = o.optInt("foldWins", 0),
            foldTies = o.optInt("foldTies", 0),
            foldLosses = o.optInt("foldLosses", 0),
            meanFoldGain = o.optDouble("meanFoldGain", 0.0),
            worstFoldGain = o.optDouble("worstFoldGain", 0.0),
            finalHoldoutGain = o.optDouble("finalHoldoutGain", 0.0),
            searchCandidateCount = o.optInt("searchCandidateCount", 0),
            selectedCandidateWeightsJson = if (o.has("selectedCandidateWeights") && !o.isNull("selectedCandidateWeights")) o.getJSONObject("selectedCandidateWeights").toString() else null,
            searchMethod = if (o.has("searchMethod") && !o.isNull("searchMethod")) o.getString("searchMethod") else null
        )
    }

    fun confirm(rec: RecommendationResult) {
        val payload = JSONObject().apply {
            put("recommendationId", rec.recommendationId)
            put("targetDraw", rec.targetDraw)
            put("games", org.json.JSONArray().apply {
                rec.games.forEach { g ->
                    put(JSONObject().apply {
                        put("index", g.index)
                        put("numbers", org.json.JSONArray(g.numbers))
                        put("score", g.score)
                    })
                }
            })
        }
        db.saveRecommendation(
            rec.targetDraw,
            rec.recommendationId,
            payload.toString()
        )
    }

    fun confirmedRecommendationId(draw: Int): String? = db.confirmedRecommendationId(draw)

    fun isConfirmed(draw: Int): Boolean = db.confirmed(draw)

    fun records(): List<ConfirmedRecord> {
        return db.listConfirmed().map { row ->
            val draw = row.first
            val id = row.second
            val payload = row.third.first
            val whenMs = row.third.second
            val winData = db.drawResult(draw)
            val evaluation = if (winData == null) null else {
                val winningNumbers = winData.first
                val bonus = winData.second
                val gamesJson = JSONObject(payload).getJSONArray("games")
                val parsedGames = mutableListOf<Pair<Int, List<Int>>>()
                for (i in 0 until gamesJson.length()) {
                    val g = gamesJson.getJSONObject(i)
                    val idx = g.optInt("index", i + 1)
                    val nums = g.getJSONArray("numbers")
                    val numbersList = (0 until nums.length()).map { nums.getInt(it) }
                    parsedGames += idx to numbersList
                }
                ConfirmedTicketEvaluator.evaluateDraw(winningNumbers, bonus, parsedGames)
            }
            val best = evaluation?.bestMatchCount
            ConfirmedRecord(draw, id, payload, whenMs, best, evaluation)
        }
    }
}
