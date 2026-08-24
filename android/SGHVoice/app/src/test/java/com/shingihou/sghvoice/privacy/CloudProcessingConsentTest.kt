package com.shingihou.sghvoice.privacy

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CloudProcessingConsentTest {

    @Test
    fun `missing or stale consent is rejected`() {
        assertFalse(CloudProcessingConsent.isAccepted(null))
        assertFalse(CloudProcessingConsent.isAccepted(0))
        assertFalse(
            CloudProcessingConsent.isAccepted(
                CloudProcessingConsent.CURRENT_VERSION - 1
            )
        )
    }

    @Test
    fun `current or newer consent is accepted`() {
        assertTrue(
            CloudProcessingConsent.isAccepted(
                CloudProcessingConsent.CURRENT_VERSION
            )
        )
        assertTrue(
            CloudProcessingConsent.isAccepted(
                CloudProcessingConsent.CURRENT_VERSION + 1
            )
        )
    }
}
