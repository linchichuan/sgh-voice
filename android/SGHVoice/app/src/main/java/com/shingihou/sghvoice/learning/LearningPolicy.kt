package com.shingihou.sghvoice.learning

import android.text.InputType
import android.view.inputmethod.EditorInfo

enum class LearningPolicyReason {
    ALLOWED,
    MISSING_EDITOR_INFO,
    NO_PERSONALIZED_LEARNING,
    PASSWORD_FIELD,
    NON_TEXT_FIELD,
    NO_SUGGESTIONS_FIELD,
    NON_NATURAL_TEXT_FIELD
}

data class LearningPolicyDecision(
    val personalizationAllowed: Boolean,
    val reason: LearningPolicyReason,
    /**
     * Sensitive fields must additionally suppress learned candidates, bounded
     * text snapshots, and cloud voice submission.
     */
    val sensitiveField: Boolean
) {
    /**
     * Static on-device suggestions are not personalized learning. They remain
     * available when an editor opts out of learning, but are suppressed for
     * passwords, non-text inputs and fields that explicitly disable suggestions.
     */
    val localSuggestionsAllowed: Boolean
        get() = reason in setOf(
            LearningPolicyReason.ALLOWED,
            LearningPolicyReason.NO_PERSONALIZED_LEARNING
        )
}

/**
 * Central privacy gate for personalized learning.
 *
 * This is intentionally conservative. It only learns from natural-language
 * text variations, and always honors IME_FLAG_NO_PERSONALIZED_LEARNING.
 */
object LearningPolicy {

    fun evaluate(editorInfo: EditorInfo?): LearningPolicyDecision {
        if (editorInfo == null) {
            return deny(LearningPolicyReason.MISSING_EDITOR_INFO)
        }
        return evaluate(editorInfo.inputType, editorInfo.imeOptions)
    }

    /**
     * Raw-value overload keeps the policy independently unit-testable without
     * constructing Android framework objects.
     */
    fun evaluate(inputType: Int, imeOptions: Int): LearningPolicyDecision {
        val inputClass = inputType and InputType.TYPE_MASK_CLASS
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        if (isPassword(inputClass, variation)) {
            return LearningPolicyDecision(
                personalizationAllowed = false,
                reason = LearningPolicyReason.PASSWORD_FIELD,
                sensitiveField = true
            )
        }
        if (inputClass != InputType.TYPE_CLASS_TEXT) {
            return deny(LearningPolicyReason.NON_TEXT_FIELD)
        }
        if (inputType and InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS != 0) {
            return deny(LearningPolicyReason.NO_SUGGESTIONS_FIELD)
        }

        val naturalLanguageVariation = variation in setOf(
            InputType.TYPE_TEXT_VARIATION_NORMAL,
            InputType.TYPE_TEXT_VARIATION_EMAIL_SUBJECT,
            InputType.TYPE_TEXT_VARIATION_LONG_MESSAGE,
            InputType.TYPE_TEXT_VARIATION_PERSON_NAME,
            InputType.TYPE_TEXT_VARIATION_PHONETIC,
            InputType.TYPE_TEXT_VARIATION_POSTAL_ADDRESS,
            InputType.TYPE_TEXT_VARIATION_SHORT_MESSAGE,
            InputType.TYPE_TEXT_VARIATION_WEB_EDIT_TEXT
        )
        if (!naturalLanguageVariation) {
            return deny(LearningPolicyReason.NON_NATURAL_TEXT_FIELD)
        }
        if (imeOptions and EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING != 0) {
            return deny(LearningPolicyReason.NO_PERSONALIZED_LEARNING)
        }

        return LearningPolicyDecision(
            personalizationAllowed = true,
            reason = LearningPolicyReason.ALLOWED,
            sensitiveField = false
        )
    }

    private fun isPassword(inputClass: Int, variation: Int): Boolean {
        return when (inputClass) {
            InputType.TYPE_CLASS_TEXT -> variation in setOf(
                InputType.TYPE_TEXT_VARIATION_PASSWORD,
                InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD,
                InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD
            )

            InputType.TYPE_CLASS_NUMBER ->
                variation == InputType.TYPE_NUMBER_VARIATION_PASSWORD

            else -> false
        }
    }

    private fun deny(reason: LearningPolicyReason) =
        LearningPolicyDecision(
            personalizationAllowed = false,
            reason = reason,
            sensitiveField = false
        )
}
