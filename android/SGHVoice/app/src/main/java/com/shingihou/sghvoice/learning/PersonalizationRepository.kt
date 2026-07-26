package com.shingihou.sghvoice.learning

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/**
 * Language/mode namespace used by the personalization layer.
 *
 * The keyboard engines remain responsible for producing canonical input keys:
 * Zhuyin should pass its normalized reading, Japanese should pass normalized
 * hiragana, and English should pass a lowercase word or prefix.
 */
enum class LearningLanguage {
    ZHUYIN,
    JAPANESE,
    ENGLISH,
    MIXED
}

data class CandidateUsage(
    val language: LearningLanguage,
    val inputKey: String,
    val candidate: String,
    val selectedCount: Int,
    val lastUsedAtMillis: Long
)

data class VoiceCorrectionRule(
    val language: LearningLanguage,
    val wrongText: String,
    val correctedText: String,
    val promptText: String,
    val evidenceCount: Int,
    val highConfidenceSeen: Boolean,
    val active: Boolean,
    val lastSeenAtMillis: Long
)

enum class CorrectionRecordStatus {
    REJECTED,
    EVIDENCE_RECORDED,
    ACTIVATED
}

data class CorrectionRecordResult(
    val status: CorrectionRecordStatus,
    val rule: VoiceCorrectionRule? = null
)

data class PersonalizationStats(
    val enabled: Boolean,
    val candidateRecordCount: Int,
    val totalCandidateSelections: Long,
    val correctionRuleCount: Int,
    val activeCorrectionRuleCount: Int,
    val totalCorrectionEvidence: Long
)

data class PersonalizationLimits(
    val maxCandidateRecords: Int = 2_000,
    val maxCorrectionRules: Int = 500,
    val lowConfidenceEvidenceThreshold: Int = 2
) {
    init {
        require(maxCandidateRecords > 0)
        require(maxCorrectionRules > 0)
        require(lowConfidenceEvidenceThreshold > 0)
    }
}

/**
 * Versioned, bounded, on-device personalization repository.
 *
 * High-confidence voice corrections become active after the first observation.
 * Lower-confidence observations require [PersonalizationLimits.lowConfidenceEvidenceThreshold]
 * identical observations. The repository never uploads learned data. Calling
 * [getPromptWords] only returns local values; the caller must separately decide
 * whether any of them may be included in a network request.
 */
class PersonalizationRepository internal constructor(
    private val storage: LearningStorage,
    private val clockMillis: () -> Long = System::currentTimeMillis,
    private val limits: PersonalizationLimits = PersonalizationLimits()
) {

    companion object {
        const val PREFERENCE_NAME = "sgh_voice_personalization"
        const val SCHEMA_VERSION = 1

        private const val KEY_SCHEMA_VERSION = "schema_version"
        private const val KEY_ENABLED = "enabled"
        private const val KEY_CANDIDATE_USAGE = "candidate_usage_v1"
        private const val KEY_VOICE_CORRECTIONS = "voice_corrections_v1"
        private const val KEY_LAST_UNDO = "last_undo_v1"

        private const val MAX_INPUT_KEY_CODE_POINTS = 128
        private const val MAX_CANDIDATE_CODE_POINTS = 128
        private const val MAX_CORRECTION_CODE_POINTS = 64

        @Volatile
        private var instance: PersonalizationRepository? = null

        fun getInstance(context: Context): PersonalizationRepository {
            return instance ?: synchronized(this) {
                instance ?: PersonalizationRepository(
                    SharedPreferencesLearningStorage(
                        context.applicationContext.getSharedPreferences(
                            PREFERENCE_NAME,
                            Context.MODE_PRIVATE
                        )
                    )
                ).also { instance = it }
            }
        }
    }

    private data class CandidateKey(
        val language: LearningLanguage,
        val inputKey: String,
        val candidate: String
    )

    private data class CorrectionKey(
        val language: LearningLanguage,
        val wrongText: String,
        val correctedText: String
    )

    private sealed interface UndoRecord {
        data class Candidate(
            val key: CandidateKey,
            val previous: CandidateUsage?,
            val evicted: List<CandidateUsage>
        ) : UndoRecord

        data class Correction(
            val key: CorrectionKey,
            val previous: VoiceCorrectionRule?,
            val evicted: List<VoiceCorrectionRule>
        ) : UndoRecord
    }

    private val candidateUsages = linkedMapOf<CandidateKey, CandidateUsage>()
    private val correctionRules = linkedMapOf<CorrectionKey, VoiceCorrectionRule>()

    init {
        initializeSchema()
        loadCandidateUsages()
        loadCorrectionRules()
        enforceBoundsAndPersistIfNeeded()
    }

    @Synchronized
    fun isEnabled(): Boolean = storage.getBoolean(KEY_ENABLED, true)

    @Synchronized
    fun setEnabled(enabled: Boolean) {
        storage.update(mapOf(KEY_ENABLED to enabled))
    }

    /**
     * Records explicit positive feedback from a candidate selection.
     *
     * Automatic default commits should only call this after the next stable
     * word boundary, so a candidate immediately corrected by the user is not
     * counted as a positive selection.
     */
    @Synchronized
    fun recordCandidateSelection(
        language: LearningLanguage,
        inputKey: String,
        candidate: String
    ): CandidateUsage? {
        if (!isEnabled()) return null

        val normalizedKey = normalizeInputKey(language, inputKey) ?: return null
        val normalizedCandidate = normalizeCandidate(candidate) ?: return null
        val key = CandidateKey(language, normalizedKey, normalizedCandidate)
        val previous = candidateUsages[key]
        val updated = CandidateUsage(
            language = language,
            inputKey = normalizedKey,
            candidate = normalizedCandidate,
            selectedCount = incrementSaturated(previous?.selectedCount ?: 0),
            lastUsedAtMillis = clockMillis()
        )
        candidateUsages[key] = updated
        val evicted = pruneCandidateUsages(protectedKey = key)

        persistCandidateUsages(
            undo = UndoRecord.Candidate(
                key = key,
                previous = previous,
                evicted = evicted
            )
        )
        return updated
    }

    /**
     * Reorders an existing candidate list without adding or removing values.
     * Unlearned candidates retain their original relative order.
     */
    @Synchronized
    fun rankCandidates(
        language: LearningLanguage,
        inputKey: String,
        candidates: List<String>
    ): List<String> {
        if (!isEnabled() || candidates.size < 2) return candidates.toList()
        val normalizedKey = normalizeInputKey(language, inputKey) ?: return candidates.toList()

        return candidates.withIndex()
            .sortedWith(
                compareByDescending<IndexedValue<String>> { indexed ->
                    val candidate = normalizeCandidate(indexed.value)
                    if (candidate == null) {
                        0
                    } else {
                        candidateUsages[
                            CandidateKey(language, normalizedKey, candidate)
                        ]?.selectedCount ?: 0
                    }
                }.thenByDescending { indexed ->
                    val candidate = normalizeCandidate(indexed.value)
                    if (candidate == null) {
                        0L
                    } else {
                        candidateUsages[
                            CandidateKey(language, normalizedKey, candidate)
                        ]?.lastUsedAtMillis ?: 0L
                    }
                }.thenBy { it.index }
            )
            .map { it.value }
    }

    @Synchronized
    fun getCandidateUsage(
        language: LearningLanguage,
        inputKey: String,
        candidate: String
    ): CandidateUsage? {
        val normalizedKey = normalizeInputKey(language, inputKey) ?: return null
        val normalizedCandidate = normalizeCandidate(candidate) ?: return null
        return candidateUsages[CandidateKey(language, normalizedKey, normalizedCandidate)]
    }

    /**
     * Adds one correction observation.
     *
     * A high-confidence result from [VoiceCorrectionTracker] is activated on
     * the first observation. Low-confidence evidence is retained but does not
     * become active until the same pair reaches the configured threshold.
     */
    @Synchronized
    fun recordVoiceCorrection(
        language: LearningLanguage,
        wrongText: String,
        correctedText: String,
        highConfidence: Boolean,
        promptText: String = correctedText
    ): CorrectionRecordResult {
        if (!isEnabled()) {
            return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        }

        val wrong = normalizeCorrectionText(wrongText)
            ?: return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        val corrected = normalizeCorrectionText(correctedText)
            ?: return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        if (wrong == corrected) {
            return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        }
        val normalizedPrompt = normalizeCorrectionText(promptText) ?: corrected

        val key = CorrectionKey(language, wrong, corrected)
        val previous = correctionRules[key]
        val evidenceCount = incrementSaturated(previous?.evidenceCount ?: 0)
        val sawHighConfidence = highConfidence || previous?.highConfidenceSeen == true
        val active = previous?.active == true ||
            sawHighConfidence ||
            evidenceCount >= limits.lowConfidenceEvidenceThreshold
        val updated = VoiceCorrectionRule(
            language = language,
            wrongText = wrong,
            correctedText = corrected,
            promptText = normalizedPrompt,
            evidenceCount = evidenceCount,
            highConfidenceSeen = sawHighConfidence,
            active = active,
            lastSeenAtMillis = clockMillis()
        )
        correctionRules[key] = updated
        val evicted = pruneCorrectionRules(protectedKey = key)

        persistCorrectionRules(
            undo = UndoRecord.Correction(
                key = key,
                previous = previous,
                evicted = evicted
            )
        )
        return CorrectionRecordResult(
            status = if (active) {
                CorrectionRecordStatus.ACTIVATED
            } else {
                CorrectionRecordStatus.EVIDENCE_RECORDED
            },
            rule = updated
        )
    }

    /**
     * Convenience overload for the output of [VoiceCorrectionTracker].
     */
    fun recordVoiceCorrection(
        language: LearningLanguage,
        replacement: CorrectionReplacement,
        highConfidence: Boolean
    ): CorrectionRecordResult {
        return recordVoiceCorrection(
            language = language,
            wrongText = replacement.wrongText,
            correctedText = replacement.correctedText,
            highConfidence = highConfidence,
            promptText = replacement.suggestedPromptText
        )
    }

    @Synchronized
    fun getActiveVoiceCorrections(
        language: LearningLanguage? = null
    ): List<VoiceCorrectionRule> {
        return correctionRules.values
            .asSequence()
            .filter { it.active }
            .filter { rule ->
                language == null ||
                    rule.language == language ||
                    rule.language == LearningLanguage.MIXED
            }
            .sortedWith(
                compareByDescending<VoiceCorrectionRule> { it.highConfidenceSeen }
                    .thenByDescending { it.evidenceCount }
                    .thenByDescending { it.lastSeenAtMillis }
            )
            .toList()
    }

    /**
     * Returns corrected terms suitable for an optional Whisper prompt.
     *
     * This method has no networking side effect. In particular, calling code
     * must apply its own privacy/consent decision before uploading these terms.
     */
    @Synchronized
    fun getPromptWords(
        language: LearningLanguage? = null,
        limit: Int = 50
    ): List<String> {
        if (!isEnabled() || limit <= 0) return emptyList()
        return getActiveVoiceCorrections(language)
            .asSequence()
            .map { it.promptText }
            .distinct()
            .take(limit)
            .toList()
    }

    /**
     * Reverts the latest candidate-selection or voice-correction mutation,
     * including any record evicted by the bounded-store policy.
     */
    @Synchronized
    fun undoLast(): Boolean {
        val undo = decodeUndo(storage.getString(KEY_LAST_UNDO, null)) ?: return false
        when (undo) {
            is UndoRecord.Candidate -> {
                candidateUsages.remove(undo.key)
                undo.previous?.let { candidateUsages[candidateKeyOf(it)] = it }
                undo.evicted.forEach { candidateUsages[candidateKeyOf(it)] = it }
                storage.update(
                    mapOf(
                        KEY_CANDIDATE_USAGE to encodeCandidateUsages(),
                        KEY_LAST_UNDO to null
                    )
                )
            }

            is UndoRecord.Correction -> {
                correctionRules.remove(undo.key)
                undo.previous?.let { correctionRules[correctionKeyOf(it)] = it }
                undo.evicted.forEach { correctionRules[correctionKeyOf(it)] = it }
                storage.update(
                    mapOf(
                        KEY_VOICE_CORRECTIONS to encodeCorrectionRules(),
                        KEY_LAST_UNDO to null
                    )
                )
            }
        }
        return true
    }

    /**
     * Removes learned candidate and correction data while preserving the user's
     * enabled/disabled preference.
     */
    @Synchronized
    fun clearAll() {
        candidateUsages.clear()
        correctionRules.clear()
        storage.update(
            mapOf(
                KEY_CANDIDATE_USAGE to null,
                KEY_VOICE_CORRECTIONS to null,
                KEY_LAST_UNDO to null,
                KEY_SCHEMA_VERSION to SCHEMA_VERSION
            )
        )
    }

    @Synchronized
    fun getStats(): PersonalizationStats {
        return PersonalizationStats(
            enabled = isEnabled(),
            candidateRecordCount = candidateUsages.size,
            totalCandidateSelections = candidateUsages.values.sumOf {
                it.selectedCount.toLong()
            },
            correctionRuleCount = correctionRules.size,
            activeCorrectionRuleCount = correctionRules.values.count { it.active },
            totalCorrectionEvidence = correctionRules.values.sumOf {
                it.evidenceCount.toLong()
            }
        )
    }

    private fun initializeSchema() {
        val storedVersion = storage.getInt(KEY_SCHEMA_VERSION, 0)
        if (storedVersion == SCHEMA_VERSION) return

        // No older schema exists yet. Unknown/future payloads are discarded
        // rather than interpreted incorrectly, while the enabled flag remains.
        storage.update(
            mapOf(
                KEY_SCHEMA_VERSION to SCHEMA_VERSION,
                KEY_CANDIDATE_USAGE to null,
                KEY_VOICE_CORRECTIONS to null,
                KEY_LAST_UNDO to null
            )
        )
    }

    private fun loadCandidateUsages() {
        val encoded = storage.getString(KEY_CANDIDATE_USAGE, null) ?: return
        try {
            val array = JSONArray(encoded)
            repeat(array.length()) { index ->
                decodeCandidateUsage(array.optJSONObject(index))?.let { usage ->
                    candidateUsages[candidateKeyOf(usage)] = usage
                }
            }
        } catch (_: Exception) {
            candidateUsages.clear()
        }
    }

    private fun loadCorrectionRules() {
        val encoded = storage.getString(KEY_VOICE_CORRECTIONS, null) ?: return
        try {
            val array = JSONArray(encoded)
            repeat(array.length()) { index ->
                decodeCorrectionRule(array.optJSONObject(index))?.let { rule ->
                    correctionRules[correctionKeyOf(rule)] = rule
                }
            }
        } catch (_: Exception) {
            correctionRules.clear()
        }
    }

    private fun enforceBoundsAndPersistIfNeeded() {
        val candidatesEvicted = pruneCandidateUsages()
        val correctionsEvicted = pruneCorrectionRules()
        val updates = linkedMapOf<String, Any?>()
        if (candidatesEvicted.isNotEmpty()) {
            updates[KEY_CANDIDATE_USAGE] = encodeCandidateUsages()
        }
        if (correctionsEvicted.isNotEmpty()) {
            updates[KEY_VOICE_CORRECTIONS] = encodeCorrectionRules()
        }
        if (updates.isNotEmpty()) storage.update(updates)
    }

    private fun pruneCandidateUsages(
        protectedKey: CandidateKey? = null
    ): List<CandidateUsage> {
        val evicted = mutableListOf<CandidateUsage>()
        while (candidateUsages.size > limits.maxCandidateRecords) {
            val victim = candidateUsages
                .filterKeys { it != protectedKey }
                .values
                .minWithOrNull(
                    compareBy<CandidateUsage> { it.selectedCount }
                        .thenBy { it.lastUsedAtMillis }
                ) ?: break
            candidateUsages.remove(candidateKeyOf(victim))
            evicted += victim
        }
        return evicted
    }

    private fun pruneCorrectionRules(
        protectedKey: CorrectionKey? = null
    ): List<VoiceCorrectionRule> {
        val evicted = mutableListOf<VoiceCorrectionRule>()
        while (correctionRules.size > limits.maxCorrectionRules) {
            val victim = correctionRules
                .filterKeys { it != protectedKey }
                .values
                .minWithOrNull(
                    compareBy<VoiceCorrectionRule> { it.active }
                        .thenBy { it.evidenceCount }
                        .thenBy { it.lastSeenAtMillis }
                ) ?: break
            correctionRules.remove(correctionKeyOf(victim))
            evicted += victim
        }
        return evicted
    }

    private fun persistCandidateUsages(undo: UndoRecord.Candidate) {
        storage.update(
            mapOf(
                KEY_CANDIDATE_USAGE to encodeCandidateUsages(),
                KEY_LAST_UNDO to encodeUndo(undo)
            )
        )
    }

    private fun persistCorrectionRules(undo: UndoRecord.Correction) {
        storage.update(
            mapOf(
                KEY_VOICE_CORRECTIONS to encodeCorrectionRules(),
                KEY_LAST_UNDO to encodeUndo(undo)
            )
        )
    }

    private fun encodeCandidateUsages(): String {
        val array = JSONArray()
        candidateUsages.values.forEach { array.put(encodeCandidateUsage(it)) }
        return array.toString()
    }

    private fun encodeCorrectionRules(): String {
        val array = JSONArray()
        correctionRules.values.forEach { array.put(encodeCorrectionRule(it)) }
        return array.toString()
    }

    private fun encodeCandidateUsage(usage: CandidateUsage): JSONObject =
        JSONObject()
            .put("language", usage.language.name)
            .put("inputKey", usage.inputKey)
            .put("candidate", usage.candidate)
            .put("selectedCount", usage.selectedCount)
            .put("lastUsedAtMillis", usage.lastUsedAtMillis)

    private fun decodeCandidateUsage(value: JSONObject?): CandidateUsage? {
        value ?: return null
        return try {
            val usage = CandidateUsage(
                language = LearningLanguage.valueOf(value.getString("language")),
                inputKey = value.getString("inputKey"),
                candidate = value.getString("candidate"),
                selectedCount = value.getInt("selectedCount").coerceAtLeast(1),
                lastUsedAtMillis = value.getLong("lastUsedAtMillis")
            )
            if (normalizeInputKey(usage.language, usage.inputKey) == null ||
                normalizeCandidate(usage.candidate) == null
            ) {
                null
            } else {
                usage
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun encodeCorrectionRule(rule: VoiceCorrectionRule): JSONObject =
        JSONObject()
            .put("language", rule.language.name)
            .put("wrongText", rule.wrongText)
            .put("correctedText", rule.correctedText)
            .put("promptText", rule.promptText)
            .put("evidenceCount", rule.evidenceCount)
            .put("highConfidenceSeen", rule.highConfidenceSeen)
            .put("active", rule.active)
            .put("lastSeenAtMillis", rule.lastSeenAtMillis)

    private fun decodeCorrectionRule(value: JSONObject?): VoiceCorrectionRule? {
        value ?: return null
        return try {
            val correctedText = value.getString("correctedText")
            val promptText = normalizeCorrectionText(
                value.optString("promptText", correctedText)
            ) ?: correctedText
            val rule = VoiceCorrectionRule(
                language = LearningLanguage.valueOf(value.getString("language")),
                wrongText = value.getString("wrongText"),
                correctedText = correctedText,
                promptText = promptText,
                evidenceCount = value.getInt("evidenceCount").coerceAtLeast(1),
                highConfidenceSeen = value.optBoolean("highConfidenceSeen", false),
                active = value.optBoolean("active", false),
                lastSeenAtMillis = value.getLong("lastSeenAtMillis")
            )
            if (normalizeCorrectionText(rule.wrongText) == null ||
                normalizeCorrectionText(rule.correctedText) == null ||
                rule.wrongText == rule.correctedText
            ) {
                null
            } else {
                rule
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun encodeUndo(undo: UndoRecord): String {
        return when (undo) {
            is UndoRecord.Candidate -> JSONObject()
                .put("type", "candidate")
                .put("language", undo.key.language.name)
                .put("inputKey", undo.key.inputKey)
                .put("candidate", undo.key.candidate)
                .put(
                    "previous",
                    undo.previous?.let(::encodeCandidateUsage) ?: JSONObject.NULL
                )
                .put(
                    "evicted",
                    JSONArray().apply {
                        undo.evicted.forEach { put(encodeCandidateUsage(it)) }
                    }
                )
                .toString()

            is UndoRecord.Correction -> JSONObject()
                .put("type", "correction")
                .put("language", undo.key.language.name)
                .put("wrongText", undo.key.wrongText)
                .put("correctedText", undo.key.correctedText)
                .put(
                    "previous",
                    undo.previous?.let(::encodeCorrectionRule) ?: JSONObject.NULL
                )
                .put(
                    "evicted",
                    JSONArray().apply {
                        undo.evicted.forEach { put(encodeCorrectionRule(it)) }
                    }
                )
                .toString()
        }
    }

    private fun decodeUndo(encoded: String?): UndoRecord? {
        if (encoded.isNullOrBlank()) return null
        return try {
            val obj = JSONObject(encoded)
            when (obj.getString("type")) {
                "candidate" -> {
                    val language = LearningLanguage.valueOf(obj.getString("language"))
                    val previous = if (obj.isNull("previous")) {
                        null
                    } else {
                        decodeCandidateUsage(obj.optJSONObject("previous"))
                    }
                    val evictedArray = obj.optJSONArray("evicted") ?: JSONArray()
                    val evicted = buildList {
                        repeat(evictedArray.length()) { index ->
                            decodeCandidateUsage(evictedArray.optJSONObject(index))?.let(::add)
                        }
                    }
                    UndoRecord.Candidate(
                        key = CandidateKey(
                            language = language,
                            inputKey = obj.getString("inputKey"),
                            candidate = obj.getString("candidate")
                        ),
                        previous = previous,
                        evicted = evicted
                    )
                }

                "correction" -> {
                    val language = LearningLanguage.valueOf(obj.getString("language"))
                    val previous = if (obj.isNull("previous")) {
                        null
                    } else {
                        decodeCorrectionRule(obj.optJSONObject("previous"))
                    }
                    val evictedArray = obj.optJSONArray("evicted") ?: JSONArray()
                    val evicted = buildList {
                        repeat(evictedArray.length()) { index ->
                            decodeCorrectionRule(evictedArray.optJSONObject(index))?.let(::add)
                        }
                    }
                    UndoRecord.Correction(
                        key = CorrectionKey(
                            language = language,
                            wrongText = obj.getString("wrongText"),
                            correctedText = obj.getString("correctedText")
                        ),
                        previous = previous,
                        evicted = evicted
                    )
                }

                else -> null
            }
        } catch (_: Exception) {
            null
        }
    }

    private fun candidateKeyOf(usage: CandidateUsage) =
        CandidateKey(usage.language, usage.inputKey, usage.candidate)

    private fun correctionKeyOf(rule: VoiceCorrectionRule) =
        CorrectionKey(rule.language, rule.wrongText, rule.correctedText)

    private fun normalizeInputKey(
        language: LearningLanguage,
        value: String
    ): String? {
        val normalized = value.trim().replace(Regex("\\s+"), " ").let {
            if (language == LearningLanguage.ENGLISH) {
                it.lowercase(Locale.ROOT)
            } else {
                it
            }
        }
        return normalized.takeIf {
            it.isNotBlank() &&
                it.codePointCount(0, it.length) <= MAX_INPUT_KEY_CODE_POINTS
        }
    }

    private fun normalizeCandidate(value: String): String? {
        val normalized = value.trim()
        return normalized.takeIf {
            it.isNotBlank() &&
                it.codePointCount(0, it.length) <= MAX_CANDIDATE_CODE_POINTS
        }
    }

    private fun normalizeCorrectionText(value: String): String? {
        val normalized = value.trim()
        return normalized.takeIf {
            it.isNotBlank() &&
                '\n' !in it &&
                '\r' !in it &&
                it.codePointCount(0, it.length) <= MAX_CORRECTION_CODE_POINTS &&
                it.codePoints().anyMatch(Character::isLetterOrDigit)
        }
    }

    private fun incrementSaturated(value: Int): Int =
        if (value == Int.MAX_VALUE) value else value + 1
}

internal interface LearningStorage {
    fun getString(key: String, defaultValue: String?): String?
    fun getInt(key: String, defaultValue: Int): Int
    fun getBoolean(key: String, defaultValue: Boolean): Boolean
    fun update(values: Map<String, Any?>)
}

private class SharedPreferencesLearningStorage(
    private val preferences: SharedPreferences
) : LearningStorage {
    override fun getString(key: String, defaultValue: String?): String? =
        preferences.getString(key, defaultValue)

    override fun getInt(key: String, defaultValue: Int): Int =
        preferences.getInt(key, defaultValue)

    override fun getBoolean(key: String, defaultValue: Boolean): Boolean =
        preferences.getBoolean(key, defaultValue)

    override fun update(values: Map<String, Any?>) {
        preferences.edit().apply {
            values.forEach { (key, value) ->
                when (value) {
                    null -> remove(key)
                    is String -> putString(key, value)
                    is Int -> putInt(key, value)
                    is Boolean -> putBoolean(key, value)
                    is Long -> putLong(key, value)
                    else -> error("Unsupported preference type: ${value::class.java.name}")
                }
            }
        }.apply()
    }
}
