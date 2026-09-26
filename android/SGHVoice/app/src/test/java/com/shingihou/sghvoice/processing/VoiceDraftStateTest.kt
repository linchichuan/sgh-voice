package com.shingihou.sghvoice.processing

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceDraftStateTest {
    @Test
    fun `multiple spoken ideas accumulate without silently inserting`() {
        val state = VoiceDraftState()
        assertTrue(state.appendComposeSegment("第一段：目的"))
        assertTrue(state.appendComposeSegment("第二段：不要改付款流程"))
        assertEquals(2, state.composeSegmentCount)
        assertEquals("第一段：目的\n第二段：不要改付款流程", state.composeNotes())
        assertFalse(state.hasPendingText)
    }

    @Test
    fun `brief limit rejects overflow without erasing prior segments`() {
        val state = VoiceDraftState()
        assertTrue(state.appendComposeSegment("a".repeat(VoiceDraftState.MAX_COMPOSE_CHARACTERS)))
        assertFalse(state.appendComposeSegment("b"))
        assertEquals(1, state.composeSegmentCount)
    }

    @Test
    fun `pending dictation requires explicit consumption`() {
        val state = VoiceDraftState()
        assertTrue(state.savePending(
            "切換畫面前的口述", VoiceDraftState.PendingOrigin.DICTATION
        ))
        assertEquals("切換畫面前的口述", state.peekPending()?.text)
        assertEquals(VoiceDraftState.PendingOrigin.DICTATION, state.peekPending()?.origin)
        state.clearPending()
        assertFalse(state.hasPendingText)
    }
}
