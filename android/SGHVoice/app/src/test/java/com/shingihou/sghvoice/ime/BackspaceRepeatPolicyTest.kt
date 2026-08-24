package com.shingihou.sghvoice.ime

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class BackspaceRepeatPolicyTest {

    @Test
    fun `repeat starts after a deliberate hold and then accelerates`() {
        assertTrue(BackspaceRepeatPolicy.INITIAL_DELAY_MS >= 350L)
        assertEquals(
            BackspaceRepeatPolicy.NORMAL_INTERVAL_MS,
            BackspaceRepeatPolicy.intervalAfter(1)
        )
        assertEquals(
            BackspaceRepeatPolicy.FAST_INTERVAL_MS,
            BackspaceRepeatPolicy.intervalAfter(
                BackspaceRepeatPolicy.ACCELERATE_AFTER
            )
        )
        assertTrue(
            BackspaceRepeatPolicy.FAST_INTERVAL_MS <
                BackspaceRepeatPolicy.NORMAL_INTERVAL_MS
        )
    }
}
