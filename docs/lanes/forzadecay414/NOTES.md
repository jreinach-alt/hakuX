# lane.forzadecay414 -- Forza's 29 -> 3 fps decay: clock or game? (#414 item 1)

Base master 85347ffbd1. Title 4D53006E (Forza Motorsport), survey route, both handhelds.
Reader: `docs/lanes/forza414/timeline.py <logcat>` (30-s rows, t = 0 at `soak start`);
scratch scripts that walked `dispatch/results/*` are not committed. The `fps` column below is
timeline.py's (flips from gfps lines per bucket), so it differs a little from the brief's
curve, which came from another reader. The last bucket (t = 420) is a partial window in every run.

## 1. Every Forza soak on disk

17 soaks with a logcat (`request.json` title `4D53006E`). One more, `1790450270-forza414-1731994`,
is `ERROR: title not on device` (the Nova, before the ISO was staged). `thermal.jsonl` exists only
from the flip474 pair onward. `inv` is the `[watch311]` line's `invalid=`, the length of
`r->invalid_surfaces`.

| result | device | ref | 30-s fps, t = 0..420 | max inv | xo start -> end | hottest cpu zone | pause engaged at t |
|---|---|---|---|---|---|---|---|
| `0-0-x-1790525921-forza414-1054756` | nova | 4b22f2526b | 14 28 30 20 10 18 20 22 26 22 30 28 30 28 4 | 91 | not recorded | - | - |
| `0-0-x-1790525923-forza414-1055334` | nova | 94f002d309 | 14 30 28 22 10 20 18 26 26 24 30 28 30 28 6 | 240 | not recorded | - | - |
| `0-0-x-1790533007-forza414-3417242` | nova | 7787feb2ae | 14 30 28 22 8 20 20 22 26 24 30 28 30 30 2 | 62 | not recorded | - | - |
| `0-0-x-1790533010-forza414-3422338` | nova | 51721e36aa | 14 30 28 22 10 20 20 22 26 24 30 30 28 30 | 72 | not recorded | - | - |
| `1-1790492278-slowdown462-690198` | nova | e5db66fa37 | 12 30 28 24 8 18 20 22 28 24 20 20 14 - - | 143 | not recorded | - | - |
| `1-1790518618-forza414-1930404` | nova | 4b22f2526b | 12 30 28 22 8 18 20 22 26 24 26 24 28 28 | 50 | not recorded | - | - |
| `0-0-y-1790408503-titlebench-8` | thor | 6561442869 | 12 30 30 30 30 28 30 30 26 (front end only) | 11 | not recorded | - | - |
| `0-0-y-1790433159-titleplay-p1-forza` | thor | a5b5b628f2 | 10 30 28 22 6 12 12 14 14 20 **2 4 4 2** - | 188 | not recorded | - | - |
| `1790450265-forza414-1731727` | thor | dc38b745b8 | 14 30 28 24 8 14 14 14 16 20 18 16 18 20 2 | 52 | not recorded | - | - |
| `1790467161-titlebench-2613303` | thor | d0e30924f8 | 12 30 28 20 2 16 14 14 **2 4 2 4 4 2** - | 65 | not recorded | - | - |
| `0-0-x-1790549041-flip474-1818830` | thor | 09fdca3ba1 | 12 30 28 24 2 16 14 14 14 18 **6 4 2 4** - | 138 | 67.4 -> 73.8 (78.1 at t = 300) | 95.4 | **330-420** |
| `0-0-x-1790549042-flip474-1819047` | thor | 09fdca3ba1 | **- 4 8 6 4** 12 14 14 16 20 20 **4 4 2 2** | 61 | 73.1 -> 74.6 (78.0 at t = 330) | 95.0 | **0-120, 360-420** |
| `1-1790552636-forza414-3224517` | thor | 35ee65562a | 12 30 28 24 4 18 18 18 20 24 22 22 24 22 8 | 147 | 60.4 -> 76.0 | 95.0 | none |
| `1-1790561602-forza414-3260817` | thor | 53c81b1a7a | 14 30 28 24 4 18 18 16 22 24 18 20 20 18 6 | 90 | 53.4 -> 78.0 | 95.8 | none |
| `1-1790613195-forza414-3088454` | thor | fa56a26f1f | 12 30 28 24 6 **12 10 8 6 6 6 4 6 4 2** | **4099** | **44.7** -> 72.6 | 95.0 | none |
| `1-1790619761-forza414-1092424` | thor | fa56a26f1f | 14 30 28 22 6 **12 8 8 6 6 6 4 4 4 2** | **3796** | 58.5 -> 74.8 | 96.2 | none |
| `1-1790619761-forza414-1092523` | thor | b991fb4c21 | 14 30 28 24 4 **12 10 8 6 4 6 4 4 4 2** | **3679** | 61.7 -> 75.1 | 96.2 | none |

(`1-1790613195-forza414-3088504` aborted before its first input and has no rows.)

- **There is a Nova Forza race: six soaks, none decays.** 18-30 fps through the race to the end.
  All six are on refs from before #517 (section 3), so they do not separate the device from the
  code.
- **There is a cold-started Thor run on the decaying code:** `3088454`, xo-therm 44.7 C at the
  start, below the brief's 50 C bar. It decays exactly like the two warm runs (58.5 and 61.7 C):
  12 -> 2 fps from the same bucket, with no cooling device at any sample and xo never above 72.6.
- **A Thor run held its race rate with the big cores at 95 C the whole way:** `3260817`
  (53c81b1a7a), with `cpu-1-*` at 92-96 C from t = 30 to the end and xo climbing to 78.0 C,
  ran 16-24 fps from t = 150 to t = 390. `3224517` (35ee65562a) did the same at 94-95 C: 18-24 fps.

## 2. Two different mechanisms, and neither is H1

The decaying runs fall into two regimes with different signatures. They were read as one curve.

**Regime S, the step: the xo-therm 78 C thermal pause (#507).** One step into 2-4 fps with the
renderer mostly idle (Ri 150-290 ms of a 250-400 ms flip), vCPU time down from ~1900 to
~1300-1400 ms per 2 s, and audio zero-filled 35-52%. This is lane.forza414's NOTES section 1
signature. Where `thermal.jsonl` exists, it lands in the bucket where xo-therm reaches 78 C, and
the next sample shows `thermal-pause-F8` (cpus 3-7 paused) and the kgsl devfreq cap engaged.
`0-0-x-1790549042-flip474-1819047` shows both directions. It starts paused (xo 73 C after the
previous arm), at 4-8 fps. It recovers to 12-20 fps once the pause releases at t = 150. It steps
back to 2-4 fps at t = 330, when xo reaches 78.0 C. The two older Thor runs with the same
signature (`titleplay-p1-forza`, `titlebench-2613303`) have no thermal log, so their pause is
inferred from the signature, not read. This is visible heat throttling, already owned by #507.
It is not the brief's H1: that one was invisible LMh/DCVS capping at the junction limit.

**Regime L, the linear decay: `r->invalid_surfaces` grows without bound.** It is the curve in the
brief: 12 -> 2 fps over the race, with no step. It is present in exactly the three runs on
fa56a26f1f and b991fb4c21, and absent in every other run on either device. In `1092424`, per
30 s from t = 150: `inv` 918, 1461, 1935, 2305, 2625, 2948, 3234, 3463, 3691, 3796, with
`[watch311] live` tracking it (each dirty invalid surface keeps its CPU-access watch). G (flip
interval) rises 81 -> 287 ms, the TB invalidate calls per 2 s rise 22750 -> 42274, and the
vCPU's time falls 1816 -> 1524 ms per 2 s. Audio never starves (0%), and no cooling device
engages. The `txw` probe names where the frame's time goes. `scan`
(`pgraph_vk_download_surfaces_in_range_if_dirty`) runs at a steady ~780-930 calls per flip, but
its time climbs linearly: 0.84 ms/flip at 11:26:02, 5.42 at 11:26:36, 13.14 at 11:27:45 and 25.56
at 11:30:44 PDT, which is ~1 us per call at the start and ~33 us per call at the end. `faf`
(`pgraph_vk_flush_all_frames`) is 0.00 calls per flip in every race line.

**The verdict on H1 and H2.** Neither holds as written.
- **H1 (hardware clock capping near the junction limit) is refuted as the cause of either
  regime.** Every H1 prediction fails on data already on disk. The cold start (`3088454`, 44.7 C)
  does not delay the decay. The big cores sit at 94-96 C in runs that do not decay
  (`3260817`, `3224517`). And the decay tracks a list length, not a temperature: `3088454`
  reaches 2 fps at xo 72.6 C, while `3260817` holds 18 fps at 78.0 C. If LMh caps the big cores
  at 95 C, it caps them equally in the runs that hold their rate, so it is not what separates them.
  The clock fields (section 4) will show whether it caps at all. They are not needed for this verdict.
- **H2 as framed (a game-state regime, the same point in the game regardless of temperature or
  device) is half right.** The decay is temperature-independent, but it is not the game's state.
  It is the emulator's: a surface list that stopped being pruned. It began with one commit
  range and does not appear on any earlier ref, on either device.

## 3. Why the list grows (read in code; the bisect arm tests it)

- `invalidate_surface()` (vk/surface.c:2747) stamps a surface invalidated inside the open command
  buffer with `invalidation_frame = r->current_frame`. That is a ring-slot index, and nothing
  resets it afterwards (the only other writes are -1 at creation and for a surface invalidated
  outside a command buffer).
- `surface_in_flight()` (surface.c:3305) is `f == r->current_frame || frame_submitted[f]`. In
  steady state every slot other than the current one is submitted: a slot's flag is cleared only
  as it becomes the next frame (draw.c:3790), and it then becomes current. So a stamped surface
  reads as in flight forever.
- `prune_invalid_surfaces()` (surface.c:3332) skips an in-flight surface. The only thing that
  makes one prunable is `pgraph_vk_flush_all_frames()` (draw.c:3398), which clears every
  `frame_submitted[]` at once, so any slot that is not current reads false until it is submitted
  again.
- **#517 (lane.drain474, fold 09050ddbe5)** moved that flush in `create_texture` from before every
  surface-to-texture bind of a recently submitted surface to the copy branch only. Forza's race
  binds directly, so after #517 nothing flushes there: `faf` 0.00 per flip. Before #517 the
  flush ran on those binds and the list stayed at 10-240. The 24 soaks of other titles on refs
  containing #517 (Blinx, AUF, DOA, Crimson Skies, Otogi, Kabuki) all peak at `invalid` 10-11. Either they
  do not invalidate surfaces inside the command buffer, or something else flushes for them.
- The cost: `pgraph_vk_download_surfaces_in_range_if_dirty` walks `invalid_surfaces` on every
  texture bind (surface.c:467), about 800 times a flip, and the dirty ones keep their CPU-access
  watch, so guest stores to their pages trap (the rising `ic`).
- The only emulator change between 53c81b1a7a (clean, `3260817`) and fa56a26f1f (decays) is #504
  (a start-up GPU timestamp-period probe, vk/renderer.c) and #517 (vk/texture.c). surface.c is
  identical between them.

**This is on master.** fa56a26f1f and 09050ddbe5 are both ancestors of 85347ffbd1, and no later
fold resets `invalidation_frame` or adds a flush to that path (read, not measured: the master
arm below measures it). Every Forza race on a build since the #517 fold (2026-09-27 20:42 PDT)
should decay this way.

**The fix is emulator code, which this lane may not edit.** Two shapes, for the owner of
vk/surface.c: make "in flight" a submission count rather than a slot index (stamp
`r->submit_count` at invalidation, and treat the surface as in flight while fewer than
`num_active_frames` submissions have completed since), or reset `invalidation_frame` to -1 for
every surface stamped with a slot when that slot's fence is waited. Either keeps #517's saving.
Putting the flush back would undo #517. (lane.local's addendum of 12:50 PDT then gave this lane
the file. The fix is PR #583, the second shape.)

## 4. The instrument: clocks in every thermal sample (done: PR #588, sections 7 and 8.4)

`docs/testing/thermal_state.py` is in lane.fanduty507's PR #571, which is open (ready, not folded).
Per the brief, it is not edited before then. Board request:
`$DISPATCH_DIR/board-requests/forzadecay414.md` asks for the file after #571 folds. The fields:
per-policy `scaling_cur_freq` (policy0, 3, 7), whatever `scaling_max_freq` is readable, and the
kgsl `gpuclk` and `throttling`. Section 2 no longer needs it. It stays worth doing for the heat
track, because it is the one way to see LMh capping in any soak.

## 5. The discriminating runs

The brief's legs were Thor cold against Thor warm, plus the Nova. The cold-against-warm half is
answered by `3088454` against `1092424`/`1092523` (section 1): same code, 44.7 C against
58.5/61.7 C, the same curve. So no cold slot was asked of lane.local. What the data does not yet
show is the commit, on a device that never pauses. Registered before any device run (both files
at 2026-09-28T19:41:21Z), Nova, survey route, 360 s, perflog, max:

| file | A | B | legs |
|---|---|---|---|
| `forzadecay414-bisect.json` | f82e7e87fe (master before #517) | 09050ddbe5 (#517 fold) | M0 race reached; P0 A flushes (faf >= 0.2/flip), B does not (<= 0.02); P1 B's invalid >= 1000; P2 A's invalid <= 400; P3 fps t = 270-330 B/A <= 0.6 |
| `forzadecay414-master.json` | f82e7e87fe (same A run) | 85347ffbd1 (master) | M0; P1 master's invalid >= 1000; P3 B/A <= 0.6 |

Each leg's failing world is in the file. In short: P0 fails if A does not flush either, so the
flush is not the link. P1 fails if #517 alone does not leak on the Nova, so #518's pending
pre-download or the Thor is part of it. P2 fails if the leak predates #517. P3 fails if the list
costs the Nova no fps. The master legs fail if a later fold already stopped it. The three soaks
are 3 x (360 + 90) s = 22.5 min of device time, under the 30-min pilot line.

Queued 2026-09-28 ~12:43 PDT at release priority by `docs/lanes/forzadecay414/queue.sh`. Each
request's expect_sha was read back and matches its file (f7c4565c56dc bisect, ce4ca9775edd master):

| request | ref | role |
|---|---|---|
| `1-1790624588-forzadecay414-3394734` | f82e7e87fe | A of both |
| `1-1790624588-forzadecay414-3394828` | 09050ddbe5 | bisect B |
| `1-1790624589-forzadecay414-3394871` | 85347ffbd1 | master B |

### 5.1 What ran (2026-09-28 15:44-16:37 PDT), read with `judge.py`

`docs/lanes/forzadecay414/judge.py <result dir>...` prints every number here. No cooling device
rose above 0 in any sample, and xo-therm stayed under 55 C.

| result | ref | ran | fps, rows t = 150..330 | invalid max / last | faf calls/flip | list walk ms/flip, first -> last race line |
|---|---|---|---|---|---|---|
| `1-1790624588-forzadecay414-3394734` | f82e7e87fe, before #517 | 360 s | 16 20 20 28 26 26 28 | 199 / 17 | 0.15 | 0.08 -> 0.12 |
| `1-1790624588-forzadecay414-3394828` | 09050ddbe5, #517 | cut at 261 s, VOID | 12 10 6 | 1996 (t = 233) | 0.00 | 1.68 -> 8.96 |
| `1-1790624588-forzadecay414-3394828-r2` | 09050ddbe5 | cut at 276 s | 12 10 4 | 1954 (t = 227) | 0.00 | 1.97 -> 8.59 |
| `1-1790624589-forzadecay414-3394871` | 85347ffbd1, master | cut at 245 s, VOID | 12 10 2 | 1969 (t = 253) | 0.00 | 2.47 -> 8.78 |
| `-3394871-r2`, `-r3` | 85347ffbd1 | cut at 77 s and 66 s | never left the boot | - | - | - |

- **On the cool device, the build before #517 does not leak and both builds after it do.** The list
  reaches about 2000 entries 100 s into the race on 09050ddbe5 and on master, against 16-199 before
  #517. Over rows t = 150-210 the leaking builds run 8.0-9.3 fps against 18.7.
- **No run of a leaking build is whole.** The Nova's USB link dropped in each (hostops:
  `hold/nova.why`, write errors at low charge). Two of the drops came in the boot, before any list
  could grow, so the link and not the build is what cuts them. Hostops re-queued the two arms as
  `-3394828-r3` and `-3394871-r4`.

### 5.2 The legs, by the letter

| file | leg | reads | by the letter |
|---|---|---|---|
| bisect | M0 race reached (G >= 40 ms in rows 180-330) | A: G 50.5 48.3 35.8 33.8 36.6 33.5 | **fails its G clause, so the file reads VOID** |
| bisect | P0 A's faf >= 0.2, B's <= 0.02 | A 0.15, B 0.00 (cut runs) | **A's clause fails** |
| bisect | P1 B's last invalid >= 1000 | 1996 and 1954 by t = 233, cut runs | not read: no whole B run |
| bisect | P2 A's max invalid <= 400 | 199 | holds |
| bisect | P3 B / A fps, rows 270-330, <= 0.6 | B has no such rows. Rows 150-210: 0.50, 0.46 | not read |
| master | M0, P1, P3 | one cut run: invalid 1969 by t = 253 | not read |

Two of these thresholds were wrong when registered, and are reported as written.
- **M0 took a slow frame as the mark of the race.** A race that does not decay runs at G 33-36 ms,
  so the clause voids the one arm that is healthy. Section 1's Nova rows already showed 28-30 fps
  late in the race. The race is marked by the txw scan's calls per flip instead: 685-931 in the
  race and 0-85 in the menus, in every run that got there. A's last route frame
  (`155038-play.png`) shows the race HUD with the race clock at 2:07.
- **P0's 0.2 was a guess.** A flushes 0.13-0.15 times a flip, once in 7 flips, and its list is
  pruned from 199 back to 16-86. The leg's failing world was "A does not flush either". That is
  not what A shows.

**The verdict of section 2 stands, and the commit is #517**, on the evidence of one whole run and
three cut ones. What is still owed is P1 and P3 on whole runs of `-r3` and `-r4`. They are
reported in PR #583, which carries the fix and reads the same two runs for its own legs.

The instrument (section 4) is PR #588, folded as 4e3d69a69b. These soaks ran after it, so their
`thermal.jsonl` samples carry `clk`. With `cpu-1-9` at 92-95 C, every `hold` sample reads cpu7 at
3187 MHz of 3187 and the GPU at 615 of 680 MHz.

## 6. The fix (attempt 2, branch `lane/forzadecay414-fix`, stacked on #579)

**Why attempt 1 did not finish.** It ended as a correct wait on the three Nova soaks (section 5),
which cannot run before the owner's evening top-up. lane.local's addendum (12:50 PDT) then gave
this lane `vk/surface.c` and the fix, and the resume carried it.

**The change** (10fe2f59a7, one hunk in vk/surface.c): `pgraph_vk_drain_deferred_surface_releases(r,
frame)` also sets `invalidation_frame = -1` on every surface in `r->invalid_surfaces` stamped with
that slot. Of section 3's two options, this is the fence-wait reset, for two reasons:
- **The drain already runs exactly when a slot's fence is known complete.** Its callers are the
  frame rotation (after `vkWaitForFences` on `next_frame`), `pgraph_vk_flush_all_frames` (slots
  other than the current one), and the two finalizers. That is the lifetime the stamp models, and
  it is the lifetime this function already gives the retired images.
- **A submission count does not bound a slot's completion here.** `submit_count` also counts the
  render thread's inline submits (FLUSH, downloads), which wait their own fence but do not rotate
  the slot. A "fewer than `num_active_frames` submits since" test could then read a deferred,
  unwaited slot as done after a couple of inline submits.

It walks the invalid list once per rotation (bounded, ~10 entries once the leak is gone), and
touches nothing on the bind path. #517's move of the flush into the copy branch stays.

**Registered before any run, 2026-09-28T19:50:59Z, refs A 85347ffbd1 (master), B 10fe2f59a7:**

| file | sha256 | device | legs |
|---|---|---|---|
| `forzadecay414-fix-forza.json` | 7a94c4f53ce8 | Nova soak, 360 s | M0; B0 faf <= 0.02; B1 max invalid <= 400; B2 not growing; B3 scan <= 3.0 ms/flip and flat; D1 fps t 270-330 >= 0.8 x t 150-210; D2 B/A >= 1.5 |
| `forzadecay414-fix-auf.json` | 1f7a76a9f942 | Nova soak, 420 s, window 255-411 | M0; M1; K1 faf <= 0.02, bs 1.00; K2 bt <= A + 0.5 ms; K3 flips/s >= 0.95 A; K4 invalid <= 20 |
| `forzadecay414-fix-pixels.json` | a4436529a25c | arms job, all 100 golden suites, 2 runs/arm | every capture byte-identical within its band |

The failing world for each leg is in its file. A of the Forza file is the master arm already queued
(`-3394871`), so it is read once for both.

**Queued** 2026-09-28 12:53 PDT by `queue_fix.sh forza`: `1-1790625108-forzadecay414-3486226`
(10fe2f59a7, Nova, 360 s; read back: device nova, expect_sha 7a94c4f53ce8). That makes four Nova
soaks, 4 x (360 + 90) s = 30 min, the whole pilot allowance. **The AUF pair is not queued yet:** it
takes the requester past 30 min. On resume, read the four Forza soaks, write
`$DISPATCH_DIR/pilots/forzadecay414.ok` (result ids, whether the route reached the race, the date),
then `queue_fix.sh auf`. The pixel file is the arms job's to queue.

**Waiting (session end, 2026-09-28 ~12:57 PDT)** on the four Nova soaks (behind the battery hold,
after the owner's top-up) and on the arms job's pixel verdict. The thermal_state.py clock instrument
(section 4) is still ungranted on the board: #571 folded (30695ba1a9), and the file goes on its own
branch once granted.

## 7. Attempt 3: the clock instrument (PR #588)

**Why attempt 2 did not finish.** It finished in a correct wait. The four Nova soaks and the arms
job's pixel pair (`1-1790625714-arms-forzadecay414-base-3793108`, `-fix-3793166`, queued by the
arms job at 13:01 PDT) are all behind the Nova's battery hold, which lifts after the owner's
top-up at about 18:00 PDT. The session was resumed because hostops granted `thermal_state.py`
at 13:16 PDT, not because any result had arrived. The arms job's AUF skip (20:01Z) is expected.
That file is hand-read, and `queue_fix.sh auf` queues it after the pilot soaks.

**The instrument** is on branch `lane/forzadecay414-clk`, stacked on master at 97c72e2a91, as PR
#588. Each `thermal.jsonl` sample gains `clk`, read in the same `adb shell` call:
- **CPU:** every cpufreq policy's `scaling_cur_freq`, `scaling_max_freq` and `cpuinfo_max_freq`,
  in kHz. Fields that do not read are left out; `scaling_max_freq` is denied on the Thor's policy0.
- **GPU:** kgsl's `gpuclk`, `max_gpuclk` and `throttling`.

`--summary` adds the clause `clock MHz cpu0 lo-hi of <ceiling>, ..., gpu ...`. The selftest leg
`clock` in `99-thermal-pause.sh` runs the real sample script on fake nodes. It fails in any of
three worlds: the policy loop's quoting breaks, an unreadable ceiling is stored as 0 (a mutant
gives `of 0`), or the summary drops the clocks. preflight passes on it.

**The device proof can only come after the fold.** Soaks run the dispatcher's snapshot of the host
tree (dispatcher.sh `snapshot_scripts`), not the request's ref. If #588 folds before the Nova
soaks run, they carry the fields, and one sample gets quoted on #414. If it folds after, any
later soak will show them.

## 8. Attempt 4: the Nova soaks, read (2026-09-28 16:45-17:10 PDT)

**Why attempt 3 did not finish.** It ended in a correct wait on the Nova, which was under its
battery hold. The soaks ran 15:44-16:37 PDT, and handback resumed the lane at 16:42 PDT. The resume
brief said none of the lane's requests was still queued. That was stale by a minute: hostops had
re-queued the two cut arms as `-3394828-r3` and `-3394871-r4` at 16:43 PDT, and put the Nova on a
charge hold (`hold/nova.why`: USB write errors at low charge on the 500 mA port).

**Reader:** `docs/lanes/forzadecay414/judge.py <result dir>...` prints every number below.

### 8.1 The seven runs

All on the Nova, survey route, regimen max. No cooling device above 0 in any sample. xo-therm
35 -> 54 C (A) and 44 -> 55 C (fix), with `cpu-1-9` at 92-95 C.

| result | ref | ran | fps, rows t = 150..330 | invalid max / last | faf calls/flip | scan ms/flip first -> last | of which range completion | walk |
|---|---|---|---|---|---|---|---|---|
| `1-1790624588-forzadecay414-3394734` | f82e7e87fe, before #517 | 360 s | 16 20 20 28 26 26 28 | 199 / 17 | 0.15 | 0.15 -> 0.12 | 0.07 -> 0.00 | 0.08 -> 0.12 |
| `1-1790625108-forzadecay414-3486226` | 10fe2f59a7, **the fix** | 360 s | 20 20 28 28 26 28 26 | **10 / 9** | 0.00 | 6.04 -> 3.84 | 5.98 -> 3.78 | **0.06 -> 0.06** |
| `1-1790624588-forzadecay414-3394828` | 09050ddbe5, #517 | cut at 261 s, VOID | 12 10 6 | 1996 (t = 233) | 0.00 | 1.68 -> 8.96 | 0.00 | 1.68 -> 8.96 |
| `1-1790624588-forzadecay414-3394828-r2` | 09050ddbe5 | cut at 276 s | 12 10 4 | 1954 (t = 227) | 0.00 | 1.97 -> 8.59 | 0.00 | 1.97 -> 8.59 |
| `1-1790624589-forzadecay414-3394871` | 85347ffbd1, master | cut at 245 s, VOID | 12 10 2 | 1969 (t = 253) | 0.00 | 7.78 -> 14.52 | 5.31 -> 5.74 | 2.47 -> 8.78 |
| `-3394871-r2` | 85347ffbd1 | cut at 77 s, VOID | never left the boot | - | - | - | - | - |
| `-3394871-r3` | 85347ffbd1 | cut at 66 s | never left the boot | - | - | - | - | - |

- **Only two runs are whole: the one before #517 and the fix.** Every run of a leaking build was cut
  by the Nova's USB link. Three were cut in the race, at 245-276 s. Two were cut in the boot, at 66
  and 77 s, before any list could grow, so the link and not the build is what cuts them.
- **The fix holds the list at 9-10 for the whole race, and its fps matches the build before #517**:
  26.7 against 26.7 over rows t = 270-330. The three leaking runs read 8.0-9.3 over rows
  t = 150-210, where the fix reads 22.7 and the build before #517 reads 18.7.
- **The route frames show the race in both whole runs.** `155038-play.png` (A) and
  `160858-play.png` (fix) have the race HUD with the race clock at 2:07 and 2:31. The car stands at
  0 mph in both, at different spots on the pit straight, so the two views are not the same scene.

### 8.2 The registered legs, by the letter

Three thresholds in the registered files were wrong. They are reported as written, not re-read.

| file | leg | reads | by the letter |
|---|---|---|---|
| fix-forza | M0 race reached (G >= 40 ms in rows 180-330) | fix: G 47.8 38.2 33.4 41.4 33.3 41.0 | **fails its G clause, so the file reads VOID**. 45 `[watch311]` lines after t = 150. |
| fix-forza | B0 faf <= 0.02 | 0.00 (78 lines) | holds |
| fix-forza | B1 max invalid <= 400 | 10 | holds |
| fix-forza | B2 last invalid <= max(60, 2 x median) | 9 against 60 | holds |
| fix-forza | B3 scan <= 3.0 ms/flip on the last race line, and <= 2 x the first | 3.84, first 6.04 | **fails the 3.0 cap** |
| fix-forza | D1 fps late / early >= 0.8 | 26.67 / 22.67 = 1.18 | holds |
| fix-forza | D2 fix / master fps >= 1.5 | no whole master run | not read |
| bisect | M0 | A: G 50.5 48.3 35.8 33.8 36.6 33.5 | **fails its G clause, VOID** |
| bisect | P0 A's faf >= 0.2, B's <= 0.02 | A 0.15, B 0.00 (cut runs) | **A's clause fails**: A flushes once in 7 flips, not once in 5 |
| bisect | P1 B's last invalid >= 1000 | 1996 and 1954 by t = 233, in cut runs | not read: no whole B run |
| bisect | P2 A's max invalid <= 400 | 199 | holds |
| bisect | P3 B / A fps, rows 270-330, <= 0.6 | B has no such rows. Rows 150-210: 0.50 and 0.46 | not read |
| master | M0, P1, P3 | one cut run: invalid 1969 by t = 253 | not read |

**What was wrong with each threshold.**
- **M0 took a slow frame as the mark of the race.** A race that does not decay runs at G 33-36 ms,
  so the clause voids exactly the arm that is fixed. Section 1's Nova rows showed 28-30 fps late in
  the race before this was registered. The race is marked by the scan's calls per flip instead:
  685-931 in the race, 0-85 in the menus, in all five runs that got there.
- **B3 capped the scan's time, which is not the walk's time.** On master and on the fix, the scan
  triggers one download completion a frame and waits on it: `[sdcall] range=fin60/.../dl60/447.9ms`
  per 60 frames. It arrived between fa56a26f1f and b991fb4c21, which is PR #543's hunk 5: the
  Thor pair `1092424` / `1092523` reads `surfupd=fin180` with no `range=`, then `surfupd=fin120
  range=fin46`. So the Thor's 0.84 ms/flip, which B3's cap was set from, had no completion in it.
  (Commit a55cd900f2's message names #518 for this. That was wrong.) Less the completion, the
  fix's walk is 0.06 ms/flip on the first race line and on the last. Master's cut run read
  2.47 -> 8.78 by t = 213.
- **P0's 0.2 was a guess.** A flushes 0.13-0.15 times a flip and its list is pruned from 199 back
  to 16-86. The leg's failing world was "A does not flush either", and that is not what A shows.

**The download time did not move with the fix.** The range completion alone reads 2.4-7.8 ms a
frame on the fix (median 6.3, 98 lines) and 3.5-5.8 on master's cut run (median 5.4, 16 lines).
All `[sdcall]` sites together read a median of
18.6 ms/frame on the fix (100 lines) and 20.1 on master's cut run (17 lines). `why=` does change: master reads
`new120/inv0`, the fix `new0/inv120`. With the stamp cleared, the two surfaces a frame come back
from the invalid list instead of being created new. That is the recycling the list exists for, and
it is what the pixel arm tests.

### 8.3 The re-cut file and what is queued

`forzadecay414-fix-forza2.json` (sha256 99a1521a6497, registered 2026-09-28T23:50:43Z, committed
a55cd900f2 before either of its runs): A 85347ffbd1, B 10fe2f59a7. M0 by scan calls per flip and
the route frame. A1 master's last invalid >= 1000, A3 master's walk >= 5.0 ms/flip. B1, B2 and D1 as
before. B3 the fix's walk <= 0.5 ms/flip, first and last race line. D2 fix / master fps >= 1.5.
Its thresholds were set from `-3486226`, which it does not judge. The bisect and master files were
not re-cut: their A run has happened.

| request | ref | what | judged by |
|---|---|---|---|
| `1-1790624588-forzadecay414-3394828-r3` | 09050ddbe5 | #517, hostops re-run | bisect (P1, P3) |
| `1-1790624589-forzadecay414-3394871-r4` | 85347ffbd1 | master, hostops re-run | master; A of fix-forza2 |
| `1-1790639501-forzadecay414-151099` | 10fe2f59a7 | the fix, second run | B of fix-forza2 |
| `1-1790639505-forzadecay414-151975` | 85347ffbd1 | AUF, master | A of fix-auf |
| `1-1790639505-forzadecay414-152037` | 10fe2f59a7 | AUF, the fix | B of fix-auf |
| `1-1790625714-arms-forzadecay414-base-3793108`, `-fix-3793166` | 85347ffbd1, 10fe2f59a7 | full sweep, arms job | fix-pixels |

`pilots/forzadecay414.ok` was written from the two whole runs before the AUF pair was queued. The
five soaks are about 40 min of Nova time.

### 8.4 The clock instrument's device proof (PR #588, folded 4e3d69a69b)

These soaks ran after the fold, so every sample carries `clk`. From `-3486226`'s `thermal.jsonl`,
the `hold` sample at 16:05:39 PDT, with `cpu-1-9` at 93.5 C:

```
"clk": {"cpu0": {"scaling_cur_freq": 2016000, "cpuinfo_max_freq": 2016000},
        "cpu3": {"scaling_cur_freq": 2803200, "scaling_max_freq": 2803200, "cpuinfo_max_freq": 2803200},
        "cpu7": {"scaling_cur_freq": 3187200, "scaling_max_freq": 3187200, "cpuinfo_max_freq": 3187200},
        "gpu": {"gpuclk": 615000000, "max_gpuclk": 680000000, "throttling": 0}}
```

run.log: `clock MHz cpu0 1786-2016 of 2016, cpu3 1651-2803 of 2803, cpu7 1843-3187 of 3187, gpu
401-615 of 680`. The low ends are the `cool` sample, taken before the title starts. Every `hold`
sample in the three runs read has cpu7 at 3187 MHz and cpu3 at its ceiling, with the hottest core
at 92-95 C. `scaling_cur_freq` is the governor's request, so this does not rule LMh out (#588's
caveat). It does not need to: the fix holds 26-28 fps with `cpu-1-9` at 93-95 C.

**Waiting (session end, 2026-09-28 ~17:15 PDT)** on the five soaks and the pixel pair in 8.3. The
Nova is on hostops' charge hold until 50% or the owner's top-up, bound 19:00 PDT. On resume: run
`judge.py` on `-r3`, `-r4` and `-151099`, and `docs/lanes/slowdown462/txwwin.py <dir> 255 411` on
the AUF pair. Look at each run's last `play` frame. Write the verdicts here and on #414. Mark #583
ready only if fix-forza2, fix-auf and fix-pixels all hold.

### 8.5 Attempt 5: fix-pixels failed on Stencil only; re-registered as fix-pixels2

Why attempt 4 did not finish: it ended waiting, correctly, on the five Nova soaks and the pixel
pair. The Nova then sat on hostops' charge hold, so `-151099`, `-151975` and `-152037` are still
queued (dispatch `queue/`, 01:34 PDT 09-29).

The arms job judged `forzadecay414-fix-pixels.json` at 22:54 PDT: FAIL, 2 of 3379, both
`Stencil/Stencil_REPLACE_ST` and `Stencil/Stencil_REPLACE_ST_ZB` 0 -> 30000
(`$WORK/arms/pairs/a4436529a25c...verdict.txt`, line 217). Not attributable to the fix:
- the pair split: base `1-1790625714-arms-forzadecay414-base-3793108` ran on the Thor, fix
  `0-0-x-1-1790625714-arms-forzadecay414-fix-3793166` on the Nova;
- Stencil_REPLACE_ST is bimodal 0/30000 on one apk (8d38739bc784) on the Thor
  (`1-1790575472-rendermode474-966088` against `1790575472-rendermode474-966088`);
- tracker #79: Stencil flakes ~8.6% per capture-run on every binary and must not be a
  must_not_move control. My registration put it under must_not_move. That was the mistake.

`forzadecay414-fix-pixels2.json` (sha256 388ea55c4b19, registered 2026-09-29 ~08:35Z): the same
claim, A 85347ffbd1, B 10fe2f59a7, 2 runs per arm, same 100-suite disc. Stencil/* still runs but
is out of must_not_move (99 globs). The old file is left as it is: its sha is bound. #583 stays
draft until fix-forza2, fix-auf and fix-pixels2 all hold.

### 8.6 Attempt 6: the fix's second Forza run and the AUF pair, read (2026-09-29 ~09:20 PDT)

Why attempt 5 did not finish: it ended waiting, correctly, on the three queued Nova soaks and the
pixels2 arm pair. The three soaks ran 08:30-09:07 PDT (Nova, regimen max). No thermal-pause device
rose above 0 in any sample of the three, and the hottest zone reached 94.7-95.1 C.

**fix-forza2** (`judge.py`). B is `1-1790639501-forzadecay414-151099` (10fe2f59a7, whole, 362.7 s):

| leg | reads | by the letter |
|---|---|---|
| M0 race reached | B: 89 scan lines, 772-857 calls/flip; last frame `083725-play.png` shows the race HUD, lap 1/2, race clock 2:21 | B holds; A see below |
| A1, A3, D2 | A's run `-3394871-r4` was withdrawn by hostops at 02:12Z: "a pre-fix Forza soak on the Nova is killed by lmkd at ~215 s (xemu 4.4 GB PSS), shown 3x (#414 comment 5882237205)" | **not read**: no whole master run exists or can exist |
| B1 max invalid <= 400 | 10 | holds |
| B2 last invalid <= max(60, 2 x median) | 9 against 60 | holds |
| B3 walk <= 0.5 ms/flip, first and last race line | 0.04 (t = 151.8), 0.05 (t = 361.9) | holds |
| D1 late / early fps >= 0.8 | 26.67 / 22.67 = 1.18 | holds |

What stands in for A: all four master and #517 runs that reached the race leaked, and each was
cut at 208-276 s with `invalid` at 1915-1996. The bisect re-run `1-1790624588-forzadecay414-3394828-r3`
(09050ddbe5) is the fourth. It reads fps 14 10 2 over rows t = 150-210, invalid 1915 at t = 208, walk
1.99 -> 7.80 ms/flip, and the soak was aborted at 261 s when adb dropped. A master run cannot reach
the D2 window because the leak itself ends the process. The memory cost is part of the defect.

**fix-auf** (`txwwin.py <dir> 255 411`). A is `1-1790639505-forzadecay414-151975` (85347ffbd1), B is
`-152037` (10fe2f59a7):

| leg | A | B | by the letter |
|---|---|---|---|
| M0 txw lines in 255-411 >= 10 | 88 | 123 | holds |
| M1 no thermal-pause in window | 0 samples | 0 samples | holds |
| K1 B faf <= 0.02, bs 1.00 | - | 0.00, 1.00 | holds |
| K2 B bt <= A + 0.5 ms/flip | 0.07 | 0.07 | holds |
| K3 B / A flips/s >= 0.95 | 34.04 | 47.49 | holds, 1.40 |
| K4 B max invalid <= 20 | 11 | 10 | holds |

K3's 1.40 is not a speedup. The two arms' last frames are different views: A faces the vault door
(`084445-play.png`) and B faces the aircraft (`090614-play.png`), and bt calls/flip differ, 78.2
against 42.4. The leg only asks that the fix not cost AUF's frame. No crash, validation or
device-lost line appears in any of the three logcats.

**fix-pixels2:** the arms job queued the pair at 1790670960. Base `1-1790670960-arms-forzadecay414-base-3483119`
is done on the Thor (85347ffbd1). The fix arm `-fix-3483172` is still queued, with no device pin in
its request. #583 stays draft until the arms job judges it.

**Resume 2026-09-29 18:30Z (why the previous session did not finish):** it ended on a wait outside
the session: the pixels2 fix arm. That is still the state. hostops re-pinned `-fix-3483172` to the
Thor at 16:26Z to match its base. It is at the head of the queue, but lane.thorheat has held the
Thor since 17:50Z (`hold/thor.why`: block-3 fan draw). The arm runs when that hold is released.
Nothing else on this PR is open.

**Resume 2026-09-29 20:15Z (attempt 2; why the previous session did not finish):** it ended on the
same outside wait, the Thor hold. That wait is over, but without a clean result. The fix arm
`-fix-3483172` ran on the Thor (apk d5aa7a873b21, DONE 13:13:58 PDT), and both of its runs hit the
1800 s timeout:

| run | captures (base: 3379 / 3379) | what stopped it |
|---|---|---|
| 1 | 2872 | guest idle (`[rr425w] idlepc=8001b02e`, `[pace526] flips=0`) from 12:03:20 PDT to the timeout, inside W_buffering `ZBuf16D_WallQuad_V1_ZB1_ZS1` (`captures1/pgraph_progress_log.txt`, last line `Starting [167/265]`) |
| 2 | 0 | host side: `WSL ... UtilAcceptVsock ... accept4 failed 110`, then `adb shell failed`, then the timeout (`run2.log`) |

- **Run 1 is not slower per test.** Over the 2408 tests both arms completed, the fix's median time
  per test is 0.89 of the base's. Their totals are 871 s and 988 s.
- **The test it stopped in is already anomalous on master.** On the same device, the base arm
  completed `ZBuf16D_WallQuad_V1_ZB1_ZS1` in **-23395 ms** (run 1) and **-23573 ms** (run 2), so the
  guest's clock jumps during that test. Across the last 400 pgraph progress logs on the host, this
  test completed 30 times, came back negative twice (both in this base arm), and stopped once
  (this fix arm).
- One idle guest in a test where master's clock misbehaves does not put the hang on the change.
  That is a reading, not a proof. The re-run decides it.

The arms job had not judged the pair yet at 13:15 PDT. With a leg unscored, it should read
INCOMPLETE, and `arms.sh` (line ~951) re-queues an INCOMPLETE pair once, on its next tick. If it
reads FAIL on the missing captures instead, the next session registers a replicate. #583 stays draft until that verdict.

- **If the re-run also stops in W_buffering on the fix but not on the base,** the hang is the
  change's. The next step is to read the fix's pruning path against that test's surfaces.

**Resume 2026-09-29 22:42Z (attempt 3; why the previous session did not finish):** it ended on an
outside wait, the arms job's verdict. That verdict (20:19Z) printed none: ab_compare refused the
pair because neither fix run proved its progress log, which is a die, not an INCOMPLETE, so
`arms.sh` did not re-queue it. hostops queued the re-run by hand at 20:40Z: base
`1-1790714366-arms-forzadecay414-base-2900948`, fix `-fix-2900992`, both pinned to the Thor. At
22:43Z both are still in `queue/`. The Thor is on `hold/thor` (battery-hostops, 21:20Z: battery
12%, lifted at >= 20%). Nothing on this PR is open except that pair's verdict; #583 stays draft
until it is judged.

**Resume 2026-09-29 23:25Z (attempt 3, second session; why the previous session did not finish):**
it ended on the same outside wait, the Thor's battery hold, and hostops confirmed that on #583 at
23:01Z. That wait did not resolve. The pair was deleted instead. At about 16:23-16:26 PDT,
`dispatch/queue/` lost all 36 queued requests, `-2900948` and `-2900992` among them, and
`dispatch/results/` lost every result directory. What remains is `.withdrawn-1789281384-issue10-arm-a`
and the arms that were queued after 16:26. `dispatcher.log` last names the pair at 16:13:15 (a Thor
battery skip). The last line before the gap is 16:22:59. At 16:26:21 the queue holds only new
`arms-surfwatch382`/`arms-vtxarr262` requests, and the battery admission reads "overhead 300s
fallback n=0" where it read "learned n=10" at 16:13. Its learned history went too. A walk of
`/home/justin` to depth 6 finds no copy of any of this lane's result dirs. The recovery manifest
(`recovery/manifest.md`, 16:15 PDT) still counted "Queued: 36".

What this does to #583:
- **pixels2 is stranded.** `$WORK/arms/pairs/388ea55c4b19….json` still names `-2900948`/`-2900992`,
  and there is no `judged/` or `skipped/` marker. `arms.sh`'s judge loop waits for both `DONE`
  files, and those can no longer appear. Its queue check reads only `queue/` and `running/`, so it
  will not re-queue the pair either. The pair needs host action: re-queue both ids, or delete
  `pairs/388ea55c….json` so the arms job queues it again (arms.sh line 919's recipe).
- **The evidence in sections 8.1-8.6 now cites result dirs that are gone.** The readings are
  recorded above and in the commits that made them, but they cannot be re-read on this host.

#583 stays draft. Its code, fix-forza2 (B holds) and fix-auf (holds) are unchanged; only the pixel
arm is open.

**Resume 2026-09-30 ~00:15Z (attempt 4 of 4; why attempt 3 did not finish):** attempt 3 could not
re-queue the pair itself. The dispatch wipe had deleted both requests, and the stale
`arms/pairs/388ea55c….json` still named them. That file made `already_ran()` count the sha as in
flight, so the arms job never queued it again. What changed this session:
- Both old halves (`-3483119`, `-3483172`) carry `VOIDED`, so the RAN set does not count them.
- No `judged/` or `skipped/` marker exists for the sha.
- I moved the stale pair record to
  `arms/.removed-for-requeue/388ea55c….pairs.json.wiped-2900948.bak`. That is the step the arms
  job's own ARM ERROR text gives.

The arms job queued the pair on its next tick (1790727472): base
`1-1790727472-arms-forzadecay414-base-2035879` (85347ffbd1) and fix `-fix-2035992` (10fe2f59a7).
Both carry expect_sha 388ea55c4b19, 2 runs each, and neither is pinned to a device. When they were
queued, the Thor and the Nova were both on holds, with 28 requests in the queue. #583 stays draft
until the `[job.arms]` verdict.

## 9. Resume 2026-09-30 07:20 PDT (lane.local's offline addendum): pixels3 and forza3 on the merged head

**Why attempt 4 did not finish.** It ended on an outside wait: the arms job's verdict on the re-queued
pixels2 pair. The pair ran, but split: base `1-1790727472-arms-forzadecay414-base-2035879` on the
Thor (85347ffbd1, apk 24205af617ee), fix `-fix-2035992` on the Nova (10fe2f59a7, apk d5aa7a873b21).
The arms job judged it at 02:40 PDT: FAIL, 37 of 3363, **CONFOUNDED (A thor, B nova)**
(`$WORK/arms/pairs/388ea55c4b19….comment.md`). Its same-device re-run was never queued. The job's
own error reads `no device to pin to: thor is gone and CHOOSE named none`
(`arms/log/388ea55c….samedev.err`). The label reads `none`: no verdict counts. Since about 21:00 PDT
09-29 GitHub is unreachable. The arms job has queued no new pair since then (its `prs.tsv` was last
written at 03:15Z), so a new registration is not picked up by it.

The 37: 36 ZPass_pixel_count captures (ZPass +672; the 35 LineWidth/PointSize/PointSizeVS
captures +1010 to +1114, e.g. `ZPassLineWidth-0x0000` 320 -> 1414), and
`Antialiasing_tests/FramebufferNotModifiedBySurfac` 0 -> 1. The better side has five Stencil
captures going to exact (30000/40000 -> 0), which is #79. A near-constant shift across one whole
suite fits a device difference; one device decides it.

**What this session did:**
- Merged origin/master 146b8887db as eec025dd37. The merge was clean. No commit since 85347ffbd1 touches
  `invalidation_frame`, `surface_in_flight` or the drain. The fix's hunk is unchanged. `retired` is
  allocated per slot at init (surface.c:5249), so the drain's early return fires only after the
  finalizer and never skips the reset.
- `judge.py --end N` reads a window other than 360 s. At the default it prints what it printed before,
  except one fix: the `w311` line's `max` and `last` were shifted by one argument. It had printed "max
  360, last (t<=10)" on `-151099`; it now prints "max 10, last (t<=360) 9", the numbers section 8 quotes.
- Registered by `register_fix3.py` at 2026-09-30T14:25:20Z, before any run, A 146b8887db, B eec025dd37:

| file | sha256 | what |
|---|---|---|
| `forzadecay414-fix-pixels3.json` | 82cd41a840fc | pixels2's claim and must_not_move list on the new refs; both arms hard-pinned to the Nova, 2 runs each |
| `forzadecay414-fix-forza3.json` | 3d3587def921 | one Nova Forza soak of B, 420 s, judged by `judge.py --end 420`: W0 whole, M0 race, B1-B3 as forza2, D1 rows 330-390 vs 150-210 >= 0.8, D3 every row 150-390 >= 0.6 x their median |

A of forza3 is not run (the lmkd kill; "Do not repeat" below). D3's 0.6 comes from `-151099`'s
0.77 over rows 150-330. That run is not judged by the file.

**Queued** at 07:33 PDT by `queue_fix.sh forza3` and `queue_fix.sh pixels3`, after the push of
92972ff031. Each was read back: device nova, and the expect_sha matches its file.

| request | ref | what |
|---|---|---|
| `1-1790778383-forzadecay414-3163702` | eec025dd37 | Forza, 420 s, perflog (forza3) |
| `1-1790778383-arms-forzadecay414-base-3163761` | 146b8887db | pixels3 A, 2 runs, hard pin nova |
| `1-1790778383-arms-forzadecay414-fix-3163802` | eec025dd37 | pixels3 B, 2 runs, hard pin nova |

**Waiting (session end, 2026-09-30 ~07:40 PDT)** on those three. The Nova is on `hold/nova`
(`lanelocal-topup`: the owner charges it off the harness), and 20 requests are queued ahead. On resume:
- `python3 docs/testing/ab_compare.py --a <base dir> --b <fix dir> --expect
  docs/testing/predictions/forzadecay414-fix-pixels3.json`
- `judge.py --end 420` on `-3163702`, and look at its last `play` frame.
- If both hold, set PR.md `State: ready`, push, and queue one more 420-s Forza run on that exact head.
  `offline_fold.py` wants a run whose ref is the branch head, and the ready commit touches only
  `docs/lanes/`. Post the verdicts to OUTBOX.md.

## 10. Resume 2026-09-30 19:25 PDT: forza3 holds; pixels3 is a FAIL on paper with one residual; ready

**Why the previous session did not finish.** It ended on an outside wait, as planned: the three Nova
requests in section 9, held behind the Nova's `lanelocal-topup` hold and 20 queued requests. All
three are DONE now.

### forza3: every leg holds

`1-1790778383-forzadecay414-3163702` (eec025dd37, Nova, apk beeb8690b7fc), `judge.py --end 420`:

| leg | rule | read | |
|---|---|---|---|
| W0 | `soak end` t >= 400, no ERROR/VOID/lmkd | soak end t = 433.2; no ERROR/VOID in run.log; 0 lmkd/DEVICE_LOST/VK_ERROR_/Fatal signal lines in logcat.txt | holds |
| M0 | >= 5 race txw lines (calls/flip >= 500) in 180-390; race HUD on the last `play` frame | 95 race scan lines; `route-frames/130524-play.png`: LAP 1/2, RACE 03:25.648, FPS 29 | holds |
| B1 | max invalid= <= 400 | 10 | holds |
| B2 | last invalid= <= max(60, 2 x median 150-240) | 9 (median 9) | holds |
| B3 | walk <= 0.5 ms/flip, first and last race line | 0.06 (t = 152.7), 0.04 (t = 427.9) | holds |
| D1 | mean fps 330-390 >= 0.8 x mean 150-210 | 29.33 / 22.00 = 1.33 | holds |
| D3 | every row 150-390 >= 0.6 x median | min 20, median 28: 0.71 | holds |

fps rows t = 150..390: `20 20 26 28 26 30 28 30 30`. The fps rises over the race; it does not fall.

### pixels3: FAIL on paper, 1 capture attributable, and master reaches that state too

`ab_compare.py --expect forzadecay414-fix-pixels3.json` on base `1-1790778383-arms-forzadecay414-base-3163761`
(146b8887db, apk eae7a2f00588) and fix `-fix-3163802` (eec025dd37, apk 06c870d29199). Both ran on the
Nova (ee317437), 2 runs each, 3379 of 3379 captures. Counts: better 44, worse 1, same 3327, noise 7.
exact 1384 -> 1392. 39 must_not_move captures moved:
- 36 ZPass_pixel_count captures went down, e.g. ZPassLineWidth-0x0000 1240 -> 320. pixels2 moved
  the same captures UP: 320 -> 1414 on a split pair.
- Blend_surface/X_Z1RGB5_Add_SrcA_DstA 15016 -> 12274 (better).
- Vertex_shader_rounding_tests/GeometrySuperscreen_0.9990 570 -> 0 (better, to exact).
- Antialiasing_tests/AAOnThenOffCPUWrite 0 -> 1 (one pixel, max_rgb 123; worse, from exact).

ab_compare's byte check calls six captures attributable, because each arm repeated itself
byte for byte. Four of the six are Stencil (#79, excluded by the registration). The other two are
AAOnThenOffCPUWrite and X_Z1RGB5.

A two-run arm repeating itself does not show that the build sets the value. Each mover's value under
the fix might also be a state master reaches. `pixel_survey.py` reads every scored capture of the
four in `dispatch/results`, one count per run, split by device and by whether the ref carries the
hunk (10fe2f59a7, eec025dd37):

| capture | fix: values | not fix: values | reading |
|---|---|---|---|
| ZPassLineWidth-0x0000 | 320 x3, 1240, 1588, 250 | 250 x27, 320 x26, 1240 x14, 276, 314 | noise: same states, same rates (p = 0.42 for 320) |
| GeometrySuperscreen_0.9990 | 0 x7 | 0 x90, 285 x13, 570 x4 | noise: 0 is master's usual value |
| X_Z1RGB5_Add_SrcA_DstA | 12274 x3, 15016 x4 | 15016 x111, 43756 x18, 12274 x8, ... | master reaches 12274 too, but less often (p = 0.0065); the better state |
| AAOnThenOffCPUWrite | 1 x4, 0 x3 | 0 x71, 1 x2 | master reaches 1 too (`1-1790610287-arms-rendermode474-fix-1969603` Thor, 61e0edf87c; `1-1790725598-arms-memfast-base-1586276` Nova, 31515f9751; same pixel, max_rgb 123), but rarely (p = 0.0003) |

Neither 61e0edf87c nor 31515f9751 carries the hunk (`git grep` of the comment finds it only in
eec025dd37). So the fix creates no new pixel state in any capture. It raises how often two captures
land in one of their existing states: AAOnThenOffCPUWrite's one-pixel miss (from 2/74 to 4/7) and
X_Z1RGB5's closer value. The per-run counts are not independent (two runs share one session), and
four captures were tested, so the p-values overstate the evidence. Even so, three of three fix
sessions on the Nova show the AA pixel at least once, against 1 of about 11 sessions without it.

Both tests turn on when the guest's write lands relative to PGRAPH's. AAOnThenOffCPUWrite is a CPU
write into a surface after an AA change. The hunk changes when an invalid surface becomes prunable,
which moves when surfaces are freed. That is consistent with a timing shift. I did not trace it:
it is outside this lane's scope, and it is one pixel against Forza's race going from 2-6 fps (and
an lmkd kill) to 26-30 fps.

**Decision: ready.** forza3 holds on every leg. The pixel residual is named here and in PR.md, so
whoever folds it reads it. The pixel claim as registered (every non-Stencil capture must not move) is
false as written, because it put four bimodal captures under must_not_move. That is the same
mistake as Stencil in pixels (#79). A follow-up that wants the AA pixel can start from the two
master captures above.

### The ready head

- Merged origin/master 70c9e96876 as 387ff6fb41. The merge was clean, nothing on master since
  146b8887db touches `vk/surface.c`, and the hunk is unchanged.
- `offline_fold.py` requires a finished run whose `ref` is a prefix of the branch head
  (offline_fold.py lines 101-111). The ready commit is a new head, so `queue_fix.sh head` queues
  one 420-s Forza run on it after the push. It is a readout, read with `judge.py --end 420`.

## 11. Resume 2026-09-30 (attempt 3's resume): the ready head's run reads clean

**Why the previous session did not finish.** It did finish its work. It pushed the ready head
78564d090b with `State: ready`, queued the head run for offline_fold.py, and ended waiting on that
run. Nothing else was outstanding. The run is `1-1790821846-forzadecay414-2624677`, DONE and not void.

**Where this readout lives.** It is on `lane/forzadecay414-fix-notes`, stacked on the ready head,
not on `lane/forzadecay414-fix`. offline_fold.py accepts a run only when its `ref` is a prefix of
the branch head (lines 107-108). A docs commit on the fix branch would void 2624677 as the head run,
so the fold would wait for another 420-s Nova run. With the fix branch left at 78564d090b, it can
fold now. This branch changes only `docs/lanes/forzadecay414/`, so after the fix folds it needs no
device run.

### The head run, by forza3's legs

`1-1790821846-forzadecay414-2624677` (ref 78564d090b, Nova ee317437, apk 920ebfc1aa6c, 420 s),
`judge.py --end 420` (a replicate; it was queued with `--no-expect`):

| leg | rule | read | |
|---|---|---|---|
| W0 | `soak end` t >= 400, no ERROR/VOID/lmkd | soak end t = 427.3; DONE, no VOID.txt; 0 ERROR/VOID in run.log; 0 lmkd/DEVICE_LOST/VK_ERROR_/Fatal signal lines in logcat.txt | holds |
| M0 | race txw lines in 180-390; race HUD on the last `play` frame | 104 race scan lines (n in judge.py's scan summary); `route-frames/194104-play.png`: LAP 1/2, RACE 02:49.007, FPS 17, the car stopped on the grass verge in 8th | holds |
| B1 | max invalid= <= 400 | 10 | holds |
| B2 | last invalid= <= max(60, 2 x median 150-240) | 10 (median 9) | holds |
| B3 | walk <= 0.5 ms/flip, first and last race line | 0.06 (t = 150.3), 0.07 (t = 424.6) | holds |
| D1 | mean fps 330-390 >= 0.8 x mean 150-210 | 20.00 / 24.00 = 0.83 | holds, narrowly |
| D3 | every row 150-390 >= 0.6 x median | min 18, median 22: 0.82 | holds |

fps rows t = 150..390: `22 22 28 28 22 22 22 20 18`. forza3 read `20 20 26 28 26 30 28 30 30`.

**The tail (20, 18) is not the list, and not the clock.**
- The list holds at 9-10 for the whole race, and the walk costs 0.06-0.07 ms/flip, the same at
  t = 150 and at t = 425.
- `thermal.jsonl` (the #588 clock fields): no cooling device engaged at any sample. cpu0, cpu3 and
  cpu7 sit at 2016 / 2707 / 3187 MHz and the GPU at 615 MHz from t = 3 s to the end. xo-therm
  rises 44 to 54.5 C; the hottest zone is `cpu-1-9` at 91-96 C. forza3's trace is the same
  (cpu3 2803 there), and it rose to 30 fps.
- The scene differs. The route's input put the car on the verge at 0 mph in 8th: race clock 02:49
  at the end, against 03:25 in forza3. The G column rises 46.7 to 55.5 over the race, which is
  more guest work per row, not a slower host.
- I did not trace the scene's cost. That is outside landing #583, and it is the per-scene fps a
  Playable verdict reads, not the decay. Before the fix, every master race on the Nova reached
  `invalid=` 1915-1996, fell to 2-6 fps and was killed by lmkd at 208-276 s (sections 8.1, 8.6).

**Verdict:** the ready head runs a full 420-s race with the list bounded and no decay mechanism.
`lane/forzadecay414-fix` stays at 78564d090b, `State: ready`, for lane.local to fold.

## 12. Resume 2026-09-30 20:15 PDT (attempt 4): the notes head's run; nothing left but the fold

**Why the previous attempt did not finish.** It did finish, apart from one wait. It pushed this
branch's ready head 089378374c and queued a Forza run on it, `1-1790823584-forzadecay414-2909711`.
offline_fold.py (`offline-git/offline_fold.py` lines 97-111) asks every branch whose diff from master
touches emulator code for a DONE, non-void run whose `ref` prefixes the head. Until the fix folds,
this branch's diff carries surface.c. The session then ended waiting on that run. Neither branch
was folded when this attempt began: origin/master is still 70c9e96876.

**2909711** (ref 089378374c, Nova ee317437, apk 961da6c7b43e, battery 57% at admit). It is DONE with
no `VOID.txt`, so it passes offline_fold.py's check for this branch. It is a short run:
- The Nova's adb link went offline at about t = 308 s. run.log reads `soak aborted: not-foreground
  after 336s of 420s`, `adb_failures=9`. logcat.txt has 0 lmkd/DEVICE_LOST/VK_ERROR_/Fatal signal lines.
- `judge.py --end 420`: `invalid=` max 10, last 10 (median 9). The walk is 0.06 ms/flip at t = 152.8
  and 0.04 at t = 308.2. fps rows t = 150..300 read `20 22 28 28 28 8`.
- The 8 is the 300-330 row cut off at about 308 s, not a fall. The last lines before the drop
  (20:13:49-20:13:59) read `gfps=25 29 30 30 29 29`, `hakuX-pace ... ms=` 1973-2220, and
  `[watch311] ... invalid=9`, then `invalid=10`.
- The thermal summary shows no thermal-pause device above 0, and the clocks flat at their maxima
  (cpu0 2016, cpu3 2707-2803, cpu7 3187, gpu 615 MHz).

It adds nothing to the fix's case, which rests on forza3 and 2624677 (sections 10 and 11). It
neither reads a full window nor shows a decay before the link drop.

**This commit moves this branch's head off 089378374c,** so 2909711 no longer matches it. That is
safe in the order PR.md already gives: fold `lane/forzadecay414-fix` (78564d090b, matched by
2624677) first. After that, this branch's diff from master is `docs/lanes/forzadecay414/` only,
offline_fold.py's code check does not apply, and no run is needed. Folded before the fix, it would
be refused for having no run. That refusal is harmless, but it is the wrong order.

**State:** both branches are `State: ready`. The lane is waiting only on lane.local's
`offline_fold.py`, which is outside this session.

## 13. Resume 2026-09-30 (lane.local 22:40 addendum): the +11 min step is the car moving, not a creep

**Why the previous attempt did not finish.** It did finish. It ended waiting on lane.local's fold,
and both branches have since folded: `lane/forzadecay414-fix` as e816bc35dd and `-fix-notes` as
01268f51de. This section is a new question, so it goes on a new branch, `lane/forzadecay414-step`,
off master b73367209a.

**The question.** The Playable confirmation `1-1790826491-lane.verdict433-3477700` (Nova ee317437,
master b1cea467c6, apk 1462cd8c05bb, `PERF_REGIMEN=default`, survey route, 1200 s after `mark play`)
failed at 45.3% of gameplay >= 30 fps (`verdict.json`). The race holds 29-30 fps for about 11
minutes and then steps to about 20 fps until the end. What changes?

**Answer: the scene. For the first 10.5 min the car is parked at 0 mph facing the grandstand. It
then drives onto the circuit and parks again in a forest section, where each frame costs about
48 ms.** fps follows the view. Within the second view it holds flat for 9 minutes.

### The frames

Route frames, with time after `mark play` (21:35:16.7) and the HUD:

| frame | t (s) | HUD | view |
|---|---|---|---|
| `213839-play.png` | 202 | RACE 03:45, 0 mph, FPS 31 | start straight, grandstand |
| `214525-play.png` | 608 | RACE 10:26, 0 mph, FPS 25 | same spot, same view |
| `214550-play.png` | 633 | RACE 10:51, R gear, 0 mph, FPS 29 | same spot, reversing |
| `214616-play.png` | 659 | RACE 11:16, 12 mph, sector 00:01.035, FPS 29 | crossing the line |
| `214640-play.png` | 683 | RACE 11:40, 41 mph, FPS 21 | on the circuit, hills, another car ahead |
| `214822-play.png` | 785 | RACE 12:50, 0 mph, sector 00:18.509, FPS 21 | forest section, parked, damaged car |
| `215609-play.png` | 1252 | RACE 18:11, 0 mph, sector 00:18.509, FPS 21 | the same view as 214822 |

The survey route's input (`axis LY min`, A x3, `RX max`) stalled the car against the wall at the
start for 10.5 minutes, then got it moving, and then stalled it again in the trees. 214822 and
215609 are the same picture. The sector time is frozen at 00:18.509 in both.

### The logcat, per 2 s, around the step

`gfps` lines (`hakuX-perf`), with t after the mark. Ri is the renderer's idle ms per frame, and Tq
counts texture dirty queries per 60 frames (`profile.c` `nv2a_profile_get_pacing_str`):
- t = 620-634: gfps 29, G 33.3 ms, Ri 10.6-11.8, Tq 1400-1423.
- t = 636, 647, 659, 665-671: single dips (gfps 21-27, Ri 0-1.7, Tq 1995-2693) while the car
  reverses and turns, and the view swings.
- **t = 684:** `gfps=21 G:47.0(32.5-56.0) ... Ri:0.6 Tq:3075`. That is one second after
  `214640-play.png`, at 41 mph on the circuit. From there on, every line reads gfps 18-24 and Ri 0.0-0.5.

### Before and after, per 60-s window

`step_split.py <dir>` (this directory). It makes one row per 60 s after the mark. The full table is
in the OUTBOX post.

| | 360-600 s (grandstand, parked) | 720-1200 s (forest, parked) |
|---|---|---|
| gfps (median per row) | 29 | 19-21 |
| G, guest frame ms (median per row) | 33.3 | 46.6-50.5 |
| flips at 2 vblanks / 3 vblanks, per min | 1684-1741 / 38-64 | 158-278 / 910-982 |
| Ri, renderer idle ms/frame | 11.4-11.8 | 0.0 |
| Tq per 60 frames | 1405-1438 | 2253-2707 |
| guest idle, `[rr425w]` idle_us / (idle+busy) | 25.2-26.4% | 40.0-42.6% |
| `[watch311] invalid=` max | 10 | 10 |
| pipeline misses (`[shd413]` dpm+dsm+dvm) | 0 | 0 |
| `[surf92]` lines per min | 1092-1126 | 1417-1476 |
| `hakuX-pages` slow stores per min | 36556-40933 | 36860-42253 |

So the step is the 60/2 -> 60/3 vsync divisor, as the addendum read it: in the forest view most
flips take 3 vblanks. The renderer has no idle time there (Ri 0), and the guest idles more (41%
against 25%). **The guest is waiting on the renderer.** The renderer is not waiting on the guest.
More textures are queried per frame, which fits a heavier view.

### The three candidates

- **Game state: yes.** The car moved from one view to another. It is a track section, not a
  replay or attract loop: the HUD shows LAP 1/2 with the race clock running in every frame.
- **Memory growth: not seen.** This run logs no PSS: `LOGCAT_SPEC` has no meminfo tag, and
  `thermal.jsonl` samples carry no memory field. But the second view is one fixed picture for
  t = 785-1252 s, and its G holds flat over 720-1200 s (49.8, 50.5, 47.5, 46.8, 48.8, 49.0, 46.6,
  47.8, 49.5 ms), with no trend. A creep that cost frame time would have to show in those 8 minutes
  of identical frames. The step is also not gradual: it lands in one 2-s line, one second after the
  frame that shows the car on the circuit.
- **GPU-cost creep from another growing list or cache: not seen,** for the same reason. The cost
  is flat for 8 minutes of one view, the invalid list holds at 10, and no pipeline misses follow
  the step.

### Heat, clocks, and one thing this run does not decide

`thermal.jsonl`, 46 samples: no cooling device above 0. xo-therm sits flat at 55.5-56.5 C from
t = 280 s. cpu3 and cpu7 are at 2707 / 3187 MHz through the step. The battery reads `Charging` at
every sample (46 -> 34%).

**`gpuclk` reads 401 MHz at all 46 samples**, from 240 s before the mark, idle, to the end.
`max_gpuclk` is 680 MHz and `throttling` is 0. Both MAX-regimen Forza runs read 615 MHz at 14 of 15
samples (`-2624677`, `-3163702`). So the default regimen (perf_mode 0) holds the GPU at 401 MHz
here. Whether the forest view is bound by that clock is not decided by this run. Ri = 0 means the
render thread is never idle, which fits either a GPU wait or CPU-side recording. Deciding it takes
the same view under both regimens. That is a per-scene performance question for whoever owns
Forza's Playable fps, not this step.

### What it means for the verdict

- The step is not a regression and not a second decay. #583's fix holds: `invalid=` is at most 10
  for 1250 s.
- **The 29-30 fps the first 11 minutes show is a parked car looking at a grandstand.** A 600-s
  confirmation on this route measures only that view. The 1200-s window caught the route moving
  the car, and it is the first reading of the circuit itself on the default regimen: about 20 fps.
- **Not queued: the 1300-s `--perflog` run the addendum offered.** The existing run answers the
  step's question. The frames and the per-2-s lines put the step at the car's move, and 8 minutes of
  one view show no creep. A further run would measure the circuit's per-scene cost, which is
  outside this step's scope.

## 14. Resume 2026-10-01 (attempt 2 on the step): nothing left to do

**Why the previous attempt did not finish.** It did finish. Section 13 answered lane.local's
22:40 addendum, `PR.md` said `State: ready`, and `lane/forzadecay414-step` folded to master as
5014d808b0. The resume came from the quiet clock, not from an open item. No Forza result has
landed in `dispatch/results` since `1-1790826491-lane.verdict433-3477700`, so section 13's
reading stands. The one open item, whether the forest view is bound by the 401 MHz GPU clock
under the default regimen, belongs to whoever owns Forza's per-scene fps, not to this lane.
No device run was queued.

## Do not repeat

- Do not commit to a branch after its head run is queued, if offline_fold.py will fold it. The
  run's `ref` must prefix the head, so a docs-only commit voids the run as the fold's check. Put
  later notes on a stacked `-notes` branch.

- Do not register a pixel claim of "every non-Stencil capture must not move". ZPass_pixel_count,
  GeometrySuperscreen_0.9990, Blend_surface/X_Z1RGB5_Add_SrcA_DstA and
  Antialiasing_tests/AAOnThenOffCPUWrite each take two or more values on master, on one device and
  one build. Run `pixel_survey.py` on a mover before calling it the change's.

- Do not re-queue a pre-fix Forza soak on the Nova to read a whole master race. lmkd kills it at
  about 215 s (hostops, #414 comment 5882237205), and adb drops with it.

- Do not put `Stencil/*` in a must_not_move list (#79). It flakes on every binary.

- Do not read a step in a survey-route Forza run as a creep before looking at the `play` frames.
  The route parks the car, and fps follows wherever it is parked: 29-30 at the start grandstand,
  19-21 in the forest section (section 13). A creep has to show as a trend across frames of one view.

- Do not mark the race by G or by fps. A race that runs well reads like a menu. Use the txw scan's
  calls per flip (>= 500) and the route frame.
- Do not cap the txw `scan` time to bound the list walk. Since #543 it holds a download completion
  (`[sdcall] range=`). Subtract it; `judge.py` prints the walk.
- Do not read the Thor's 2-4 fps step with audio starving as the decay. That is the xo-78 C pause
  (#507): it lands with `thermal-pause-F8`, and the vCPU and audio lose their cores.
- Do not look for H1 in core temperatures. The big cores sit at 94-96 C in runs that hold 18-24
  fps. Read `invalid=` on the `[watch311]` line first. If it climbs past a few hundred, the run
  is measuring the list, not the code under test. PR #543's hunk-5 pair (`1092424`/`1092523`)
  measured 9 fps in its window for that reason, against pilot 2's 17 on older code.
- Do not "fix" this by putting the flush back before direct binds. That undoes #517 for every
  title. The defect is the slot-index `invalidation_frame`.
