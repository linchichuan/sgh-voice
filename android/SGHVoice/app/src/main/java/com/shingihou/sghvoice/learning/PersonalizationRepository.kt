package com.shingihou.sghvoice.learning

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import com.shingihou.sghvoice.processing.FactPreservation
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

/** Where a learned rule may be applied. Latin rules still require ASCII word boundaries. */
enum class CorrectionScope {
    /** Legacy (pre-v2) Han rule whose original context is unknown. */
    ANY,
    LATIN,
    CHINESE,
    JAPANESE
}

data class VoiceCorrectionRule(
    val language: LearningLanguage,
    val wrongText: String,
    val correctedText: String,
    val promptText: String,
    val evidenceCount: Int,
    val highConfidenceSeen: Boolean,
    /** true = 已生效 (eligible for safe hints/rules); false = 待確認 (local only). */
    val active: Boolean,
    val lastSeenAtMillis: Long,
    val scope: CorrectionScope = CorrectionScope.ANY,
    val confirmedByUser: Boolean = false,
    val lastTurnId: Long? = null
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
    val totalCorrectionEvidence: Long,
    val pendingCorrectionRuleCount: Int = 0
)

data class PersonalizationLimits(
    val maxCandidateRecords: Int = 2_000,
    val maxCorrectionRules: Int = 500,
    /** Distinct voice turns needed when the edit was never anchored on both sides. */
    val lowConfidenceEvidenceThreshold: Int = 3,
    /** Distinct voice turns needed before a short correction becomes 已生效. */
    val activationEvidenceThreshold: Int = 2,
    val maxRejectedCorrections: Int = 200
) {
    init {
        require(maxCandidateRecords > 0)
        require(maxCorrectionRules > 0)
        require(lowConfidenceEvidenceThreshold > 0)
        require(activationEvidenceThreshold > 0)
        require(maxRejectedCorrections > 0)
    }
}

/**
 * Versioned, bounded, on-device personalization repository.
 *
 * A learned voice correction starts as 待確認 (pending): it stays on this device only, is
 * never sent as a hint and never replaces text. It becomes 已生效 (active) only after the same pair was seen in
 * [PersonalizationLimits.activationEvidenceThreshold] different voice turns (more when the
 * edit was never anchored), or when the user confirms it in settings. Pairs that change a
 * number, unit, date, sign, currency or negation, style-word swaps and long rewrites are
 * never learned. Undone or deleted pairs go to a bounded rejection list and are not
 * relearned. Only short word pairs are stored. The repository never uploads learned data. Calling
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
        const val SCHEMA_VERSION = 2

        private const val KEY_SCHEMA_VERSION = "schema_version"
        private const val KEY_ENABLED = "enabled"
        private const val KEY_CANDIDATE_USAGE = "candidate_usage_v1"
        private const val KEY_VOICE_CORRECTIONS_V1 = "voice_corrections_v1"
        private const val KEY_LAST_UNDO_V1 = "last_undo_v1"
        private const val KEY_VOICE_CORRECTIONS = "voice_corrections_v2"
        private const val KEY_REJECTED_CORRECTIONS = "voice_corrections_rejected_v2"
        private const val KEY_LAST_UNDO = "last_undo_v2"

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

    private val rejectedCorrections = linkedSetOf<Pair<String, String>>()

    init {
        initializeSchema()
        loadCandidateUsages()
        loadCorrectionRules()
        loadRejectedCorrections()
        migrateV1CorrectionsIfNeeded()
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
     * Adds one correction observation from one voice turn.
     *
     * New pairs start 待確認. The same pair seen again in a different voice turn
     * ([turnId]) becomes 已生效; observations within one turn count once. Facts-changing
     * pairs, style-word swaps, long rewrites, rejected pairs and pairs longer than
     * [LearnedTerms.MAX_LEARNED_CODE_POINTS] are refused. Recording the reverse of an
     * existing rule (the user changed a learned word back) removes that rule instead.
     *
     * [promptText] is ignored: the hint is always derived from the pair itself (spec 6).
     */
    @Synchronized
    fun recordVoiceCorrection(
        language: LearningLanguage,
        wrongText: String,
        correctedText: String,
        highConfidence: Boolean,
        promptText: String = correctedText,
        turnId: Long? = null,
        scope: CorrectionScope? = null
    ): CorrectionRecordResult {
        if (!isEnabled()) {
            return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        }

        val wrong = normalizeCorrectionText(wrongText, LearnedTerms.MAX_LEARNED_CODE_POINTS)
            ?: return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        val corrected = normalizeCorrectionText(correctedText, LearnedTerms.MAX_LEARNED_CODE_POINTS)
            ?: return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        if (wrong == corrected || (wrong to corrected) in rejectedCorrections ||
            LearnedTerms.rejectionReason(wrong, corrected) != null
        ) {
            return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        }

        val reversed = correctionRules.keys.filter { it.wrongText == corrected && it.correctedText == wrong }
        if (reversed.isNotEmpty()) {
            // The user turned a learned word back: demote it, do not learn a ping-pong pair.
            reversed.forEach { key ->
                correctionRules.remove(key)
                addRejected(key.wrongText, key.correctedText)
            }
            storage.update(
                mapOf(
                    KEY_VOICE_CORRECTIONS to encodeCorrectionRules(),
                    KEY_REJECTED_CORRECTIONS to encodeRejected(),
                    KEY_LAST_UNDO to null
                )
            )
            return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        }

        val key = CorrectionKey(language, wrong, corrected)
        val previous = correctionRules[key]
        val sameTurn = turnId != null && previous?.lastTurnId == turnId
        val evidenceCount = if (sameTurn) previous!!.evidenceCount
            else incrementSaturated(previous?.evidenceCount ?: 0)
        val sawHighConfidence = highConfidence || previous?.highConfidenceSeen == true
        val threshold = if (sawHighConfidence) limits.activationEvidenceThreshold
            else maxOf(limits.activationEvidenceThreshold, limits.lowConfidenceEvidenceThreshold)
        val active = previous?.active == true || evidenceCount >= threshold
        val updated = VoiceCorrectionRule(
            language = language,
            wrongText = wrong,
            correctedText = corrected,
            promptText = LearnedTerms.promptTerm(wrong, corrected),
            evidenceCount = evidenceCount,
            highConfidenceSeen = sawHighConfidence,
            active = active,
            lastSeenAtMillis = clockMillis(),
            scope = previous?.scope ?: scope ?: LearnedTerms.scopeOf(wrong, corrected, language),
            confirmedByUser = previous?.confirmedByUser == true,
            lastTurnId = turnId ?: previous?.lastTurnId
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
        highConfidence: Boolean,
        turnId: Long? = null,
        scope: CorrectionScope? = null
    ): CorrectionRecordResult {
        return recordVoiceCorrection(
            language = language,
            wrongText = replacement.wrongText,
            correctedText = replacement.correctedText,
            highConfidence = highConfidence,
            promptText = replacement.suggestedPromptText,
            turnId = turnId,
            scope = scope
        )
    }

    /** All learned rules (待確認 and 已生效), most recent first, for the settings list. */
    @Synchronized
    fun getVoiceCorrections(): List<VoiceCorrectionRule> =
        correctionRules.values.sortedByDescending { it.lastSeenAtMillis }

    /** The user confirmed a rule in settings: it becomes 已生效 immediately. */
    @Synchronized
    fun confirmVoiceCorrection(wrongText: String, correctedText: String): Boolean {
        val keys = keysOf(wrongText, correctedText)
        if (keys.isEmpty()) return false
        keys.forEach { key ->
            correctionRules[key] = correctionRules.getValue(key).copy(active = true, confirmedByUser = true)
        }
        persistUserEdit(keys)
        return true
    }

    /**
     * Replaces a rule with the user's own spelling. The new pair is 已生效 and confirmed;
     * the old pair is rejected so it is not relearned. A pair that changes a fact is refused
     * and the existing rule stays unchanged.
     */
    @Synchronized
    fun editVoiceCorrection(
        wrongText: String,
        correctedText: String,
        newWrongText: String,
        newCorrectedText: String
    ): CorrectionRecordResult {
        val oldKeys = keysOf(wrongText, correctedText)
        val wrong = normalizeCorrectionText(newWrongText, MAX_CORRECTION_CODE_POINTS)
        val corrected = normalizeCorrectionText(newCorrectedText, MAX_CORRECTION_CODE_POINTS)
        if (oldKeys.isEmpty() || wrong == null || corrected == null || wrong == corrected ||
            !FactPreservation.correctionPreservesFacts(wrong, corrected)
        ) {
            return CorrectionRecordResult(CorrectionRecordStatus.REJECTED)
        }
        val old = correctionRules.getValue(oldKeys.first())
        oldKeys.forEach { correctionRules.remove(it) }
        if (old.wrongText != wrong || old.correctedText != corrected) addRejected(old.wrongText, old.correctedText)
        rejectedCorrections.remove(wrong to corrected)
        val key = CorrectionKey(old.language, wrong, corrected)
        val newScope = LearnedTerms.scopeOf(wrong, corrected, old.language)
        val updated = VoiceCorrectionRule(
            language = old.language,
            wrongText = wrong,
            correctedText = corrected,
            promptText = LearnedTerms.promptTerm(wrong, corrected),
            evidenceCount = maxOf(1, correctionRules[key]?.evidenceCount ?: old.evidenceCount),
            highConfidenceSeen = old.highConfidenceSeen,
            active = true,
            lastSeenAtMillis = clockMillis(),
            scope = if (newScope == CorrectionScope.LATIN || old.scope == CorrectionScope.LATIN) newScope else old.scope,
            confirmedByUser = true,
            lastTurnId = old.lastTurnId
        )
        correctionRules[key] = updated
        pruneCorrectionRules(protectedKey = key)
        persistUserEdit(oldKeys + key)
        return CorrectionRecordResult(CorrectionRecordStatus.ACTIVATED, updated)
    }

    /** Deletes a rule; the pair goes to the rejection list and is not learned again. */
    @Synchronized
    fun deleteVoiceCorrection(wrongText: String, correctedText: String): Boolean {
        val keys = keysOf(wrongText, correctedText)
        if (keys.isEmpty()) return false
        keys.forEach { correctionRules.remove(it) }
        addRejected(wrongText, correctedText)
        persistUserEdit(keys)
        return true
    }

    @Synchronized
    fun isRejectedCorrection(wrongText: String, correctedText: String): Boolean =
        (wrongText to correctedText) in rejectedCorrections

    /** 已生效 rules as known mishearing aliases (wrong -> right) for the dictation guard. */
    @Synchronized
    fun getLearnedSpellingAliases(): Map<String, String> {
        if (!isEnabled()) return emptyMap()
        return getActiveVoiceCorrections().asReversed()
            .associate { it.wrongText to it.correctedText }
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
                compareByDescending<VoiceCorrectionRule> { it.confirmedByUser }
                    .thenByDescending { it.highConfidenceSeen }
                    .thenByDescending { it.evidenceCount }
                    .thenByDescending { it.lastSeenAtMillis }
            )
            .toList()
    }

    /**
     * Returns corrected words of 已生效 rules, suitable for STT and AI spelling references.
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
            // Re-derive hints so an already-active schema-v2 rule with the old empty
            // single-Han prompt benefits too, without relearning or changing consent.
            .map { LearnedTerms.promptTerm(it.wrongText, it.correctedText) }
            .filter { it.isNotBlank() }
            .distinct()
            .take(limit)
            .toList()
    }

    /**
     * Reverts the latest candidate-selection or voice-correction learning, including any
     * record evicted by the bounded-store policy. An undone correction is removed and put
     * on the rejection list so the same pair is not learned again.
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
                undo.evicted.forEach { correctionRules[correctionKeyOf(it)] = it }
                addRejected(undo.key.wrongText, undo.key.correctedText)
                storage.update(
                    mapOf(
                        KEY_VOICE_CORRECTIONS to encodeCorrectionRules(),
                        KEY_REJECTED_CORRECTIONS to encodeRejected(),
                        KEY_LAST_UNDO to null
                    )
                )
            }
        }
        return true
    }

    /**
     * Removes learned candidate and correction data (including the rejection list) while
     * preserving the user's enabled/disabled preference.
     */
    @Synchronized
    fun clearAll() {
        candidateUsages.clear()
        correctionRules.clear()
        rejectedCorrections.clear()
        storage.update(
            mapOf(
                KEY_CANDIDATE_USAGE to null,
                KEY_VOICE_CORRECTIONS to null,
                KEY_VOICE_CORRECTIONS_V1 to null,
                KEY_REJECTED_CORRECTIONS to null,
                KEY_LAST_UNDO to null,
                KEY_LAST_UNDO_V1 to null,
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
            },
            pendingCorrectionRuleCount = correctionRules.values.count { !it.active }
        )
    }

    private fun keysOf(wrongText: String, correctedText: String): List<CorrectionKey> =
        correctionRules.keys.filter { it.wrongText == wrongText && it.correctedText == correctedText }

    private fun addRejected(wrong: String, corrected: String) {
        rejectedCorrections.remove(wrong to corrected)
        rejectedCorrections.add(wrong to corrected)
        while (rejectedCorrections.size > limits.maxRejectedCorrections) {
            rejectedCorrections.remove(rejectedCorrections.first())
        }
    }

    /** Settings edits are explicit user actions; they are not "the latest learning" to undo. */
    private fun persistUserEdit(touched: Collection<CorrectionKey>) {
        val undo = decodeUndo(storage.getString(KEY_LAST_UNDO, null))
        val clearUndo = undo is UndoRecord.Correction && touched.any {
            it.wrongText == undo.key.wrongText && it.correctedText == undo.key.correctedText
        }
        storage.update(
            buildMap {
                put(KEY_VOICE_CORRECTIONS, encodeCorrectionRules())
                put(KEY_REJECTED_CORRECTIONS, encodeRejected())
                if (clearUndo) put(KEY_LAST_UNDO, null)
            }
        )
    }

    private fun initializeSchema() {
        val storedVersion = storage.getInt(KEY_SCHEMA_VERSION, 0)
        if (storedVersion <= SCHEMA_VERSION) return

        // An unknown future payload is discarded rather than interpreted incorrectly,
        // while the enabled flag remains. Older versions are migrated, never discarded.
        storage.update(
            mapOf(
                KEY_SCHEMA_VERSION to SCHEMA_VERSION,
                KEY_CANDIDATE_USAGE to null,
                KEY_VOICE_CORRECTIONS to null,
                KEY_REJECTED_CORRECTIONS to null,
                KEY_LAST_UNDO to null
            )
        )
    }

    /**
     * v1 -> v2: retain each rule's activation state behind the fact filter. Pending or
     * unspecified rules must not acquire permission to appear in cloud hints on upgrade.
     * Each hint is re-derived without sentence context. The v1 payload is
     * removed only in the same write that stores the migrated rules. When the payload cannot
     * be parsed nothing is deleted and the migration is retried on the next start.
     */
    private fun migrateV1CorrectionsIfNeeded() {
        val storedVersion = storage.getInt(KEY_SCHEMA_VERSION, 0)
        if (storedVersion >= SCHEMA_VERSION) return
        val encoded = storage.getString(KEY_VOICE_CORRECTIONS_V1, null)
        if (encoded != null) {
            val array = try {
                JSONArray(encoded)
            } catch (_: Exception) {
                return
            }
            repeat(array.length()) { index ->
                val legacy = decodeCorrectionRule(array.optJSONObject(index)) ?: return@repeat
                if (!FactPreservation.correctionPreservesFacts(legacy.wrongText, legacy.correctedText)) {
                    return@repeat
                }
                val migrated = legacy.copy(
                    promptText = LearnedTerms.promptTerm(legacy.wrongText, legacy.correctedText),
                    active = legacy.active,
                    scope = legacyScope(legacy),
                    lastTurnId = null
                )
                correctionRules.putIfAbsent(correctionKeyOf(migrated), migrated)
            }
        }
        pruneCorrectionRules()
        storage.update(
            mapOf(
                KEY_VOICE_CORRECTIONS to encodeCorrectionRules(),
                KEY_VOICE_CORRECTIONS_V1 to null,
                KEY_LAST_UNDO_V1 to null,
                KEY_SCHEMA_VERSION to SCHEMA_VERSION
            )
        )
    }

    /** A legacy Han rule's original language is unknown, so it keeps applying everywhere. */
    private fun legacyScope(rule: VoiceCorrectionRule): CorrectionScope =
        when (val derived = LearnedTerms.scopeOf(rule.wrongText, rule.correctedText, rule.language)) {
            CorrectionScope.CHINESE -> CorrectionScope.ANY
            else -> derived
        }

    private fun loadRejectedCorrections() {
        val encoded = storage.getString(KEY_REJECTED_CORRECTIONS, null) ?: return
        try {
            val array = JSONArray(encoded)
            repeat(array.length()) { index ->
                val pair = array.optJSONArray(index) ?: return@repeat
                val wrong = pair.optString(0)
                val corrected = pair.optString(1)
                if (wrong.isNotEmpty() && corrected.isNotEmpty()) rejectedCorrections.add(wrong to corrected)
            }
        } catch (_: Exception) {
            rejectedCorrections.clear()
        }
    }

    private fun encodeRejected(): String {
        val array = JSONArray()
        rejectedCorrections.forEach { (wrong, corrected) -> array.put(JSONArray().put(wrong).put(corrected)) }
        return array.toString()
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
                        .thenBy { it.confirmedByUser }
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
            .put("scope", rule.scope.name)
            .put("confirmedByUser", rule.confirmedByUser)
            .apply { rule.lastTurnId?.let { put("lastTurnId", it) } }

    private fun decodeCorrectionRule(value: JSONObject?): VoiceCorrectionRule? {
        value ?: return null
        return try {
            val correctedText = value.getString("correctedText")
            val promptText = value.optString("promptText", correctedText).trim()
                .takeIf { it.isEmpty() || normalizeCorrectionText(it) != null } ?: ""
            val rule = VoiceCorrectionRule(
                language = LearningLanguage.valueOf(value.getString("language")),
                wrongText = value.getString("wrongText"),
                correctedText = correctedText,
                promptText = promptText,
                evidenceCount = value.getInt("evidenceCount").coerceAtLeast(1),
                highConfidenceSeen = value.optBoolean("highConfidenceSeen", false),
                active = value.optBoolean("active", false),
                lastSeenAtMillis = value.getLong("lastSeenAtMillis"),
                scope = runCatching { CorrectionScope.valueOf(value.optString("scope", "ANY")) }
                    .getOrDefault(CorrectionScope.ANY),
                confirmedByUser = value.optBoolean("confirmedByUser", false),
                lastTurnId = if (value.has("lastTurnId")) value.optLong("lastTurnId") else null
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

    private fun normalizeCorrectionText(
        value: String,
        maxCodePoints: Int = MAX_CORRECTION_CODE_POINTS
    ): String? {
        val normalized = value.trim()
        return normalized.takeIf {
            it.isNotBlank() &&
                '\n' !in it &&
                '\r' !in it &&
                it.codePointCount(0, it.length) <= maxCodePoints &&
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
