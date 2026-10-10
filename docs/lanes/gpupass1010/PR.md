gpupass1010: NFS Most Wanted's GPU frame -- render mode A/B and the cold-start pass count (#433, 0.5)

State: draft
Lane: gpupass1010            Issue: #433
Base: origin/master @ bfd6986fa2 (lane/texscan1010 merged in, per the dispatch note; step 3's
  census needs texscan1010's GPU-side cube-face copy on the base)
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

## Run plan (4-run/500s cap; see NOTES.md section 3)

| run | ref | env | serves |
|---|---|---|---|
| A | R_off | `HAKUX_GPUXFR=1` | step 1 off-arm + step 3 off-arm |
| B | R_off | `HAKUX_GPUXFR=1 HAKUX_TEXSCAN=1` | step 3 on-arm |
| C | R_on | `HAKUX_GPUXFR=1` | step 1 on-arm, sample 1 |
| D | R_on | `HAKUX_GPUXFR=1` | step 1 on-arm, sample 2 |

Pilot gate (lane-role contract): A+C queued first as the pilot (~19.7 min est.), reviewed, then
B+D.

## Step 4 (pixel check) -- answered without new device time

`kTitleRenderModes` only fires when the booted disc's own title id matches a table row
(`xemu_android.cpp` `ApplyRenderMode`, around line 936). The pgraph pixel-suite test disc boots
under a synthetic title id (e.g. `FFFF0002`) that matches no row in the table, before or after
this lane's NFS row. Adding the row is therefore architecturally a no-op for every pgraph pixel
suite run: `rendermode474`'s own verdict ("PASS: all 1059 registered checks hold") already fully
answers step 4, since the suites it ran never could have differed by anything this lane's single
table row does. No pixel run queued for this leg.

## Status

Draft -- device runs pending. This PR will move to `State: ready` with the full tables, the
`Release note (...): ...` line, and the keep/drop recommendation once results land; see
`docs/lanes/gpupass1010/NOTES.md` / `WAITING` for what is still outstanding.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
