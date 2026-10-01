package com.lotto.lab.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import org.json.JSONArray
import org.json.JSONObject

class LottoDb(context: Context) : SQLiteOpenHelper(context, "lotto_lab.db", null, 1) {
    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE draws(
                draw_no INTEGER PRIMARY KEY,
                date TEXT NOT NULL,
                n1 INTEGER NOT NULL, n2 INTEGER NOT NULL, n3 INTEGER NOT NULL,
                n4 INTEGER NOT NULL, n5 INTEGER NOT NULL, n6 INTEGER NOT NULL,
                bonus INTEGER NOT NULL
            )
        """.trimIndent())
        db.execSQL("""
            CREATE TABLE app_state(
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """.trimIndent())
        db.execSQL("""
            CREATE TABLE recommendations(
                draw_no INTEGER PRIMARY KEY,
                recommendation_id TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                confirmed_at INTEGER NOT NULL
            )
        """.trimIndent())
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    fun replaceHistory(payload: JSONObject) {
        val data = payload.getJSONArray("data")
        writableDatabase.beginTransaction()
        try {
            writableDatabase.delete("draws", null, null)
            for (i in 0 until data.length()) {
                val item = data.getJSONObject(i)
                val nums = item.getJSONArray("numbers")
                val values = ContentValues().apply {
                    put("draw_no", item.getInt("drawNo"))
                    put("date", item.getString("date"))
                    for (n in 0 until 6) put("n${n + 1}", nums.getInt(n))
                    put("bonus", item.getInt("bonusNo"))
                }
                writableDatabase.insertOrThrow("draws", null, values)
            }
            writableDatabase.setTransactionSuccessful()
        } finally {
            writableDatabase.endTransaction()
        }
    }

    fun drawCount(): Int =
        readableDatabase.rawQuery("SELECT COUNT(*) FROM draws", null).use {
            it.moveToFirst(); it.getInt(0)
        }

    fun latestDraw(): Int =
        readableDatabase.rawQuery("SELECT COALESCE(MAX(draw_no),0) FROM draws", null).use {
            it.moveToFirst(); it.getInt(0)
        }

    fun historyJson(): String {
        val array = JSONArray()
        readableDatabase.rawQuery("""
            SELECT draw_no,date,n1,n2,n3,n4,n5,n6,bonus
            FROM draws ORDER BY draw_no
        """.trimIndent(), null).use { c ->
            while (c.moveToNext()) {
                array.put(JSONObject().apply {
                    put("draw", c.getInt(0))
                    put("date", c.getString(1))
                    put("numbers", JSONArray().apply {
                        for (i in 2..7) put(c.getInt(i))
                    })
                    put("bonus", c.getInt(8))
                })
            }
        }
        return array.toString()
    }

    fun saveState(key: String, value: String) {
        writableDatabase.insertWithOnConflict(
            "app_state", null,
            ContentValues().apply {
                put("key", key)
                put("value", value)
            },
            SQLiteDatabase.CONFLICT_REPLACE
        )
    }

    fun loadState(key: String): String? =
        readableDatabase.rawQuery(
            "SELECT value FROM app_state WHERE key=?",
            arrayOf(key)
        ).use { c -> if (c.moveToFirst()) c.getString(0) else null }

    fun saveRecommendation(draw: Int, recommendationId: String, payloadJson: String) {
        writableDatabase.insertWithOnConflict(
            "recommendations", null,
            ContentValues().apply {
                put("draw_no", draw)
                put("recommendation_id", recommendationId)
                put("payload_json", payloadJson)
                put("confirmed_at", System.currentTimeMillis())
            },
            SQLiteDatabase.CONFLICT_REPLACE
        )
    }

    fun confirmed(draw: Int): Boolean =
        readableDatabase.rawQuery(
            "SELECT 1 FROM recommendations WHERE draw_no=?",
            arrayOf(draw.toString())
        ).use { it.moveToFirst() }

    fun confirmedRecommendationId(draw: Int): String? =
        readableDatabase.rawQuery(
            "SELECT recommendation_id FROM recommendations WHERE draw_no=?",
            arrayOf(draw.toString())
        ).use { c -> if (c.moveToFirst()) c.getString(0) else null }

    fun recommendationPayload(draw: Int): String? =
        readableDatabase.rawQuery(
            "SELECT payload_json FROM recommendations WHERE draw_no=?",
            arrayOf(draw.toString())
        ).use { c -> if (c.moveToFirst()) c.getString(0) else null }

    fun listConfirmed(): List<Triple<Int, String, Pair<String, Long>>> {
        val out = mutableListOf<Triple<Int, String, Pair<String, Long>>>()
        readableDatabase.rawQuery("""
            SELECT draw_no,recommendation_id,payload_json,confirmed_at
            FROM recommendations ORDER BY draw_no DESC
        """.trimIndent(), null).use { c ->
            while (c.moveToNext()) {
                out += Triple(c.getInt(0), c.getString(1), c.getString(2) to c.getLong(3))
            }
        }
        return out
    }

    fun drawResult(draw: Int): Pair<List<Int>, Int>? =
        readableDatabase.rawQuery("""
            SELECT n1,n2,n3,n4,n5,n6,bonus FROM draws WHERE draw_no=?
        """.trimIndent(), arrayOf(draw.toString())).use { c ->
            if (!c.moveToFirst()) null
            else {
                val numbers = (0..5).map { c.getInt(it) }
                val bonus = c.getInt(6)
                numbers to bonus
            }
        }

    fun winningNumbers(draw: Int): Set<Int>? =
        readableDatabase.rawQuery("""
            SELECT n1,n2,n3,n4,n5,n6 FROM draws WHERE draw_no=?
        """.trimIndent(), arrayOf(draw.toString())).use { c ->
            if (!c.moveToFirst()) null
            else (0..5).map { c.getInt(it) }.toSet()
        }
}
