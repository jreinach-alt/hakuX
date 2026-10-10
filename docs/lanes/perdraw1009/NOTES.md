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

## 8. What the next lane should not repeat

- Do not read pfifo_thread's self time as renderer work: 87.5% of it is perflog
  clock reads.
- Do not judge a per-draw cut by gfps on this route: the reachable race scene sits
  at the cap. Judge us/draw and Idle.
- A cpu-clock profile is blind to Fin's waits; size Fin from the phase line.
- A pulsed RT on NFS MW never gets the car going; hold it.
