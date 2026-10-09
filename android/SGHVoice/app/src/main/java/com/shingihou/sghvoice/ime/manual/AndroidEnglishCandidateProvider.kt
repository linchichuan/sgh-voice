package com.shingihou.sghvoice.ime.manual

import android.content.Context
import java.io.InputStream
import java.util.Locale
import java.util.PriorityQueue

/** Sorted offline word/frequency table; prefix queries retain only their top K. */
class CompactEnglishLexicon private constructor(
    private val entries: List<EnglishCandidate>
) : EnglishCandidateProvider {
    val wordCount: Int get() = entries.size

    override fun candidates(prefix: String, limit: Int): List<EnglishCandidate> {
        if (limit <= 0 || prefix.isBlank()) return emptyList()
        val normalized = prefix.lowercase(Locale.ROOT)
        var low = 0
        var high = entries.size
        while (low < high) {
            val middle = (low + high).ushr(1)
            if (entries[middle].text < normalized) low = middle + 1 else high = middle
        }
        val bestFirst = compareByDescending<EnglishCandidate> { it.score }.thenBy { it.text }
        val best = PriorityQueue(bestFirst.reversed())
        while (low < entries.size) {
            val entry = entries[low++]
            if (!entry.text.startsWith(normalized)) break
            if (entry.text.length <= normalized.length) continue
            if (best.size < limit) best.add(entry)
            else if (bestFirst.compare(entry, best.peek()) < 0) {
                best.remove()
                best.add(entry)
            }
        }
        return best.sortedWith(bestFirst)
    }

    companion object {
        private val WORD = Regex("[a-z]{2,32}(?:'[a-z]+)?")

        fun load(input: InputStream): CompactEnglishLexicon {
            val words = mutableMapOf<String, Int>()
            input.bufferedReader(Charsets.UTF_8).useLines { lines ->
                lines.forEach { line ->
                    if (line.isBlank() || line.startsWith("#")) return@forEach
                    val columns = line.split('\t')
                    if (columns.size != 2) return@forEach
                    val word = columns[0]
                    val frequency = columns[1].toIntOrNull() ?: return@forEach
                    if (word.length > 32 || !WORD.matches(word) || frequency !in 1..255) return@forEach
                    words[word] = maxOf(frequency, words[word] ?: 0)
                }
            }
            require(words.isNotEmpty()) { "Empty English lexicon" }
            return CompactEnglishLexicon(words.toSortedMap().map { (word, frequency) ->
                EnglishCandidate(word, frequency)
            })
        }
    }
}

/** Existing everyday seed words keep their original order ahead of corpus words. */
class SeededEnglishCandidateProvider(
    private val lexicon: EnglishCandidateProvider,
    private val seeds: EnglishCandidateProvider = LocalEnglishCandidateProvider
) : EnglishCandidateProvider {
    override fun candidates(prefix: String, limit: Int): List<EnglishCandidate> {
        if (limit <= 0 || prefix.isBlank()) return emptyList()
        val preferred = seeds.candidates(prefix, limit).map { it.copy(score = 10_000 + it.score) }
        if (preferred.size >= limit) return preferred
        val seen = preferred.map { it.text }.toSet()
        val extra = lexicon.candidates(prefix, limit + preferred.size)
            .filterNot { it.text in seen }
            .take(limit - preferred.size)
        return preferred + extra
    }
}

/** Asset parsing is lazy/off the keypress path when warmUp is called by the IME. */
class AndroidEnglishCandidateProvider(context: Context) : EnglishCandidateProvider {
    companion object {
        const val LEXICON_ASSET_PATH = "english/aosp_english.tsv"
    }

    private val assets = context.applicationContext.assets
    private val delegate: EnglishCandidateProvider by lazy(LazyThreadSafetyMode.SYNCHRONIZED) {
        runCatching {
            assets.open(LEXICON_ASSET_PATH).use { SeededEnglishCandidateProvider(CompactEnglishLexicon.load(it)) }
        }.getOrElse { LocalEnglishCandidateProvider }
    }

    override fun candidates(prefix: String, limit: Int): List<EnglishCandidate> =
        delegate.candidates(prefix, limit)

    fun warmUp() {
        delegate
    }
}
