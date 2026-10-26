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
    // No account, backend or paid API is required. Each source contains a complete history.
    private val historySources = listOf(
        "기존 원본" to "https://raw.githubusercontent.com/JunKwon91/lotto-data/main/data/lotto-history.json",
        "공개 미러 A" to "https://smok95.github.io/lotto/results/all.json",
        "공개 미러 B" to "https://papaya5rhw1984.github.io/lotto-data/all.json"
    )

    suspend fun ensureData(): String = withContext(Dispatchers.IO) {
        val before = db.latestDraw()
        val expected = DrawHistoryPolicy.expectedCompletedDraw()
        val savedHistory = if (before > 0) db.historyJson() else null
        var best: DrawHistorySnapshot? = null
        var sourceUsed = ""
        val failures = mutableListOf<String>()

        for ((name, url) in historySources) {
            try {
                val incoming = DrawHistoryPolicy.parse(fetchText(url))
                if (incoming.latestDraw < before) {
                    failures.add(name + ": 저장 데이터보다 오래됨 (" + incoming.latestDraw + "회)")
                    continue
                }
                if (savedHistory != null &&
                    !DrawHistoryPolicy.matchingOverlap(savedHistory, incoming)) {
                    failures.add(name + ": 기존 당첨 결과와 불일치")
                    continue
                }
                if (best == null || incoming.latestDraw > best.latestDraw) {
                    best = incoming
                    sourceUsed = name
                }
                if (incoming.latestDraw >= expected) break
            } catch (e: Exception) {
                failures.add(name + ": " + (e.message ?: "조회 실패").take(100))
            }
        }

        val chosen = best
        if (chosen != null && chosen.latestDraw > before) {
            // replaceHistory changes only the draws table, inside one SQL transaction.
            // Confirmed tickets and research state stay untouched.
            db.replaceHistory(chosen.payload)
        }
        val latest = db.latestDraw()
        if (latest == 0) {
            throw IllegalStateException("당첨 데이터를 가져올 수 없습니다. " + failures.joinToString("; "))
        }
        when {
            latest < expected ->
                "⚠️ 데이터 지연: " + latest + "회까지 저장됨 · 현재 " + expected +
                    "회 결과 필요. 구매 전 갱신을 확인하세요. " +
                    failures.take(2).joinToString("; ")
            chosen != null && chosen.latestDraw > before ->
                "최신 " + latest + "회 업데이트 완료 · " + sourceUsed
            chosen != null ->
                "최신 " + latest + "회 확인 완료 · " + sourceUsed
            else ->
                "저장된 " + latest + "회 데이터 사용 · 온라인 확인 실패 (" +
                    failures.take(2).joinToString("; ") + ")"
        }
    }

    private fun fetchText(url: String): String {
        val conn = java.net.URL(url).openConnection() as java.net.HttpURLConnection
        conn.connectTimeout = 8000
        conn.readTimeout = 20000
        conn.requestMethod = "GET"
        conn.setRequestProperty("User-Agent", "LottoLabMobile/1.2")
        conn.setRequestProperty("Cache-Control", "no-cache")
        return try {
            if (conn.responseCode !in 200..299) {
                throw IllegalStateException("HTTP " + conn.responseCode)
            }
            conn.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
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
