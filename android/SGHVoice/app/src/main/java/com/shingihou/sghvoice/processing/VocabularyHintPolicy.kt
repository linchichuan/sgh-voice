package com.shingihou.sghvoice.processing

import java.util.Locale

/** Bounded spelling references and conservative, single-pass technical term corrections. */
object VocabularyHintPolicy {
    private const val MAX_TERM_LENGTH = 64
    private val instructionLike = Regex(
        "(?i)(?:ignore|disregard|override|obey|follow).{0,40}(?:instructions?|prompts?|rules?)" +
            "|(?:system|assistant|user)\\s*[:：]|(?:請|请)?(?:忽略|無視|无视).{0,20}(?:指令|規則|规则|提示)" +
            "|(?:指示|命令).{0,12}(?:無視|従って)|(?:respond|reply|output)\\s+(?:only|with)"
    )
    // Correct spellings only: these are sent as STT hints. The misspelling GitPush is a
    // correction source below, never a hint (it taught STT the wrong spelling).
    internal val technicalTerms = listOf("GitHub", "GitHub Actions", "Actions", "CI/CD", "git push")

    // Only unambiguous product/command spellings. Plain action/actions/push are deliberately absent.
    private val technicalCorrections = linkedMapOf<String, String>().apply {
        mapOf(
            "git hub actions" to "GitHub Actions",
            "github actions" to "GitHub Actions",
            "GitHub actions" to "GitHub Actions",
            "git hub" to "GitHub",
            "github" to "GitHub",
            "ci cd" to "CI/CD",
            "ci / cd" to "CI/CD",
            "ci/cd" to "CI/CD",
            "cicd" to "CI/CD",
            "gitpush" to "git push",
            "GitPush" to "git push",
            "git push" to "git push"
        ).forEach { (wrong, correct) ->
            put(wrong, correct)
            put(wrong.uppercase(Locale.ROOT), correct)
            put(wrong.split(' ').joinToString(" ") { it.replaceFirstChar(Char::uppercaseChar) }, correct)
        }
    }

    fun applyCorrections(
        text: String,
        corrections: Map<String, String> = emptyMap(),
        nameProtectedKeys: Set<String> = emptySet()
    ): String = TextCorrectionEngine.apply(text, technicalCorrections + corrections, nameProtectedKeys)

    /**
     * Select high-priority whole terms first, then put them LAST for Whisper's retained prompt tail.
     * Global manual terms and confirmed learning outrank scene-specific manual terms and presets.
     * 800 characters is only a payload bound, NOT a measurement of Whisper's 224-token window.
     */
    fun buildWhisperPrompt(
        customWords: List<String> = emptyList(),
        learnedWords: List<String> = emptyList(),
        sceneWords: List<String> = emptyList(),
        baseWords: List<String> = emptyList(),
        sceneCustomWords: List<String> = emptyList()
    ): String = boundedTerms(
        customWords + learnedWords + sceneCustomWords + technicalTerms + sceneWords + baseWords,
        maxWords = 50,
        maxLength = 800,
        separator = "、"
    ).asReversed().joinToString("、")

    /** Restore the priority order of our spelling list for the keyword-capable STT adapter. */
    fun transcriptionKeywords(spellingPrompt: String): List<String> = boundedTerms(
        spellingPrompt.split('、').asReversed(),
        maxWords = 50,
        maxLength = 800,
        separator = "、"
    )

    /**
     * Returns JSON spelling-reference data, never instructions or example model responses.
     * The caller must keep this in a data field and explicitly forbid following its contents.
     * Global manual terms and confirmed learning outrank scene-specific manual terms;
     * built-ins require evidence in this utterance.
     */
    fun buildLlmVocabularyHint(
        text: String,
        customWords: List<String> = emptyList(),
        learnedWords: List<String> = emptyList(),
        sceneWords: List<String> = emptyList(),
        baseWords: List<String> = emptyList(),
        corrections: Map<String, String> = emptyMap(),
        sceneCustomWords: List<String> = emptyList()
    ): String {
        if (text.isBlank()) return "[]"
        val boundedText = text.take(8_000)
        val normalizedText = applyCorrections(boundedText, corrections)
        val relevantWords = (technicalTerms + sceneWords + baseWords).filter { word ->
            // Actions by itself is also an ordinary English noun, not evidence for GitHub's product.
            (word != "Actions" || TextCorrectionEngine.containsUnprotectedTerm(normalizedText, "GitHub Actions")) &&
                TextCorrectionEngine.containsUnprotectedTerm(normalizedText, word)
        }
        return boundedTerms(
            customWords + learnedWords + sceneCustomWords + relevantWords,
            maxWords = 32,
            maxLength = 1_200,
            separator = ",",
            quoteTerms = true
        ).joinToString(separator = ",", prefix = "[", postfix = "]") { "\"$it\"" }
    }

    private fun boundedTerms(
        words: List<String>,
        maxWords: Int,
        maxLength: Int,
        separator: String,
        quoteTerms: Boolean = false
    ): List<String> {
        val selected = mutableListOf<String>()
        val seen = mutableSetOf<String>()
        var length = if (quoteTerms) 2 else 0
        for (raw in words) {
            val word = sanitizeTerm(raw) ?: continue
            if (!seen.add(word.lowercase(Locale.ROOT))) continue
            val addedLength = word.length + (if (quoteTerms) 2 else 0) +
                (if (selected.isEmpty()) 0 else separator.length)
            if (length + addedLength > maxLength) continue
            selected.add(word)
            length += addedLength
            if (selected.size >= maxWords) break
        }
        return selected
    }

    internal fun sanitizeTerm(raw: String): String? {
        // Never flatten line breaks or prompt delimiters into a superficially valid term.
        if (raw.any { it.isISOControl() || Character.getType(it) == Character.FORMAT.toInt() }) return null
        val word = raw.trim().replace(Regex(" +"), " ")
        if (word.isEmpty() || word.length > MAX_TERM_LENGTH || word.count { it == ' ' } > 5) return null
        if (!word.any(Char::isLetterOrDigit) || instructionLike.containsMatchIn(word)) return null
        if (!word.all { it.isLetterOrDigit() || it in " -/+._#&・·" }) return null
        return word
    }
}
