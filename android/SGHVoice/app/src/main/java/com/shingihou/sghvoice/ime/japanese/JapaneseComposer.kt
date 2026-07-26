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
 * Pure Kotlin state holder for Phase 1 Japanese manual input.
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

    var scriptMode: JapaneseScriptMode = initialScriptMode
        private set

    val rawRomaji: String
        get() = input.toString()

    val hasComposition: Boolean
        get() = input.isNotEmpty()

    val composition: String
        get() {
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
            val finalized = RomajiToHiragana.convert(
                input.toString(),
                finalizeTerminalN = true
            )
            return finalized.hiragana.takeIf { finalized.isComplete }
        }

    val hasPendingRomaji: Boolean
        get() = hiraganaReading == null && hasComposition

    fun appendRomaji(character: Char): Boolean {
        if (!RomajiToHiragana.isSupportedInput(character.toString())) return false
        input.append(character.lowercaseChar())
        return true
    }

    fun appendRomaji(value: String): Boolean {
        if (!RomajiToHiragana.isSupportedInput(value)) return false
        input.append(value.lowercase())
        return true
    }

    /** Replaces the input transactionally. */
    fun setRomaji(value: String): Boolean {
        if (!RomajiToHiragana.isSupportedInput(value)) return false
        input.clear()
        input.append(value.lowercase())
        return true
    }

    /** Removes one original keystroke and recomputes the visible composition. */
    fun backspace(): Boolean {
        if (input.isEmpty()) return false
        input.deleteCharAt(input.lastIndex)
        return true
    }

    fun clear() {
        input.clear()
    }

    fun setScriptMode(mode: JapaneseScriptMode) {
        scriptMode = mode
    }

    fun toggleScriptMode(): JapaneseScriptMode {
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
        candidates += fallbacks

        return candidates
            .distinctBy { it.text }
            .take(limit)
    }

    fun selectCandidate(
        index: Int,
        limit: Int = DEFAULT_CANDIDATE_LIMIT
    ): JapaneseCandidate? {
        val selected = getCandidates(limit).getOrNull(index) ?: return null
        clear()
        return selected
    }

    fun peekBestOrRaw(): JapaneseCandidate? = getCandidates(limit = 1).firstOrNull()

    fun commitBestOrRaw(): JapaneseCandidate? {
        val candidate = peekBestOrRaw() ?: return null
        clear()
        return candidate
    }

    /**
     * Commits the preferred kana fallback without applying a kanji candidate.
     * Unresolved non-`n` romaji is preserved verbatim.
     */
    fun commitRaw(): JapaneseCandidate? {
        if (!hasComposition) return null
        val reading = hiraganaReading
        val candidate = if (reading == null) {
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
        clear()
        return candidate
    }
}
