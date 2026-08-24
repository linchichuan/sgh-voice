package com.shingihou.sghvoice.privacy

/**
 * Versioned consent contract for every Android cloud-processing path.
 *
 * Increment [CURRENT_VERSION] whenever the disclosed data categories,
 * recipients, or processing route materially changes. A missing or older
 * value must always fail closed before recording starts.
 */
object CloudProcessingConsent {
    const val CURRENT_VERSION = 2

    fun isAccepted(storedVersion: Int?): Boolean =
        storedVersion != null && storedVersion >= CURRENT_VERSION
}
