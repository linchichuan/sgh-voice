package com.shingihou.sghvoice.api

import kotlinx.coroutines.runBlocking
import okhttp3.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Buffer
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.mockito.kotlin.mock
import org.mockito.kotlin.whenever
import java.net.ServerSocket
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

class DictationPunctuationRecoveryTest {
    @Test fun `punctuation deadline includes stalled response body after headers`() {
        val source = "Please check the report today we will discuss it tomorrow"
        val config = mock<ApiConfig>().also {
            whenever(it.llmEngine).thenReturn("groq")
            whenever(it.groqApiKey).thenReturn("synthetic-test-key")
            whenever(it.groqLlmModel).thenReturn("test-model")
            whenever(it.outputStyle).thenReturn("normal")
            whenever(it.hasCloudProcessingConsent).thenReturn(true)
        }
        val releaseBody = CountDownLatch(1)
        val requests = AtomicInteger()
        val server = ServerSocket(0, 2, java.net.InetAddress.getLoopbackAddress())
        val worker = thread(isDaemon = true, name = "punctuation-local-http") {
            repeat(2) { index ->
                server.accept().use { socket ->
                    val input = java.io.DataInputStream(socket.getInputStream())
                    var contentLength = 0
                    while (true) {
                        val line = input.readLine() ?: break
                        if (line.isEmpty()) break
                        if (line.startsWith("Content-Length:", ignoreCase = true)) {
                            contentLength = line.substringAfter(':').trim().toInt()
                        }
                    }
                    repeat(contentLength) { input.read() }
                    requests.incrementAndGet()
                    val body = JSONObject().put("choices", JSONArray().put(JSONObject()
                        .put("finish_reason", "stop").put("message", JSONObject().put("content", source))))
                        .toString().toByteArray(Charsets.UTF_8)
                    val output = socket.getOutputStream()
                    output.write(("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n" +
                        "Content-Length: ${body.size}\r\nConnection: close\r\n\r\n").toByteArray())
                    output.flush()
                    // Real socket I/O: coroutine cancellation alone cannot interrupt
                    // ResponseBody.string() once the headers callback has resumed.
                    if (index == 1) releaseBody.await(18, TimeUnit.SECONDS)
                    runCatching { output.write(body); output.flush() }
                }
            }
        }
        val transport = OkHttpClient.Builder().readTimeout(60, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val local = chain.request().newBuilder().url("http://127.0.0.1:${server.localPort}/test").build()
                chain.proceed(local)
            }.build()
        try {
            val started = System.nanoTime()
            val result = runBlocking { LlmClient(config, transport).refineDictation(source) }
            val elapsedMs = TimeUnit.NANOSECONDS.toMillis(System.nanoTime() - started)
            assertEquals(source, result.text)
            assertEquals(2, requests.get())
            assertTrue("12-second recovery deadline exceeded: ${elapsedMs}ms", elapsedMs < 15_000)
        } finally {
            releaseBody.countDown()
            server.close()
            worker.join(2_000)
            transport.dispatcher.executorService.shutdownNow()
            transport.connectionPool.evictAll()
        }
    }

    private fun run(source: String, replies: List<String>, engine: String = "groq", revokeAfterFirst: Boolean = false, onRequest: () -> Unit = {}): Pair<LlmClient.RefinementResult, List<JSONObject>> = runBlocking {
        val requests = mutableListOf<JSONObject>()
        val config = mock<ApiConfig>().also {
            whenever(it.llmEngine).thenReturn(engine)
            whenever(it.groqApiKey).thenReturn("synthetic-test-key")
            whenever(it.openAiApiKey).thenReturn("synthetic-test-key")
            whenever(it.anthropicApiKey).thenReturn("synthetic-test-key")
            whenever(it.groqLlmModel).thenReturn("test-model")
            whenever(it.openAiLlmModel).thenReturn("test-model")
            whenever(it.claudeModel).thenReturn("test-model")
            whenever(it.outputStyle).thenReturn("normal")
            whenever(it.hasCloudProcessingConsent).thenReturn(true)
        }
        val transport = OkHttpClient.Builder().addInterceptor { chain ->
            onRequest()
            val buffer = Buffer()
            chain.request().body!!.writeTo(buffer)
            requests += JSONObject(buffer.readUtf8())
            if (revokeAfterFirst && requests.size == 1) {
                whenever(config.hasCloudProcessingConsent).thenReturn(false)
            }
            val reply = replies.getOrElse(requests.lastIndex) { error("Retry must be bounded") }
            val json = JSONObject().put("choices", JSONArray().put(JSONObject().put("finish_reason", "stop")
                .put("message", JSONObject().put("content", reply))))
                .put("stop_reason", "end_turn")
                .put("content", JSONArray().put(JSONObject().put("type", "text").put("text", reply)))
            Response.Builder().request(chain.request()).protocol(Protocol.HTTP_1_1).code(200).message("OK")
                .body(json.toString().toResponseBody("application/json".toMediaType())).build()
        }.build()
        LlmClient(config, transport).refineDictation(source) to requests
    }

    @Test fun `rejected word rewrite can recover punctuation without accepting wrong words across providers`() {
        val source = "今天請林先生買三台電腦明天再付款不要更改金額"
        val expected = "今天請林先生買三台電腦，明天再付款，不要更改金額。"
        for (engine in listOf("claude", "openai", "groq")) {
            val (result, requests) = run(source, listOf(expected.replace("買", "賣"), expected), engine)
            assertEquals(engine, expected, result.text)
            assertEquals(LlmClient.RefinementStatus.APPLIED, result.status)
            assertEquals(2, requests.size)
        }
    }

    @Test fun `long unpunctuated reply gets one formatting only retry`() {
        val source = "今日は資料を確認します明日は会議に参加します変更はしないでください"
        val expected = "今日は資料を確認します。明日は会議に参加します。変更はしないでください。"
        val (result, requests) = run(source, listOf(source, expected))
        assertEquals(expected, result.text)
        assertEquals(2, requests.size)
    }

    @Test fun `recovery changing a number or negation still fails closed without a third request`() {
        val source = "今天請林先生買三台電腦明天再付款不要更改金額"
        val wrong = "今天請王先生買四台電腦，明天再付款，可以更改金額。"
        val (result, requests) = run(source, listOf(wrong, wrong))
        assertEquals(source, result.text)
        assertEquals(LlmClient.RefinementStatus.REJECTED, result.status)
        assertEquals(2, requests.size)
    }

    @Test fun `already punctuated and disabled paths do not add requests`() {
        val source = "今天先測試，明天再部署。"
        assertEquals(1, run(source, listOf(source)).second.size)
        assertEquals(0, run(source, emptyList(), "none").second.size)
    }

    @Test fun `consent withdrawn after first response prevents punctuation retry from leaving device`() {
        val source = "今天請林先生買三台電腦明天再付款不要更改金額"
        var sent = 0
        assertThrows(CloudProcessingConsentException::class.java) {
            run(source, listOf(source), revokeAfterFirst = true, onRequest = { sent++ })
        }
        assertEquals(1, sent)
    }

    @Test fun `English recovery keeps word boundaries and URLs intact`() {
        val source = "Please check the report today we will discuss it tomorrow"
        val expected = "Please check the report today. We will discuss it tomorrow."
        // Case changes are deliberately not allowed in this second, formatting-only pass.
        val allowed = expected.replace("We", "we")
        assertEquals(allowed, run(source, listOf(source, allowed)).first.text)
        val source2 = "Please work now here and do not change the report"
        val invalid = "Please work nowhere, and do not change the report."
        assertEquals(source2, run(source2, listOf(invalid, invalid)).first.text)
        val url = "https://example.com/a/very/long/path"
        assertEquals(1, run(url, listOf(url)).second.size)
    }
}
