package com.shingihou.sghvoice.learning

/** One changed region; [start]/[end] are code-point offsets in the original text. */
internal data class EditHunk(
    val start: Int,
    val end: Int,
    val wrong: String,
    val corrected: String
)

/**
 * Token-level diff used only by correction learning. Latin words and digit runs are atomic
 * tokens, every other code point (Han, kana, punctuation) is its own token, and a whitespace
 * run is one token. Bounded: returns null instead of computing a large alignment.
 */
internal object EditHunks {
    private const val MAX_ALIGNED_TOKENS = 600

    private class Token(val text: String, val start: Int, val end: Int, val latin: Boolean)

    /** All changed regions between [original] and [edited], or null when too large to align. */
    fun hunks(original: String, edited: String): List<EditHunk>? {
        val a = tokenize(original)
        val b = tokenize(edited)
        val matches = align(a, b) { x, y -> x.text == y.text } ?: return null
        val raw = mutableListOf<IntArray>() // [aFrom, aTo, bFrom, bTo] token indices
        var ai = 0
        var bi = 0
        for ((ma, mb) in matches + (a.size to b.size)) {
            if (ma > ai || mb > bi) raw += intArrayOf(ai, ma, bi, mb)
            ai = ma + 1
            bi = mb + 1
        }
        // "git hub actions" -> "GitHub Actions": two hunks joined by one kept space are one fix.
        val merged = mutableListOf<IntArray>()
        for (hunk in raw) {
            val last = merged.lastOrNull()
            if (last != null && hunk[0] == last[1] + 1 && hunk[2] == last[3] + 1 &&
                a[last[1]].text.isBlank() && last[0] < last[1] && last[2] < last[3] &&
                hunk[0] < hunk[1] && hunk[2] < hunk[3]
            ) {
                last[1] = hunk[1]
                last[3] = hunk[3]
            } else {
                merged += hunk
            }
        }
        val originalPoints = original.codePointCount(0, original.length)
        val editedPoints = edited.codePointCount(0, edited.length)
        return merged.map { (aFrom, aTo, bFrom, bTo) ->
            val start = if (aFrom < a.size) a[aFrom].start else originalPoints
            val end = if (aTo > aFrom) a[aTo - 1].end else start
            val editStart = if (bFrom < b.size) b[bFrom].start else editedPoints
            val editEnd = if (bTo > bFrom) b[bTo - 1].end else editStart
            EditHunk(start, end, original.substringByCodePoints(start, end), edited.substringByCodePoints(editStart, editEnd))
        }
    }

    /**
     * Marks each code point of [committed] that appears unchanged (Latin case-insensitive) in
     * [stt], i.e. came from speech recognition rather than from AI cleanup. Null when too large.
     */
    fun verbatimMask(committed: String, stt: String): BooleanArray? {
        val a = tokenize(committed)
        val b = tokenize(stt)
        val matches = align(a, b) { x, y ->
            x.text == y.text || (x.latin && y.latin && x.text.equals(y.text, ignoreCase = true))
        } ?: return null
        val mask = BooleanArray(committed.codePointCount(0, committed.length))
        matches.forEach { (index, _) -> for (point in a[index].start until a[index].end) mask[point] = true }
        return mask
    }

    /** Rewrite size of one hunk: edit distance for Latin-only fixes, otherwise the replaced length. */
    fun changeCost(hunk: EditHunk): Int {
        val latin = (hunk.wrong + hunk.corrected).all { it.code < 128 }
        return if (latin) levenshtein(hunk.wrong.lowercase(), hunk.corrected.lowercase())
        else hunk.end - hunk.start
    }

    private fun align(a: List<Token>, b: List<Token>, same: (Token, Token) -> Boolean): List<Pair<Int, Int>>? {
        var prefix = 0
        while (prefix < a.size && prefix < b.size && same(a[prefix], b[prefix])) prefix++
        var suffix = 0
        while (suffix < a.size - prefix && suffix < b.size - prefix &&
            same(a[a.size - 1 - suffix], b[b.size - 1 - suffix])
        ) suffix++
        val n = a.size - prefix - suffix
        val m = b.size - prefix - suffix
        if (n > MAX_ALIGNED_TOKENS || m > MAX_ALIGNED_TOKENS) return null
        val width = m + 1
        val dp = IntArray((n + 1) * width)
        for (i in n - 1 downTo 0) for (j in m - 1 downTo 0) {
            dp[i * width + j] = if (same(a[prefix + i], b[prefix + j])) dp[(i + 1) * width + j + 1] + 1
            else maxOf(dp[(i + 1) * width + j], dp[i * width + j + 1])
        }
        val matches = ArrayList<Pair<Int, Int>>(prefix + suffix + minOf(n, m))
        for (k in 0 until prefix) matches += k to k
        var i = 0
        var j = 0
        while (i < n && j < m) {
            when {
                same(a[prefix + i], b[prefix + j]) -> { matches += (prefix + i) to (prefix + j); i++; j++ }
                dp[(i + 1) * width + j] >= dp[i * width + j + 1] -> i++
                else -> j++
            }
        }
        for (k in 0 until suffix) matches += (a.size - suffix + k) to (b.size - suffix + k)
        return matches
    }

    private fun tokenize(text: String): List<Token> {
        val points = text.codePoints().toArray()
        val tokens = ArrayList<Token>(points.size)
        var index = 0
        while (index < points.size) {
            val start = index
            val point = points[index]
            val latin = isWordPoint(point)
            when {
                latin -> while (index < points.size && isWordPoint(points[index])) index++
                Character.isWhitespace(point) -> while (index < points.size && Character.isWhitespace(points[index])) index++
                else -> index++
            }
            tokens += Token(substring(points, start, index), start, index, latin)
        }
        return tokens
    }

    /** Latin/other-alphabet letters and digits; Han and kana are single-character tokens. */
    private fun isWordPoint(point: Int): Boolean {
        if (!Character.isLetterOrDigit(point)) return false
        return when (Character.UnicodeScript.of(point)) {
            Character.UnicodeScript.HAN, Character.UnicodeScript.HIRAGANA,
            Character.UnicodeScript.KATAKANA, Character.UnicodeScript.HANGUL -> false
            else -> true
        }
    }

    private fun substring(points: IntArray, start: Int, end: Int): String = buildString(end - start) {
        for (index in start until end) appendCodePoint(points[index])
    }

    private fun String.substringByCodePoints(start: Int, end: Int): String =
        substring(offsetByCodePoints(0, start), offsetByCodePoints(0, end))

    private fun levenshtein(a: String, b: String): Int {
        var previous = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            val current = IntArray(b.length + 1)
            current[0] = i
            for (j in 1..b.length) {
                current[j] = minOf(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + if (a[i - 1] == b[j - 1]) 0 else 1)
            }
            previous = current
        }
        return previous[b.length]
    }
}
