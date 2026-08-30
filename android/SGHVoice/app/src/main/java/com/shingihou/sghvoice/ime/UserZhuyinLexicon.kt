package com.shingihou.sghvoice.ime

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject

internal data class UserZhuyinEntry(
    val text: String,
    val reading: String
)

internal fun normalizeUserZhuyinEntry(
    rawText: String,
    rawReading: String
): UserZhuyinEntry? {
    val text = rawText.trim()
    if (text.isEmpty()) return null
    val codePointCount = text.codePointCount(0, text.length)
    if (codePointCount !in 1..12 || !text.allHanCodePoints()) return null

    val composer = ZhuyinComposer()
    if (!composer.setComposition(rawReading) || !composer.isCompleteComposition) return null
    if (composer.syllables.size != codePointCount) return null
    return UserZhuyinEntry(text, composer.normalizedReading)
}

internal class UserZhuyinIndex(
    val entries: List<UserZhuyinEntry>
) : ZhuyinLexicon {
    companion object {
        private const val USER_SCORE_OFFSET = 2_000_000
    }

    private val exactEntries: Map<String, List<ZhuyinLexiconEntry>> = entries
        .withIndex()
        .groupBy(
            keySelector = { it.value.reading },
            valueTransform = { indexed ->
                ZhuyinLexiconEntry(
                    indexed.value.text,
                    USER_SCORE_OFFSET - indexed.index
                )
            }
        )
    private val toneFoldedEntries: Map<String, List<ZhuyinLexiconEntry>> =
        exactEntries.entries
            .groupBy(
                keySelector = { foldZhuyinTones(it.key) },
                valueTransform = { it.value }
            )
            .mapValues { (_, groups) ->
                groups.flatten()
                    .sortedByDescending { it.score }
                    .distinctBy { it.text }
            }
    private val contextEntries: Map<String, List<ZhuyinLexiconEntry>> = buildMap {
        val collected = mutableMapOf<String, MutableList<ZhuyinLexiconEntry>>()
        this@UserZhuyinIndex.entries.forEachIndexed { index, entry ->
            if (entry.text.codePointCount(0, entry.text.length) < 2) return@forEachIndexed
            val prefixEnd = entry.text.offsetByCodePoints(0, 1)
            val prefix = entry.text.substring(0, prefixEnd)
            val suffix = entry.text.substring(prefixEnd)
            collected.getOrPut(prefix) { mutableListOf() } += ZhuyinLexiconEntry(
                suffix,
                USER_SCORE_OFFSET - index
            )
        }
        collected.forEach { (prefix, values) ->
            put(
                prefix,
                values.sortedByDescending { it.score }.distinctBy { it.text }
            )
        }
    }

    override fun lookup(reading: String): List<ZhuyinLexiconEntry> =
        exactEntries[canonicalizeZhuyinReading(reading)].orEmpty()

    override fun lookupToneFolded(
        reading: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        return toneFoldedEntries[foldZhuyinTones(reading)].orEmpty().take(limit)
    }

    override fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val prefix = canonicalizeZhuyinReading(readingPrefix)
        return exactEntries.asSequence()
            .filter { (reading, _) -> reading.startsWith(prefix) }
            .flatMap { it.value.asSequence() }
            .sortedByDescending { it.score }
            .distinctBy { it.text }
            .take(limit)
            .toList()
    }

    override fun lookupNext(
        previousText: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val prefix = trailingHanCharacter(previousText) ?: return emptyList()
        return contextEntries[prefix].orEmpty().take(limit)
    }
}

/** On-device user dictionary with explicit, validated Zhuyin readings. */
internal class UserZhuyinLexiconStore(context: Context) : ZhuyinLexicon {
    companion object {
        private const val PREF_NAME = "sgh_voice_dictionary"
        private const val KEY_ENTRIES = "custom_zhuyin_entries_v1"
        private const val MAX_ENTRIES = 200
    }

    private val preferences = context.applicationContext.getSharedPreferences(
        PREF_NAME,
        Context.MODE_PRIVATE
    )

    @Volatile
    private var index = UserZhuyinIndex(loadEntries())

    private val preferenceListener =
        SharedPreferences.OnSharedPreferenceChangeListener { _, key ->
            if (key == KEY_ENTRIES) index = UserZhuyinIndex(loadEntries())
        }

    init {
        preferences.registerOnSharedPreferenceChangeListener(preferenceListener)
    }

    fun getEntries(): List<UserZhuyinEntry> = index.entries

    fun addEntry(text: String, reading: String): Boolean {
        val entry = normalizeUserZhuyinEntry(text, reading) ?: return false
        val current = index.entries
        if (entry in current || current.size >= MAX_ENTRIES) return false
        persist(current + entry)
        return true
    }

    fun removeEntry(entry: UserZhuyinEntry) {
        persist(index.entries.filterNot { it == entry })
    }

    override fun lookup(reading: String): List<ZhuyinLexiconEntry> = index.lookup(reading)

    override fun lookupToneFolded(
        reading: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> = index.lookupToneFolded(reading, limit)

    override fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> = index.lookupPrefix(readingPrefix, limit)

    override fun lookupNext(
        previousText: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> = index.lookupNext(previousText, limit)

    private fun persist(entries: List<UserZhuyinEntry>) {
        index = UserZhuyinIndex(entries)
        val json = JSONArray().apply {
            entries.forEach { entry ->
                put(
                    JSONObject()
                        .put("text", entry.text)
                        .put("reading", entry.reading)
                )
            }
        }
        preferences.edit().putString(KEY_ENTRIES, json.toString()).apply()
    }

    private fun loadEntries(): List<UserZhuyinEntry> {
        val raw = preferences.getString(KEY_ENTRIES, null) ?: return emptyList()
        return try {
            val array = JSONArray(raw)
            buildList {
                for (index in 0 until array.length()) {
                    val item = array.optJSONObject(index) ?: continue
                    normalizeUserZhuyinEntry(
                        item.optString("text"),
                        item.optString("reading")
                    )?.let(::add)
                    if (size >= MAX_ENTRIES) break
                }
            }.distinct()
        } catch (_: Exception) {
            emptyList()
        }
    }
}

private fun String.allHanCodePoints(): Boolean {
    var offset = 0
    while (offset < length) {
        val codepoint = codePointAt(offset)
        val isHan = codepoint == 0x3007 ||
            codepoint in 0x3400..0x4DBF ||
            codepoint in 0x4E00..0x9FFF ||
            codepoint in 0xF900..0xFAFF ||
            codepoint in 0x20000..0x323AF
        if (!isHan) return false
        offset += Character.charCount(codepoint)
    }
    return true
}
