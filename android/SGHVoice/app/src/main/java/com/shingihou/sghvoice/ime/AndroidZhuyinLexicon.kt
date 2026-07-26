package com.shingihou.sghvoice.ime

import android.content.Context

/**
 * Loads common Traditional Chinese single-character candidates from the compact
 * Unicode Unihan asset, then merges SGH Voice's small phrase seed lexicon ahead
 * of those candidates.
 *
 * This keeps manual input completely offline. It does not send Zhuyin keystrokes
 * to Whisper, an LLM, or any other network service.
 */
class AndroidZhuyinLexicon(context: Context) : ZhuyinLexicon {

    companion object {
        private const val ASSET_PATH = "zhuyin/unihan_zhuyin_candidates.tsv"
        private const val SEED_SCORE_OFFSET = 1_000_000
        private const val MAX_PREFIX_READINGS_TO_SCAN = 64
        private const val MAX_PREFIX_CANDIDATES_TO_SCAN = 256
        private const val PREFIX_COMPLETION_PENALTY = 8
    }

    private val appContext = context.applicationContext
    private val entriesByReading: Map<String, List<ZhuyinLexiconEntry>> by lazy(
        LazyThreadSafetyMode.SYNCHRONIZED
    ) {
        loadAllAssetEntries()
    }
    private val entriesByToneFoldedReading: Map<String, List<ZhuyinLexiconEntry>> by lazy(
        LazyThreadSafetyMode.SYNCHRONIZED
    ) {
        buildToneFoldedIndex(entriesByReading)
    }
    private val sortedReadings: List<String> by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        entriesByReading.keys.sorted()
    }

    override fun lookup(reading: String): List<ZhuyinLexiconEntry> {
        val normalized = canonicalizeZhuyinReading(reading)
        return mergeRankedEntries(
            PhaseOneZhuyinLexicon.lookup(normalized).map(::boostSeedEntry),
            entriesByReading[normalized].orEmpty(),
            limit = Int.MAX_VALUE
        )
    }

    override fun lookupToneFolded(
        reading: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val folded = foldZhuyinTones(reading)
        if (folded.isEmpty()) return emptyList()
        return mergeRankedEntries(
            PhaseOneZhuyinLexicon.lookupToneFolded(reading, limit)
                .map(::boostSeedEntry),
            entriesByToneFoldedReading[folded].orEmpty(),
            limit = limit
        )
    }

    override fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val prefix = canonicalizeZhuyinReading(readingPrefix)
        if (prefix.isEmpty() || ' ' in prefix) return emptyList()

        val collected = mutableMapOf<String, ZhuyinLexiconEntry>()
        PhaseOneZhuyinLexicon.lookupPrefix(prefix, limit)
            .map(::boostSeedEntry)
            .forEach { entry -> mergeBest(collected, entry) }

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
                mergeBest(
                    collected,
                    entry.copy(score = entry.score - completionPenalty)
                )
                candidatesScanned += 1
            }
            readingsScanned += 1
            readingIndex += 1
        }

        return collected.values
            .sortedByDescending { it.score }
            .take(limit)
    }

    /** Loads the compact asset off the first keypress path. */
    fun warmUp() {
        entriesByReading.size
        entriesByToneFoldedReading.size
        sortedReadings.size
    }

    private fun loadAllAssetEntries(): Map<String, List<ZhuyinLexiconEntry>> {
        val result = mutableMapOf<String, List<ZhuyinLexiconEntry>>()
        appContext.assets.open(ASSET_PATH).bufferedReader(Charsets.UTF_8).useLines { lines ->
            lines.forEach { line ->
                if (line.isEmpty() || line.startsWith("#")) return@forEach
                val reading = line.substringBefore('\t')
                if (reading.isBlank() || '\t' !in line) return@forEach
                val entries = line
                    .substringAfter('\t')
                    .split('|')
                    .mapNotNull { encoded ->
                        val separator = encoded.lastIndexOf(':')
                        if (separator <= 0) return@mapNotNull null
                        val text = encoded.substring(0, separator)
                        val score = encoded.substring(separator + 1).toIntOrNull() ?: 0
                        if (text.isBlank()) null else ZhuyinLexiconEntry(text, score)
                    }
                if (entries.isNotEmpty()) {
                    result[reading] = entries
                }
            }
        }
        return result
    }

    private fun buildToneFoldedIndex(
        exactEntries: Map<String, List<ZhuyinLexiconEntry>>
    ): Map<String, List<ZhuyinLexiconEntry>> {
        val collected =
            mutableMapOf<String, MutableMap<String, ZhuyinLexiconEntry>>()
        exactEntries.forEach { (reading, entries) ->
            val folded = foldZhuyinTones(reading)
            if (folded.isEmpty()) return@forEach
            val byText = collected.getOrPut(folded) { mutableMapOf() }
            entries.forEach { entry -> mergeBest(byText, entry) }
        }
        return collected.mapValues { (_, byText) ->
            byText.values.sortedByDescending { it.score }
        }
    }

    private fun boostSeedEntry(entry: ZhuyinLexiconEntry): ZhuyinLexiconEntry =
        entry.copy(score = SEED_SCORE_OFFSET + entry.score)

    private fun mergeRankedEntries(
        first: List<ZhuyinLexiconEntry>,
        second: List<ZhuyinLexiconEntry>,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val collected = mutableMapOf<String, ZhuyinLexiconEntry>()
        first.forEach { mergeBest(collected, it) }
        second.forEach { mergeBest(collected, it) }
        return collected.values
            .sortedByDescending { it.score }
            .take(limit)
    }

    private fun mergeBest(
        entries: MutableMap<String, ZhuyinLexiconEntry>,
        candidate: ZhuyinLexiconEntry
    ) {
        val old = entries[candidate.text]
        if (old == null || candidate.score > old.score) {
            entries[candidate.text] = candidate
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
