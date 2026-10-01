package com.lotto.lab

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.lotto.lab.data.LottoRepository
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = LottoRepository(app)
    private val _ui = MutableStateFlow(AppUiState())
    val ui: StateFlow<AppUiState> = _ui.asStateFlow()

    init {
        refreshAll()
    }

    fun refreshAll() {
        viewModelScope.launch {
            _ui.value = _ui.value.copy(loading = true, error = null)
            try {
                val msg = repo.ensureData()
                val rec = repo.recommend(_ui.value.games, _ui.value.style)
                _ui.value = _ui.value.copy(
                    loading = false,
                    recommendation = rec,
                    research = repo.savedResearch(),
                    records = repo.records(),
                    dataMessage = msg,
                    confirmedCurrent = repo.confirmedRecommendationId(rec.targetDraw) == rec.recommendationId,
                    confirmedRecommendationId = repo.confirmedRecommendationId(rec.targetDraw)
                )
            } catch (e: Exception) {
                _ui.value = _ui.value.copy(
                    loading = false,
                    error = e.message ?: e.toString()
                )
            }
        }
    }

    fun setStyle(style: String) {
        _ui.value = _ui.value.copy(style = style)
        recompute()
    }

    fun setGames(games: Int) {
        _ui.value = _ui.value.copy(games = games.coerceIn(1, 10))
        recompute()
    }

    private fun recompute() {
        viewModelScope.launch {
            try {
                _ui.value = _ui.value.copy(loading = true, error = null)
                val rec = repo.recommend(_ui.value.games, _ui.value.style)
                _ui.value = _ui.value.copy(
                    loading = false,
                    recommendation = rec,
                    confirmedCurrent = repo.confirmedRecommendationId(rec.targetDraw) == rec.recommendationId,
                    confirmedRecommendationId = repo.confirmedRecommendationId(rec.targetDraw)
                )
            } catch (e: Exception) {
                _ui.value = _ui.value.copy(loading = false, error = e.message)
            }
        }
    }

    fun runResearch() {
        viewModelScope.launch {
            _ui.value = _ui.value.copy(runningResearch = true, error = null)
            try {
                val research = repo.runResearch()
                val rec = repo.recommend(_ui.value.games, _ui.value.style)
                _ui.value = _ui.value.copy(
                    runningResearch = false,
                    research = research,
                    recommendation = rec,
                    confirmedCurrent = repo.confirmedRecommendationId(rec.targetDraw) == rec.recommendationId,
                    confirmedRecommendationId = repo.confirmedRecommendationId(rec.targetDraw)
                )
            } catch (e: Exception) {
                _ui.value = _ui.value.copy(
                    runningResearch = false,
                    error = e.message ?: e.toString()
                )
            }
        }
    }

    fun confirmCurrent() {
        val rec = _ui.value.recommendation ?: return
        viewModelScope.launch(Dispatchers.IO) {
            repo.confirm(rec)
            withContext(Dispatchers.Main) {
                _ui.value = _ui.value.copy(
                    confirmedCurrent = true,
                    confirmedRecommendationId = rec.recommendationId,
                    records = repo.records()
                )
            }
        }
    }
}
