package com.shingihou.sghvoice.ime

import android.content.Context

/**
 * Production Traditional Chinese lexicon backed by pinned McBopomofo data.
 *
 * The large sorted assets are memory-mapped and searched through sparse
 * indexes. Manual Zhuyin stays completely on-device while avoiding the heap
 * and startup cost of materializing more than 150,000 candidates as Maps.
 */
class AndroidZhuyinLexicon(context: Context) : ZhuyinLexicon {

    companion object {
        private const val EXACT_ASSET_PATH =
            "zhuyin/traditional_zhuyin_exact.zlex"
        private const val EXACT_INDEX_PATH =
            "zhuyin/traditional_zhuyin_exact.zidx"
        private const val FOLDED_ASSET_PATH =
            "zhuyin/traditional_zhuyin_folded.zlex"
        private const val FOLDED_INDEX_PATH =
            "zhuyin/traditional_zhuyin_folded.zidx"
        private const val CONTEXT_ASSET_PATH =
            "zhuyin/traditional_zhuyin_context.zlex"
        private const val CONTEXT_INDEX_PATH =
            "zhuyin/traditional_zhuyin_context.zidx"

        private const val SEED_SCORE_OFFSET = 1_000_000
        private const val MAX_PREFIX_READINGS_TO_SCAN = 64
        private const val MAX_PREFIX_CANDIDATES_TO_SCAN = 256
        private const val PREFIX_COMPLETION_PENALTY = 8
    }

    private val appContext = context.applicationContext
    private val userLexicon = UserZhuyinLexiconStore(appContext)
    private val exactAsset = IndexedZhuyinAsset(
        appContext,
        EXACT_ASSET_PATH,
        EXACT_INDEX_PATH
    )
    private val foldedAsset = IndexedZhuyinAsset(
        appContext,
        FOLDED_ASSET_PATH,
        FOLDED_INDEX_PATH
    )
    private val contextAsset = IndexedZhuyinAsset(
        appContext,
        CONTEXT_ASSET_PATH,
        CONTEXT_INDEX_PATH
    )

    override fun lookup(reading: String): List<ZhuyinLexiconEntry> {
        val normalized = canonicalizeZhuyinReading(reading)
        return mergeRankedEntries(
            userLexicon.lookup(normalized) +
                PhaseOneZhuyinLexicon.lookup(normalized).map(::boostSeedEntry),
            exactAsset.lookupExact(normalized),
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
            userLexicon.lookupToneFolded(reading, limit) +
                PhaseOneZhuyinLexicon.lookupToneFolded(reading, limit)
                    .map(::boostSeedEntry),
            foldedAsset.lookupExact(folded),
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
        userLexicon.lookupPrefix(prefix, limit)
            .forEach { entry -> mergeBest(collected, entry) }
        PhaseOneZhuyinLexicon.lookupPrefix(prefix, limit)
            .map(::boostSeedEntry)
            .forEach { entry -> mergeBest(collected, entry) }

        var candidatesScanned = 0
        exactAsset.lookupPrefix(prefix, MAX_PREFIX_READINGS_TO_SCAN)
            .forEach { row ->
                if (candidatesScanned >= MAX_PREFIX_CANDIDATES_TO_SCAN) return@forEach
                val completionPenalty = (
                    row.key.length - prefix.length
                    ).coerceAtLeast(0) * PREFIX_COMPLETION_PENALTY
                row.entries.forEach { entry ->
                    if (candidatesScanned >= MAX_PREFIX_CANDIDATES_TO_SCAN) {
                        return@forEach
                    }
                    mergeBest(
                        collected,
                        entry.copy(score = entry.score - completionPenalty)
                    )
                    candidatesScanned += 1
                }
            }

        return collected.values
            .sortedByDescending { it.score }
            .take(limit)
    }

    override fun lookupNext(
        previousText: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val prefix = trailingHanCharacter(previousText) ?: return emptyList()
        return mergeRankedEntries(
            userLexicon.lookupNext(previousText, limit),
            contextAsset.lookupExact(prefix),
            limit
        )
    }

    /** Maps the exact, tone-folded and associated assets off the keypress path. */
    fun warmUp() {
        exactAsset.warmUp()
        foldedAsset.warmUp()
        contextAsset.warmUp()
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
}

internal fun trailingHanCharacter(text: String): String? {
    if (text.isEmpty()) return null
    val codepoint = text.codePointBefore(text.length)
    val isHan = codepoint == 0x3007 ||
        codepoint in 0x3400..0x4DBF ||
        codepoint in 0x4E00..0x9FFF ||
        codepoint in 0xF900..0xFAFF ||
        codepoint in 0x20000..0x323AF
    return if (isHan) String(Character.toChars(codepoint)) else null
}
