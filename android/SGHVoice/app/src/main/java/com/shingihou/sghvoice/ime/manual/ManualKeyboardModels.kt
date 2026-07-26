package com.shingihou.sghvoice.ime.manual

/**
 * Manual modes rendered inside the single SGH Voice system IME.
 *
 * Voice deliberately is not included here because it does not use a key grid.
 */
enum class ManualKeyboardMode {
    ZHUYIN,
    JAPANESE,
    ENGLISH
}

/**
 * The visible key layer is independent from the selected language.
 *
 * This lets English and Japanese share QWERTY as well as the numeric/symbol
 * layouts, while Zhuyin can still switch to the same utility layers.
 */
enum class KeyboardLayer {
    LETTERS,
    NUMBERS,
    SYMBOLS
}

enum class ShiftState {
    OFF,
    ONCE,
    CAPS_LOCK
}

enum class KeyRole {
    CHARACTER,
    MODIFIER,
    SPACE,
    ACTION
}

sealed class KeyAction {
    data class InsertText(val text: String) : KeyAction()
    data class SwitchLayer(val layer: KeyboardLayer) : KeyAction()

    object Backspace : KeyAction()
    object Enter : KeyAction()
    object Shift : KeyAction()
    object Space : KeyAction()
    object ToggleJapaneseScript : KeyAction()
}

/**
 * Platform-neutral key description consumed by the Android View layer.
 *
 * [minTouchTargetDp] is metadata rather than an Android `Dp`, keeping this
 * model JVM-testable. The renderer remains responsible for measuring the
 * actual View and must never make it smaller than this value.
 */
data class KeySpec(
    val id: String,
    val label: String,
    val action: KeyAction,
    val role: KeyRole = KeyRole.CHARACTER,
    val widthWeight: Float = 1f,
    val alternatives: List<String> = emptyList(),
    val contentDescription: String = label,
    val minTouchTargetDp: Int = MIN_TOUCH_TARGET_DP
) {
    init {
        require(id.isNotBlank()) { "A key id cannot be blank." }
        require(label.isNotEmpty()) { "A key label cannot be empty." }
        require(widthWeight > 0f) { "A key width weight must be positive." }
        require(minTouchTargetDp >= MIN_TOUCH_TARGET_DP) {
            "A key touch target must be at least $MIN_TOUCH_TARGET_DP dp."
        }
    }

    companion object {
        const val MIN_TOUCH_TARGET_DP = 44
    }
}

data class KeyboardRow(
    val keys: List<KeySpec>
) {
    init {
        require(keys.isNotEmpty()) { "A keyboard row cannot be empty." }
    }
}

data class ManualKeyboardLayout(
    val mode: ManualKeyboardMode,
    val layer: KeyboardLayer,
    val rows: List<KeyboardRow>,
    val shiftState: ShiftState = ShiftState.OFF
) {
    init {
        require(rows.isNotEmpty()) { "A keyboard layout cannot be empty." }
    }
}
