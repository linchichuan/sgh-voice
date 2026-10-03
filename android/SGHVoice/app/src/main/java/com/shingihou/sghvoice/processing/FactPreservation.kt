package com.shingihou.sghvoice.processing

/**
 * Shared, comparison-only detection of facts a spelling repair must never change:
 * numbers (Arabic and CJK numerals) with their unit/date suffix, signs, currencies
 * and negations. Used by the dictation guard and by dictionary corrections.
 */
internal object FactPreservation {
    const val NUMERAL_CHARS = "0123456789０１２３４５６７８９零〇一二兩两三四五六七八九十百千萬万億亿"

    private val numberWithUnit = Regex(
        "[$NUMERAL_CHARS]+(?:[.,:/][$NUMERAL_CHARS]+)*\\s*" +
            "(?:小時|小时|分鐘|分钟|美元|美金|日圓|日元|日幣|台幣|元|圓|円|塊|點|点|時|时|分|秒|年|月|日|號|号|週|周|天|個|个|位|人|次|件|份|台|臺|倍|%|％)?"
    )
    private val signOrCurrency = Regex(
        "[+\\-−－＋±負负$＄¥￥€£%％]|零下|マイナス|プラス|美元|美金|日圓|日元|日幣|台幣|人民幣|韓元|歐元|港幣|元|圓|円|塊錢|" +
            "\\b(?:dollars?|yen|usd|jpy|twd|eur|minus|plus)\\b",
        RegexOption.IGNORE_CASE
    )

    /**
     * Negation cues. Japanese ず/ぬ count only after an a-row (or せ/来) verb stem, so the
     * adverb まず / 先ず, はず and ずつ are not negations; 行かず, 実行せず, 知らぬ are.
     */
    val NEGATION = Regex(
        "不是|不要|不能|不會|不可以|不用|沒有|無法|沒辦法|別|不|沒|無|ない|ません|" +
            "(?<=[かがさざただなばまらわ])ぬ|(?<=[かがさざただなばまらわせ来])ず|" +
            "\\b(?:not|never|no|without|cannot|can't|don't|doesn't|didn't|won't|isn't|aren't|shouldn't|wouldn't|couldn't)\\b",
        RegexOption.IGNORE_CASE
    )
    private val adverbMazu = Regex("(?<![\\p{L}\\p{N}])まず|先ず")

    private const val TITLES = "先生|小姐|女士|老師|老师|醫師|医师|醫生|医生|太太|教授|さん|様|樣|氏|くん|ちゃん|" +
        "經理|经理|總監|总监|董事長|董事长|社長|部長|部长|課長|课长|係長|專務|専務|常務|主任|律師|律师|" +
        "院長|院长|校長|校长|處長|处长|科長|科长|組長|组长|店長|店长|會長|会长|博士|藥師|薬剤師|護理師|" +
        "總(?![是共算計结結之括體体])|总(?![是共算计结之括体])"

    /**
     * A person's name next to a title: up to 3 Han/katakana characters right before a title
     * (林先生, 陳小姐, 田中さん), or the word after Mr./Ms./Mrs./Dr./Prof. The window is
     * deliberately generous (交給林先生 protects 交給林): unknown boundaries fail closed.
     */
    val NAME_WITH_TITLE = Regex(
        "[\\p{script=Han}ァ-ヺー]{1,3}(?:$TITLES)|\\b(?:Mr|Ms|Mrs|Dr|Prof)\\.?\\s+[A-Za-z][A-Za-z'-]*"
    )

    fun nameSignature(text: String): List<String> =
        NAME_WITH_TITLE.findAll(text).map { it.value.replace(Regex("\\s+"), " ") }.toList()

    fun nameRanges(text: String): List<IntRange> = NAME_WITH_TITLE.findAll(text).map { it.range }.toList()

    fun countNegations(text: String): Int = NEGATION.findAll(adverbMazu.replace(text, "＿")).count()

    fun containsNumeral(text: String): Boolean = text.any { it in NUMERAL_CHARS }

    private fun signature(text: String): List<String> {
        val neutral = adverbMazu.replace(text, "＿")
        return numberWithUnit.findAll(neutral).map { "n:" + it.value.replace(Regex("\\s+"), "") }.toList() +
            signOrCurrency.findAll(neutral).map { "s:" + it.value.lowercase() }.toList() +
            NEGATION.findAll(neutral).map { "x:" + it.value.lowercase() }.toList() +
            nameSignature(neutral).map { "p:$it" } +
            // Same extractor as the dictation guard: (sign, value, unit) of every quantity.
            NumericFacts.extract(neutral).map { "v:$it" }
    }

    /** A dictionary rule may only fix spelling; it may never change a fact. */
    fun correctionPreservesFacts(wrong: String, corrected: String): Boolean =
        signature(wrong) == signature(corrected)
}
