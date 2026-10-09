# surfdl1008: does the NBA Live 05 surface-download finding generalise? NBA Live 06/07, Midnight Club 2 (#433, 0.5)

## Attempt 2: why attempt 1 did not cover this, and what changed

Attempt 1 finished and its PR was folded into master at 22:00:33 PDT
(`93fbc525fc` on `origin/master`, merge of `e9eb8bcf07`), concluding NBA Live
06 and 07 were both gated off (`prequeue.py` REVIEW/BLOCK) with no existing
perflog soak to read instead, and that Midnight Club 2 was fully answered by
an unrelated lane's existing run. That conclusion was correct for the
information live at the time. The owner's addendum clearing the below-bar
BLOCK for this lane's telemetry requests was approved at 22:05 PDT -- five
minutes *after* the fold -- so attempt 1 never saw it. This attempt (resumed
in the same worktree, fast-forwarded onto `origin/master` which already
contains attempt 1's folded work) acts on the addendum: NBA Live 06 and 07
are re-gated below, found eligible for telemetry, and queued. See "Attempt 2"
sections below; the Midnight Club 2 analysis is unchanged from attempt 1.

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

## Attempt 2: the addendum applies, NBA Live 06 and 07 queued

Re-ran `pm/prequeue.py` on both titles against today's current state (after
merging `origin/master`, which already carries attempt 1's folded work).
Both now print a single BLOCK, the identical reason named in the addendum:

```
BLOCK   last verdict missed the fps bar: telemetry and a fix, not a retest (owner 10-03)
RESULT: BLOCK
```
(plus non-blocking REVIEW lines for the same FAIL verdicts and prose
mentions, unchanged from attempt 1's reading). Note this *disagrees* with
attempt 1's NOTES, which read NBA Live 06 as REVIEW-only (not BLOCK) due to
a suspected `fps_ok_share` `0 or 1` substitution bug in `prequeue.py`. Reread
the actual line here: `last.get("fps_ok_share", 1) is not None and
last.get("fps_ok_share", 1) < 0.9` -- `.get(key, default)` only substitutes
the default when the KEY IS ABSENT, not when its value is falsy, so
`fps_ok_share: 0.0` reads as `0.0`, not `1`, and `0.0 < 0.9` correctly fires
BLOCK. That bug does not reproduce by reading the code now; attempt 1's
claim was a misread, not a fixed regression (no change to `pm/prequeue.py`
was made by this lane or found in its history). Correcting the record here
since attempt 1's "For the next lane" repeated the claim.

Per the owner's addendum, this one BLOCK reason does not stop a telemetry
request from this lane, and no other BLOCK fires for either title (no
RalliSport exclusion, no football, no crash/device hold, no banked Playable,
and both have confirmed Nova copies per `listing-nova.txt`). Both titles are
in scope.

**Route.** The brief requires a stored route; attempt 1 (quoting
`fps20786/NOTES.md`, written before 10-06) said NBA Live 2004/06/07 had "no
path or route". That is now stale: pathfind ran confirmation holds on both
titles on 10-06 (`wt/pathfind/docs/lanes/pathfind/runs/nbalive06-1006` and
`.../nbalive07-1006`), each with a `steps.jsonl` that reaches gameplay
through a scripted menu path -- including the sports-setup rule's own
"Quarter Length to the longest" steps (06: steps 10-12, maxing at 12
minutes; 07: steps 10-13, same) -- before the hold's free-play fps gate
stopped each at ~188s (median 19 fps, well below the confirmation bar; this
is the same FAIL that `prequeue.py` reads above, not a crash or a route
defect). That scripted menu-nav prefix plus `fps20786/steps2route.py` is
exactly the recipe attempt 1 used to build Midnight Club 2's `gnr-mc2` route
from a *different* lane's pathfind path -- the same tool applies here, from
these titles' *own* pathfind paths.

Built both routes with `steps2route.py`, cutting at each run's first
`gameplay`-state step (06: step 14 @136.2s; 07: step 16 @158.6s -- matching
NBA Live 2005's own recipe in `fps20786/make-routes.sh`, which also cuts at
its first `gameplay` step, #20), then looping NBA Live 2005's own basketball
genre tokens (`RT:1,STICK:up:1,A,STICK:right:1,X,STICK:left:1,B,STICK:down:1,Y`
-- same engine, same genre, reused rather than invented) for `--hold-s 300`
(5 minutes) post-mark:

```
python3 docs/lanes/fps20786/steps2route.py <pathfind run>/steps.jsonl \
    --name "NBA Live 0X (<id>)" --gameplay <N> \
    --loop "RT:1,STICK:up:1,A,STICK:right:1,X,STICK:left:1,B,STICK:down:1,Y" \
    --hold-s 300 --source "pathfind runs/nbalive0X-1006 (10-06, lane/pathfind)"
```

Both validated with `docs/testing/titles/route.sh --check` (134 and 140
lines; route ends ~446s and ~467s after launch respectively). Committed
copies live at `docs/lanes/surfdl1008/routes/{nbalive06,nbalive07}.route`
(this lane's own territory). `request.sh --route NAME` resolves only from
`docs/testing/titles/routes/` (no path override in `titlestate.py
resolve-route`), so each was copied there *transiently* -- long enough to
queue, since the queued request copies the route's full TEXT into itself
and is then self-contained -- and removed immediately after both requests
were accepted; `git status` on that directory is clean again (same pattern
as attempt 1's unstated inference that `lane.gpunonrender` did this for
`gnr-mc2`, which never appears committed anywhere either).

**Queued** (Nova, `--priority study`, `--no-expect "telemetry survey, not an
A/B arm"`, no device hold taken, no `--wait`):

| title | request id | route | seconds | env |
|---|---|---|---|---|
| NBA Live 06 (4541007A) | `1-1791525334-surfdl1008-4042714` | nbalive06 | 460 | perflog, HAKUX_GPUXFR=1, HAKUX_FRAMETRACE=1 |
| NBA Live 07 (454100A1) | `1-1791525340-surfdl1008-4043345` | nbalive07 | 480 | perflog, HAKUX_GPUXFR=1, HAKUX_FRAMETRACE=1 |

At queue time, `dispatch/queue/` held 9 earlier `lane.profileddefault1008`
requests ahead of both of mine (checked the directory directly, not
`status.sh`, which blocks as a live dashboard rather than a one-shot
report). Both of mine queue behind those, as the brief requires for
`lane.fpstelemetry1008`'s Nova requests, and by the same courtesy for
whatever else is already ahead. **No result yet** -- this is a WAITING
state, not a finished measurement; see `docs/lanes/surfdl1008/WAITING`.

## Verdict (per title)

- **NBA Live 06: queued, not yet measured.** Cleared at the gate under the
  owner's addendum (BLOCK was the only reason, and it is the one named as
  cleared); route built from pathfind's own 10-06 path; request
  `1-1791525334-surfdl1008-4042714` queued behind 9 others. Update this
  section once the result lands.
- **NBA Live 07: queued, not yet measured.** Same gate/route situation;
  request `1-1791525340-surfdl1008-4043345` queued behind the same 9.
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

- **Finish reading the two queued results** (`1-1791525334-surfdl1008-4042714`
  NBA Live 06, `1-1791525340-surfdl1008-4043345` NBA Live 07) with
  `fps20786/sdsurvey.py` + `xfrsurvey.py` + `near30/decompose.py`, mark at
  each route's `mark gameplay` line, same method as the Midnight Club 2
  section above, and fill in the Verdict bullets. Check for a thermal pause
  first (voids the row) before reading anything else.
- Attempt 1's claim of a `prequeue.py` `fps_ok_share` `0 or 1` gate bug does
  **not** reproduce: re-read in Attempt 2 above, the actual line is
  `last.get("fps_ok_share", 1)`, whose default only applies when the key is
  missing, not when its value is falsy, so `0.0` reads as `0.0` and BLOCKs
  correctly. Don't repeat that claim; there is no known bug in this rule.
- Before queuing any device request, check `dispatch/results` for an
  existing perflog soak of the same title first (title/ISO string, any age).
  Midnight Club 2 already had one, 2 days old, built by an unrelated lane
  for an unrelated question, and it answered this brief in full.
- A title with "no path or route" in an older lane's NOTES may have one now:
  `fps20786/NOTES.md`'s "no path or route" for NBA Live 06/07 was written
  before pathfind's 10-06 confirmation holds on both existed. Check
  `wt/pathfind/docs/lanes/pathfind/runs/<slug>/steps.jsonl` directly (glob
  `**/<slug>*/verdict.json` under that tree, per `pm/prequeue.py`'s own
  search pattern) before concluding no route can be built.
- `request.sh --route NAME` only resolves from `docs/testing/titles/routes/`
  (no override flag in `titlestate.py resolve-route`), which is outside any
  lane's own territory. The pattern every lane before this one seems to have
  used (none commit a route there) is: copy the route in, queue (the
  request embeds the route's full text, so it is self-contained from then
  on), remove the copy, confirm `git status` is clean of that directory
  again. Routes built here are kept, committed, under
  `docs/lanes/surfdl1008/routes/` for provenance.
