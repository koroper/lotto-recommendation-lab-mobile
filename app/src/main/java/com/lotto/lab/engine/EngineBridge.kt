package com.lotto.lab.engine

import com.chaquo.python.Python
import com.lotto.lab.*
import org.json.JSONObject

object EngineBridge {
    private fun module() = Python.getInstance().getModule("mobile_engine")

    fun recommend(
        historyJson: String,
        weightsJson: String?,
        games: Int,
        style: String
    ): RecommendationResult {
        val config = JSONObject()
            .put("games", games)
            .put("style", style)
            .toString()

        val raw = module().callAttr(
            "recommend",
            historyJson,
            weightsJson ?: "",
            config
        ).toString()

        val o = JSONObject(raw)
        val gamesArray = o.getJSONArray("games")
        val gamesList = (0 until gamesArray.length()).map { i ->
            val g = gamesArray.getJSONObject(i)
            GameResult(
                index = g.getInt("index"),
                numbers = (0 until g.getJSONArray("numbers").length())
                    .map { g.getJSONArray("numbers").getInt(it) },
                score = g.getDouble("score"),
                rank = g.getInt("rank"),
                total = g.getInt("total"),
                percentile = g.getDouble("percentile")
            )
        }
        val c = o.getJSONObject("confidence")

        return RecommendationResult(
            latestDraw = o.getInt("latestDraw"),
            latestDate = o.getString("latestDate"),
            targetDraw = o.getInt("targetDraw"),
            recommendationId = o.getString("recommendationId"),
            games = gamesList,
            core = o.getJSONArray("core").toIntList(),
            semiCore = o.getJSONArray("semiCore").toIntList(),
            axis = o.getJSONArray("axis").toIntList(),
            candidatePool = o.getJSONArray("candidatePool").toIntList(),
            confidence = Confidence(
                score = c.getDouble("score"),
                label = c.getString("label"),
                agreement = c.getDouble("agreement"),
                rankConsistency = c.getDouble("rankConsistency"),
                separation = c.getDouble("separation")
            ),
            weightsJson = o.getJSONObject("weights").toString()
        )
    }

    fun quickResearch(historyJson: String, testDraws: Int = 40): ResearchResult {
        val raw = module().callAttr("quick_research", historyJson, testDraws).toString()
        val o = JSONObject(raw)
        val foldsArray = o.optJSONArray("folds")
        val foldsList = if (foldsArray != null) {
            (0 until foldsArray.length()).map { i ->
                val f = foldsArray.getJSONObject(i)
                ValidationFold(
                    fold = f.getInt("fold"),
                    trainDraws = f.getInt("trainDraws"),
                    valDraws = f.getInt("valDraws"),
                    baseScore = f.getDouble("baseScore"),
                    candidateScore = f.getDouble("candidateScore"),
                    gain = f.getDouble("gain")
                )
            }
        } else {
            emptyList()
        }

        return ResearchResult(
            promoted = o.getBoolean("promoted"),
            message = o.getString("message"),
            weightsJson = o.getJSONObject("weights").toString(),
            testedDraws = o.optInt("testedDraws", 0),
            fullEqual = o.optDouble("fullEqual", 0.0),
            fullCandidate = o.optDouble("fullCandidate", 0.0),
            holdoutEqual = o.optDouble("holdoutEqual", 0.0),
            holdoutCandidate = o.optDouble("holdoutCandidate", 0.0),
            foldCount = o.optInt("foldCount", foldsList.size),
            foldWins = o.optInt("foldWins", 0),
            foldTies = o.optInt("foldTies", 0),
            foldLosses = o.optInt("foldLosses", 0),
            meanFoldGain = o.optDouble("meanFoldGain", 0.0),
            worstFoldGain = o.optDouble("worstFoldGain", 0.0),
            finalHoldoutGain = o.optDouble("finalHoldoutGain", o.optDouble("holdoutGain", 0.0)),
            primaryReason = if (o.has("primaryReason") && !o.isNull("primaryReason")) o.getString("primaryReason") else null,
            folds = foldsList
        )
    }
}

private fun org.json.JSONArray.toIntList(): List<Int> =
    (0 until length()).map { getInt(it) }
