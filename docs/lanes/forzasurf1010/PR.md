lane.forzasurf1010 -- does the default-on surfgpu route remove Forza's surface-download wait? (#433, 0.5)

State: ready

Lane: forzasurf1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 510dacff37, merged forward to origin/master @ 99f662cdb9 (one unrelated fold,
  nightlywrap1010's nightly-notes tooling -- no conflict, nothing in this lane's territory)
Files: docs/lanes/forzasurf1010/NOTES.md, docs/lanes/forzasurf1010/PR.md,
  docs/testing/titles/routes/forza-soak1010.route, docs/testing/predictions/forzasurf1010-ab.json
Prediction: docs/testing/predictions/forzasurf1010-ab.json (registered, a_ref=b_ref=ab1acc4154)
Needs device: yes (Nova, used)    Needs NDK: no
Release note (none): measurement only, no emulator code changed

## Question

Does lane.surfgpudefault1009's shipped default (`HAKUX_SURFGPU=1`) remove the per-frame `surfupd`
wait lane.frametrace named on Forza Motorsport (12.2 ms/frame, `vk/draw.c:4319`'s non-deferred
SURFACE_DOWN finish, caller `surfupd` at `surface.c:5169`)? frametrace's own capture was invalid
(car stalled against the wall, 8th of 8) -- this lane re-measured on a confirmed moving scene.

## Method

Two arms (`HAKUX_SURFGPU=0`/`1`, both `HAKUX_FRAMETRACE=1`, same ref `ab1acc4154`), 2 runs/arm as
registered, route `forza-soak1010` (480 s, drive-then-mark), Nova. Switch state confirmed by
`[surfgpu] on` presence/absence in each run's logcat. Moving-car confirmed by hand from each run's
full `route-state.tsv`: both arms hold continuous `play`/`hud:hud-lap+motion` (no `stalled` rows)
for 340-360 s after `mark gameplay` in all four runs.

`sg_judge.py --expect forzasurf1010-ab.json` FAILed its V4 (thermal-pause) leg on all four runs,
cascading NO DATA into P3/P4 -- traced to a judge-tool gap, not a real event: `near30/decompose.py`
requires a `ROUTE H:M:S mark gameplay` line in `run.log`, which drive.py's screen-aware `mark`
routes never write there (only to device logcat and `route-state.tsv`), so `decompose()` returns
`(None, 'no mark')` before it ever reaches the `THERMAL:` line, and a missing read is treated as
"paused". All four runs' `run.log` carry `THERMAL: no thermal-pause device above 0` directly --
confirmed by patching a scratch copy of each result dir with the missing `ROUTE` line (device-clock
H:M:S of that run's own `mark gameplay` logcat line) and running `decompose.py` against the
patches. This is a shared gap (any lane pairing a drive.py `mark` route with this reader hits it),
not fixed here (outside this lane's territory) -- flagging for a follow-on.

## Result (2 runs/arm, averaged; see NOTES.md section 7 for the per-run table)

| metric | off (A) | on (B) | registered bar | result |
|---|---|---|---|---|
| surfupd ms/flip | 6.64 | 0.16 | P0>=4.0 / P1<=2.0 | PASS both |
| range ms/flip | 5.77 | 9.69 | reported only | **grows** under surfgpu |
| tobuf ms/flip | absent | 3.46 | reported only | **new caller**, absent off |
| all-`[sdcall]`-callers sum ms/flip | 17.79 | 13.77 | P2 ratio<=0.6 | 0.77, **FAIL** |
| [surfgpu] nodisp/flip | -- | 0.045 | P1>=0.2 | **FAIL** both runs |
| ph_Fin ms (decompose, patched) | 12.75 | 14.35 | P3 drop>=3.0 | **rose** +1.60, both runs |
| gfps (decompose, patched) | 24.92 | 26.00 | P4 gain>=1.0 | +1.08, PASS on the average only (per-run: +1.56, then +0.60) |

No thermal pause in any run. V1-V3 PASS; V4 is the judge-tool false-FAIL above, not scored as void.

## Decision: outcome (b) -- the wait moved, it did not disappear

surfgpu does exactly what lane.surfgpu1009 built it to do: `surfupd`'s wait drops from ~6.6 to
~0.15-0.2 ms/flip, consistently, in both runs. But that is not Forza's whole surface-download
wait. Most of the freed budget relocates to two callers surfgpu does not reach: `range`
(surfdl1008's Midnight Club 2 caller, `texture.c`'s `pgraph_vk_download_surfaces_in_range_if_dirty`,
5.77->9.69 ms/flip, now the dominant caller with surfgpu on -- bigger than `surfupd` ever was with
it off) and a new caller `tobuf` (0->3.46 ms/flip, absent entirely with surfgpu off, so it is
conditional on surfgpu's own path rather than a pre-existing wait moved by coincidence). The
all-caller sum only falls 23% against the registered 40% floor, and `ph_Fin` -- the
renderer-finish-wait phase that sum feeds -- **rises** in both runs rather than falling. `gfps`
ticks up on average (+1.08, clearing the +1.0 floor) but inconsistently between the two runs
(+1.56 then +0.60) and despite `ph_Fin` rising both times, so the headline gain plausibly comes
from slack outside the renderer-finish path this judge measures, not from surfgpu removing wait on
this title. `nodisp` (surfgpu's no-display-surface-needed counter) stayed at 0.02-0.07/flip, well
under the 0.2 floor NBA Live's mechanism cleared -- Forza rereads its surfaces for a reason
surfgpu's dedup path does not avoid here, plausibly the HUD/minimap feed visible as `tobuf`.

This already ships (surfgpudefault1009, folded 7d574ece8b) -- nothing to flip. It is a real,
modest, net-positive change for Forza (gfps up, nothing scored regressed outright), but it is not
the fix for Forza's surface-download wait; most of that wait is still there, just under a
different name.

**Follow-on (brief step 5(c)'s proposal, with this lane's numbers as its P x win):** a GPU-side
surface-to-texture conversion at the `texture.c` call site (`create_texture()`'s call into
`pgraph_vk_download_surfaces_in_range_if_dirty`), the same shape of fix surfgpu1009 built for
`surfupd`/`reuse`, applied to the `range` caller surfgpu structurally cannot reach. P (probability):
high that the mechanism generalizes -- surfgpu1009 already proved the GPU-side-rebind approach
works for one caller on this render path; `range`'s call site is the same kind of
surface-read-back, just a different trigger (texture creation vs. display-surface rebind). Win
(size): `range` averages 9.69 ms/flip with surfgpu on, now the single largest `[sdcall]` caller on
Forza and larger than the `surfupd` wait this lane originally set out to measure -- removing it
would address the P2/P3 FAILs (sum ratio, ph_Fin) that this lane's data shows surfgpu leaves open.
Not written here (brief step 5 is explicit: propose, do not implement).

Prediction: `docs/testing/predictions/forzasurf1010-ab.json`, registered before any scored run,
`a_ref`=`b_ref`=`ab1acc4154`. Pilot verdict: `dispatch/pilots/forzasurf1010.ok`. All four runs'
result dirs on disk under `dispatch/results/` (ids in NOTES.md sections 4 and 7).
