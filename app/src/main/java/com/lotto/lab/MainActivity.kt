package com.lotto.lab

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.lotto.lab.ui.theme.LottoLabTheme
import java.text.SimpleDateFormat
import java.util.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            LottoLabTheme {
                LottoApp()
            }
        }
    }
}

@Composable
fun LottoApp(vm: MainViewModel = viewModel()) {
    val state by vm.ui.collectAsState()
    var screen by remember { mutableStateOf(Screen.RECOMMEND) }

    Scaffold(
        bottomBar = {
            NavigationBar {
                listOf(
                    Screen.RECOMMEND to "🎟\n추천",
                    Screen.RESEARCH to "🧪\n연구",
                    Screen.RECORDS to "📊\n기록",
                    Screen.SETTINGS to "⚙\n설정"
                ).forEach { (item, label) ->
                    NavigationBarItem(
                        selected = screen == item,
                        onClick = { screen = item },
                        icon = { Text(label, textAlign = TextAlign.Center) },
                        label = null
                    )
                }
            }
        }
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            when {
                state.loading && state.recommendation == null -> LoadingScreen("추천 엔진 계산 중...")
                state.error != null && state.recommendation == null -> ErrorScreen(state.error!!, vm::refreshAll)
                else -> when (screen) {
                    Screen.RECOMMEND -> RecommendationScreen(state, vm)
                    Screen.RESEARCH -> ResearchScreen(state, vm)
                    Screen.RECORDS -> RecordsScreen(state)
                    Screen.SETTINGS -> SettingsScreen(state, vm)
                }
            }
        }
    }
}

@Composable
private fun Header(title: String, subtitle: String? = null) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 14.dp)) {
        Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
        subtitle?.let {
            Spacer(Modifier.height(3.dp))
            Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
fun RecommendationScreen(state: AppUiState, vm: MainViewModel) {
    val rec = state.recommendation ?: return LoadingScreen("추천 계산 중...")
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item {
            Header(
                "🎯 ${rec.targetDraw}회 최종 추천",
                "최신 ${rec.latestDraw}회 · ${rec.latestDate} · ${state.dataMessage}"
            )
        }

        if (state.confirmedCurrent) {
            item {
                Surface(
                    modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                    color = MaterialTheme.colorScheme.primaryContainer,
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Text(
                        "✅ 이번 회차 구매안 확정 완료 · ${rec.recommendationId}",
                        Modifier.padding(14.dp),
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        if (!state.confirmedCurrent && state.confirmedRecommendationId != null) {
            item {
                Surface(
                    modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                    color = MaterialTheme.colorScheme.tertiaryContainer,
                    shape = RoundedCornerShape(14.dp)
                ) {
                    Text(
                        "⚠️ 확정한 구매안(${state.confirmedRecommendationId})과 현재 추천(${rec.recommendationId})이 다릅니다. 바꾸려면 다시 확정하세요.",
                        Modifier.padding(14.dp),
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }

        items(rec.games) { game -> GameCard(game) }

        item {
            Row(
                Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                SummaryCard("🔥 최우선", rec.core.joinToString(" · "), Modifier.weight(1f))
                SummaryCard(
                    "🔒 실전축",
                    if (rec.axis.isEmpty()) "뚜렷한 축 없음" else rec.axis.joinToString(" · "),
                    Modifier.weight(1f)
                )
            }
        }

        item {
            SummaryCard(
                "내부 추천 확신도",
                "${rec.confidence.score} / 100 · ${rec.confidence.label}",
                Modifier.padding(horizontal = 16.dp).fillMaxWidth()
            )
        }

        item {
            Text(
                "📱 매장에서 바로 보기",
                Modifier.padding(horizontal = 18.dp, vertical = 6.dp),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold
            )
            Surface(
                Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                shape = RoundedCornerShape(14.dp),
                tonalElevation = 2.dp
            ) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    rec.games.forEach { g ->
                        Text(
                            "${g.index}게임   ${g.numbers.joinToString("  ") { "%02d".format(it) }}",
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }
            }
        }

        item {
            Button(
                onClick = vm::confirmCurrent,
                modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                enabled = !state.loading
            ) {
                Text(if (state.confirmedCurrent) "확정 구매안 업데이트" else "이번 주 구매안 확정")
            }
        }

        state.error?.let { error ->
            item {
                Text(error, Modifier.padding(horizontal = 16.dp), color = MaterialTheme.colorScheme.error)
            }
        }
    }
}

@Composable
private fun GameCard(game: GameResult) {
    Card(
        Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
        shape = RoundedCornerShape(16.dp)
    ) {
        Column(Modifier.padding(15.dp)) {
            Text("${game.index}게임", fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(7.dp)) {
                game.numbers.forEach { LottoBall(it) }
            }
            Spacer(Modifier.height(10.dp))
            Text(
                "추천 ${"%.1f".format(game.score)} · ${game.rank}/${game.total}위 · 상위 ${"%.2f".format(game.percentile)}%",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}

@Composable
private fun LottoBall(
    number: Int,
    isMatched: Boolean = false,
    isBonus: Boolean = false,
    size: Dp = 42.dp
) {
    val (bgColor, textColor) = when {
        isMatched -> MaterialTheme.colorScheme.primary to MaterialTheme.colorScheme.onPrimary
        isBonus -> MaterialTheme.colorScheme.tertiary to MaterialTheme.colorScheme.onTertiary
        else -> MaterialTheme.colorScheme.surfaceVariant to MaterialTheme.colorScheme.onSurfaceVariant
    }
    Box(
        Modifier
            .size(size)
            .background(bgColor, CircleShape),
        contentAlignment = Alignment.Center
    ) {
        Text(
            number.toString(),
            color = textColor,
            fontWeight = if (isMatched || isBonus) FontWeight.ExtraBold else FontWeight.Bold,
            style = if (size < 36.dp) MaterialTheme.typography.bodySmall else MaterialTheme.typography.bodyMedium
        )
    }
}

@Composable
private fun SummaryCard(label: String, value: String, modifier: Modifier) {
    Card(modifier, shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(13.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(4.dp))
            Text(value, fontWeight = FontWeight.Bold)
        }
    }
}

private fun formatSignedGain(v: Double): String {
    return if (v >= 0) String.format(Locale.US, "+%.3f", v) else String.format(Locale.US, "%.3f", v)
}

@Composable
fun ResearchScreen(state: AppUiState, vm: MainViewModel) {
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        item {
            Header("🧪 모바일 빠른 연구", "최근 과거 회차를 다중 Walk-Forward 구간으로 반복 검증하고 홀드아웃을 통과한 가중치만 반영합니다.")
        }
        item {
            Button(
                onClick = vm::runResearch,
                modifier = Modifier.padding(horizontal = 16.dp).fillMaxWidth(),
                enabled = !state.runningResearch
            ) {
                if (state.runningResearch) {
                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("연구 계산 중...")
                } else {
                    Text("빠른 연구 검증 실행")
                }
            }
        }

        state.research?.let { r ->
            item {
                Card(Modifier.padding(horizontal = 16.dp).fillMaxWidth()) {
                    Column(Modifier.padding(15.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                if (r.promoted) "✅ 연구 보정 적용" else "🟡 기본 가중치 유지 (HOLD)",
                                fontWeight = FontWeight.ExtraBold,
                                style = MaterialTheme.typography.titleMedium
                            )
                            if (!r.promoted && r.primaryReason != null) {
                                Surface(
                                    color = MaterialTheme.colorScheme.errorContainer,
                                    shape = RoundedCornerShape(6.dp)
                                ) {
                                    Text(
                                        r.primaryReason,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onErrorContainer,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }
                        }
                        Text(r.message, style = MaterialTheme.typography.bodyMedium)
                        HorizontalDivider()

                        if (r.searchCandidateCount > 0) {
                            Text(
                                "후보 탐색 ${r.searchCandidateCount}개 · 선택된 가중치 검증",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                        }

                        if (r.foldCount > 0) {
                            Text("반복 검증 ${r.foldCount}회", fontWeight = FontWeight.Bold)
                            Text(
                                "후보 우세 ${r.foldWins}회 · 동률 ${r.foldTies}회 · 열세 ${r.foldLosses}회",
                                style = MaterialTheme.typography.bodyMedium
                            )
                            Text(
                                "평균 개선 ${formatSignedGain(r.meanFoldGain)}",
                                style = MaterialTheme.typography.bodyMedium
                            )
                            Text(
                                "최악 구간 ${formatSignedGain(r.worstFoldGain)}",
                                style = MaterialTheme.typography.bodyMedium
                            )
                            Text(
                                "최종 홀드아웃 ${formatSignedGain(r.finalHoldoutGain)}",
                                style = MaterialTheme.typography.bodyMedium
                            )
                            Text(
                                "전체 검증 ${r.testedDraws}회 · 기본 ${r.fullEqual} / 후보 ${r.fullCandidate}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        } else {
                            Text("검증 회차: ${r.testedDraws}회")
                            Text("전체 · 기본 ${r.fullEqual} / 후보 ${r.fullCandidate}")
                            Text("홀드아웃 · 기본 ${r.holdoutEqual} / 후보 ${r.holdoutCandidate}")
                        }
                    }
                }
            }
            item {
                Text(
                    "※ 검증 지표는 과거 회차 기준 모델 상대 점수이며, 미래 복권 당첨 확률 향상을 의미하지 않습니다.",
                    Modifier.padding(horizontal = 16.dp),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        } ?: item {
            Text(
                "아직 모바일 연구를 실행하지 않았습니다. 기본 추천은 6개 모델 동일비중으로 계산됩니다.",
                Modifier.padding(horizontal = 16.dp)
            )
        }
    }
}

@Composable
fun RecordsScreen(state: AppUiState) {
    var selectedWindow by remember { mutableStateOf(PerformanceWindow.RECENT_10) }
    val summary = remember(state.records, selectedWindow) {
        PerformanceAggregator.aggregate(state.records, selectedWindow)
    }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp)
    ) {
        item { Header("📊 실제 확정 기록", "결과 발표 전에 확정한 구매안만 추적합니다.") }

        // Performance Dashboard Card
        item {
            Card(Modifier.padding(horizontal = 16.dp).fillMaxWidth()) {
                Column(
                    Modifier.padding(14.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Text(
                        "실제 구매 성과 대시보드",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )

                    // 1. Filter chips: 최근 10회, 최근 30회, 전체
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        PerformanceWindow.values().forEach { window ->
                            FilterChip(
                                selected = selectedWindow == window,
                                onClick = { selectedWindow = window },
                                label = { Text(window.label) }
                            )
                        }
                    }

                    // 2. Main summary: 결과 확인 N회, 결과 대기 N회
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Surface(
                            color = MaterialTheme.colorScheme.primaryContainer,
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text(
                                "결과 확인 ${summary.completedDraws}회",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onPrimaryContainer
                            )
                        }
                        Surface(
                            color = MaterialTheme.colorScheme.secondaryContainer,
                            shape = RoundedCornerShape(8.dp)
                        ) {
                            Text(
                                "결과 대기 ${summary.pendingDraws}회",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = MaterialTheme.colorScheme.onSecondaryContainer
                            )
                        }
                    }

                    // Empty / Early data UX or Metrics
                    if (summary.completedDraws == 0) {
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(8.dp),
                            modifier = Modifier.fillMaxWidth()
                        ) {
                            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text(
                                    "아직 결과가 확인된 구매안이 없습니다.",
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                if (summary.pendingDraws > 0) {
                                    Text(
                                        "결과 대기 중인 구매안 ${summary.pendingDraws}회는 추첨 결과가 등록되면 자동으로 성과에 반영됩니다.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant
                                    )
                                }
                            }
                        }
                    } else {
                        // 3. Metric cards: 평균 최고 일치, 3개 이상, 4개 이상, 최고 결과
                        val avgStr = summary.averageBestMatches?.let { String.format(Locale.KOREA, "%.2f개", it) } ?: "—"
                        val bestTierStr = summary.bestTier?.label ?: "—"

                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            DashboardMetricCard(
                                title = "평균 최고 일치",
                                value = avgStr,
                                modifier = Modifier.weight(1f)
                            )
                            DashboardMetricCard(
                                title = "3개 이상",
                                value = "${summary.drawsWith3Plus}회",
                                modifier = Modifier.weight(1f)
                            )
                        }
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            DashboardMetricCard(
                                title = "4개 이상",
                                value = "${summary.drawsWith4Plus}회",
                                modifier = Modifier.weight(1f)
                            )
                            DashboardMetricCard(
                                title = "최고 결과",
                                value = bestTierStr,
                                modifier = Modifier.weight(1f),
                                isHighlight = summary.bestTier != null && summary.bestTier != PrizeTier.NONE
                            )
                        }

                        // 4. Compact result distribution
                        HorizontalDivider(Modifier.padding(vertical = 2.dp))

                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                "회차별 최고 등수 분포",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                fontWeight = FontWeight.Bold
                            )
                            val distText = "1등 ${summary.tierCounts[PrizeTier.FIRST] ?: 0} · 2등 ${summary.tierCounts[PrizeTier.SECOND] ?: 0} · 3등 ${summary.tierCounts[PrizeTier.THIRD] ?: 0} · 4등 ${summary.tierCounts[PrizeTier.FOURTH] ?: 0} · 5등 ${summary.tierCounts[PrizeTier.FIFTH] ?: 0} · 미당첨 ${summary.tierCounts[PrizeTier.NONE] ?: 0}"
                            Text(
                                distText,
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                        }

                        Text(
                            "※ 과거 확정 성과는 미래 로또 6/45의 물리적 독립 당첨 확률을 변경하지 않습니다.",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }
            }
        }

        item {
            Text(
                "구매안별 상세 결과",
                Modifier.padding(horizontal = 16.dp, vertical = 2.dp),
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold
            )
        }

        if (state.records.isEmpty()) {
            item { Text("아직 확정 구매안 기록이 없습니다.", Modifier.padding(horizontal = 16.dp)) }
        } else {
            items(state.records) { r ->
                Card(Modifier.padding(horizontal = 16.dp).fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text("${r.draw}회", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.titleMedium)
                            Text(r.recommendationId, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        val date = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.KOREA).format(Date(r.confirmedAt))
                        Text("확정 $date", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)

                        val eval = r.evaluation
                        if (eval == null) {
                            Text(
                                "아직 결과 발표 전",
                                color = MaterialTheme.colorScheme.primary,
                                fontWeight = FontWeight.SemiBold
                            )
                        } else {
                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("당첨 번호", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                                Row(
                                    verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(4.dp)
                                ) {
                                    eval.winningNumbers.forEach { num ->
                                        LottoBall(number = num, isMatched = true, size = 32.dp)
                                    }
                                    Text("+", fontWeight = FontWeight.Bold, modifier = Modifier.padding(horizontal = 2.dp))
                                    LottoBall(number = eval.bonus, isBonus = true, size = 32.dp)
                                    Text(
                                        "보너스",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.tertiary,
                                        fontWeight = FontWeight.Bold
                                    )
                                }
                            }

                            val summaryText = if (eval.bestTier == PrizeTier.NONE) {
                                "최고 결과 · 미당첨 · ${eval.bestMatchCount}개 일치"
                            } else {
                                "최고 결과 · ${eval.bestTier.label} · ${eval.bestMatchCount}개 일치"
                            }
                            Surface(
                                color = if (eval.bestTier != PrizeTier.NONE) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                                shape = RoundedCornerShape(8.dp)
                            ) {
                                Text(
                                    summaryText,
                                    modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp),
                                    fontWeight = FontWeight.Bold,
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = if (eval.bestTier != PrizeTier.NONE) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }

                            HorizontalDivider(Modifier.padding(vertical = 4.dp))

                            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                eval.games.forEach { g ->
                                    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                        Row(verticalAlignment = Alignment.CenterVertically) {
                                            Text(
                                                "${g.index}게임 · ${g.mainMatchCount}개 일치 · ${g.prizeTier.label}",
                                                fontWeight = FontWeight.SemiBold,
                                                style = MaterialTheme.typography.bodyMedium,
                                                color = if (g.prizeTier != PrizeTier.NONE) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                                            )
                                            if (g.hasBonus) {
                                                Spacer(Modifier.width(6.dp))
                                                Text(
                                                    "(보너스 일치)",
                                                    style = MaterialTheme.typography.labelSmall,
                                                    color = MaterialTheme.colorScheme.tertiary,
                                                    fontWeight = FontWeight.Bold
                                                )
                                            }
                                        }
                                        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                            val matchedSet = g.matchedMainNumbers.toSet()
                                            g.numbers.forEach { num ->
                                                val isMatched = num in matchedSet
                                                val isBonus = num == eval.bonus
                                                LottoBall(
                                                    number = num,
                                                    isMatched = isMatched,
                                                    isBonus = isBonus,
                                                    size = 30.dp
                                                )
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SettingsScreen(state: AppUiState, vm: MainViewModel) {
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(bottom = 24.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item { Header("⚙ 설정", "모바일 v1은 핵심 구매 설정부터 제공합니다.") }
        item {
            Text("5게임 구성 방식", Modifier.padding(horizontal = 16.dp), fontWeight = FontWeight.Bold)
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("표준", "집중", "분산").forEach { style ->
                    FilterChip(selected = state.style == style, onClick = { vm.setStyle(style) }, label = { Text(style) })
                }
            }
        }
        item {
            Text("구매 게임 수: ${state.games}", Modifier.padding(horizontal = 16.dp), fontWeight = FontWeight.Bold)
            Row(Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { vm.setGames(state.games - 1) }, enabled = state.games > 1) { Text("−") }
                OutlinedButton(onClick = { vm.setGames(state.games + 1) }, enabled = state.games < 10) { Text("+") }
                Spacer(Modifier.weight(1f))
                OutlinedButton(onClick = vm::refreshAll) { Text("최신 데이터 확인") }
            }
        }
        item {
            Card(Modifier.padding(horizontal = 16.dp).fillMaxWidth()) {
                Column(Modifier.padding(14.dp)) {
                    Text("서버 필요 없음", fontWeight = FontWeight.Bold)
                    Text(
                        "당첨 데이터 업데이트에만 인터넷을 사용하고, 추천 계산·연구·확정 기록은 휴대폰 내부에서 처리합니다.",
                        style = MaterialTheme.typography.bodySmall
                    )
                }
            }
        }
    }
}

@Composable
private fun LoadingScreen(text: String) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            CircularProgressIndicator()
            Spacer(Modifier.height(12.dp))
            Text(text)
        }
    }
}

@Composable
private fun ErrorScreen(error: String, retry: () -> Unit) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(Modifier.padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text("실행 중 문제가 발생했습니다.", fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(8.dp))
            Text(error, color = MaterialTheme.colorScheme.error)
            Spacer(Modifier.height(16.dp))
            Button(onClick = retry) { Text("다시 시도") }
        }
    }
}

@Composable
private fun DashboardMetricCard(
    title: String,
    value: String,
    modifier: Modifier = Modifier,
    isHighlight: Boolean = false
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(8.dp),
        color = if (isHighlight) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant
    ) {
        Column(
            Modifier.padding(10.dp),
            verticalArrangement = Arrangement.spacedBy(2.dp)
        ) {
            Text(
                title,
                style = MaterialTheme.typography.labelSmall,
                color = if (isHighlight) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
            )
            Text(
                value,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = if (isHighlight) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurface
            )
        }
    }
}
