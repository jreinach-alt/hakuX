# surfdl1008: does the NBA Live 05 surface-download finding generalise? NBA Live 06/07, Midnight Club 2 (#433, 0.5)

Brief (owner order 10-08 ~21:30 PDT, dispatched directly by lane.local, no issue):
NBA Live 05 makes one synchronous surface-download finish per frame
(`fps20786`, filed as #794; `async794` built and refuted fix 1 for NBA's own
caller). Question: do NBA Live 06, NBA Live 07 and Midnight Club 2 show the
same per-frame download, with the same share of Tot?

## Gate: which of the three can run at all (pm/prequeue.py, Nova only)

Per the brief, a title is queued only if its ISO is already on the Nova
*and* `python3 pm/prequeue.py "<title>"` prints `CLEAR`. `pm/` is outside
this worktree; reached it with `python3 /home/justin/hakux-work/pm/prequeue.py`
(Bash blocks `ls`/`cat` outside the worktree, python3 does not —
[[lane-sandbox-blocks-board-requests]]).

| title | ISO on Nova | prequeue.py | queued? |
|---|---|---|---|
| NBA Live 06 (4541007A) | yes (`listing-nova.txt` 10-04; title-registry `nova` tag) | **REVIEW** (every verdict on disk is a FAIL; last `nbalive06-1006` 2026-10-06 23:31, median 19.98 fps, fps_ok_share 0.0, only 187 s of the 600 s confirmation) | no |
| NBA Live 07 (454100A1) | yes (same listing/tag) | **BLOCK** ("last verdict missed the fps bar: telemetry and a fix, not a retest (owner 10-03)"; last `nbalive07-1006` 2026-10-06 23:39, median 19.99, fps_ok_share 0.011) | no |
| Midnight Club 2 (54540008) | yes (not in `listing-nova.txt`'s 10-04 snapshot, but the 10-06 run `sweep-54540008`'s own `request.json` has `"device": "nova"`, and today's active Nova-space-freeing deletion list (`wt/pathfind/scratch/nova-free-1008.list`) does not name it) | **CLEAR** ("no record found" in the ledger/registry/holds the script checks) | yes, see below |

Only Midnight Club 2 clears the gate. Neither NBA title is run here, by the
brief's own rule (`must print CLEAR`), even though in NBA Live 07's case the
BLOCK text is literally describing a policy of "telemetry and a fix, not a
retest" -- which sounds like exactly what this lane is -- and in NBA Live
06's case the BLOCK did not fire only because `prequeue.py`'s rule reads
`last.get("fps_ok_share") or 1`, and NBA 06's share is exactly `0.0`, which
Python's `or` treats as falsy and silently replaces with `1` (not `< 0.9`,
so no BLOCK -- only the weaker REVIEW). NBA 06's true result (0% of 62
windows at the bar) is at least as bad as NBA 07's (1.1%). This is a gate
bug, not a reason to route around the gate myself: the brief's rule is a
flat "must print CLEAR," and second-guessing a BLOCK/REVIEW from inside the
lane that rule exists to constrain is the failure mode the gate is for. Both
are left for the owner/lane.local to clear explicitly if a telemetry-only
run on either title is wanted despite the below-bar holds.

No existing perflog soak of NBA Live 06 or NBA Live 07 exists anywhere in
`dispatch/results` either (searched by title string, ISO filename and title
id across every result directory, no age cutoff): nothing to read offline
in place of a run. **NBA Live 06 and NBA Live 07: not measured, skipped at
the gate, no device time spent.**

## Midnight Club 2: an existing perflog run already answers this, read instead of queuing a new one

Before queuing, checked `dispatch/results` for any existing perflog soak of
Midnight Club 2 (by title/ISO string, no age cutoff; [[never-rerun-a-script-to-read-its-output]]
applies to device runs too -- don't spend device time re-measuring what is
already on disk). One exists: `1-1791274137-lane.gpunonrender-2624798`
(2026-10-06, ref `5eef1dacd9`, Nova, `perflog=true`, `HAKUX_GPUXFR=1`, 330 s,
route `gnr-mc2`). That route was itself built by `lane.gpunonrender` with
`fps20786`'s own `steps2route.py`, from pathfind's recorded, complete
gameplay path `pathfind/docs/lanes/pathfind/runs/sweep-54540008` (the same
method this brief would have used to build a route from scratch, already
done and already run). It lacks `HAKUX_FRAMETRACE=1` (the brief's third env
var), but none of the three named instruments (`sdsurvey.py`, `xfrsurvey.py`,
`near30/decompose.py`) read anything that env var adds; they read
`hakuX-stall`, `hakuX-phase` and `xemu-gpu` lines, all present under plain
perflog. Reading this run in place of queuing a fresh one saves the device
time and this lane's $25 cap for nothing measurable in return. **No Nova
request was queued in this lane.**

The run's route marks `mark gameplay` at logcat timestamp `03:50:05.334`
(`run.log` line 73, after the 14 scripted menu/cutscene steps). Decomposed
with `fps20786/decompose.py --mark 03:50:05` (its own copy, which adds
`--mark` over `near30/decompose.py`) and `fps20786/extras.py` with the same
mark; cross-checked against `lane.gpunonrender`'s own `[sdcall]`
caller-attribution instrument from the same run (its NOTES.md, "Scope (B)").

### Measured, post-mark, all 97 of 97 two-second rows (194 s of play)

No thermal pause (`decompose.py` THERMAL line: "no thermal-pause device
above 0"); row not voided.

| metric | value |
|---|---|
| gfps (mean, these rows) | 24.32 |
| share >= 28.5 | 0.00 (every row below the bar) |
| VBLANKs per flip | v2 0.53, v3 0.47 -- on the 2-vs-3-VBLANK edge |
| F (ms/frame) | 41.11 |
| Ri (render thread parked) | 0.00 -- never parks, fully saturated |
| rcpu + rblk (= F - Ri) | 25.79 + 15.30 |
| gbusy / gidle | 13.42 / 27.74 -- guest mostly idle |
| lockw (vCPU pgraph.lock wait) | 0.00 -- no lock contention |
| ph_GPU | 34.60 |
| ph_Draw | 16.40 |
| ph_Fin (Sub 13.5 + Fen 2.9) | 16.45 |
| ph_Tot | 34.40 |
| hakuX-stall sd/flip (median, 86 post-mark RPBreaks lines) | 1.50 (dirty 0.50 + cDef 1.00) |

Share of Tot: ph_Fin / ph_Tot = 16.45 / 34.40 = **48%**; ph_Fin / F = 40%.

Cross-checked against `sdsurvey.py` run over the whole logcat (menus
included, so it ranks, it does not judge -- its own documented caveat):
sd/fl 1.50, dirty 0.50, cDef 1.00, Fin 16.3, GPU 34.2, gfps 24 -- matches the
post-mark numbers to within rounding, so the two cold-start menu rows before
the mark do not move the read.

### What the plain phase.Fin number cannot see, and what `lane.gpunonrender`'s own instrument adds

`ph_Fin` (hakuX-phase) bundles **every** finish a frame waits on: the
surface-download finish this lane is asking about, *and* the flip's own
`pgraph_vk_finish(VK_FINISH_REASON_FLIP_STALL)`, which every title pays at
every flip regardless of surface downloads. `sdsurvey.py`'s `Fin` column
inherits the same blur ([[what-the-instrument-cannot-see]]). `lane.gpunonrender`'s
`[sdcall]` lines, from the same run, split the wait by caller and give the
surface-download share specifically:

| per frame (lane.gpunonrender, same run) | value |
|---|---|
| `[sdcall]` `range` caller: finishes, wait | 1.00, 7.98 ms (dl 2.5) |
| `[sdcall]` `record` caller: wait | 0.01 ms |
| `[sdcall]` all callers: wait | **8.00 ms** |
| `xemu-gpu` Tot / Rnd / Xfr | 34.6 / 33.8 / 0.8 |

So of the blunt 16.45 ms `ph_Fin`, about **8.0 ms is the surface-download
finish** this lane is asking about, and the remaining ~8.4 ms is the flip's
own fence wait -- present on every title, not part of this mechanism, and
not removable by any fix to surface downloads.

### The caller is different from NBA's, and it is the class async794 already showed deferral cannot fix

`lane.gpunonrender`'s NOTES.md names the call site directly: **`texture.c:2100`**,
inside `create_texture()` (`hw/xbox/nv2a/pgraph/vk/texture.c`), where a
texture bind that cannot read a surface's image directly falls back to
`pgraph_vk_download_surfaces_in_range_if_dirty()` -- a scan over the
surface list that forces a pending download to complete, because the
texture is about to be read from VRAM rather than from the surface's own
image. This is the `range` caller in `[sdcall]`'s naming, read above.

NBA Live 2005's wait (the one `fps20786` found and `async794` built fix 1
against) is a *different* caller: `reuse`, in `hw/xbox/nv2a/pgraph/vk/surface.c`
(`deferred_downloads_clear_surface` / `download_surface_complete_deferred_at`),
triggered by unshelving a struct that names a pending download, with nobody
yet consuming the bytes at the moment of the wait. `async794`'s pilot
(NOTES.md, "The pilot: fix 1 is refuted") showed that even on NBA's own
`reuse` site, deferring the wait to the guest's next sync point does not
remove it when something else consumes the downloaded bytes first: NBA's own
`surfupd` rebinding does an image -> VRAM -> image round trip that must
complete the download regardless of deferral. `async794`'s survey of the
*other* titles (Counter-Strike, Top Spin: `txr dl`, a texture bind's direct
synchronous download) found the same shape: "the consumer is the emulator
itself, on the CPU, immediately; no amount of deferral removes that wait.
What removes it is a GPU-side path from the surface image to the texture...
which conversion is needed depends on why the bind refused the surface."

Midnight Club 2's `range` caller is in that second class, not NBA's first:
`texture.c:2100`'s scan exists precisely because the texture bind already
decided it cannot read the surface's image directly (`!surface_to_texture`),
so the same async794 finding applies by the same reasoning, without needing
a separate pilot: **moving the wait to the guest's next sync point would not
remove it**, because the consumer (the texture upload from VRAM) runs on the
emulator's own CPU path before the guest could observe anything either way.
What would have to change is `texture.c:2100`'s call site -- a GPU-side
surface-to-texture conversion so `create_texture()` never needs
`pgraph_vk_download_surfaces_in_range_if_dirty()` for this bind shape -- not
`surface.c`'s `reuse`-site deferral that `async794` built and folded (fix 2
only; fix 1 was stripped).

### Caveat: even that fix would not, by itself, clear 30 fps here

NBA Live 2005's GPU cost alone (18.5 ms/frame) was comfortably under the
33.3 ms two-VBLANK ceiling, so fps20786/async794 could say the serial
renderer was the *whole* story: remove the finish wait, and the renderer's
cost drops under 33.3 and the title gets two VBLANKs instead of three.
Midnight Club 2's `ph_GPU` is **34.60 ms/frame already, on its own, above
that ceiling** (unlike NBA's 18.5 or Counter-Strike's 24.6, both measured
comfortably under in fps20786). Removing the full 8.0 ms `range` wait would
likely narrow the v3 share (0.47 today) but is not shown here to guarantee
clearing the bar by itself -- that would need a fix to the surface-to-texture
conversion to also not add GPU work of its own, which is outside what this
lane's instruments can see (decompose.py and `[sdcall]` give per-frame CPU/
wait time, not where inside the GPU's 34.6 ms a converted path would land).

## Verdict (per title)

- **NBA Live 06: not measured.** Blocked at the gate (prequeue REVIEW, not
  CLEAR); no existing perflog soak to read instead.
- **NBA Live 07: not measured.** Blocked at the gate (prequeue BLOCK, owner
  10-03 policy); no existing perflog soak to read instead.
- **Midnight Club 2: partial generalisation, different caller.** The same
  class of bound is present (a synchronous `SURFACE_DOWN` finish
  serialising the render thread against the GPU, ~8.0 ms/frame of it, with
  no pgraph.lock contention since the guest is mostly idle), but the forcing
  caller is `texture.c:2100`'s surface-range scan (the texture-bind class),
  not NBA's `surface.c` `reuse` site. async794's own evidence on the
  structurally identical texture-bind class (Counter-Strike, Top Spin)
  already shows the NBA fix (deferral) would not remove this wait; the
  function that would have to change is `create_texture()`'s call to
  `pgraph_vk_download_surfaces_in_range_if_dirty()` at texture.c:2100,
  replaced with a GPU-side surface-to-texture conversion -- and even that is
  not shown here to be sufficient alone, since Midnight Club 2's GPU cost
  (34.6 ms/frame) already exceeds the 33.3 ms ceiling before the finish wait
  is counted at all. No patch attempted (out of scope).

## For the next lane

- Don't re-run NBA Live 06/07 without clearing the gate first (prequeue
  REVIEW/BLOCK); if the owner wants telemetry on either despite the
  below-bar hold, that needs an explicit exception recorded against the
  hold, not a lane routing around `prequeue.py`'s RESULT line.
- `pm/prequeue.py`'s fps-bar BLOCK rule (`last.get("fps_ok_share") or 1 <
  0.9`) misses a verdict whose `fps_ok_share` is exactly `0.0` (Python's
  `or` treats it as missing and substitutes `1`). NBA Live 06 is the live
  example. Not fixed here (outside this lane's territory: `pm/` is not under
  `docs/lanes/surfdl1008/**`); flagging for whoever owns `pm/prequeue.py`.
- Before queuing any device request, check `dispatch/results` for an
  existing perflog soak of the same title first (title/ISO string, any age).
  Midnight Club 2 already had one, 2 days old, built by an unrelated lane
  for an unrelated question, and it answered this brief in full.
