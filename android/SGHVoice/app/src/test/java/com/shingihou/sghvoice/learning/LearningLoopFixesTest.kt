package com.shingihou.sghvoice.learning

import android.content.SharedPreferences
import com.shingihou.sghvoice.processing.DictionaryManager
import com.shingihou.sghvoice.processing.TranscriptionPipeline
import com.shingihou.sghvoice.processing.TranslationLanguage
import com.shingihou.sghvoice.processing.TranslationRequest
import com.shingihou.sghvoice.processing.VoiceTask
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import org.mockito.kotlin.mock

/**
 * Problems 7-11 (learning loop). Real tracker, learning adapter, repository and dictionary;
 * only storage is synthetic. All inputs are synthetic, expectations are literal values.
 */
class LearningLoopFixesTest {

    private var now = 0L
    private fun tracker() = VoiceCorrectionTracker(clockElapsedMillis = { now })

    /** Anchored on both sides, as in a normal editor: high-confidence evidence. */
    private fun snapshot(text: String) = BoundedTextSnapshot(
        beforeCursor = "前文：$text", afterCursor = "：後文", windowStartOffset = 0
    )

    private fun repository(storage: LearningStorage = MemoryStorage()) = PersonalizationRepository(storage, { now })

    private fun dictionary(repository: PersonalizationRepository) =
        DictionaryManager(mock<SharedPreferences>()) { repository }

    /** Simulates one voice turn: commit, the user's successive editor states, then finalization. */
    private fun turn(original: String, vararg edits: String, stt: String? = null): List<LearnedCorrection> {
        val tracker = tracker()
        assertTrue(tracker.begin(1L, original, snapshot(original), sttText = stt))
        edits.forEach { edited ->
            now += 1_000L
            tracker.inspect(1L, snapshot(edited))
        }
        now += 5_000L
        return tracker.finish(1L)
    }

    private fun List<LearnedCorrection>.pairs() =
        map { it.replacement.wrongText to it.replacement.correctedText }

    private fun record(repository: PersonalizationRepository, learned: List<LearnedCorrection>, turnId: Long) =
        learned.map {
            repository.recordVoiceCorrection(LearningLanguage.MIXED, it.replacement, it.highConfidence, turnId, it.scope)
        }

    // ---- Spec 1: several edits in one voice turn, extracted from the final stable text ----

    @Test fun `E12 two replacements in one voice turn are both learned once`() {
        val learned = turn("請用Orbyt檢查Kotlun。", "請用Orbit檢查Kotlun。", "請用Orbit檢查Kotlin。")
        assertEquals(listOf("Orbyt" to "Orbit", "Kotlun" to "Kotlin"), learned.pairs())
        assertTrue(learned.all { it.highConfidence })
    }

    @Test fun `E13 delete then retype in pieces learns only the final GitHub Actions`() {
        val learned = turn(
            "請檢查吉他哈布艾克申的設定。",
            "請檢查的設定。",
            "請檢查GitHub的設定。",
            "請檢查GitHub Actions的設定。"
        )
        assertEquals(listOf("吉他哈布艾克申" to "GitHub Actions"), learned.pairs())
    }

    @Test fun `L3 delete then retype Han never learns the intermediate character`() {
        val learned = turn("我們在家開會。", "我們開會。", "我們再開會。", "我們再加開會。")
        assertEquals(listOf("在家" to "再加"), learned.pairs())
    }

    @Test fun `E14 a pure insertion does not stop later corrections in the same turn`() {
        val learned = turn("請用Orbyt檢查Kotlun。", "請先用Orbyt檢查Kotlun。", "請先用Orbyt檢查Kotlin。")
        assertEquals(listOf("Kotlun" to "Kotlin"), learned.pairs())
    }

    @Test fun `clearing the whole voice result learns nothing even after retyping`() {
        assertTrue(turn("測試一下", "", "你好嗎").isEmpty())
    }

    @Test fun `finishing right after the last edit at expiry learns nothing`() {
        val tracker = tracker()
        tracker.begin(1L, "請用Kotlun。", snapshot("請用Kotlun。"))
        now = 59_500L
        tracker.inspect(1L, snapshot("請用Kotlin。"))
        now = 60_100L
        assertTrue("A possibly unfinished edit at the deadline is not learned", tracker.finish(1L).isEmpty())
        assertFalse(tracker.isTracking())
    }

    // ---- Spec 2: typo fix vs meaning change; pending before active ----

    @Test fun `E15 number and negation changes are neither learned nor applied`() {
        val repository = repository()
        for (turnId in 1L..3L) {
            record(repository, turn("下午三點開會。", "下午四點開會。"), turnId).forEach {
                assertEquals(CorrectionRecordStatus.REJECTED, it.status)
            }
            record(repository, turn("今天不要部署。", "今天可以部署。"), turnId).forEach {
                assertEquals(CorrectionRecordStatus.REJECTED, it.status)
            }
        }
        for ((wrong, corrected) in listOf("三點" to "四點", "不要" to "可以", "1,200美元" to "1,300美元", "-3%" to "+3%")) {
            assertEquals(CorrectionRecordStatus.REJECTED,
                repository.recordVoiceCorrection(LearningLanguage.MIXED, wrong, corrected, true, turnId = 9L).status)
        }
        assertTrue(repository.getVoiceCorrections().isEmpty())
        val dictionary = dictionary(repository)
        assertEquals("明天下午三點開會，你不要部署。",
            dictionary.applyCorrections("明天下午三點開會，你不要部署。", includePersonalization = true))
    }

    @Test fun `synonym swaps and long rewrites are not learned`() {
        val repository = repository()
        for (turnId in 1L..2L) {
            assertEquals(CorrectionRecordStatus.REJECTED,
                repository.recordVoiceCorrection(LearningLanguage.MIXED, "接著", "然後", true, turnId = turnId).status)
        }
        val longWrong = "這一段是使用者重新改寫過的整句內容並不是錯字"
        val longCorrected = "這段內容被完整改寫成另外一個說法所以不能學習"
        assertEquals(CorrectionRecordStatus.REJECTED,
            repository.recordVoiceCorrection(LearningLanguage.MIXED, longWrong, longCorrected, true, turnId = 3L).status)
        assertTrue(turn("今天先檢查程式碼然後部署。", "今天我們要先開會討論需求。").isEmpty())
        assertEquals("接著部署", dictionary(repository).applyCorrections("接著部署", includePersonalization = true))
    }

    @Test fun `new correction stays pending until a second voice turn and pending is never used`() {
        val repository = repository()
        val dictionary = dictionary(repository)
        val first = record(repository, turn("請用Zorblat測試。", "請用Zorbit測試。"), turnId = 1L).single()
        assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED, first.status)
        assertFalse(first.rule!!.active)

        // Pending stays local: no replacement, no STT hint, no LLM vocabulary, no guard alias.
        assertEquals("下次Zorblat", dictionary.applyCorrections("下次Zorblat", includePersonalization = true))
        assertFalse(dictionary.buildWhisperPrompt(includePersonalization = true).split('、').contains("Zorbit"))
        assertFalse(dictionary.buildLlmVocabularyHint("下次Zorblat", includePersonalization = true).contains("Zorbit"))
        assertFalse(dictionary.getSpellingAliases(includeLearned = true).containsKey("Zorblat"))

        // The same voice turn finalized twice is still one piece of evidence.
        assertEquals(CorrectionRecordStatus.EVIDENCE_RECORDED,
            record(repository, turn("請用Zorblat測試。", "請用Zorbit測試。"), turnId = 1L).single().status)

        val second = record(repository, turn("再用Zorblat一次。", "再用Zorbit一次。"), turnId = 2L).single()
        assertEquals(CorrectionRecordStatus.ACTIVATED, second.status)
        assertEquals("下次Zorbit", dictionary.applyCorrections("下次Zorblat", includePersonalization = true))
        assertEquals(mapOf("Zorblat" to "Zorbit"), repository.getLearnedSpellingAliases())
        assertTrue(dictionary.buildWhisperPrompt(includePersonalization = true).split('、').contains("Zorbit"))
        assertEquals(1, repository.getStats().activeCorrectionRuleCount)
        assertEquals(0, repository.getStats().pendingCorrectionRuleCount)
    }

    @Test fun `user confirmation in settings activates a pending rule`() {
        val repository = repository()
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Orbyt", "Orbit", true, turnId = 1L)
        assertEquals(1, repository.getStats().pendingCorrectionRuleCount)
        assertTrue(repository.confirmVoiceCorrection("Orbyt", "Orbit"))
        val rule = repository.getVoiceCorrections().single()
        assertTrue(rule.active)
        assertTrue(rule.confirmedByUser)
        assertEquals("用Orbit", dictionary(repository).applyCorrections("用Orbyt", includePersonalization = true))
    }

    // ---- Spec 3: never learn AI-generated text ----

    @Test fun `E21 reverting an AI rewrite is not learned while an STT typo in the same turn is`() {
        val stt = "我先檢查然後用Kotlun部署。"
        val aiCommitted = "我先檢查，接著用Kotlun部署。"
        val learned = turn(aiCommitted, "我先檢查，然後用Kotlun部署。", "我先檢查，然後用Kotlin部署。", stt = stt)
        assertEquals(listOf("Kotlun" to "Kotlin"), learned.pairs())
    }

    @Test fun `translation and compose outputs are never tracked for learning`() {
        val result = TranscriptionPipeline.Result(text = "AI cleaned text", learningBaseline = "stt text")
        assertEquals("stt text", VoiceLearningGate.trackingBaseline(VoiceTask.Dictation, result))
        assertNull(VoiceLearningGate.trackingBaseline(VoiceTask.Dictation, result.copy(learningBaseline = "")))
        val request = TranslationRequest.create(listOf(TranslationLanguage.ENGLISH))
        assertNull(VoiceLearningGate.trackingBaseline(VoiceTask.Translation(request), result))
        assertNull(VoiceLearningGate.trackingBaseline(VoiceTask.Compose, result))
    }

    // ---- Spec 4: scope, rejection list, reverse edits, bounds ----

    @Test fun `Han rule keeps its Chinese scope but never replaces literally, Latin rule applies anywhere`() {
        val repository = repository()
        for (turnId in 1L..2L) {
            record(repository, turn("這家清涼很近。", "這家診療很近。"), turnId)
            record(repository, turn("用Kotlun寫。", "用Kotlin寫。"), turnId)
        }
        val chinese = repository.getVoiceCorrections().single { it.wrongText == "清涼" }
        assertEquals(CorrectionScope.CHINESE, chinese.scope)
        val dictionary = dictionary(repository)
        // Learned Han rules never replace literally (no word boundaries). A Han->Han pair is an STT
        // hint only (2026-10-03 gap 3): not a guard alias, so the LLM cannot carry it across contexts.
        assertEquals("清涼所很近", dictionary.applyCorrections("清涼所很近", includePersonalization = true))
        assertNull(dictionary.getSpellingAliases(includeLearned = true)["清涼"])
        assertEquals("清涼な風です。Kotlinで書く。",
            dictionary.applyCorrections("清涼な風です。Kotlunで書く。", includePersonalization = true))
    }

    @Test fun `E16 undo removes the rule and puts it on the rejected list`() {
        val repository = repository()
        val dictionary = dictionary(repository)
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Zorblat", "Zorbit", true, turnId = 1L)
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Zorblat", "Zorbit", true, turnId = 2L)
        assertEquals("用Zorbit", dictionary.applyCorrections("用Zorblat", includePersonalization = true))

        assertTrue(repository.undoLast())
        assertEquals("用Zorblat", dictionary.applyCorrections("用Zorblat", includePersonalization = true))
        assertFalse(dictionary.buildWhisperPrompt(includePersonalization = true).split('、').contains("Zorbit"))
        assertTrue(repository.isRejectedCorrection("Zorblat", "Zorbit"))
        assertEquals(CorrectionRecordStatus.REJECTED,
            repository.recordVoiceCorrection(LearningLanguage.MIXED, "Zorblat", "Zorbit", true, turnId = 3L).status)
    }

    @Test fun `deleted rule is never relearned and an edited rule is confirmed`() {
        val repository = repository()
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Orbyt", "Orbit", true, turnId = 1L)
        assertTrue(repository.deleteVoiceCorrection("Orbyt", "Orbit"))
        assertEquals(CorrectionRecordStatus.REJECTED,
            repository.recordVoiceCorrection(LearningLanguage.MIXED, "Orbyt", "Orbit", true, turnId = 2L).status)

        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Zorblat", "Zorbt", true, turnId = 3L)
        val edited = repository.editVoiceCorrection("Zorblat", "Zorbt", "Zorblat", "Zorbit")
        assertEquals(CorrectionRecordStatus.ACTIVATED, edited.status)
        val rule = repository.getVoiceCorrections().single()
        assertEquals("Zorblat" to "Zorbit", rule.wrongText to rule.correctedText)
        assertTrue(rule.active && rule.confirmedByUser)
        // Editing into a meaning change is refused and keeps the existing rule.
        assertEquals(CorrectionRecordStatus.REJECTED,
            repository.editVoiceCorrection("Zorblat", "Zorbit", "三點", "四點").status)
        assertEquals(listOf("Zorblat"), repository.getVoiceCorrections().map { it.wrongText })
    }

    @Test fun `changing a learned word back demotes it instead of learning both directions`() {
        val repository = repository()
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Kotlun", "Kotlin", true, turnId = 1L)
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Kotlun", "Kotlin", true, turnId = 2L)
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Kotlin", "Kotlun", true, turnId = 3L)
        assertTrue(repository.getActiveVoiceCorrections().isEmpty())
        assertTrue(repository.isRejectedCorrection("Kotlun", "Kotlin"))
        assertEquals("用Kotlun", dictionary(repository).applyCorrections("用Kotlun", includePersonalization = true))
    }

    @Test fun `rule length and total count are bounded`() {
        val repository = PersonalizationRepository(MemoryStorage(), { now }, PersonalizationLimits(maxCorrectionRules = 3))
        assertEquals(CorrectionRecordStatus.REJECTED, repository.recordVoiceCorrection(
            LearningLanguage.MIXED, "Abcdefghijklmnopqrstuvwxyz", "Abcdefghijklmnopqrstuvwxyy", true, turnId = 1L).status)
        for (index in 0 until 6) {
            now += 1
            repository.recordVoiceCorrection(LearningLanguage.MIXED, "Zorb${'a' + index}t", "Zorb${'a' + index}x", true, turnId = index.toLong())
        }
        assertEquals(3, repository.getVoiceCorrections().size)
    }

    // ---- Spec 6: only the corrected word is a prompt hint ----

    @Test fun `STT hint is the corrected word without surrounding sentence context`() {
        val repository = repository()
        for (turnId in 1L..2L) {
            record(repository, turn("請檢查吉他哈布的設定。", "請檢查GitHub的設定。"), turnId)
            record(repository, turn("我代表新義豐公司出席。", "我代表新義豊公司出席。"), turnId)
        }
        assertEquals(2, repository.getActiveVoiceCorrections().size)
        // A one-character fix inside a complete short CJK term must not disappear.
        assertEquals(setOf("GitHub", "新義豊公司"), repository.getPromptWords().toSet())
        val hints = dictionary(repository).buildWhisperPrompt(includePersonalization = true).split('、')
        assertTrue(hints.contains("GitHub"))
        assertTrue(hints.contains("新義豊公司"))
        // The built-in vocabulary independently contains 代表取締役. Reject the source
        // sentence's attached context, not that unrelated, pre-existing spelling hint.
        assertTrue(hints.none { it.contains("代表新義") || it.contains("公司出席") || it.contains("查GitHub") || it.contains("GitHub的") })
        // A learned Han->Han fix is neither a literal replacement nor a guard alias (gap 3);
        // only the Han->ASCII pair stays an alias.
        assertNull(dictionary(repository).getSpellingAliases(includeLearned = true)["新義豐公司"])
    }

    // ---- Spec 9: migration of v1 data ----

    @Test fun `v1 rules preserve activation behind the fact filter and keep a pending rule`() {
        val storage = MemoryStorage()
        fun rule(wrong: String, corrected: String, active: Boolean, prompt: String = corrected) = JSONObject()
            .put("language", "MIXED").put("wrongText", wrong).put("correctedText", corrected)
            .put("promptText", prompt).put("evidenceCount", 1).put("highConfidenceSeen", true)
            .put("active", active).put("lastSeenAtMillis", 5L)
        storage.update(mapOf(
            "schema_version" to 1,
            "voice_corrections_v1" to JSONArray()
                .put(rule("Kotlun", "Kotlin", true))
                .put(rule("下午三點開", "下午四點開", true))
                .put(rule("不要", "可以", true))
                .put(rule("新義豐公司", "新義豊公司", true))
                .put(rule("Orbyt", "Orbit", false))
                .toString(),
            "candidate_usage_v1" to "[]"
        ))
        val repository = repository(storage)
        val migrated = repository.getVoiceCorrections().associate { it.wrongText to it }
        assertEquals(setOf("Kotlun", "新義豐公司", "Orbyt"), migrated.keys)
        assertTrue(migrated.getValue("Kotlun").active)
        assertTrue(migrated.getValue("新義豐公司").active)
        assertFalse("Upgrade is not user confirmation", migrated.getValue("Orbyt").active)
        assertEquals(CorrectionScope.LATIN, migrated.getValue("Kotlun").scope)
        assertEquals(CorrectionScope.ANY, migrated.getValue("新義豐公司").scope)
        // Migration preserves a bounded whole short term, never the surrounding sentence.
        assertEquals("新義豊公司", migrated.getValue("新義豐公司").promptText)
        assertEquals(2, storage.getInt("schema_version", 0))
        // Reload from the migrated store gives the same rules.
        assertEquals(migrated.keys, repository(storage).getVoiceCorrections().map { it.wrongText }.toSet())
        assertEquals(setOf("Kotlun", "新義豐公司"),
            repository(storage).getActiveVoiceCorrections().map { it.wrongText }.toSet())
    }

    @Test fun `failed migration never clears the user's stored data`() {
        val storage = MemoryStorage()
        storage.update(mapOf("schema_version" to 1, "voice_corrections_v1" to "{not json"))
        val repository = repository(storage)
        assertTrue(repository.getVoiceCorrections().isEmpty())
        assertEquals("{not json", storage.getString("voice_corrections_v1", null))
        assertEquals(1, storage.getInt("schema_version", 0))
    }

    @Test fun `clear all also clears the rejected list`() {
        val repository = repository()
        repository.recordVoiceCorrection(LearningLanguage.MIXED, "Orbyt", "Orbit", true, turnId = 1L)
        repository.deleteVoiceCorrection("Orbyt", "Orbit")
        repository.clearAll()
        assertFalse(repository.isRejectedCorrection("Orbyt", "Orbit"))
    }
}

internal class MemoryStorage : LearningStorage {
    private val values = mutableMapOf<String, Any>()
    override fun getString(key: String, defaultValue: String?) = values[key] as? String ?: defaultValue
    override fun getInt(key: String, defaultValue: Int) = values[key] as? Int ?: defaultValue
    override fun getBoolean(key: String, defaultValue: Boolean) = values[key] as? Boolean ?: defaultValue
    override fun update(values: Map<String, Any?>) {
        values.forEach { (key, value) -> if (value == null) this.values.remove(key) else this.values[key] = value }
    }
}
