# Halo CE: the ship's rear lights show through the hull after the cut to the front (opening cinematic)

State: ready

Lane: haloship1017            Issue: #1039
Base: master @ 8d260f39fc (master merged in at 9abd80e90c and 07b7b6d996)
Files: docs/lanes/haloship1017/, docs/testing/nv2a_index.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/reports.c, ui/xemu-input.c, ui/xemu.c
Prediction: none: closed with no arm (owner: not reproduced on Turnip; no fix written)
Needs device: no    Needs NDK: no

Release note (none): instrumentation only, off unless set: frame dump schema 11 (visibility tests), HAKUX_ZREP, HAKUX_PAD_FILE.

**Result: not a defect.** On 10-17 (~14:00 PDT) the owner confirmed that the rear lights no longer show through
the hull on the Turnip driver. Both sightings, 0.5.1-rc1 on 10-16 and 0.5.2-rc1 on 10-17, were in the release
app `com.jreinach.hakux`, which had no custom driver until the owner selected T30 at ~13:20 on 10-17
(bindpose1017, #1043). So both ran on the stock Qualcomm driver. #1039 is closed on that basis, and no fix is
written.

**On record: a desktop one-frame flash from `HAKUX_REPORT_EARLY`.** The desktop is lavapipe with 0.5.2 defaults.
Halo draws each light's flare with the depth test off. The flare's brightness comes from the previous frame's
visibility-test count, and the guest waits for every count with no timeout (disassembly). At the cut, EARLY
answers the first front frame's 12 rear tests with the behind shot's counts, so the next frame draws all 12
rear flares through the hull for one frame.

| run (desktop) | first front frame: own count nz/sum | guest given | rear flares drawn in a front frame |
|---|---|---|---|
| r4b, defaults (ASYNC + EARLY) | 0/0 | 12/730 | 12, at alpha 0.196 / 0.184, one frame (f42) |
| r5 e0, `HAKUX_REPORT_EARLY=0` | 0/0 | 0/0 | none |
| r5 a0, `HAKUX_REPORT_ASYNC=0` | 0/0 | 0/0 | none |

A guard was designed and costed offline but not built: refuse an early answer when the offset's test quad moved
more than 32 guest px and the stale count is >= 1. It catches 12 of 12 at all three cuts for about 1% of EARLY's
saved waits. `docs/lanes/haloship1017/NOTES.md` has the mechanism, the remedies ranked by P x win, and a recipe
for reopening.

**What lands.** The lane's analysis tools (`docs/lanes/haloship1017/`), and the instrument. Every part of the
instrument is off unless set:
- `reports.c` / `renderer.c`: `HAKUX_ZREP`, per-report lines with the own count and the early flag;
- frame dump schema 11, with visibility-test fields. It is numbered after #1038's schema 10 (the shadow-sampling
  fields), which folded first. Both field sets are written in every dump, so 11 is "as 10, plus" these;
- `ui/`: `HAKUX_PAD_FILE`, scripted desktop pad input.

`nv2a_index.json` is regenerated for the two new GET_REPORT_OFFSET sites, from the fold's pinned trees
(`nxdk_pgraph_tests` 6743b6ab, the committed `tests_commit`; still 104 suites, `resolved_tables` 1).

**Selftest fragments: none.** No harness script changes. `75-nv2a-index.sh` and `75-nv2a-index-drift.sh` test
`nv2a_index.py` on synthetic trees, and `99-release-note-line.sh` and `86-nightly-notes.sh` test the
nightly-notes parser; this PR changes none of those scripts. Two checks do cover this change: the build, for
the hw/ and ui/ code, and `nv2a_index.py check`, for the regenerated index (preflight passes it). No default
changes, so no default-on screen is needed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
