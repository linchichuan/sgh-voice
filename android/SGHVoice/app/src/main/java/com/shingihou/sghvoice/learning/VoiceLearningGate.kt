package com.shingihou.sghvoice.learning

import com.shingihou.sghvoice.processing.TranscriptionPipeline
import com.shingihou.sghvoice.processing.VoiceTask

/** Decides which committed voice output may be tracked for correction learning. */
object VoiceLearningGate {
    /**
     * @return the STT-derived baseline user edits are compared against, or null when edits of
     * this output must never be learned: translation and「幫我寫」(compose) outputs are AI text,
     * and a dictation without a baseline cannot prove which spans came from speech (fail closed).
     */
    fun trackingBaseline(task: VoiceTask, result: TranscriptionPipeline.Result): String? = when (task) {
        VoiceTask.Dictation -> result.learningBaseline.takeIf { it.isNotBlank() }
        else -> null
    }
}
