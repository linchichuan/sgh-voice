package com.shingihou.sghvoice.ime.manual

import com.shingihou.sghvoice.ime.ZhuyinComposer
import com.shingihou.sghvoice.ime.ZhuyinKey
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.japanese.Kana12Key
import java.util.Locale

/**
 * Produces key-grid data for every manual mode without creating Android Views.
 *
 * English and Japanese Romaji share QWERTY geometry. Japanese can alternatively
 * expose the native phone 12-key kana layout without changing other modes.
 * Numeric and symbol pages are shared across all three manual modes.
 */
class ManualKeyboardLayoutProvider {

    fun layout(
        mode: ManualKeyboardMode,
        layer: KeyboardLayer = KeyboardLayer.LETTERS,
        shiftState: ShiftState = ShiftState.OFF,
        japaneseInputStyle: JapaneseInputStyle = JapaneseInputStyle.ROMAJI
    ): ManualKeyboardLayout {
        val rows = when (layer) {
            KeyboardLayer.LETTERS -> when (mode) {
                ManualKeyboardMode.ZHUYIN -> ZhuyinLayoutAdapter.adapt()
                ManualKeyboardMode.JAPANESE -> when (japaneseInputStyle) {
                    JapaneseInputStyle.ROMAJI -> qwertyRows(mode, shiftState)
                    JapaneseInputStyle.KANA_12_KEY -> kana12Rows()
                }
                ManualKeyboardMode.ENGLISH -> qwertyRows(mode, shiftState)
            }

            KeyboardLayer.NUMBERS -> numericRows(mode)
            KeyboardLayer.SYMBOLS -> symbolRows(mode)
        }
        return ManualKeyboardLayout(
            mode = mode,
            layer = layer,
            rows = rows,
            shiftState = shiftState,
            japaneseInputStyle = japaneseInputStyle
        )
    }

    private fun qwertyRows(
        mode: ManualKeyboardMode,
        shiftState: ShiftState
    ): List<KeyboardRow> {
        val uppercase = shiftState != ShiftState.OFF
        val prefix = mode.name.lowercase(Locale.ROOT)
        val letterRows = listOf("qwertyuiop", "asdfghjkl")
            .mapIndexed { rowIndex, letters ->
                KeyboardRow(
                    letters.map { letter ->
                        characterKey(
                            id = "${prefix}_letter_$letter",
                            text = if (uppercase) {
                                letter.uppercaseChar().toString()
                            } else {
                                letter.toString()
                            },
                            contentDescription = "Letter $letter",
                            alternatives = latinAlternatives(letter)
                        )
                    }
                )
            }
            .toMutableList()

        letterRows += KeyboardRow(
            buildList {
                add(
                    actionKey(
                        id = if (mode == ManualKeyboardMode.JAPANESE) {
                            "japanese_layout"
                        } else {
                            "${prefix}_shift"
                        },
                        label = if (mode == ManualKeyboardMode.JAPANESE) {
                            "12キー"
                        } else {
                            shiftLabel(shiftState)
                        },
                        action = if (mode == ManualKeyboardMode.JAPANESE) {
                            KeyAction.ToggleJapaneseLayout
                        } else {
                            KeyAction.Shift
                        },
                        contentDescription = if (mode == ManualKeyboardMode.JAPANESE) {
                            "Switch to Japanese 12-key kana"
                        } else {
                            shiftDescription(shiftState)
                        },
                        widthWeight = 1.35f
                    )
                )
                "zxcvbnm".forEach { letter ->
                    add(
                        characterKey(
                            id = "${prefix}_letter_$letter",
                            text = if (uppercase) {
                                letter.uppercaseChar().toString()
                            } else {
                                letter.toString()
                            },
                            contentDescription = "Letter $letter",
                            alternatives = latinAlternatives(letter)
                        )
                    )
                }
                add(backspaceKey(prefix))
            }
        )

        letterRows += when (mode) {
            ManualKeyboardMode.ENGLISH -> englishBottomRow()
            ManualKeyboardMode.JAPANESE -> japaneseBottomRow()
            ManualKeyboardMode.ZHUYIN -> error("Zhuyin does not use QWERTY rows.")
        }
        return letterRows
    }

    private fun englishBottomRow(): KeyboardRow = KeyboardRow(
        listOf(
            switchLayerKey("english_numbers", "?123", KeyboardLayer.NUMBERS),
            characterKey("english_comma", ",", "Comma"),
            spaceKey("english_space", widthWeight = 4f),
            characterKey("english_period", ".", "Period"),
            enterKey("english_enter")
        )
    )

    private fun japaneseBottomRow(): KeyboardRow = KeyboardRow(
        listOf(
            switchLayerKey("japanese_numbers", "?123", KeyboardLayer.NUMBERS),
            actionKey(
                id = "japanese_script",
                label = "かな",
                action = KeyAction.ToggleJapaneseScript,
                contentDescription = "Toggle Hiragana and Katakana",
                widthWeight = 1.15f
            ),
            spaceKey("japanese_space", widthWeight = 3.2f),
            characterKey("japanese_comma", "、", "Japanese comma"),
            characterKey("japanese_period", "。", "Japanese period"),
            enterKey("japanese_enter")
        )
    )

    private fun kana12Rows(): List<KeyboardRow> = listOf(
        kanaRow(
            listOf("a", "ka", "sa").map(::kanaGroupKey),
            backspaceKey("japanese_kana")
        ),
        kanaRow(
            listOf("ta", "na", "ha").map(::kanaGroupKey),
            actionKey(
                "japanese_kana_finalize", "→",
                KeyAction.FinalizeJapaneseKana,
                "Finish current kana for a repeated character"
            )
        ),
        kanaRow(
            listOf("ma", "ya", "ra").map(::kanaGroupKey),
            actionKey(
                "japanese_script", "かな", KeyAction.ToggleJapaneseScript,
                "Toggle Hiragana and Katakana"
            )
        ),
        kanaRow(
            listOf(
                actionKey(
                    "japanese_kana_modifier", "小゛゜",
                    KeyAction.TransformJapaneseKana,
                    "Small, voiced or semi-voiced kana"
                ),
                kanaGroupKey("wa"),
                characterKey(
                    "japanese_kana_punctuation", "、", "Japanese punctuation",
                    alternatives = listOf("。", "！", "？")
                )
            ),
            enterKey("japanese_kana_enter")
        ),
        KeyboardRow(
            listOf(
                switchLayerKey(
                    "japanese_kana_numbers", "?123", KeyboardLayer.NUMBERS,
                    widthWeight = 1f
                ),
                actionKey(
                    "japanese_layout", "ABC", KeyAction.ToggleJapaneseLayout,
                    "Switch to Japanese Romaji QWERTY"
                ),
                spaceKey("japanese_kana_space", widthWeight = 1.75f)
            )
        )
    )

    /** Keep the phone keypad's three columns aligned beside a narrower action rail. */
    private fun kanaRow(keys: List<KeySpec>, action: KeySpec): KeyboardRow =
        KeyboardRow(keys + action.copy(widthWeight = 0.75f))

    private fun kanaGroupKey(group: String): KeySpec {
        val kana = Kana12Key.groups.getValue(group)
        return KeySpec(
            id = "japanese_kana_$group",
            label = kana.first(),
            action = KeyAction.TapJapaneseKana(group),
            alternatives = kana.drop(1),
            contentDescription = "${kana.joinToString(" ")} kana key"
        )
    }

    private fun numericRows(mode: ManualKeyboardMode): List<KeyboardRow> {
        val prefix = mode.name.lowercase(Locale.ROOT)
        return listOf(
            characterRow(prefix, "1234567890"),
            KeyboardRow(
                listOf("@", "#", "$", "%", "&", "-", "+", "(", ")", "/")
                    .map { characterKey("${prefix}_number_${stableId(it)}", it) }
            ),
            KeyboardRow(
                buildList {
                    add(
                        switchLayerKey(
                            "${prefix}_symbols",
                            "=\\<",
                            KeyboardLayer.SYMBOLS,
                            widthWeight = 1.35f
                        )
                    )
                    listOf("*", "\"", "'", ":", ";", "!", "?").forEach { symbol ->
                        add(characterKey("${prefix}_number_${stableId(symbol)}", symbol))
                    }
                    add(backspaceKey("${prefix}_number"))
                }
            ),
            utilityBottomRow(mode, KeyboardLayer.LETTERS)
        )
    }

    private fun symbolRows(mode: ManualKeyboardMode): List<KeyboardRow> {
        val prefix = mode.name.lowercase(Locale.ROOT)
        return listOf(
            KeyboardRow(
                listOf("~", "`", "|", "•", "√", "π", "÷", "×", "{", "}")
                    .map { characterKey("${prefix}_symbol_${stableId(it)}", it) }
            ),
            KeyboardRow(
                listOf("€", "£", "¥", "₩", "^", "_", "=", "[", "]", "\\")
                    .map { characterKey("${prefix}_symbol_${stableId(it)}", it) }
            ),
            KeyboardRow(
                buildList {
                    add(
                        switchLayerKey(
                            "${prefix}_numbers",
                            "?123",
                            KeyboardLayer.NUMBERS,
                            widthWeight = 1.35f
                        )
                    )
                    listOf("<", ">", "©", "®", "™", "✓", "°").forEach { symbol ->
                        add(characterKey("${prefix}_symbol_${stableId(symbol)}", symbol))
                    }
                    add(backspaceKey("${prefix}_symbol"))
                }
            ),
            utilityBottomRow(mode, KeyboardLayer.LETTERS)
        )
    }

    private fun utilityBottomRow(
        mode: ManualKeyboardMode,
        targetLayer: KeyboardLayer
    ): KeyboardRow {
        val prefix = mode.name.lowercase(Locale.ROOT)
        val returnLabel = when (mode) {
            ManualKeyboardMode.ZHUYIN -> "注"
            ManualKeyboardMode.JAPANESE -> "あ"
            ManualKeyboardMode.ENGLISH -> "ABC"
        }
        val punctuation = when (mode) {
            ManualKeyboardMode.ZHUYIN -> "，" to "。"
            ManualKeyboardMode.JAPANESE -> "、" to "。"
            ManualKeyboardMode.ENGLISH -> "," to "."
        }
        return KeyboardRow(
            listOf(
                switchLayerKey("${prefix}_letters", returnLabel, targetLayer),
                characterKey(
                    "${prefix}_utility_comma",
                    punctuation.first,
                    "Comma"
                ),
                spaceKey("${prefix}_utility_space", widthWeight = 4f),
                characterKey(
                    "${prefix}_utility_period",
                    punctuation.second,
                    "Period"
                ),
                enterKey("${prefix}_utility_enter")
            )
        )
    }

    private fun characterRow(prefix: String, characters: String): KeyboardRow =
        KeyboardRow(
            characters.map { character ->
                characterKey(
                    id = "${prefix}_character_${stableId(character.toString())}",
                    text = character.toString()
                )
            }
        )

    private fun characterKey(
        id: String,
        text: String,
        contentDescription: String = text,
        alternatives: List<String> = emptyList()
    ): KeySpec = KeySpec(
        id = id,
        label = text,
        action = KeyAction.InsertText(text),
        alternatives = alternatives,
        contentDescription = contentDescription
    )

    private fun actionKey(
        id: String,
        label: String,
        action: KeyAction,
        contentDescription: String,
        widthWeight: Float = 1f
    ): KeySpec = KeySpec(
        id = id,
        label = label,
        action = action,
        role = KeyRole.MODIFIER,
        widthWeight = widthWeight,
        contentDescription = contentDescription
    )

    private fun switchLayerKey(
        id: String,
        label: String,
        layer: KeyboardLayer,
        widthWeight: Float = 1.35f
    ): KeySpec = actionKey(
        id = id,
        label = label,
        action = KeyAction.SwitchLayer(layer),
        contentDescription = "Switch to ${layer.name.lowercase(Locale.ROOT)}",
        widthWeight = widthWeight
    )

    private fun backspaceKey(prefix: String): KeySpec = actionKey(
        id = "${prefix}_backspace",
        label = "⌫",
        action = KeyAction.Backspace,
        contentDescription = "Backspace",
        widthWeight = 1.35f
    )

    private fun spaceKey(id: String, widthWeight: Float): KeySpec = KeySpec(
        id = id,
        label = "space",
        action = KeyAction.Space,
        role = KeyRole.SPACE,
        widthWeight = widthWeight,
        contentDescription = "Space"
    )

    private fun enterKey(id: String): KeySpec = KeySpec(
        id = id,
        label = "↵",
        action = KeyAction.Enter,
        role = KeyRole.ACTION,
        widthWeight = 1.35f,
        contentDescription = "Enter"
    )

    private fun shiftLabel(state: ShiftState): String = when (state) {
        ShiftState.OFF -> "⇧"
        ShiftState.ONCE -> "⇧"
        ShiftState.CAPS_LOCK -> "⇪"
    }

    private fun shiftDescription(state: ShiftState): String = when (state) {
        ShiftState.OFF -> "Shift off"
        ShiftState.ONCE -> "Shift once"
        ShiftState.CAPS_LOCK -> "Caps lock"
    }

    private fun latinAlternatives(letter: Char): List<String> = when (letter) {
        'a' -> listOf("á", "à", "â", "ä", "ã", "å", "æ")
        'c' -> listOf("ç")
        'e' -> listOf("é", "è", "ê", "ë")
        'i' -> listOf("í", "ì", "î", "ï")
        'n' -> listOf("ñ")
        'o' -> listOf("ó", "ò", "ô", "ö", "õ", "ø", "œ")
        's' -> listOf("ß")
        'u' -> listOf("ú", "ù", "û", "ü")
        'y' -> listOf("ý", "ÿ")
        else -> emptyList()
    }

    private fun stableId(text: String): String =
        text.codePoints().toArray().joinToString("_") { it.toString(16) }
}

/**
 * Adapts the existing Taiwan-standard Zhuyin mapping to the shared key model.
 */
object ZhuyinLayoutAdapter {
    fun adapt(
        sourceRows: List<List<ZhuyinKey>> = ZhuyinComposer.STANDARD_KEYBOARD_ROWS
    ): List<KeyboardRow> {
        val phoneticRows = sourceRows.mapIndexed { rowIndex, row ->
            KeyboardRow(
                row.mapIndexed { columnIndex, key ->
                    val symbol = key.symbol.toString()
                    KeySpec(
                        id = "zhuyin_${rowIndex}_$columnIndex",
                        label = symbol,
                        action = KeyAction.InsertText(symbol),
                        contentDescription = "Zhuyin $symbol"
                    )
                }
            )
        }.toMutableList()

        phoneticRows += KeyboardRow(
            listOf(
                KeySpec(
                    id = "zhuyin_numbers",
                    label = "?123",
                    action = KeyAction.SwitchLayer(KeyboardLayer.NUMBERS),
                    role = KeyRole.MODIFIER,
                    widthWeight = 1.35f,
                    contentDescription = "Switch to numbers"
                ),
                KeySpec(
                    id = "zhuyin_comma",
                    label = "，",
                    action = KeyAction.InsertText("，"),
                    contentDescription = "Chinese comma"
                ),
                KeySpec(
                    id = "zhuyin_space",
                    label = "space",
                    action = KeyAction.Space,
                    role = KeyRole.SPACE,
                    widthWeight = 3.5f,
                    contentDescription = "Commit candidate or insert space"
                ),
                KeySpec(
                    id = "zhuyin_period",
                    label = "。",
                    action = KeyAction.InsertText("。"),
                    contentDescription = "Chinese period"
                ),
                KeySpec(
                    id = "zhuyin_backspace",
                    label = "⌫",
                    action = KeyAction.Backspace,
                    role = KeyRole.MODIFIER,
                    widthWeight = 1.35f,
                    contentDescription = "Backspace"
                ),
                KeySpec(
                    id = "zhuyin_enter",
                    label = "↵",
                    action = KeyAction.Enter,
                    role = KeyRole.ACTION,
                    widthWeight = 1.35f,
                    contentDescription = "Enter"
                )
            )
        )
        return phoneticRows
    }
}
