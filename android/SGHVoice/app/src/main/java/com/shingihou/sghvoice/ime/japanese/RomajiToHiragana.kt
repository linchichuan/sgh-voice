package com.shingihou.sghvoice.ime.japanese

import java.text.Normalizer
import java.util.Locale

/**
 * Result of converting an incremental romaji buffer.
 *
 * [pendingRomaji] is deliberately retained instead of dropped. For example,
 * `ky` remains pending until `a`, `u`, or `o` arrives. The keyboard can render
 * [displayText] without losing an unfinished keystroke sequence.
 */
data class RomajiConversion(
    val hiragana: String,
    val pendingRomaji: String
) {
    val displayText: String
        get() = hiragana + pendingRomaji

    val isComplete: Boolean
        get() = pendingRomaji.isEmpty()
}

/**
 * Stateless, pure Kotlin Hepburn/IME-style romaji-to-hiragana conversion.
 *
 * This converter is intentionally independent of Android so it can be covered
 * by ordinary JVM tests. A caller that stores the original romaji buffer can
 * implement lossless backspace by removing one input character and converting
 * again.
 */
object RomajiToHiragana {
    private val VOWELS = "aiueo".toSet()
    private val CONSONANTS = "bcdfghjklmpqrstvwxyz".toSet()
    private val SUPPORTED_INPUT = ("abcdefghijklmnopqrstuvwxyz'-").toSet()

    private val TABLE: Map<String, String> = mapOf(
        // Vowels.
        "a" to "あ", "i" to "い", "u" to "う", "e" to "え", "o" to "お",

        // Basic gojuon and common IME aliases.
        "ka" to "か", "ki" to "き", "ku" to "く", "ke" to "け", "ko" to "こ",
        "ca" to "か", "ci" to "し", "cu" to "く", "ce" to "せ", "co" to "こ",
        "sa" to "さ", "shi" to "し", "si" to "し", "su" to "す", "se" to "せ", "so" to "そ",
        "ta" to "た", "chi" to "ち", "ti" to "ち", "tsu" to "つ", "tu" to "つ",
        "te" to "て", "to" to "と",
        "na" to "な", "ni" to "に", "nu" to "ぬ", "ne" to "ね", "no" to "の",
        "ha" to "は", "hi" to "ひ", "fu" to "ふ", "hu" to "ふ", "he" to "へ", "ho" to "ほ",
        "ma" to "ま", "mi" to "み", "mu" to "む", "me" to "め", "mo" to "も",
        "ya" to "や", "yu" to "ゆ", "yo" to "よ",
        "ra" to "ら", "ri" to "り", "ru" to "る", "re" to "れ", "ro" to "ろ",
        "wa" to "わ", "wo" to "を",

        // Voiced and semi-voiced rows.
        "ga" to "が", "gi" to "ぎ", "gu" to "ぐ", "ge" to "げ", "go" to "ご",
        "za" to "ざ", "ji" to "じ", "zi" to "じ", "zu" to "ず", "ze" to "ぜ", "zo" to "ぞ",
        "da" to "だ", "di" to "ぢ", "du" to "づ", "de" to "で", "do" to "ど",
        "ba" to "ば", "bi" to "び", "bu" to "ぶ", "be" to "べ", "bo" to "ぼ",
        "pa" to "ぱ", "pi" to "ぴ", "pu" to "ぷ", "pe" to "ぺ", "po" to "ぽ",

        // Contracted sounds (拗音).
        "kya" to "きゃ", "kyu" to "きゅ", "kyo" to "きょ",
        "gya" to "ぎゃ", "gyu" to "ぎゅ", "gyo" to "ぎょ",
        "sha" to "しゃ", "shu" to "しゅ", "sho" to "しょ",
        "sya" to "しゃ", "syu" to "しゅ", "syo" to "しょ",
        "ja" to "じゃ", "ju" to "じゅ", "jo" to "じょ",
        "jya" to "じゃ", "jyu" to "じゅ", "jyo" to "じょ",
        "zya" to "じゃ", "zyu" to "じゅ", "zyo" to "じょ",
        "cha" to "ちゃ", "chu" to "ちゅ", "cho" to "ちょ",
        "cya" to "ちゃ", "cyu" to "ちゅ", "cyo" to "ちょ",
        "tya" to "ちゃ", "tyu" to "ちゅ", "tyo" to "ちょ",
        "dya" to "ぢゃ", "dyu" to "ぢゅ", "dyo" to "ぢょ",
        "nya" to "にゃ", "nyu" to "にゅ", "nyo" to "にょ",
        "hya" to "ひゃ", "hyu" to "ひゅ", "hyo" to "ひょ",
        "bya" to "びゃ", "byu" to "びゅ", "byo" to "びょ",
        "pya" to "ぴゃ", "pyu" to "ぴゅ", "pyo" to "ぴょ",
        "mya" to "みゃ", "myu" to "みゅ", "myo" to "みょ",
        "rya" to "りゃ", "ryu" to "りゅ", "ryo" to "りょ",

        // Explicit small kana (小假名).
        "xa" to "ぁ", "xi" to "ぃ", "xu" to "ぅ", "xe" to "ぇ", "xo" to "ぉ",
        "la" to "ぁ", "li" to "ぃ", "lu" to "ぅ", "le" to "ぇ", "lo" to "ぉ",
        "xya" to "ゃ", "xyu" to "ゅ", "xyo" to "ょ",
        "lya" to "ゃ", "lyu" to "ゅ", "lyo" to "ょ",
        "xtu" to "っ", "xtsu" to "っ", "ltu" to "っ", "ltsu" to "っ",
        "xwa" to "ゎ", "lwa" to "ゎ",
        "xka" to "ゕ", "lka" to "ゕ", "xke" to "ゖ", "lke" to "ゖ",

        // Common foreign-sound sequences.
        "ye" to "いぇ",
        "wi" to "うぃ", "wu" to "う", "we" to "うぇ",
        "wha" to "うぁ", "whi" to "うぃ", "whe" to "うぇ", "who" to "うぉ",
        "kwa" to "くぁ", "kwi" to "くぃ", "kwe" to "くぇ", "kwo" to "くぉ",
        "gwa" to "ぐぁ", "gwi" to "ぐぃ", "gwe" to "ぐぇ", "gwo" to "ぐぉ",
        "qa" to "くぁ", "qi" to "くぃ", "qe" to "くぇ", "qo" to "くぉ",
        "qya" to "くゃ", "qyu" to "くゅ", "qyo" to "くょ",
        "she" to "しぇ", "je" to "じぇ", "che" to "ちぇ",
        "tsa" to "つぁ", "tsi" to "つぃ", "tse" to "つぇ", "tso" to "つぉ",
        "thi" to "てぃ", "thu" to "てゅ", "the" to "てぇ", "tho" to "てょ",
        "dhi" to "でぃ", "dhu" to "でゅ", "dhe" to "でぇ", "dho" to "でょ",
        "tyi" to "てぃ", "dyi" to "でぃ",
        "fa" to "ふぁ", "fi" to "ふぃ", "fe" to "ふぇ", "fo" to "ふぉ",
        "fya" to "ふゃ", "fyu" to "ふゅ", "fyo" to "ふょ",
        "va" to "ゔぁ", "vi" to "ゔぃ", "vu" to "ゔ", "ve" to "ゔぇ", "vo" to "ゔぉ",
        "vya" to "ゔゃ", "vyu" to "ゔゅ", "vyo" to "ゔょ"
    )

    private val maxSequenceLength = TABLE.keys.maxOf(String::length)

    /**
     * Converts [input]. A terminal single `n` stays pending during ordinary
     * composition, but [finalizeTerminalN] resolves it to `ん` for candidate
     * lookup and commit.
     */
    fun convert(
        input: String,
        finalizeTerminalN: Boolean = false
    ): RomajiConversion {
        val normalized = input.lowercase(Locale.ROOT)
        require(normalized.all { it in SUPPORTED_INPUT }) {
            "Romaji input may only contain ASCII letters, apostrophe, and hyphen."
        }

        val output = StringBuilder()
        var index = 0
        while (index < normalized.length) {
            val current = normalized[index]

            if (current == '-') {
                output.append('ー')
                index += 1
                continue
            }

            if (current == 'n') {
                if (index == normalized.lastIndex) {
                    if (finalizeTerminalN) {
                        output.append('ん')
                        index += 1
                    } else {
                        return RomajiConversion(output.toString(), "n")
                    }
                    continue
                }

                val next = normalized[index + 1]
                if (next == '\'') {
                    output.append('ん')
                    index += 2
                    continue
                }
                if (next == 'n') {
                    val afterDoubleN = normalized.getOrNull(index + 2)
                    output.append('ん')
                    index += if (afterDoubleN != null && (afterDoubleN in VOWELS || afterDoubleN == 'y')) {
                        1
                    } else {
                        2
                    }
                    continue
                }
                if (next !in VOWELS && next != 'y') {
                    output.append('ん')
                    index += 1
                    continue
                }
            }

            if (
                index + 1 < normalized.length &&
                current in CONSONANTS &&
                current != 'n' &&
                normalized[index + 1] == current
            ) {
                output.append('っ')
                index += 1
                continue
            }

            // `matcha` is a common spelling whose sokuon precedes `cha`.
            if (normalized.startsWith("tch", startIndex = index)) {
                output.append('っ')
                index += 1
                continue
            }

            val remainingLength = normalized.length - index
            var matchedLength = minOf(maxSequenceLength, remainingLength)
            var matchedKana: String? = null
            while (matchedLength > 0) {
                val sequence = normalized.substring(index, index + matchedLength)
                matchedKana = TABLE[sequence]
                if (matchedKana != null) break
                matchedLength -= 1
            }

            if (matchedKana == null) {
                return RomajiConversion(
                    hiragana = output.toString(),
                    pendingRomaji = normalized.substring(index)
                )
            }
            output.append(matchedKana)
            index += matchedLength
        }

        return RomajiConversion(output.toString(), pendingRomaji = "")
    }

    fun isSupportedInput(value: String): Boolean =
        value.lowercase(Locale.ROOT).all { it in SUPPORTED_INPUT }
}

/** Unicode-only script conversion used by candidate fallbacks and lookup. */
object JapaneseScripts {
    fun hiraganaToKatakana(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFKC)
            .mapCodePoints { codepoint ->
                when (codepoint) {
                    in 0x3041..0x3096,
                    in 0x309D..0x309E -> codepoint + 0x60
                    else -> codepoint
                }
            }

    fun katakanaToHiragana(value: String): String =
        Normalizer.normalize(value, Normalizer.Form.NFKC)
            .mapCodePoints { codepoint ->
                when (codepoint) {
                    in 0x30A1..0x30F6,
                    in 0x30FD..0x30FE -> codepoint - 0x60
                    else -> codepoint
                }
            }

    private fun String.mapCodePoints(transform: (Int) -> Int): String {
        val result = StringBuilder(length)
        codePoints().forEach { result.appendCodePoint(transform(it)) }
        return result.toString()
    }
}
