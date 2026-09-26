package com.shingihou.sghvoice.ime.japanese

/** Japanese manual keyboard geometry. The stored reading is always hiragana. */
enum class JapaneseInputStyle {
    ROMAJI,
    KANA_12_KEY
}

/** The ten character groups on a conventional Japanese phone keyboard. */
object Kana12Key {
    const val MULTITAP_WINDOW_MS = 850L

    val groups: Map<String, List<String>> = linkedMapOf(
        "a" to listOf("あ", "い", "う", "え", "お"),
        "ka" to listOf("か", "き", "く", "け", "こ"),
        "sa" to listOf("さ", "し", "す", "せ", "そ"),
        "ta" to listOf("た", "ち", "つ", "て", "と"),
        "na" to listOf("な", "に", "ぬ", "ね", "の"),
        "ha" to listOf("は", "ひ", "ふ", "へ", "ほ"),
        "ma" to listOf("ま", "み", "む", "め", "も"),
        "ya" to listOf("や", "ゆ", "よ"),
        "ra" to listOf("ら", "り", "る", "れ", "ろ"),
        "wa" to listOf("わ", "を", "ん", "ー")
    )

    /** Cycling the modifier key covers voiced, semi-voiced and small kana. */
    private val modifierCycles: List<List<String>> = listOf(
        listOf("あ", "ぁ"), listOf("い", "ぃ"), listOf("う", "ぅ", "ゔ"),
        listOf("え", "ぇ"), listOf("お", "ぉ"),
        listOf("か", "が"), listOf("き", "ぎ"), listOf("く", "ぐ"),
        listOf("け", "げ"), listOf("こ", "ご"),
        listOf("さ", "ざ"), listOf("し", "じ"), listOf("す", "ず"),
        listOf("せ", "ぜ"), listOf("そ", "ぞ"),
        listOf("た", "だ"), listOf("ち", "ぢ"), listOf("つ", "っ", "づ"),
        listOf("て", "で"), listOf("と", "ど"),
        listOf("は", "ば", "ぱ"), listOf("ひ", "び", "ぴ"),
        listOf("ふ", "ぶ", "ぷ"), listOf("へ", "べ", "ぺ"),
        listOf("ほ", "ぼ", "ぽ"),
        listOf("や", "ゃ"), listOf("ゆ", "ゅ"), listOf("よ", "ょ"),
        listOf("わ", "ゎ")
    )

    fun nextModified(kana: String): String? {
        val cycle = modifierCycles.firstOrNull { kana in it } ?: return null
        return cycle[(cycle.indexOf(kana) + 1) % cycle.size]
    }

    fun isKana(character: Char): Boolean = character in '\u3041'..'\u3096' || character == 'ー'
}
