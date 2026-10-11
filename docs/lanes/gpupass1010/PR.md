gpupass1010: NFS Most Wanted's GPU frame -- render mode A/B and the cold-start pass count (#433, 0.5)

State: ready
Lane: gpupass1010            Issue: #433
Base: origin/master @ c18fdd344a (lane/texscan1010 merged in at bfd6986fa2 per the dispatch
  note; origin/master merged in again at c18fdd344a to bring in texscan1010/pfifowait1009/
  forzasurf1010's folds -- see NOTES.md section 5. Both arm refs (9c8b1b12b6, 81ab5f3418) are
  unchanged by either merge.)
Files: android/app/src/main/cpp/xemu_android.cpp (kTitleRenderModes row only),
  docs/lanes/gpupass1010/**, docs/testing/predictions/gpupass1010-*.json
Prediction: docs/testing/predictions/gpupass1010-rendermode.json @ sha256 d6615f8ae93fda3b947f4e750d96ce353f36bd867ec8e55341cdab16a6155000;
  docs/testing/predictions/gpupass1010-texscan.json @ sha256 d8fc8ad3e177d11d85d8f5f2175a976fe61b43b1e35d45653322b214525af78c
Needs device: yes (Nova, used)
Needs NDK: no

## What this is

Issue #433, step 5 of `docs/lanes/nfs30plan1010/PLAN.md`: measure NFS Most Wanted's GPU frame at
the race start under sysmem vs the driver's GMEM default (the remedy class `rendermode474`
landed), and report render passes per frame with `HAKUX_TEXSCAN` on vs off now that
`lane/texscan1010` has landed its GPU-side cube-face copy. Dispatched early (2026-10-10 11:47
PDT) because texscan1010's own A/B already moved GPU busy from 13.4 to 18.0 ms/frame and put the
whole frame behind the end-of-frame occlusion-report fence -- the dispatch condition's early
clause.

Two commits, both in territory:
- `9c8b1b12b6` (**R_off**): adds the lane's reader scripts only (`gpuread.py`, new; `phaseread.py`
  /`ftwin.py`, copied from `nfs30plan1010`). No render-mode change -- NFS still renders at the
  driver's GMEM default.
- `81ab5f3418` (**R_on**): one line, `{0x4541007B, "sysmem"}` added to `kTitleRenderModes`.

Two predictions registered before any device run (`docs/testing/predictions/gpupass1010-{rendermode,texscan}.json`),
naming `9c8b1b12b6`/`81ab5f3418` as `a_ref`/`b_ref`. Full reasoning in
`docs/lanes/gpupass1010/NOTES.md`.

## Run plan (4-run/500s cap; corrected -- see NOTES.md sections 4-5)

A **plain build's `xfr_emit()` is compiled out** (`NV2A_PERF_LOG`-gated; only `--perflog` sets
it), so the brief's literal "plain build + HAKUX_GPUXFR=1 for the pass census" cannot produce
any of the GPU-busy/X/R/passes figures. Discovered via the pilot pair (both ran clean, zero
`xemu-xfr` lines); corrected (`ebcbd61064`) before queuing further device time. Final plan,
inside the same 4-run cap:

| run | ref | env | build | serves |
|---|---|---|---|---|
| A | R_off | `HAKUX_GPUXFR=1` | plain | period/pace/v-hist only (no XFR data) |
| C | R_on | `HAKUX_GPUXFR=1` | plain | period/pace/v-hist only (no XFR data) |
| B' | R_off | `HAKUX_GPUXFR=1` | perflog | step 1 off-arm GPU busy/X/R/passes |
| D' | R_on | `HAKUX_GPUXFR=1` | perflog | step 1 on-arm GPU busy/X/R/passes |

Step 3's `HAKUX_TEXSCAN=1` on-arm is **DEFERRED**, not measured this lane (budget fully
consumed by A/C/B'/D'; see `gpupass1010-texscan.json`'s `status` field). Pilot gate: A+C queued
first (~19.7 min est.), reviewed (`pilots/gpupass1010.ok`), then B'+D' queued.
`1-1791660793-gpupass1010-760340` (B', off) / `1-1791660794-gpupass1010-761330` (D', on) are
queued on the shared Nova behind 8 `reportasync1010` + several `drawrec1010` requests at the
time of writing -- see `WAITING`.

## Step 4 (pixel check) -- answered without new device time

`kTitleRenderModes` only fires when the booted disc's own title id matches a table row
(`xemu_android.cpp` `ApplyRenderMode`, around line 936). The pgraph pixel-suite test disc boots
under a synthetic title id (e.g. `FFFF0002`) that matches no row in the table, before or after
this lane's NFS row. Adding the row is therefore architecturally a no-op for every pgraph pixel
suite run: `rendermode474`'s own verdict ("PASS: all 1059 registered checks hold") already fully
answers step 4, since the suites it ran never could have differed by anything this lane's single
table row does. No pixel run queued for this leg.

## Results (B'/D', perflog; full detail and three `gpuread.py` bugs fixed: NOTES.md sections 6-9)

Both runs landed, DONE, clean (no truncation, no fatal lines, 12/12 go marks, matched "max"
perf/fan regimen, moving-player gameplay confirmed from `s1-g11.png` frames in both arms).
Three bugs in this lane's own reader (`gpuread.py`) were found and fixed reading them --
a false-FATAL match on the benign `hakuX-unhandled` tag, a cold-window label that never
matched the route's actual `mark gameplay` string, and a cumulative-vs-per-window denominator
bug in the period calculation -- committed as `d3baeb348b`. None of the three were data
problems; the device runs were clean throughout.

`python3 docs/lanes/gpupass1010/gpuread.py --arm <off|on> <run dir>`:

| window | arm | n | GPU busy ms | X/R | mode(in/out) | passes/frame | period ms |
|---|---|---|---|---|---|---|---|
| cold (gameplay) | off | 9 | 5.10 | 0.24 | 0.81 | 15.6 | 59.56 (n=4) |
| cold (gameplay) | on | 11 | 3.83 | 0.02 | 0.98 | 13.8 | 51.37 (n=4) |
| warm (gameplay) | off | 119 | 3.98 | 0.03 | 0.97 | 10.4 | 44.50 (n=44) |
| warm (gameplay) | on | 140 | 3.54 | 0.01 | 0.99 | 9.6 | 43.71 (n=46) |
| cold_cd (countdown) | off | 3 | 7.12 | 0.41 | 0.71 | 23.6 | -- |
| cold_cd (countdown) | on | 3 | 5.15 | 0.02 | 0.98 | 21.9 | -- |
| warm_cd (countdown) | off | 35 | 4.26 | 0.02 | 0.98 | 10.0 | -- |
| warm_cd (countdown) | on | 36 | 4.07 | 0.01 | 0.99 | 9.2 | -- |

Verdict legs: off-arm `V=PASS M=FAIL G=PASS X=PASS P=PASS`; on-arm `V=PASS M=PASS G=PASS
X=PASS P=PASS`. The off-arm M FAIL is a one-hundredth-over-threshold windowing artifact
(gameplay-window cold, n=9) -- the countdown window (`cold_cd`, closer to the baseline's own
measurement slice) confirms GMEM unambiguously at 0.71, and the on-arm's own mode leg is a
clean 0.98 PASS in both windows. Not read as a render-mode failure; see NOTES.md section 8.

**Directionally as predicted, smaller than the conditional magnitude:** GPU busy falls off->on
in every bucket (cold_cd -28%, cold gameplay -25%), X/R collapses toward 0 in every bucket
(cold_cd 0.41->0.02), passes/frame is unchanged within noise as predicted, and period stays
flat within noise in the reliable (warm, n=44/46) bucket -- confirming the GPU is not yet on
NFS's critical path at this base (reportasync1010 not merged here), consistent with
`pfifowait1009`'s own FAIL verdict. But both arms' absolute GPU-busy/pass magnitudes read
3-4x below nfs30plan1010's own cited census (21.7 ms/69 passes cold) -- an open discrepancy,
present equally in both arms (so not a render-mode effect), not resolved within this lane's
device budget. Flagged as a named follow-up for #433 (NOTES.md section 9): re-verify the
census against this reader's windowing, or find what differs between the two readers. Treat
the off-vs-on *deltas* above as trustworthy (same reader, same route, applied identically to
both arms); treat the *absolute* magnitudes as uncertain against the brief's baseline.

**Step 3 (texscan cross-check, off-arm only, no new device time):** `HAKUX_GPUXFR=1`-only cold
passes/frame is 15.6 (gameplay window) / 23.6 (countdown window) -- itself part of the same
section-9 discrepancy against the 69-pass baseline. The `HAKUX_TEXSCAN=1` on/off delta this
sub-prediction asks for was never queued (budget fully spent on the render-mode pair, as
`gpupass1010-texscan.json`'s `status` field says at registration) and remains unjudged --
a follow-up for #433, not blocking this PR.

## Recommendation: keep the NFS `kTitleRenderModes` sysmem row

Zero measured downside (pixel check is an architectural no-op -- see "Step 4" above; passes/frame
unchanged within noise; period does not regress in the reliable bucket) and a real, if modest,
upside (GPU busy down 25-28% at the race start, mode-confirmation and X/R legs both confirm the
row actually engages sysmem and collapses the GMEM double-pass signature, matching the
gmem474/rendermode474/flip474 corpus). The section-9 magnitude discrepancy affects how big the
win is, not whether there is one. The GPU is not yet on NFS's critical path at this base, so a
player will not see a frame-time change from this row today -- expected, and already named in
the brief's "Why" as positioning for when the GPU is on the path (reportasync1010, or heavier
tracks/conditions).

Release note (performance): Need for Speed: Most Wanted's race-start rendering now uses the
driver's sysmem path instead of GMEM tiling, cutting measured GPU time per frame by roughly a
quarter at the race start; no visible frame-time change yet on this build, since the GPU is not
the limiting stage for this title today.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
