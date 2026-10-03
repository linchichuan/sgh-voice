package com.shingihou.sghvoice.api

/** Narrow comparison rules for spoken hesitation; never rewrites the user's output. */
internal object DictationDisfluency {
    private const val BOUNDARY = "(^|[，,。.；;！!？?、…⋯\\n][\\t ]*)"
    private const val DELIMITER = "(?:[\\t ]*[，,、][\\t ]*|[\\t ]+(?=\\S))"
    private val hesitation = Regex(
        BOUNDARY + "(?:嗯+|呃+|啊+|えーと|えっと|あのー|そのー|[Uu]m|[Uu]h)" + DELIMITER
    )
    // STT often joins an initial 嗯 directly to the next Han word. Keep the standalone
    // acknowledgment and 嗯哼 / other vocal responses; never extend this to lexical 呃逆.
    private val attachedEn = Regex(BOUNDARY + "嗯+(?![嗯哼啊呀哦])(?=\\p{script=Han})")
    // Adjacent pronoun restarts only: never arbitrary repeated Han, names, quantities,
    // negations, emphasis (好好 / 不要不要), or repetitions across separate clauses.
    private val chineseRestart = Regex(BOUNDARY + "(我|你|他|她)(?:[\\t ]*[，,]?[\\t ]*\\2)+(?=[\\p{L}])")
    private val englishRestart = Regex(
        BOUNDARY + "(I|we|you|he|she|it|they)" +
            "(?:(?:[\\t ]+|[\\t ]*,[\\t ]*)\\2)+(?=[\\t ]+[A-Za-z])",
        RegexOption.IGNORE_CASE
    )
    // Keeping one connective preserves chronology; a single 然後 is never a free deletion.
    private val repeatedThen = Regex(BOUNDARY + "然後(?:[\\t ]*[，,]?[\\t ]*然後)+")
    private val literal = Regex(
        "`[^`]*`|\"[^\"\\n]*\"|「[^」]*」|『[^』]*』|" +
            "https?://[^\\s，。！？]+|(?:/|[A-Za-z]:\\\\)[^\\s，。！？]+"
    )
    private val ellipsis = Regex("[.]{3,}|…+|⋯+")
    private val identifier = Regex("https?://[^\\s，。！？]+|(?:/|[A-Za-z]:\\\\)[^\\s，。！？]+")
    private val contentToken = Regex("[A-Za-z0-9]+|[\\p{L}\\p{N}]")

    fun comparisonText(text: String): String {
        var result = text
        // Each pass can expose the next clause-initial filler (嗯，啊，呃，...).
        // Bound the work for untrusted transcript/model input.
        for (pass in 0 until 8) {
            val next = replaceOutsideLiterals(result, hesitation) { it.groupValues[1] }
            if (next == result) break
            result = next
        }
        result = replaceOutsideLiterals(result, attachedEn) { it.groupValues[1] }
        result = replaceOutsideLiterals(result, chineseRestart) { it.groupValues[1] + it.groupValues[2] }
        result = replaceOutsideLiterals(result, englishRestart) { match ->
            // We, we is a restart, but IT, IT may enumerate a department and its support.
            val acronym = Regex("[A-Za-z]{2,}").findAll(match.value).any { it.value.all(Char::isUpperCase) }
            if (acronym) match.value else match.groupValues[1] + match.groupValues[2]
        }
        return replaceOutsideLiterals(result, repeatedThen) { it.groupValues[1] + "然後" }
    }

    /** Called on aligned comparison text: preserve pause count AND its place in the content. */
    fun preservesEllipses(source: String, candidate: String): Boolean =
        ellipsisAnchors(source) == ellipsisAnchors(candidate)

    private fun ellipsisAnchors(text: String): List<List<String>> {
        // URLs and paths are identifiers rather than prose punctuation. Quoted ellipses
        // still count: a literal instruction to retain them must not be silently erased.
        val protected = identifier.findAll(text).map { it.range }.toList()
        return ellipsis.findAll(text)
            .filter { pause -> protected.none { it.first <= pause.range.last && it.last >= pause.range.first } }
            .map { pause -> contentToken.findAll(text.substring(0, pause.range.first))
                .map { it.value.lowercase() }.toList() }
            .toList()
    }

    private fun replaceOutsideLiterals(text: String, pattern: Regex, replace: (MatchResult) -> String): String {
        val protected = literal.findAll(text).map { it.range }.toList()
        return pattern.replace(text) { match ->
            if (protected.any { it.first <= match.range.last && it.last >= match.range.first })
                match.value else replace(match)
        }
    }
}
