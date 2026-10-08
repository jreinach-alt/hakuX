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

## 12. The fourth capture: does the blink happen while the dump runs?

Section 11's one open point is whether capture 3's run flickered at all. The reason for one more run, which the
third capture could not give: it had no images. `rallisport-804d.route` is 804c with the seven race shots
replaced by sixteen back-to-back screencaps from race clock ~5.6 (0.7-2.4 s each on 804c's log, so they cover
race clock ~6-20). The emulator is untouched: same ref, same `noimages` dump, same N. If the body is absent on
alternate frames while its draws are recorded, several shots show the rival's shadow without its body, and
section 11's reading (lost after recording, H4) holds for a flickering run. If every shot in the pass shows the
body, the dump run did not flicker, and the next step is a capture without the dump.

`1791150751-lane.accuracy804-2407540` (14:58-15:02 PDT) **voided**: the app never reached `SDL_main`. The logcat
has 3 lines, both `hakuX-route` soak markers and no hakuX line at all, against 9,728 for capture 3. Focus was lost
at +30 s ("no focused window on display 0", twice), the route stopped, and the display read OFF at the end. The
one recorded difference from capture 3 is `shader_cache: cleared: apk 9c2b2969be27 -> 63f4c763dc9a`: another
lane's run had installed its APK on the Nova between my two runs. The pulled `framedump_1791150736.jsonl`
(14:52) is that other run's file: my dump never opened, so `fdump_clear_previous` never ran. Re-queued once as
`1791151399-lane.accuracy804-2607611`. It follows lane.hitchcause's run at ref `b559c094eb`, so it starts after
another APK switch: the same condition, which makes it a test of that cause as well.

The rerun `1791151399-lane.accuracy804-2607611` (15:05-15:09) **voided the same way** (3 logcat lines, no dump,
`guest never appeared in 200s`), again right after a lane.hitchcause run on a newer build (`c53ade8dd620`, ref
`b559c094eb`). Re-queuing at `5e4196fefd` again would void again, for this reason:

**Cause of both voids (likely, with one falsifier): the libfolders pref migration.** `GamesFolders.read()` and
`write()` (android/.../GamesFolders.kt:24, :29), folded at `10f14d301d`, move the games folder from
`gamesFolderUri` to the JSON list `gamesFolderUris` and **remove the legacy key**. A build older than that fold
(my `5e4196fefd` APK) reads only `gamesFolderUri` in `LauncherActivity`. Once a newer build has started on the
device, the old build finds no games folder, its `hasGamesFolder`/`hasDvd` checks fail, and the launcher goes to
setup instead of the emulator: no `SDL_main`, no focused window, a void. The Nova's run list fits it exactly. Every
run boots except my two, and those are the only runs where a pre-libfolders build followed a post-libfolders one
(hitchcause `805cb8054f` -> mine, hitchcause `b559c094eb` -> mine). Capture 3 at the same APK and env followed my
own APK and booted; captures 1-2 followed older builds and booted. I cannot read the device (a lane never touches
one), so the launcher's screen and the crash buffer are unread. The falsifier is the next run: the same route and
dump on master `10f14d301d`, which carries the migration, must boot.

It affects every request pinned to a ref older than `10f14d301d`, on any device where a newer build has run (A/B
base arms included). The guard is not in this lane's territory: keep writing `gamesFolderUri` (the first folder)
alongside `gamesFolderUris` instead of removing it, or have the dispatcher restore the pref per APK. Reported in
OUTBOX for the PM.

Capture 4 therefore runs on master: `1791151872-lane.accuracy804-2787512` (ref `10f14d301d`, perflog, same env and
route). It is self-contained: its own dump says whether the body is recorded every frame on master, and its own
screencaps say whether that run blinked.

## 13. Capture 4 (master): the dump run does not blink

`1791151872-lane.accuracy804-2787512`, ref `10f14d301d` (master, APK `1ebf4fde7ede`, perflog), 15:25-15:29 PDT. **It
booted** (9,692 logcat lines, dump opened), the falsifier section 12 named for the libfolders cause. `hw/` is
identical between `5e4196fefd` and `10f14d301d` (empty `git diff --stat -- hw/`), so this is capture 3's draw path.

Route shots, back to back, ~0.7 s apart (~21 game frames, so consecutive shots fall on alternating frame
parities): race clock 5.71, 6.50, 7.21, 7.96, 8.57, 9.26 and 10.00 show the Nissan (approaching, airborne beside
the camera at 7.21, alongside at 7.96, ahead after that, small by 10.00); 10.78-16.92 show the empty road. **The
body is drawn in 7 of 7 shots of the pass.** If it were missing on alternate frames, as in flicker801's frames,
seven drawn shots in a row would come up about once in 128. The dump (`framedump_1791152888.jsonl`, 600 frames,
490,351 draws) again has no key alternating for more than 7 frames (the visibility box).

So the run with the dump does not blink, and section 11's reading ("recorded every frame, lost after recording")
was made on a run that probably did not show the defect. It does not stand as the answer. Which builds blinked:
flicker801's bursts (08:53-09:23 PDT) ran on the Nova's installed debug app, APK `74a9f3ab781a`, ref `4a3308a21e`,
**not** perflog. `4a3308a21e` is an ancestor of `5e4196fefd` with no `hw/xbox/nv2a` change between them. Same nv2a
code, then. What differs from the blinking runs: (a) the frame dump was running (one `fprintf` record per draw,
~850 KB per frame on the thread that records draws); (b) the perflog flavour; (c) the route (pathfind's replay vs
fixed waits; both reach the same race start with the player standing).

Capture 5 changes only (a): `1791153088-lane.accuracy804-3337927`, the same master perflog APK, same route and
16 shots, no `XEMU_FRAME_DUMP`. If it blinks, the dump suppresses the defect: the cause is timing-sensitive, and
the frame dump cannot attribute it. If it does not, (b) is next.

## 14. Capture 5, and a correction to section 13: the screencaps were too sparse to see a blink

Capture 5 (`1791153088-lane.accuracy804-3337927`, master perflog, no dump): the body is drawn in all seven shots of
the pass (race clock 5.74-10.14), including 7.95 with the Nissan beside the camera.

**Correction.** Sections 13 and 14 counted "7 of 7 shots" as ~1/128 odds against a blink. That is wrong.
flicker801's per-triple scores (`runs/s2/4D53000F-claim/b1/flicker.tsv`) show the large blinks (100-330 permille
of the frame) only from 0.40 to 1.07 s into the burst: **a ~0.65 s window, while the rival is within a car length of
the camera**. In flicker801's worst triple the body fills the left half in N, and in N-1 and N+1 only its shadow
is drawn, right under the camera. After that window the scores are small (a distant car). My shots are ~0.7 s
apart, so each run put one or two shots in the window (capture 4: 7.21, 7.96; capture 5: 7.24, 7.95). Two drawn
shots happen 1 time in 4 under a 50% blink. **Captures 4 and 5 cannot say whether those runs blinked**, and
section 13's "the dump suppresses it / master lost it" question is open, not answered.

What stands from the dumps (captures 3 and 4): through the close pass (capture 3 frames ~140-180, race clock
~7.3-8.5) the near rival's body draws are recorded in every frame except whole-car dropouts that the guest
makes, and no recorded field of them changes frame to frame. Whether those frames' pixels had the body is the
open point.

Capture 6, the instrument that reads both in one frame: `1791153455-lane.accuracy804-3495243`, master perflog,
`XEMU_FRAME_DUMP=120,after152,images,cap400`. The images mode writes each frame's display PPM after a fence wait,
so the picture belongs to the records it is filed under (`fdump_end_frame`). Timing from capture 4: the dump
opened at `SDL_main` + N + 1.37 s and race clock 0 was at ~+147.2 s, so it starts at race clock ~6.2. 120 frames
at <= 30/s last >= 4 s and cover the 7.4-8.1 close pass with ~1 s of slack on either side. It decides:

| in the close pass | reading |
|---|---|
| a frame's records hold the body draws and its image has no body (shadow drawn) | lost after recording (H4): the cause is in what the draw consumes that the dump does not record (vertex data, constants, clip/depth state); next is per-draw vertex-attribute and constant capture for those frames |
| frames whose image lacks the body also lack its records | the guest skips it: back to a guest-side gate (H1-type), which captures 3-4 did not show |
| every image has the body | no blink in a dump run with a fence wait per frame; the wait itself may hide a timing race, and the next capture is a video of a run with no dump |

The images mode costs a fence wait per frame, which could itself suppress a timing-dependent defect. That is
the third row, and the reason it is not read as "fixed".

## 15. Capture 6: the close pass, every frame imaged: no blink

`1791153455-lane.accuracy804-3495243` (master `10f14d301d`, perflog, `XEMU_FRAME_DUMP=120,after152,images,cap400`),
15:38-15:42 PDT. The dump ran 15:40:35.05-15:40:39.26: 120 frames, 102,490 draws, 118 images (f0 and f38 stale,
not written). The images' race clocks run **05.49 to 09.58**, so the timing landed as planned.

The rival comes from behind on the left, lands beside the camera at ~7.0, and from **f53 to f91 (race clock 7.34-8.55)
its rear fills the left half of the frame**. That is the scene of flicker801's frame N, close enough to read the
same Havoline and NISSAN decals. **The body is in the image of every one of the 118 frames.** No frame shows the
shadow without the body. The near-LOD body draws (`9d4f17a01cee3e05`, >= 1800 indices) are in the records of every
frame of the pass (2-4 per frame) except f92, a whole-car guest dropout. f92's image still shows the body at 08.64,
the same clock as f93. So a dropout frame's records are not the frame that was displayed: the game drew no cars
in a frame it did not present. That is not the blink.

What the six captures settle and what they do not:

| | reading |
|---|---|
| the blink's scene | reproduced in captures 3-6 by `rallisport-804c/d.route` (Single Race, Safari SS1, Ford Escort, player standing): the Nissan passes within a car length of the camera at race clock ~7.3-8.6 |
| H1, the guest leaving the body out on alternate frames | not seen: in every dump the body's draws are issued every frame of the pass |
| the blink itself | **not reproduced in any run where it could be seen.** Capture 6 imaged every frame: none. Captures 4 and 5 (screencaps 0.7 s apart) put 1-2 shots in the window: both drawn, which says nothing (section 14) |
| what differs from flicker801's 3/3 blinking runs | the build flavour (flicker801: debug app `74a9f3ab781a`, ref `4a3308a21e`, **not perflog**; mine: perflog), the frame dump (in 3 of my 4 race runs; capture 6's fence wait per frame), and the capture (flicker801: `screenrecord` at the display rate; mine: screencaps or dump images). The nv2a code is the same (no `hw/xbox/nv2a` change from `4a3308a21e` to `10f14d301d`) |

**The brief's question, does the guest issue the car-body draws every frame, is answered "yes" for every run I
could instrument, and none of those runs blinked.** So the dump has not identified the cause. Per the brief I stop
here, without guessing a fix. The defect may need the non-perflog build, or timing that both dump modes disturb.
Neither is shown.

What the next capture needs, and why it is not mine to run: a **video of a run with no frame dump on the
non-perflog build**, the conditions flicker801 had, on master, through this route. If that blinks, the defect
lives, and the instrument must leave timing alone. The next step is then a perflog-only run, still with video, to
learn whether the flavour matters. A dispatched soak cannot record video (`route.sh` has `shot` and no `record`
step), and the burst tooling that can (`burst_capture.py`, a held session) is off limits to this lane by the
brief. So it goes to the PM: either a `record` step in `route.sh` (screenrecord on the device, pulled with the
run), or one flicker801-style claim burst on master's non-perflog build through `rallisport-804d.route`'s path. If
master does not blink either, RalliSport's Playable confirmation run (600 s, owner flicker check by eye) is the
cheaper next step. A fixed defect and an intermittent one look the same there, but the owner's eye is the judge
of record for flicker.

## 16. Do not repeat (additions)

- Do not read a screencap series as "no blink" when its spacing is longer than the blink window: the close pass
  lasts ~1.3 s and flicker801's large blinks ~0.65 s; screencaps run ~0.7 s apart.
- Do not queue a ref older than `10f14d301d` on a device where a newer build has run: libfolders' pref
  migration voids it (section 12).
- `XEMU_FRAME_DUMP` caps at 600 frames whatever the spec asks; at the race's 30-36 flips/s that is 16-20 s.
- The route that reaches the rival pass is `rallisport-804d.route` (or 804c). Hat RIGHT must be released at once
  (804b's 0.35 s hold auto-repeats to OPTIONS). Race clock 0 falls at `SDL_main` + ~147 s, and an env dump opens at
  `SDL_main` + N + ~1.4 s.
- A whole-car dropout frame in the dump (all car keys absent for 1-6 frames) is a frame the game did not
  present (capture 6, f92), not the blink.

## 17. Attempt 5 (addendum 10-04 16:00 PDT): does a plain master build blink?

Why attempt 4 stopped: it finished the brief as written. Section 15's result (no instrumented run blinked, so the
dump cannot identify the cause) went into PR.md as ready, and the next capture (video of a plain run) was outside
the brief. lane.local's addendum now allows it: one supervised flicker801-style check of a plain master build.

Build: master `63f4827758` (no `hw/` or `android/` change from `10f14d301d`, captures 4-6), **not perflog**, the
dispatcher's build (`builds/63f4827758.apk`), the same flavour as flicker801's blinking app. The dispatcher built
and installed it with a 60 s boot on the Nova, `1791154233-lane.accuracy804-3802159` (no route, no env), so the
held session runs the installed app and installs nothing by hand.

Session: `session804e.sh` takes the Nova (`hold.sh take` + `wait-idle 900`, release on every exit), checks the
installed APK's sha256 against the cached APK and that `env_vars` is empty (no frame dump), composes the titles
disk as the dispatcher does (`titlestate.prepare`), launches as pathfind does, plays `rallisport-804e.route`
(804d's path with no screencap in the race; it ends at race clock ~4) and takes one 6 s screenrecord burst
(`burst_capture.py`, scored by `flicker_score.py`) over race clock ~4.5-10.5, which holds the close pass
(7.3-8.6). A second run only if the first scores clean (p90 <= 5). Frames are then read by eye.

### 17.1 Results: both plain and perflog master blink under a screenrecord burst

| run | build (installed APK sha256, checked on the device) | env_vars | burst | flicker_score | what the frames show (read by eye) |
|---|---|---|---|---|---|
| plain1 15:52-15:56 | `63f4827758` **non-perflog** (`ed371becc3eb`), ubershader ON | empty | 6 s rec, 27.3 unique fps | **FLICKER** p90 29.4, 108 of 161 triples hit, max 39.8 | the start-race A was lost and the spare A started it, so the burst covers the 3-2-1 countdown and race clock 0-3, not the close pass. During the countdown the Beetle (#2) in front of the camera **vanishes on alternate frames with its shadow drawn** (worst triple f97-f100, race time 00:00.00), and the Corolla (#6) beside it with it. After GO each car blinks on its own (Corolla absent at 0.61, Beetle at 1.42, shadows drawn). Hits run unbroken through the countdown (`XXXX...X`, ~2.6 s), then sporadic. This is the owner's "no cars during a countdown". |
| perflog1 15:59-16:02 | `10f14d301d` **perflog** (`1ebf4fde7ede`, the APK of captures 4-6) | empty | 10 s rec, 14.8 unique fps (dt max 602 ms) | **FLICKER** p90 22.1, 45 of 145, max 323.7 | race clock 5.39-15.24, the close pass. Worst triple race clock 07.92 / 07.94 / 07.97: the Nissan's rear fills the frame in N; N-1 and N+1 show only its shadow on the road. Again at 08.89 (shadow, no car). flicker801's frame, exactly. |

Evidence: `runs/plain1/`, `runs/perflog1/` (contact sheets, worst triples, flicker.tsv, capture.json, session.log).

**Which knob removed the blink in my captures.** The owner sees the blink by eye, so screenrecord does not
create it. The perflog flavour does not remove it (perflog1 blinks in the same close pass where capture 6 did
not). That leaves the frame dump. The only run of mine that could see a blink and showed none was capture 6,
`XEMU_FRAME_DUMP=...,images`, which **waits on a fence for every frame** before writing the image. (Captures 3-5
cannot say: noimages dump or 0.7 s screencaps.) So: **a per-frame GPU wait removes the blink**; plain and perflog
builds without it blink, 2 of 2 today, 3 of 3 for flicker801.

That is what section 3's H1 predicts. The stale occlusion read happens only when the report is read before the
GPU has run the frame's queries; a fence wait per frame makes the GPU finish first. The other facts H1 needs are
already measured: the guest runs ~30 visibility-test render-pass breaks per flip in the race (capture 3, `qry`), it
issues the body draws every frame it presents (captures 3, 6: in a non-blinking run, so the guest's per-frame
decision is not observed in a blinking one), and what goes missing is whole car bodies with their shadows kept,
on stationary cars too (the countdown), which a period-2 visibility recurrence produces. Section 11's "H1
refuted" was read on a run that did not blink (section 13 already flagged that), so it is withdrawn.

### 17.2 The test of H1: master + reports-804.diff, same held burst

`hw/xbox/nv2a/pgraph/vk/reports.c` is granted to this lane (territory row lane.accuracy804, 10:5x PDT 10-04), so
the patch is now applied on the branch (`510ebb25f2`): `pgraph_vk_process_pending_reports_internal()` waits the
fence of every submitted frame before `vkGetQueryPoolResults` when queries are in flight. It cannot wait on a fence
that was never submitted: `frame_submitted[i]` is true only from the submit (render_thread.c:153,
submit_worker.c:61) to the rotation wait that clears it (draw.c:4350-4355).

| burst on the patched plain build | reading |
|---|---|
| no blink in 2 runs (p90 <= 5, frames read by eye, a car near the camera in the window) | H1 is the cause; the fix is this patch |
| blinks | H1 refuted; the per-frame fence wait suppresses something else, and the patch comes back out |

### 17.3 Result: the patched build does not blink. H1 is the cause; the fix is in reports.c

Held session 16:05-16:11 PDT, installed APK `acc497b4f822` (= `builds/510ebb25f2.apk`, master + reports-804,
non-perflog, checked on the device), env_vars empty, the same route and a 10 s screenrecord burst per run.

| run | race clock in the burst | flicker_score | the worst triple, read by eye |
|---|---|---|---|
| patched-run1 | 5.15-14.68 (the close pass, 7.0-9.0) | **clear** p90 0.83, 13 of 139 hits in one stretch | race clock 07.36 / 07.39 / 07.44: the Nissan's rear fills the frame in **all three** frames; the hits are the car moving at a car length (spoiler and decal edges), not a blink |
| patched-run2 | the same pass | **clear** p90 1.02, 15 of 137 | race clock 07.39 / 07.40 / 07.42: body in all three, edge motion only |

Against the same scene: unpatched master blinked in every run that filmed it (plain1 countdown and race clock 0-3,
perflog1 race clock 7.92-8.89 with p90 22.1, flicker801's 3 of 3 boots on pathfind's path, which reaches the same
start). The patch removes it in 2 of 2. Both outcomes were laid out in 17.2 before the runs. The other knob that
removed it, capture 6's per-frame fence wait, works by the same mechanism.

**Cause.** RalliSport tests each car's visibility with occlusion queries and draws the body only when the last
report it read says the car was visible. A deferred finish (FLIP_STALL, PRESENTING, STALLED, SURFACE_DOWN_FLUSH)
returns to the guest after `vkQueueSubmit`, without the fence wait. `pgraph_vk_process_pending_reports_internal()`
then reads the query pool with WAIT_BIT. On Turnip the slot's reset is a GPU command, so a slot the GPU has not
reset yet reads as available, holding the count from the previous command buffer's query at that index. The
report for frame k therefore holds frame k-1's count, which gives the period-2 recurrence of section 3. The
shadow is not gated by the query, so it is drawn every frame.

**Fix** (`hw/xbox/nv2a/pgraph/vk/reports.c`, `pgraph_vk_process_pending_reports_internal()`, granted file): when
queries are in flight, wait the fence of every submitted frame before reading the results. Upstream xemu always
waits before reading. Only a finish that recorded a query pays for it, but RalliSport records ~30 per flip in a
race, so its race frames now serialise CPU and GPU at those finishes. **The fps cost is not measured here.** The
screenrecord rate (14.2-14.4 unique fps patched against 14.8 for perflog1 in the same pass) runs straight after an
APK switch with a cold shader cache (dt max 0.5-0.6 s) and is no fps number. RalliSport's Playable confirmation
(600 s, fps verdict plus the owner's flicker check) measures it.

Nova hold time used: 3.2 + 3.0 + 5.9 = ~12 min (three sessions), plus three 60 s dispatched install boots.

## 18. Do not repeat (additions)

- Do not read "the dump shows the body every frame" as refuting a visibility-test gate when that run did not
  blink: section 11's refutation of H1 was read on a non-blinking run, and H1 was the cause.
- An instrument that waits on the GPU every frame (`XEMU_FRAME_DUMP ...,images`) removes a CPU/GPU ordering
  defect. Check whether a defect survives the instrument before reading anything from it: one plain-build video
  first would have saved captures 3-6.
- A dispatched 60 s boot at a ref is the clean way to get a build installed for a held session: the dispatcher
  builds the right flavour, clears the shader cache and writes `env_vars`, and `session804e.sh` checks the APK's
  sha256 against `builds/<ref>.apk` before touching anything.
- `rallisport-804e.route`'s first start-race A is sometimes lost (plain1). The spare A then starts the race ~8 s
  later, and a 6 s burst lands on the countdown, which blinks too. A 10 s burst covers either case.

## 19. Attempt 2 of the re-open (addendum 10-04 19:10 PDT): the owner sees no rival cars on the fix build

**Why the previous attempt did not finish.** It did finish the brief it had: "does a plain build blink, and if so
which knob removes it" (section 17), and it was folded as `6f463a0ae2`. Its acceptance test was "does not blink",
which a build with no rival cars also passes. The owner then played the fix build (debug
0.4.1-1004-064ca7aa43) and saw no flicker and **no NPC cars or shadows at all**. This attempt answers that.

### 19.1 Offline, before any device run

**The owner's build is the code my patched captures ran, file for file.** `git diff 510ebb25f2 064ca7aa43 -- .
':!docs'` is empty: the owner's APK and my test APK (`acc497b4f822`, section 17.3) differ only in docs.

**Three captures on that exact code show rival cars**, two of them in frames I had already read:

| capture | code | what the frames show |
|---|---|---|
| patched-run1, 16:05-16:11 (`runs/patched-run1/sheet.jpg`) | `510ebb25f2`, non-perflog | a rival far ahead at race clock 5.15-6.40, the Nissan landing beside the camera at 7.03, its rear filling the frame 7.36-8.32, then pulling away at 8.94-9.57. Body drawn in every frame of the worst triple |
| patched-run2 | same | same pass, body in all three frames of the worst triple |
| lane.local's 600 s hold, 16:22 (`~/hakux-work/perf/2026-10-04-ralli804-fps/run/frames/015-gameplay.jpg`, `016-probe-a.jpg`) | the installed `510ebb25f2` (lanelocal-log 16:35 entry) | **015, race clock 00:00.00 (the grid): the Beetle (#1, Mobil) right in front of the camera and the Corolla (#6, Castrol) to its left, both drawn.** 016-probe-a, 06.67: the Nissan beside the camera. The hold's own strip (race clock 1:38-12:05) shows no rival because the player is last and stuck on scenery, not because cars are missing |

So the claim "the fix makes the visibility count read 0 on every frame" does not hold on the dispatcher's path: the
grid cars and the passing Nissan are drawn on the fix build. What the owner saw is not reproduced by any capture,
and no capture so far ran what the owner ran.

**What differs between the owner's session and every capture**, from the dispatcher's last copy of the Nova prefs
(`dispatch/.prefs.nova.xml`, 15:50) and `titlestate`:

1. **The HDD.** Every dispatched and pathfind run swaps `hddPath` to `titles.qcow2`, the composed golden
   (`cc9b4ced4a0f`, pathfind's profile: Single Race, Rally, Safari SS1, Ford Escort). The app's own `hddPath` is
   `hdd.img`, which is what the owner plays on: their own profile, saves and game options.
2. **The mode, track and how far they drove.** Unknown. My captures and lane.local's have the player standing or
   stuck at the start, with the rivals passing the camera. A player who drives off the line leaves the rivals behind
   (out of view, shadows too) unless the race has cars ahead.
3. **Session age and shader cache.** The owner played after a 120 s gate run and a reinstall; mine ran straight
   after an APK switch.

None of these is shown to matter. The instrument below separates "the visibility tests return 0" (an emulator
defect the owner's session exposes) from "the cars were not in view" (a capture question).

### 19.2 Instrumentation (reports.c, granted file; off unless set)

`HAKUX_OCCL_LOG=<s>` writes one `hakuX-lane` line per guest frame from `<s>` seconds after the first report: the
queries read (`q`), how many were nonzero (`qnz`), how many submitted frames were still running on the GPU at the
read (`pend`), the reports handed to the guest (`rep`, `repnz`, `repmax`) and the first 48 report values (`v=`).
`HAKUX_OCCL_WAIT=0` skips the #804 fence wait, the code before the fix, in the same binary. So one build gives the
zero-vs-nonzero split before and after the change. Compiled with the NDK clang (`-fsyntax-only -Wall`): clean.

Route `rallisport-804f.route`: 804d plus six screencaps during the countdown (`c1`-`c6`), then 804d's sixteen race
shots (`r1`-`r16`, race clock ~5-11, the pass).

| arm | env | reads |
|---|---|---|
| fix | `HAKUX_OCCL_LOG=100` | grid and pass shots show the rivals or not; `v=` shows what the guest got |
| no-fix | `HAKUX_OCCL_LOG=100 HAKUX_OCCL_WAIT=0` | the same, the pre-fix reads; `pend` > 0 with a changed `v=` pattern is the stale read of section 17.3 |

What each outcome means:

| fix arm | reading |
|---|---|
| cars in the shots, `repnz` > 0 on car frames | the fix works on this path; the owner's session differs in something the golden HDD and this route do not reproduce, and the owner is asked for mode/track/what was on screen |
| no cars, `repnz` = 0 where the no-fix arm has nonzero | the correct read is 0: the visibility test's own draws pass no samples on our GPU path, and the pre-fix blink came from stale slots holding another query's count. The fix belongs in what the test draws against (depth/clip state of the query draws), not in the read |

## 20. Attempt 3 of the re-open: the two queued runs, read; Career is the lead

**Why the previous attempt did not finish.** It ended as designed, WAITING on two Nova runs queued behind the
owner's hold (section 19.2). Both ran 19:16-19:25 PDT (clean, adb_failures 0), and handback resumed the lane.

### 20.1 The fence wait on and off, one binary (`5e16698c99`), route `rallisport-804f` (Single Race, Safari SS1)

Evidence: `runs/occl-fix/`, `runs/occl-nofix/` (contact sheets of c1-c6 and r1-r16, the `[occl804]` lines).
`occl_read.py` reads the logcat lines.

| | fix arm `1791166524` (`HAKUX_OCCL_LOG=100`) | no-fix arm `1791166528` (`+ HAKUX_OCCL_WAIT=0`) |
|---|---|---|
| intro flyover (c1-c3) | Escort #7 and the others drawn | the same |
| grid, race clock 00:00.00 (c4-c6) | **Beetle #3/#2 in front of the camera, Corolla #6 to its left, both drawn** | the same |
| race clock 2.8-6.3 | a rival ahead on the left, drawn in every shot | the same |
| the pass | **Nissan rear fills the frame at 07.39 and 08.14**, drawn at 08.77, 09.45 | Nissan airborne beside the camera at 07.08, rear fills the frame 07.76 and 08.32, drawn at 08.96 |
| `[occl804]` frames logged | 5,571 | 5,597 |
| `pend` > 0 (a submitted frame still on the GPU at the read) | **0 frames** | **0 frames** |
| race window (grid to r16): queries nonzero | 6,545 of 21,848 (30.0%) | 6,907 of 22,363 (30.9%) |
| race window: query batches with every report 0 | 37 of 745 | 48 of 747 |

So, on the owner's exact code, in the Single Race scene: the rivals and their shadows are drawn on the grid and
through the pass, and the visibility tests return nonzero counts in 30% of reads, the same with the fence wait
on and off. The brief's candidates for "results now zero or unreachable" (wrong slots, reset at read, reading
an unsubmitted frame, wrong offset) each predict a zero-heavy fix arm. None shows: the fix arm's report values
are indistinguishable from the no-fix arm's.

`pend` = 0 on every frame of both arms also means that **in these runs, with no screenrecord, the fence wait
had nothing to wait for**. Every submitted frame's fence was already signalled when the reports were read
(`submit_frames` = 2 on the Nova, per the dump session records of captures 3-6). The stale read of section 17.3
needs a frame still on the GPU at the read. It did not occur in either arm here, so these two runs could not
blink and say nothing for or against the fix's effect on the blink. They answer only the owner's question: on
this path the fix build does not zero the visibility reads and does not remove the cars. The blinking runs
(plain1, perflog1, flicker801) all ran a 6-10 s `screenrecord`, which adds GPU and encoder load. Whether the
owner's eye-visible blink came from the same GPU-behind-the-read window is not measured.

### 20.2 The owner's symptom on code from before the fix: Career

Capture 1 (`1791136124`, ref `5e4196fefd`, **before the reports.c fix**) took **CAREER -> Safari SS-1**, the item
lit on the game menu, so the mode a player reaches by pressing A. Its shots (`runs/cap1-career-sheet.jpg`; the
originals are in the result dir) show POS 4 OF 4, the player at the start banner, and **no rival car or shadow
at race clock 7.37, 11.31, 15.21, 19.05, 23.96 or 46.30**. Its dump has **0 frames with a rival body draw**
(shaders `9d4f17a01cee3e05`/`ece9f59044a636fd`) in 600 race frames (race clock 4-14). Capture 3 (Single Race,
same code) has them in 414 of 600. The visibility boxes run in Career too (shader `8f6c865e558bb778`, 390
frames).

So "no NPC cars visible at all, ever, nor their shadows" is what Career's Safari SS-1 looked like **before the
fix**, to a standing player. Single Race starts all four cars on a grid behind each other. Career starts the
player alone at the banner, and the rivals are not drawn. The mode has not been confirmed by the owner. Career is
the default and the likeliest choice, P ~0.6. If the owner drove, a rival might still come into view later in
the stage: capture 1 stood still.

### 20.3 What would close it, queued

`rallisport-804g.route`: capture 1's Career path, unchanged, then the throttle held (`axis RT max`) for ~50 s
with a shot every ~2 s, no steering. The same binary, the fence wait off then on:

| run | env |
|---|---|
| `1791167617-lane.accuracy804-3666473` | `HAKUX_OCCL_LOG=100 HAKUX_OCCL_WAIT=0` (pre-fix) |
| `1791167624-lane.accuracy804-3669384` | `HAKUX_OCCL_LOG=100` (the shipped fix) |

| result | reading |
|---|---|
| no rival in any shot of either arm | the owner's "no cars" is Career's normal start on any build; the fix did not remove them. RalliSport goes to the owner's flicker check in Single Race, where both rival scenes exist |
| a rival in the no-fix arm's shots and none in the fix arm's, at the same stage point | a real regression in Career; the `[occl804]` values of the two arms at that point show which reads changed |
| a rival in both | not a regression; the owner's session differed in something else (ask for the mode and the moment) |

The order is deliberate: the no-fix arm runs first, so the Nova is left with `HAKUX_OCCL_LOG=100` only, the
shipped fence-wait behaviour plus a log line per frame.

**Side effect to know about.** The dispatcher clears `env_vars` only at the next request (dispatcher.sh "we clean
up after ourselves", lazily). After my 19:24 no-fix arm, the Nova's app carried `HAKUX_OCCL_WAIT=0`, the pre-fix
read, into whatever ran next by hand: lane.pathfind's held run from 19:25 (`gg-hold2`), and the owner, if they
play before the next dispatched request. The owner's own 17:2x-19:10 session inherited no env: the dispatched
runs before it (15:52-17:20) all had empty env.

## 21. Do not repeat (additions)

- Do not reach RalliSport's rivals through CAREER and do not judge "cars missing" there: Career's Safari SS-1
  start shows no rival on code from before the fix (capture 1). Single Race (804c/d/f) has the grid and the pass.
- `pend` (submitted frames still on the GPU at the report read) was 0 in every frame of a dispatched run without
  screenrecord. A run that is to show the stale read needs the GPU behind the read; check `pend` before reading a
  no-fix arm as "the blink's condition".
- A request's env stays on the device until the next request: queue an A/B so the shipped-behaviour arm runs last.

## 22. Attempt 4 of the re-open: the Career drive runs, read; car presence counted per frame

**Why the previous attempt did not finish.** It ended as designed, WAITING on the two Career runs of section 20.3,
queued behind lane.pathfind's hold. Both ran (20:02 and 20:36 PDT, ref `5e16698c99`, APK `2c335088e76b`, the
golden HDD) and handback resumed the lane. Nothing was left half-done.

### 22.1 Career, Safari SS-1, throttle held, fence wait off and on

Evidence: `runs/career-nofix/`, `runs/career-fix/` (sheets of c1-c3 and d1-d20 plus the gameplay shot; the
`[occl804]` lines from c2 to the gameplay shot).

| | no-fix arm `1791167617` (`HAKUX_OCCL_WAIT=0`) | fix arm `1791167624` (shipped fix) |
|---|---|---|
| shots | start banner, race clock 0.00 and 1.4, then 6.9 to 60.7 (POS 4 OF 4 in every shot) | start banner, 0.00 and 1.7, then 7.1 to 61.1 (POS 4 OF 4) |
| rival car or shadow in any shot | **none** | **none** |
| visibility queries nonzero, c2 to the end | 444 of 18,668 (2.4%) | 492 of 17,095 (2.9%) |
| query batches with every report 0 | 2,280 of 2,674 | 2,042 of 2,474 |
| `pend` > 0 | 0 frames | 0 frames |

Section 20.3's first row holds: **no rival in either arm.** The owner's "no NPC cars visible at all, ever, nor
their shadows" is what Career's Safari SS-1 shows on this emulator with the fence wait off (the code before the
fix) and on alike, and capture 1 already showed it on `5e4196fefd`, a build from before reports.c changed. The
fix did not remove the cars there. The visibility reads are mostly zero in Career and equally so in both arms,
against 30% nonzero in Single Race (section 20.1), so Career's tests have few hits to report on either build.

Not checked: whether a real Xbox shows a rival in Career's Safari SS-1 in the first minute. A player who drives
the stage longer, or another Career event, is not covered. Nothing here suggests an emulator defect in Career,
and nothing rules one out. If one exists, it is older than the fix.

### 22.2 The car is drawn on every frame of the pass on the fix build: pixels counted

The patched screenrecord bursts of section 17.3 (`s804e-c`, installed APK `acc497b4f822` = `510ebb25f2`, code
identical to the owner's `064ca7aa43`) and the unpatched perflog1 burst (`s804e-b`, `10f14d301d`) keep every
video frame. `carpix.py` takes each unique frame (a frame that differs from the previous one by a mean of 0.5 or
more out of 255) and counts the Nissan's red livery pixels below the HUD row, with the tachometer masked.
`carshare.py` sets the pass window from the first to the last frame with red share > 0.015 (the car near the
camera) and calls a frame absent at red share <= 0.003. Calibrated by eye on perflog1: the shadow-only frames
read 0.0007-0.0014, and frames with the body drawn read 0.004-0.06.

| burst | build | pass window (race clock ~7.2 to ~8.8) | body drawn | absent frames |
|---|---|---|---|---|
| perflog1 | unpatched | 50 unique frames | **43 (86.0%)** | u63, u69, u75, u77, u81, u82, u97 (race clock 7.52, 7.71, 7.92, 7.97, 8.09, 8.10, ~8.6) |
| patched-run1 | the fix | 48 | **48 (100%)** | none |
| patched-run2 | the fix | 51 | **51 (100%)** | none |

Sheets with the race clock on every frame: `runs/presence/{perflog1,patched1,patched2}-pass.jpg`. Read by eye,
they agree with the count, with one difference: perflog1 also loses the body at 07.17 (just before the window
opens) and at 08.52 (u95), where the exhaust flame's orange pixels lift the red share to 0.0049. So the
unpatched miss count is at least 7 and by eye 9.

**This capture shows a car**, the passing Nissan. It is the capture the PR names.

What it does not cover:
- **30 s with the countdown, on the fix build, under a screenrecord.** The patched bursts are 10 s and start at
  race clock ~5. On the fix build the grid cars are drawn in single shots: occl-fix c4-c6 (Beetle and Corolla at
  00:00.00) and lane.local's hold frame 015. But those runs had `pend` = 0, so a blink could not show in them.
  The unpatched countdown blink (plain1) has no filmed counterpart on the fix build.
- **Why the blink needs a screenrecord.** Every dispatched run without one had `pend` = 0 (sections 20.1, 22.1).

**fps on the fix build**: lane.local's 600 s hold (16:22, the installed `510ebb25f2`) scored 534 windows, 100% at
or above the 30 fps bar, window median 56.5, min 29.63
(`~/hakux-work/perf/2026-10-04-ralli804-fps/run/verdict.json`). That hold's player was stuck behind the field,
so most of its windows are not the ~30 queries per flip of a rival pass. The fps cost of the wait while rivals
are in view is not measured on its own.

### 22.3 Where #804 stands

| question | answer | evidence |
|---|---|---|
| does the fix zero the visibility reads or remove the cars? | no, in both modes tried | Single Race: 30.0% vs 30.9% nonzero, cars on the grid and in the pass (20.1). Career: 2.9% vs 2.4%, no rivals in either arm (22.1) |
| where does the owner's "no cars, ever" come from? | Career's Safari SS-1 looks like that on the code before the fix too (capture 1, 22.1) | the owner's mode is still unconfirmed; Career is the menu default |
| does the fix stop the blink? | yes in the pass: body in 100% of 99 unique frames over two bursts, against 86% unpatched | 22.2 |
| what is left | a 30 s filmed window with the countdown on the fix build, and the owner's eye check in **Single Race** | needs a held screenrecord session or the owner |

No device time was used in this attempt.

## 23. Do not repeat (additions)

- Do not judge RalliSport's rivals in Career, Safari SS-1: no rival is drawn in the first minute on any build
  tested, so "no cars" there tells you nothing about a fix. Use Single Race (804c/d/f routes).
- Before asking for a new capture, check whether the old ones kept every frame. The section 17 bursts kept all
  frames in `.scratch/s804e-*/run*/fr/`, which was enough for a per-frame presence count with no device time.
- In a blink count, a red share threshold can mistake the exhaust flame for the body (perflog1 u95). Read the
  sheet by eye next to the count.
