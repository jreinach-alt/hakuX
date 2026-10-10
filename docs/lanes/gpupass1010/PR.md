gpupass1010: NFS Most Wanted's GPU frame -- render mode A/B and the cold-start pass count (#433, 0.5)

State: draft
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

## Status

Draft -- waiting on `1-1791660793-gpupass1010-760340` (off, perflog) and
`1-1791660794-gpupass1010-761330` (on, perflog), queued but not yet run (Nova shared queue,
8+ requests ahead at merge time `c18fdd344a`). This PR will move to `State: ready` with the
full tables, the `Release note (...): ...` line, and the keep/drop recommendation once results
land; see `docs/lanes/gpupass1010/NOTES.md` / `WAITING`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
