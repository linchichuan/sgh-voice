package com.shingihou.sghvoice.processing

import java.math.BigDecimal

/**
 * Comparison-only numeric fact extractor shared by the dictation guard (LlmClient) and the
 * dictionary/learned-rule side (FactPreservation / TextCorrectionEngine). Never rewrites output.
 *
 * A numeric fact is (sign, normalized value, unit or ""). Values come from Arabic digits
 * (decimals, thousands separators, %), full-width digits and Chinese / Japanese numerals
 * (七十五, 三千兩百, 一萬五, 二〇二六). 萬/億/千/百 after a number are magnitude multipliers
 * (-300 萬 = -3000000). Signs: adjacent -/−/－/+/＋, or 負, 零下, 減, マイナス, minus,
 * 正, プラス, plus right before the number. Ordinals (第一) and fixed expressions where a
 * numeral is not a quantity (一下, 一起, 萬一 ...) are excluded.
 */
internal object NumericFacts {
    data class Fact(val sign: String, val value: String, val unit: String) {
        override fun toString() = "$sign|$value|$unit"
    }

    private class Hit(val start: Int, val end: Int, val fact: Fact, val canonical: String?)

    private const val CJK_DIGITS = "零〇一二兩两三四五六七八九"
    private const val CJK_SMALL = "十百千"
    private const val CJK_BIG = "萬万億亿"
    private const val CJK_NUMERALS = CJK_DIGITS + CJK_SMALL + CJK_BIG
    private const val ANY_NUMERAL = "0-9０-９$CJK_NUMERALS"
    private const val MASK = '□'

    /** Spans whose numerals are not quantities. Same-length masking keeps offsets. */
    private val NON_QUANTITY = Regex(
        // Ordinals: 第一, 第 3 (the following 點/條/項 is not a unit of a quantity).
        "第\\s*[$ANY_NUMERAL]+|" +
            // Fixed expressions; not when glued to a preceding numeral (十一下 / 一萬一 / 三點十分).
            "(?<![$ANY_NUMERAL])(?:一下|一些|一起|一直|一定|一般|一樣|一样|一切|一旦|一邊|一边|" +
            "一點點|一点点|一點兒|一点儿|一會|一会|一番|一緒|一応|一體|一体|一律|一致|一向|一再|" +
            "一方面|一路|一同|一旁|一口氣|一口气|萬一|万一|萬が一|万が一|" +
            "千[萬万](?=[不別别要記记務务])|(?<![點点時时])十分)|" +
            "(?:有|這|这|那|快|慢|多|少|好|早|晚)一[點点]|統一|统一|唯一|同一|之一|其一|" +
            // Verb-一-verb (看一看).
            "(?<=(\\p{script=Han}))一(?=\\1)"
    )
    // 零下 / 百分之 are sign / unit words that contain numeral characters.
    private val PREFIX_WORDS = Regex("零下(?=\\s*[$ANY_NUMERAL])|百分之(?=\\s*[$ANY_NUMERAL])")

    private val ASCII_NUMBER = Regex(
        "[0-9]{1,3}(?:,[0-9]{3})+(?:\\.[0-9]+)?(?![0-9])|[0-9]+(?:[.:/-][0-9]+)*"
    )
    private val LITERAL_CONTEXT = Regex("`[^`]*`|https?://[^\\s，。！？]+|(?:/|[A-Za-z]:\\\\)[^\\s，。！？]+")
    private const val IDENTIFIER_CHARS =
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_./:@\\+-#"
    private val SIMPLE_DECIMAL = Regex("[0-9,]+(?:\\.[0-9]+)?")
    private val UNIT = Regex(
        "(?:平方公尺|平方米|公里|公斤|公分|公尺|公升|毫升|毫米|釐米|厘米|小時|小时|分鐘|分钟|" +
            "美元|美金|日圓|日元|日幣|新台幣|台幣|臺幣|人民幣|港幣|歐元|韓元|キロ|グラム|メートル|ドル|" +
            "°C|°F|℃|%|％|度|米|坪|元|圓|円|塊|秒|分|點|点|時|时|年|月|日|號|号|週|周|天|個|个|位|人|" +
            "次|件|份|台|臺|倍|歲|岁|歳|張|张|本|枚|回|成)|" +
            "(?:percent|dollars?|usd|yen|jpy|twd|eur|km|kg|cm|mm|ml|mg|m|g|hours?|hrs?|minutes?|mins?|" +
            "seconds?|secs?|days?|weeks?|months?|years?)(?![A-Za-z])",
        RegexOption.IGNORE_CASE
    )
    private val UNIT_ALIASES = mapOf(
        "号" to "日", "號" to "日", "点" to "點", "时" to "時", "个" to "個", "臺" to "台", "张" to "張",
        "岁" to "歲", "歳" to "歲", "周" to "週", "小时" to "小時", "分钟" to "分鐘", "％" to "%",
        "percent" to "%", "℃" to "度", "°c" to "度", "美金" to "美元", "日元" to "日圓", "臺幣" to "台幣",
        "hrs" to "hour", "hr" to "hour", "mins" to "minute", "min" to "minute", "secs" to "second", "sec" to "second"
    )
    private val CURRENCY_PREFIX = mapOf('$' to "$", '＄' to "$", '¥' to "¥", '￥' to "¥", '€' to "€", '£' to "£")
    private val MINUS_WORDS = listOf("負", "负", "零下", "マイナス", "減", "减")
    private val PLUS_WORDS = listOf("プラス")

    fun extract(text: String): List<Fact> = scan(text).map { it.fact }

    /** Multiset equality: every numeric fact of [a] appears in [b] equally often and vice versa. */
    fun sameFacts(a: String, b: String): Boolean =
        extract(a).map { it.toString() }.sorted() == extract(b).map { it.toString() }.sorted()

    /**
     * Comparison-only: rewrites Chinese / full-width numerals to Arabic so a value-preserving
     * conversion (三公里 → 3公里, 二〇二六年 → 2026年) compares equal. ASCII numbers, ordinals
     * and fixed expressions are left untouched.
     */
    fun canonicalize(text: String): String {
        val folded = fold(text)
        val literals = LITERAL_CONTEXT.findAll(folded).map { it.range }.toList()
        val hits = scan(text).filter { hit ->
            hit.canonical != null &&
                // id_四點, /tmp/會議四點, `v四`: numerals glued to identifiers, paths, URLs and
                // code stay literal so the guard's literal-span comparison still sees the change.
                folded.getOrNull(hit.start - 1).let { it == null || it !in IDENTIFIER_CHARS } &&
                literals.none { it.first < hit.end && it.last >= hit.start }
        }
        if (hits.isEmpty()) return folded
        return buildString(folded.length) {
            var last = 0
            for (hit in hits) {
                append(folded, last, hit.start)
                append(hit.canonical)
                last = hit.end
            }
            append(folded, last, folded.length)
        }
    }

    private fun fold(text: String): String = buildString(text.length) {
        for (c in text) append(if (c in '０'..'９') '0' + (c - '０') else c)
    }

    private fun mask(folded: String): String {
        val chars = folded.toCharArray()
        for (regex in listOf(NON_QUANTITY, PREFIX_WORDS)) {
            regex.findAll(folded).forEach { m -> for (i in m.range) chars[i] = MASK }
        }
        return String(chars)
    }

    private fun scan(text: String): List<Hit> {
        val folded = fold(text)
        val masked = mask(folded)
        val hits = mutableListOf<Hit>()
        var i = 0
        while (i < masked.length) {
            val c = masked[i]
            when {
                c in '0'..'9' -> {
                    val token = ASCII_NUMBER.find(masked, i)?.takeIf { it.range.first == i }?.value
                        ?: masked.substring(i, i + 1)
                    var end = i + token.length
                    var value: String
                    if (SIMPLE_DECIMAL.matches(token) && token.count { it == '.' } <= 1) {
                        var number = BigDecimal(token.replace(",", ""))
                        var j = end
                        while (j < masked.length && masked[j] == ' ') j++
                        var multiplied = false
                        while (j < masked.length && masked[j] in "百千萬万億亿") {
                            number = number.multiply(BigDecimal(scale(masked[j])))
                            j++
                            multiplied = true
                        }
                        if (multiplied) end = j
                        value = number.stripTrailingZeros().toPlainString()
                    } else {
                        value = token
                    }
                    // The canonical form of an ASCII number is itself (folded); keep it literal.
                    hits += Hit(i, end, fact(folded, i, end, value), null)
                    i = end
                }
                c in CJK_NUMERALS -> {
                    var j = i
                    while (j < masked.length && masked[j] in CJK_NUMERALS) j++
                    val run = masked.substring(i, j)
                    val number = parseCjk(run)
                    if (number == null) {
                        i = j
                        continue
                    }
                    val bigUnits = run.count { it in CJK_BIG }
                    val canonical = if (bigUnits == 1 && run.length > 1 && run.last() in CJK_BIG)
                        parseCjk(run.dropLast(1))?.toPlainString()?.plus(normalizeBig(run.last()))
                    else null
                    // Colloquial abbreviations (一百二, 一萬五) are compared by value but never
                    // canonicalized: an Arabic rewrite of them keeps failing the literal span check.
                    val colloquial = run.length >= 2 && digitOf(run.last()) > 0 &&
                        run[run.length - 2] in "百千萬万億亿"
                    hits += Hit(i, j, fact(folded, i, j, number.toPlainString()),
                        if (colloquial) null else canonical ?: number.toPlainString())
                    i = j
                }
                else -> i++
            }
        }
        return hits
    }

    private fun normalizeBig(c: Char) = when (c) { '万' -> '萬'; '亿' -> '億'; else -> c }

    private fun scale(c: Char): Long = when (c) {
        '十' -> 10L; '百' -> 100L; '千' -> 1_000L; '萬', '万' -> 10_000L; '億', '亿' -> 100_000_000L
        else -> 1L
    }

    private fun fact(folded: String, start: Int, end: Int, value: String): Fact {
        var k = start
        var percent = false
        if (k >= 3 && folded.startsWith("百分之", k - 3)) {
            percent = true
            k -= 3
        } else if (k >= 4 && folded.startsWith("百分之", k - 4) && folded[k - 1].isWhitespace()) {
            percent = true
            k -= 4
        }
        var sign = symbolSign(folded, k)
        if (sign.isNotEmpty()) k -= 1
        var currency = ""
        CURRENCY_PREFIX[folded.getOrNull(k - 1)]?.let { currency = it; k -= 1 }
        if (sign.isEmpty()) {
            sign = symbolSign(folded, k)
        }
        if (sign.isEmpty()) sign = wordSign(folded.substring(0, k).trimEnd())

        var j = end
        while (j < folded.length && (folded[j] == ' ' || folded[j] == '　' || folded[j] == '\t')) j++
        val unitMatch = UNIT.find(folded, j)?.takeIf { it.range.first == j }?.value
        val unit = when {
            percent -> "%"
            unitMatch != null -> normalizeUnit(unitMatch)
            else -> currency
        }
        return Fact(sign, value, unit)
    }

    private fun symbolSign(folded: String, k: Int): String {
        val c = folded.getOrNull(k - 1) ?: return ""
        val sign = when (c) { '-', '−', '－', '﹣' -> "-"; '+', '＋' -> "+"; else -> return "" }
        val previous = folded.getOrNull(k - 2)
        // 3-5 / A-5 / COVID-19: a hyphen glued to a word or number is not a sign.
        if (previous != null && (previous in 'A'..'Z' || previous in 'a'..'z' || previous in '0'..'9' ||
                previous in CJK_NUMERALS)) return ""
        return sign
    }

    private fun wordSign(before: String): String {
        if (MINUS_WORDS.any { before.endsWith(it) }) return "-"
        if (PLUS_WORDS.any { before.endsWith(it) }) return "+"
        val lower = before.lowercase()
        for ((word, sign) in listOf("minus" to "-", "plus" to "+")) {
            if (lower.endsWith(word)) {
                val previous = lower.getOrNull(lower.length - word.length - 1)
                if (previous == null || previous !in 'a'..'z') return sign
            }
        }
        // 正 is a sign only after a non-Han character or a copula / temperature word (氣溫正五度).
        if (before.endsWith("正")) {
            val previous = before.getOrNull(before.length - 2)
            if (previous == null || previous in "是為为溫温：: " ||
                !Character.UnicodeScript.of(previous.code).equals(Character.UnicodeScript.HAN)) return "+"
        }
        return ""
    }

    private fun normalizeUnit(unit: String): String {
        val lower = unit.lowercase()
        UNIT_ALIASES[unit]?.let { return it }
        UNIT_ALIASES[lower]?.let { return it }
        if (lower.first() in 'a'..'z') {
            return if (lower.length > 3 && lower.endsWith("s")) lower.dropLast(1) else lower
        }
        return unit
    }

    /** Chinese / Japanese numeral run to a value; null when the run is not a number. */
    private fun parseCjk(run: String): BigDecimal? {
        if (run.isEmpty()) return null
        val hasUnit = run.any { it in CJK_SMALL || it in CJK_BIG }
        if (!hasUnit) {
            // Digit-by-digit (二〇二六, 一二三) or a single digit.
            return BigDecimal(run.map { digitOf(it) }.joinToString(""))
        }
        if (run.none { digitOf(it) >= 0 } && run != "十") {
            // 百 / 千 / 萬 alone (百貨, 千葉, 萬事) are not quantities.
            if (run.any { it != '十' }) return null
        }
        var total = BigDecimal.ZERO
        var section = 0L
        var pending: Long? = null
        var lastScale = 0L
        var zeroSeen = false
        var previousWasUnit = false
        for (ch in run) {
            val d = digitOf(ch)
            if (d >= 0) {
                if (d == 0) zeroSeen = true
                if (pending != null && pending != 0L && !previousWasUnit) return null
                pending = d.toLong()
                previousWasUnit = false
                continue
            }
            val s = scale(ch)
            if (s < 10_000L) {
                section += (pending ?: 1L) * s
                lastScale = s
                zeroSeen = false
            } else {
                val sectionValue = section + (pending ?: 0L)
                val multiplier = if (sectionValue == 0L && total == BigDecimal.ZERO) 1L else sectionValue
                total = if (s == 100_000_000L)
                    total.add(BigDecimal(multiplier)).multiply(BigDecimal(s))
                else total.add(BigDecimal(multiplier).multiply(BigDecimal(s)))
                section = 0L
                lastScale = s
                zeroSeen = false
            }
            pending = null
            previousWasUnit = true
        }
        if (pending != null) {
            // Colloquial abbreviation: 一萬五 = 15000, 一百二 = 120; 一萬零五 = 10005.
            val tail = if (!zeroSeen && lastScale > 10L) pending * (lastScale / 10L) else pending
            if (lastScale >= 10_000L) total = total.add(BigDecimal(tail)) else section += tail
        }
        return total.add(BigDecimal(section))
    }

    private fun digitOf(c: Char): Int = when (c) {
        '零', '〇' -> 0; '一' -> 1; '二', '兩', '两' -> 2; '三' -> 3; '四' -> 4
        '五' -> 5; '六' -> 6; '七' -> 7; '八' -> 8; '九' -> 9; else -> -1
    }
}
