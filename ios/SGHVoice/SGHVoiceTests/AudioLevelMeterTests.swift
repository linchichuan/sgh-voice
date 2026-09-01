import Testing
@testable import SGHVoice

struct AudioLevelMeterTests {
    @Test func silenceIsFlatAndSpeechPowerIsVisible() {
        #expect(AudioLevelMeter.normalizedPower(decibels: -80) == 0)
        #expect(AudioLevelMeter.normalizedPower(decibels: -52) == 0)
        #expect(
            AudioLevelMeter.normalizedPower(decibels: -18) >
                AudioLevelMeter.normalizedPower(decibels: -36)
        )
        #expect(AudioLevelMeter.normalizedPower(decibels: -6) == 1)
    }
}
