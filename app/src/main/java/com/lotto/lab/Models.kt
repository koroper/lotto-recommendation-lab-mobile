package com.lotto.lab

data class GameResult(
    val index: Int,
    val numbers: List<Int>,
    val score: Double,
    val rank: Int,
    val total: Int,
    val percentile: Double
)

data class Confidence(
    val score: Double,
    val label: String,
    val agreement: Double,
    val rankConsistency: Double,
    val separation: Double
)

data class RecommendationResult(
    val latestDraw: Int,
    val latestDate: String,
    val targetDraw: Int,
    val recommendationId: String,
    val games: List<GameResult>,
    val core: List<Int>,
    val semiCore: List<Int>,
    val axis: List<Int>,
    val candidatePool: List<Int>,
    val confidence: Confidence,
    val weightsJson: String
)

data class ValidationFold(
    val fold: Int,
    val trainDraws: Int,
    val valDraws: Int,
    val baseScore: Double,
    val candidateScore: Double,
    val gain: Double
)

data class ResearchResult(
    val promoted: Boolean,
    val message: String,
    val weightsJson: String,
    val testedDraws: Int,
    val fullEqual: Double,
    val fullCandidate: Double,
    val holdoutEqual: Double,
    val holdoutCandidate: Double,
    val foldCount: Int = 3,
    val foldWins: Int = 0,
    val foldTies: Int = 0,
    val foldLosses: Int = 0,
    val meanFoldGain: Double = 0.0,
    val worstFoldGain: Double = 0.0,
    val finalHoldoutGain: Double = 0.0,
    val primaryReason: String? = null,
    val folds: List<ValidationFold> = emptyList(),
    val searchCandidateCount: Int = 0,
    val selectedCandidateWeightsJson: String? = null,
    val searchMethod: String? = null
)

data class ConfirmedRecord(
    val draw: Int,
    val recommendationId: String,
    val payloadJson: String,
    val confirmedAt: Long,
    val bestMatches: Int? = null,
    val evaluation: DrawEvaluation? = null
)

enum class Screen { RECOMMEND, RESEARCH, RECORDS, SETTINGS }

data class AppUiState(
    val loading: Boolean = true,
    val runningResearch: Boolean = false,
    val error: String? = null,
    val recommendation: RecommendationResult? = null,
    val research: ResearchResult? = null,
    val records: List<ConfirmedRecord> = emptyList(),
    val style: String = "표준",
    val games: Int = 5,
    val dataMessage: String = "",
    val confirmedCurrent: Boolean = false,
    val confirmedRecommendationId: String? = null
)
