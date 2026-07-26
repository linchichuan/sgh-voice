package com.shingihou.sghvoice.ime.manual

import java.util.Locale

enum class EnglishCandidateSource {
    BASE,
    CUSTOM,
    PERSONAL
}

data class EnglishCandidate(
    val text: String,
    val score: Int = 0,
    val source: EnglishCandidateSource = EnglishCandidateSource.BASE,
    val id: String = text
) {
    init {
        require(text.isNotBlank()) { "A candidate cannot be blank." }
        require(id.isNotBlank()) { "A candidate id cannot be blank." }
    }
}

fun interface EnglishCandidateProvider {
    /**
     * Returns ranked candidates for a lowercase prefix.
     */
    fun candidates(prefix: String, limit: Int): List<EnglishCandidate>
}

interface EnglishCandidateHook {
    fun onCandidateAccepted(typedPrefix: String, candidate: EnglishCandidate) = Unit

    fun onPrefixReplaced(typedPrefix: String, replacement: String) = Unit
}

sealed class EnglishEdit {
    data class SetComposingText(val text: String) : EnglishEdit()
    data class CommitText(val text: String) : EnglishEdit()

    object ClearComposition : EnglishEdit()
    object DeleteBeforeCursor : EnglishEdit()
    object NoOp : EnglishEdit()
}

/**
 * Pure Kotlin English word composer.
 *
 * The class owns only the current token and shift state. Android
 * `InputConnection` calls are intentionally represented as [EnglishEdit] so
 * the IME service can apply them safely to its current input session.
 */
class EnglishComposer(
    private val candidateProvider: EnglishCandidateProvider =
        EnglishCandidateProvider { _, _ -> emptyList() },
    private val candidateHook: EnglishCandidateHook = object : EnglishCandidateHook {}
) {
    private val buffer = StringBuilder()

    var shiftState: ShiftState = ShiftState.OFF
        private set

    val currentWord: String
        get() = buffer.toString()

    val isComposing: Boolean
        get() = buffer.isNotEmpty()

    /**
     * Cycles through off → one-shot → caps lock → off.
     *
     * The View may map a double tap to two calls, while keeping gesture timing
     * outside this deterministic composer.
     */
    fun pressShift(): ShiftState {
        shiftState = when (shiftState) {
            ShiftState.OFF -> ShiftState.ONCE
            ShiftState.ONCE -> ShiftState.CAPS_LOCK
            ShiftState.CAPS_LOCK -> ShiftState.OFF
        }
        return shiftState
    }

    fun setShiftState(state: ShiftState) {
        shiftState = state
    }

    /**
     * Adds an English word character. Apostrophe and hyphen are allowed inside
     * a token because they are common in names and contractions.
     */
    fun inputCharacter(character: Char): EnglishEdit {
        if (!character.isLetter() && character != '\'' && character != '-') {
            return EnglishEdit.NoOp
        }

        val transformed = when {
            !character.isLetter() -> character
            shiftState == ShiftState.ONCE || shiftState == ShiftState.CAPS_LOCK ->
                character.uppercaseChar()

            else -> character.lowercaseChar()
        }
        buffer.append(transformed)
        if (shiftState == ShiftState.ONCE && character.isLetter()) {
            shiftState = ShiftState.OFF
        }
        return EnglishEdit.SetComposingText(currentWord)
    }

    /**
     * Removes one composing character, or asks the host to delete before the
     * cursor when there is no local composition.
     */
    fun backspace(): EnglishEdit {
        if (buffer.isEmpty()) return EnglishEdit.DeleteBeforeCursor
        buffer.deleteCharAt(buffer.lastIndex)
        return if (buffer.isEmpty()) {
            EnglishEdit.ClearComposition
        } else {
            EnglishEdit.SetComposingText(currentWord)
        }
    }

    /**
     * Returns candidate-hook results for the current lowercase prefix.
     */
    fun candidates(limit: Int = DEFAULT_CANDIDATE_LIMIT): List<EnglishCandidate> {
        require(limit >= 0) { "Candidate limit cannot be negative." }
        if (limit == 0 || buffer.isEmpty()) return emptyList()

        val normalizedPrefix = normalizedPrefix()
        return candidateProvider.candidates(normalizedPrefix, limit)
            .asSequence()
            .filter { it.text.isNotBlank() }
            .distinctBy { it.id }
            .sortedByDescending { it.score }
            .take(limit)
            .toList()
    }

    /**
     * Replaces the current prefix but leaves it as composing text so the user
     * can continue typing.
     */
    fun replacePrefix(replacement: String): EnglishEdit {
        if (replacement.isBlank()) return EnglishEdit.NoOp
        val typedPrefix = currentWord
        val casedReplacement = matchCurrentCase(replacement.trim())
        buffer.clear()
        buffer.append(casedReplacement)
        candidateHook.onPrefixReplaced(typedPrefix, casedReplacement)
        return EnglishEdit.SetComposingText(casedReplacement)
    }

    /**
     * Accepts a candidate and commits it, optionally followed by a separator.
     */
    fun acceptCandidate(
        candidate: EnglishCandidate,
        separator: String = ""
    ): EnglishEdit {
        val typedPrefix = currentWord
        val committedCandidate = matchCurrentCase(candidate.text)
        buffer.clear()
        candidateHook.onCandidateAccepted(
            typedPrefix,
            candidate.copy(text = committedCandidate)
        )
        return EnglishEdit.CommitText(committedCandidate + separator)
    }

    /**
     * Commits the current word. If it is empty, only a requested separator is
     * committed, which makes the same method usable for the space key.
     */
    fun commitWord(separator: String = ""): EnglishEdit {
        if (buffer.isEmpty()) {
            return if (separator.isEmpty()) {
                EnglishEdit.NoOp
            } else {
                EnglishEdit.CommitText(separator)
            }
        }
        val committed = currentWord + separator
        buffer.clear()
        return EnglishEdit.CommitText(committed)
    }

    fun reset(resetShift: Boolean = true): EnglishEdit {
        val hadComposition = buffer.isNotEmpty()
        buffer.clear()
        if (resetShift) shiftState = ShiftState.OFF
        return if (hadComposition) {
            EnglishEdit.ClearComposition
        } else {
            EnglishEdit.NoOp
        }
    }

    private fun normalizedPrefix(): String =
        currentWord.lowercase(Locale.ROOT)

    private fun matchCurrentCase(candidate: String): String {
        val typed = currentWord
        val typedLetters = typed.filter(Char::isLetter)
        if (typedLetters.isEmpty()) return candidate

        return when {
            typedLetters.all(Char::isUpperCase) -> candidate.uppercase(Locale.ROOT)
            typed.firstOrNull()?.isUpperCase() == true ->
                candidate.replaceFirstChar { character ->
                    if (character.isLowerCase()) character.titlecaseChar() else character
                }

            else -> candidate
        }
    }

    companion object {
        const val DEFAULT_CANDIDATE_LIMIT = 8
    }
}
