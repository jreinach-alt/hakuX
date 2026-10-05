# lane.belowbar1005: what holds Buffy, NG Black and DOA3 below the 28.5 fps bar; is the #804 fence wait the cost? (#433)

Brief (lane.local, 2026-10-05): telemetry first, not a retest. The suspect is
the 10-04 #804 fix (510ebb25f2, folded 6f463a0ae2 at 18:45 PDT 10-04): before
every occlusion-query read, `pgraph_vk_process_pending_reports_internal`
waits on the fence of every submitted frame (hw/xbox/nv2a/pgraph/vk/reports.c
243-263). P ~0.25 that it is the cost.

The switch exists as named: `HAKUX_OCCL_WAIT=0` skips the wait
(reports.c 158-159, 243); `HAKUX_OCCL_LOG=<s>` logs one `[occl804]` line per
guest frame on tag `hakuX-lane` from <s> s after the first finish, with the
queries read (`q`), how many were nonzero, and how many submitted frames were
still running at the read (`pend`, i.e. how often the wait actually blocks).
The wait runs only when `num_queries_in_flight > 0`: a title that reads no
occlusion query never pays it.

## Step 0: which build each below-bar run used

The retro-* runs are lane.pathfind held runs (`wt/pathfind/docs/lanes/pathfind/runs/`).
Their verdict.json has `ref: null`; a held run uses whatever debug apk the
last dispatched request installed. From `dispatch/logs/dispatcher.log`
(`shader cache cleared: apk X -> Y`, `ENV: cleared`):

| run | app start (PDT 10-04) | installed by | ref | apk | #804 fence wait | env in the pref |
|---|---|---|---|---|---|---|
| retro-doa3 | 20:40:28 | 1791167624-lane.accuracy804-3669384 (ended 20:40:19) | 5e16698c99 | 2c335088e76b | **yes** (default on) | HAKUX_OCCL_LOG=100 (logging only; its tag is not in pathfind's logcat spec) |
| retro-ngb | 21:19:28 | 1791169299-lane.async794-4125394 (ended 21:03:10) | 39fc5d0a57 | 425964a8c624 | **no** | cleared |
| retro-buffy | 21:36:07 | same | 39fc5d0a57 | 425964a8c624 | **no** | cleared |

`git merge-base --is-ancestor 510ebb25f2 39fc5d0a57` is false: 39fc5d0a57 is
lane/async794's head, which merged master f3bd87638e from before the #804
fold. **So the Buffy and NG Black runs that screened below the bar did not
contain the fence wait.** It cannot be what held them there. Only the DOA3
run carried it.

Regimen: all three are held runs on the device's defaults; the 10-02 runs
they are compared against (titleroutes, titleroutes2) are dispatcher soaks on
the "max" regimen (`thermal.regimen: max`). fps20786 already found the same
title reading 20 vs 24 fps between the two. Compare like with like.

### The earlier figures, re-read

| title | run | device, regimen | ref | window median | share >= 28.5 | what it measured |
|---|---|---|---|---|---|---|
| Buffy | 1790931264 / 1790932722 (10-02) | Nova, max | 17c3bc721f / 68bd2e6df6 | 29.97 | 0.95 / 0.96 | a stuck view at the canyon's first ledges (targets.toml: "one frozen sky view for ~4 min") |
| Buffy | retro-buffy (10-04) | Nova, defaults | 39fc5d0a57 | 29.27 | 0.55 | 608 s of play on the forest path |
| NG Black | 1790944628 (10-02) | Nova, max | bd03a589f7 | 39.4 | 0.75 | 110 s of play, judged against a 60 target |
| NG Black | retro-ngb (10-04) | Nova, defaults | 39fc5d0a57 | 27.61 | 0.25 | 611 s of play |
| DOA3 | 1790805442 (09-30) | Thor, max | 5b193af6d0 | 52.22 | 0.60 | crashed at 475 s |
| DOA3 | retro-doa3 (10-04) | Nova, defaults | 5e16698c99 | 29.96 | 0.44 | 600 s play of 856 (menus, cutscenes) |

Neither 10-02 figure is a like-for-like baseline: Buffy's measured a stuck
view, NG Black's 110 s on a different regimen. There is no same-device,
same-regimen, same-scene pair before and after 6f463a0ae2 for any of the three.

## Step 1: decomposition of the existing runs (offline)

`decompose.py` here is docs/lanes/fps20786/decompose.py unchanged (the near30
method; columns in docs/lanes/fps20786/NOTES.md "Method"). Rows are the 2-s
always-on windows from the start of each run's captured logcat (`--mark` =
first line: Buffy 21:38:37, NGB 21:24:48, DOA3 20:45:45, all in held play).
None of the three is a perflog build, so ph_GPU / ph_Fin / lockw are absent.
All Nova, all device defaults: same device, so the rows compare.

Per guest frame of F ms (medians of rows):

| title | rows | fps | F | gbusy | gidle | Ri (render idle) | rcpu (render on-CPU) | rblk (render blocked) | v_run (vCPU on-CPU) | v_blk (vCPU asleep) |
|---|---|---|---|---|---|---|---|---|---|---|
| Buffy, below 28.5 | 153 | 26.5 | 37.8 | 31.0 | 6.6 | 19.6 | 11.2 | 7.8 | 30.8 | 8.0 |
| Buffy, slowest 10% | 39 | 24.6 | 40.7 | 39.0 | 1.7 | 18.9 | 12.1 | 10.4 | 31.4 | 9.3 |
| NGB, below 28.5 | 229 | 27.2 | 36.8 | 36.3 | 0.4 | 0.6 | 11.6 | 24.1 | 21.3 | 15.5 |
| NGB, slowest 10% | 58 | 26.4 | 37.9 | 37.6 | 0.1 | 1.9 | 11.9 | 24.4 | 22.0 | 16.4 |
| DOA3, below 28.5 | 209 | 20.0 | 50.1 | 23.9 | 27.5 (23.3 timer-woken) | 6.6 | 12.5 | 32.1 | 46.7 | 4.9 |
| DOA3, slowest 10% | 53 | 17.0 | 58.9 | 26.7 | 32.9 | 7.4 | 14.3 | 36.8 | 52.7 | 5.6 |

Read:

- **Buffy: the vCPU (guest code).** In the slow rows the guest is busy 31 of
  38 ms and 39 of 41 in the slowest tenth; the renderer sits idle ~19 ms per
  frame waiting for the guest. The vCPU thread is on-CPU 31 ms and asleep
  8-9 ms per frame, which is a lock or condition wait inside guest work
  (near30's Tron signature: v_blk tracking the renderer). VBLANKs per flip
  are v2 57 of 60 with a few v3: a 30-fps title missing 33.3 ms by a few ms.
- **NG Black: the render thread, blocked.** The guest never reaches its idle
  loop (gbusy = F), so the thread split carries it: the renderer is never
  idle (Ri 0.6), on-CPU only 11.6 ms and **blocked 24 ms per frame**, and
  the vCPU sleeps 15.5 ms per frame behind it. The VBLANK interrupt itself is
  late: `vbl ... rate=39-46 Hz, def=59-65 of 80-93` (deferred) where Buffy
  reads ~56.5 Hz, def=7. Blocked time with a tiny on-CPU share is a GPU or
  fence wait; which one needs a perflog run (ph_GPU vs ph_Fin, `hakuX-stall`
  finish reasons). The #804 wait was not in this build.
- **DOA3: the render thread, blocked, on one stage.** The slow rows are one
  stretch, t = 150-560 s, at 18-20 fps; the route frames there show the Bass
  fight on the gold-screen dojo stage with a reflective floor (FPS overlay
  19). Other fights in the same run read 30-55 fps. In the stretch the guest
  idles ~28 ms per frame woken by the timer (it waits; it does not work)
  while the render thread is blocked 30-37 ms and on-CPU 12-14. That is a
  renderer-side bound, and this build **did** carry the fence wait.

## Step 2: decisive test (registered here, before any run)

One binary, ref d32c35d3ce (master: the #804 fix, the switch, and async794),
plain debug build. Nova, `--env PERF_REGIMEN=default` (the regimen of the
below-bar held runs). Route `routes/bb-buffy.route`: retro-buffy's 13
pathfind steps at their own times + 4 s, then pathfind's `attack` hold loop
(STICK:up, X, A, RSTICK:right, STICK:down, B, RSTICK:left, X), mark at
~121 s. 360 s per arm (the brief says 300; with a 121-s menu path that leaves
179 s of play, 360 leaves ~240). Both arms `HAKUX_OCCL_LOG=150`.

- arm N: `HAKUX_OCCL_WAIT=0` (no wait), queued first
- arm W: wait on (the shipped code), queued last, so the Nova is left on the
  shipped setting

The first arm after a new apk runs on a cleared shader cache and the second
keeps it; with the ubershader on (`ubershader: ON (#569)`, retro-buffy
hitches 0) that costs little frame rate, and the bias favours W, the
direction against the hypothesis. Read `shader_cache` in both result.json.

**Decision rule.** Score each arm with the dispatcher's verdict (fps_ok_share
at 28.5, window median) over the scored window from the mark.
- share(N) - share(W) >= 0.15: the fence wait costs frame rate. Write the
  fix proposal (wait only for queries the guest reads, only for the frames
  that recorded them) and flag it on OUTBOX for lane.local.
- otherwise: the wait is not Buffy's bound. Then `[occl804]` says why: `q=0`
  on every line means Buffy reads no occlusion queries and the arm could not
  see the wait at all (inert by construction, not a refutation for other
  titles); `q>0` with `pend>0` means the wait blocks but is absorbed (the
  renderer has ~19 ms of idle per frame to absorb it, per Step 1).

Prediction before the run: no difference beyond noise (P 0.85). Buffy's slow
rows are vCPU-bound with the renderer idle ~19 ms per frame, so a render
thread wait has room to hide; and its below-bar run did not have the wait.

### Arm N (1-1791212323-lane.belowbar1005-2091227, 07:59-08:06 PDT 10-05)

apk ce2ac5751374 (d32c35d3ce), shader cache cleared, regimen default. The env
took: `[occl804] config log=1 after_s=150 wait=0` at 07:59:42. The route
reached live play at the Spanish Mission at the mark (route-frames
080153-gameplay through 080543-hold, overlay FPS 29). Verdict (title_verdict.py
on a copy): 234 s of play, **fps_ok_share 0.83**, window median 29.96, no
hang, no hitch.

**Buffy reads no occlusion queries.** From 08:02:12 (150 s after the first
finish) to the end at 08:05:47, the log printed no `[occl804] f=` line. A line
is printed for every guest frame in which `pgraph_vk_process_pending_reports_internal`
found a query in flight or a report queued (reports.c 227-233, 180-187), so
none was, for 215 s of play. The fence wait sits behind
`num_queries_in_flight > 0` (reports.c 243), so on Buffy it never runs, on
either arm. The A/B cannot move Buffy's frame rate: **inert by construction**.
That answers the brief's question for Buffy (the fix is not its cost) but
says nothing about titles that do read queries; DOA3 and NG Black are checked
below with the same log.

Decomposed (rows from the mark):

| run | rows | share >= 28.5 | fps | F | gbusy | gidle | Ri | rcpu | rblk | v_run | v_blk |
|---|---|---|---|---|---|---|---|---|---|---|---|
| arm N, all | 121 | 0.81 | 29.9 | 33.5 | 15.1 | 18.7 | 25.8 | 7.8 | 0.2 | 32.0 | 1.6 |
| arm N, below 28.5 | 23 | -- | 27.2 | 36.7 | 26.7 | 10.4 | 23.7 | 10.0 | 6.1 | 30.1 | 6.5 |
| retro-buffy, all | 302 | 0.49 | 28.5 | 35.1 | 25.9 | 9.1 | 22.3 | 10.3 | 3.5 | 30.5 | 4.7 |

The share differs (0.81 vs 0.49) because the scene differs: the route's
loop stays around the mission courtyard, while pathfind's hold walked on to
the forest path, where the guest works 26 ms per frame against 15 here. In
both, the slow rows are the guest's (gbusy 27-31 of 37-38 ms, renderer idle
19-24 ms). Buffy is a 30-fps title that misses 33.3 ms by a few ms when
the guest's own work grows.

### Arm W (1-1791212327-lane.belowbar1005-2091528, 08:44-08:51 PDT) and the verdict

Same apk, `[occl804] config log=1 after_s=150 wait=1`. The shader cache was
cleared here too (`apk unrecorded -> ce2ac5751374`: lane.hitchcause's held
session had installed its own apk in between), so both arms started cold.
Again no `[occl804] f=` line in 210 s of logged play.

| arm | fence wait | play s | fps_ok_share | window median | occl lines |
|---|---|---|---|---|---|
| N | off | 234 | **0.83** | 29.96 | config only |
| W | on (shipped) | 212 | **0.67** | 29.96 (verdict), 29.7 rows | config only |

By the registered rule, share(N) - share(W) = 0.16 >= 0.15, which would read
"the fence wait costs frame rate". **It does not, and the rule as written
was wrong to key on the share alone**: the code it tests did not run in
either arm (no query in flight, no report queued, for the whole logged
window), so the two arms executed the same instructions and the 16 points
are run-to-run variation. Where it comes from, in 30-s buckets: the arms
match for the first 90 s (0.53/0.40, 0.73/0.80, 0.93/0.93) and part where the
loop's walk ends up. Arm W's walk left the mission courtyard for the forest
path at t = 90-150 s and again at 210 s (route frame 084922-hold: the forest
path, overlay FPS 24), the same stretch that pulled retro-buffy to 0.55; arm
N stayed in the courtyard. In those buckets every component rises together
(guest busy 21-31 ms, render CPU 10.5-12.7, render blocked 7-12.5, vCPU
asleep 4.4-10): heavier content, not one stall.

So for Buffy: **the #804 fence wait is not the cost; it never executes.**
And a 300-360 s route soak of Buffy carries about +/-0.15 of share from the
walk alone; any future Buffy A/B needs either a scene the loop cannot leave
or the occl-style "did the code run" line, not the share.

Side effect, flagged: lane.pathfind took the Nova (gg5, hold at 07:59:34)
while arm N ran, so its held run started on this apk with arm N's env still
in the pref (`HAKUX_OCCL_WAIT=0`, `HAKUX_OCCL_LOG=150`, `PERF_REGIMEN=default`;
the dispatcher clears env only at the next request). For a title that reads
occlusion queries that is the pre-#804 behaviour. Arm W, queued behind it,
restores the shipped env when it runs.

## Step 3a: NG Black (1-1791212834-lane.belowbar1005-2132085, 09:06-09:15 PDT)

Perflog build of d32c35d3ce (apk 63abb775f234, shader cache cleared), regimen
default, shipped fence wait, `HAKUX_OCCL_LOG=200`. Route `routes/bb-ngb.route`
(retro-ngb's 32 steps, then the attack loop) reached play at the mark
(09:11:19): Ryu at the chapter-1 waterfall gorge (route frames 091237-hold
FPS 39, 091431-hold FPS 35). 217 s of play: fps_ok_share 0.78, 4 hitches
(worst 291 ms, cold cache). Not retro-ngb's stretch (0.25): pathfind's hold
walked further; the waterfall is the lighter opening.

**NG Black reads occlusion queries, and the wait never blocks.** 190
`[occl804] f=` lines from 09:12:35 to 09:14:58: queries in 190 guest frames
of ~5,000 (q = 1-3 per frame, the visible-pixel count of a small effect,
values ~200), and `pend=0` on all 190: at every read, no submitted frame was
still running, so `vkWaitForFences` returned on signalled fences. The wait
costs NG Black nothing measurable here; no WAIT=0 arm is needed to say so (it
would differ only by those already-signalled waits).

**Bound: the GPU.** Per guest frame (decompose.py rows, perflog columns):

| rows | n | share >= 28.5 | fps | F | GPU (ph_GPU) | render on-CPU | render blocked | render idle | finish | vCPU asleep | lockw |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 112 | 0.79 | 35.1 | 28.5 | 24.2 | 11.2 | 16.5 | 0.3 | 2.7 | 9.8 | 1.4 |
| below 28.5 | 23 | -- | 25.5 | 39.2 | 32.6 | 15.0 | 23.9 | 0.3 | 2.6 | 15.2 | 6.3 |

- F tracks the GPU time in every 30-s bucket (GPU 21-27 ms, F 25-38): the
  frame is the GPU's time plus ~4 ms. The render thread is never idle
  (Ri < 1.5 ms) and its blocked time (15-24 ms) is the flip waiting on the
  GPU (finish is only 2.6-4 ms: `Fin:5.8(Sub:0.3 Fen:5.5)` per frame at
  most, `flip60 stlDef75` per 2 s, **no surface-download finishes**: `sd0`,
  `dlSrc 0`, so not #794's class).
- **Half of the GPU time is outside render passes.** xemu-gpu medians:
  Tot 23.9 = Rnd 12.2 + **Xfr 11.7** ms per frame (`gpu_nonrender_ms`). Over
  the same windows: 7-8 surface uploads per frame (`xemu-surf #upl:444-463`
  per 60 frames), 7 render-pass breaks per frame for surfaces
  (`hakuX-rpbrk srf420` per 60), 3 clears per frame (`clr180`), 9 texture
  ↔ surface conversions (`S2T:9`). That GPU-side copy/convert work is the
  lever, not the draws (282 draws/frame, R 10-12 ms).
- The slow buckets (t = 0-30 and 150-180 s) add pipeline creation (ph_Draw
  11-17 ms against 6-8, cold cache) and pgraph.lock wait (6-12 ms, `flip_op`
  10 ms per frame on average); they are where the hitches are.
- NG Black is a 60-fps title (VBLANKs per flip v1 0.65, v2 0.29 here): it
  runs 30-40 fps against a 30 bar, so it is under the bar only where the GPU
  load passes 33 ms.

## Step 3b: DOA3 (1-1791212838-lane.belowbar1005-2132217, 09:53-10:02 PDT)

Same perflog apk (63abb775f234, cache kept from the NGB run), regimen default,
shipped wait, `HAKUX_OCCL_LOG=120` (`config log=1 after_s=120 wait=1`).
Route `routes/bb-doa3.route` (retro-doa3's 15 steps, then the attack loop)
reached a Story fight at the mark (09:56:24), but the loop lost it: from
~09:58 the frames are the title attract (`PRESS START BUTTON` over stage
flyovers: 095816 the forest, 100120 the red-and-gold dojo with the lacquered
floor). A route defect (the loop has no START for the continue screen), not a
measurement defect: the attract renders the same stages with the same engine.
Verdict on the window: 323 s, fps_ok_share 0.59.

**DOA3 reads no occlusion queries.** No `[occl804] f=` line in 360 s of
logged time (fight and attract). The wait never runs, as on Buffy.

**Bound on the slow stage: the GPU, with one synchronous surface download
per flip.** hakuX-phase medians by window:

| window (s after mark) | scene | GPU ms/frame | render | non-render | finish | sd finishes per flip |
|---|---|---|---|---|---|---|
| 0-60 | Story fight | 26.4 | 14.0 | 11.6 | 12.0 | 0 |
| 60-120 | fight / continue | 21.0 | 10.3 | 10.6 | 2.6 | 0 |
| 120-150 | attract | 42.4 | 20.9 | 21.1 | 6.4 | 0 |
| 150-270 | attract (forest etc.) | 15.1 | 8.2 | 7.6 | 0.7 | 0 |
| **270-330** | **attract, the dojo (FPS 19)** | **58.7** | **33.2** | **25.5** | **30.3** | **1** (`sd60 dirtyIf60` per 2 s) |

The dojo is the stage retro-doa3 spent t = 150-560 s on at 18-20 fps (the
Bass fight, route frame 204919). There the GPU alone needs ~58 ms per frame:
33 ms in render passes (the lacquered floor's reflection draws the scene
twice) and 25 ms outside them (9.4 surface uploads per frame, `#upl:562`
per 60). On top of that one download-if-dirty per flip ends in a synchronous
`SURFACE_DOWN` finish (#794's class, the dirtyIf branch; async794's folded
form, 2344ae1ee2, releases pgraph.lock across the deferred-download wait and
leaves the download synchronous), so the render thread waits 30 ms per frame in Fin (Sub 30.0).
Even with the download asynchronous the GPU's 58 ms is past 50 ms (three
VBLANKs): DOA3 on that stage is GPU-bound first.

## Cross-title: GPU time outside render passes (`xfrsurvey.py`, offline)

NG Black's and DOA3's GPU frames are half non-render time, so every perflog
soak of the last 14 days was ranked by it (`xfrsurvey.tsv`, fixed-width; medians of the
`xemu-gpu` lines with Tot >= 8 ms, so menus drop out; whole logcats, a
ranking, not a verdict). Xfr is `gpu_nonrender_ms`: the command buffer's
GPU span (`cb_end - cb_start` timestamps) minus the timestamped spans of its
render passes (vk/draw.c 3689-3726). So it is copies, uploads, blits,
conversions, clears and barriers between passes, plus any pass beyond
`GPU_TS_MAX_RENDER_PASSES`.

| title | Tot | Rnd | **Xfr** | Xfr/Tot | RP per frame |
|---|---|---|---|---|---|
| ToeJam & Earl III | 52.3 | 34.4 | **17.9** | 0.34 | 17 |
| 007 Agent Under Fire | 28.8 | 18.1 | **14.5** | 0.50 | 4 |
| DOA Ultimate | 31.6 | 19.1 | **13.2** | 0.42 | 9 |
| NG Black | 23.9 | 12.2 | **11.7** | 0.49 | 12 |
| Otogi | 22.4 | 11.0 | **11.4** | 0.51 | 2 |
| DOA3 (whole run; the dojo alone 25.5) | 18.4 | 10.2 | **10.3** | 0.56 | 3 |
| Crash Twinsanity | 18.3 | 10.3 | 7.1 | 0.39 | 15 |
| Halo 2 | 14.3 | 8.2 | 6.3 | 0.44 | 25 |
| Black | 11.2 | 5.8 | 5.5 | 0.49 | 19 |
| ... Blinx, Burnout, PGR, BF2, Counter-Strike, NBA 2005 | 18-42 | | 0.2-1.3 | 0.00-0.07 | |

It does not track the render-pass count (Otogi 2 passes and 11.4 ms; Top Spin
149 passes and 4.5 ms), so it is not the per-pass tile load/store. What it is
inside is not measured anywhere yet: no timestamp brackets the uploads,
copies or conversions. In the NGB and DOA3 windows the co-measured counters
are ~8-9 `pgraph_vk_upload_surface_data` calls per frame (`xemu-surf #upl`;
a call can be a no-op, `[surf413]` counts the real ones) and 9
surface-to-texture binds (`S2T:9`, NGB).

## Answer

**The #804 fence wait is not the cost, for any of the three.**

| title | below-bar run had the wait? | reads occlusion queries? | does the wait block? |
|---|---|---|---|
| Buffy | no (39fc5d0a57) | **no** (0 lines, both arms, 210+ s of play) | never runs |
| NG Black | no (39fc5d0a57) | yes, in ~4% of frames (q 1-3) | **no**: pend = 0 on all 190 reads |
| DOA3 | yes (5e16698c99) | **no** (0 lines, 360 s) | never runs |

The registered share rule fired on Buffy (0.83 vs 0.67) with the code under
test not executing in either arm; that gap is the walk (see "Arm W"). No fix
proposal for the wait is warranted by these titles. The one place it can
cost is a title whose queries are read while a submitted frame is still on
the GPU (`pend > 0`), which is RalliSport's case, the one it was written for.

Per title, the bound and the next step by P x win:

| title | bound (evidence) | next step | P | win |
|---|---|---|---|---|
| **NG Black** | **GPU**: F = GPU + ~4 ms in every bucket; GPU at 680 MHz (max) in 7 of 8 play samples; Ri < 1.5; no sd finishes; half the GPU time non-render (11.7 of 23.9) | Measure what the non-render GPU time is: timestamps around surface uploads, texture uploads, surface-to-texture copies and conversions in the perflog build (a decide-first measurement), then cut the largest | 0.4 that one category holds most of it and is avoidable (redundant uploads/conversions), on the evidence that the titles at the top share engines and the bottom half of the table has ~0 | NG Black: slow rows 32.6 ms GPU -> ~22-27, so 28.5+ in most windows; the same fix reaches AUF, DOA Ultimate, Otogi, DOA3, ToeJam (5-18 ms each) |
| **DOA3** | **GPU** on the dojo stage: 58.7 ms (render 33.2, non-render 25.5), plus one synchronous download-if-dirty per flip (Fin 30 ms). Other stages 15-26 ms GPU, 35-50 fps | Same non-render measurement (shared). Then #794's dirtyIf download made asynchronous | 0.2 that the dojo reaches 28.5 even with both: its render passes alone are 33 ms | One stage of DOA3; the rest already passes |
| **Buffy** | **vCPU**: guest busy 27-31 ms of 37-38 in slow rows, renderer idle 15-24 ms, GPU clock mostly 401-550 MHz (not GPU-bound); vCPU asleep 6-12 ms per frame in the slow rows | Perflog split of that sleep (queued: 1-1791217580); if it is pgraph.lock, the #474 extension; otherwise the vCPU JIT direction (owner 09-28) | see below | Buffy misses 33.3 ms by 4-8 ms on the forest path |
