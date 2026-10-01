package com.lotto.lab

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ConfirmedTicketEvaluatorTest {

    private val winning = listOf(3, 11, 14, 18, 26, 34)
    private val bonus = 42

    @Test
    fun testPrizeTierDirectEvaluation() {
        assertEquals(PrizeTier.FIRST, PrizeTier.evaluate(6, false))
        assertEquals(PrizeTier.FIRST, PrizeTier.evaluate(6, true))
        assertEquals(PrizeTier.SECOND, PrizeTier.evaluate(5, true))
        assertEquals(PrizeTier.THIRD, PrizeTier.evaluate(5, false))
        assertEquals(PrizeTier.FOURTH, PrizeTier.evaluate(4, false))
        assertEquals(PrizeTier.FOURTH, PrizeTier.evaluate(4, true))
        assertEquals(PrizeTier.FIFTH, PrizeTier.evaluate(3, false))
        assertEquals(PrizeTier.FIFTH, PrizeTier.evaluate(3, true))
        assertEquals(PrizeTier.NONE, PrizeTier.evaluate(2, false))
        assertEquals(PrizeTier.NONE, PrizeTier.evaluate(2, true))
        assertEquals(PrizeTier.NONE, PrizeTier.evaluate(1, false))
        assertEquals(PrizeTier.NONE, PrizeTier.evaluate(0, false))
    }

    @Test
    fun testSixMainMatchesEvaluatesToFirst() {
        val game = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(3, 11, 14, 18, 26, 34),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(6, game.mainMatchCount)
        assertEquals(PrizeTier.FIRST, game.prizeTier)
    }

    @Test
    fun testFiveMainPlusBonusEvaluatesToSecond() {
        val game = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(3, 11, 14, 18, 26, 42),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(5, game.mainMatchCount)
        assertTrue(game.hasBonus)
        assertEquals(PrizeTier.SECOND, game.prizeTier)
    }

    @Test
    fun testFiveMainOnlyEvaluatesToThird() {
        val game = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(3, 11, 14, 18, 26, 45),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(5, game.mainMatchCount)
        assertFalse(game.hasBonus)
        assertEquals(PrizeTier.THIRD, game.prizeTier)
    }

    @Test
    fun testFourMainMatchesEvaluatesToFourth() {
        val gameNoBonus = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(3, 11, 14, 18, 40, 45),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(4, gameNoBonus.mainMatchCount)
        assertEquals(PrizeTier.FOURTH, gameNoBonus.prizeTier)

        val gameWithBonus = ConfirmedTicketEvaluator.evaluateGame(
            index = 2,
            numbers = listOf(3, 11, 14, 18, 42, 45),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(4, gameWithBonus.mainMatchCount)
        assertTrue(gameWithBonus.hasBonus)
        assertEquals(PrizeTier.FOURTH, gameWithBonus.prizeTier)
    }

    @Test
    fun testThreeMainMatchesEvaluatesToFifth() {
        val game = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(3, 11, 14, 39, 40, 45),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(3, game.mainMatchCount)
        assertEquals(PrizeTier.FIFTH, game.prizeTier)
    }

    @Test
    fun testTwoOrFewerMatchesEvaluatesToNone() {
        val gameTwo = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(3, 11, 38, 39, 40, 45),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(2, gameTwo.mainMatchCount)
        assertEquals(PrizeTier.NONE, gameTwo.prizeTier)

        val gameTwoWithBonus = ConfirmedTicketEvaluator.evaluateGame(
            index = 2,
            numbers = listOf(3, 11, 42, 39, 40, 45),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(2, gameTwoWithBonus.mainMatchCount)
        assertTrue(gameTwoWithBonus.hasBonus)
        assertEquals(PrizeTier.NONE, gameTwoWithBonus.prizeTier)

        val gameZero = ConfirmedTicketEvaluator.evaluateGame(
            index = 3,
            numbers = listOf(1, 2, 4, 5, 6, 7),
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(0, gameZero.mainMatchCount)
        assertEquals(PrizeTier.NONE, gameZero.prizeTier)
    }

    @Test
    fun testMatchedMainNumbersContainsExactMatchingValues() {
        val numbers = listOf(3, 11, 14, 18, 40, 45)
        val game = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = numbers,
            winningNumbers = winning,
            bonus = bonus
        )
        assertEquals(listOf(3, 11, 14, 18), game.matchedMainNumbers)
    }

    @Test
    fun testBonusDetectionIsCorrect() {
        val gameWithBonus = ConfirmedTicketEvaluator.evaluateGame(
            index = 1,
            numbers = listOf(1, 2, 3, 4, 5, 42),
            winningNumbers = winning,
            bonus = bonus
        )
        assertTrue(gameWithBonus.hasBonus)

        val gameWithoutBonus = ConfirmedTicketEvaluator.evaluateGame(
            index = 2,
            numbers = listOf(1, 2, 3, 4, 5, 43),
            winningNumbers = winning,
            bonus = bonus
        )
        assertFalse(gameWithoutBonus.hasBonus)
    }

    @Test
    fun testDrawLevelBestTierSelectedCorrectly() {
        val rawGames = listOf(
            1 to listOf(3, 11, 38, 39, 40, 45),
            2 to listOf(3, 11, 14, 18, 40, 45),
            3 to listOf(3, 11, 14, 39, 40, 45)
        )
        val drawEval = ConfirmedTicketEvaluator.evaluateDraw(winning, bonus, rawGames)
        assertEquals(PrizeTier.FOURTH, drawEval.bestTier)
    }

    @Test
    fun testDrawLevelBestMatchCountIsCorrect() {
        val rawGames = listOf(
            1 to listOf(3, 11, 38, 39, 40, 45),
            2 to listOf(3, 11, 14, 18, 40, 45),
            3 to listOf(3, 11, 14, 39, 40, 45)
        )
        val drawEval = ConfirmedTicketEvaluator.evaluateDraw(winning, bonus, rawGames)
        assertEquals(4, drawEval.bestMatchCount)
        assertEquals(3, drawEval.games.size)
    }
}
