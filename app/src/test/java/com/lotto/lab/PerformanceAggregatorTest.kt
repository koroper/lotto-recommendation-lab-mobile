package com.lotto.lab

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class PerformanceAggregatorTest {

    private fun makeRecord(
        draw: Int,
        confirmedAt: Long = draw * 1000L,
        bestMatchCount: Int? = null,
        bestTier: PrizeTier? = null
    ): ConfirmedRecord {
        val evaluation = if (bestMatchCount != null && bestTier != null) {
            DrawEvaluation(
                winningNumbers = listOf(1, 2, 3, 4, 5, 6),
                bonus = 7,
                games = emptyList(),
                bestTier = bestTier,
                bestMatchCount = bestMatchCount
            )
        } else {
            null
        }
        return ConfirmedRecord(
            draw = draw,
            recommendationId = "REC-$draw",
            payloadJson = "{}",
            confirmedAt = confirmedAt,
            bestMatches = bestMatchCount,
            evaluation = evaluation
        )
    }

    @Test
    fun testPendingRecordsExcludedFromCompletedMetrics() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1002, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1003),
            makeRecord(draw = 1004)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)
        assertEquals(2, summary.completedDraws)
        assertEquals(2, summary.pendingDraws)
        assertEquals(3.5, summary.averageBestMatches!!, 0.0001)
        assertEquals(2, summary.drawsWith3Plus)
        assertEquals(1, summary.drawsWith4Plus)
        assertEquals(0, summary.tierCounts[PrizeTier.NONE])
    }

    @Test
    fun testPendingRecordsCountedCorrectlyInPendingDraws() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 2, bestTier = PrizeTier.NONE),
            makeRecord(draw = 1002, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1003, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1004),
            makeRecord(draw = 1005)
        )
        val s10 = PerformanceAggregator.aggregate(records, PerformanceWindow.RECENT_10)
        val s30 = PerformanceAggregator.aggregate(records, PerformanceWindow.RECENT_30)
        val sAll = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)

        assertEquals(2, s10.pendingDraws)
        assertEquals(2, s30.pendingDraws)
        assertEquals(2, sAll.pendingDraws)
    }

    @Test
    fun testAverageBestMatchesIsCorrect() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1002, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1003, bestMatchCount = 2, bestTier = PrizeTier.NONE)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)
        assertEquals(3.0, summary.averageBestMatches!!, 0.0001)
    }

    @Test
    fun testDrawsWith3PlusCountIsCorrect() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 5, bestTier = PrizeTier.THIRD),
            makeRecord(draw = 1002, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1003, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1004, bestMatchCount = 2, bestTier = PrizeTier.NONE),
            makeRecord(draw = 1005, bestMatchCount = 1, bestTier = PrizeTier.NONE)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)
        assertEquals(3, summary.drawsWith3Plus)
    }

    @Test
    fun testDrawsWith4PlusCountIsCorrect() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 5, bestTier = PrizeTier.THIRD),
            makeRecord(draw = 1002, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1003, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1004, bestMatchCount = 2, bestTier = PrizeTier.NONE),
            makeRecord(draw = 1005, bestMatchCount = 1, bestTier = PrizeTier.NONE)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)
        assertEquals(2, summary.drawsWith4Plus)
    }

    @Test
    fun testBestPrizeTierIsCorrect() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 2, bestTier = PrizeTier.NONE),
            makeRecord(draw = 1002, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1003, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1004, bestMatchCount = 3, bestTier = PrizeTier.FIFTH)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)
        assertEquals(PrizeTier.FOURTH, summary.bestTier)
    }

    @Test
    fun testTierDistributionCountsOneBestTierPerDraw() {
        val records = listOf(
            makeRecord(draw = 1001, bestMatchCount = 6, bestTier = PrizeTier.FIRST),
            makeRecord(draw = 1002, bestMatchCount = 5, bestTier = PrizeTier.SECOND),
            makeRecord(draw = 1003, bestMatchCount = 5, bestTier = PrizeTier.THIRD),
            makeRecord(draw = 1004, bestMatchCount = 4, bestTier = PrizeTier.FOURTH),
            makeRecord(draw = 1005, bestMatchCount = 3, bestTier = PrizeTier.FIFTH),
            makeRecord(draw = 1006, bestMatchCount = 1, bestTier = PrizeTier.NONE)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.ALL)
        assertEquals(1, summary.tierCounts[PrizeTier.FIRST])
        assertEquals(1, summary.tierCounts[PrizeTier.SECOND])
        assertEquals(1, summary.tierCounts[PrizeTier.THIRD])
        assertEquals(1, summary.tierCounts[PrizeTier.FOURTH])
        assertEquals(1, summary.tierCounts[PrizeTier.FIFTH])
        assertEquals(1, summary.tierCounts[PrizeTier.NONE])
        assertEquals(6, summary.tierCounts.values.sum())
        assertEquals(summary.completedDraws, summary.tierCounts.values.sum())
    }

    @Test
    fun testRecent10SelectsExactlyLatest10EvaluatedRecords() {
        val records = (1001..1005).map {
            makeRecord(draw = it, bestMatchCount = 1, bestTier = PrizeTier.NONE)
        } + (1006..1015).map {
            makeRecord(draw = it, bestMatchCount = 5, bestTier = PrizeTier.THIRD)
        }

        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.RECENT_10)
        assertEquals(10, summary.completedDraws)
        assertEquals(5.0, summary.averageBestMatches!!, 0.0001)
        assertEquals(10, summary.drawsWith3Plus)
        assertEquals(10, summary.drawsWith4Plus)
        assertEquals(PrizeTier.THIRD, summary.bestTier)
        assertEquals(10, summary.tierCounts[PrizeTier.THIRD])
        assertEquals(0, summary.tierCounts[PrizeTier.NONE])
    }

    @Test
    fun testRecent30BehavesCorrectlyWithFewerThan30Records() {
        val records = (1..12).map {
            makeRecord(draw = 1000 + it, bestMatchCount = 3, bestTier = PrizeTier.FIFTH)
        }
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.RECENT_30)
        assertEquals(12, summary.completedDraws)
        assertEquals(3.0, summary.averageBestMatches!!, 0.0001)
        assertEquals(12, summary.drawsWith3Plus)
        assertEquals(PrizeTier.FIFTH, summary.bestTier)
    }

    @Test
    fun testEmptyCompletedDatasetReturnsNullAverageAndNullBestTier() {
        val records = listOf(
            makeRecord(draw = 1001),
            makeRecord(draw = 1002)
        )
        val summary = PerformanceAggregator.aggregate(records, PerformanceWindow.RECENT_10)
        assertEquals(0, summary.completedDraws)
        assertEquals(2, summary.pendingDraws)
        assertNull(summary.averageBestMatches)
        assertNull(summary.bestTier)
        assertEquals(0, summary.drawsWith3Plus)
        assertEquals(0, summary.drawsWith4Plus)
        assertEquals(0, summary.tierCounts.values.sum())
    }

    @Test
    fun testRecordOrderDoesNotCorruptSelectedWindowResult() {
        val originalList = (1001..1015).map { draw ->
            if (draw <= 1005) {
                makeRecord(draw = draw, bestMatchCount = 1, bestTier = PrizeTier.NONE)
            } else {
                makeRecord(draw = draw, bestMatchCount = 4, bestTier = PrizeTier.FOURTH)
            }
        }
        val shuffledList = originalList.reversed()

        val summaryOriginal = PerformanceAggregator.aggregate(originalList, PerformanceWindow.RECENT_10)
        val summaryShuffled = PerformanceAggregator.aggregate(shuffledList, PerformanceWindow.RECENT_10)

        assertEquals(summaryOriginal.completedDraws, summaryShuffled.completedDraws)
        assertEquals(summaryOriginal.averageBestMatches!!, summaryShuffled.averageBestMatches!!, 0.0001)
        assertEquals(summaryOriginal.drawsWith3Plus, summaryShuffled.drawsWith3Plus)
        assertEquals(summaryOriginal.drawsWith4Plus, summaryShuffled.drawsWith4Plus)
        assertEquals(summaryOriginal.bestTier, summaryShuffled.bestTier)
        assertEquals(summaryOriginal.tierCounts, summaryShuffled.tierCounts)
    }
}
