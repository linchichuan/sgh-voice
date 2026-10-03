package com.shingihou.sghvoice.api

import com.shingihou.sghvoice.processing.FactPreservation

/**
 * Comparison-only token alignment for the dictation guard. It never rewrites output.
 *
 * It removes from BOTH comparison strings only changes that are provably spelling repairs,
 * so every remaining fact check (identifiers, retention, negation) runs unchanged on the rest:
 *  - case-only changes of ordinary words (sgh voice -> SGH Voice, iphone -> iPhone);
 *    mixed-case identifiers such as MyRepo keep their exact case;
 *  - a misheard span replaced by a known term (コトリン -> Kotlin, Kotlun -> Kotlin). A span with
 *    Han/other non-kana script is accepted ONLY when it is a known mishearing alias whose
 *    right-hand side is exactly the inserted term (吉他哈布 -> GitHub from a correction rule);
 *    an unknown Han span (資料庫 -> GitHub) is a meaning change and stays in the comparison.
 *    The replaced span must exist (pure insertions are new facts), must not contain a number,
 *    a negation or a protected identifier, is bounded in length, and the inserted words must
 *    form known vocabulary terms without digits;
 *  - an explicitly abandoned clause before a spoken repair cue (「跟小王，不對，跟小李」),
 *    only when that clause contains no number and no negation.
 */
internal class DictationAlignment(
    private val asciiSpan: Regex,
    private val isProtected: (String) -> Boolean,
    knownTerms: Collection<String>,
    extraKnownWords: Set<String>,
    aliases: Map<String, String> = emptyMap()
) {
    // wrong span (letters/digits only) -> normalized right-hand term
    private val aliasTargets: Map<String, Set<String>> = aliases.entries
        .groupBy({ it.key.filter(Char::isLetterOrDigit) }, { normalizeTerm(it.value) })
        .filterKeys { it.isNotEmpty() }
        .mapValues { it.value.toSet() }

    private data class Token(val text: String, val start: Int, val end: Int) {
        val ascii: Boolean get() = text[0].code < 128
        val word: Boolean get() = text.all { it in 'A'..'Z' || it in 'a'..'z' }
    }

    private val knownNormalized: Set<String> = knownTerms.map(::normalizeTerm).filter { it.isNotEmpty() }.toSet()
    private val knownWords: Set<String> = knownTerms
        .flatMap { term -> term.split(Regex("[^A-Za-z]+")) }
        .filter { it.isNotEmpty() }
        .map { it.lowercase() }
        .toSet() + extraKnownWords

    /** @return reduced (source, candidate), or null when alignment is too large to compute. */
    fun reduce(source: String, candidate: String): Pair<String, String>? {
        val src = tokenize(source)
        val cand = tokenize(candidate)
        val n = src.size
        val m = cand.size
        if (n.toLong() * m.toLong() > MAX_CELLS) return null

        val width = m + 1
        val dp = IntArray((n + 1) * width)
        for (i in 1..n) for (j in 1..m) {
            dp[i * width + j] = if (same(src[i - 1], cand[j - 1])) dp[(i - 1) * width + j - 1] + 1
            else maxOf(dp[(i - 1) * width + j], dp[i * width + j - 1])
        }
        // Backtrack from the end: equal tokens always match, which aligns the FINAL
        // version of a spoken repair and leaves the abandoned version as a deletion.
        val ops = ArrayList<IntArray>() // [type(0 match,1 del,2 ins), srcIndex, candIndex]
        var i = n
        var j = m
        while (i > 0 || j > 0) {
            if (i > 0 && j > 0 && same(src[i - 1], cand[j - 1])) {
                ops.add(intArrayOf(0, i - 1, j - 1)); i--; j--
            } else if (j == 0 || i > 0 && dp[(i - 1) * width + j] >= dp[i * width + j - 1]) {
                ops.add(intArrayOf(1, i - 1, -1)); i--
            } else {
                ops.add(intArrayOf(2, -1, j - 1)); j--
            }
        }
        ops.reverse()

        val freeRanges = abandonedRepairRanges(source)
        val dropSource = BooleanArray(n)
        val dropCandidate = BooleanArray(m)
        val replaceCandidate = arrayOfNulls<String>(m)
        var k = 0
        while (k < ops.size) {
            if (ops[k][0] == 0) {
                val s = src[ops[k][1]]
                val c = cand[ops[k][2]]
                if (s.text != c.text) replaceCandidate[ops[k][2]] = s.text
                k++
                continue
            }
            val deleted = mutableListOf<Int>()
            val inserted = mutableListOf<Int>()
            while (k < ops.size && ops[k][0] != 0) {
                if (ops[k][0] == 1) deleted += ops[k][1] else inserted += ops[k][2]
                k++
            }
            if (isApprovedSubstitution(source, deleted.map { src[it] }, inserted.map { cand[it] })) {
                deleted.forEach { dropSource[it] = true }
                inserted.forEach { dropCandidate[it] = true }
            } else {
                deleted.filter { idx -> freeRanges.any { src[idx].start >= it.first && src[idx].end - 1 <= it.last } }
                    .forEach { dropSource[it] = true }
            }
        }
        return rebuild(source, src, dropSource, emptyMap()) to
            rebuild(candidate, cand, dropCandidate,
                replaceCandidate.withIndex().filter { it.value != null }.associate { it.index to it.value!! })
    }

    private fun tokenize(text: String): List<Token> {
        val spans = asciiSpan.findAll(text).associateBy { it.range.first }
        val tokens = mutableListOf<Token>()
        var index = 0
        while (index < text.length) {
            val span = spans[index]
            if (span != null) {
                tokens += Token(span.value, index, span.range.last + 1)
                index = span.range.last + 1
                continue
            }
            val codePoint = text.codePointAt(index)
            val size = Character.charCount(codePoint)
            if (Character.isLetterOrDigit(codePoint)) tokens += Token(text.substring(index, index + size), index, index + size)
            index += size
        }
        return tokens
    }

    private fun same(source: Token, candidate: Token): Boolean {
        if (source.text == candidate.text) return true
        if (!source.word || !candidate.word || !source.text.equals(candidate.text, ignoreCase = true)) return false
        val text = source.text
        val ordinaryCase = text == text.lowercase() ||
            (text[0].isUpperCase() && text.drop(1) == text.drop(1).lowercase())
        return ordinaryCase || text.lowercase() in knownWords
    }

    private fun isApprovedSubstitution(source: String, deleted: List<Token>, inserted: List<Token>): Boolean {
        if (deleted.isEmpty() || inserted.isEmpty()) return false
        if (!wholeScriptSpan(source, deleted.first().start, deleted.last().end)) return false
        if (inserted.any { !it.ascii || it.text.any(Char::isDigit) }) return false
        val deletedText = deleted.joinToString("") { it.text }
        val insertedTerm = inserted.joinToString("") { normalizeTerm(it.text) }
        val knownAlias = aliasTargets[deletedText]?.contains(insertedTerm) == true
        if (!knownAlias && !coveredByKnownTerms(inserted.map { normalizeTerm(it.text) })) return false
        if (deletedText.codePointCount(0, deletedText.length) > MAX_REPLACED_CODE_POINTS) return false
        if (FactPreservation.containsNumeral(deletedText) || FactPreservation.countNegations(deletedText) > 0) return false
        if (deleted.any { it.ascii && isProtected(it.text) }) return false
        val asciiDeleted = deleted.filter { it.ascii }
        if (asciiDeleted.isEmpty()) {
            // A matching consonant skeleton is not proof (コトラン != コトリン).
            // Keep only explicit aliases or exact curated loanword spellings.
            if (deleted.all { isKana(it.text) }) {
                return knownAlias || CURATED_LOANWORDS[deletedText] == insertedTerm
            }
            // Han can be a real word (資料庫); only a known mishearing alias may be replaced.
            return knownAlias
        }
        if (asciiDeleted.size != deleted.size) return false
        // Closeness to a product word cannot distinguish an unfamiliar name from a typo.
        return knownAlias
    }

    private fun isKana(text: String): Boolean = text.all {
        it in '\u3041'..'\u309F' || it in '\u30A1'..'\u30FA' || it in '\u30FC'..'\u30FF' || it in '\uFF66'..'\uFF9F'
    }

    private fun coveredByKnownTerms(parts: List<String>): Boolean {
        val reachable = BooleanArray(parts.size + 1).also { it[0] = true }
        for (end in 1..parts.size) for (start in 0 until end) {
            if (reachable[start] && parts.subList(start, end).joinToString("") in knownNormalized) {
                reachable[end] = true
                break
            }
        }
        return reachable[parts.size]
    }

    private fun abandonedRepairRanges(text: String): List<IntRange> = REPAIR_CUE.findAll(text).mapNotNull { cue ->
        val clauseStart = text.substring(0, cue.range.first).indexOfLast { it in CLAUSE_BOUNDARY } + 1
        val abandoned = text.substring(clauseStart, cue.range.first)
        val following = text.substring(cue.range.last + 1).trimStart()
        val valid = abandoned.isNotBlank() && following.isNotEmpty() && following[0] !in CLAUSE_BOUNDARY &&
            abandoned.codePointCount(0, abandoned.length) <= MAX_ABANDONED_CODE_POINTS &&
            !FactPreservation.containsNumeral(abandoned) && FactPreservation.countNegations(abandoned) == 0
        if (valid) clauseStart..cue.range.last else null
    }.toList()

    private fun rebuild(text: String, tokens: List<Token>, drop: BooleanArray, replace: Map<Int, String>): String {
        if (drop.none { it } && replace.isEmpty()) return text
        val builder = StringBuilder()
        var cursor = 0
        tokens.forEachIndexed { index, token ->
            builder.append(text, cursor, token.start)
            when {
                drop[index] -> if (token.ascii) builder.append(' ')
                replace[index] != null -> builder.append(replace[index])
                else -> builder.append(token.text)
            }
            cursor = token.end
        }
        builder.append(text, cursor, text.length)
        return builder.toString()
    }


    companion object {
        /**
         * CJK has no inferred word boundary here. Only a whole CJK run (or a span
         * explicitly delimited by whitespace/punctuation) is admissible. A rule learned
         * in another sentence cannot authorize 可樂→Claude inside 可樂餅. Filter BOTH
         * alignment and the guard's explicit-alias fallback using this same policy.
         */
        fun aliasesForContext(source: String, aliases: Map<String, String>): Map<String, String> =
            aliases.filter { (wrong, _) ->
                if (wrong.isEmpty()) false else {
                    var start = source.indexOf(wrong)
                    var safe = start >= 0
                    while (start >= 0 && safe) {
                        safe = wholeScriptSpan(source, start, start + wrong.length)
                        start = source.indexOf(wrong, start + 1)
                    }
                    safe
                }
            }

        private fun scriptGroup(point: Int): Int = when (Character.UnicodeScript.of(point)) {
            Character.UnicodeScript.HAN,
            Character.UnicodeScript.HIRAGANA,
            Character.UnicodeScript.KATAKANA -> 1
            else -> if (point == 0x30FC || point == 0xFF70) 1 else 0
        }

        private fun wholeScriptSpan(source: String, start: Int, end: Int): Boolean {
            val first = scriptGroup(source.codePointAt(start))
            val last = scriptGroup(source.codePointBefore(end))
            return !(first != 0 && start > 0 && scriptGroup(source.codePointBefore(start)) == first) &&
                !(last != 0 && end < source.length && scriptGroup(source.codePointAt(end)) == last)
        }

        private val CURATED_LOANWORDS = mapOf(
            "コトリン" to "kotlin", "ギットハブ" to "github", "アクションズ" to "actions"
        )
        private const val MAX_CELLS = 1_000_000L
        private const val MAX_REPLACED_CODE_POINTS = 24
        private const val MAX_ABANDONED_CODE_POINTS = 24
        private const val CLAUSE_BOUNDARY = "，,。！？!?；;\n、"
        private val REPAIR_CUE = Regex(
            "[，,]\\s*(?:不對|不对|不是|不|更正|說錯了|说错了|講錯了|讲错了|我是說|我是说)\\s*[，,]"
        )

        fun normalizeTerm(term: String): String =
            term.lowercase().filter { it.isLetterOrDigit() || it in "/._+#-" }
    }
}
