package com.shingihou.sghvoice.learning

import org.junit.Assert.assertEquals
import org.junit.Test

class RecentVoiceContextTest {
    @Test fun `context uses corrected voice text only in the original editor`() {
        val context = RecentVoiceContext { 1L }
        context.remember(1L, "請用Orbyt", true)
        context.corrected(1L, "請用Orbyt", "請用Orbit")
        assertEquals("請用Orbit", context.get(1L, true))
        assertEquals("", context.get(2L, true))
        assertEquals("", context.get(1L, true))
    }

    @Test fun `expiry opt out and unverified edits clear context`() {
        var now = 0L
        val context = RecentVoiceContext { now }
        context.remember(1L, "voice", true)
        now = 59_000L
        context.corrected(1L, "voice", "Voice")
        now = 60_001L
        assertEquals("", context.get(1L, true))
        context.remember(1L, "voice", true)
        assertEquals("", context.get(1L, false))
        assertEquals("", context.get(1L, true))
        context.remember(1L, "voice", true)
        context.corrected(1L, "different", "other")
        assertEquals("", context.get(1L, true))
    }

    @Test fun `unicode bound and explicit clearing prevent retaining full documents`() {
        val context = RecentVoiceContext { 0L }
        context.remember(1L, "🙂".repeat(512), true)
        assertEquals("🙂".repeat(512), context.get(1L, true))
        context.remember(1L, "🙂".repeat(513), true)
        assertEquals("🙂".repeat(512), context.get(1L, true))
        context.remember(1L, "voice", false)
        assertEquals("", context.get(1L, true))
        context.remember(1L, "voice", true)
        context.clear()
        assertEquals("", context.get(1L, true))
    }
}
