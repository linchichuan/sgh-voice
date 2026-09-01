import Foundation

/// Converts AVAudioRecorder power readings to an ephemeral 0...1 UI level.
enum AudioLevelMeter {
    private static let silenceFloor: Float = -52
    private static let speechCeiling: Float = -8

    static func normalizedPower(decibels: Float) -> Float {
        guard decibels.isFinite, decibels > silenceFloor else { return 0 }
        guard decibels < speechCeiling else { return 1 }
        return ((decibels - silenceFloor) / (speechCeiling - silenceFloor))
            .clamped(to: 0...1)
    }
}

private extension Comparable {
    func clamped(to range: ClosedRange<Self>) -> Self {
        min(max(self, range.lowerBound), range.upperBound)
    }
}
