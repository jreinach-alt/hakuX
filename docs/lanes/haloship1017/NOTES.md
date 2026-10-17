# lane.haloship1017 -- Halo CE: the ship's rear lights show through the hull after the cut to the front (#1039)

Opening cinematic, The Pillar of Autumn (4D530004). Owner, 10-17: behind the ship its rear lights show (correct);
after the cut to the front they show through the hull; an original Xbox does not. Not game-blocking, same class
as #939. Branched from master @ 8d260f39fc.

## Status

Step 0 done (this file, before any code). Desktop input works (r2), the cut is located (r2), the light tests
are identified and count 0 in the steady front shot (r2, r3). **r4b (attempt 2) reproduces it on the desktop and
locates it:** the rear lights are lens flares drawn with the depth test OFF, and the second frame after the cut
(f42) draws all 12 of them at alpha 0.18-0.20, because the first front frame's tests (f41, own count 0) were
answered with the behind shot's counts (12/730) by `HAKUX_REPORT_EARLY`. See "r4b" below.

**r5 and the disassembly (attempt 2, 13:40 PDT):**
- Legs e0 (`HAKUX_REPORT_EARLY=0`, 0.5.1-rc1's report config) and a0 (`HAKUX_REPORT_ASYNC=0`) are both clean
  across the cut, with no rear flare in any front frame.
- Halo's flare read waits for every result, with no timeout, so a late count can never carry over.
- On Turnip-class drivers, the 0.5.2 defect is EARLY's, and only EARLY's.
- The owner's two sightings (0.5.1-rc1 on 10-16, 0.5.2-rc1 on 10-17) were in the release app,
  `com.jreinach.hakux`. bindpose1017 (#1043, folded 9abd80e90c) showed that this app has never had a custom
  driver, so both ran on the **stock Qualcomm driver**, which the owner's 10-17 rule says is never used or tested.
  See "The 0.5.1-rc1 sighting" below.
- Next: Nova legs N0 and N1 on Turnip, and the remedy for EARLY at a cut, ranked below.

**Why attempt 1 did not finish (12:08 PDT):** the 300-turn cap. It spent its turns on Step 0, the instrument,
three desktop runs and many single-command polls, and the cap fell 40 s into r4 (route.log ends at
`002_boot40`; systemd's SIGTERM at session end killed qemu). Everything before r4 was committed and pushed. r4 is
rerun from the start in attempt 2, with fewer, larger steps: one detached run, one blocking wait per run.

r2's shots place the behind shot by guest frame (`nv2a_frame`, luma >= 240 fraction): 4175 dark, **4188-4256
bright (0.052-0.081)** except 4231 (0.0000, one shot: noted, read in r4), 4266 onward 0.0000. So the behind shot
is ~80 guest frames and the cut lies between 4256 and 4266.

## Step 0: what was searched

- `git log --all -S` and `--grep` for: GET_REPORT, CLEAR_REPORT_VALUE, SET_ZPASS_PIXEL_COUNT_ENABLE, zpass/ZPASS,
  occlusion, REPORT_ASYNC, REPORT_EARLY/rearly, REPORT_TRACE/rtrace, zeta, depth clear, w-buffer, zmin/zmax/depth
  range/clamp, lens flare/flare/corona, halo (top 60), query pool/vkCmdBeginQuery/VK_QUERY_TYPE_OCCLUSION/PRECISE,
  surface reload.
- Tracker: `git show origin/board:nv2a_issues.toml` rows 1039, 939, 1018, 1038, 938, 737-739, 994, 527, 535, 804,
  76, 276, 272, 989. No row mentions a flare or corona.
- Lane notes read in full or in their report/depth sections: reportasync1010, halo1016 (reports sections, R1-R8,
  "should not repeat" :809-823), defaulton1017 (verdict table :92-114, `vis` :352-357), accuracy804 :40-94 and
  :493-577, cloud-527 (git 4e7ec92a67), notify488 :49-79, x1port1012 (gd, #939).
- Docs: `docs/releases/v0.5.2.md:13-16`, `dispatch/board-requests/xbox.md:332, 381, 400-436`,
  `docs/lanes/xbox/OUTBOX.md:3-29`, `docs/testing/desktop-runs.md`.
- Code: `hw/xbox/nv2a/pgraph/vk/reports.c` (whole report path), `vk/draw.c` begin_query/end_query/begin_draw
  (:3941-3974, :7170-7201), `vk/instance.c:892`, `pgraph.c:4456-4466` and `pgraph_write_zpass_pixel_cnt_report`.
- `MainActivity.kt:38-42` FASTPATHS_VARS: REPORT_ASYNC, TEXSCAN, DRAWREC, UNI_BULK, UNI_UBERCACHE, UNI_FOGCACHE,
  POSTED_PUT, LOCKFREE_WAKE, all "1" while the `fastpaths` pref is on (default true). Also default-on: SURFGPU=1,
  GPL=3. C defaults in 0.5.2: S2T_CVT, REPORT_EARLY (needs ASYNC), FLDCW_CHAIN, FIST_ROUND on; IBC off. Prefs
  off by default: skip_occlusion_queries, fast_fences, draw_reorder, frame_skip.

**Found: no prior work on this defect.** No commit, tracker row or notes section covers geometry or lights
showing through a hull in Halo. The nearest mechanism on record is REPORT_EARLY's predicted cost (a flare one
frame late at a cut), which nobody captured.

## Already tried

| approach | where (commit, lane, NOTES line) | verdict | what it means here |
|---|---|---|---|
| A1. Async report reader (`HAKUX_REPORT_ASYNC`), armed gate | 2e9f535300, 477893cdbf, fold 6052ff98d4; reportasync1010 NOTES :20-21, :92, :294, :798 | ZPass 72/72 byte-identical; "a frame later, never a wrong count"; default-on via fastpaths | Halo spins on the status word (halo1016 :590-594), so ASYNC hands it the exact count, late. ASYNC alone cannot give Halo a wrong count. It was on in 0.5.1-rc1 |
| A2. Early answer (`HAKUX_REPORT_EARLY`, R8), gap==1 gate, stale/vis counters | 08fd920b5c (fold 15f8524be1), 7f6b99db87 (fold c3660fdd86); halo1016 :668-688, :764-766, :800, :821; defaulton1017 :92-114, :352-357 | shipped default-on in 0.5.2 only; Halo HVIS 0.0055; its cost (flare one frame stale at a cut) predicted, **never captured** | the only recorded mechanism that shows a hidden light. It is not in 0.5.1-rc1, so it explains the sighting only if the build was 0.5.2-rc1 (tracker #1018 says the owner played 0.5.2-rc1 on 10-17). At most a frame or two per cut |
| A3. Report CATCHUP (R5) / SUBMIT (R7) | 7da5534b6b, 08fd920b5c; halo1016 :220-221, :237, :748-755, :786, :823 | measured, lose (fps). Off | timing only, off by default: not in the shipped path. Not rerun |
| A4. #804 stale query read: wait on fences (`HAKUX_OCCL_WAIT`, default 1) | 3ad43b49da, ee8999c296, 510ebb25f2, 5e16698c99 (fold 6f463a0ae2); accuracy804 :43-84, :493-507, :565-577 | folded; fixed RalliSport's alternate-frame bodies | Turnip's reset is a GPU command, so an early read returned the last cb's count. Fixed on the sync path; ASYNC waits on the fence by construction. `HAKUX_OCCL_WAIT=0` would reinstate it (a mutant, not a remedy) |
| A5. Reports written after the report DMA is rebound (#527) | 9e19e81a05 (lane/cloud-527, PR #535 closed 10-12, never folded); cloud-527 NOTES | never landed; #527 orphaned. **Counter correctness unsettled**: ZPass's first report read 40,960 (right), 49,152 (0026f00534), and 65,536 on the Thor with sysmem and a kept cache, which is the depth-hidden quad counted | the only record of a handheld counting fragments that the depth test should have rejected. Directly relevant to H2 below |
| A6. Query creation, PRECISE flag | upstream a5385803db, 80fda910b1, d47fef9467; hakuX: none | never changed | PRECISE only when `occlusionQueryPrecise` is offered (instance.c:892). Non-precise may inflate a nonzero count, never turn 0 into nonzero, so it cannot by itself show a fully hidden light |
| A7. Skip occlusion queries (pref) | upstream 41586e3025; draw.c:7177-7201 | off by default | with it on the count is never written (0 or last). A discriminator here: lights gated by tests disappear or freeze; ordinary geometry is unaffected |
| A8. Depth value fixes: D24 saturate, w-buffer slope offset, float depth encoding, F24 one unit high | c2336637cf (#266), bdc26fa5c8, 23a8962df2, c59ad280fd | folded | depth precision at the far end. A wrong depth here would show as z-fighting, not a whole light through a whole hull. Low prior for H5 |
| A9. CULL_NEAR_FAR_EN / ZMinMax, zclamp | ed8e1cd3be, bf23a7f1ce (#276, PR #368), 2dc5d1b884 | folded, verification pending | a test quad clamped instead of clipped could pass. Relevant to H5 and to the test draw's own depth under H3 |
| A10. `HAKUX_ZETA_D24` | ede7c891c5 (fpsbelow1012), surface.c:6685-6726 | off by default | not in the shipped path |
| A11. Depth clear fixes | 51721e36aa (#414), cde230bf1d (#91), b991fb4c21 | folded | a cleared or reloaded zeta at the test is H3; these fixed specific clears, none in Halo |
| A12. Zeta/colour role swaps of one 640x480 surface | halo1016 census (60 Z<->C swaps, f130 <-> f44, pitch 2560, handed off on the GPU) | observed, never judged | a candidate H3 mechanism: the test runs against a surface that held colour, or a zeta reloaded from guest memory without the hull |
| A13. X1 BOX report path | halo1016 | = upstream's synchronous path | not to be ported |

## Symptoms and their accounts (filled as measured)

1. Behind the ship the rear lights show. Correct. **Account (r4b):** they are lens flares, 12 depth-test-off
   quads a frame whose brightness the CPU sets from each light's pixel-count test (0x60200-0x602b0, 4-182
   samples each from behind).
2. After the cut to the front, the lights show through the hull; hardware does not. **Account (desktop, 0.5.2
   defaults):** the first front frame's tests are answered with the behind shot's counts (EARLY), so the next
   frame draws all 12 flares, depth test off, through the hull.
   **0.5.1-rc1 (no EARLY):** the code gives the guest its own counts. e0 shows 0 from the front, and the guest
   waits for each count (the disassembly). So the flares through the hull need a host count that is nonzero from
   the front. Neither desktop nor Turnip-class code produces one. The owner's sighting ran on the stock Qualcomm
   driver (below), the one GPU-side difference left. The stock mechanism itself is not measured, and under the
   owner's rule it will not be. N0 checks the code on Turnip.
3. How many frames it lasts. **Desktop, 0.5.2 defaults: one frame** (f42, the second after the cut), alpha
   0.18-0.20 against 0.53-0.79 behind. The length is fixed by the guest, not by timing. An early answer is always
   exactly one frame old, and the next frame's answer (0) turns the flare off at once. So on a device it is one
   frame per cut too.
4. Desktop: **yes**, as that one frame, in the draw records. Not in the dumped images (the frame that would show
   it has none), which is why r2-r4b's pictures looked clean.
5. Fast paths off: **clean on the desktop** (a0, `HAKUX_REPORT_ASYNC=0`, which also turns EARLY off). The 12
   rear tests count 0 from the first front frame on, and no rear flare is drawn after the cut.

## Hypotheses

The rear lights are most likely Halo lens flares: Halo tests a light's visibility with a pixel count (544 armed
GET_REPORTs a frame in this cinematic, polled about a frame later, halo1016 :590-599) and draws the flare with no
depth test when the count is nonzero. Every L1 case is "the count is nonzero from the front".

| # | hypothesis | Already-tried row | P | hit (instrument) | miss |
|---|---|---|---|---|---|
| H1 | L1(a): a stale count at the cut. EARLY answers the front shot's first test with the behind shot's count | A2 | 0.20 | defect lasts 1-2 frames after the cut; gone with `HAKUX_REPORT_EARLY=0`; per-offset trace shows the early answer nonzero and its own count 0 | lasts the whole shot, or shows with EARLY=0, or on a build with no EARLY |
| H2 | L1(c): the host GPU counts samples that fail the depth test (Adreno LRZ/GMEM/binning, or a query span that takes in other draws) | A5 (Thor counted the hidden quad), A6 | 0.20 | Nova shows it, desktop does not; per-offset count nonzero on the Nova for the light's tests in the front shot where the desktop's is 0 | desktop shows it too (then H3/H4/H5) |
| H3 | L1(b): the test draws against a zeta that lacks the hull: wrong surface bound, cleared, reloaded, or a Z<->C role swap | A11, A12 | 0.20 | gd dump of the front shot: at the test draws the bound zeta is not the surface the hull wrote, or was cleared/uploaded between hull and test | test draws bound to the hull's zeta with its depth intact |
| H4 | L1(d): the counter's span or reset differs from the NV2A: CLEAR_REPORT_VALUE position, a query left open across draws with zpass off, the running sum | A1, A5 | 0.10 | per-report trace: a light's count equals hull + test, or carries across a clear | each count equals the test draw's own passing samples |
| H5 | L2: the lights are ordinary geometry and their depth test does not reject them (depth values, range, clamp, clip) | A8, A9, A10 | 0.20 | lights still show through with queries skipped (A7); gd shows the light's draws with depth test on and passing where the hull is nearer | lights vanish or freeze with queries skipped |
| H6 | L3: the aarch64 JIT computes the guest's visibility decision differently | new: searched FIST/FLDCW commits (#939 5d4b689ed9, 56fdef2c85), nothing on visibility | 0.05 | Nova shows, desktop does not, with identical per-offset counts | counts differ (then H2) |
| H7 | L4: draw order or blend | new: searched draw reorder (off by default, refused while zpass is on, draw.c:9433), nothing | 0.05 | gd: the light drawn after the hull with blend over it, no depth involved | |

**Build question: answered from the owner's own save.** The owner's 10-16 Halo states
(`captures/owner-halo-1016/states/4d530004/slot0`) carry build 2636e89f4a, and
`git merge-base --is-ancestor 15f8524be1 2636e89f4a` exits 1: the EARLY fold is not in it. The owner, 10-17
~11:55 PDT (via lane.xbox, brief ADDENDUM 1): "The lighting issue was present in both builds." The sighting was on
a build with ASYNC (exact count, a frame late, Halo spins until it lands) and no EARLY. So **H1 cannot be the
origin** (P 0.20 -> 0.03, kept only as "EARLY may lengthen it in 0.5.2", which the EARLY=0 leg measures). Its
weight goes to H2-H5, and H8 joins:

| # | hypothesis | P | hit | miss |
|---|---|---|---|---|
| H8 | a draw that writes the hull's depth is skipped on the host at the cut (pipeline or shader still compiling: `{"t":"skip"}` in gd), so the tests pass where the hull should be | 0.10 | skip records for hull-like draws in the first frames after the cut, defect lasts until they compile | no skips across the cut |

Re-ranked: H3 0.25, H2 0.20, H5 0.20, H4 0.12, H8 0.10, H6 0.05, H7 0.05, H1 0.03.

**Re-ranked on r4b (attempt 2).** The flares are drawn with the depth test off and the host's own counts are
right, so every GPU-side hypothesis lost its hit on the desktop: H3 0.25 -> 0.04, H5 0.20 -> 0.02 (the light
draws are not depth-tested at all), H4 0.12 -> 0.02, H8 0.10 -> 0.02 (no skips), H7 0.05 -> 0.02. The defect is
the guest being given a count that is not its own test's. Two ways to that, one per build:

| # | hypothesis | P | hit | miss |
|---|---|---|---|---|
| H1 | (0.5.2) EARLY answers the first front frame's tests with the behind counts | **0.95 for 0.5.2 on the desktop** (seen: f41 given 12/730, own 0/0; f42 draws the 12) | e0 leg: no rear flare in any front frame | e0 still draws them |
| H9 | (0.5.1-rc1, no EARLY) the flare code does not wait for its result: on "not ready" (0x88760828) it keeps the last answer, and ASYNC's write (16-33 ms after queue, halo1016 RT) is not there yet when a fast guest reads it, so the behind counts carry over the cut the same way | 0.45 | disassembly: the flare caller of 0x1810f0 does not spin; e0 on the desktop clean (slow guest, results land first) | the flare caller spins until ready (then ASYNC gives it the exact 0) |
| H2 | (Nova) Adreno counts the hidden test quad (A5's Thor record) | 0.15 | Nova per-offset counts nonzero in the front shot | Nova counts 0 there (the 21 halo1016 front frames are clean, which already leans against a whole-shot H2) |
| H6 | (Nova) the aarch64 JIT decides differently | 0.03 | | |

## Instrument (#1039, committed before its data)

Frame dump schema 10 (`vk/renderer.c`): each draw record gets `"zq"` (serial of the occlusion query it was
counted in, -1 none) and `"zp"` (the guest's ZPASS enable); each GET_REPORT/CLEAR_REPORT_VALUE writes
`{"t":"rep","f","n","rs","qs","clr","off","zq"}`. `HAKUX_ZREP=<path>[,<MB>]` (`vk/reports.c`) writes, from
whichever path reads the queries (async reader or sync finish), `q <serial> <samples>` per query and
`r <rs> <qs> <off> <value> <early>` / `c <rs> <qs>` per report, starting at the first dump armed. Joined on
the serials, one dump says for every report which draws it counted (with their depth state, zeta address and
colour target) and what it came to. Desktop input with no window: `HAKUX_PAD_FILE=<path>` (`ui/xemu-input.c`)
presses the button a file names, as pad.sh does on a device. All off unless set.

## Plan, by P x win

The win is the same for every hypothesis (the defect gone, no fps cost), so the order is P and what each step
decides:

1. Desktop reproduction, every frame across the cut (`gd` frame dumps + `HAKUX_REPORT_TRACE=1`). Decides H2/H6
   against the rest (symptom 4) and counts frames (symptom 3, H1 vs the rest).
2. A per-report instrument: for each GET_REPORT, its offset, guest frame, count, and the draws its query spanned
   (gd draw index, depth test/func/write, bound zeta address). Decides H3/H4/H5 in one dump of the front shot.
3. Legs on the desktop, same input: EARLY=0, ASYNC=0, queries skipped. Nova legs queued to run when the owner
   frees it.

## Desktop runs

All runs: `docs/lanes/haloship1017/desk_route.py`, llvmpipe Vulkan, `-display none`, keyboard on port 1, the Nova
titles disk copy (`titles-nova-e0446ac3006f`) as the HDD, the 0.5.2 fast-path defaults. Output in
`build-linux/run/<run>/` (not committed: frames are large).

| run | head | what | result |
|---|---|---|---|
| r1 | 084e5e266b + route runner | route to the profile screen, gated | boot reached the main menu (CAMPAIGN lit) in ~60-120 s. **START never reached the guest**: no `[pad1039]` line, pad file never read. Cause: with `-display none`, `sdl2_display_init` never runs, so the main thread waits on `display_init_sem` for good and `xemu_input_init` never binds a controller. Fix: `ui/xemu.c` binds input from a machine-ready notifier when `HAKUX_PAD_FILE` is set. Also the runner globbed `*.json` for `*.jsonl`, so every shot timed out (files were still moved). No crash |
| r2 | 1d1f39671b (input fix) | route to the cinematic (gates at menu and profile: existing profile New001 selected, none created), then one frame every 2 s for 200 s, `--zrep` | input works. Loading ~90 s, cinematic from mark+~98 s. **The cut is between shot 081 (mark+166 s, nv2a_frame 4256, behind: engines lit) and 082 (mark+170 s, frame 4266, front).** ~6 guest frames/s on llvmpipe. Front-view shots 082-098 (one frame per 2 s, 30 s) show no rear light through the hull. No crash |

**The light tests (r2, `vistests.py`, shots 081 and 082).** Halo tests each light with its own report:
CLEAR_REPORT_VALUE, one 4-vertex quad (`inline_buffer`, prim 7) with depth test LEQUAL, colour writes off
(`cm0`), against the main zeta 0x2198000 (the hull's), then GET_REPORT, at offsets 0x60000 + 16 k. 44-45 tests a
frame, all after the scene (draws 92-135 behind, 114-158 front). One query per test (`nq 1`), so the count is
the quad's own passing samples: no span or carry (H4's "count = hull + test" is not what happens here).

| shot | view | tests | nonzero | values |
|---|---|---|---|---|
| 081 | behind | 44 | 12 | pairs: 182,182 and 169,169 (the engines), 9,9 / 6,6 / 9,9 / 6,6 (the four small lights) |
| 082 | front | 45 | 2 | 2 and 4 samples (0x600f0, 0x601f0); the other 43 are 0 |

So on the desktop, in the steady front shot, the hidden lights count 0 (or a few edge samples), which is right.
Symptom 4 is "no" for the steady shot; the frames right after the cut were not in r2 (one frame per 2 s).

| run | head | what | result |
|---|---|---|---|
| r3 | 1d1f39671b build | every frame from mark+140 s (300 frames, `gd`, `--zrep`) | **missed the cut**: frame 0 is already the front shot, closer in than r2's last shot 098. The load ran 30-40 s faster than r2's, so mark+140 s here is past r2's mark+170 s content. Aiming by the clock is the mistake the brief names; r4 arms by content (`--on-bright`). What r3 does show (`perframe.py`, 300 frames): **no `{"t":"skip"}` record in any frame**; every frame's light tests run after 59-101 depth-writing draws on the tests' zeta; in the front shot 2-9 of 42-46 tests are nonzero at 1-6 samples each (edge samples) until the camera reaches the bridge window (f170+, sums to 76 at 0x600f0/0x601f0: lights in view there). No crash; C: 57 GB |

**The Nova's own route-frames** (halo1016 request `0-0-x-1792231793-halo1016-2208576`, the kept route on
a warm shader cache) show the front shot (frame 032100, ~mark+30 s past the cut) with no glow through the hull.
So on the Nova as well the steady front shot is clean, and the owner's sighting is in the frames just after the
cut, or on a different cache or settings state from that run's.

**H8 on the default path.** `async_compile` is off by default (`SettingsActivity.kt:69`, C default
`draw.c:35`), and with it off the PFIFO thread compiles a missing pipeline before the draw instead of skipping it
(`draw.c:3049`, `shaders.c:1362`). So a default build skips a draw only with no pipeline at all (cache exhausted,
`draws_skipped_no_pipeline`). r3 saw none. H8 stays live only for a player with async compile on, or a pipeline
creation that fails; the owner's settings are not known.

| run | head | what | result |
|---|---|---|---|
| r4 | 1d1f39671b build | as r4b | killed at boot by attempt 1's session end (turn cap) |
| r4b | 1d1f39671b build (no emulator change since) | `desk_route.py --on-bright 0.045 300,images,gd,cap3000 --every 2 --cine 900 --zrep`, 0.5.2 defaults (ASYNC + EARLY on) | the trigger fired at mark+75.6 s (bright 0.0803, the behind shot); 300 frames f0-f299, nv2a 2136-2435. **The cut is f40 -> f41 (nv2a 2176 -> 2177).** No `{"t":"skip"}` in any frame. No crash; C: 57 GB |

### r4b: the rear lights are flares, and the stale answer draws them one frame through the hull

**The flare draws** (`drawlist.py`, `flares.py`, f40 against f42). After the 44 light tests and the scene's
`zon:eq` passes, each frame draws its flares as `inline_buffer` quads (prim 7, count 4) of shader 7d6aedad
(texture 8d84860d) with the **depth test off** (`zOFF:le`, blend 0x14a = ADD, src alpha, one), then two
full-width quads of a5aae408. The dump has no inline vertex data, but gd's `va` (each attribute's inline value,
replayed) is the quad's last vertex: screen position (attr 0) and a colour whose alpha is the brightness
(attr 9). Behind (f30-f40), 12 quads: 8 of colour (0.369,0.886,1) and 4 of (0.259,0.478,1), alpha 0.53-0.79,
positions (345-459, 262-368) -- the engines and the four small lights. So **nothing on the GPU can hide a flare**:
the CPU draws it or not, at a brightness it computes from the light's test.

**Every frame across the cut** (`cutflare.py`: the 12 rear tests' own counts, what the guest was given, the
frame's 7d6aedad quads):

| f | nv2a | view | rear tests: own count nz/sum | answered early | guest given nz/sum | flare quads drawn |
|---|---|---|---|---|---|---|
| 38 | 2174 | behind | 12/751 | 12 | 12/726 | 12 rear, a 0.68-0.75 |
| 39 | 2175 | behind | 12/730 | 12 | 12/751 | 12 rear, a 0.71-0.76 |
| 40 | 2176 | behind | 12/730 | 12 | 12/730 | 12 rear, a 0.53-0.76 |
| **41** | 2177 | front | **0/0** | 12 | **12/730** | none |
| **42** | 2178 | front | 0/0 | 12 | 0/0 | **12 rear, a 0.196 (8) and 0.184 (4), at (208-291, 265-336): behind the hull, depth test off** |
| 43 | 2179 | front | 0/0 | 12 | 0/0 | 1 other light, colour (0.42,0.45,0.29), a 0.012 |
| 44-70 | 2180-2206 | front | 0/0 | 12 | 0/0 | that one light, a 0.02-0.06, ramping |

Read: the guest draws a frame's flares from the previous frame's test answers (f42's flares from f41's
answers), resets them at the cut (f41 draws none), and drops a flare at once when its answer is 0 (f43). The
first front frame's tests are hidden behind the hull and count 0 on the host (right), but EARLY answered them
with the offset's last count, the behind shot's 730. So f42 draws the 12 rear flares at ~50/255 through the hull,
for exactly one frame. On the NV2A the report is written when the GPU reaches GET_REPORT, so f41's answer is 0
and f42 draws nothing.

The images cannot show this frame: f42's draws appear in the next image (the dump's images lag one frame here,
f40 and f41's images are byte-identical), and f43 has no image (`img_sync` -2, stale). The draw records are the
judge: a rear flare quad in a front frame is the defect, whatever a picture shows.

**What this rules out on the desktop.** The tests' own counts are right in every frame (0 from the front, from
f41 on, against the hull's zeta, after 85-109 depth-writing draws): H2 (host counts failing samples), H3 (zeta
without the hull), H4 (span/reset) and H5 (depth test on the light) have no hit. H8: no skips. What is left is
which answer the guest gets, and when.

### r5: the same cut with EARLY off (e0) and with the async reader off (a0)

`legs.sh build-linux/run/r5 e0=HAKUX_REPORT_EARLY=0 a0=HAKUX_REPORT_ASYNC=0` (r4b's recipe: aim by the glow,
300 frames, gd, zrep). Same build. `cutflare.py` over each cut:

| leg | f | nv2a | view | rear tests: own nz/sum | answered early | guest given nz/sum | flare quads drawn |
|---|---|---|---|---|---|---|---|
| e0 | 53-56 | 2069-2072 | behind | 12/726-743 | 0 | = own | 12 rear, a 0.74-0.79 |
| e0 | **57** | 2073 | front | 0/0 | 0 | **0/0** | none |
| e0 | 58-62 | 2074-2078 | front | 0/0 | 0 | 0/0 | 1 other light (0.42,0.45,0.29), a 0.012-0.031 |
| a0 | 62 / **63** / 64+ | 2093 / 2094 / 2095+ | behind / front / front | 12 / 0 / 0 | 0 | = own | rear / none / the one other light |

Both are clean: the first front frame's answers are its own zeros, and no rear flare is drawn in any front frame.
So on the desktop the defect is EARLY and nothing else. ASYNC by itself (e0) hands over the exact count, late,
and the guest waits for it. No crash in either leg; C: 57 GB free after each.

### Halo's flare code (disassembly, offline)

Read from `default.xbe` (`.text` at 0x11000, the D3D section at 0x180e40). A subagent did the reading; I checked
the deciding listings myself.
- **Frame order.** The frame function 0x5dbc0 first calls 0x62690 -> 0x801e0 -> **0x60460, which reads every
  flare test queued in the previous frame**. Then it queues this frame's flares (0x5fe80, 40-byte records,
  count at `[0x2e34e0]`), issues the tests (0x60560 -> 0x63c00) and draws the flares (0x606b0).
- **The issue step.** A test is BeginVisibilityTest, a 4-vertex quad, and EndVisibilityTest(i), where i is
  the queue position. So report slot i (0x60000 + 16 i) is reused every frame, by whichever light is i-th in
  the queue. The test is skipped when the projected area is <= 0, and the area is stored as the expected total.
- **The read step waits.** For each record with area > 0, it calls 0x63460. That function calls
  GetVisibilityTestResult (0x1810f0) and **spins while it returns 0x88760828 (not ready), with no timeout,
  kick or yield**. Then t = (count*255 + area/2)/area, clamped to 255. t == 0 sets the brightness byte to 0 at
  once. Otherwise the byte moves up as (3 old + t)/4 or down as (old + t)/2. Last, the queue count is zeroed.
- **What is stored.** One brightness byte per flare, not per test. For map lights it is at 0x27ffb0 + slot*4 +
  view; for objects at 0x2bffd0 + obj*0x22, cleared when the slot's owner tag changes at queue time. That
  clearing is f41's reset in r4b. No reset is tied to a camera cut.

What this decides:
- **H9 (no wait, keeps the last answer) is refuted.** Since the guest waits for every count, a late count
  cannot carry over a cut. A count arrives exactly or not at all.
- **A race on slot reuse is impossible.** Every test issued in frame N is waited on before frame N+1 issues
  its own.
- **Only a wrong count can draw a hidden flare.** That means EARLY, a host GPU that counts the hidden quad, or
  a different quad.

### The 0.5.1-rc1 sighting: the stock Qualcomm driver

- **The package.** The owner's 10-16 logs (`captures/owner-halo-1016/logcat-nova-full.txt`, `-2154.txt`) are
  package `com.jreinach.hakux`, the release app. The slot0 state's `hdd` path is
  `/storage/emulated/0/Android/data/com.jreinach.hakux/...`.
- **The driver.** bindpose1017 (#1043, folded 9abd80e90c, update 2) shows that this app had no custom driver
  from its install on 09-06. At 10-17 09:06 and 09:23 it logged `GPU driver: no custom driver installed, using
  system default` and `[gpl569] ext=0 ... mode=0`, after 0.5.2-rc1 was installed over 0.5.1 with data kept.
  lane.xbox (13:50, from lane.local) adds that it first got T30 when the owner selected it at ~13:20 today. So
  both of the owner's sightings (0.5.1-rc1 on 10-16, 0.5.2-rc1 on 10-17) ran on the stock driver. The 10-16
  logs carry no driver line either way; the install history is what settles it.
- **The owner's rule (10-17).** The stock driver is never used or tested, and a stock-only result is a
  wrong-setup arm. lane.xbox reports the same trap on #1038 (squares only on stock, gone on T30 at 13:34).
- **What it means for 0.5.1-rc1.** With no EARLY, a hidden flare needs a host count that is nonzero from the
  front (above). The code produces none on the desktop. The stock driver is the one GPU-side difference left,
  so H2 on stock is the account for 0.5.1-rc1. Its mechanism is unmeasured and stays so. N0 (Turnip, EARLY=0)
  is what checks that the code is clean on the Nova's GPU.
- **For 0.5.2-rc1 on stock:** EARLY's one-frame flash would be there regardless of driver.

### Hypotheses, final for the desktop (re-ranked on r5, the disassembly and the driver)

| # | hypothesis | P | evidence |
|---|---|---|---|
| H1 | EARLY answers the first front frame's tests (and a reordered slot's) with another test's count | **0.97, the 0.5.2 defect, driver-independent** | r4b: f41 given 12/730 against its own 0/0, f42 draws 12 rear flares. e0 and a0: clean. Offline: the same class at f255 and f263 (reorders, α 0.016-0.043) |
| H2-stock | the stock Qualcomm driver counts the hidden test quad (or gets the query wrong) | 0.6 as the 0.5.1-rc1 account; not chased (owner rule) | both sightings ran on stock; the code is clean without EARLY; A5 records a handheld counting the depth-hidden ZPass quad |
| H2-Turnip | Turnip counts the hidden quad | 0.05 | halo1016's Turnip front frames are clean (21 frames, steady shot); N0 decides |
| H9 | the guest keeps a stale answer on "not ready" | 0.00 | refuted: 0x63460 spins with no timeout |
| H3, H4, H5, H7, H8 | zeta without the hull, span/reset, a depth-tested light, draw order, a skipped draw | <= 0.02 each | r4b: own counts right in every frame, flares are depth-test-off, no skips |
| H6 | the aarch64 JIT decides differently | 0.02 | N0/N1 compare with the desktop |

### Remedies, ranked by P x win (offline cost from the dumps, `testquad.py`)

The cost of refusing an early answer is a frame in which the guest waits for the GPU. That wait is what EARLY
removed: 42.1 -> 35.9 ms/f in Halo's cinematic (halo1016's arms B, E; defaulton1017 :325). A frame waits if any
one of its reports is not answered early, so the cost unit is frames that wait, per 300.

| # | remedy | P it clears the cut flash | added waiting frames / 300 (r4b, e0 sim, a0 sim) | win | status |
|---|---|---|---|---|---|
| R1 | **Moved-quad guard:** refuse an early answer when the offset's test quad (inline position, attribute 0) moved more than 32 guest px since the offset's last test **and** the stale answer is nonzero | 0.9. Offline: catches 12 of 12 at all three cuts, plus the reorder flashes | 2 (the cut already waits in r4b), 2, 4: about 1%, ~0.06 ms/f at 6.2 ms per waiting frame | the defect gone, and the reorder class too, for ~1% of EARLY's gain | **building** |
| R2 | EARLY off by default | 1.0 (e0, a0 clean) | every frame: 6.2 ms/f, #1018's whole gain | the defect gone, Halo's cinematic 15% slower | measured by e0 plus halo1016's arms; the fallback if R1 fails |
| R3 | Key the early answer by quad position instead of offset (nearest previous test within T) | 0.9 | T=8: 156; T=16: 112; T=32: 59 | low: about a fifth to half of EARLY's gain | rejected on the measurement |
| R4 | Moved-quad guard on every answer, zero or not | 0.9 | T=8: 151; T=32: 60 | low | rejected on the measurement: within-shot quads jump, but nearly always with a stale answer of 0, which is harmless |
| R5 | Turnip by default (bindpose1017's R2), for the stock sightings | n/a here | n/a | every release user off stock | the owner's decision, not this lane's |

Why "nonzero" is the right half. A stale 0 for a light that is now in view only delays its fade-in by one
frame, and at a cut the guest's own reset starts it from 0 anyway. A stale nonzero answer for a light now
hidden is the defect. N must be 1 rather than a sample threshold: the four small rear lights' stale answers
are 4-6 samples, and f42 drew them at α 0.184. Guard knees from `testquad.py --nzguard` (r4b, N=1):

| T (guest px) | added waits | refused | hidden caught | hidden missed (max stale) |
|---|---|---|---|---|
| 16 | 20 | 51 | 24 | 191 (4) |
| 24 | 6 | 30 | 18 | 197 (4) |
| **32** | **3** (f0 is the dump's start; 2 real) | 27 | 15 | 200 (4) |
| 64 | 3 | 27 | 15 | 200 (4) |
| 96 | 3 | 23 | 11 | 204 (9) |

The 200 missed are 1-4 sample edge counts at a quad that did not move. They are a light becoming occluded in
place, shown one frame longer at its old spot. That is EARLY's designed latency (defaulton1017's HVIS
0.0055), not a light seen through a hull. 32 is the knee, and 32-64 behave the same.

## Crash log (desktop)

None yet (r1-r5: no dump in `wsl-crashes/`; C: 57 GB free after each).

## Questions

1. ~~Which build did the owner see it on?~~ Answered from slot0's meta: 2636e89f4a, no EARLY (above).
2. ~~Which driver?~~ The release app, stock until ~13:20 today (bindpose1017, lane.xbox). Not a question for
   the owner.
