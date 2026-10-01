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

    suspend fun recommend(games: Int, style: String): RecommendationResult =
        withContext(Dispatchers.Default) {
            EngineBridge.recommend(
                db.historyJson(),
                db.loadState("research_weights"),
                games,
                style
            )
        }

    suspend fun runResearch(): ResearchResult = withContext(Dispatchers.Default) {
        val result = EngineBridge.quickResearch(db.historyJson(), 40)
        db.saveState("research_result", JSONObject().apply {
            put("promoted", result.promoted)
            put("message", result.message)
            put("weights", JSONObject(result.weightsJson))
            put("testedDraws", result.testedDraws)
            put("fullEqual", result.fullEqual)
            put("fullCandidate", result.fullCandidate)
            put("holdoutEqual", result.holdoutEqual)
            put("holdoutCandidate", result.holdoutCandidate)
        }.toString())
        if (result.promoted) db.saveState("research_weights", result.weightsJson)
        else db.saveState("research_weights", "")
        result
    }

    fun savedResearch(): ResearchResult? {
        val raw = db.loadState("research_result") ?: return null
        val o = JSONObject(raw)
        return ResearchResult(
            promoted = o.getBoolean("promoted"),
            message = o.getString("message"),
            weightsJson = o.getJSONObject("weights").toString(),
            testedDraws = o.getInt("testedDraws"),
            fullEqual = o.getDouble("fullEqual"),
            fullCandidate = o.getDouble("fullCandidate"),
            holdoutEqual = o.getDouble("holdoutEqual"),
            holdoutCandidate = o.getDouble("holdoutCandidate")
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
            val actual = db.winningNumbers(draw)
            val best = if (actual == null) null else {
                val games = JSONObject(payload).getJSONArray("games")
                var bestMatch = 0
                for (i in 0 until games.length()) {
                    val nums = games.getJSONObject(i).getJSONArray("numbers")
                    val set = (0 until nums.length()).map { nums.getInt(it) }.toSet()
                    bestMatch = maxOf(bestMatch, set.intersect(actual).size)
                }
                bestMatch
            }
            ConfirmedRecord(draw, id, payload, whenMs, best)
        }
    }
}
