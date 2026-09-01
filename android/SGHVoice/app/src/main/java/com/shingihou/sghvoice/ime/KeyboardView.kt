package com.shingihou.sghvoice.ime

import android.annotation.SuppressLint
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Typeface
import android.graphics.drawable.InsetDrawable
import android.text.TextUtils
import android.util.AttributeSet
import android.view.HapticFeedbackConstants
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.View.OnAttachStateChangeListener
import android.widget.GridLayout
import android.widget.HorizontalScrollView
import android.widget.ImageButton
import android.widget.LinearLayout
import android.widget.PopupMenu
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.doOnAttach
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.core.widget.TextViewCompat
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.japanese.JapaneseScriptMode
import com.shingihou.sghvoice.ime.manual.KeyAction
import com.shingihou.sghvoice.ime.manual.KeyRole
import com.shingihou.sghvoice.ime.manual.KeySpec
import com.shingihou.sghvoice.ime.manual.KeyboardLayer
import com.shingihou.sghvoice.ime.manual.ManualKeyboardLayoutProvider
import com.shingihou.sghvoice.ime.manual.ManualKeyboardMode
import com.shingihou.sghvoice.ime.manual.ShiftState
import com.shingihou.sghvoice.processing.RecognitionLanguage
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationRequest

/**
 * SGH Voice 鍵盤視圖。
 *
 * 四種模式都留在同一個 Android IME subtype 內；View 只呈現鍵盤及回報
 * 語意化按鍵事件，組字、候選學習、錄音與 InputConnection 仍由 service 管理。
 */
class KeyboardView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : LinearLayout(context, attrs, defStyleAttr) {

    companion object {
        private const val MAX_RENDERED_CANDIDATES = 32
        private const val EXPANDED_CANDIDATE_COLUMNS = 3
    }

    enum class InputMode {
        VOICE,
        ZHUYIN,
        JAPANESE,
        ENGLISH
    }

    interface KeyboardActionListener {
        fun onMicToggle()
        fun onTranslationPickerRequested()
        fun onTranslationRequested(request: TranslationRequest)
        fun onRecognitionLanguageChanged(language: RecognitionLanguage)
        fun onInputModeChanged(mode: InputMode)
        fun onKeyAction(action: KeyAction)
        fun onCandidateSelected(candidate: String)
        fun onNextKeyboardPressed()
        fun onKeyboardPickerRequested()
    }

    private val layoutProvider = ManualKeyboardLayoutProvider()
    private var listener: KeyboardActionListener? = null
    private var inputMode = InputMode.VOICE
    private var keyboardLayer = KeyboardLayer.LETTERS
    private var shiftState = ShiftState.OFF
    private var japaneseScriptMode = JapaneseScriptMode.HIRAGANA
    private var recognitionLanguage = RecognitionLanguage.AUTO

    private lateinit var keyboardRoot: View
    private lateinit var voiceModeButton: TextView
    private lateinit var zhuyinModeButton: TextView
    private lateinit var japaneseModeButton: TextView
    private lateinit var englishModeButton: TextView
    private lateinit var nextKeyboardButton: ImageButton
    private lateinit var voicePanel: View
    private lateinit var manualPanel: View
    private lateinit var voiceActionRow: View
    private lateinit var micButton: TextView
    private lateinit var statusText: TextView
    private lateinit var voiceStateDot: View
    private lateinit var audioWaveform: AudioWaveformView
    private lateinit var voiceHint: TextView
    private lateinit var translationPanel: View
    private lateinit var translationCancelButton: TextView
    private lateinit var translationStartButton: TextView
    private lateinit var translationChipButtons: Map<TranslationLanguage, TextView>
    private val selectedTranslationTargets = linkedSetOf<TranslationLanguage>()
    private lateinit var compositionText: TextView
    private lateinit var candidateScroller: HorizontalScrollView
    private lateinit var candidateContainer: LinearLayout
    private lateinit var candidateExpandButton: ImageButton
    private lateinit var candidateExpandedPanel: View
    private lateinit var candidateGrid: GridLayout
    private lateinit var manualKeyRows: LinearLayout
    private lateinit var layerButton: TextView
    private lateinit var commaButton: TextView
    private lateinit var spaceButton: TextView
    private lateinit var periodButton: TextView
    private lateinit var backspaceButton: TextView
    private lateinit var enterButton: TextView
    private var latestCandidates: List<String> = emptyList()
    private var candidatesExpanded = false

    init {
        layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        LayoutInflater.from(context).inflate(R.layout.keyboard_view, this, true)
        bindViews()
        installNavigationBarInsets()
        bindActions()
        setInputMode(InputMode.VOICE)
        updateCandidates("", emptyList())
    }

    fun setKeyboardActionListener(listener: KeyboardActionListener) {
        this.listener = listener
    }

    fun setInputMode(mode: InputMode) {
        setCandidatesExpanded(false)
        hideTranslationPanel()
        inputMode = mode
        keyboardLayer = KeyboardLayer.LETTERS
        shiftState = ShiftState.OFF

        val isVoice = mode == InputMode.VOICE
        voicePanel.isVisible = isVoice
        voiceActionRow.isVisible = isVoice
        manualPanel.isVisible = !isVoice

        styleModeButton(voiceModeButton, mode == InputMode.VOICE)
        styleModeButton(zhuyinModeButton, mode == InputMode.ZHUYIN)
        styleModeButton(japaneseModeButton, mode == InputMode.JAPANESE)
        styleModeButton(englishModeButton, mode == InputMode.ENGLISH)

        if (isVoice) {
            configureVoiceActions()
        } else {
            compositionText.hint = context.getString(
                when (mode) {
                    InputMode.ZHUYIN -> R.string.zhuyin_composition_hint
                    InputMode.JAPANESE -> R.string.japanese_composition_hint
                    InputMode.ENGLISH -> R.string.english_composition_hint
                    InputMode.VOICE -> R.string.zhuyin_composition_hint
                }
            )
            renderManualKeyboard()
        }
        renderVoiceModeLabel()
    }

    fun setRecognitionLanguage(language: RecognitionLanguage) {
        recognitionLanguage = language
        renderVoiceModeLabel()
    }

    fun setManualKeyboardState(
        layer: KeyboardLayer = keyboardLayer,
        shift: ShiftState = shiftState
    ) {
        if (layer == keyboardLayer && shift == shiftState) return
        keyboardLayer = layer
        shiftState = shift
        if (inputMode != InputMode.VOICE) renderManualKeyboard()
    }

    fun setJapaneseScriptMode(mode: JapaneseScriptMode) {
        if (japaneseScriptMode == mode) return
        japaneseScriptMode = mode
        if (inputMode == InputMode.JAPANESE && keyboardLayer == KeyboardLayer.LETTERS) {
            renderManualKeyboard()
        }
    }

    fun setStatusText(text: String) {
        statusText.text = text
    }

    fun setRecordingElapsed(formattedElapsed: String, translating: Boolean = false) {
        statusText.text = context.getString(
            if (translating) {
                R.string.status_translation_recording_elapsed
            } else {
                R.string.status_recording_elapsed
            },
            formattedElapsed
        )
    }

    fun setAudioLevel(level: Float) {
        audioWaveform.setAudioLevel(level)
    }

    fun setTranslationRecordingMode() {
        micButton.setText(R.string.mic_action_translation_recording)
        micButton.contentDescription =
            context.getString(R.string.translation_recording_mic_desc)
    }

    fun showTranslationPanel(targets: List<TranslationLanguage>) {
        selectedTranslationTargets.clear()
        selectedTranslationTargets.addAll(
            runCatching { TranslationRequest.create(targets).targets }
                .getOrDefault(listOf(TranslationLanguage.JAPANESE))
        )
        renderTranslationTargets()
        micButton.isVisible = false
        translationPanel.isVisible = true
        voiceHint.isVisible = false
        statusText.setText(R.string.translation_picker_status)
        translationPanel.announceForAccessibility(
            context.getString(R.string.translation_picker_accessibility)
        )
    }

    fun hideTranslationPanel() {
        if (!::translationPanel.isInitialized) return
        translationPanel.isVisible = false
        micButton.isVisible = true
        voiceHint.isVisible = true
    }

    fun updateCandidates(composition: String, candidates: List<String>) {
        compositionText.text = composition
        compositionText.isVisible = composition.isNotBlank()
        latestCandidates = candidates
            .asSequence()
            .filter { it.isNotBlank() }
            .distinct()
            .take(MAX_RENDERED_CANDIDATES)
            .toList()
        candidateContainer.removeAllViews()
        candidateGrid.removeAllViews()
        candidateScroller.scrollTo(0, 0)

        if (composition.isBlank() && latestCandidates.isEmpty()) {
            candidateExpandButton.isVisible = false
            setCandidatesExpanded(false)
            candidateContainer.addView(createCandidateMessage(R.string.candidate_ready_hint))
            return
        }

        if (composition.isNotBlank() && latestCandidates.isEmpty()) {
            candidateExpandButton.isVisible = false
            setCandidatesExpanded(false)
            candidateContainer.addView(createCandidateMessage(R.string.zhuyin_no_candidates))
            return
        }

        latestCandidates.forEachIndexed { index, candidate ->
            candidateContainer.addView(createCandidateButton(candidate, primary = index == 0))
            candidateGrid.addView(
                createCandidateButton(
                    candidate,
                    primary = index == 0,
                    gridIndex = index
                )
            )
        }

        val renderedSnapshot = latestCandidates
        candidateScroller.post {
            if (latestCandidates != renderedSnapshot) return@post
            val hasOverflow =
                candidateContainer.measuredWidth > candidateScroller.measuredWidth
            candidateExpandButton.isVisible =
                hasOverflow || renderedSnapshot.size > EXPANDED_CANDIDATE_COLUMNS
            if (!candidateExpandButton.isVisible) setCandidatesExpanded(false)
        }
    }

    fun updateState(state: VoiceInputIME.ImeState) {
        when (state) {
            VoiceInputIME.ImeState.IDLE -> {
                audioWaveform.setRecordingActive(false)
                statusText.setText(R.string.status_idle)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = true,
                    colorRes = R.color.mic_bg,
                    labelRes = R.string.mic_action_start,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_idle
                )
            }

            VoiceInputIME.ImeState.STARTING -> {
                audioWaveform.setRecordingActive(true)
                audioWaveform.setAudioLevel(0f)
                statusText.setText(R.string.status_starting)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = false,
                    colorRes = R.color.mic_bg_processing,
                    labelRes = R.string.mic_action_processing,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_processing
                )
            }

            VoiceInputIME.ImeState.RECORDING -> {
                audioWaveform.setRecordingActive(true)
                statusText.setText(R.string.status_recording)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_recording))
                applyMicState(
                    enabled = true,
                    colorRes = R.color.mic_bg_recording,
                    labelRes = R.string.mic_action_recording,
                    iconRes = R.drawable.ic_stop,
                    dotColorRes = R.color.status_dot_recording
                )
            }

            VoiceInputIME.ImeState.STOPPING -> {
                audioWaveform.setRecordingActive(false)
                statusText.setText(R.string.status_stopping)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = false,
                    colorRes = R.color.mic_bg_processing,
                    labelRes = R.string.mic_action_processing,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_processing
                )
            }

            VoiceInputIME.ImeState.PROCESSING -> {
                audioWaveform.setRecordingActive(false)
                statusText.setText(R.string.status_processing)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = false,
                    colorRes = R.color.mic_bg_processing,
                    labelRes = R.string.mic_action_processing,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_processing
                )
            }

            VoiceInputIME.ImeState.DONE -> {
                audioWaveform.setRecordingActive(false)
                statusText.setText(R.string.status_done)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_success))
                applyMicState(
                    enabled = true,
                    colorRes = R.color.mic_bg,
                    labelRes = R.string.mic_action_start,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_success
                )
            }

            VoiceInputIME.ImeState.ERROR -> {
                audioWaveform.setRecordingActive(false)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_recording))
                applyMicState(
                    enabled = true,
                    colorRes = R.color.mic_bg,
                    labelRes = R.string.mic_action_start,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_recording
                )
            }
        }
    }

    private fun bindViews() {
        keyboardRoot = findViewById(R.id.keyboard_root)
        voiceModeButton = findViewById(R.id.btn_mode_voice)
        zhuyinModeButton = findViewById(R.id.btn_mode_zhuyin)
        japaneseModeButton = findViewById(R.id.btn_mode_japanese)
        englishModeButton = findViewById(R.id.btn_mode_english)
        nextKeyboardButton = findViewById(R.id.btn_next_keyboard)
        voicePanel = findViewById(R.id.panel_voice)
        manualPanel = findViewById(R.id.panel_manual)
        voiceActionRow = findViewById(R.id.voice_action_row)
        micButton = findViewById(R.id.btn_mic)
        statusText = findViewById(R.id.tv_status)
        voiceStateDot = findViewById(R.id.voice_state_dot)
        audioWaveform = findViewById(R.id.audio_waveform)
        voiceHint = findViewById(R.id.tv_voice_hint)
        translationPanel = findViewById(R.id.translation_panel)
        translationCancelButton = findViewById(R.id.btn_translation_cancel)
        translationStartButton = findViewById(R.id.btn_translation_start)
        translationChipButtons = linkedMapOf(
            TranslationLanguage.TRADITIONAL_CHINESE to
                findViewById(R.id.chip_translation_zh_hant),
            TranslationLanguage.JAPANESE to findViewById(R.id.chip_translation_ja),
            TranslationLanguage.ENGLISH to findViewById(R.id.chip_translation_en),
            TranslationLanguage.KOREAN to findViewById(R.id.chip_translation_ko)
        )
        compositionText = findViewById(R.id.tv_composition)
        candidateScroller = findViewById(R.id.candidate_scroller)
        candidateContainer = findViewById(R.id.candidate_container)
        candidateExpandButton = findViewById(R.id.btn_expand_candidates)
        candidateExpandedPanel = findViewById(R.id.candidate_expanded_panel)
        candidateGrid = findViewById(R.id.candidate_grid)
        manualKeyRows = findViewById(R.id.manual_key_rows)
        layerButton = findViewById(R.id.btn_layer)
        commaButton = findViewById(R.id.btn_comma)
        spaceButton = findViewById(R.id.btn_space)
        periodButton = findViewById(R.id.btn_period)
        backspaceButton = findViewById(R.id.btn_backspace)
        enterButton = findViewById(R.id.btn_enter)
    }

    private fun installNavigationBarInsets() {
        val baseBottomPadding = keyboardRoot.paddingBottom
        ViewCompat.setOnApplyWindowInsetsListener(this) { _, windowInsets ->
            val navigationBarBottom = windowInsets
                .getInsets(WindowInsetsCompat.Type.navigationBars())
                .bottom
            keyboardRoot.updatePadding(bottom = baseBottomPadding + navigationBarBottom)
            windowInsets
        }
        doOnAttach { ViewCompat.requestApplyInsets(it) }
    }

    private fun bindActions() {
        bindModeButton(voiceModeButton, InputMode.VOICE)
        bindModeButton(zhuyinModeButton, InputMode.ZHUYIN)
        bindModeButton(japaneseModeButton, InputMode.JAPANESE)
        bindModeButton(englishModeButton, InputMode.ENGLISH)

        nextKeyboardButton.setOnClickListener {
            hapticTap(it)
            listener?.onNextKeyboardPressed()
        }
        nextKeyboardButton.setOnLongClickListener {
            it.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            listener?.onKeyboardPickerRequested()
            true
        }
        candidateExpandButton.setOnClickListener {
            hapticTap(it)
            setCandidatesExpanded(!candidatesExpanded)
        }
        micButton.setOnClickListener {
            hapticTap(it)
            hideTranslationPanel()
            listener?.onMicToggle()
        }
        micButton.setOnLongClickListener {
            if (!it.isEnabled) return@setOnLongClickListener false
            it.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
            listener?.onTranslationPickerRequested()
            true
        }
        translationChipButtons.forEach { (language, button) ->
            button.setOnClickListener {
                hapticTap(it)
                if (!selectedTranslationTargets.remove(language)) {
                    selectedTranslationTargets.add(language)
                }
                renderTranslationTargets()
            }
        }
        translationCancelButton.setOnClickListener {
            hapticTap(it)
            hideTranslationPanel()
            updateState(VoiceInputIME.ImeState.IDLE)
        }
        translationStartButton.setOnClickListener {
            if (selectedTranslationTargets.isEmpty()) return@setOnClickListener
            hapticTap(it)
            val request = TranslationRequest.create(selectedTranslationTargets)
            hideTranslationPanel()
            listener?.onTranslationRequested(request)
        }
        layerButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.InsertText("@")) }
        commaButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.InsertText("，")) }
        spaceButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.Space) }
        periodButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.InsertText("。")) }
        backspaceButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.Backspace) }
        installRepeatingBackspace(backspaceButton)
        enterButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.Enter) }
    }

    private fun bindModeButton(button: TextView, mode: InputMode) {
        button.setOnClickListener {
            if (mode == InputMode.VOICE && mode == inputMode) {
                hapticTap(it)
                showRecognitionLanguageMenu(it)
                return@setOnClickListener
            }
            if (mode == inputMode) return@setOnClickListener
            hapticTap(it)
            listener?.onInputModeChanged(mode)
        }
    }

    private fun dispatchVoiceAction(view: View, action: KeyAction) {
        hapticTap(view)
        listener?.onKeyAction(action)
    }

    private fun configureVoiceActions() {
        layerButton.text = "@"
        commaButton.text = "，"
        periodButton.text = "。"
    }

    private fun renderVoiceModeLabel() {
        if (!::voiceModeButton.isInitialized) return
        if (inputMode == InputMode.VOICE) {
            voiceModeButton.setText(recognitionLanguageShortLabel(recognitionLanguage))
            voiceModeButton.contentDescription = context.getString(
                R.string.recognition_language_button_desc,
                context.getString(recognitionLanguageLabel(recognitionLanguage))
            )
        } else {
            voiceModeButton.setText(R.string.mode_voice)
            voiceModeButton.setContentDescription(
                context.getString(R.string.mode_voice_desc)
            )
        }
    }

    private fun showRecognitionLanguageMenu(anchor: View) {
        PopupMenu(context, anchor).apply {
            RecognitionLanguage.entries.forEach { language ->
                menu.add(
                    R.id.group_recognition_language,
                    language.ordinal,
                    language.ordinal,
                    recognitionLanguageLabel(language)
                ).apply {
                    isCheckable = true
                    isChecked = language == recognitionLanguage
                }
            }
            menu.setGroupCheckable(R.id.group_recognition_language, true, true)
            setOnMenuItemClickListener { item ->
                val language = RecognitionLanguage.entries.getOrNull(item.itemId)
                    ?: return@setOnMenuItemClickListener false
                listener?.onRecognitionLanguageChanged(language)
                true
            }
            show()
        }
    }

    private fun recognitionLanguageLabel(language: RecognitionLanguage): Int =
        when (language) {
            RecognitionLanguage.AUTO -> R.string.recognition_language_auto
            RecognitionLanguage.TRADITIONAL_CHINESE ->
                R.string.recognition_language_traditional_chinese
            RecognitionLanguage.JAPANESE -> R.string.recognition_language_japanese
            RecognitionLanguage.ENGLISH -> R.string.recognition_language_english
            RecognitionLanguage.KOREAN -> R.string.recognition_language_korean
        }

    private fun recognitionLanguageShortLabel(language: RecognitionLanguage): Int =
        when (language) {
            RecognitionLanguage.AUTO -> R.string.recognition_language_auto_short
            RecognitionLanguage.TRADITIONAL_CHINESE ->
                R.string.recognition_language_traditional_chinese_short
            RecognitionLanguage.JAPANESE -> R.string.recognition_language_japanese_short
            RecognitionLanguage.ENGLISH -> R.string.recognition_language_english_short
            RecognitionLanguage.KOREAN -> R.string.recognition_language_korean_short
        }

    private fun renderTranslationTargets() {
        translationChipButtons.forEach { (language, button) ->
            val selected = language in selectedTranslationTargets
            styleModeButton(button, selected)
            button.contentDescription = context.getString(
                if (selected) {
                    R.string.translation_target_selected_desc
                } else {
                    R.string.translation_target_unselected_desc
                },
                button.text
            )
        }
        val hasSelection = selectedTranslationTargets.isNotEmpty()
        translationStartButton.isEnabled = hasSelection
        translationStartButton.alpha = if (hasSelection) 1f else 0.45f
    }

    private fun renderManualKeyboard() {
        val manualMode = when (inputMode) {
            InputMode.ZHUYIN -> ManualKeyboardMode.ZHUYIN
            InputMode.JAPANESE -> ManualKeyboardMode.JAPANESE
            InputMode.ENGLISH -> ManualKeyboardMode.ENGLISH
            InputMode.VOICE -> return
        }
        val layout = layoutProvider.layout(manualMode, keyboardLayer, shiftState)
        manualKeyRows.removeAllViews()
        layout.rows.forEachIndexed { rowIndex, row ->
            val rowView = LinearLayout(context).apply {
                orientation = HORIZONTAL
                gravity = android.view.Gravity.CENTER
                layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, dp(48))
                val horizontalInset = when {
                    manualMode == ManualKeyboardMode.ZHUYIN ||
                        keyboardLayer != KeyboardLayer.LETTERS -> 0
                    rowIndex == 1 -> dp(14)
                    rowIndex == 2 -> dp(2)
                    else -> 0
                }
                setPadding(horizontalInset, 0, horizontalInset, 0)
            }
            row.keys.forEach { key -> rowView.addView(createKeyButton(key)) }
            manualKeyRows.addView(rowView)
        }
    }

    private fun createKeyButton(key: KeySpec): TextView {
        return TextView(context).apply {
            val displayLabel = when {
                key.role == KeyRole.SPACE -> context.getString(R.string.key_space)
                key.id == "japanese_script" &&
                    japaneseScriptMode == JapaneseScriptMode.HIRAGANA -> "カナ"
                key.id == "japanese_script" -> "かな"
                else -> key.label
            }
            text = displayLabel
            contentDescription = key.contentDescription
            gravity = android.view.Gravity.CENTER
            includeFontPadding = false
            maxLines = 1
            textSize = when {
                displayLabel.length > 4 -> 12f
                key.role == KeyRole.CHARACTER -> 18f
                else -> 13f
            }
            val isActiveModifier =
                key.action == KeyAction.Shift && shiftState != ShiftState.OFF
            val backgroundRes = when {
                key.role == KeyRole.ACTION -> R.drawable.key_enter_bg
                isActiveModifier -> R.drawable.key_active_bg
                key.role == KeyRole.MODIFIER -> R.drawable.key_special_bg
                else -> R.drawable.key_bg
            }
            val textColorRes = if (key.role == KeyRole.ACTION || isActiveModifier) {
                R.color.key_text_enter
            } else {
                R.color.key_text
            }
            setTextColor(ContextCompat.getColor(context, textColorRes))
            background = InsetDrawable(
                ContextCompat.getDrawable(context, backgroundRes),
                dp(2),
                dp(2),
                dp(2),
                dp(2)
            )
            setTypeface(
                Typeface.create(
                    "sans-serif",
                    if (key.role == KeyRole.CHARACTER) Typeface.NORMAL else Typeface.BOLD
                )
            )
            layoutParams = LayoutParams(0, dp(48), key.widthWeight)
            setOnClickListener {
                hapticTap(it)
                when (val action = key.action) {
                    is KeyAction.SwitchLayer -> {
                        keyboardLayer = action.layer
                        shiftState = ShiftState.OFF
                        renderManualKeyboard()
                    }

                    KeyAction.Shift -> {
                        if (inputMode == InputMode.JAPANESE) {
                            shiftState = when (shiftState) {
                                ShiftState.OFF -> ShiftState.ONCE
                                ShiftState.ONCE -> ShiftState.CAPS_LOCK
                                ShiftState.CAPS_LOCK -> ShiftState.OFF
                            }
                            renderManualKeyboard()
                        } else {
                            listener?.onKeyAction(action)
                        }
                    }

                    else -> {
                        listener?.onKeyAction(action)
                        if (inputMode == InputMode.JAPANESE &&
                            action is KeyAction.InsertText &&
                            shiftState == ShiftState.ONCE
                        ) {
                            shiftState = ShiftState.OFF
                            renderManualKeyboard()
                        }
                    }
                }
            }
            if (key.action == KeyAction.Backspace) {
                installRepeatingBackspace(this)
            } else if (key.alternatives.isNotEmpty()) {
                setOnLongClickListener {
                    showAlternatives(this, key.alternatives)
                    true
                }
            }
        }
    }

    private fun showAlternatives(anchor: View, alternatives: List<String>) {
        PopupMenu(context, anchor).apply {
            alternatives.forEachIndexed { index, value ->
                menu.add(0, index, index, value)
            }
            setOnMenuItemClickListener { item ->
                val value = alternatives.getOrNull(item.itemId) ?: return@setOnMenuItemClickListener false
                listener?.onKeyAction(KeyAction.InsertText(value))
                true
            }
            show()
        }
    }

    private fun createCandidateMessage(messageRes: Int): TextView =
        TextView(context).apply {
            setText(messageRes)
            setTextColor(ContextCompat.getColor(context, R.color.keyboard_muted_text))
            textSize = 13f
            gravity = android.view.Gravity.CENTER_VERTICAL
            ellipsize = TextUtils.TruncateAt.END
            maxLines = 1
            setPadding(dp(10), 0, dp(10), 0)
            layoutParams = LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.MATCH_PARENT)
        }

    private fun createCandidateButton(
        candidate: String,
        primary: Boolean,
        gridIndex: Int? = null
    ): TextView {
        return TextView(context).apply {
            text = candidate
            contentDescription = context.getString(
                R.string.candidate_content_description,
                candidate
            )
            gravity = android.view.Gravity.CENTER
            includeFontPadding = false
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
            minWidth = dp(48)
            textSize = if (candidate.length > 2) 17f else 20f
            setTextColor(
                ContextCompat.getColor(
                    context,
                    if (primary) R.color.candidate_primary_text else R.color.candidate_text
                )
            )
            setTypeface(null, if (primary) Typeface.BOLD else Typeface.NORMAL)
            background = ContextCompat.getDrawable(
                context,
                if (primary) R.drawable.candidate_primary_bg else R.drawable.candidate_bg
            )
            setPadding(dp(12), 0, dp(12), 0)
            layoutParams = if (gridIndex == null) {
                LayoutParams(LayoutParams.WRAP_CONTENT, dp(44)).apply {
                    marginStart = dp(3)
                    marginEnd = dp(3)
                }
            } else {
                GridLayout.LayoutParams(
                    GridLayout.spec(gridIndex / EXPANDED_CANDIDATE_COLUMNS),
                    GridLayout.spec(gridIndex % EXPANDED_CANDIDATE_COLUMNS, 1f)
                ).apply {
                    width = 0
                    height = dp(44)
                    setMargins(dp(3), dp(3), dp(3), dp(3))
                }
            }
            setOnClickListener {
                hapticTap(it)
                setCandidatesExpanded(false)
                listener?.onCandidateSelected(candidate)
            }
        }
    }

    private fun setCandidatesExpanded(expanded: Boolean) {
        val shouldExpand =
            expanded && latestCandidates.isNotEmpty() && candidateExpandButton.isVisible
        candidatesExpanded = shouldExpand
        if (shouldExpand && manualKeyRows.height > 0) {
            candidateExpandedPanel.layoutParams =
                candidateExpandedPanel.layoutParams.apply {
                    height = manualKeyRows.height
                }
        }
        candidateScroller.visibility = if (shouldExpand) View.INVISIBLE else View.VISIBLE
        candidateExpandedPanel.isVisible = shouldExpand
        manualKeyRows.isVisible = !shouldExpand
        candidateExpandButton.setImageResource(
            if (shouldExpand) R.drawable.ic_expand_less else R.drawable.ic_expand_more
        )
        candidateExpandButton.contentDescription = context.getString(
            if (shouldExpand) {
                R.string.candidate_collapse_desc
            } else {
                R.string.candidate_expand_desc
            }
        )
    }

    private fun styleModeButton(button: TextView, selected: Boolean) {
        button.background = if (selected) {
            ContextCompat.getDrawable(context, R.drawable.mode_selected_bg)
        } else {
            ContextCompat.getDrawable(context, R.drawable.mode_unselected_bg)
        }
        button.setTextColor(
            ContextCompat.getColor(
                context,
                if (selected) R.color.keyboard_selected_text else R.color.keyboard_muted_text
            )
        )
        button.typeface = Typeface.create("sans-serif-medium", Typeface.NORMAL)
        button.isSelected = selected
    }

    @SuppressLint("ClickableViewAccessibility")
    private fun installRepeatingBackspace(button: TextView) {
        var repeatCount = 0
        var isRepeating = false
        val repeatAction = object : Runnable {
            override fun run() {
                if (!button.isPressed || !button.isAttachedToWindow) return
                if (!isRepeating) {
                    isRepeating = true
                    button.performHapticFeedback(HapticFeedbackConstants.LONG_PRESS)
                }
                listener?.onKeyAction(KeyAction.Backspace)
                repeatCount += 1
                button.postDelayed(
                    this,
                    BackspaceRepeatPolicy.intervalAfter(repeatCount)
                )
            }
        }

        fun stopRepeating() {
            button.removeCallbacks(repeatAction)
            repeatCount = 0
            isRepeating = false
        }

        button.setOnTouchListener { view, event ->
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    stopRepeating()
                    view.isPressed = true
                    button.postDelayed(
                        repeatAction,
                        BackspaceRepeatPolicy.INITIAL_DELAY_MS
                    )
                    true
                }

                MotionEvent.ACTION_UP -> {
                    val repeated = isRepeating
                    stopRepeating()
                    view.isPressed = false
                    if (!repeated) view.performClick()
                    true
                }

                MotionEvent.ACTION_CANCEL,
                MotionEvent.ACTION_OUTSIDE -> {
                    stopRepeating()
                    view.isPressed = false
                    true
                }

                else -> true
            }
        }
        button.addOnAttachStateChangeListener(object : OnAttachStateChangeListener {
            override fun onViewAttachedToWindow(view: View) = Unit

            override fun onViewDetachedFromWindow(view: View) {
                stopRepeating()
            }
        })
    }

    private fun applyMicState(
        enabled: Boolean,
        colorRes: Int,
        labelRes: Int,
        iconRes: Int,
        dotColorRes: Int
    ) {
        micButton.isEnabled = enabled
        micButton.alpha = 1f
        micButton.setText(labelRes)
        micButton.contentDescription = context.getString(labelRes)
        micButton.setCompoundDrawablesRelativeWithIntrinsicBounds(iconRes, 0, 0, 0)
        TextViewCompat.setCompoundDrawableTintList(
            micButton,
            ColorStateList.valueOf(
                ContextCompat.getColor(context, R.color.mic_icon)
            )
        )
        micButton.backgroundTintList = ColorStateList.valueOf(
            ContextCompat.getColor(context, colorRes)
        )
        ViewCompat.setBackgroundTintList(
            voiceStateDot,
            ColorStateList.valueOf(ContextCompat.getColor(context, dotColorRes))
        )
    }

    private fun hapticTap(view: View) {
        view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
    }

    private fun dp(value: Int): Int = (value * resources.displayMetrics.density).toInt()
}
