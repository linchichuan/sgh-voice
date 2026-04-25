#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path


FILES = [
    Path("/Users/lin/Library/CloudStorage/Dropbox-新義豊株式会社/林紀全/LIN個人檔案/自傳self story/nanobanana_prompts_en.md"),
    Path("/Users/lin/Library/CloudStorage/Dropbox-新義豊株式会社/林紀全/LIN個人檔案/自傳self story/nanobanana_prompts_jp.md"),
]

RULES_BLOCK = """\
> **Generation Rules (OpenAI GPT Image directives):**
> 1. **Characters:** All subjects must be Asian (Taiwanese, Japanese, Chinese). Strictly no Western/Caucasian faces.
> 2. **Settings:** Backgrounds restricted to Japan, China, or Taiwan.
> 3. **Medical facilities:** Laboratories must feel high-tech and sterile-clean; **private clinics must feel calm, quiet, and uncrowded** (uncrowded, quiet, private clinic, few people).
> 4. **Style:** Photorealistic, cinematic lighting, high resolution (photorealistic, cinematic lighting, 8k, raw photo).
> 5. **Recurring protagonist:** The narrator, coordinator, translator, founder, driver, or lone male lead in every applicable scene must be the same person: **Lin Ji-Quan**, a Taiwanese man.
> 6. **Character anchor for Lin Ji-Quan:** warm medium skin, oval face, defined cheekbones, dark brown eyes, straight black hair with a natural side part, slim build, clean-shaven face, restrained expression, understated business-casual wardrobe.
> 7. **Age continuity:** Prologue through Chapter 4 = early 30s; Chapters 5 through 9 = late 30s; Chapters 10 through 12 = early 40s. Keep the same facial identity and only age him naturally.
> 8. **Supporting cast separation:** If another man appears in the same scene, do not let him resemble Lin Ji-Quan unless the scene explicitly identifies him as the recurring protagonist.
> 9. **OpenAI prompting preference:** one clear focal subject, one stable setting, one emotional beat, and minimal extra faces unless the scene explicitly requires more people.
> 10. **Visual consistency priority:** preserve the same face shape, eye shape, nose, hairline, and body proportions for Lin Ji-Quan across all scenes, while allowing wardrobe, pose, and lighting to change.
"""

PROMPT_PREFIX = (
    "Character continuity note: If this scene centers on the recurring narrator, "
    "coordinator, translator, founder, driver, or lone male lead, render him as "
    "the same Taiwanese protagonist, Lin Ji-Quan, with warm medium skin, oval "
    "face, defined cheekbones, dark brown eyes, straight black hair with a "
    "natural side part, slim build, clean-shaven face, and a restrained "
    "expression; preserve the same facial identity, hairline, eye shape, and "
    "body proportions across scenes. If another male character appears, keep him "
    "visibly distinct from Lin Ji-Quan. "
)


def transform(text: str) -> str:
    text = text.replace(
        "# Nano Banana Image Prompts (English Edition) — 65 Images Total",
        "# OpenAI GPT Image Prompts (English Edition) — 65 Images Total",
    )
    text = text.replace(
        "# Nano Banana Image Prompts (Japanese Edition) — 65 Images Total",
        "# OpenAI GPT Image Prompts (Japanese Edition) — 65 Images Total",
    )

    old_rules_start = "> **Generation Rules (Nano Banana directives):**"
    if old_rules_start in text:
        start = text.index(old_rules_start)
        divider = text.index("\n---", start)
        text = text[:start] + RULES_BLOCK + text[divider:]

    marker = "> **Prompt**: "
    replaced_lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        leading = line[: len(line) - len(stripped)]
        if stripped.startswith(marker):
            prompt_body = stripped[len(marker) :]
            if not prompt_body.startswith(PROMPT_PREFIX):
                line = leading + marker + PROMPT_PREFIX + prompt_body
        replaced_lines.append(line)
    text = "\n".join(replaced_lines) + ("\n" if text.endswith("\n") else "")
    return text


def main() -> int:
    for path in FILES:
        original = path.read_text(encoding="utf-8")
        updated = transform(original)
        path.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
