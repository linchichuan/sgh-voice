#!/usr/bin/env python3
"""CI-only: fetch a few public Japanese speech clips with reference text.

Source: Google FLEURS ja_jp dev split (CC-BY 4.0), read speech, no clinical or
personal data. Clips are converted to the recorder's 16 kHz mono PCM16 WAV
contract and listed in clips.json for windows_launcher --speech-set. Clips
after the first --skip unique sentences are used, so this acceptance gate does
not reuse the clips that scripts/benchmark_windows_ja_stt.py selects models on.
Never packaged.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tarfile

FLEURS_REPO = "google/fleurs"


def to_pcm16k(source, target):
    import numpy as np
    import soundfile
    audio, rate = soundfile.read(str(source), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if rate != 16000:
        positions = np.arange(0, len(audio) * 16000 / rate) * rate / 16000
        audio = np.interp(positions, np.arange(len(audio)), audio).astype("float32")
    soundfile.write(str(target), audio, 16000, subtype="PCM_16")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--skip", type=int, default=40)
    parser.add_argument("--phone-mp3", action="store_true", help="also build an imported MP3 test case")
    args = parser.parse_args(argv)
    from huggingface_hub import hf_hub_download
    tsv = Path(hf_hub_download(FLEURS_REPO, "data/ja_jp/dev.tsv", repo_type="dataset"))
    seen, wanted = [], {}
    for line in tsv.read_text(encoding="utf-8").splitlines():
        cols = line.split("\t")
        if len(cols) < 3 or cols[0] in seen:
            continue
        seen.append(cols[0])
        if len(seen) > args.skip:
            wanted[cols[1]] = cols[2]
        if len(wanted) >= args.count:
            break
    archive = hf_hub_download(FLEURS_REPO, "data/ja_jp/audio/dev.tar.gz", repo_type="dataset")
    args.out.mkdir(parents=True, exist_ok=True)
    clips = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            name = Path(member.name).name
            if member.isfile() and name in wanted:
                raw = args.out / ("raw-" + name)
                raw.write_bytes(tar.extractfile(member).read())
                wav = args.out / name
                to_pcm16k(raw, wav)
                raw.unlink()
                clips.append({"wav": str(wav.resolve()), "reference": wanted[name]})
    if len(clips) != args.count:
        raise SystemExit(f"Expected {args.count} clips, prepared {len(clips)}")
    if args.phone_mp3:
        # A phone-style import: the first three clips joined with 2 s pauses,
        # stored as 44.1 kHz stereo MP3 (exercises decode, mix-down, resample, VAD).
        import numpy as np
        import soundfile
        parts, texts = [], []
        for clip in clips[:3]:
            audio, _ = soundfile.read(clip["wav"], dtype="float32")
            parts += [audio, np.zeros(32000, dtype="float32")]
            texts.append(clip["reference"])
        joined = np.concatenate(parts)
        positions = np.arange(0, len(joined) * 44100 / 16000) * 16000 / 44100
        upsampled = np.interp(positions, np.arange(len(joined)), joined).astype("float32")
        mp3 = args.out / "phone-recording.mp3"
        soundfile.write(str(mp3), np.stack([upsampled, upsampled], axis=1), 44100,
                        format="MP3", subtype="MPEG_LAYER_III")
        clips.append({"wav": str(mp3.resolve()), "reference": "".join(texts), "import": True})
    (args.out / "clips.json").write_text(json.dumps(clips, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"PASS prepared {len(clips)} public FLEURS ja_jp clips (CC-BY 4.0) in {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
