package com.shingihou.sghvoice.ime

import android.text.InputType
import android.view.View
import android.view.inputmethod.BaseInputConnection
import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.learning.*
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.*
import org.robolectric.Robolectric
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class VoiceLearningConnectionTest {
    @Test fun `real IME records successive corrected terms and refreshes only its own voice context`() {
        val service = spy(Robolectric.buildService(VoiceInputIME::class.java).get())
        val connection = BaseInputConnection(View(RuntimeEnvironment.getApplication()), true)
        doReturn(connection).`when`(service).currentInputConnection
        val repository = mock<PersonalizationRepository>()
        whenever(repository.isEnabled()).thenReturn(true)
        whenever(repository.recordVoiceCorrection(any(), any<CorrectionReplacement>(), any(), anyOrNull(), anyOrNull()))
            .thenReturn(CorrectionRecordResult(CorrectionRecordStatus.ACTIVATED))
        val config = mock<ApiConfig>()
        whenever(config.recentVoiceContextEnabled).thenReturn(true)
        fun field(name: String) = VoiceInputIME::class.java.getDeclaredField(name).apply { isAccessible = true }
        fun invoke(name: String, vararg args: Any?) = VoiceInputIME::class.java.declaredMethods
            .single { it.name == name }.apply { isAccessible = true }.invoke(service, *args)
        field("personalization").set(service, repository)
        field("apiConfig").set(service, config)
        field("currentLearningDecision").set(service, LearningPolicy.evaluate(InputType.TYPE_CLASS_TEXT, 0))
        val sessionId = field("inputSessionId").getLong(service)
        val original = "請用Orbyt檢查Kotlun。"
        connection.commitText("前文後文", 1)
        connection.setSelection(2, 2)
        connection.commitText(original, 1)
        invoke("beginVoiceCorrectionTracking", sessionId, connection, original, original)
        fun replaceAllVoice(text: String) {
            connection.setSelection(2, requireNotNull(connection.editable).length - 2)
            connection.commitText(text, 1)
            invoke("inspectVoiceCorrection")
        }
        replaceAllVoice("請用Orbit檢查Kotlun。")
        replaceAllVoice("請用Orbit檢查Kotlin。")
        // Learning happens once, from the final text, when the voice turn ends.
        verify(repository, never()).recordVoiceCorrection(any(), any<CorrectionReplacement>(), any(), anyOrNull(), anyOrNull())
        invoke("finalizeCorrectionTracking", false, 0L)
        val corrections = argumentCaptor<CorrectionReplacement>()
        verify(repository, times(2)).recordVoiceCorrection(
            eq(LearningLanguage.MIXED), corrections.capture(), eq(true), any(), eq(CorrectionScope.LATIN))
        assertEquals(listOf("Orbit", "Kotlin"), corrections.allValues.map { it.correctedText })
        val context = field("recentVoiceContext").get(service) as RecentVoiceContext
        assertEquals("請用Orbit檢查Kotlin。", context.get(sessionId, true))
        invoke("cancelCorrectionTracking")
        assertEquals("", context.get(sessionId, true))
    }
}
