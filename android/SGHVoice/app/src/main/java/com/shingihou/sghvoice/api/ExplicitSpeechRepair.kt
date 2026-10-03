package com.shingihou.sghvoice.api

/** Comparison-only normalization of explicit spoken repairs, never an output rewrite. */
internal object ExplicitSpeechRepair {
    private const val NUMBER = "(?:[0-9]+(?:[.:/-][0-9]+)*|[零〇一二兩三四五六七八九十百千萬億]+)"
    private const val UNIT = "(?:小時|分鐘|美元|日圓|日元|元|點|時|分|年|月|日|號|個|位|人|次|天|週|件|份|台|臺|倍|%)"
    // Punctuation on both sides of the repair cue matters: "三點不是四點"
    // is a comparison, not permission to discard 三點.
    private val quantityRepair = Regex(
        "(?<![A-Za-z0-9零〇一二兩三四五六七八九十百千萬億負负第_+−－＋.:/-])($NUMBER)\\s*($UNIT)?[，,]\\s*" +
            "(?:不是|不對|不对|不|更正)[，,]\\s*(?:應該是|应该是|是)?\\s*" +
            "($NUMBER)\\s*($UNIT)?"
    )
    private val temporalRepair = Regex(
        "(?:今天|明天|後天|昨天|前天)[，,]\\s*(?:不是|不對|不对|不)[，,]\\s*" +
            "(?:是\\s*)?(今天|明天|後天|昨天|前天)"
    )
    private val locativeRestart = Regex("[啊呀][，,]\\s*沒有[，,]\\s*(?=(?:是)?在)")
    private val clauseBoundary = Regex("[，,。！？!?；;\\n]")
    private val negativeOrQuestion = Regex("不是|不要|不能|沒有|無法|沒|不|無|嗎|吗|呢|[?？]")
    private val quantity = Regex("(?:[+\\-−－＋負负]\\s*)?$NUMBER\\s*$UNIT(?:半)?")
    // Deliberately exclude calendar dates, ordinals, decimals, signed values,
    // half-hours and digit-by-digit numbers. This is NOT a general number parser.
    private val comparableQuantity = Regex(
        "($NUMBER)\\s*(小時|分鐘|美元|日圓|日元|元|點|時|分|個|位|人|次|天|週|件|份|台|臺|倍|%)(半)?"
    )
    private val literalContext = Regex("`[^`]*`|https?://[^\\s，。！？]+|(?:/|[A-Za-z]:\\\\)[^\\s，。！？]+")
    private const val NUMERAL_CHARS = "零〇一二兩三四五六七八九十百千萬億"
    private const val NUMBER_BOUNDARY = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./:@\\+-−－＋#"

    /** Comparison only: never rewrite what the user sees or sends. */
    fun canonicalizeQuantities(text: String): String {
        val literalRanges = literalContext.findAll(text).map { it.range }.toList()
        return comparableQuantity.replace(text) { match ->
            val before = text.substring(0, match.range.first).trimEnd().lastOrNull()
            val after = text.substring(match.range.last + 1).trimStart().firstOrNull()
            val blockedBefore = before != null &&
                (before in NUMBER_BOUNDARY || before in NUMERAL_CHARS || before in "負负第點点")
            val blockedAfter = after != null &&
                (after in NUMBER_BOUNDARY || after in NUMERAL_CHARS || after == '半')
            val literal = literalRanges.any { it.first <= match.range.last && it.last >= match.range.first }
            val value = boundedInteger(match.groupValues[1])
            if (literal || blockedBefore || blockedAfter || match.groupValues[3].isNotEmpty() || value == null)
                match.value
            else "$value${match.groupValues[2]}"
        }
    }

    private fun boundedInteger(token: String): Int? {
        if (token.length > 15) return null
        if (token.all { it in '0'..'9' }) {
            if (token.length > 1 && token.startsWith('0')) return null
            return token.toIntOrNull()?.takeIf { it in 0..9999 }
        }
        val normalized = token.replace('兩', '二').replace('〇', '零')
        var total = 0
        var pending: Int? = null
        var previousScale = 10_000
        for (char in normalized) {
            val digit = "零一二三四五六七八九".indexOf(char)
            if (digit >= 0) {
                if (pending != null && pending != 0) return null
                pending = digit
            } else {
                val scale = when (char) { '十' -> 10; '百' -> 100; '千' -> 1000; else -> return null }
                if (scale >= previousScale) return null
                val multiplier = pending ?: if (scale == 10 && total == 0) 1 else return null
                total += multiplier * scale
                previousScale = scale
                pending = null
            }
        }
        val value = total + (pending ?: 0)
        // Round-trip validation rejects ambiguous colloquial forms such as 一百二,
        // malformed repeated scales and Chinese serial numbers such as 二〇二六.
        return value.takeIf { it in 0..9999 && spellInteger(it) == normalized }
    }

    private fun spellInteger(value: Int): String {
        if (value == 0) return "零"
        var remaining = value
        var needsZero = false
        return buildString {
            for ((scale, suffix) in listOf(1000 to "千", 100 to "百", 10 to "十", 1 to "")) {
                val digit = remaining / scale
                remaining %= scale
                if (digit == 0) {
                    if (isNotEmpty() && remaining > 0) needsZero = true
                } else {
                    if (needsZero) append('零')
                    needsZero = false
                    if (!(scale == 10 && value in 10..19)) append("零一二三四五六七八九"[digit])
                    append(suffix)
                }
            }
        }
    }

    fun preservesCorrectedQuantities(source: String, candidate: String): Boolean {
        // Compare every quantity, not just explicit repairs: numeral equivalence
        // never permits changing/dropping its unit or moving it to another fact.
        fun quantities(text: String) = quantity.findAll(canonicalizeQuantities(normalize(text)))
            .map { it.value.replace(Regex("\\s+"), "") }.toList()
        return quantities(source) == quantities(candidate)
    }

    fun normalize(text: String): String {
        var result = temporalRepair.replace(text) { it.groupValues[1] }
        // Bounded passes handle "3 點，不是，4 點，不是，5 點".
        for (pass in 0 until 8) {
            val next = quantityRepair.replace(result) { match ->
                val firstUnit = match.groupValues[2]
                val finalUnit = match.groupValues[4]
                val preceding = result.substring(0, match.range.first).trimEnd().lastOrNull()
                val signedOrOrdinal = preceding != null && preceding in "+-−－＋負负第"
                if (!signedOrOrdinal && firstUnit == finalUnit) match.groupValues[3] + finalUnit else match.value
            }
            if (next == result) break
            result = next
        }
        result = locativeRestart.replace(result) { match ->
            val before = result.substring(0, match.range.first)
            val previousClause = before.substringAfterLast('。').substringAfterLast('？')
                .substringAfterLast('?').substringAfterLast('\n')
            val after = result.substring(match.range.last + 1)
            val followingClause = clauseBoundary.split(after, limit = 2).first()
            // An isolated "沒有" answering a question or describing absence
            // remains a real negation. Only this filler + positive location
            // restart is treated as the speaker correcting their phrasing.
            val followsQuestion = before.trimEnd().endsWith('？') || before.trimEnd().endsWith('?')
            if (!followsQuestion && previousClause.isNotBlank() &&
                !negativeOrQuestion.containsMatchIn(previousClause) &&
                !negativeOrQuestion.containsMatchIn(followingClause)
            ) "，" else match.value
        }
        return result
    }
}
