package com.shingihou.sghvoice.processing

import com.shingihou.sghvoice.api.ApiConfig
import com.shingihou.sghvoice.api.CloudProcessingConsentException
import com.shingihou.sghvoice.api.ComposeException
import com.shingihou.sghvoice.api.LlmClient
import com.shingihou.sghvoice.api.WhisperClient
import kotlinx.coroutines.runBlocking
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Response
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.mockito.kotlin.*

/** Real draft store, pipeline, LLM guard and OpenCC; only HTTP and preference storage are synthetic. */
class ContinuousDraftOrganizationTest {
    private val first = "今天檢查 GitHub Actions。"
    private val second = "明天不要更改設定。"
    private val notes = "$first\n$second"
    private val formatted = "$first\n\n$second"

    private fun pipeline(reply: String, requests: MutableList<JSONObject>,
                         consent: () -> Boolean = { true }, engine: String = "groq"): TranscriptionPipeline {
        val config = mock<ApiConfig> {
            on { llmEngine } doReturn engine
            on { groqApiKey } doReturn "synthetic-key"
            on { groqLlmModel } doReturn "synthetic-model"
            on { outputStyle } doReturn "normal"
            on { hasCloudProcessingConsent } doAnswer { consent() }
        }
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            val body = Buffer()
            chain.request().body!!.writeTo(body)
            requests += JSONObject(body.readUtf8())
            val response = JSONObject().put("choices", JSONArray().put(JSONObject()
                .put("finish_reason", "stop").put("message", JSONObject().put("content", reply))))
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1)
                .code(200).message("OK").body(response.toString()
                    .toResponseBody("application/json".toMediaType())).build()
        }.build()
        val dictionary = mock<DictionaryManager> {
            on { getSceneSystemPromptExtra() } doReturn ""
            on { buildLlmVocabularyHint(any(), any()) } doReturn "[]"
            on { applyCorrections(any(), any()) } doAnswer { it.getArgument<String>(0) }
        }
        return TranscriptionPipeline(mock<WhisperClient>(), LlmClient(config, transport),
            dictionary, OpenCCConverter(), consent)
    }

    @Test fun `all confirmed segments reach one faithful request without a short context window`() = runBlocking {
        val state = VoiceDraftState()
        state.appendComposeSegment(first)
        state.appendComposeSegment(second)
        val requests = mutableListOf<JSONObject>()
        val result = pipeline(formatted, requests).organizeNotes(state.composeNotes())
        assertEquals(formatted, result)
        assertEquals(1, requests.size)
        val messages = requests.single().getJSONArray("messages")
        val payload = JSONObject(messages.getJSONObject(1).getString("content"))
        assertEquals(notes, payload.getString("source_text"))
        assertFalse(payload.has("brief"))
        assertFalse(payload.has("previous_context"))
        assertTrue(messages.getJSONObject(0).getString("content").contains("絕不可回答"))
        assertEquals(notes, state.composeNotes())
        assertFalse("Generation cannot silently insert or consume the source draft", state.hasPendingText)
    }

    @Test fun `changed facts leave all original segments available for retry`() {
        val state = VoiceDraftState()
        state.appendComposeSegment(first)
        state.appendComposeSegment(second)
        val requests = mutableListOf<JSONObject>()
        assertThrows(ComposeException::class.java) {
            runBlocking { pipeline("$first\n明天可以更改設定。", requests).organizeNotes(state.composeNotes()) }
        }
        assertEquals(notes, state.composeNotes())
        assertFalse(state.hasPendingText)
        assertEquals(1, requests.size)
    }

    @Test fun `a question remains speech and is not answered by organization`() {
        val requests = mutableListOf<JSONObject>()
        assertThrows(ComposeException::class.java) {
            runBlocking { pipeline("你可以重新啟動伺服器。", requests).organizeNotes("為什麼伺服器沒有啟動？") }
        }
    }

    @Test fun `disabled AI and invalid draft do not pretend organization succeeded`() {
        val requests = mutableListOf<JSONObject>()
        assertThrows(ComposeException::class.java) {
            runBlocking { pipeline(formatted, requests, engine = "none").organizeNotes(notes) }
        }
        for (invalid in listOf("", "字".repeat(VoiceDraftState.MAX_COMPOSE_CHARACTERS + 1))) {
            assertThrows(ComposeException::class.java) {
                runBlocking { pipeline(formatted, requests).organizeNotes(invalid) }
            }
        }
        assertTrue(requests.isEmpty())
    }

    @Test fun `revoked consent prevents draft upload`() {
        val requests = mutableListOf<JSONObject>()
        assertThrows(CloudProcessingConsentException::class.java) {
            runBlocking { pipeline(formatted, requests, consent = { false }).organizeNotes(notes) }
        }
        assertTrue(requests.isEmpty())
    }

    @Test fun `overlong formatted output cannot report a saved draft and retains original notes`() {
        val state = VoiceDraftState()
        val source = "Test.\n".repeat(1000).trim()
        val oversized = "Test.\n          \n".repeat(1000).trim()
        state.appendComposeSegment(source)
        assertTrue(oversized.length > VoiceDraftState.MAX_PENDING_CHARACTERS)
        val requests = mutableListOf<JSONObject>()
        assertThrows(ComposeException::class.java) {
            runBlocking { pipeline(oversized, requests).organizeNotes(state.composeNotes()) }
        }
        assertEquals(1, requests.size)
        assertEquals(source, state.composeNotes())
        assertFalse(state.hasPendingText)
    }
}
