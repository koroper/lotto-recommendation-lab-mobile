package com.lotto.lab

enum class PrizeTier(val label: String, val order: Int) {
    FIRST("1등", 1),
    SECOND("2등", 2),
    THIRD("3등", 3),
    FOURTH("4등", 4),
    FIFTH("5등", 5),
    NONE("미당첨", 6);

    companion object {
        fun evaluate(mainMatchCount: Int, hasBonus: Boolean): PrizeTier = when {
            mainMatchCount == 6 -> FIRST
            mainMatchCount == 5 && hasBonus -> SECOND
            mainMatchCount == 5 -> THIRD
            mainMatchCount == 4 -> FOURTH
            mainMatchCount == 3 -> FIFTH
            else -> NONE
        }
    }
}

data class ConfirmedGameEvaluation(
    val index: Int,
    val numbers: List<Int>,
    val matchedMainNumbers: List<Int>,
    val mainMatchCount: Int,
    val hasBonus: Boolean,
    val prizeTier: PrizeTier
)

data class DrawEvaluation(
    val winningNumbers: List<Int>,
    val bonus: Int,
    val games: List<ConfirmedGameEvaluation>,
    val bestTier: PrizeTier,
    val bestMatchCount: Int
)

object ConfirmedTicketEvaluator {
    fun evaluateGame(
        index: Int,
        numbers: List<Int>,
        winningNumbers: List<Int>,
        bonus: Int
    ): ConfirmedGameEvaluation {
        val winningSet = winningNumbers.toSet()
        val matched = numbers.filter { it in winningSet }
        val matchCount = matched.size
        val hasBonus = numbers.contains(bonus)
        val tier = PrizeTier.evaluate(matchCount, hasBonus)
        return ConfirmedGameEvaluation(
            index = index,
            numbers = numbers,
            matchedMainNumbers = matched,
            mainMatchCount = matchCount,
            hasBonus = hasBonus,
            prizeTier = tier
        )
    }

    fun evaluateDraw(
        winningNumbers: List<Int>,
        bonus: Int,
        rawGames: List<Pair<Int, List<Int>>>
    ): DrawEvaluation {
        val games = rawGames.map { (index, numbers) ->
            evaluateGame(index, numbers, winningNumbers, bonus)
        }
        val bestTier = games.minByOrNull { it.prizeTier.order }?.prizeTier ?: PrizeTier.NONE
        val bestMatchCount = games.maxOfOrNull { it.mainMatchCount } ?: 0
        return DrawEvaluation(
            winningNumbers = winningNumbers,
            bonus = bonus,
            games = games,
            bestTier = bestTier,
            bestMatchCount = bestMatchCount
        )
    }
}

enum class PerformanceWindow(val label: String, val limit: Int?) {
    RECENT_10("최근 10회", 10),
    RECENT_30("최근 30회", 30),
    ALL("전체", null)
}

data class PerformanceSummary(
    val completedDraws: Int,
    val pendingDraws: Int,
    val averageBestMatches: Double?,
    val drawsWith3Plus: Int,
    val drawsWith4Plus: Int,
    val bestTier: PrizeTier?,
    val tierCounts: Map<PrizeTier, Int>
)

object PerformanceAggregator {
    fun aggregate(
        records: List<ConfirmedRecord>,
        window: PerformanceWindow = PerformanceWindow.RECENT_10
    ): PerformanceSummary = aggregate(records, window.limit)

    fun aggregate(
        records: List<ConfirmedRecord>,
        limit: Int?
    ): PerformanceSummary {
        val pendingDraws = records.count { it.evaluation == null }
        val evaluatedRecords = records
            .filter { it.evaluation != null }
            .sortedWith(compareByDescending<ConfirmedRecord> { it.draw }.thenByDescending { it.confirmedAt })

        val windowed = if (limit != null && limit > 0) {
            evaluatedRecords.take(limit)
        } else {
            evaluatedRecords
        }

        val completedDraws = windowed.size
        val tierCounts = PrizeTier.values().associateWith { tier ->
            windowed.count { it.evaluation?.bestTier == tier }
        }

        if (completedDraws == 0) {
            return PerformanceSummary(
                completedDraws = 0,
                pendingDraws = pendingDraws,
                averageBestMatches = null,
                drawsWith3Plus = 0,
                drawsWith4Plus = 0,
                bestTier = null,
                tierCounts = tierCounts
            )
        }

        val avgBestMatches = windowed.map { it.evaluation!!.bestMatchCount }.average()
        val drawsWith3Plus = windowed.count { it.evaluation!!.bestMatchCount >= 3 }
        val drawsWith4Plus = windowed.count { it.evaluation!!.bestMatchCount >= 4 }
        val bestTier = windowed.mapNotNull { it.evaluation?.bestTier }.minByOrNull { it.order }

        return PerformanceSummary(
            completedDraws = completedDraws,
            pendingDraws = pendingDraws,
            averageBestMatches = avgBestMatches,
            drawsWith3Plus = drawsWith3Plus,
            drawsWith4Plus = drawsWith4Plus,
            bestTier = bestTier,
            tierCounts = tierCounts
        )
    }
}
