package com.shingihou.sghvoice.api

import com.shingihou.sghvoice.processing.RecognitionLanguage
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import okhttp3.Call
import okhttp3.Interceptor
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.net.SocketTimeoutException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Synthetic responses only: the interceptor never opens a provider connection. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class WhisperClientTest {
    private fun config(model: String = "gpt-transcribe", engine: String = "openai") = mock<ApiConfig>().also {
        whenever(it.whisperModel).thenReturn(model)
        whenever(it.sttEngine).thenReturn(engine)
        whenever(it.openAiApiKey).thenReturn("synthetic-test-key")
        whenever(it.groqApiKey).thenReturn("synthetic-groq-key")
        whenever(it.groqSttModel).thenReturn("whisper-large-v3-turbo")
        whenever(it.recognitionLanguage).thenReturn(RecognitionLanguage.AUTO)
        whenever(it.hasCloudProcessingConsent).thenReturn(true)
    }

    private fun http(handler: (Request) -> Response) = OkHttpClient.Builder()
        .addInterceptor(Interceptor { handler(it.request()) }).build()

    private fun response(request: Request, code: Int = 200, json: String = "{\"text\":\"SGH Phone 測試\"}") =
        Response.Builder().request(request).protocol(Protocol.HTTP_1_1)
            .code(code).message("synthetic").body(json.toResponseBody("application/json".toMediaType())).build()

    private fun Request.form() = Buffer().also { body!!.writeTo(it) }.readUtf8()
    private fun Request.values(name: String): List<String> = (body as MultipartBody).parts
        .filter { it.headers?.get("Content-Disposition") == "form-data; name=\"$name\"" }
        .map { part -> Buffer().also { part.body.writeTo(it) }.readUtf8() }

    @Test fun `new model sends keywords and multiple languages without legacy prompt or language`() = runBlocking {
        var captured: Request? = null
        val client = WhisperClient(config(), http { captured = it; response(it) })
        try {
            assertEquals("SGH Phone 測試", client.transcribe(ByteArray(44), "GitHub、KusuriJapan、SGH Phone"))
            val body = captured!!.form()
            assertEquals(listOf("SGH Phone", "KusuriJapan", "GitHub"), captured!!.values("keywords[]"))
            assertTrue(body.indexOf("SGH Phone") < body.indexOf("KusuriJapan"))
            assertEquals(listOf("zh", "ja", "en"), captured!!.values("languages[]"))
            assertFalse(body.contains("name=\"language\""))
            assertFalse(body.contains("name=\"prompt\""))
        } finally { client.shutdown() }
    }

    @Test fun `explicit language replaces multilingual hints and unsafe keywords never leave client`() = runBlocking {
        val config = config()
        whenever(config.recognitionLanguage).thenReturn(RecognitionLanguage.KOREAN)
        val client = WhisperClient(config, http {
            val body = it.form()
            assertEquals(listOf("ko"), it.values("languages[]"))
            assertFalse(body.contains("\r\n\r\nzh\r\n"))
            assertFalse(body.contains("<bad>"))
            assertFalse(body.contains("line\nbreak"))
            assertTrue(body.contains("GoodName"))
            response(it)
        })
        try { client.transcribe(ByteArray(44), "<bad>、line\nbreak、GoodName"); Unit }
        finally { client.shutdown() }
    }

    @Test fun `legacy OpenAI models and Groq retain prompt and singular language`() = runBlocking {
        for ((engine, model) in listOf("openai" to "whisper-1", "openai" to "gpt-4o-transcribe", "openai" to "gpt-4o-mini-transcribe", "groq" to "gpt-transcribe")) {
            val config = config(model, engine)
            whenever(config.recognitionLanguage).thenReturn(RecognitionLanguage.JAPANESE)
            val client = WhisperClient(config, http {
                val body = it.form()
                assertEquals(listOf("GitHub、SGH Phone"), it.values("prompt"))
                assertEquals(listOf("ja"), it.values("language"))
                assertFalse(body.contains("keywords[]"))
                assertFalse(body.contains("languages[]"))
                assertEquals(if (engine == "groq") "api.groq.com" else "api.openai.com", it.url.host)
                response(it)
            })
            try { client.transcribe(ByteArray(44), "GitHub、SGH Phone") }
            finally { client.shutdown() }
        }
    }

    @Test fun `empty vocabulary adds no hints and legacy auto omits language`() = runBlocking {
        for (model in listOf("gpt-transcribe", "whisper-1")) {
            val client = WhisperClient(config(model), http {
                val body = it.form()
                assertFalse(body.contains("keywords[]"))
                assertFalse(body.contains("name=\"prompt\""))
                assertFalse(body.contains("name=\"language\""))
                assertEquals(model == "gpt-transcribe", body.contains("languages[]"))
                response(it)
            })
            try { client.transcribe(ByteArray(44)) }
            finally { client.shutdown() }
        }
    }

    @Test fun `invalid authentication unavailable model and transient status fail without provider retry`() {
        for (code in listOf(400, 401, 403, 404, 429, 503)) {
            var calls = 0
            val client = WhisperClient(config(), http { calls++; response(it, code, "{\"error\":\"private upstream detail\"}") })
            try {
                val error = assertThrows(WhisperException::class.java) { runBlocking { client.transcribe(ByteArray(44)) } }
                assertEquals("Speech recognition HTTP $code", error.message)
                assertEquals(1, calls)
            } finally { client.shutdown() }
        }
    }

    @Test fun `malformed response and timeout produce sanitized errors`() {
        for (json in listOf("{}", "{\"text\":42}", "{\"text\":null}", "not-json")) {
            val invalid = WhisperClient(config(), http { response(it, json = json) })
            try {
                assertThrows(WhisperException::class.java) { runBlocking { invalid.transcribe(ByteArray(44)) } }
            } finally { invalid.shutdown() }
        }
        val timeout = WhisperClient(config(), http { throw SocketTimeoutException("private upstream detail") })
        try {
            val error = assertThrows(WhisperException::class.java) { runBlocking { timeout.transcribe(ByteArray(44)) } }
            assertFalse(error.message.orEmpty().contains("private upstream"))
        } finally { timeout.shutdown() }
    }

    @Test fun `cancelling transcription cancels the HTTP call and returns no transcript`() = runBlocking {
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        var call: Call? = null
        var returned = false
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            call = chain.call()
            started.countDown()
            check(release.await(5, TimeUnit.SECONDS))
            response(chain.request())
        }.build()
        val client = WhisperClient(config(), transport)
        val job = launch(Dispatchers.IO) {
            client.transcribe(ByteArray(44))
            returned = true
        }
        try {
            assertTrue(started.await(5, TimeUnit.SECONDS))
            job.cancelAndJoin()
            assertTrue(call!!.isCanceled())
            assertFalse(returned)
        } finally {
            release.countDown()
            job.cancelAndJoin()
            client.shutdown()
        }
    }

    @Test fun `no consent stops network and existing missing OpenAI key Groq route stays legacy`() = runBlocking {
        var calls = 0
        val config = config()
        whenever(config.hasCloudProcessingConsent).thenReturn(false)
        val client = WhisperClient(config, http {
            calls++
            assertEquals("api.groq.com", it.url.host)
            assertFalse(it.form().contains("keywords[]"))
            response(it)
        })
        try {
            assertThrows(CloudProcessingConsentException::class.java) { runBlocking { client.transcribe(ByteArray(44)) } }
            assertEquals(0, calls)
            whenever(config.hasCloudProcessingConsent).thenReturn(true)
            whenever(config.openAiApiKey).thenReturn("")
            client.transcribe(ByteArray(44), "SGH Phone")
            assertEquals(1, calls)
        } finally { client.shutdown() }
    }
}
