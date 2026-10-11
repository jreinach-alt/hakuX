coldstart1010: NFS Most Wanted's first race start after loading, census and largest fix (#433, 0.5)
State: ready

Lane: coldstart1010     Issue: #433 (umbrella), none filed
Base: master @ 9dc20e31f9
Files: hw/xbox/nv2a/pgraph/vk/draw.c, docs/lanes/coldstart1010/**, docs/testing/predictions/coldstart1010-*.json
Prediction: docs/testing/predictions/coldstart1010-depth.json @ 37d06242945828fafab2f2fd7c270ef83c05d979a6257fb45239b72be60dffad
Prediction: docs/testing/predictions/coldstart1010-stack.json @ 4e025db7f7938c627792af7c291ee68c19564b415c255c8c429e027c8bbf60c5
Needs device: yes (Nova)
Needs NDK: yes

Step 1 is a census of NFS MW's cold race start 1 against the warm countdown: the PFIFO thread's ms per frame
split by cause, with GPU busy, render passes per frame and vCPU busy. Step 2 prices the remedies by probability
x win, builds the top one behind a default-off switch and A/Bs it.

**Census** (NOTES sections 1-3 and 6). All six switches are on. At depth 2, cold start 1 runs 37.9 ms against
33.75 warm, in the plain A arms.
- The renderer's share is the guest's wait for pfifo.lock (lockw): 9.0 ms a frame cold.
- Behind that wait is the submit ring. On the Nova it is 2 deep: the Android native pref default is 2, while the
  settings screen shows 3. Every finish's slot rotation waits for the command buffer submitted one finish earlier,
  with pfifo.lock held (`p_c_rep` 6.1 ms a frame cold).
- The cold start's 2.6x render passes are the first race's rain: `srf` breaks with surface-to-texture copies,
  57 against 15 a frame. No pipeline is created, no texture is uploaded and no surface is created. The guest's
  own cold work is +4-5 ms, and that is the scene, not the renderer.

**Built:** `HAKUX_SUBMIT_FRAMES=N` (draw.c, `xemu_set_submit_frames`). It overrides the command-buffer ring depth
over the `submit_frames` pref, up to `NUM_SUBMIT_FRAMES` (3). When unset, it changes nothing.

**Verdicts.** 3 runs per arm, plain build, ref 786f82d4bb. Each A/B had one void run, rerun once with its cause
named in NOTES.

| A/B | A | B | cold 1, A -> B | K (<= 34.5) | C | W (warm) | G (post-GO) | M (ms blocked in rotation) |
|---|---|---|---|---|---|---|---|---|
| `coldstart1010-depth.json` | six switches, depth 2 | + depth 3 | 37.93 -> 36.42 (-1.51) | FAIL | PASS | -0.12 PASS | -0.01 PASS | 2.91 -> 0.92 PASS |
| `coldstart1010-stack.json` | + posted store, depth 2 | + posted store, depth 3 | 36.28 -> 34.79 (-1.49) | FAIL by 0.29 | PASS | -0.01 PASS | -0.00 PASS | 2.66 -> 0.20 PASS |

| configuration | cold 1 | change |
|---|---|---|
| six switches | 37.93 | |
| + depth 3 | 36.42 | -1.51 |
| + posted store (`HAKUX_POSTED_PUT=1`) | 36.28 | -1.65 |
| + both | **34.79** | **-3.14** |

Warm and post-GO do not move in any configuration: 33.6-33.75 and 33.4. Depth changes only which slot a finish
records into, not what any draw draws, so there is no pixel leg.

**What is left** (NOTES section 9, two frametrace runs of the stacked configuration):
- The PFIFO thread runs past 2 VBLANKs on 0-1 % of cold frames, and the GPU is busy 10.8 of 33.3 ms. The renderer
  no longer paces the cold frame.
- The guest still waits 2.2-2.35 ms a frame for pfifo.lock, against 0.7-0.8 warm. That wait puts 24-27 % of cold
  frames past 2 VBLANKs; without it, 4-5 % would be.
- It is counted in only two places: `pfifo_post_kick`, which takes the lock to wake a parked PFIFO thread, and
  `user_write`'s locked branch for USER stores other than DMA_PUT. Both are in pfifo.c and user.c, which are not
  this lane's files.

**Ranked next step** (NOTES section 10):
1. Make the two measured remedies the defaults: native `submit_frames` 2 -> 3 at `xemu_android.cpp:1188`
   (fastpaths1010's file), and the posted store on (postput1010's switch). E is 1.35 + 1.5 ms. Together they
   measured -3.14 ms.
2. A pfifo.c/user.c lane. It first separates the two lockw sites and books their holder, which is cheap and
   decides which site to fix. Then it builds a wake that does not take pfifo.lock (E ~0.5 ms; cold start 1 to
   about 33.6-33.9).

Release note (none): opt-in switch HAKUX_SUBMIT_FRAMES, off by default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
