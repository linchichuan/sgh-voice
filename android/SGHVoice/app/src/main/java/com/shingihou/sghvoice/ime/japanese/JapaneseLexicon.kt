package com.shingihou.sghvoice.ime.japanese

import android.content.Context
import java.io.InputStream

data class JapaneseLexiconEntry(
    val text: String,
    val score: Int = 0
)

fun interface JapaneseLexicon {
    /** Exact lookup by a kana reading. Katakana is normalized to hiragana. */
    fun lookup(reading: String): List<JapaneseLexiconEntry>

    /**
     * Returns bounded predictions whose normalized reading starts with
     * [readingPrefix]. Exact lookup remains a separate, higher-priority tier.
     */
    fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<JapaneseLexiconEntry> = emptyList()
}

/**
 * In-memory reader for the compact, generated JMdict candidate asset.
 *
 * File format (UTF-8):
 * `reading<TAB>score<TAB>candidate`
 *
 * The class is Android-free apart from the separate [AndroidJapaneseLexicon]
 * adapter, allowing parser and ranking behavior to be tested on the JVM.
 */
class CompactJapaneseLexicon private constructor(
    private val entriesByReading: Map<String, List<JapaneseLexiconEntry>>
) : JapaneseLexicon {

    private val sortedReadings = entriesByReading.keys.sorted()

    override fun lookup(reading: String): List<JapaneseLexiconEntry> {
        val normalized = JapaneseScripts.katakanaToHiragana(reading.trim())
        if (normalized.isEmpty()) return emptyList()
        return entriesByReading[normalized].orEmpty()
    }

    override fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<JapaneseLexiconEntry> {
        if (limit <= 0) return emptyList()
        val prefix = JapaneseScripts.katakanaToHiragana(readingPrefix.trim())
        if (prefix.isEmpty()) return emptyList()

        val collected = mutableMapOf<String, JapaneseLexiconEntry>()
        var readingIndex = lowerBound(sortedReadings, prefix)
        var readingsScanned = 0
        var candidatesScanned = 0
        while (
            readingIndex < sortedReadings.size &&
            readingsScanned < MAX_PREFIX_READINGS_TO_SCAN &&
            candidatesScanned < MAX_PREFIX_CANDIDATES_TO_SCAN
        ) {
            val candidateReading = sortedReadings[readingIndex]
            if (!candidateReading.startsWith(prefix)) break

            val completionPenalty = (
                candidateReading.length - prefix.length
                ).coerceAtLeast(0) * PREFIX_COMPLETION_PENALTY
            for (entry in entriesByReading[candidateReading].orEmpty()) {
                if (candidatesScanned >= MAX_PREFIX_CANDIDATES_TO_SCAN) break
                val adjusted = entry.copy(score = entry.score - completionPenalty)
                val old = collected[adjusted.text]
                if (old == null || adjusted.score > old.score) {
                    collected[adjusted.text] = adjusted
                }
                candidatesScanned += 1
            }

            readingsScanned += 1
            readingIndex += 1
        }

        return collected.values
            .sortedWith(
                compareByDescending<JapaneseLexiconEntry> { it.score }
                    .thenBy { it.text.length }
                    .thenBy { it.text }
            )
            .take(limit)
    }

    val readingCount: Int
        get() = entriesByReading.size

    val candidateCount: Int
        get() = entriesByReading.values.sumOf { it.size }

    companion object {
        private const val MAX_PREFIX_READINGS_TO_SCAN = 64
        private const val MAX_PREFIX_CANDIDATES_TO_SCAN = 256
        // JMdict priority scores span roughly 2,000–5,100. A meaningful
        // per-kana completion cost prevents a longer high-priority compound
        // (for example 日本酒) from outranking its common shorter completion
        // (日本) while preserving score order among similarly sized matches.
        private const val PREFIX_COMPLETION_PENALTY = 1_000

        fun load(
            input: InputStream,
            maxCandidatesPerReading: Int = 24
        ): CompactJapaneseLexicon {
            require(maxCandidatesPerReading > 0) {
                "maxCandidatesPerReading must be greater than zero."
            }

            val collected =
                mutableMapOf<String, MutableMap<String, JapaneseLexiconEntry>>()
            input.bufferedReader(Charsets.UTF_8).useLines { lines ->
                lines.forEach { line ->
                    if (line.isBlank() || line.startsWith("#")) return@forEach
                    val columns = line.split('\t', limit = 3)
                    if (columns.size != 3) return@forEach

                    val reading =
                        JapaneseScripts.katakanaToHiragana(columns[0].trim())
                    val score = columns[1].toIntOrNull() ?: return@forEach
                    val candidate = columns[2]
                    if (
                        reading.isBlank() ||
                        candidate.isBlank() ||
                        '\n' in candidate ||
                        '\r' in candidate ||
                        '\t' in candidate
                    ) {
                        return@forEach
                    }

                    val byText = collected.getOrPut(reading) { mutableMapOf() }
                    val old = byText[candidate]
                    if (old == null || score > old.score) {
                        byText[candidate] = JapaneseLexiconEntry(candidate, score)
                    }
                }
            }

            val ranked = collected.mapValues { (_, byText) ->
                byText.values
                    .sortedWith(
                        compareByDescending<JapaneseLexiconEntry> { it.score }
                            .thenBy { it.text.length }
                            .thenBy { it.text }
                    )
                    .take(maxCandidatesPerReading)
            }
            return CompactJapaneseLexicon(ranked)
        }
    }

    private fun lowerBound(values: List<String>, target: String): Int {
        var low = 0
        var high = values.size
        while (low < high) {
            val middle = (low + high).ushr(1)
            if (values[middle] < target) {
                low = middle + 1
            } else {
                high = middle
            }
        }
        return low
    }
}

/**
 * Android asset adapter for the generated JMdict subset.
 *
 * Loading is lazy and synchronized so keyboard startup is not blocked before
 * Japanese mode is used. A missing/corrupt asset degrades to kana fallbacks
 * rather than crashing the entire input method.
 */
class AndroidJapaneseLexicon(context: Context) : JapaneseLexicon {
    companion object {
        const val LEXICON_ASSET_PATH = "japanese/jmdict_common.tsv"
        const val SNAPSHOT_ASSET_PATH = "japanese/snapshot.json"
        const val ATTRIBUTION_ASSET_PATH = "japanese/ATTRIBUTION.txt"
        const val LICENCE_ASSET_PATH = "japanese/CC-BY-SA-4.0.txt"
    }

    private val appContext = context.applicationContext
    private val delegate: JapaneseLexicon by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        runCatching {
            appContext.assets.open(LEXICON_ASSET_PATH).use {
                CompactJapaneseLexicon.load(it)
            }
        }.getOrElse {
            JapaneseLexicon { emptyList() }
        }
    }

    override fun lookup(reading: String): List<JapaneseLexiconEntry> =
        delegate.lookup(reading)

    override fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<JapaneseLexiconEntry> =
        delegate.lookupPrefix(readingPrefix, limit)

    /** Triggers asset parsing away from the first candidate request. */
    fun warmUp() {
        delegate.lookup("")
    }
}
