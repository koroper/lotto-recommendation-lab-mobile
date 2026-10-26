package com.lotto.lab.data

import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONTokener
import java.time.DayOfWeek
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.temporal.ChronoUnit

/** Normalize independently maintained history formats into the existing DB import schema. */
internal data class DrawHistorySnapshot(
    val payload: JSONObject,
    val latestDraw: Int,
    val latestDate: String
)

internal object DrawHistoryPolicy {
    private val kst = ZoneId.of("Asia/Seoul")
    // Verified draw 1247: 2026-10-24 (Saturday). After 21:00 KST, expect its result.
    private val anchorDate = LocalDate.of(2026, 10, 24)
    private const val anchorDraw = 1247

    fun expectedCompletedDraw(now: ZonedDateTime = ZonedDateTime.now(kst)): Int {
        val local = now.withZoneSameInstant(kst)
        val days = ChronoUnit.DAYS.between(anchorDate, local.toLocalDate()).toInt()
        val elapsedWeeks = Math.floorDiv(days, 7)
        val beforeSaturdayResult = local.dayOfWeek == DayOfWeek.SATURDAY &&
            local.toLocalTime().isBefore(LocalTime.of(21, 0))
        return (anchorDraw + elapsedWeeks - if (beforeSaturdayResult) 1 else 0).coerceAtLeast(1)
    }

    fun parse(raw: String, today: LocalDate = LocalDate.now(kst)): DrawHistorySnapshot {
        val root = JSONTokener(raw).nextValue()
        val input = when (root) {
            is JSONArray -> root
            is JSONObject -> root.optJSONArray("data")
                ?: throw IllegalArgumentException("data 배열 없음")
            else -> throw IllegalArgumentException("지원하지 않는 JSON 구조")
        }
        require(input.length() >= 60) { "전체 추첨 이력이 너무 짧음" }
        val normalized = JSONArray()
        var previousDate = LocalDate.MIN
        for (i in 0 until input.length()) {
            val item = input.getJSONObject(i)
            val draw = if (item.has("drawNo")) item.getInt("drawNo") else item.getInt("draw_no")
            // Strict 1..N continuity also protects against duplicate, missing or shuffled draws.
            require(draw == i + 1) { "회차 누락·중복·순서 오류: " + draw }
            val date = item.getString("date").take(10)
            val day = LocalDate.parse(date)
            require(!day.isBefore(previousDate) && !day.isAfter(today)) { "추첨일 오류: " + draw }
            previousDate = day

            val numbers = item.getJSONArray("numbers")
            require(numbers.length() == 6) { "당첨번호 개수 오류: " + draw }
            val unique = mutableSetOf<Int>()
            val six = JSONArray()
            for (n in 0 until 6) {
                val number = numbers.getInt(n)
                require(number in 1..45 && unique.add(number)) { "당첨번호 오류: " + draw }
                six.put(number)
            }
            val bonus = if (item.has("bonusNo")) item.getInt("bonusNo") else item.getInt("bonus_no")
            require(bonus in 1..45 && bonus !in unique) { "보너스 번호 오류: " + draw }
            normalized.put(JSONObject().apply {
                put("drawNo", draw)
                put("date", date)
                put("numbers", six)
                put("bonusNo", bonus)
            })
        }
        return DrawHistorySnapshot(
            JSONObject().put("data", normalized).put("latestRound", input.length()),
            input.length(), previousDate.toString()
        )
    }

    /** Reject an incoming source which rewrites already confirmed draws in the local DB. */
    fun matchingOverlap(localHistory: String, incoming: DrawHistorySnapshot): Boolean {
        val saved = JSONArray(localHistory)
        val remote = incoming.payload.getJSONArray("data")
        for (i in 0 until saved.length()) {
            val item = saved.getJSONObject(i)
            val draw = item.getInt("draw")
            if (draw <= incoming.latestDraw && draw > saved.length() - 20) {
                val candidate = remote.getJSONObject(draw - 1)
                if (item.getString("date").take(10) != candidate.getString("date")) return false
                if (item.getInt("bonus") != candidate.getInt("bonusNo")) return false
                val left = item.getJSONArray("numbers")
                val right = candidate.getJSONArray("numbers")
                if ((0 until 6).any { left.getInt(it) != right.getInt(it) }) return false
            }
        }
        return true
    }
}
