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
`--ez verify true` runs device-side checks
of the large single control, busy-state gating, one tap/one action, actual
`、` / `，` / `。` dispatch, and the translation picker. The preview header reports
PASS or FAIL. Clicks only change synthetic state/text; they never record or
submit a transcript.

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
