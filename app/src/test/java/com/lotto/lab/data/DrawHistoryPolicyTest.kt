package com.lotto.lab.data

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import java.time.LocalDate
import java.time.ZoneId
import java.time.ZonedDateTime

class DrawHistoryPolicyTest {
    private val today = LocalDate.of(2026, 10, 26)

    private fun sample(count: Int = 60, snakeCase: Boolean = true): JSONArray {
        return JSONArray().apply {
            for (draw in 1..count) {
                val date = LocalDate.of(2002, 12, 7).plusWeeks((draw - 1).toLong()).toString()
                put(JSONObject().apply {
                    put(if (snakeCase) "draw_no" else "drawNo", draw)
                    put("date", if (snakeCase) date + "T00:00:00Z" else date)
                    put("numbers", JSONArray(listOf(1, 2, 3, 4, 5, 6)))
                    put(if (snakeCase) "bonus_no" else "bonusNo", 7)
                })
            }
        }
    }

    @Test fun convertsMirrorArrayAndNormalizesUtcDate() {
        val parsed = DrawHistoryPolicy.parse(sample().toString(), today)
        assertEquals(60, parsed.latestDraw)
        assertEquals("2004-01-24", parsed.latestDate)
        val first = parsed.payload.getJSONArray("data").getJSONObject(0)
        assertEquals(1, first.getInt("drawNo"))
        assertEquals("2002-12-07", first.getString("date"))
        assertEquals(7, first.getInt("bonusNo"))
    }

    @Test fun acceptsLegacyObjectPayload() {
        val legacy = JSONObject().put("data", sample(snakeCase = false))
        val parsed = DrawHistoryPolicy.parse(legacy.toString(), today)
        assertEquals(60, parsed.payload.getJSONArray("data").length())
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsSkippedOrRepeatedDraw() {
        val data = sample()
        data.getJSONObject(59).put("draw_no", 59)
        DrawHistoryPolicy.parse(data.toString(), today)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsDuplicateNumbers() {
        val data = sample()
        data.getJSONObject(59).put("numbers", JSONArray(listOf(1, 1, 2, 3, 4, 5)))
        DrawHistoryPolicy.parse(data.toString(), today)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsBonusOverlap() {
        val data = sample()
        data.getJSONObject(59).put("bonus_no", 6)
        DrawHistoryPolicy.parse(data.toString(), today)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsFutureDate() {
        val data = sample()
        data.getJSONObject(59).put("date", "2027-01-01T00:00:00Z")
        DrawHistoryPolicy.parse(data.toString(), today)
    }

    @Test fun detectsHistoricalRewritesAndAllowsNewDraw() {
        val oldData = sample(60)
        val saved = JSONArray()
        for (i in 0 until oldData.length()) {
            val old = oldData.getJSONObject(i)
            saved.put(JSONObject().apply {
                put("draw", i + 1)
                put("date", old.getString("date").take(10))
                put("numbers", old.getJSONArray("numbers"))
                put("bonus", old.getInt("bonus_no"))
            })
        }
        val appended = DrawHistoryPolicy.parse(sample(61).toString(), today)
        assertTrue(DrawHistoryPolicy.matchingOverlap(saved.toString(), appended))
        val changed = sample(61)
        changed.getJSONObject(59).put("bonus_no", 8)
        assertFalse(DrawHistoryPolicy.matchingOverlap(saved.toString(),
            DrawHistoryPolicy.parse(changed.toString(), today)))
    }

    @Test fun usesCorrectKstDrawCutoff() {
        val kst = ZoneId.of("Asia/Seoul")
        fun at(value: String) = ZonedDateTime.parse(value).withZoneSameInstant(kst)
        assertEquals(1246, DrawHistoryPolicy.expectedCompletedDraw(at("2026-10-24T18:41:00+09:00")))
        assertEquals(1247, DrawHistoryPolicy.expectedCompletedDraw(at("2026-10-24T21:01:00+09:00")))
        assertEquals(1247, DrawHistoryPolicy.expectedCompletedDraw(at("2026-10-26T13:00:00+09:00")))
        assertEquals(1247, DrawHistoryPolicy.expectedCompletedDraw(at("2026-10-31T19:00:00+09:00")))
        assertEquals(1248, DrawHistoryPolicy.expectedCompletedDraw(at("2026-11-01T10:00:00+09:00")))
    }
}
