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
