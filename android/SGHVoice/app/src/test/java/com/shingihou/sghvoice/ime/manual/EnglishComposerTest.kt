package com.shingihou.sghvoice.ime.manual

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class EnglishComposerTest {

    @Test
    fun `default composer suggests common local words without changing typed prefix`() {
        val composer = EnglishComposer()
        "hel".forEach { composer.inputCharacter(it) }

        val suggestions = composer.candidates().map { it.text }

        assertTrue("hello must be offered for hel", "hello" in suggestions)
        assertTrue("help must be offered for hel", "help" in suggestions)
        assertEquals("hel", composer.currentWord)
        assertEquals(EnglishEdit.CommitText("hel "), composer.commitWord(" "))
    }

    @Test
    fun `local completions track prefix edits and candidate selection is explicit`() {
        val composer = EnglishComposer()
        composer.pressShift()
        "hell".forEach { composer.inputCharacter(it) }
        assertEquals(listOf("hello"), composer.candidates().map { it.text })
        assertEquals(EnglishEdit.SetComposingText("Hel"), composer.backspace())
        assertTrue(composer.candidates().any { it.text == "help" })
        val hello = composer.candidates().first { it.text == "hello" }
        assertEquals(EnglishEdit.CommitText("Hello "), composer.acceptCandidate(hello, " "))
        assertTrue(composer.candidates().isEmpty())
    }

    @Test
    fun `local vocabulary only completes prefixes and respects limits`() {
        val provider = LocalEnglishCandidateProvider
        assertEquals(listOf("hello"), provider.candidates("HEL", 1).map { it.text })
        assertTrue(provider.candidates("wor", 8).map { it.text }.containsAll(listOf("work", "world")))
        assertTrue(provider.candidates("", 8).isEmpty())
        assertTrue(provider.candidates("he", 0).isEmpty())
        assertTrue(provider.candidates("zzzz", 8).isEmpty())
        assertTrue(provider.candidates("hel", 8).all { it.text.startsWith("hel") })
    }

    @Test
    fun `one-shot shift applies to one letter and then turns off`() {
        val composer = EnglishComposer()

        assertEquals(ShiftState.ONCE, composer.pressShift())
        assertEquals(
            EnglishEdit.SetComposingText("A"),
            composer.inputCharacter('a')
        )
        assertEquals(ShiftState.OFF, composer.shiftState)
        assertEquals(
            EnglishEdit.SetComposingText("Ab"),
            composer.inputCharacter('B')
        )
    }

    @Test
    fun `second shift press enables caps lock until explicitly disabled`() {
        val composer = EnglishComposer()

        composer.pressShift()
        assertEquals(ShiftState.CAPS_LOCK, composer.pressShift())
        composer.inputCharacter('a')
        composer.inputCharacter('b')

        assertEquals("AB", composer.currentWord)
        assertEquals(ShiftState.CAPS_LOCK, composer.shiftState)
        assertEquals(ShiftState.OFF, composer.pressShift())
        composer.inputCharacter('C')
        assertEquals("ABc", composer.currentWord)
    }

    @Test
    fun `backspace edits local composition before deleting host text`() {
        val composer = EnglishComposer()
        composer.inputCharacter('c')
        composer.inputCharacter('a')
        composer.inputCharacter('t')

        assertEquals(
            EnglishEdit.SetComposingText("ca"),
            composer.backspace()
        )
        composer.backspace()
        assertEquals(EnglishEdit.ClearComposition, composer.backspace())
        assertFalse(composer.isComposing)
        assertEquals(EnglishEdit.DeleteBeforeCursor, composer.backspace())
    }

    @Test
    fun `word commit includes separator and clears composition`() {
        val composer = EnglishComposer()
        "hello".forEach { composer.inputCharacter(it) }

        assertEquals(
            EnglishEdit.CommitText("hello "),
            composer.commitWord(" ")
        )
        assertEquals("", composer.currentWord)
        assertFalse(composer.isComposing)
        assertEquals(
            EnglishEdit.CommitText(" "),
            composer.commitWord(" ")
        )
    }

    @Test
    fun `candidate provider receives normalized prefix and results are ranked`() {
        var observedPrefix = ""
        var observedLimit = 0
        val composer = EnglishComposer(
            candidateProvider = EnglishCandidateProvider { prefix, limit ->
                observedPrefix = prefix
                observedLimit = limit
                listOf(
                    EnglishCandidate("hello", score = 10),
                    EnglishCandidate("help", score = 30),
                    EnglishCandidate("helium", score = 20)
                )
            }
        )
        composer.pressShift()
        "he".forEach { composer.inputCharacter(it) }

        val candidates = composer.candidates(limit = 2)

        assertEquals("he", observedPrefix)
        assertEquals(2, observedLimit)
        assertEquals(listOf("help", "helium"), candidates.map { it.text })
    }

    @Test
    fun `candidate acceptance preserves typed capitalization and reports hook`() {
        var acceptedPrefix = ""
        var acceptedCandidate: EnglishCandidate? = null
        val hook = object : EnglishCandidateHook {
            override fun onCandidateAccepted(
                typedPrefix: String,
                candidate: EnglishCandidate
            ) {
                acceptedPrefix = typedPrefix
                acceptedCandidate = candidate
            }
        }
        val composer = EnglishComposer(candidateHook = hook)
        composer.pressShift()
        "hel".forEach { composer.inputCharacter(it) }

        val edit = composer.acceptCandidate(
            EnglishCandidate(
                text = "hello",
                source = EnglishCandidateSource.PERSONAL
            ),
            separator = " "
        )

        assertEquals(EnglishEdit.CommitText("Hello "), edit)
        assertEquals("Hel", acceptedPrefix)
        assertEquals("Hello", acceptedCandidate?.text)
        assertEquals(EnglishCandidateSource.PERSONAL, acceptedCandidate?.source)
        assertFalse(composer.isComposing)
    }

    @Test
    fun `prefix replacement remains composing and allows continued input`() {
        var hookValue = ""
        val hook = object : EnglishCandidateHook {
            override fun onPrefixReplaced(
                typedPrefix: String,
                replacement: String
            ) {
                hookValue = "$typedPrefix->$replacement"
            }
        }
        val composer = EnglishComposer(candidateHook = hook)
        "repo".forEach { composer.inputCharacter(it) }

        assertEquals(
            EnglishEdit.SetComposingText("repository"),
            composer.replacePrefix("repository")
        )
        assertEquals("repo->repository", hookValue)
        assertEquals(
            EnglishEdit.SetComposingText("repositorys"),
            composer.inputCharacter('s')
        )
        assertTrue(composer.isComposing)
    }

    @Test
    fun `apostrophe and hyphen remain inside current word`() {
        val composer = EnglishComposer()

        "don't-stop".forEach { character ->
            assertTrue(composer.inputCharacter(character) is EnglishEdit.SetComposingText)
        }

        assertEquals("don't-stop", composer.currentWord)
        assertEquals(
            EnglishEdit.CommitText("don't-stop"),
            composer.commitWord()
        )
    }

    @Test
    fun `unsupported punctuation does not alter composition`() {
        val composer = EnglishComposer()
        composer.inputCharacter('a')

        assertEquals(EnglishEdit.NoOp, composer.inputCharacter('.'))
        assertEquals("a", composer.currentWord)
    }
}
