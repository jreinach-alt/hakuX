# accuracy804 NOTES (#804)

RalliSport Challenge (4D53000F): a rival car near the camera is drawn in frame N and absent in N-1 and N+1, while
its shadow is drawn in all three. Owner, 10-04: "that's the flicker I reported". This lane finds where the draw
goes missing.

## 1. What flicker801 left (read, not re-measured)

Sources: wt/flicker801 `docs/lanes/flicker801/{NOTES.md,TABLE.md,runs/}` and its untracked `.flkscratch/` (the
pathfind replay logs and burst mp4s).

- Three bursts of 3 boots catch it, every one at the race start of Safari SS-1, POS 4 OF 4, a rival passing the
  stationary player at race clock ~8 s: s2 b1 p90 194.1, s3 boot A b1 14.6, s3 boot B b1 14.1. Every burst with no
  rival in view reads clear (0.0-1.69).
- s2 b1's hits come in runs (`XXXXXXXXXXXXXXXXXXXXX....XXXXXX...`): the blink is the burst's normal state while the
  rival is in view, not a one-off.
- Pacing is flat across it (pathfind 08:16: gfps 59, G 16.7 ms, 1.0 vblank per flip). Nothing slow coincides.
- Correction (attempt 2, section 9): every positive burst came from pathfind's replay, which takes main menu RIGHT
  -> SINGLE RACE -> Rally -> Safari SS1. Career's Safari SS-1 (the same stage) has no rival in view at all, and the
  positive bursts ran at 35 unique fps (s3 claim-1 b1 `capture.json`) where the empty Career start runs at 59.

What each worst triple shows (frame N-1 | N | N+1 | diff):

| burst | race clock N-1, N, N+1 | N-1 | N | N+1 |
|---|---|---|---|---|
| s3 claim-1 b1 (`worst.jpg`) | 07.99, 08.03, 08.04 | road, the rival's shadow (dark blob, left), no body | the Nissan's rear fills the left half; HUD, trees, tent identical | as N-1: shadow, no body |
| s2 claim b1 | 08.01, 08.04, 08.07 | shadow, no body | body drawn, a little further left | shadow, no body |

The clock advances in every frame, so these are three consecutive game frames (30 fps), not a repeated or dropped
presentation. Everything else in the frame (sky, trees, crowd, HUD, the rival's shadow) is drawn in all three; only
the body's draws come and go. That rules out a whole-frame skip (`frame_skip_active` drops every draw of a frame,
vk/draw.c:7180, and is off by default) and a presentation problem.

## 2. What the frame dump can and cannot see

`fdump_log_draw` (vk/renderer.c) is called from `nv2a_diag_log_draw_call`, which every draw kind reaches only after
`vkCmdDraw*` was recorded (vk/draw.c:8567, 8644, 8716, 8796). The async-compile skip (`r->async_draw_skip`,
vk/draw.c:4897-4923) jumps past it. So a dump record means "recorded into the command buffer", not "issued by the
guest": a draw we drop at the skip is absent from the dump, the same as a draw the guest never sent. The records
carry the shader-state hash, colour target and every texture stage's offset, so a car body is identifiable by its
livery texture.

The dump records nothing about occlusion queries: not `SET_ZPASS_PIXEL_COUNT_ENABLE`, not `GET_REPORT`, not the
value written back. The perflog build's `hakuX-rpbrk` line does: `qry` is the render-pass breaks that query
begin/end caused over the last 60 flips (`opt_stats_log_and_reset`, vk/draw.c:1044), and the dispatcher keeps that
tag.

## 3. The defect found in code: occlusion results are read before the GPU has run the queries

`pgraph_vk_finish` ends with `pgraph_vk_process_pending_reports_internal(d)` (vk/draw.c:4485), which reads the
occlusion query pool with `VK_QUERY_RESULT_WAIT_BIT` (vk/reports.c:131-136) and writes each guest `GET_REPORT`.

- For a deferred finish (FLIP_STALL, PRESENTING, STALLED, SURFACE_DOWN_FLUSH; vk/draw.c:4169-4172) the PFIFO
  thread waits only until the render thread has called `vkQueueSubmit` (`wait_frame_submitted`, :4283), not for
  the fence. The reports are then read at once.
- Each query was reset by `vkCmdResetQueryPool` inside the same command buffer (`begin_query`, vk/draw.c:3447), and
  indices restart at 0 in every command buffer (`num_queries_in_flight = 0`, reports.c:172).
- `vkCmdResetQueryPool` is a GPU command. In Turnip the availability flag is GPU-written memory: the reset is a
  `CP_MEM_WRITE` (`emit_reset_query_pool`, mesa-turnipfork `src/freedreno/vulkan/tu_query_pool.cc:1033`), and
  `get_query_pool_results` waits only while `available` reads 0 (:694-702). Before the GPU reaches the reset,
  the slot still reads available with the count from the last command buffer that used that index.
- So on the Nova and the Thor, a deferred finish returns, for query i, the count from the PREVIOUS command
  buffer's query i, without waiting.
- Upstream xemu waits on the fence before reading (the `#else` branch, still in `8acb63d855^`). hakuX's deferred
  fences (`a679ef565d`/`3ff8906772`, 2026-02-25/26) and the render-thread deferred finish (`8acb63d855`) dropped
  that wait for flip finishes; STALLED joined the deferred set later.

How that makes a car blink on alternate frames: say the game draws a car's body only if the car's visibility test
in the previous frame passed, and the test covers the body draw. Let D(k) mean "body drawn in frame k" and V(k)
mean "frame k's test counted pixels", so V(k) = D(k) when the car is on screen. Correctly, D(k+1) = V(k): stable.
With the stale read, the report written at the end of frame k holds frame k-1's count, so D(k+1) = V(k-1) =
D(k-1). That is a period-2 recurrence: any single frame where the body and its test disagree (the car entering
view, a LOD switch) splits the even and odd frames, and they stay split. The shadow is not gated by the test, so
it is drawn every frame. Pacing is untouched, because the draw count only changes by one car per frame.

This explanation needs one thing the code cannot show: that RalliSport gates the car body on a visibility test.
The XBE cannot answer it: all 32 Xbox titles in `/mnt/d/hakux-staging/sweep` carry `GET_REPORT` and
`SET_ZPASS_PIXEL_COUNT_ENABLE` push headers, because the D3D library is linked whole (RalliSport 2 and 4, the
others 2-11 and 4-7). The capture's `qry` count answers it.

Corroboration, not proof: #527 (cloud-527, PR #535) found the ZPass suite's first report differs by run (40,960 /
49,152 / 65,536) though the test draws the same thing. A first report read from a reused, not-yet-reset slot would
do exactly that; cloud-527's explanation for the other 35 reports (written after the report DMA was rebound) is a
separate defect in `pgraph_vk_process_pending_reports`, and its fix does not touch this path.

## 4. Candidates, P x win

| cause | P (evidence) | win | how the capture separates it |
|---|---|---|---|
| H1: stale occlusion result (section 3) | ~0.5: a concrete defect on exactly this path, matches body-gone/shadow-kept and flat pacing; unknown whether RalliSport uses visibility tests | every title that gates draws on visibility tests (lens flares, cars, LOD), on both handhelds | body keys alternate in the dump AND `qry` > 0 in the race |
| H2: we drop the recorded body draw (async skip, a null pipeline in `begin_draw` :5201) | ~0.1: a compile skip lasts until the shader is ready, not for seconds of strict alternation on a kept cache, three boots in a row | this title | body keys alternate but `qry` = 0, and `draws_skipped_pending` would need to toggle per frame; a skipped draw is absent from the dump, so the dump alone cannot separate it from H3 |
| H3: the game relies on a surface or buffer persisting from the previous frame | ~0.2: the brief's alternative; nothing in the frames shows a persistence effect (the body is simply absent, not stale) | surface-cache fix, broad | body keys alternate, `qry` = 0 |
| H4: the body is recorded every frame but rasterises to nothing on alternate frames (depth/clip/state) | ~0.2 | draw-path fix | body keys present in every frame |

H1 first: it is the only candidate with a known defect behind it, and its fix is small, so its test is the
capture already queued.

## 5. The capture (one Nova run)

`1791136124-lane.accuracy804-3752333`: ref `5e4196fefd` (master), `--perflog` (cached APK, and the build adds
`hakuX-rpbrk`), route `rallisport-804` (copied untracked into `docs/testing/titles/routes/` to queue; the
committed copy is `docs/lanes/accuracy804/rallisport-804.route`), 190 s,
`--env XEMU_FRAME_DUMP=600,after138,noimages,cap1500`, `--pull 'framedump_*'`.

The route does not replay pathfind's path step by step. pathfind's replay presses on what it sees (sigs and model
calls), and the title reached the menu at 23, 32 or 35 s in its three replays depending on how the logo presses
landed; one extra A at the title would shift every later press by one screen and send the main menu's RIGHT into
the wrong screen. A dispatched soak cannot use `waitfor` either: `dispatcher.sh:1351` writes only the route's text
into the result dir, so a reference crop does not travel with it. So the route:

- presses nothing until +65 s, then START. The survey soak `1-1791124360-lanelocal-3022739` (Nova, 07:33) did
  exactly that and had the intro running at +65 s and the title at +71 s;
- then presses only A, 6 s apart: title, profile select (pathfind's replay on this golden, `cc9b4ced4a0f`, reached
  the main menu with one A), main menu (Career is lit), SELECT EVENT, SELECT CAR. Every menu input is A, so a lost
  press delays the race instead of sending a wrong input;
- waits 25 s on the options screen ("start race" lit; it waits for input), presses A at ~+127 s, and A again at
  ~+136 s in case one press was lost (A in a running race does nothing visible: survey frames 07:35:47-07:37:26).

Choosing N: race clock 0 comes 7-12 s after the start-race A (pathfind's replay 7 s, the survey's career start
12 s), and the rival passes at race clock ~8 s, so the alternating stretch should be at +142..+149 s of the soak.
An env-armed dump starts its clock about 1 s after soak start (`framedump: armed by env` 0.7 s after `SDL_main:
start`, run 1789950294-drvab77-stock-2). `after138` starts the dump at ~+139 s; 600 frames at the race's 30 fps is
~20 s, to ~+159 s. Shots r1-r5 at ~+141..+155 s show whether the rival is on screen.

## 6. What the capture decides

| dump (`alt_draws.py --min-run 10`) | `qry` in the race (`hakuX-rpbrk`) | reading | fix lives in |
|---|---|---|---|
| body keys alternate | > 0 | the guest decides per frame and runs visibility tests: H1 | `vk/reports.c`, `pgraph_vk_process_pending_reports_internal` (patch below) |
| body keys alternate | 0 | guest-side gate that is not a visibility test (H3), or our skip (H2) | second capture needed: `draws_skipped_pending` per frame, or images |
| body keys present every frame | any | recorded every frame, lost after recording: H4, a draw-path fix | second capture with images (`images` spec) on the alternating frames |
| no rival in the window (shots) | - | timing missed | one more run with N moved by the measured offset |

## 7. The fix (not applied: needs `hw/xbox/nv2a/pgraph/vk/reports.c`, requested from the board)

`docs/lanes/accuracy804/reports-804.diff`: in `pgraph_vk_process_pending_reports_internal()`, when queries are in
flight, wait the fence of every submitted frame before `vkGetQueryPoolResults`. Only a finish that recorded a
query pays the wait; that is the wait upstream xemu always takes. It stays out of `vk/draw.c` (lane.async794's,
whose work is on the same finish path), and it does not overlap PR #535's hunk in the non-internal function.
`git apply --check` passes on master; the patched file passes `-fsyntax-only` with the Android build's own compile
command (arm64 Release, `dispatch/build-tree`).

Cost: a title that runs visibility tests waits for the GPU at each finish that recorded one, as upstream does. A
cheaper form exists only if a report may be late, and a late report is this bug.

## 8. Do not repeat

- Do not scan an XBE for `GET_REPORT`/`ZPASS` method headers to ask whether a title uses visibility tests: every
  title has them (32 of 32).
- Do not read a missing draw in a frame dump as "the guest did not issue it": the dump records after the
  async-compile skip.
- Do not use `waitfor` in a route meant for a dispatched soak: the reference crops do not travel.
- Do not reach RalliSport's race through CAREER: no rival is ever in view there. Take pathfind's SINGLE RACE path.
- Do not write `press RIGHT` for a menu that pathfind navigated: pathfind sends the hat (`HATX max` then `mid`),
  route.sh's `press RIGHT` sends the BTN_DPAD_RIGHT key, and a title may ignore the key (goldeneye-ra).
- Do not key a frame-dump draw on its colour target: RalliSport triple-buffers (0x3bd8000, 0x3d04000, 0x3e30000),
  so every draw's full key changes every frame and nothing reads as present in >= 95% of frames.

## 9. Attempt 2 (10-04 PDT): the first capture, read

Why attempt 1 stopped: it ended as designed, WAITING on the capture `1791136124-lane.accuracy804-3752333` behind
lane.pathfind's hold. The capture ran 13:46:24-13:49:38 PDT on the Nova, clean (adb_failures 0, xo 39 C at start,
no thermal pause), and handback resumed the lane on it.

What it shows (dump `framedump_1791146922.jsonl`: 600 frames, 417,408 draws, 13:48:42.7-13:48:52.8 PDT):

| question | reading |
|---|---|
| where the dump sits | race clock 0 at 13:48:38.6 (r1 read 00:07.37 at 13:48:45.97), so frames 0-599 are race clock ~4.1-14.2 s. The first start-race A started it, 7.0 s before race clock 0. The dump began 138.56 s after `armed by env`. |
| was a rival in view | **no**. Shots at race clock 7.37, 11.31, 15.21, 19.05, 23.96, 46.30 show an empty road at POS 4 OF 4, and the dump agrees: 129 of its 133 draw keys (kind, primitive, count, shader, textures) have the SAME count in all 600 frames, so nothing entered or left the view. The route took CAREER (section 1's correction). |
| visibility tests | **yes, every race frame.** `qry` (render-pass breaks from query begin/end, per 60 flips) is 0 in every menu and 400-594 from the race start on. The dump has the geometry: an untextured `inline_array` of 24-vertex quads (a 6-faced box), shader `8f6c865e558bb778`, 5 per frame at draw n 136-140, in 390 of 600 frames, irregularly (`5055505055505050550550...`). 5 boxes x 2 breaks x 0.65 = 6.5 per flip, the `qry` rate (~7). |
| what else varies | two untextured quad keys at the frame's end (n 675-685) strictly alternate 1/2 and 2/4 per frame (draws 690/698): overlay draws into the swap-chain buffer, the same in every frame pair. A textured quad (tex `0x03901800`, 3 per frame) comes and goes in even-length blocks. |
| render-to-texture | none in the window: every draw targets one of the three 640x480 swap-chain buffers, and no sampled texture offset equals a colour target. |

So the brief's question, does the guest issue the car-body draws every frame or on alternate frames, is
**unanswered by this capture**: there was no rival to draw. What it did settle is H1's open precondition in
part: RalliSport runs 5 visibility tests per tested frame all through the race. What they gate is still open.

**Second capture, and why the first could not give it:** the first had no rival on screen. The second replays
pathfind's own menu path (`rallisport-804b.route`: main menu hat-RIGHT -> SINGLE RACE -> Rally -> SAFARI SS1 ->
default car -> start race), the mode all three positive bursts came from. Same ref (`5e4196fefd`, cached perflog
APK), so the two dumps compare draw for draw.

Choosing N: the route adds 2.35 s of hat input and one more 6 s menu step (race type before track), so the
start-race A falls at ~+134 s and race clock 0 at ~+141 s. In flicker801 the rival is in view from race clock
~7.5 s for most of an 8 s burst (s3 claim-1 b1: 130 hits in 282 triples). `XEMU_FRAME_DUMP=1000,after141`
starts at ~+141.5 s. 1000 frames last 16.7 s at 60 flips/s and longer if the rival drops the game toward 35
fps, so race clock 8 s is in the window for any race clock 0 from ~+134 to ~+150 s. Shots r1-r7 at race clock
~4-17 s show whether the rival is on screen.

Queued 10-04 PDT as `1791147878-lane.accuracy804-1639330` (perflog, `--pull 'framedump_*'`, pinned to the Nova),
behind lane.pathfind's hold and 6 earlier requests. The lane is WAITING on it (`WAITING`). Reading it: section 6's
table, with `alt_draws.py` (its full key no longer includes the colour target) and the shots r1-r7.

## 10. Attempt 3 (10-04 PDT): the second capture, read; a third queued

Why attempt 2 stopped: it ended as designed, WAITING on capture 2 (`1791147878-lane.accuracy804-1639330`). That
ran 14:32:11-14:35:31 PDT on the Nova, clean (xo 40.6 C at start), and handback resumed the lane on it.

What capture 2 shows: **it never reached a race.** The route reached the GAME MENU on time (shot `mainmenu`,
+88.4 s, Career lit, Career the leftmost item). The hat RIGHT was held 0.35 s (`axis HATX max`, `wait 0.35`,
`axis HATX mid`) and the menu auto-repeated past Single Race to OPTIONS; the A presses then went OPTIONS ->
Controller Settings -> the controller diagram -> back to Controller Settings, where every race shot (r1-r7) and
the dump's 600 frames sit. pathfind sends max and mid back to back and sleeps 0.35 s after the release
(`pathfind.py send()`), so its hold is one adb call, ~0.14 s.

Two more things capture 2 measured, which the third capture uses:

- The dump is capped at 600 frames (`FDUMP_MAX_FRAMES`, vk/renderer.c:1794): `1000,after141` dumped 600. At the
  race's 60 flips/s (capture 1) that is a 10 s window.
- The route ran slower than section 9 planned: start-race A at +140.3 s (planned ~+134), spare A at +148.6. The
  dump began at 14:34:34.4, +142.7 s after `SDL_main: start` (N + 1.7 s). With the right menu, race clock 0 would
  have been ~+147.3 and the dump would have closed at race clock ~5, before the rival (~7.5). So capture 2 would
  have missed even on the right path.

**Third capture, and why the first two could not give it:** neither had a rival on screen (capture 1: Career has
none; capture 2: never left the menus). `rallisport-804c.route` is 804b with the hat released at once (`axis HATX
max`, `axis HATX mid`, `wait 2.35`, so every later press keeps 804b's measured time). Same ref (`5e4196fefd`,
cached perflog APK) as both earlier captures.

Choosing N: the dump starts at route + N + ~1.8 s. With race clock 0 at ~+147.3 (start-race A +140.3, plus the
7.0 s capture 1 and pathfind's replay both measured), `after149` starts at ~+150.8 = race clock ~3.5 and ends
~10 s later at race clock ~13.5. Race clock 8 is inside the window for any race clock 0 from +142.8 to +152.8,
i.e. the start-race A may land 2.5 s early or 5.5 s late. Shots r1-r7 at ~+152..+169 (race clock ~5-22) show
whether the rival is on screen.

Queued 14:41 PDT as `1791150087-lane.accuracy804-2199171` (perflog, `--pull 'framedump_*'`, pinned to the Nova);
it was claimed at once (queue empty but for fmv303c).

## 11. The third capture, read: the guest issues the rival's body every frame

`1791150087-lane.accuracy804-2199171` ran 14:41:54-14:45:30 PDT on the Nova (xo 31.9 C at start, clean). The route
went MAIN MENU -> SINGLE RACE -> Rally -> SAFARI SS1 -> Ford Escort -> start race (every shot as planned). The
start-race A came at +140.6 s and race clock 0 at ~14:44:22.0 (r2 read 08.28 at 14:44:30.27). The dump
(`framedump_1791150264.jsonl`: 600 frames, 489,406 draws, 510 MB) covers 14:44:24.7-14:44:41.2 = **race clock
~2.7-19.2**, at 30-36 flips/s (gfps 28-31; the race runs at 30 game fps, as flicker801's 35 unique fps
implied). r1 (05.42) shows a rival ahead on the left, **r2 (08.28) shows the Nissan beside the camera, body
drawn**, r3 (11.11) and later show the empty road. Dump frames are consecutive guest flips (`nv2a_frame` steps by
1 in every record).

| question | reading |
|---|---|
| does any draw key alternate | **no.** `alt_draws.py --min-run 10`: 0 of 496 full keys and 0 of 255 tex keys. Over the rival pass (frames 130-300, race clock ~7-12) the longest strict period-2 stretch of any key is 9 frames, on the untextured 24-vertex box (`19054f81558bb778`, the visibility-test geometry); no car key exceeds 4. |
| the near rival's body | shader `9d4f17a01cee3e05`, livery `0x02ded000`, 2673 indices (the highest of that car's LODs: 339, 1341, 1896, 2673 come and go in multi-frame blocks as it nears). It is recorded **in every frame from race clock ~8 to ~10** (frames ~168-235) except the dropouts below, together with that car's other parts (`ece9f59044a636fd`/`0x02dea000`, `9d4f17a01cee3e05`/`0x02e03000`). |
| dropouts | 1-6 frame runs where **every** car's draws are absent together (frames 175-176, 182-183, 205, 209, 217, 240-244, 252-253, ...), with ~60-80 fewer draws in that frame. Not period 2, and not ours: the perflog shows `ASkip:0 FSkip:0 NoP:0 NullP:0` (no async-compile skip, no null pipeline) in every 2 s window. The guest leaves the cars out of those frames. |
| per-draw state | every car draw targets that frame's own colour buffer (0 off-target in 600 frames), is inside a render pass, in the frame's single command buffer, at draw n ~84-205, before the visibility boxes (n 215+). Each car key's pipeline (the fixed-function state) changes only in multi-frame blocks, never per frame. |
| visibility tests | still every race frame: `qry` 1747-1788 render-pass breaks per 60 flips (~30 per flip) in the race. |

What the dump decides, in the brief's table: **the guest issues the car-body draws every frame, and we record
them every frame**. The game does not leave the body out on alternate frames, so the body is lost after
recording. That **refutes H1** (section 3, the stale occlusion read) as the cause of this flicker: H1 needs the
guest to decide per frame whether to issue the body, and it does not. The reports defect in section 3 is still a
defect in code (a read that does not wait), but this capture removes it as the explanation for #804. H2 (our
skip) is ruled out by `ASkip:0 NullP:0`, and H3 (the game relying on a buffer kept from the previous frame) has
nothing to support it: no render-to-texture, every draw to the swap-chain buffer. **H4 stands**: recorded every
frame, invisible on alternate frames.

What the dump cannot see, and which H4 turns on: the vertex attribute data and its upload, the vertex-shader
constants (the body's transform), the depth surface and its contents, and dynamic state (viewport, scissor, depth
bias). Every recorded field of the body draw is the same frame to frame: shader, pipeline, textures, colour target,
render pass. So the difference between a drawn and an undrawn frame is in one of those unrecorded inputs.

**The one thing this capture cannot say**: whether this run flickered. The dump had no images, and only one route
shot (r2) fell in the rival pass; it shows the body. flicker801 caught the blink at exactly this race clock on
this path in 3 of 3 boots, on the Nova, but never with a dump running. If the dump suppressed it, the reading
above would be about a run without the defect.
