# Keyboard visual preview (debug only)

`KeyboardPreviewActivity` renders the production `KeyboardView` under a synthetic
text field. It does not create `VoiceInputIME`, request microphone access, call
an API, or read/write user preferences. The activity is in `src/debug`, has no
launcher entry, and is absent from release APKs and app bundles.

After installing a debug APK:

```sh
adb shell am start -n com.shingihou.sghvoice/.debug.KeyboardPreviewActivity --es mode voice --es state recording --ef level 0.6
```

The `mode` extra accepts `voice`, `zhuyin`, `japanese`, and `english`. The `state`
extra accepts the IME state names (`idle`, `starting`, `recording`, `stopping`,
`processing`, `done`, `error`). `level` is a fixed synthetic float in `0..1`;
`0` previews silence. Defaults are `voice`, `recording`, and `0.6`.

Optional `--es locale zh-TW` renders the keyboard in Traditional Chinese (force
stop/relaunch when changing locale). `--ef fontScale 1.5` changes only this
synthetic keyboard's font scale (0.85–2.0), not the device setting.
`--es learning pending` or `--es learning saved` previews the short learning
status with synthetic state only; it never records a correction or touches the
personal dictionary. Combine with `--es state done` for post-dictation UI.
`--es task compose --es draft notes --es state done` previews the writing actions.
Use `--es draft pending` for a saved transcription, and `--ez preview true` to open
its scrollable text preview. `--ez retry true --es state error` renders audio retry
and discard actions. `--es japaneseStyle kana --es mode japanese --es state idle`
renders the flick keypad (tap = first kana; left/up/right/down select the other vowels).
`--ei heightPercent 90` changes the shared keyboard height (90–125, default 100),
without saving a preference. `--ez translation true --es state idle` opens
the translation picker. All text and retry state are synthetic.
`--es palette mint|sky|lavender|peach|rose|sand` previews the six light microphone
surfaces without saving a preference. Geometry verification also checks caption
contrast for every palette against the real rendered text color.
The 2.8.2 circle fades radially to transparent; it has no surrounding border,
padding frame or elevation shadow. The geometry contract asserts that boundary.
`--es mode palette --es state idle` renders the real settings colour picker above
the real microphone view. Its selection updates the synthetic preview only and
never opens `ApiConfig` or saves a user preference.

For constrained viewport checks, `--ei widthDp 280 --ei heightDp 360` limits the
keyboard width and simulated available window height. The top mode selector and
voice punctuation row stay outside the bounded middle scroll area. These extras
do not modify device settings. Force stop/relaunch when changing dimensions.
All modes use the original 372dp Zhuyin footprint at 100%, plus navigation insets,
capped at 80% of the available window. Wide landscape voice uses two columns; constrained
manual keyboards keep their touch targets and allow the middle area to scroll.
`--ez verify true` runs device-side checks
of the large single control, busy-state gating, one tap/one action, actual
`、` / `，` / `。` dispatch, and the translation picker. The preview header reports
PASS or FAIL. Clicks only change synthetic state/text; they never record or
submit a transcript.
The result is also written to the `KeyboardPreview` logcat tag. The geometry check
accepts a compact landscape circle and verifies the bottom actions are unclipped.

Recording previews provide a sample every 50 ms for at most 10 seconds, then
return to idle. Take a recording-state screenshot within that interval. No
callbacks remain after `onStop`; relaunching the same command restarts the
bounded preview. Manual modes do not run the audio sample callback.

Examples:

```sh
adb shell am start -n com.shingihou.sghvoice/.debug.KeyboardPreviewActivity --es mode voice --es state recording --ef level 0
adb shell am start -n com.shingihou.sghvoice/.debug.KeyboardPreviewActivity --es mode zhuyin --es state idle
adb shell am start -n com.shingihou.sghvoice/.debug.KeyboardPreviewActivity --es mode japanese --es state idle
adb shell am start -n com.shingihou.sghvoice/.debug.KeyboardPreviewActivity --es mode english --es state idle
```

To compare reduced motion, use the emulator's existing Android animation
settings: with animator duration scale disabled the inner waves stay flat
and respond using color/opacity only. Restore the previous
setting after verification. Any screenshots or recordings of this activity
must be identified as synthetic UI previews, not microphone or STT validation.
