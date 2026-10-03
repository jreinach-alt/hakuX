# Size the green-block FMV defect (#303): 2 titles, neither blocked in gameplay; #303 waits

State: ready

Lane: greensize303            Issue: #303
Base: master @ ddbc5f0173 (lane branched at 5661db4f2b; origin/master merged in, no rebase)
Files: docs/lanes/greensize303/NOTES.md, docs/lanes/greensize303/OUTBOX.md, docs/lanes/greensize303/PR.md, docs/lanes/greensize303/hits.tsv, docs/lanes/greensize303/tools/greenscan.py, docs/lanes/greensize303/sheet_other.png, docs/lanes/greensize303/sheet_spikeout.png, docs/lanes/greensize303/sheet_gamecheck_zero.png
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

Release note: none (analysis only; no emulator code changed)

## Result

The gate in the brief (3 or more titles green in gameplay, or a green screen that blocks reaching play) is **not met**.

| Title | Where the green appears | Blocks reach or hold play? |
|---|---|---|
| Star Wars Episode III (4C410017) | publisher logo, intro video, title screen, opening FMV/cutscenes. Gameplay clean. | No. Pathfind reached gameplay in 3.5 min |
| Spikeout: Battle Street (53450029) | Sega and NewEntertainment logos, title card, story FMV, loading screen. Title screen and gameplay clean. | No. Pathfind reached gameplay in 4.3 min |

Natural saturated green (Sonic Heroes, Blinx, Arctic Thunder, Crash, fuzion) flagged by the first detector pass and confirmed as not the defect by eye.

## Method

- 24,241 frames read on disk (pathfind runs; dispatch `frames` and `route-frames`).
- `tools/greenscan.py`: 8x8-block share of pure-green pixels. Calibrated on the Star Wars title screen and Spikeout loading screen after a first pass at a stricter colour missed the darker green.
- Every title's flagged frames were checked by eye, one representative per phase group (contact sheets in this directory).

## Likely subsystem (hypothesis, not fixed)

Luma survives under the green blocks, and the chroma is wrong. That matches a packed YUV path (YUY2/UYVY). Candidates: `hw/xbox/nv2a/pgraph/texture.c` (YUY2/UYVY conversion) and `hw/xbox/nv2a/pgraph/vk/display.c` (`convert_yuy2_to_rgb`). Not measured.

## Next (P x win)

- **A. Probe** the texture color_format and chroma bytes on the FMV draws, one device run per title. P 0.8 that it decides the subsystem. Cheap, so first if the gate is met.
- **B. Fix** the YUY2/UYVY chroma handling after A. P 0.3-0.4 (mechanism fits, unmeasured). Win is cosmetic on 2 titles' pre-game FMVs, 0 titles unblocked.

#303 waits. Full table and the candidate list in `docs/lanes/greensize303/NOTES.md`.

Checks run locally (offline protocol; no CI):
- `greenscan.py` run end to end over 24,241 frames; output `hits.tsv` (177 flagged frames).
- No harness files changed, so `docs/testing/jobs/selftest.sh` is not required.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
