package com.shingihou.sghvoice.ime

/**
 * A ranked entry returned by a [ZhuyinLexicon].
 *
 * The composer deliberately keeps the lexicon contract small so Phase 1's seed
 * data can later be replaced by an on-device database without changing the IME UI.
 */
data class ZhuyinLexiconEntry(
    val text: String,
    val score: Int = 0
)

fun interface ZhuyinLexicon {
    /**
     * Looks up a canonical reading whose syllables are separated by one ASCII
     * space and whose tone marks follow their syllable, for example
     * `ㄋㄧˇ ㄏㄠˇ`.
     */
    fun lookup(reading: String): List<ZhuyinLexiconEntry>

    /**
     * Looks up readings after removing tone marks. Implementations should keep
     * this bounded and rank more common candidates first.
     */
    fun lookupToneFolded(
        reading: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> = emptyList()

    /**
     * Looks up candidates whose canonical reading starts with [readingPrefix].
     * This is used only while the final syllable is incomplete.
     */
    fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> = emptyList()
}

internal fun canonicalizeZhuyinReading(reading: String): String =
    reading.trim()
        .split(Regex("\\s+"))
        .filter { it.isNotEmpty() }
        .joinToString(" ")

internal fun foldZhuyinTones(reading: String): String =
    canonicalizeZhuyinReading(reading)
        .filterNot { it in ZhuyinComposer.TONE_MARKS }

enum class ZhuyinCandidateSource {
    LEXICON,
    TONE_FOLDED,
    PREFIX_PREDICTION,
    SEGMENTED,
    RAW_FALLBACK
}

/**
 * A value the keyboard can render in its candidate strip and later commit.
 */
data class ZhuyinCandidate(
    val text: String,
    val reading: String,
    val source: ZhuyinCandidateSource,
    val score: Int = 0
)

data class ZhuyinKey(
    val hardwareKey: Char,
    val symbol: Char
)

/**
 * Pure Kotlin state holder for a small, Phase 1 Zhuyin input method.
 *
 * This class handles phonetic composition and candidate selection only. It does
 * not claim to be a complete Mandarin input engine: prediction, fuzzy matching,
 * user learning and a production-size lexicon belong in a future lexicon
 * implementation injected through [lexicon].
 */
class ZhuyinComposer(
    private val lexicon: ZhuyinLexicon = PhaseOneZhuyinLexicon
) {
    companion object {
        const val DEFAULT_CANDIDATE_LIMIT = 9
        private const val MAX_PREDICTION_QUERY_RESULTS = 24
        private const val MAX_CANDIDATES_PER_SYLLABLE = 6
        private const val MAX_BEAM_WIDTH = 24

        val INITIALS: Set<Char> =
            "ㄅㄆㄇㄈㄉㄊㄋㄌㄍㄎㄏㄐㄑㄒㄓㄔㄕㄖㄗㄘㄙ".toSet()
        val MEDIALS: Set<Char> = "ㄧㄨㄩ".toSet()
        val FINALS: Set<Char> = "ㄚㄛㄜㄝㄞㄟㄠㄡㄢㄣㄤㄥㄦ".toSet()
        val TONE_MARKS: Set<Char> = "ˊˇˋ˙".toSet()
        val PHONETIC_SYMBOLS: Set<Char> = INITIALS + MEDIALS + FINALS
        val STANDARD_SYMBOLS: Set<Char> = PHONETIC_SYMBOLS + TONE_MARKS

        /**
         * Standard Taiwan (大千式) keyboard mapping, arranged by physical rows.
         * A touchscreen keyboard may render these rows directly or only use
         * [STANDARD_KEY_MAP] to translate its own key views.
         */
        val STANDARD_KEYBOARD_ROWS: List<List<ZhuyinKey>> = listOf(
            "1234567890-".zip("ㄅㄉˇˋㄓˊ˙ㄚㄞㄢㄦ").map { ZhuyinKey(it.first, it.second) },
            "qwertyuiop".zip("ㄆㄊㄍㄐㄔㄗㄧㄛㄟㄣ").map { ZhuyinKey(it.first, it.second) },
            "asdfghjkl;".zip("ㄇㄋㄎㄑㄕㄘㄨㄜㄠㄤ").map { ZhuyinKey(it.first, it.second) },
            "zxcvbnm,./".zip("ㄈㄌㄏㄒㄖㄙㄩㄝㄡㄥ").map { ZhuyinKey(it.first, it.second) }
        )

        val STANDARD_KEY_MAP: Map<Char, Char> =
            STANDARD_KEYBOARD_ROWS.flatten().associate { it.hardwareKey to it.symbol }

        private val APICAL_INITIALS = "ㄓㄔㄕㄖㄗㄘㄙ".toSet()
        private val PALATAL_INITIALS = "ㄐㄑㄒ".toSet()
        private val VELAR_INITIALS = "ㄍㄎㄏ".toSet()
        private val LABIAL_INITIALS = "ㄅㄆㄇㄈ".toSet()
        private val RETROFLEX_AND_DENTAL_INITIALS = "ㄓㄔㄕㄖㄗㄘㄙ".toSet()

        private val FINALS_AFTER_MEDIAL: Map<Char, Set<Char>> = mapOf(
            'ㄧ' to "ㄚㄛㄝㄠㄡㄢㄣㄤㄥ".toSet(),
            'ㄨ' to "ㄚㄛㄞㄟㄢㄣㄤㄥ".toSet(),
            'ㄩ' to "ㄝㄢㄣㄥ".toSet()
        )
    }

    private val completedSyllables = mutableListOf<String>()
    private val current = StringBuilder()

    /**
     * Text intended for the composing span. A trailing space is retained after
     * [separateSyllable] so the user can see the active syllable boundary.
     */
    val composition: String
        get() = buildString {
            append(completedSyllables.joinToString(" "))
            if (completedSyllables.isNotEmpty()) append(' ')
            append(current)
        }

    val currentSyllable: String
        get() = current.toString()

    val syllables: List<String>
        get() = buildList {
            addAll(completedSyllables)
            if (current.isNotEmpty()) add(current.toString())
        }

    val normalizedReading: String
        get() = syllables.joinToString(" ")

    val hasComposition: Boolean
        get() = completedSyllables.isNotEmpty() || current.isNotEmpty()

    /**
     * Appends one Bopomofo symbol. ASCII space is accepted as a syllable
     * delimiter. A phonetic symbol after a tone mark starts the next syllable
     * automatically; an initial after a complete unmarked syllable does too.
     *
     * @return false when [symbol] is unknown or would make the syllable invalid.
     */
    fun append(symbol: Char): Boolean {
        if (symbol == ' ') return separateSyllable()
        if (symbol !in STANDARD_SYMBOLS) return false

        if (current.isNotEmpty() && symbol !in TONE_MARKS) {
            val parts = parseSyllable(current.toString()) ?: return false
            val startsAfterTone = parts.tone != null
            val startsWithNewInitial =
                symbol in INITIALS && isCompleteSyllable(current.toString())
            if (startsAfterTone || startsWithNewInitial) {
                completedSyllables += current.toString()
                current.clear()
            }
        }

        var proposed = current.toString() + symbol
        if (parseSyllable(proposed) == null) {
            // First-tone syllables have no visible tone key. When the next
            // symbol cannot belong to an already complete syllable (for
            // example ㄓㄨㄥ followed by ㄨ in「中文」), start a new syllable
            // automatically instead of forcing a dedicated delimiter key.
            if (!isCompleteSyllable(current.toString()) || parseSyllable(symbol.toString()) == null) {
                return false
            }
            completedSyllables += current.toString()
            current.clear()
            proposed = symbol.toString()
        }
        if (symbol in TONE_MARKS && !isCompleteSyllable(current.toString())) return false

        current.append(symbol)
        return true
    }

    /**
     * Translates one standard Taiwan keyboard key to Zhuyin and appends it.
     * Uppercase Latin keys are accepted. Space inserts a syllable delimiter.
     */
    fun appendKey(key: Char): Boolean {
        if (key == ' ') return separateSyllable()
        val symbol = STANDARD_KEY_MAP[key.lowercaseChar()] ?: return false
        return append(symbol)
    }

    /**
     * Replaces the full composition transactionally. Neutral tone written in
     * display form before a syllable (`˙ㄉㄜ`) is normalized to the internal
     * key form (`ㄉㄜ˙`).
     */
    fun setComposition(reading: String): Boolean {
        val oldCompleted = completedSyllables.toList()
        val oldCurrent = current.toString()
        clear()

        val tokens = reading.trim().split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (tokens.isEmpty()) return true

        val accepted = tokens.withIndex().all { (index, rawToken) ->
            val token =
                if (rawToken.length > 1 && rawToken.first() == '˙') {
                    rawToken.drop(1) + '˙'
                } else {
                    rawToken
                }
            token.all(::append) &&
                (index == tokens.lastIndex || separateSyllable())
        }

        if (!accepted) {
            clear()
            completedSyllables += oldCompleted
            current.append(oldCurrent)
        }
        return accepted
    }

    /**
     * Finishes the current valid syllable and starts a new one.
     */
    fun separateSyllable(): Boolean {
        if (!isCompleteSyllable(current.toString())) return false
        completedSyllables += current.toString()
        current.clear()
        return true
    }

    /**
     * Removes one composing unit. When the cursor is after a delimiter, the
     * first backspace removes that delimiter and reopens the preceding syllable.
     */
    fun backspace(): Boolean {
        if (current.isNotEmpty()) {
            current.deleteCharAt(current.lastIndex)
            return true
        }
        if (completedSyllables.isNotEmpty()) {
            current.append(completedSyllables.removeAt(completedSyllables.lastIndex))
            return true
        }
        return false
    }

    fun clear() {
        completedSyllables.clear()
        current.clear()
    }

    /**
     * Returns ranked lexicon candidates plus a raw Zhuyin fallback when room is
     * available. The raw fallback never inserts internal syllable spaces.
     */
    fun getCandidates(
        limit: Int = DEFAULT_CANDIDATE_LIMIT,
        includeRawFallback: Boolean = true
    ): List<ZhuyinCandidate> {
        require(limit >= 0) { "Candidate limit cannot be negative." }
        if (limit == 0 || !hasComposition) return emptyList()

        val reading = normalizedReading
        val ranked = mutableListOf<ZhuyinCandidate>()
        val seenTexts = mutableSetOf<String>()

        fun appendEntries(
            entries: List<ZhuyinLexiconEntry>,
            source: ZhuyinCandidateSource
        ) {
            if (ranked.size >= limit) return
            entries.asSequence()
                .filter { it.text.isNotBlank() }
                .sortedByDescending { it.score }
                .distinctBy { it.text }
                .forEach { entry ->
                    if (ranked.size >= limit) return@forEach
                    if (seenTexts.add(entry.text)) {
                        ranked += ZhuyinCandidate(
                            text = entry.text,
                            reading = reading,
                            source = source,
                            score = entry.score
                        )
                    }
                }
        }

        appendEntries(
            lexicon.lookup(reading),
            ZhuyinCandidateSource.LEXICON
        )
        appendEntries(
            lexicon.lookupToneFolded(
                reading,
                minOf(limit, MAX_PREDICTION_QUERY_RESULTS)
            ),
            ZhuyinCandidateSource.TONE_FOLDED
        )

        if (syllables.size == 1) {
            appendEntries(
                lexicon.lookupPrefix(
                    reading,
                    minOf(limit, MAX_PREDICTION_QUERY_RESULTS)
                ),
                ZhuyinCandidateSource.PREFIX_PREDICTION
            )
        } else if (ranked.size < limit) {
            segmentedCandidates(limit - ranked.size).forEach { candidate ->
                if (ranked.size < limit && seenTexts.add(candidate.text)) {
                    ranked += candidate
                }
            }
        }

        if (includeRawFallback && ranked.size < limit) {
            val raw = rawCandidate()
            if (seenTexts.add(raw.text)) ranked += raw
        }
        return ranked.take(limit)
    }

    /**
     * Selects the currently visible candidate at [index]. A valid selection
     * clears the composition and returns the exact value the IME should commit.
     */
    fun selectCandidate(
        index: Int,
        limit: Int = DEFAULT_CANDIDATE_LIMIT,
        includeRawFallback: Boolean = true
    ): ZhuyinCandidate? {
        val selected = getCandidates(limit, includeRawFallback).getOrNull(index) ?: return null
        clear()
        return selected
    }

    /**
     * Returns the first lexicon result, or raw Zhuyin when no result exists,
     * without changing composition state.
     */
    fun peekBestOrRaw(): ZhuyinCandidate? {
        if (!hasComposition) return null
        return getCandidates(limit = 1, includeRawFallback = false).firstOrNull()
            ?: rawCandidate()
    }

    /**
     * Commits the first lexicon result, or raw Zhuyin when no result exists.
     */
    fun commitBestOrRaw(): ZhuyinCandidate? {
        val best = peekBestOrRaw() ?: return null
        clear()
        return best
    }

    /**
     * Explicit raw fallback for unknown readings. Internal delimiter spaces are
     * removed because they are composition metadata rather than typed content.
     */
    fun commitRaw(): ZhuyinCandidate? {
        if (!hasComposition) return null
        val raw = rawCandidate()
        clear()
        return raw
    }

    private fun rawCandidate(): ZhuyinCandidate =
        ZhuyinCandidate(
            text = normalizedReading.replace(" ", ""),
            reading = normalizedReading,
            source = ZhuyinCandidateSource.RAW_FALLBACK
        )

    private fun segmentedCandidates(limit: Int): List<ZhuyinCandidate> {
        if (limit <= 0 || syllables.size < 2) return emptyList()

        data class Piece(
            val text: String,
            val score: Int,
            val matchPenalty: Int,
            val matched: Boolean
        )

        data class Beam(
            val text: String,
            val score: Long,
            val matchPenalty: Int,
            val matchedPieceCount: Int
        )

        val beamWidth = minOf(MAX_BEAM_WIDTH, maxOf(limit * 2, 1))
        var beams = listOf(Beam("", 0L, 0, 0))

        for (syllable in syllables) {
            val pieces = mutableListOf<Piece>()
            val seen = mutableSetOf<String>()

            fun appendPieces(
                entries: List<ZhuyinLexiconEntry>,
                matchPenalty: Int
            ) {
                entries.asSequence()
                    .filter { it.text.isNotBlank() }
                    .sortedByDescending { it.score }
                    .distinctBy { it.text }
                    .take(MAX_CANDIDATES_PER_SYLLABLE)
                    .forEach { entry ->
                        if (seen.add(entry.text)) {
                            pieces += Piece(
                                text = entry.text,
                                score = entry.score,
                                matchPenalty = matchPenalty,
                                matched = true
                            )
                        }
                    }
            }

            appendPieces(lexicon.lookup(syllable), matchPenalty = 0)
            appendPieces(
                lexicon.lookupToneFolded(syllable, MAX_CANDIDATES_PER_SYLLABLE),
                matchPenalty = 1
            )
            appendPieces(
                lexicon.lookupPrefix(syllable, MAX_CANDIDATES_PER_SYLLABLE),
                matchPenalty = 2
            )
            if (pieces.isEmpty()) {
                pieces += Piece(
                    text = syllable,
                    score = 0,
                    matchPenalty = 3,
                    matched = false
                )
            }

            beams = beams.asSequence()
                .flatMap { beam ->
                    pieces.asSequence().map { piece ->
                        Beam(
                            text = beam.text + piece.text,
                            score = beam.score + piece.score,
                            matchPenalty = beam.matchPenalty + piece.matchPenalty,
                            matchedPieceCount = beam.matchedPieceCount +
                                if (piece.matched) 1 else 0
                        )
                    }
                }
                .sortedWith(
                    compareBy<Beam> { it.matchPenalty }
                        .thenByDescending { it.score }
                        .thenBy { it.text.length }
                        .thenBy { it.text }
                )
                .distinctBy { it.text }
                .take(beamWidth)
                .toList()
        }

        return beams.asSequence()
            .filter { it.matchedPieceCount > 0 }
            .take(limit)
            .map { beam ->
                ZhuyinCandidate(
                    text = beam.text,
                    reading = normalizedReading,
                    source = ZhuyinCandidateSource.SEGMENTED,
                    score = beam.score.coerceIn(
                        Int.MIN_VALUE.toLong(),
                        Int.MAX_VALUE.toLong()
                    ).toInt()
                )
            }
            .toList()
    }

    private fun isCompleteSyllable(syllable: String): Boolean {
        val parts = parseSyllable(syllable) ?: return false
        if (parts.initial == null && parts.medial == null && parts.final == null) return false

        if (parts.initial in PALATAL_INITIALS && parts.medial == null) return false
        if (parts.initial != null && parts.medial == null && parts.final == null) {
            return parts.initial in APICAL_INITIALS
        }
        return true
    }

    /**
     * Parses ordering and the most important Mandarin phonotactic constraints.
     * It intentionally permits partial syllables while the user is composing.
     */
    private fun parseSyllable(syllable: String): SyllableParts? {
        if (syllable.isEmpty()) return SyllableParts()

        var initial: Char? = null
        var medial: Char? = null
        var final: Char? = null
        var tone: Char? = null
        var stage = 0

        for (symbol in syllable) {
            when (symbol) {
                in INITIALS -> {
                    if (stage != 0 || initial != null) return null
                    initial = symbol
                    stage = 1
                }

                in MEDIALS -> {
                    if (stage > 1 || medial != null) return null
                    medial = symbol
                    stage = 2
                }

                in FINALS -> {
                    if (stage > 2 || final != null) return null
                    final = symbol
                    stage = 3
                }

                in TONE_MARKS -> {
                    if (stage == 0 || tone != null || symbol != syllable.last()) return null
                    tone = symbol
                    stage = 4
                }

                else -> return null
            }
        }

        if (initial in PALATAL_INITIALS && medial != null && medial !in setOf('ㄧ', 'ㄩ')) {
            return null
        }
        if (initial in PALATAL_INITIALS && final != null && medial == null) return null
        if (initial in VELAR_INITIALS && medial in setOf('ㄧ', 'ㄩ')) return null
        if (initial in RETROFLEX_AND_DENTAL_INITIALS && medial in setOf('ㄧ', 'ㄩ')) {
            return null
        }
        if (initial in LABIAL_INITIALS && medial == 'ㄩ') return null
        if (initial == 'ㄈ' && medial == 'ㄧ') return null

        if (medial != null && final != null) {
            if (final !in FINALS_AFTER_MEDIAL.getValue(medial)) return null
        }
        if (final == 'ㄦ' && (initial != null || medial != null)) return null

        return SyllableParts(initial, medial, final, tone)
    }

    private data class SyllableParts(
        val initial: Char? = null,
        val medial: Char? = null,
        val final: Char? = null,
        val tone: Char? = null
    )
}

/**
 * Small, explicitly maintained seed lexicon for Phase 1 UI integration and
 * smoke testing. It is not a comprehensive language model or dictionary.
 */
object PhaseOneZhuyinLexicon : ZhuyinLexicon {
    private val entries: Map<String, List<ZhuyinLexiconEntry>> = mapOf(
        "ㄋㄧˇ" to ranked("你"),
        "ㄏㄠˇ" to ranked("好"),
        "ㄋㄧˇ ㄏㄠˇ" to ranked("你好"),
        "ㄨㄛˇ" to ranked("我"),
        "ㄕˋ" to ranked("是", "事", "市", "室"),
        "ㄉㄜ" to ranked("的"),
        "ㄉㄜ˙" to ranked("的"),
        "ㄌㄜ˙" to ranked("了"),
        "ㄗㄞˋ" to ranked("在"),
        "ㄧㄡˇ" to ranked("有"),
        "ㄅㄨˋ" to ranked("不"),
        "ㄖㄣˊ" to ranked("人"),
        "ㄑㄧㄥˇ" to ranked("請"),
        "ㄒㄧㄝˋ" to ranked("謝"),
        "ㄐㄧㄢˋ" to ranked("見", "件", "建"),
        "ㄏㄨㄚˋ" to ranked("話", "化", "畫"),
        "ㄓㄨㄥ" to ranked("中"),
        "ㄨㄣˊ" to ranked("文"),
        "ㄓㄨㄥ ㄨㄣˊ" to ranked("中文"),
        "ㄕㄥ" to ranked("聲"),
        "ㄧㄣ" to ranked("音"),
        "ㄕㄥ ㄧㄣ" to ranked("聲音"),
        "ㄩˇ ㄧㄣ" to ranked("語音"),
        "ㄓㄨˋ ㄧㄣ" to ranked("注音"),
        "ㄕㄨ ㄖㄨˋ ㄈㄚˇ" to ranked("輸入法"),
        "ㄊㄞˊ ㄨㄢ" to ranked("台灣"),
        "ㄖˋ ㄅㄣˇ" to ranked("日本"),
        "ㄈㄢˊ ㄊㄧˇ" to ranked("繁體"),
        "ㄐㄧㄢˇ ㄊㄧˇ" to ranked("簡體"),
        "ㄒㄧㄝˋ ㄒㄧㄝ˙" to ranked("謝謝"),
        "ㄗㄞˋ ㄐㄧㄢˋ" to ranked("再見")
    )

    override fun lookup(reading: String): List<ZhuyinLexiconEntry> =
        entries[canonicalizeZhuyinReading(reading)].orEmpty()

    override fun lookupToneFolded(
        reading: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val folded = foldZhuyinTones(reading)
        if (folded.isEmpty()) return emptyList()
        return entries.asSequence()
            .filter { (candidateReading, _) ->
                foldZhuyinTones(candidateReading) == folded
            }
            .flatMap { it.value.asSequence() }
            .sortedByDescending { it.score }
            .distinctBy { it.text }
            .take(limit)
            .toList()
    }

    override fun lookupPrefix(
        readingPrefix: String,
        limit: Int
    ): List<ZhuyinLexiconEntry> {
        if (limit <= 0) return emptyList()
        val prefix = canonicalizeZhuyinReading(readingPrefix)
        if (prefix.isEmpty()) return emptyList()
        val expectedBoundaryCount = prefix.count { it == ' ' }
        return entries.asSequence()
            .filter { (candidateReading, _) ->
                candidateReading.count { it == ' ' } == expectedBoundaryCount &&
                    candidateReading.startsWith(prefix)
            }
            .flatMap { it.value.asSequence() }
            .sortedByDescending { it.score }
            .distinctBy { it.text }
            .take(limit)
            .toList()
    }

    private fun ranked(vararg values: String): List<ZhuyinLexiconEntry> =
        values.mapIndexed { index, text ->
            ZhuyinLexiconEntry(text = text, score = values.size - index)
        }
}
