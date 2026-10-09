package com.shingihou.sghvoice.ime

import android.annotation.SuppressLint
import android.content.Context
import android.content.res.ColorStateList
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.ColorFilter
import android.graphics.Paint
import android.graphics.PixelFormat
import android.graphics.Typeface
import android.graphics.drawable.Drawable
import android.graphics.drawable.InsetDrawable
import android.graphics.drawable.GradientDrawable
import android.graphics.drawable.RippleDrawable
import android.graphics.drawable.StateListDrawable
import android.text.SpannableString
import android.text.Spanned
import android.text.TextUtils
import android.text.style.ReplacementSpan
import android.util.AttributeSet
import android.util.TypedValue
import android.view.HapticFeedbackConstants
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.ViewGroup
import android.view.View.OnAttachStateChangeListener
import android.widget.GridLayout
import android.widget.FrameLayout
import android.widget.HorizontalScrollView
import android.widget.ImageButton
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.PopupMenu
import android.widget.TextView
import androidx.core.content.ContextCompat
import androidx.core.graphics.ColorUtils
import androidx.core.view.AccessibilityDelegateCompat
import androidx.core.view.ViewCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.doOnAttach
import androidx.core.view.isVisible
import androidx.core.view.updatePadding
import androidx.core.view.accessibility.AccessibilityNodeInfoCompat
import androidx.core.widget.NestedScrollView
import androidx.core.widget.TextViewCompat
import com.shingihou.sghvoice.R
import com.shingihou.sghvoice.ime.japanese.JapaneseScriptMode
import com.shingihou.sghvoice.ime.japanese.JapaneseInputStyle
import com.shingihou.sghvoice.ime.japanese.KanaFlickKeyView
import com.shingihou.sghvoice.ime.manual.KeyAction
import com.shingihou.sghvoice.ime.manual.EmojiPalette
import com.shingihou.sghvoice.ime.manual.KeyRole
import com.shingihou.sghvoice.ime.manual.KeySpec
import com.shingihou.sghvoice.ime.manual.KeyboardLayer
import com.shingihou.sghvoice.ime.manual.ManualKeyboardLayoutProvider
import com.shingihou.sghvoice.ime.manual.ManualKeyboardMode
import com.shingihou.sghvoice.ime.manual.ShiftState
import com.shingihou.sghvoice.processing.RecognitionLanguage
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationRequest
import java.util.Locale

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
        private const val MAX_RENDERED_CANDIDATES = 48
        private const val EXPANDED_CANDIDATE_COLUMNS = 3
        private const val ZHUYIN_EXPANDED_CANDIDATE_COLUMNS = 2
    }

    enum class InputMode {
        VOICE,
        ZHUYIN,
        JAPANESE,
        ENGLISH
    }

    enum class VoiceActionMode { DICTATION, COMPOSE }

    interface KeyboardActionListener {
        fun onMicToggle()
        fun onVoiceActionModeChanged(mode: VoiceActionMode)
        fun onComposeContinue()
        fun onComposeGenerate()
        fun onComposeOrganize() {}
        fun onComposeClear()
        fun onPendingInsert()
        fun onPendingDiscard()
        fun onPendingRetry()
        fun onDraftPreviewRequested()
        fun onTranslationPickerRequested()
        fun onTranslationRequested(request: TranslationRequest)
        fun onRecognitionLanguageChanged(language: RecognitionLanguage)
        fun onInputModeChanged(mode: InputMode)
        fun onKeyAction(action: KeyAction)
        fun onCandidateSelected(candidate: String)
        fun onNextKeyboardPressed()
        fun onKeyboardPickerRequested()
        fun onZhuyinReselectRequested() {}
    }

    private val layoutProvider = ManualKeyboardLayoutProvider()
    private var listener: KeyboardActionListener? = null
    private var inputMode = InputMode.VOICE
    private var keyboardLayer = KeyboardLayer.LETTERS
    private var shiftState = ShiftState.OFF
    private var japaneseScriptMode = JapaneseScriptMode.HIRAGANA
    private var japaneseInputStyle = JapaneseInputStyle.ROMAJI
    private var voiceActionMode = VoiceActionMode.DICTATION
    private var hasComposeNotes = false
    private var hasPendingDraft = false
    private var retryAvailable = false
    private var draftPreviewShown = false
    private var voicePalette = VoicePalette.MINT.argb
    private var keyboardHeightPercent = KeyboardSizing.DEFAULT_PERCENT
    private var currentVoiceState = VoiceInputIME.ImeState.IDLE
    private var recognitionLanguage = RecognitionLanguage.AUTO

    private lateinit var keyboardRoot: View
    private lateinit var contentScroll: NestedScrollView
    private lateinit var captureArea: View
    private lateinit var draftPreviewPanel: View
    private lateinit var draftPreviewText: TextView
    private lateinit var draftPreviewButton: TextView
    private lateinit var draftPreviewCloseButton: TextView
    private lateinit var voiceModeButton: TextView
    private lateinit var zhuyinModeButton: TextView
    private lateinit var japaneseModeButton: TextView
    private lateinit var englishModeButton: TextView
    private lateinit var nextKeyboardButton: ImageButton
    private lateinit var voicePanel: View
    private lateinit var manualPanel: View
    private lateinit var voiceActionRow: View
    private lateinit var micButton: View
    private lateinit var micOuterRing: View
    private lateinit var micActionLabel: TextView
    private lateinit var micActionIcon: ImageView
    private lateinit var statusText: TextView
    private lateinit var voiceStateDot: View
    private lateinit var audioWaveform: AudioWaveformView
    private lateinit var voiceTaskSwitch: LinearLayout
    private lateinit var dictationTaskButton: TextView
    private lateinit var composeTaskButton: TextView
    private lateinit var composeActionRow: View
    private lateinit var composeContinueButton: TextView
    private lateinit var composeGenerateButton: TextView
    private lateinit var composeClearButton: TextView
    private lateinit var pendingInsertRow: View
    private lateinit var pendingInsertButton: TextView
    private lateinit var pendingDiscardButton: TextView
    private lateinit var translationPanel: View
    private lateinit var translationCancelButton: TextView
    private lateinit var translationStartButton: TextView
    private lateinit var translationChipButtons: Map<TranslationLanguage, TextView>
    private val selectedTranslationTargets = linkedSetOf<TranslationLanguage>()
    private lateinit var compositionText: TextView
    private lateinit var compositionSummary: HorizontalScrollView
    private lateinit var compositionSummaryContent: FrameLayout
    private lateinit var inputStrip: LinearLayout
    private lateinit var manualCandidateHeader: LinearLayout
    private lateinit var zhuyinReselectButton: TextView
    private var zhuyinReselectAvailable = false
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
    private var emojiPanelVisible = false
    private var emojiPage = 0

    init {
        layoutParams = LayoutParams(LayoutParams.MATCH_PARENT, LayoutParams.WRAP_CONTENT)
        LayoutInflater.from(context).inflate(R.layout.keyboard_view, this, true)
        bindViews()
        installNavigationBarInsets()
        bindActions()
        setInputMode(InputMode.VOICE)
        setVoiceActionMode(voiceActionMode)
        updateCandidates("", emptyList())
    }

    fun setKeyboardActionListener(listener: KeyboardActionListener) {
        this.listener = listener
    }

    fun setKeyboardHeightPercent(percent: Int) {
        val normalized = KeyboardSizing.normalize(percent)
        if (keyboardHeightPercent == normalized) return
        keyboardHeightPercent = normalized
        requestLayout()
    }

    private fun updateTouchSplitting(group: ViewGroup) {
        // Only flick needs a single gesture owner. Keep normal overlapping QWERTY taps.
        group.isMotionEventSplittingEnabled = emojiPanelVisible || inputMode != InputMode.JAPANESE ||
            japaneseInputStyle != JapaneseInputStyle.KANA_12_KEY || keyboardLayer != KeyboardLayer.LETTERS
        for (index in 0 until group.childCount) {
            (group.getChildAt(index) as? ViewGroup)?.let(::updateTouchSplitting)
        }
    }

    fun setInputMode(mode: InputMode) {
        emojiPanelVisible = false
        candidateExpandButton.isEnabled = true
        setCandidatesExpanded(false)
        hideTranslationPanel()
        inputMode = mode
        renderCompositionLayout()
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
        renderDraftActions()
        renderEmojiButton()
        updateTouchSplitting(this)
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
        if (inputMode != InputMode.VOICE || emojiPanelVisible) renderManualKeyboard()
    }

    fun setJapaneseScriptMode(mode: JapaneseScriptMode) {
        if (japaneseScriptMode == mode) return
        japaneseScriptMode = mode
        if (inputMode == InputMode.JAPANESE && keyboardLayer == KeyboardLayer.LETTERS) {
            renderManualKeyboard()
        }
    }

    fun setJapaneseInputStyle(style: JapaneseInputStyle) {
        if (japaneseInputStyle == style) return
        japaneseInputStyle = style
        if (inputMode == InputMode.JAPANESE && keyboardLayer == KeyboardLayer.LETTERS) {
            renderManualKeyboard()
        }
    }

    fun setVoiceActionMode(mode: VoiceActionMode) {
        voiceActionMode = mode
        styleVoiceTaskButton(dictationTaskButton, mode == VoiceActionMode.DICTATION)
        styleVoiceTaskButton(composeTaskButton, mode == VoiceActionMode.COMPOSE)
        dictationTaskButton.setTextColor(ContextCompat.getColor(context,
            if (mode == VoiceActionMode.DICTATION) R.color.voice_task_selected_text
            else R.color.voice_task_unselected_text
        ))
        composeTaskButton.setTextColor(ContextCompat.getColor(context,
            if (mode == VoiceActionMode.COMPOSE) R.color.voice_task_selected_text
            else R.color.voice_task_unselected_text
        ))
        dictationTaskButton.isSelected = mode == VoiceActionMode.DICTATION
        composeTaskButton.isSelected = mode == VoiceActionMode.COMPOSE
        renderDraftActions()
    }

    private fun styleVoiceTaskButton(button: TextView, selected: Boolean) {
        val surface = ContextCompat.getDrawable(context,
            if (selected) R.drawable.voice_task_selected_bg else R.drawable.voice_task_unselected_bg)
        // Quiet 28 dp cards at opposite edges; the full 44 dp area remains tappable.
        button.background = InsetDrawable(surface, 0, dp(8), 0, dp(8))
    }

    fun setDraftActions(hasNotes: Boolean, hasPending: Boolean) {
        hasComposeNotes = hasNotes
        hasPendingDraft = hasPending
        renderDraftActions()
    }

    fun setDraftPreview(text: String) {
        draftPreviewText.text = text
        if (text.isBlank()) draftPreviewShown = false
        renderDraftActions()
    }

    fun showDraftPreview() {
        if (draftPreviewText.text.isBlank() || !isVoiceIdle()) return
        draftPreviewShown = true
        hideTranslationPanel()
        renderDraftActions()
    }

    fun hideDraftPreview() {
        draftPreviewShown = false
        renderDraftActions()
    }

    fun setRetryAvailable(available: Boolean) {
        retryAvailable = available
        renderDraftActions()
    }

    /** A light surface preference shared by the oval and its live audio accent. */
    fun setVoicePalette(palette: Int) {
        val opaque = ColorUtils.setAlphaComponent(palette, 255)
        voicePalette = if (ColorUtils.calculateLuminance(opaque) < 0.65) {
            ColorUtils.blendARGB(opaque, Color.WHITE, 0.85f)
        } else opaque
        renderVoicePalette()
    }

    private fun renderVoicePalette() {
        val ink = ContextCompat.getColor(context, R.color.mic_text_recording)
        val surfaceColor = ColorUtils.blendARGB(voicePalette, Color.WHITE,
            if (currentVoiceState in setOf(VoiceInputIME.ImeState.STARTING,
                    VoiceInputIME.ImeState.STOPPING, VoiceInputIME.ImeState.PROCESSING)) 0.22f else 0f)
        val accent = ColorUtils.blendARGB(voicePalette, ink, 0.58f)
        // The full touch target remains; only the painted edge fades away.
        micOuterRing.background = null
        micOuterRing.elevation = 0f
        micButton.backgroundTintList = null
        // An opaque oval ripple mask reintroduces a hard edge during touch/focus.
        // Every feedback state must fade to transparent using the same surface.
        micButton.background = StateListDrawable().apply {
            addState(intArrayOf(android.R.attr.state_pressed),
                SoftVoiceCircleDrawable(ColorUtils.blendARGB(surfaceColor, ink, 0.05f)))
            addState(intArrayOf(android.R.attr.state_focused),
                SoftVoiceCircleDrawable(ColorUtils.blendARGB(surfaceColor, ink, 0.08f)))
            addState(intArrayOf(), SoftVoiceCircleDrawable(surfaceColor))
        }
        micActionIcon.imageTintList = ColorStateList.valueOf(ink)
        micActionLabel.setTextColor(ink)
        audioWaveform.setPaletteColors(accent, ColorUtils.blendARGB(voicePalette, ink, 0.36f))
    }

    private fun isVoiceIdle() = currentVoiceState in setOf(
        VoiceInputIME.ImeState.IDLE,
        VoiceInputIME.ImeState.DONE,
        VoiceInputIME.ImeState.ERROR
    )

    private fun renderDraftActions() {
        val idle = isVoiceIdle()
        if (emojiPanelVisible && !idle) setEmojiPanelVisible(false)
        nextKeyboardButton.isEnabled = idle
        nextKeyboardButton.alpha = if (idle) 1f else 0.45f
        val canChangeVoiceTask = idle
        listOf(dictationTaskButton, composeTaskButton).forEach { button ->
            button.isEnabled = canChangeVoiceTask
            button.alpha = if (canChangeVoiceTask) 1f else 0.58f
        }
        if (!idle) draftPreviewShown = false
        val canPreview = draftPreviewText.text.isNotBlank() && idle &&
            (hasComposeNotes || hasPendingDraft)
        if (!canPreview) draftPreviewShown = false
        draftPreviewButton.isVisible = canPreview && !draftPreviewShown && !translationPanel.isVisible
        draftPreviewPanel.isVisible = draftPreviewShown && canPreview
        captureArea.isVisible = !translationPanel.isVisible
        micOuterRing.isVisible = !draftPreviewPanel.isVisible
        composeActionRow.isVisible = inputMode == InputMode.VOICE &&
            voiceActionMode == VoiceActionMode.COMPOSE && hasComposeNotes && !hasPendingDraft && !retryAvailable
        composeContinueButton.isEnabled = idle
        composeGenerateButton.isEnabled = idle
        composeClearButton.isEnabled = idle
        pendingInsertRow.isVisible = inputMode == InputMode.VOICE && (hasPendingDraft || retryAvailable)
        pendingInsertButton.setText(if (retryAvailable) R.string.voice_pending_retry else R.string.voice_pending_insert)
        pendingInsertButton.contentDescription = pendingInsertButton.text
        pendingInsertButton.isEnabled = idle
        pendingDiscardButton.isEnabled = idle
        listOf(composeContinueButton, composeGenerateButton, composeClearButton,
            pendingInsertButton, pendingDiscardButton).forEach { it.alpha = if (idle) 1f else 0.45f }
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
        micActionLabel.setText(R.string.mic_action_translation_recording)
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
        captureArea.isVisible = false
        translationPanel.isVisible = true
        draftPreviewButton.isVisible = false
        statusText.setText(R.string.translation_picker_status)
        translationPanel.announceForAccessibility(
            context.getString(R.string.translation_picker_accessibility)
        )
    }

    fun hideTranslationPanel() {
        if (!::translationPanel.isInitialized) return
        translationPanel.isVisible = false
        renderDraftActions()
    }

    fun updateCandidates(composition: String, candidates: List<String>) {
        compositionText.text = composition
        compositionText.isVisible = composition.isNotBlank()
        renderCompositionLayout()
        latestCandidates = candidates
            .asSequence()
            .filter { it.isNotBlank() }
            .distinct()
            .take(MAX_RENDERED_CANDIDATES)
            .toList()
        renderJapaneseUtilityKeys()
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
        }
        if (candidatesExpanded) renderCandidateGrid()

        val renderedSnapshot = latestCandidates
        candidateScroller.post {
            if (latestCandidates != renderedSnapshot) return@post
            val hasOverflow =
                candidateContainer.measuredWidth > candidateScroller.measuredWidth
            candidateExpandButton.isVisible =
                candidatesExpanded || hasOverflow || renderedSnapshot.size > EXPANDED_CANDIDATE_COLUMNS
            if (!candidateExpandButton.isVisible) setCandidatesExpanded(false)
        }
    }

    fun setZhuyinReselectAvailable(available: Boolean) {
        zhuyinReselectAvailable = available
        renderZhuyinReselectAction()
    }

    private fun candidateTextLocale(): Locale = when (inputMode) {
        InputMode.ZHUYIN -> Locale.TAIWAN
        InputMode.JAPANESE -> Locale.JAPANESE
        InputMode.ENGLISH -> Locale.ENGLISH
        InputMode.VOICE -> resources.configuration.locales[0]
    }

    private fun renderCompositionLayout() {
        val zhuyin = inputMode == InputMode.ZHUYIN
        val expandedZhuyin = zhuyin && candidatesExpanded
        val separateReading = zhuyin || isJapanesePhoneLayout()
        val useSummary = separateReading && !candidatesExpanded
        val targetParent = if (useSummary) compositionSummaryContent else inputStrip
        if (compositionText.parent != targetParent) {
            (compositionText.parent as? ViewGroup)?.removeView(compositionText)
            if (useSummary) {
                compositionSummaryContent.addView(compositionText,
                    FrameLayout.LayoutParams(LayoutParams.WRAP_CONTENT, LayoutParams.MATCH_PARENT))
            } else {
                inputStrip.addView(compositionText, 0,
                    LayoutParams(if (expandedZhuyin) 0 else LayoutParams.WRAP_CONTENT,
                        dp(if (expandedZhuyin) 52 else 44), if (expandedZhuyin) 1f else 0f)
                        .apply { marginEnd = dp(3) })
            }
        }
        compositionText.textLocale = candidateTextLocale()
        compositionText.textSize = if (separateReading) 14f else 17f
        compositionText.maxWidth = if (useSummary || zhuyin) Int.MAX_VALUE else dp(96)
        compositionText.minWidth = if (separateReading) 0 else dp(48)
        compositionText.maxLines = if (expandedZhuyin) 2 else 1
        compositionText.ellipsize = when {
            expandedZhuyin -> TextUtils.TruncateAt.END
            useSummary || zhuyin -> null
            else -> TextUtils.TruncateAt.START
        }
        compositionText.background = if (separateReading) null else
            ContextCompat.getDrawable(context, R.drawable.composition_chip_bg)
        // Reserve the reading line even before typing. GONE used to move every key
        // by 28dp and shrink the rows on the first phonetic tap.
        compositionSummary.visibility = when {
            !useSummary || emojiPanelVisible -> View.GONE
            compositionText.text.isNotBlank() -> View.VISIBLE
            else -> View.INVISIBLE
        }
        val readingHeight = dp(if (resources.configuration.fontScale > 1.3f) 28 else 20)
        compositionSummary.layoutParams.height = readingHeight
        manualCandidateHeader.layoutParams.height = readingHeight + dp(56)
        if (zhuyin) compositionSummary.scrollTo(0, 0)
        inputStrip.layoutParams.height = dp(if (zhuyin) 56 else 50)
        inputStrip.updatePadding(top = dp(if (zhuyin) 2 else 3), bottom = dp(if (zhuyin) 2 else 3))
        candidateScroller.layoutParams.height = dp(if (zhuyin) 52 else 44)
        candidateExpandButton.layoutParams.apply {
            width = dp(if (zhuyin) 48 else 44)
            height = dp(if (zhuyin) 52 else 44)
        }
        renderZhuyinReselectAction()
    }

    private fun renderZhuyinReselectAction() {
        zhuyinReselectButton.isVisible = inputMode == InputMode.ZHUYIN && !emojiPanelVisible
        zhuyinReselectButton.isEnabled = zhuyinReselectAvailable && zhuyinReselectButton.isVisible
        zhuyinReselectButton.alpha = if (zhuyinReselectButton.isEnabled) 1f else 0.45f
    }

    fun updateState(state: VoiceInputIME.ImeState) {
        currentVoiceState = state
        when (state) {
            VoiceInputIME.ImeState.IDLE -> {
                audioWaveform.setRecordingActive(false)
                statusText.setText(R.string.status_idle)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = true,
                    labelRes = R.string.mic_action_start,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_idle
                )
            }

            VoiceInputIME.ImeState.STARTING -> {
                audioWaveform.setRecordingActive(false)
                audioWaveform.setAudioLevel(0f)
                statusText.setText(R.string.status_starting)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = false,
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
                    labelRes = R.string.mic_action_recording,
                    iconRes = R.drawable.ic_check,
                    dotColorRes = R.color.status_dot_recording
                )
            }

            VoiceInputIME.ImeState.STOPPING -> {
                audioWaveform.setRecordingActive(false)
                statusText.setText(R.string.status_stopping)
                statusText.setTextColor(ContextCompat.getColor(context, R.color.status_text))
                applyMicState(
                    enabled = false,
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
                    labelRes = R.string.mic_action_start,
                    iconRes = R.drawable.ic_mic,
                    dotColorRes = R.color.status_dot_recording
                )
            }
        }
        micActionIcon.isVisible = state != VoiceInputIME.ImeState.RECORDING
        if (voiceActionMode == VoiceActionMode.COMPOSE) {
            when (state) {
                VoiceInputIME.ImeState.IDLE,
                VoiceInputIME.ImeState.DONE,
                VoiceInputIME.ImeState.ERROR -> {
                    micActionLabel.setText(R.string.voice_compose_mic_start)
                    micButton.contentDescription = context.getString(R.string.voice_compose_mic_start)
                }
                VoiceInputIME.ImeState.RECORDING -> {
                    micActionLabel.setText(R.string.voice_compose_mic_finish)
                    micButton.contentDescription = context.getString(R.string.voice_compose_mic_finish)
                }
                else -> Unit
            }
        }
        renderDraftActions()
    }

    private fun bindViews() {
        keyboardRoot = findViewById(R.id.keyboard_root)
        contentScroll = findViewById(R.id.keyboard_content_scroll)
        captureArea = findViewById(R.id.voice_capture_area)
        draftPreviewPanel = findViewById(R.id.draft_preview_panel)
        draftPreviewText = findViewById(R.id.tv_draft_preview)
        draftPreviewButton = findViewById(R.id.btn_draft_preview)
        draftPreviewCloseButton = findViewById(R.id.btn_draft_preview_close)
        voiceModeButton = findViewById(R.id.btn_mode_voice)
        zhuyinModeButton = findViewById(R.id.btn_mode_zhuyin)
        japaneseModeButton = findViewById(R.id.btn_mode_japanese)
        englishModeButton = findViewById(R.id.btn_mode_english)
        nextKeyboardButton = findViewById(R.id.btn_next_keyboard)
        voicePanel = findViewById(R.id.panel_voice)
        manualPanel = findViewById(R.id.panel_manual)
        voiceActionRow = findViewById(R.id.voice_action_row)
        micButton = findViewById(R.id.btn_mic)
        micOuterRing = findViewById(R.id.mic_outer_ring)
        micActionLabel = findViewById(R.id.mic_action_label)
        micActionIcon = findViewById(R.id.mic_action_icon)
        ViewCompat.setAccessibilityDelegate(micButton, object : AccessibilityDelegateCompat() {
            override fun onInitializeAccessibilityNodeInfo(host: View, info: AccessibilityNodeInfoCompat) {
                super.onInitializeAccessibilityNodeInfo(host, info)
                info.className = "android.widget.Button"
            }
        })
        statusText = findViewById(R.id.tv_status)
        voiceStateDot = findViewById(R.id.voice_state_dot)
        audioWaveform = findViewById(R.id.audio_waveform)
        voiceTaskSwitch = findViewById(R.id.voice_task_switch)
        dictationTaskButton = findViewById(R.id.btn_voice_dictation)
        composeTaskButton = findViewById(R.id.btn_voice_compose)
        listOf(dictationTaskButton, composeTaskButton).forEach {
            TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(
                it, 10, 12, 1, TypedValue.COMPLEX_UNIT_SP
            )
        }
        composeActionRow = findViewById(R.id.compose_action_row)
        composeContinueButton = findViewById(R.id.btn_compose_continue)
        composeGenerateButton = findViewById(R.id.btn_compose_generate)
        composeClearButton = findViewById(R.id.btn_compose_clear)
        pendingInsertRow = findViewById(R.id.pending_insert_row)
        pendingInsertButton = findViewById(R.id.btn_pending_insert)
        pendingDiscardButton = findViewById(R.id.btn_pending_discard)
        listOf(composeContinueButton, composeGenerateButton, composeClearButton,
            pendingInsertButton, pendingDiscardButton, draftPreviewButton,
            draftPreviewCloseButton).forEach { button ->
            button.maxLines = 2
            button.includeFontPadding = false
            TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(
                button, 10, 13, 1, TypedValue.COMPLEX_UNIT_SP
            )
        }
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
        compositionSummary = findViewById(R.id.zhuyin_composition_summary)
        compositionSummaryContent = findViewById(R.id.zhuyin_composition_summary_content)
        inputStrip = findViewById(R.id.input_strip)
        manualCandidateHeader = findViewById(R.id.manual_candidate_header)
        zhuyinReselectButton = findViewById(R.id.btn_zhuyin_reselect)
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
        setEnterIcon(enterButton)
        // Voice-mode utility keys look one third shorter, without shrinking their targets.
        listOf(layerButton, commaButton, spaceButton, periodButton, backspaceButton, enterButton)
            .forEach { button ->
                button.background = InsetDrawable(button.background, 0, dp(8), 0, dp(8))
                button.elevation = 0f
                button.includeFontPadding = false
            }
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

    override fun onMeasure(widthMeasureSpec: Int, heightMeasureSpec: Int) {
        if (!::contentScroll.isInitialized) {
            super.onMeasure(widthMeasureSpec, heightMeasureSpec)
            return
        }
        val width = MeasureSpec.getSize(widthMeasureSpec)
        // Give the company mark and larger SGH room without crowding the tabs
        // on narrow phones. Their group stays centred in the same 44dp row.
        val brandWidth = dp(if (width < dp(320)) 88 else if (width < dp(360)) 96 else 104)
        findViewById<View>(R.id.keyboard_brand_group).layoutParams.width = brandWidth
        findViewById<TextView>(R.id.tv_keyboard_brand).maxWidth = brandWidth - dp(24)
        val captureWidth = (width - keyboardRoot.paddingLeft - keyboardRoot.paddingRight -
            voicePanel.paddingLeft - voicePanel.paddingRight).coerceAtLeast(dp(48))
        val maximumTaskWidth = (captureWidth * 0.44f).toInt()
        listOf(dictationTaskButton, composeTaskButton).forEach {
            it.maxWidth = maximumTaskWidth
        }
        val preferred = resources.getDimensionPixelSize(R.dimen.voice_mic_diameter)
        val minimum = dp(if (resources.configuration.fontScale > 1.3f) 104 else 88)
        // Keep the shape broad even on a narrow phone or a short landscape viewport.
        val captureHeight = minOf(maxOf(preferred, minimum), (captureWidth * 0.64f).toInt())
            .coerceAtLeast(dp(48))
        resizeCaptureArea(captureWidth, captureHeight)
        // Never derive the IME footprint from the current mode's natural content height.
        // Navigation padding is additive, but the available-screen cap is shared by all modes.
        val navigationPadding = (keyboardRoot.paddingBottom - dp(6)).coerceAtLeast(0)
        val screenBudget = dp((resources.configuration.screenHeightDp * 0.80f).toInt()
            .coerceAtLeast(160))
        val parentBudget = if (MeasureSpec.getMode(heightMeasureSpec) == MeasureSpec.UNSPECIFIED) {
            screenBudget
        } else MeasureSpec.getSize(heightMeasureSpec)
        val targetHeight = minOf(dp(KeyboardSizing.heightDp(keyboardHeightPercent)) + navigationPadding,
            screenBudget, parentBudget)
        val fixedHeight = keyboardRoot.paddingTop + keyboardRoot.paddingBottom + dp(44) +
            if (voiceActionRow.isVisible) dp(56) else 0
        val bodyBudget = (targetHeight - fixedHeight).coerceAtLeast(0)
        // Romaji grows into the same key area as five-row English/Zhuyin/Kana.
        // On very short screens, scroll rather than reduce targets below 44dp.
        val rows = manualKeyRows.childCount
        if (rows > 0) {
            val candidateAreaHeight = manualPanel.paddingTop + manualCandidateHeader.layoutParams.height
            val gridHeight = (bodyBudget - candidateAreaHeight).coerceAtLeast(rows * dp(44))
            manualKeyRows.layoutParams.height = gridHeight
            for (index in 0 until rows) {
                manualKeyRows.getChildAt(index).layoutParams.height =
                    gridHeight / rows + if (index < gridHeight % rows) 1 else 0
            }
            candidateExpandedPanel.layoutParams.height = (gridHeight - dp(4)).coerceAtLeast(0)
        }
        contentScroll.layoutParams.height = bodyBudget
        super.onMeasure(widthMeasureSpec, heightMeasureSpec)
        val naturalHeight = contentScroll.getChildAt(0).measuredHeight
        if (inputMode == InputMode.VOICE && naturalHeight > bodyBudget) {
            resizeCaptureArea(captureWidth,
                (captureHeight - (naturalHeight - bodyBudget)).coerceAtLeast(minOf(minimum, captureHeight)))
        }
        super.onMeasure(widthMeasureSpec, heightMeasureSpec)
    }

    private fun resizeCaptureArea(ovalWidth: Int, ovalHeight: Int) {
        captureArea.layoutParams.height = ovalHeight
        micOuterRing.layoutParams.width = ovalWidth
        micOuterRing.layoutParams.height = ovalHeight
        val compact = ovalHeight < dp(140)
        (micActionIcon.layoutParams as FrameLayout.LayoutParams).apply {
            width = dp(if (compact) 24 else 32)
            height = width
            topMargin = (ovalHeight * if (compact) 0.16f else 0.26f).toInt()
        }
        (micActionLabel.layoutParams as FrameLayout.LayoutParams).apply {
            width = (ovalWidth * 0.74f).toInt().coerceAtLeast(dp(40))
            this.height = dp(if (resources.configuration.fontScale > 1.3f) 48 else if (compact) 32 else 40)
            bottomMargin = dp(if (compact) 3 else 8)
        }
    }

    private fun bindActions() {
        bindModeButton(voiceModeButton, InputMode.VOICE)
        bindModeButton(zhuyinModeButton, InputMode.ZHUYIN)
        bindModeButton(japaneseModeButton, InputMode.JAPANESE)
        bindModeButton(englishModeButton, InputMode.ENGLISH)

        dictationTaskButton.setOnClickListener {
            hapticTap(it)
            listener?.onVoiceActionModeChanged(VoiceActionMode.DICTATION)
        }
        composeTaskButton.setOnClickListener {
            hapticTap(it)
            listener?.onVoiceActionModeChanged(VoiceActionMode.COMPOSE)
        }
        composeContinueButton.setOnClickListener {
            hapticTap(it)
            listener?.onComposeContinue()
        }
        composeGenerateButton.setOnClickListener {
            hapticTap(it)
            // Keep the two task cards. Choose the meaning of "generate" explicitly:
            // faithful organization must never treat a spoken question as a writing command.
            PopupMenu(context, it).apply {
                menu.add(0, 1, 0, R.string.draft_organize_choice)
                menu.add(0, 2, 1, R.string.draft_write_choice)
                setOnMenuItemClickListener { item ->
                    if (isVoiceIdle()) {
                        if (item.itemId == 1) listener?.onComposeOrganize()
                        else listener?.onComposeGenerate()
                    }
                    true
                }
                show()
            }
        }
        composeClearButton.setOnClickListener {
            hapticTap(it)
            listener?.onComposeClear()
        }
        pendingInsertButton.setOnClickListener {
            hapticTap(it)
            if (retryAvailable) listener?.onPendingRetry() else listener?.onPendingInsert()
        }
        pendingDiscardButton.setOnClickListener {
            hapticTap(it)
            listener?.onPendingDiscard()
        }
        draftPreviewButton.setOnClickListener {
            hapticTap(it)
            listener?.onDraftPreviewRequested()
        }
        draftPreviewCloseButton.setOnClickListener {
            hapticTap(it)
            hideDraftPreview()
        }

        nextKeyboardButton.setOnClickListener {
            hapticTap(it)
            if (isVoiceIdle()) setEmojiPanelVisible(!emojiPanelVisible)
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
        zhuyinReselectButton.setOnClickListener {
            if (!zhuyinReselectButton.isEnabled) return@setOnClickListener
            hapticTap(it)
            setCandidatesExpanded(false)
            listener?.onZhuyinReselectRequested()
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
        layerButton.setOnClickListener { dispatchVoiceAction(it, KeyAction.InsertText("、")) }
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
        layerButton.setText(R.string.key_ideographic_comma)
        commaButton.text = "，"
        periodButton.text = "。"
    }

    private fun setEmojiPanelVisible(visible: Boolean) {
        emojiPanelVisible = visible
        renderCompositionLayout()
        candidateExpandButton.isEnabled = !visible
        setCandidatesExpanded(false)
        val showVoice = inputMode == InputMode.VOICE && !visible
        voicePanel.isVisible = showVoice
        voiceActionRow.isVisible = showVoice
        manualPanel.isVisible = !showVoice
        renderEmojiButton()
        if (showVoice) manualKeyRows.removeAllViews() else renderManualKeyboard()
        updateTouchSplitting(this)
        requestLayout()
    }

    private fun renderEmojiButton() {
        nextKeyboardButton.contentDescription = context.getString(
            if (emojiPanelVisible) R.string.keyboard_emoji_close else R.string.keyboard_emoji_open
        )
        if (emojiPanelVisible) {
            nextKeyboardButton.setImageResource(R.drawable.ic_keyboard_switch)
        } else {
            nextKeyboardButton.setImageDrawable(EmojiEntryDrawable(
                ContextCompat.getColor(context, R.color.key_text), dp(24)
            ))
        }
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
        renderCompositionLayout()
        val manualMode = when (inputMode) {
            InputMode.ZHUYIN -> ManualKeyboardMode.ZHUYIN
            InputMode.JAPANESE -> ManualKeyboardMode.JAPANESE
            InputMode.ENGLISH -> ManualKeyboardMode.ENGLISH
            InputMode.VOICE -> if (emojiPanelVisible) ManualKeyboardMode.ENGLISH else return
        }
        val rows = if (emojiPanelVisible) layoutProvider.emojiRows(emojiPage)
            else layoutProvider.layout(manualMode, keyboardLayer, shiftState, japaneseInputStyle).rows
        manualKeyRows.removeAllViews()
        rows.forEachIndexed { rowIndex, row ->
            val rowView = LinearLayout(context).apply {
                orientation = HORIZONTAL
                gravity = android.view.Gravity.CENTER
                layoutParams = LayoutParams(
                    LayoutParams.MATCH_PARENT,
                    if (manualMode == ManualKeyboardMode.ZHUYIN) dp(52) else dp(48)
                )
                val letterRowIndex = rowIndex - if (manualMode == ManualKeyboardMode.ENGLISH &&
                    keyboardLayer == KeyboardLayer.LETTERS && !emojiPanelVisible) 1 else 0
                val horizontalInset = when {
                    emojiPanelVisible -> 0
                    manualMode == ManualKeyboardMode.ZHUYIN ||
                        japaneseInputStyle == JapaneseInputStyle.KANA_12_KEY && manualMode == ManualKeyboardMode.JAPANESE ||
                        keyboardLayer != KeyboardLayer.LETTERS -> 0
                    letterRowIndex == 1 -> dp(14)
                    letterRowIndex == 2 -> dp(2)
                    else -> 0
                }
                setPadding(horizontalInset, 0, horizontalInset, 0)
            }
            row.keys.forEach { key -> rowView.addView(createKeyButton(key)) }
            manualKeyRows.addView(rowView)
        }
        updateTouchSplitting(this)
        renderJapaneseUtilityKeys()
    }

    private fun isJapanesePhoneLayout(): Boolean = inputMode == InputMode.JAPANESE &&
        japaneseInputStyle == JapaneseInputStyle.KANA_12_KEY &&
        keyboardLayer == KeyboardLayer.LETTERS && !emojiPanelVisible

    /** Change labels in place. Rebuilding keys while typing would interrupt an active flick. */
    private fun renderJapaneseUtilityKeys() {
        if (!isJapanesePhoneLayout()) return
        val composing = compositionText.text.isNotBlank()
        findViewWithTag<TextView>("japanese_kana_space")?.apply {
            text = if (composing) "候補" else "空白"
            contentDescription = context.getString(if (composing) R.string.japanese_candidates_action else R.string.key_space)
        }
        findViewWithTag<TextView>("japanese_kana_enter")?.apply {
            if (composing) { text = "確定"; textSize = 16f } else setEnterIcon(this)
            contentDescription = context.getString(if (composing) R.string.japanese_confirm_reading else R.string.japanese_enter_action)
        }
        findViewWithTag<View>("japanese_kana_convert")?.isEnabled = latestCandidates.isNotEmpty()
        findViewWithTag<View>("japanese_kana_reverse")?.isEnabled = composing
    }

    private fun showJapaneseCandidates() {
        if (!isJapanesePhoneLayout() || latestCandidates.isEmpty()) return
        // Explicit conversion is allowed even when two kana fallbacks fit the strip.
        candidateExpandButton.isVisible = true
        setCandidatesExpanded(true)
    }

    private fun showJapaneseInputOptions(anchor: View) {
        PopupMenu(context, anchor).apply {
            menu.add(0, 1, 0, if (japaneseScriptMode == JapaneseScriptMode.HIRAGANA)
                R.string.japanese_switch_katakana else R.string.japanese_switch_hiragana)
            menu.add(0, 2, 1, R.string.japanese_switch_romaji)
            menu.add(0, 3, 2, R.string.japanese_switch_numbers)
            setOnMenuItemClickListener { item ->
                when (item.itemId) {
                    1 -> listener?.onKeyAction(KeyAction.ToggleJapaneseScript)
                    2 -> listener?.onKeyAction(KeyAction.ToggleJapaneseLayout)
                    3 -> {
                        listener?.onKeyAction(KeyAction.FinalizeJapaneseKana)
                        keyboardLayer = KeyboardLayer.NUMBERS
                        renderManualKeyboard()
                    }
                }
                true
            }
            show()
        }
    }

    private fun createKeyButton(key: KeySpec): TextView {
        return (if (key.action is KeyAction.TapJapaneseKana) KanaFlickKeyView(context)
            else TextView(context)).apply {
            tag = key.id
            val displayLabel = when {
                key.action == KeyAction.ToggleEmoji -> when (inputMode) {
                    InputMode.VOICE -> context.getString(R.string.mode_voice)
                    InputMode.ZHUYIN -> "注"
                    InputMode.JAPANESE -> "あ"
                    InputMode.ENGLISH -> "ABC"
                }
                key.role == KeyRole.SPACE -> context.getString(R.string.key_space)
                key.id == "japanese_script" &&
                    japaneseScriptMode == JapaneseScriptMode.HIRAGANA -> "カナ"
                key.id == "japanese_script" -> "かな"
                key.action == KeyAction.ToggleJapaneseLayout &&
                    japaneseInputStyle == JapaneseInputStyle.KANA_12_KEY -> "ABC"
                else -> key.label
            }
            text = displayLabel
            contentDescription = when (key.action) {
                KeyAction.ToggleEmoji -> context.getString(R.string.keyboard_emoji_close)
                KeyAction.NextEmojiPage -> context.getString(R.string.keyboard_emoji_next_page)
                KeyAction.CursorLeft -> context.getString(R.string.keyboard_cursor_left)
                KeyAction.CursorRight -> context.getString(R.string.keyboard_cursor_right)
                KeyAction.ReverseJapaneseKana -> context.getString(R.string.japanese_reverse_kana)
                KeyAction.ShowJapaneseCandidates -> context.getString(R.string.japanese_candidates_action)
                KeyAction.JapaneseInputOptions -> context.getString(R.string.japanese_input_options)
                else -> key.contentDescription
            }
            gravity = android.view.Gravity.CENTER
            includeFontPadding = false
            maxLines = 1
            textSize = when {
                key.action is KeyAction.InsertEmoji -> 24f
                key.action == KeyAction.Enter -> 27f
                key.action == KeyAction.CursorLeft || key.action == KeyAction.CursorRight -> 22f
                isJapanesePhoneLayout() && key.action is KeyAction.TapJapaneseKana -> 23f
                isJapanesePhoneLayout() && key.action == KeyAction.ReverseJapaneseKana -> 24f
                isJapanesePhoneLayout() -> 16f
                displayLabel.length > 4 -> 12f
                inputMode == InputMode.ZHUYIN && key.role == KeyRole.CHARACTER -> 21f
                key.role == KeyRole.CHARACTER -> 18f
                else -> 13f
            }
            if (isJapanesePhoneLayout() && key.action !is KeyAction.TapJapaneseKana &&
                key.action != KeyAction.CursorLeft && key.action != KeyAction.CursorRight &&
                key.action != KeyAction.ReverseJapaneseKana && key.action != KeyAction.Backspace) {
                // Rails are intentionally narrower. Fit their short labels without ellipses
                // at large system font sizes while retaining the full-size touch cell.
                TextViewCompat.setAutoSizeTextTypeUniformWithConfiguration(this, 10, 16, 1,
                    TypedValue.COMPLEX_UNIT_SP)
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
            val surface = if (isJapanesePhoneLayout()) {
                val fill = when {
                    key.role == KeyRole.ACTION -> R.color.key_enter_bg
                    key.role == KeyRole.MODIFIER || key.role == KeyRole.SPACE -> R.color.key_special_bg
                    else -> R.color.key_bg
                }
                // Compact, quiet rectangular caps; the whole cell remains the touch target.
                val shape = GradientDrawable().apply {
                    cornerRadius = dp(6).toFloat()
                    setColor(ContextCompat.getColor(context, fill))
                }
                RippleDrawable(ColorStateList.valueOf(ContextCompat.getColor(context, R.color.key_bg_pressed)), shape, null)
            } else ContextCompat.getDrawable(context, backgroundRes)
            val inset = dp(if (isJapanesePhoneLayout()) 3 else 2)
            background = InsetDrawable(surface, inset, inset, inset, inset)
            // setBackground copies drawable padding; text insets must be applied afterwards.
            if (isJapanesePhoneLayout()) setPadding(dp(6), 0, dp(6), 0)
            setTypeface(
                Typeface.create(
                    "sans-serif",
                    if (key.role == KeyRole.CHARACTER) Typeface.NORMAL else Typeface.BOLD
                )
            )
            if (key.action == KeyAction.Enter) setEnterIcon(this)
            layoutParams = LayoutParams(
                0,
                LayoutParams.MATCH_PARENT,
                key.widthWeight
            )
            setOnClickListener {
                hapticTap(it)
                when (val action = key.action) {
                    KeyAction.JapaneseInputOptions -> showJapaneseInputOptions(this)
                    KeyAction.ShowJapaneseCandidates -> showJapaneseCandidates()
                    KeyAction.Space -> {
                        if (isJapanesePhoneLayout() && compositionText.text.isNotBlank()) showJapaneseCandidates()
                        else listener?.onKeyAction(action)
                    }
                    KeyAction.ToggleEmoji -> setEmojiPanelVisible(!emojiPanelVisible)
                    KeyAction.NextEmojiPage -> {
                        emojiPage = EmojiPalette.normalizedPage(emojiPage + 1)
                        renderManualKeyboard()
                        manualKeyRows.announceForAccessibility(context.getString(
                            R.string.keyboard_emoji_page, emojiPage + 1, EmojiPalette.pages.size
                        ))
                    }
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
            if (this is KanaFlickKeyView && key.action is KeyAction.TapJapaneseKana) {
                bindFlick(
                    key.action.group,
                    onKana = { kana ->
                        hapticTap(this)
                        listener?.onKeyAction(KeyAction.InsertText(kana))
                    },
                    onCenterTap = {
                        hapticTap(this)
                        listener?.onKeyAction(key.action)
                    }
                )
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
            textLocale = candidateTextLocale()
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
        gridRow: Int? = null,
        gridColumn: Int = 0,
        gridSpan: Int = 1
    ): TextView {
        return TextView(context).apply {
            text = candidate
            textLocale = candidateTextLocale()
            contentDescription = context.getString(
                R.string.candidate_content_description,
                candidate
            )
            gravity = android.view.Gravity.CENTER
            includeFontPadding = false
            val expandedZhuyin = inputMode == InputMode.ZHUYIN && gridRow != null
            maxLines = if (expandedZhuyin) Int.MAX_VALUE else 1
            ellipsize = if (expandedZhuyin) null else TextUtils.TruncateAt.END
            minWidth = dp(48)
            textSize = if (inputMode == InputMode.ZHUYIN) {
                22f
            } else {
                if (candidate.length > 2) 17f else 20f
            }
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
            val candidateHeight = dp(if (inputMode == InputMode.ZHUYIN) 52 else 44)
            minimumHeight = candidateHeight
            setPadding(dp(12), if (expandedZhuyin) dp(8) else 0,
                dp(12), if (expandedZhuyin) dp(8) else 0)
            layoutParams = if (gridRow == null) {
                LayoutParams(LayoutParams.WRAP_CONTENT, candidateHeight).apply {
                    marginStart = dp(3)
                    marginEnd = dp(3)
                }
            } else {
                GridLayout.LayoutParams(
                    GridLayout.spec(gridRow),
                    GridLayout.spec(gridColumn, gridSpan, gridSpan.toFloat())
                ).apply {
                    width = 0
                    height = if (expandedZhuyin) LayoutParams.WRAP_CONTENT else candidateHeight
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
            expanded && !emojiPanelVisible && latestCandidates.isNotEmpty() && candidateExpandButton.isVisible
        if (shouldExpand && !candidatesExpanded) {
            renderCandidateGrid()
        } else if (!shouldExpand) {
            candidateGrid.removeAllViews()
        }
        candidatesExpanded = shouldExpand
        renderCompositionLayout()
        if (shouldExpand && manualKeyRows.height > 0) {
            candidateExpandedPanel.layoutParams =
                candidateExpandedPanel.layoutParams.apply {
                    height = (manualKeyRows.height - dp(4)).coerceAtLeast(0)
                }
        }
        candidateScroller.visibility = when {
            shouldExpand && inputMode == InputMode.ZHUYIN -> View.GONE
            shouldExpand -> View.INVISIBLE
            else -> View.VISIBLE
        }
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

    private fun renderCandidateGrid() {
        candidateGrid.removeAllViews()
        val columns = if (inputMode == InputMode.ZHUYIN) ZHUYIN_EXPANDED_CANDIDATE_COLUMNS
            else EXPANDED_CANDIDATE_COLUMNS
        candidateGrid.columnCount = columns
        var row = 0
        var column = 0
        latestCandidates.forEachIndexed { index, candidate ->
            val span = if (inputMode == InputMode.ZHUYIN &&
                candidate.codePointCount(0, candidate.length) > 4) columns else 1
            if (column + span > columns) {
                row++
                column = 0
            }
            candidateGrid.addView(
                createCandidateButton(candidate, primary = index == 0,
                    gridRow = row, gridColumn = column, gridSpan = span)
            )
            column += span
            if (column == columns) {
                row++
                column = 0
            }
        }
    }

    private fun setEnterIcon(button: TextView) {
        val icon = ContextCompat.getDrawable(context, R.drawable.ic_key_enter)?.mutate()
            ?: return
        val size = dp(24)
        icon.setBounds(0, 0, size, size)
        icon.setTint(ContextCompat.getColor(context, R.color.key_text_enter))
        // A fixed-size span keeps the existing TextView, localized accessibility
        // label and click action, without relying on each font's tiny ↵ glyph.
        button.text = SpannableString("\uFFFC").apply {
            setSpan(object : ReplacementSpan() {
                override fun getSize(
                    paint: Paint,
                    text: CharSequence,
                    start: Int,
                    end: Int,
                    fm: Paint.FontMetricsInt?
                ): Int {
                    fm?.let {
                        val metrics = paint.fontMetricsInt
                        val center = (metrics.ascent + metrics.descent) / 2
                        it.ascent = center - size / 2
                        it.descent = it.ascent + size
                        it.top = it.ascent
                        it.bottom = it.descent
                    }
                    return size
                }

                override fun draw(
                    canvas: Canvas,
                    text: CharSequence,
                    start: Int,
                    end: Int,
                    x: Float,
                    top: Int,
                    y: Int,
                    bottom: Int,
                    paint: Paint
                ) {
                    val checkpoint = canvas.save()
                    canvas.translate(x, (top + bottom - size) / 2f)
                    icon.draw(canvas)
                    canvas.restoreToCount(checkpoint)
                }
            }, 0, length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE)
        }
    }

    private fun styleModeButton(button: TextView, selected: Boolean) {
        val surface = if (selected) {
            ContextCompat.getDrawable(context, R.drawable.mode_selected_bg)
        } else {
            ContextCompat.getDrawable(context, R.drawable.mode_unselected_bg)
        }
        val isKeyboardMode = button === voiceModeButton || button === zhuyinModeButton ||
            button === japaneseModeButton || button === englishModeButton
        // Compact the visible pill, while retaining the full 44 dp touch area.
        button.background = if (isKeyboardMode) {
            InsetDrawable(surface, 0, dp(6), 0, dp(6))
        } else {
            surface
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
        labelRes: Int,
        iconRes: Int,
        dotColorRes: Int
    ) {
        micButton.isEnabled = enabled
        micButton.alpha = 1f
        micActionLabel.setText(labelRes)
        micButton.contentDescription = context.getString(labelRes)
        micActionIcon.setImageResource(iconRes)
        renderVoicePalette()
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

/** A monochrome toolbar icon, independent of the device's colored emoji font. */
private class EmojiEntryDrawable(color: Int, private val size: Int) : Drawable() {
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        this.color = color
        strokeWidth = 1.8f
        style = Paint.Style.STROKE
        strokeCap = Paint.Cap.ROUND
    }

    override fun getIntrinsicWidth() = size
    override fun getIntrinsicHeight() = size

    override fun draw(canvas: Canvas) {
        val saved = canvas.save()
        canvas.translate(bounds.left.toFloat(), bounds.top.toFloat())
        canvas.scale(bounds.width() / 24f, bounds.height() / 24f)
        paint.style = Paint.Style.STROKE
        canvas.drawCircle(12f, 12f, 9f, paint)
        canvas.drawArc(7f, 8f, 17f, 17f, 20f, 140f, false, paint)
        paint.style = Paint.Style.FILL
        canvas.drawCircle(9f, 9f, 1f, paint)
        canvas.drawCircle(15f, 9f, 1f, paint)
        canvas.restoreToCount(saved)
    }

    override fun setAlpha(alpha: Int) { paint.alpha = alpha; invalidateSelf() }
    override fun setColorFilter(colorFilter: ColorFilter?) {
        paint.colorFilter = colorFilter
        invalidateSelf()
    }
    @Suppress("DEPRECATION")
    override fun getOpacity() = PixelFormat.TRANSLUCENT
}
