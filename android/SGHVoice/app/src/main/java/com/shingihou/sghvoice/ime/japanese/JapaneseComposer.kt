package com.shingihou.sghvoice.ime.japanese

enum class JapaneseScriptMode {
    HIRAGANA,
    KATAKANA
}

enum class JapaneseCandidateSource {
    LEXICON,
    PREFIX_PREDICTION,
    HIRAGANA_FALLBACK,
    KATAKANA_FALLBACK,
    UNRESOLVED_ROMAJI_FALLBACK
}

data class JapaneseCandidate(
    val text: String,
    val reading: String,
    val source: JapaneseCandidateSource,
    val score: Int = 0
)

/**
 * Pure Kotlin state holder for Japanese manual input.
 *
 * The original romaji buffer is retained, making every backspace lossless.
 * Exact JMdict lookup only runs after the buffer has a complete kana reading.
 * Phrase segmentation, conjugation, contextual prediction, and learning are
 * intentionally outside this Phase 1 contract.
 */
class JapaneseComposer(
    private val lexicon: JapaneseLexicon = JapaneseLexicon { emptyList() },
    initialScriptMode: JapaneseScriptMode = JapaneseScriptMode.HIRAGANA
) {
    companion object {
        const val DEFAULT_CANDIDATE_LIMIT = 9
        private const val MAX_PREFIX_QUERY_RESULTS = 24
    }

    private val input = StringBuilder()
    private val kanaInput = StringBuilder()
    private var lastKanaTapGroup: String? = null
    private var lastKanaTapAtMs: Long = Long.MIN_VALUE
    private var lastKanaTapIndex: Int = 0

    var inputStyle: JapaneseInputStyle = JapaneseInputStyle.ROMAJI
        private set

    var scriptMode: JapaneseScriptMode = initialScriptMode
        private set

    val rawRomaji: String
        get() = input.toString()

    val hasComposition: Boolean
        get() = input.isNotEmpty() || kanaInput.isNotEmpty()

    val composition: String
        get() {
            if (inputStyle == JapaneseInputStyle.KANA_12_KEY) {
                val reading = kanaInput.toString()
                return when (scriptMode) {
                    JapaneseScriptMode.HIRAGANA -> reading
                    JapaneseScriptMode.KATAKANA -> JapaneseScripts.hiraganaToKatakana(reading)
                }
            }
            val converted = RomajiToHiragana.convert(input.toString())
            val convertedKana = when (scriptMode) {
                JapaneseScriptMode.HIRAGANA -> converted.hiragana
                JapaneseScriptMode.KATAKANA ->
                    JapaneseScripts.hiraganaToKatakana(converted.hiragana)
            }
            return convertedKana + converted.pendingRomaji
        }

    /**
     * Complete, normalized hiragana reading used for exact lookup.
     *
     * A single terminal `n` is finalized to `ん`; other unresolved romaji
     * sequences return null and are never sent to the lexicon.
     */
    val hiraganaReading: String?
        get() {
            if (!hasComposition) return null
            if (inputStyle == JapaneseInputStyle.KANA_12_KEY) return kanaInput.toString()
            val finalized = RomajiToHiragana.convert(
                input.toString(),
                finalizeTerminalN = true
            )
            return finalized.hiragana.takeIf { finalized.isComplete }
        }

    val hasPendingRomaji: Boolean
        get() = inputStyle == JapaneseInputStyle.ROMAJI &&
            hiraganaReading == null && hasComposition

    /** A layout change never discards an active reading; commit it first. */
    fun setInputStyle(style: JapaneseInputStyle): Boolean {
        if (style == inputStyle) return true
        if (hasComposition) return false
        inputStyle = style
        return true
    }

    /** Inserts a kana selected by long-press without entering multi-tap cycling. */
    fun appendKana(kana: String): Boolean {
        if (inputStyle != JapaneseInputStyle.KANA_12_KEY ||
            kana.length != 1 || !Kana12Key.isKana(kana[0])) return false
        finalizeKanaTap()
        kanaInput.append(kana)
        return true
    }

    /** Consecutive taps of one key cycle its kana; a pause or another key appends. */
    fun tapKana(group: String, nowMs: Long): Boolean {
        if (inputStyle != JapaneseInputStyle.KANA_12_KEY) return false
        val kana = Kana12Key.groups[group] ?: return false
        val cycling = lastKanaTapGroup == group && kanaInput.isNotEmpty() &&
            nowMs >= lastKanaTapAtMs &&
            nowMs - lastKanaTapAtMs <= Kana12Key.MULTITAP_WINDOW_MS
        if (cycling) {
            lastKanaTapIndex = (lastKanaTapIndex + 1) % kana.size
            kanaInput.replace(kanaInput.lastIndex, kanaInput.length, kana[lastKanaTapIndex])
        } else {
            lastKanaTapIndex = 0
            kanaInput.append(kana.first())
        }
        lastKanaTapGroup = group
        lastKanaTapAtMs = nowMs
        return true
    }

    /** Separates two identical first-column kana without waiting for the timeout. */
    fun finalizeKanaTap() {
        lastKanaTapGroup = null
        lastKanaTapAtMs = Long.MIN_VALUE
        lastKanaTapIndex = 0
    }

    /** Cycles the last kana through its small, voiced or semi-voiced forms. */
    fun transformLastKana(): Boolean {
        if (inputStyle != JapaneseInputStyle.KANA_12_KEY || kanaInput.isEmpty()) return false
        val replacement = Kana12Key.nextModified(kanaInput.last().toString()) ?: return false
        kanaInput.replace(kanaInput.lastIndex, kanaInput.length, replacement)
        finalizeKanaTap()
        return true
    }

    fun appendRomaji(character: Char): Boolean {
        if (inputStyle != JapaneseInputStyle.ROMAJI) return false
        if (!RomajiToHiragana.isSupportedInput(character.toString())) return false
        input.append(character.lowercaseChar())
        return true
    }

    fun appendRomaji(value: String): Boolean {
        if (inputStyle != JapaneseInputStyle.ROMAJI) return false
        if (!RomajiToHiragana.isSupportedInput(value)) return false
        input.append(value.lowercase())
        return true
    }

    /** Replaces the input transactionally. */
    fun setRomaji(value: String): Boolean {
        if (inputStyle != JapaneseInputStyle.ROMAJI) return false
        if (!RomajiToHiragana.isSupportedInput(value)) return false
        input.clear()
        input.append(value.lowercase())
        return true
    }

    /** Removes one original keystroke and recomputes the visible composition. */
    fun backspace(): Boolean {
        if (inputStyle == JapaneseInputStyle.KANA_12_KEY) {
            if (kanaInput.isEmpty()) return false
            kanaInput.deleteCharAt(kanaInput.lastIndex)
            finalizeKanaTap()
            return true
        }
        if (input.isEmpty()) return false
        input.deleteCharAt(input.lastIndex)
        return true
    }

    fun clear() {
        input.clear()
        kanaInput.clear()
        finalizeKanaTap()
    }

    fun setScriptMode(mode: JapaneseScriptMode) {
        if (mode != scriptMode) finalizeKanaTap()
        scriptMode = mode
    }

    fun toggleScriptMode(): JapaneseScriptMode {
        finalizeKanaTap()
        scriptMode = when (scriptMode) {
            JapaneseScriptMode.HIRAGANA -> JapaneseScriptMode.KATAKANA
            JapaneseScriptMode.KATAKANA -> JapaneseScriptMode.HIRAGANA
        }
        return scriptMode
    }

    fun getCandidates(
        limit: Int = DEFAULT_CANDIDATE_LIMIT
    ): List<JapaneseCandidate> {
        require(limit >= 0) { "Candidate limit cannot be negative." }
        if (limit == 0 || !hasComposition) return emptyList()

        val reading = hiraganaReading
        if (reading == null) {
            return listOf(
                JapaneseCandidate(
                    text = composition,
                    reading = composition,
                    source = JapaneseCandidateSource.UNRESOLVED_ROMAJI_FALLBACK
                )
            )
        }

        val candidates = lexicon.lookup(reading)
            .asSequence()
            .filter { it.text.isNotBlank() }
            .sortedByDescending { it.score }
            .distinctBy { it.text }
            .map {
                JapaneseCandidate(
                    text = it.text,
                    reading = reading,
                    source = JapaneseCandidateSource.LEXICON,
                    score = it.score
                )
            }
            .toMutableList()

        if (candidates.size < limit) {
            val predicted = lexicon.lookupPrefix(
                reading,
                minOf(limit, MAX_PREFIX_QUERY_RESULTS)
            )
                .asSequence()
                .filter { it.text.isNotBlank() }
                .sortedByDescending { it.score }
                .distinctBy { it.text }
                .map {
                    JapaneseCandidate(
                        text = it.text,
                        reading = reading,
                        source = JapaneseCandidateSource.PREFIX_PREDICTION,
                        score = it.score
                    )
                }
                .toList()
            candidates += predicted
        }

        val katakana = JapaneseScripts.hiraganaToKatakana(reading)
        val fallbacks = when (scriptMode) {
            JapaneseScriptMode.HIRAGANA -> listOf(
                JapaneseCandidate(
                    text = reading,
                    reading = reading,
                    source = JapaneseCandidateSource.HIRAGANA_FALLBACK
                ),
                JapaneseCandidate(
                    text = katakana,
                    reading = reading,
                    source = JapaneseCandidateSource.KATAKANA_FALLBACK
                )
            )
            JapaneseScriptMode.KATAKANA -> listOf(
                JapaneseCandidate(
                    text = katakana,
                    reading = reading,
                    source = JapaneseCandidateSource.KATAKANA_FALLBACK
                ),
                JapaneseCandidate(
                    text = reading,
                    reading = reading,
                    source = JapaneseCandidateSource.HIRAGANA_FALLBACK
                )
            )
        }
        // Kana must stay selectable even when dictionary results fill the strip.
        // Keep the existing conversion order within the remaining dictionary slots.
        val visibleFallbacks = fallbacks.distinctBy { it.text }.take(limit)
        val fallbackTexts = visibleFallbacks.map { it.text }.toSet()
        val conversions = candidates
            .distinctBy { it.text }
            .filterNot { it.text in fallbackTexts }
            .take(limit - visibleFallbacks.size)
        val visibleTexts = (conversions + visibleFallbacks).map { it.text }.toSet()
        // A dictionary result may itself be kana. Retain its original rank.
        return (candidates + visibleFallbacks)
            .distinctBy { it.text }
            .filter { it.text in visibleTexts }
    }

    fun selectCandidate(
        index: Int,
        limit: Int = DEFAULT_CANDIDATE_LIMIT
    ): JapaneseCandidate? {
        val selected = getCandidates(limit).getOrNull(index) ?: return null
        clear()
        return selected
    }

    fun peekBestOrRaw(): JapaneseCandidate? = getCandidates().firstOrNull()

    fun commitBestOrRaw(): JapaneseCandidate? {
        val candidate = peekBestOrRaw() ?: return null
        clear()
        return candidate
    }

    /**
     * Reads the preferred kana fallback without applying a kanji candidate.
     * The host can commit first and only clear after InputConnection succeeds.
     * Unresolved non-`n` romaji is preserved verbatim.
     */
    fun peekRaw(): JapaneseCandidate? {
        if (!hasComposition) return null
        val reading = hiraganaReading
        return if (reading == null) {
            JapaneseCandidate(
                text = composition,
                reading = composition,
                source = JapaneseCandidateSource.UNRESOLVED_ROMAJI_FALLBACK
            )
        } else {
            when (scriptMode) {
                JapaneseScriptMode.HIRAGANA -> JapaneseCandidate(
                    text = reading,
                    reading = reading,
                    source = JapaneseCandidateSource.HIRAGANA_FALLBACK
                )
                JapaneseScriptMode.KATAKANA -> JapaneseCandidate(
                    text = JapaneseScripts.hiraganaToKatakana(reading),
                    reading = reading,
                    source = JapaneseCandidateSource.KATAKANA_FALLBACK
                )
            }
        }
    }

    /** Commits exactly the preferred kana reading, never a dictionary prediction. */
    fun commitRaw(): JapaneseCandidate? {
        val candidate = peekRaw() ?: return null
        clear()
        return candidate
    }
}
