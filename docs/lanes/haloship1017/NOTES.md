# lane.haloship1017 -- Halo CE: the ship's rear lights show through the hull after the cut to the front (#1039)

Opening cinematic, The Pillar of Autumn (4D530004). Owner, 10-17: behind the ship its rear lights show (correct);
after the cut to the front they show through the hull; an original Xbox does not. Not game-blocking, same class
as #939. Branched from master @ 8d260f39fc.

## Status

Step 0 done (this file, before any code). Desktop input works (r2), the cut is located (r2), the light tests
are identified and count 0 in the steady front shot (r2, r3). Running: r4, every frame across the cut, armed by
the engine glow. Next: per-frame light tests and images for the first frames after the cut.

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

1. Behind the ship the rear lights show. Correct. Account: TBD (they are what H1-H5 gate).
2. After the cut to the front, the lights show through the hull; hardware does not. Account: TBD.
3. How many frames it lasts after the cut. Unknown; first measurement.
4. Desktop: unknown.
5. Fast paths off: unknown.

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

## Crash log (desktop)

None yet (r1-r3: no dump in `wsl-crashes/`; C: 57 GB free after each).

## Questions

1. ~~Which build did the owner see it on?~~ Answered from slot0's meta: 2636e89f4a, no EARLY (above).
