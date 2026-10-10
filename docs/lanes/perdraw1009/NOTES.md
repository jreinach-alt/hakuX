# perdraw1009 NOTES

## 0. Why attempt 1 didn't finish

Attempt 1 made exactly one commit (681f335fa1, the draft-claim PR.md) and then
stopped. Per `pm/lanelocal-log.md` "2026-10-09 22:50 PDT [lane.local] perdraw1009
restarted on Sonnet": the lane had been started via the board worktree's stale
copy of `lane.sh` (`docs/testing/lane.sh` under `board-wt/.boardtree`), which is
missing usagemode1009's "usage Low" cap (a 17-line diff). Usage was Low at the
time, so the stale script let the lane run on Opus anyway, printed no "usage
Low" line, and lane.local stopped the unit and restarted via the real
`/home/justin/hakuX/docs/testing/lane.sh resume perdraw1009` ("attempt 2 on
claude-sonnet-5"). Nothing about the brief or the worktree was wrong; the
infra that launched attempt 1 was reading the wrong script. This (attempt 2)
picks up the brief from scratch, below.

**Attempt 2 (Sonnet, 22:49:59-23:00:59 PDT) did not finish either, again for an
external reason.** The unit journal shows lane.local stopped it at 23:00:59 and
restarted it at 23:01:02 on `claude-opus-5-5` (the usage meter was recalibrated
at 22:57 and the lane's `.model` file says Opus). That session had committed
93f5542ce3 (sections 1-2 and the shaders.c ubosz gate) and left section 3b
uncommitted; it had queued no device request. Its session log is empty (killed
before the JSON was written). The Opus session that resumes from here (still
counted "attempt 2") re-checks section 1's reading before building on it.

**The rest of attempt 2 (Opus, 23:01-00:3x) built sections 3-8, the four-run
A/B, genread.py and HAKUX_UNI_TOGGLE/togread.py, and the attempt counter was
reset to 1 for usage-window bookkeeping before this resume** (`pm/lanelocal-log.md`
"2026-10-09 23:05 PDT": "attempt counter overwritten 2 -> 1"). That session ended
on `WAITING` for the four queued arms (300-turn cap) and was resumed by
lanewaker once they landed; it then wrote 315feaaa87 (NOTES on the measured
splits), 334904b9e7 (genread.py) and 3b6ab0f363 (HAKUX_UNI_TOGGLE + togread.py,
00:04 PDT) but **never ran armread.py against the four completed results, so
it never found the thing togread.py was built to fix**: the finished commit
message for 3b6ab0f363 already states the cause correctly from the result
files' draws/frame alone (439/438 vs 801), but no armread.py table or frame
was pulled to confirm it, no toggle run was queued, and WAITING/PR.md/OUTBOX
were never updated past the four-arm state. It ended mid-work with no
device request outstanding and no `WAITING` line for lanewaker to act on,
which is why this session starts from a clean idle state rather than a
resumed wait. This session (still "attempt 1" per the restarted counter)
read the four results with armread.py (section 9), confirmed the scene-drift
diagnosis on the actual frames, registered `perdraw1009-nfs-toggle.json` and
queued the toggle run (section 10). That session ended correctly on
`WAITING` for the one queued request (300-turn cap, nothing else outstanding)
rather than an unfinished state; this resume (still counted "attempt 2") found
the run's `DONE` marker already on disk, read it with `togread.py` (section
10's close), and finishes the job from there.

## 1. Where the per-draw time goes (job item 1)

Source: lane.local's 45 s simpleperf profile of the owner's 3-racer start
(`lanelocal-scratch/nfs-race-1009/prof/nfs-race-fp.data`, cpu-clock 1 kHz, frame
pointers, build 1b1fec978d-perflog), re-split with `prof_tree.py` (this dir): every
libxemu.so frame re-symbolized with `llvm-symbolizer --inlining` against the same
build's .so, so a function inlined into its caller gets its own line. Renderer tid
32436, 18,941 samples. ms/frame below are at 13 fps and ~1,630 draws/frame (the
brief's figures for that start), so 1 ms/frame = 0.61 us/draw.

**This section replaces attempt 2's Sonnet reading, which had three errors:**
(a) "no snprintf on the shader-bind path": there is one, every draw:
`pgraph_glsl_vsh_uber_values` -> `uber_printed_float` -> snprintf, 0.46 ms/frame;
(b) ubosz was "~1.2 ms/frame": its upload hook alone is 1.39, with its name table
and strncmp ~1.8 under update_descriptor_sets, and 2.74 in all; (c) the uniform
copy cost was placed in buffer.c's append_to_buffer: it is in shaders.c's
`apply_uniform_updates` -> glsl.h `uniform_copy`, one call per array element.

Under `flush_draw_one_pass` (17.6 ms/frame, 54% of the thread):

| subtree | ms/frame | what it is | whose file |
|---|---|---|---|
| create_pipeline (inclusive) | 7.51 | holds bind_shaders, update_shader_uniforms (early-hit path), bind_textures | draw.c |
| pgraph_vk_update_shader_uniforms | 4.43 | see the next table | shaders.c (mine) |
| pgraph_vk_update_descriptor_sets | 3.42 | ubosz upload hook 1.39, memcmp 0.79, memcpy 0.68, strncmp 0.24 | shaders.c |
| pgraph_vk_bind_textures / create_texture | 2.33 / 2.12 | texture lookup, check_texture_dirty 0.76, fast_hash 0.61 | texture.c (surfgpu1009) |
| sync_vertex_ram_buffer -> tlb_reset_dirty | 1.59 / 1.47 | dirty-page scan of vertex RAM, every draw | draw.c (surfgpu1009) |
| nv2a_clock_ns (perflog timers) | 1.65 | the phase timers themselves | perflog only |
| download_surfaces_in_range_if_dirty | 0.71 | surface readback before a draw | draw.c / surface.c |

Under `pgraph_vk_update_shader_uniforms` (4.43 ms/frame = 2.7 us/draw):

| piece | ms/frame | removable by |
|---|---|---|
| apply_uniform_updates -> uniform_copy, per element, + memcpy | ~2.84 (vsh 2.01, psh 0.56, ubVsh 0.27) | F1 HAKUX_UNI_BULK, ~1.9 of it (the bytes are still copied) |
| pgraph_glsl_vsh_uber_values (snprintf of each program constant) | 0.75-0.78 | F2 HAKUX_UNI_UBERCACHE, ~0.73 |
| update_carried_fog_coord -> vsh_fog_write (token walk) | 0.27 | F3 HAKUX_UNI_FOGCACHE, ~0.24 |

**pfifo_thread's self time (the brief's 6.0 ms) is the perflog's own clock.**
`--self-of pfifo_thread`: 4,231 samples, of which 3,703 (87.5%) are
`nv2a_clock_ns` (debug.h:477-478), the timers `cbl_enter`/`cbl_leave` and the
puller's per-method timing call (pfifo.c 849, 864, 1680, 1767, 1776, 1783, 1787,
1799, 1836, 2202). The pusher and puller themselves are 287 + 72 samples (~0.5 ms
at the brief's rate), method dispatch inside the puller; the FIFO spin
(`pfifo_thread` own lines 2196-2206) is ~80 samples. So pfifo_thread is not a
renderer cost a release build pays; it inflates every perflog run's renderer
time by ~5 ms/frame at 15.6 fps (the rate the brief's 6.0 came from; 6.3 at 13).
pfifo.c is not mine: the lines are in OUTBOX.

**Fin is bigger than Draw on NFS and is not CPU work.** Baseline phase line in the
fixed scene: `Draw:5.5 ... Fin:10.0(Sub:2.5 Fen:1.4) Idle:13.8` with `Fin: Sd1`:
one surface download a frame forces a finish (draw.c 5017-5183 waits on
qemu_event_wait for the download). A cpu-clock profile does not sample a thread
blocked in a wait, so none of the profile's tables above can see it. At the 30 fps
cap it costs nothing (Idle 13.8 ms is left); in the heavy start it is on the frame's
path. surfgpu1009's area: OUTBOX.

## 2. Perflog ubosz counter (job item 2) -- done

`pgraph_vk_ubosz_note_upload`/`_note_bind`/`_log_and_reset` (shaders.c) return at
once unless `HAKUX_UBOSZ_LOG` is set (read once, default off). The draw.c call
sites are untouched (still inside `#if NV2A_PERF_LOG`). In the profile above that
hook is 1.39 ms/frame plus ~0.4 of name-table work: every perflog build's renderer
time drops by about that from this commit on, which is a measurement change, not a
speedup a player sees. bf2ubosize433's `ubosz[...]` line now needs
`HAKUX_UBOSZ_LOG=1` (OUTBOX).

## 3. NFS controls (Addendum 1, settled on device)

Step-0 run 1-1791612289-perdraw1009-1529147 held LT alone 12 s, then RT alone 12 s.
Frames: s20-idle 0 MPH gear 1; lt-02s..lt-12s gear R, up to 54 MPH; rt-02s 40 MPH;
rt-08s 95 MPH gear 3; rt-12s 87 MPH at 65% complete. **pad.sh's `axis RT` is the
gas and `axis LT` reverses**, as the owner said; no swap reaches the game on the
Nova's pad. (pad.sh's LOGICAL table maps RT -> ABS_GAS; SDLControllerManager's
GAS/BRAKE swap is a sort-order swap and does not bite here.) fpstelemetry1008b's
"gear R at 0 MPH" frames were taken with RT pulsed, not held, so the car never got
going; that needs no device run. Logcat after 23:09:48 in run 1529147 is the owner
driving, not the route.

## 4. Route and baseline

`nfs-mw.route`: boot steps from fpstelemetry1008b, `mark gameplay` at ~235 s, then RT
held, one 1 s LX left pulse at +12 s. Baseline 1-1791613176-perdraw1009-1735811
(build 1b1fec978d-perflog, no flag), frames on host clock after the mark: +10 s 108
MPH gear 3 (64%), +21 s 63 MPH scraping the left wall (67%), +31 s on 0 MPH wedged
against the wall under a left chevron (68%), revving, to the end. The logcat mark
(`hakuX-route: mark gameplay`) is 2.5 s later on the device clock than run.log's.

| window (device s after mark) | rows | us/draw (Draw/BE) | row sd | draws/frame | Draw ms | (Pipe+Mfp)/draw | gfps | Idle ms | Fin ms |
|---|---|---|---|---|---|---|---|---|---|
| MOTION (0, 24] | 12 | 13.55 | -- | 350-1025 | 5.0-12.8 | 6.84 | 28.3 | -- | -- |
| STATIC (40, 78] | 19 | 12.26 | 0.16 | 439 | 5.38 | 6.61 | 29.0 | 14.0 | 10.2 |

So the race scene this route reaches runs at the 30 fps cap (D 16.7, 2 VBLANKs a
frame) with ~14 ms/frame of renderer idle: **a per-draw cut cannot raise gfps
here.** The A/B therefore judges Draw us/draw and (Pipe+Mfp)/draw, and states gfps as
unchanged; the scene where a cut would show as fps (the owner's 3-racer start, 13
fps, ~1,650 draws) is not reachable by a route yet. The STATIC window is one fixed
scene with a 0.16 us/draw row sd: the A/B's matched-scene leg. The route's tail was
then cut to 80 s after the mark (~317 s a run) so four arms fit the 30 min pilot gate.

What the baseline cannot see: steering. The one LX pulse got the car round one curve
and into a wall at the next; a longer moving window needs a steering script, which
is a separate route job (the frames show where: the left-hand turn at 67-68%).

## 5. The fix: three default-off switches (job item 3)

Commit 9bdfd6d4f0, shaders.c and renderer.h only:

- **HAKUX_UNI_BULK** (F1): `uniform_copy_draw` sends an array uniform whose reflected
  stride equals its element size (std140 vec4 arrays, the 192-entry vsh constants)
  through one memcpy; anything else goes through the original per-element loop with
  constant-size element copies. Byte identity checked on the host by
  `bulkcheck.sh` (this dir): shaders.c's own functions, extracted from the file,
  against glsl.h's `uniform_copy` over 2,000 random std140 blocks plus the 13 shapes
  the shaders declare: `OK 2013`. Three mutants (copy one element short, vec3 copied
  as 8 bytes, stride `>=` for `==`) each print MISMATCH.
- **HAKUX_UNI_UBERCACHE** (F2): `pgraph_glsl_vsh_uber_values` is a pure function of
  `binding->state.vsh` (glsl/vsh-uber.c 222-317), and nothing writes a binding's
  state after `shader_cache_entry_init` (grep: reads only). Its output is kept per
  ShaderBinding (`vsh_cache.uber`), invalidated in entry_init.
- **HAKUX_UNI_FOGCACHE** (F3): `pgraph_glsl_vsh_fog_write` likewise (glsl/vsh.c 364),
  kept as `vsh_cache.fog_write`.

`[perdraw433] bulk=%d ubercache=%d fogcache=%d` is logged once per process under
hakuX-perf. Host type-check: build-desktop/compile_commands.json's shaders.c
command, redirected at this worktree, `-I wt -I wt/include` first, `-fsyntax-only`:
rc 0.

## 6. Ranking (expected ms/frame removed x probability, at the profiled start)

| # | candidate | ms/frame if it works | P | E | status |
|---|---|---|---|---|---|
| 1 | F1+F2+F3 per-draw uniform work (shaders.c) | ~2.9 | 0.7 | ~2.0 | done, A/B queued |
| 2 | Fin: a GPU finish per frame for one surface download (draw.c/surface.c) | several ms at the start (blocked time, unmeasured by the profile) | 0.5 | high, unsized | surfgpu1009's area, OUTBOX |
| 3 | create_texture/bind_textures lookups (texture.c) | ~1-2 of 4.4 | 0.5 | ~0.7 | surfgpu1009's, OUTBOX |
| 4 | sync_vertex_ram_buffer's dirty-page reset every draw (draw.c) | ~1.0 of 1.6 | 0.5 | ~0.5 | draw.c, after transfer |
| 5 | update_descriptor_sets' memcmp/memcpy (shaders.c) | ~0.5 of 1.5 | 0.4 | ~0.2 | not started |
| -- | pfifo clock reads, ubosz | 5-7 (perflog only) | 1.0 | 0 for a player | measurement; ubosz gated, pfifo in OUTBOX |

P for #1 is the probability the profiled cost transfers to the routed scene and
turns into removable time; the A/B measures it. #2 is ranked by its size: Fin is
the largest renderer phase on NFS (10 ms of a 30 ms frame in the fixed scene), and
an ubershader-style "do it differently" fix there (no per-frame finish: read the
surface back asynchronously) is the approach that fits a tiled GPU; it is not this
lane's file.

## 7. The A/B (job items 4-6)

Prediction `docs/testing/predictions/perdraw1009-nfs-soak.json` (registered
06:34Z, sha256 b1ee6d91fc5d...), judge `armread.py` (this dir), both in dfae6708c1.
One build, 9bdfd6d4f0; B = the three switches =1, A = all three =0, two runs each,
queued B1 A1 B2 A2 (off arm last: the env pref outlives a run):

| arm | request |
|---|---|
| B1 | 1-1791614071-perdraw1009-2017514 |
| A1 | 1-1791614079-perdraw1009-2018606 |
| B2 | 1-1791614081-perdraw1009-2018875 |
| A2 | 1-1791614116-perdraw1009-2019230 |

Point prediction: STATIC Draw -1.5 us/draw (~-12%, ~-0.66 ms/frame at 439 draws),
in [-3.0, -0.7]; (Pipe+Mfp)/draw <= -0.7; MOTION in [-3.0, -0.4]; gfps unchanged at
the cap (|d| <= 0.5) and no MOTION regression (>= -1); pixels: no 80 px region of the
STATIC frames moves past the within-arm floor + 8. armread.py was checked on the
baseline as both arms (all A/B legs read zero, V and X pass) and against a mutant
copy of the baseline with +12 blue over the top third of four frames (X FAIL, 120
regions).

Profile pass: the dispatcher has no simpleperf hook (request.sh and the soak take no
profiling option). If the flag-on arm needs a profile, it is a separate pass with
host-tools/profile_ab.sh, not a hand-recorded one on a timed arm (lane.local, 10-09).

## 9. The four-run A/B, read (job items 4-6, continued)

`armread.py --a 1-...-2018606 1-...-2019230 --b 1-...-2017514 1-...-2018875 --expect
perdraw1009-nfs-soak.json`: V, P0-P3, P6 PASS; P4, P5, X FAIL. Reading the per-pair
table (armread.py prints one row per run) rather than the combined arm means first:

| pair | A run | B run | A draws/frame | B draws/frame | A us/d | B us/d | B-A us/d | B-A pm/d | A gfps | B gfps |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2018606 | 2017514 | 439 | 438 | 11.27 | 8.98 | -2.29 | -1.88 | 29.0 | 29.0 |
| 2 | 2019230 | 2018875 | 855 | 801 | 9.31 | 7.83 | -1.49 | -1.59 | 26.4 | 28.4 |

**The two pairs stopped against two different walls.** Frames at the route's
+10s shot (`drive-010s`, common to all four runs, before any divergence) show
all four at the same 65% wall under the same sunset skyline -- the step that
does not yet distinguish pairs. By the STATIC window (+40..+78s host) pair 1's
frames (`234030`/`234629`-ish) are the plain wall at 65%/68% complete (timer
2:34-2:35) and pair 2's (`235244`/`001734`) are a wall under a burning "Heat It
Up" billboard at 66% (timer 2:45) -- a different stretch of the same curved
wall, reached because the car keeps grinding along it for the ~120s after the
LX pulse rather than stopping dead; which stretch it ends up grinding to is
not controlled by anything this route scripts. **Re-running armread.py on each
pair alone (table above) passes every perf leg**: both pairs independently
read -1.5 to -2.3 us/draw and -1.6 to -1.9 (Pipe+Mfp)/draw, both inside the
registered bands, with gfps unchanged in pair 1 (both at the 29.0 fps cap) and
up in pair 2 (A2 at 26.4, below the cap, so the cut shows as fps there --
a win, not the predicted "no change", because that particular wall position
wasn't fully capped). The combined table's P4 and P5 fail only because they
average across the two different scenes, not because either arm regressed.

**X fails for the same reason, and by more than scene content alone
explains.** Pixel-diffing the +10s frames (verifiably the *same* wall, same
timer to within 0.1s, same 65% complete) across all four runs: A1-vs-B1 (same
arm pairing as the file judges) reads max region d 207, mean 49.5, 144/192
regions over floor+8 -- and **A1-vs-A2 (both off, flags 0/0/0) reads max 208,
mean 50.1, 156/192**, as large as any cross-arm pair. Two runs of the SAME
flag state differ from each other by as much as two runs of different flag
states, at a point in the route both plainly share. The chase camera's
position is a few degrees off between any two live runs of the same held
input (collision/physics jitter), which reframes the whole background against
the fixed 80 px grid -- a camera pan moves every region, a flag changing a
handful of draws' shading would not. **With one run per arm, X's floor is
forced to 0** (armread.py's within-arm floor needs >= 2 runs per arm to
compute; this file has that, but only within a pair, and the combined table
mixes pairs), so a margin of 8 over a floor of 0 fails on run-to-run camera
noise alone, before any flag effect. X as registered is not a valid falsifier
on this route with separate runs -- not because the fix is wrong, but because
the instrument cannot tell a camera pan from a shading change. (Verified with
`armread.py`'s own `regions`/`dmax` on the four `drive-010s.png` files,
pairwise, outside any leg.)

**Verdict on the four-run file: P1-P3 and P6 held in both pairs independently;
P4/P5 are an artifact of averaging two scenes; X cannot be read as registered.**
The per-draw cut itself is not in doubt from this data. What is still open is
the pixel leg job item 6 actually asks for ("the flag-on arm must match
flag-off on the same scenes"), which needs same-scene frames from different
flag states -- exactly what HAKUX_UNI_TOGGLE was built for (section 10).

## 10. The toggle run (job item 6, retried)

Registered `docs/testing/predictions/perdraw1009-nfs-toggle.json` (sha256
482fc384aa29445f981bacd6cd7171c9684b6ff4cd8b8e61c4e8e76b206fe840) against
`a_ref`/`b_ref` 3f6762f180 (this branch's HEAD after merging origin/master,
which carries 3b6ab0f363's HAKUX_UNI_TOGGLE/togread.py; the merge brought in
only nightlynotes1009's fold, nothing touching this lane's files). One run,
`HAKUX_UNI_TOGGLE=10` only (no HAKUX_UNI_BULK/_UBERCACHE/_FOGCACHE env: the
toggle poll overwrites all three from the wall clock on its first tick
regardless of their initial value, so setting them is a no-op once the toggle
is on). Queued: `1-1791618767-perdraw1009-3415447`, `--seconds 380` (the
updated route's comment says it ends ~360s after launch), `--route nfs-mw
--device nova --perflog --ref 3f6762f180`.

This reads both flag states against the SAME wall (one run, so one camera
trajectory), which is what section 9 found the four-run file could not do.
Judge with `togread.py <run> --expect perdraw1009-nfs-toggle.json --sheet
<out>.png`; read the sheet (green/red bar per frame = on/off) before any leg,
the same discipline as armread.py's baseline check.

`docs/lanes/perdraw1009/WAITING` carries this request id. When it lands:
read togread.py's table and legs, update this section with the result, update
PR.md's state, and only then consider job item 7 (BF2/Spider-Man 2
generalisation via genread.py, already written but not yet run against
anything).

**Read (2026-10-10, this session).** `togread.py 1-1791618767-perdraw1009-3415447
--expect perdraw1009-nfs-toggle.json --sheet /tmp/toggle-sheet.png`: all six legs
PASS.

| state | n rows | us/draw | se | (Pipe+Mfp)/draw | draws/frame | gfps | Idle ms |
|---|---|---|---|---|---|---|---|
| off (phase 0) | 17 | 11.22 | 0.06 | 6.34 | 440 | 29.0 | 14.49 |
| on (phase 1) | 19 | 9.52 | 0.09 | 4.68 | 432 | 29.0 | 15.54 |
| on - off | -- | **-1.70** (-15.2%) | -- | **-1.66** | -8 (-1.8%, inside V_be_match) | +0.00 | +1.05 |

- V: marked, finished, no fatal line, no thermal pause in the window, toggle_ms
  10000, >= 6 rows each phase, on/off BE within 10% (one scene) -- PASS.
- T1: -1.70 us/draw in [-3.2, -0.7] -- PASS. Matches the four-run file's two
  matched pairs (-2.29, -1.49) and the profiled model (-1.8).
- T2: (Pipe+Mfp)/draw -1.66 <= -0.70 -- PASS. The switches reach the timed
  per-draw path, not some other counter.
- T3: |on-off| 1.70 us/draw against pooled SE 0.11 (15.5x, >= 3x needed), one
  sign -- PASS.
- T4: gfps on-off +0.00, within the 1.0 tolerance; both phases sit at the 30
  fps cap (29.0 = 29.0) as predicted. Idle up 1.05 ms/frame, consistent with
  less renderer work at a fixed frame budget -- PASS.
- XT: 13 drive frames in STATIC, 3 same-phase / 5 cross-phase pairs within the
  7 s gap; 0 regions crossed same+8, 2 regions crossed cross+8 the other way
  (the control); excess -2, well inside the +8 budget -- PASS. The sheet
  (`/tmp/toggle-sheet.png`, not committed -- it's a scratch artifact, regenerate
  from the run if needed) shows the same wall, same skyline, same speedometer
  reading across every frame with no visible shading change between green
  (on) and red (off) bars.

**Verdict: the fix holds.** Read within one run against one scene -- the
instrument the four-run file lacked -- HAKUX_UNI_BULK/_UBERCACHE/_FOGCACHE cut
STATIC Draw us/draw by 1.70 (-15.2%) and (Pipe+Mfp)/draw by 1.66, with gfps
unchanged at the 30 fps cap and pixels unchanged (XT). This closes job items
4-6.

## 12. The BF2 generalisation arm (job item 7)

NFS won and pixels held, so job item 7 applies: one generalisation arm on a
second draw-heavy title. genread.py (334904b9e7) was already written for
this but never run.

**Grounding the prediction instead of guessing a number.** `docs/lanes/bf2stall433/NOTES.md`
(folded, this tree) sized BF2's own known heavy-view cost: 12-14 us/draw, and
section 1/7 there found it is GPU-side serialization from the per-draw UBO
rebind, not CPU uniform-copy time -- there is no per-draw barrier, event wait
or render-pass split on master, and "the draws are serialized" on the GPU.
`docs/lanes/bf2push656/NOTES.md` section 5 then built the fix that budget
predicts (push constants, halving UBO binds/draw, 0.916 -> 0.453) and its
heavy-view GPU ms did NOT move (38.3 -> 42.3 ms, P1 REFUTED): BF2's heavy
view is GPU-bound, so a CPU/driver-side fix there does not show as GPU ms or
fps. This lane's fix is exactly that kind of fix -- CPU time inside
`pgraph_vk_update_shader_uniforms` (memcpy, cached uber constants, cached fog
string) -- so the generalisation question is whether it moves genread.py's
CPU-side "med us/draw", not whether it moves BF2's fps. Registered
`docs/testing/predictions/perdraw1009-bf2-gen.json` (commit 62e4491ef6,
sha256 32999ceee794cf74e15dd11313a95c7f09f33d95bb4484781e3253ee6d095e09)
against `a_ref`/`b_ref` 9cf824802e (this branch, after the toggle-read
commit): point prediction GAME median us/draw B-A in [-3.0, -0.3] (genread's
own built-in defaults, which already matched this reasoning), (Pipe+Mfp)/draw
B-A <= -0.3, no heavy-row gfps regression (>= -1.0), no requirement either way
on heavy-row gfps improving (GPU-bound). One build (switches are env-gated,
default off), A = no env, B = the three switches =1, route bf2mc, 420 s,
`--perflog --device nova`. Queued:

| arm | request |
|---|---|
| A | 1-1791620320-perdraw1009-3885164 |
| B | 1-1791620323-perdraw1009-3885931 |

`docs/lanes/perdraw1009/WAITING` carries both ids. When they land: `python3
docs/lanes/perdraw1009/genread.py --a 1-...-3885164 --b 1-...-3885931 --expect
docs/testing/predictions/perdraw1009-bf2-gen.json --sheet <out>.png`, read the
sheet and every leg (same discipline as section 10), update this section with
the result, update PR.md, and only then mark the PR ready. A G1 pass with G4
flat is the generalisation result job item 7 asks for; a G1 fail means the
NFS win is specific to NFS's uniform mix (worth knowing, not a reason to
touch anything else) and should be written up as such, not retried with a
different band.

## 13. What the next lane should not repeat

- Do not read pfifo_thread's self time as renderer work: 87.5% of it is perflog
  clock reads.
- Do not judge a per-draw cut by gfps on this route: the reachable race scene sits
  at the cap. Judge us/draw and Idle.
- A cpu-clock profile is blind to Fin's waits; size Fin from the phase line.
- A pulsed RT on NFS MW never gets the car going; hold it.
- **Separate runs of a live-input route are not the same scene even when
  draws/frame nearly match (438 vs 439), and are not reliably far apart when
  they visibly differ (801 vs 855 both read as "pair 2").** Pixel-diff the
  frames before trusting draws/frame as a scene proxy; two off-arm runs can
  differ as much as an on-vs-off pair.
- A table averaged across runs can hide that every individual run passed (or
  every individual run failed); read armread.py's per-run rows, not just its
  combined legs, before concluding from P4/P5/X.
- HAKUX_UNI_TOGGLE exists so a route that cannot be pinned to one scene across
  runs can still be A/B'd: flip within a run instead of queuing more runs.
