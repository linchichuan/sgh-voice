package com.shingihou.sghvoice.learning

import android.text.InputType
import android.view.inputmethod.EditorInfo
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class LearningPolicyTest {

    @Test
    fun `normal messages and person names allow personalization`() {
        val message = LearningPolicy.evaluate(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_SHORT_MESSAGE,
            0
        )
        val name = LearningPolicy.evaluate(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PERSON_NAME,
            0
        )

        assertTrue(message.personalizationAllowed)
        assertTrue(name.personalizationAllowed)
        assertEquals(LearningPolicyReason.ALLOWED, message.reason)
    }

    @Test
    fun `no personalized learning flag always wins`() {
        val decision = LearningPolicy.evaluate(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_NORMAL,
            EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING
        )

        assertFalse(decision.personalizationAllowed)
        assertEquals(
            LearningPolicyReason.NO_PERSONALIZED_LEARNING,
            decision.reason
        )
    }

    @Test
    fun `all password variations are sensitive and disabled`() {
        val inputs = listOf(
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD,
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD,
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD,
            InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD
        )

        inputs.forEach { inputType ->
            val decision = LearningPolicy.evaluate(inputType, 0)
            assertFalse(decision.personalizationAllowed)
            assertTrue(decision.sensitiveField)
            assertEquals(LearningPolicyReason.PASSWORD_FIELD, decision.reason)
        }
    }

    @Test
    fun `number phone date and null fields are disabled`() {
        listOf(
            InputType.TYPE_NULL,
            InputType.TYPE_CLASS_NUMBER,
            InputType.TYPE_CLASS_PHONE,
            InputType.TYPE_CLASS_DATETIME
        ).forEach { inputType ->
            val decision = LearningPolicy.evaluate(inputType, 0)
            assertFalse(decision.personalizationAllowed)
            assertEquals(LearningPolicyReason.NON_TEXT_FIELD, decision.reason)
        }
    }

    @Test
    fun `email uri filter and no-suggestions fields are disabled`() {
        val variations = listOf(
            InputType.TYPE_TEXT_VARIATION_EMAIL_ADDRESS,
            InputType.TYPE_TEXT_VARIATION_WEB_EMAIL_ADDRESS,
            InputType.TYPE_TEXT_VARIATION_URI,
            InputType.TYPE_TEXT_VARIATION_FILTER
        )
        variations.forEach { variation ->
            val decision = LearningPolicy.evaluate(
                InputType.TYPE_CLASS_TEXT or variation,
                0
            )
            assertFalse(decision.personalizationAllowed)
            assertEquals(
                LearningPolicyReason.NON_NATURAL_TEXT_FIELD,
                decision.reason
            )
        }

        val noSuggestions = LearningPolicy.evaluate(
            InputType.TYPE_CLASS_TEXT or
                InputType.TYPE_TEXT_VARIATION_NORMAL or
                InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS,
            0
        )
        assertFalse(noSuggestions.personalizationAllowed)
        assertEquals(
            LearningPolicyReason.NO_SUGGESTIONS_FIELD,
            noSuggestions.reason
        )
    }
}
