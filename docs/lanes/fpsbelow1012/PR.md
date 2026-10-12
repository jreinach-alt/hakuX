# fpsbelow1012: the below-bar titles on the Nova at master, and one fix that lifts several (#433, 0.5)

State: ready

Lane: fpsbelow1012          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 5326de78b2, merged 00fde8afb3, a13a2f52db, then origin/master on 10-12 05:5x PDT (0 behind)
Files: docs/lanes/fpsbelow1012/NOTES.md, docs/lanes/fpsbelow1012/OUTBOX.md, docs/lanes/fpsbelow1012/PR.md, docs/lanes/fpsbelow1012/drafts/vtxexact.diff, docs/lanes/fpsbelow1012/tools/ab-bbuckets.out, docs/lanes/fpsbelow1012/tools/ab-handread.out, docs/lanes/fpsbelow1012/tools/ab-zread.out, docs/lanes/fpsbelow1012/tools/depthpair-abcompare.out, docs/lanes/fpsbelow1012/tools/ndkcheck.py, docs/lanes/fpsbelow1012/tools/rangefin-all.out, docs/lanes/fpsbelow1012/tools/rangefin.out, docs/lanes/fpsbelow1012/tools/rangefin.py, docs/lanes/fpsbelow1012/tools/rfread.py, docs/lanes/fpsbelow1012/tools/routecheck.py, docs/lanes/fpsbelow1012/tools/routecheck.tsv, docs/lanes/fpsbelow1012/tools/sdrange.py, docs/lanes/fpsbelow1012/tools/tilesim.py, docs/lanes/fpsbelow1012/tools/vtxrange.out, docs/lanes/fpsbelow1012/tools/vtxrange.py, docs/lanes/fpsbelow1012/tools/zread.py, docs/testing/nv2a_index.json, docs/testing/predictions/fpsbelow1012-vtxexact.json, docs/testing/predictions/fpsbelow1012-zetad24-pixels.json, docs/testing/predictions/fpsbelow1012-zetad24.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/vertex.c
Prediction: docs/testing/predictions/fpsbelow1012-zetad24.json @ ec352c20a21e07b144e4b1cc6bfaa895d0792fd745c215135a0a3a739c6dce7e (title A/B, judged: LOSS); docs/testing/predictions/fpsbelow1012-zetad24-pixels.json @ c543e6ac7e76b4bc73d102c1140b9f59b7816cce469b47086a950e0ad1e9caee (depth cost, judged: PASS); docs/testing/predictions/fpsbelow1012-vtxexact.json @ eb30dbad227e76d2ec45886f26af3eafdb5e0d1c2de3d78fdfdd29b274062bf4 (L4a on MC3, queued)
Needs device: yes (Nova, sweep tier)    Needs NDK: yes

**The switch.** `HAKUX_ZETA_D24=1` (vk/surface.c, off by default) stores Z24S8 as D24_UNORM_S8_UINT instead of
D32_SFLOAT_S8_UINT. With D32S8, Turnip keeps the stencil as a separate 1-byte plane in GMEM. That doubles the A740's
tile width alignment to 192, so a 640/720x480 pass with 32-bit colour needs two tiles, and two tiles get no HW
binning: each tile replays the whole draw stream. As D24S8 the pass fits one tile (NOTES.md section 5, read from the
driver source before any run).

`HAKUX_VTX_EXACT=1` (vk/draw.c, vertex.c, renderer.h, off by default) makes the vertex-RAM sync stale-test and
download only the bytes a draw reads, instead of the page-rounded range. On Midnight Club 3 the rounding reaches a
256x256 render target that sits mid-page after a vertex buffer, and it downloads that target on every draw
(NOTES.md section 10a). The copy into the vertex buffer still covers the rounded pages.

The PR also adds two perf-build instruments, neither on in a release build:
- `HAKUX_RANGELOG=1` (off by default): an `[sdrange]` line naming each `range` surface download's surface, its
  caller, and whether the draw's exact vertex bytes reach it.
- `[sdrfin]` (always on in perf builds): it splits `range` completions by why each one completed the deferred batch
  (NOTES.md section 13).

**Table and telemetry.** The offline table of the 43 Nova titles is NOTES.md section 2. Only 4 have a gameplay route
the profile gate admits, and 9 more the survey route (section 1). Telemetry at master is in sections 8, 10a and 11.

**The A/B** (`fpsbelow1012-zetad24.json`): one binary be0239bac8, B adds the env, sweep tier, one run per arm. Each
class window is read off the A arm alone.

| title | M: census in/out A -> B | P: GPU outer span per cb A -> B | W: G, gfps median A -> B | legs |
|---|---|---|---|---|
| Ninja Gaiden Black | 0.53 -> 0.99 | 21.54 -> 12.34 ms (x0.57) | 25.6 -> 16.9 ms, 40 -> 59 | every leg passes |
| Dead or Alive 3 | 0.51 -> 0.97 | 15.98 -> 10.16 ms (x0.64) | 16.9 -> 16.7 ms, 58 -> 59 | W FAIL |
| Buffy | 0.49 -> 1.00 | 21.29 -> 12.58 ms (x0.59) | 33.4 -> 33.4 ms, 29 -> 29 | W FAIL |

**Registered verdict: LOSS.** One of three titles passes every leg; the rule needs two. The W leg is a median against
a frame cap on DOA3 (60 Hz) and Buffy (its own 30), and NOTES 9b and 9c said so before their B arms ran. The
mechanism legs (V, M, P) pass on all three.

Hand-read, not judged (whole run, survey route):

| title | fps_ok A -> B | J/frame A -> B | like for like? |
|---|---|---|---|
| NG Black | 0.847 -> 0.960 | 0.192 -> 0.164 | yes |
| Buffy | 0.793 -> 1.000 | 0.278 -> 0.261 | yes; every 30-s bucket at the 30 cap |
| DOA3 | 0.698 -> 0.961 | 0.210 -> 0.170 | no: a different opponent and stage |

**The depth cost** (`fpsbelow1012-zetad24-pixels.json`, 10 depth suites, one binary c1112f2c1a, one run per arm):
**PASS on every registered leg** (NOTES.md section 14).

| leg | read, B (A) |
|---|---|
| z16 holds | 72 of 72 unchanged |
| the two 0x800007 clears >= 250k px | 271,662 each (654) |
| other z24 FZn rows move <= 20k | largest +4,086 |
| z24 FZn `_ZB` sum in 300k-1.5M | 618,394 (43,690) |
| no new blank | none |

No colour pixel moved outside a label in any of the 941 captures. Outside the legs, W_buffering's F24 rows (60
captures) read their depth back one unit high on every drawn pixel. Drawn colour is identical there, and the
fixed-D24 rows did not move. The section that predicted the cost had said F24 would be small. lane.local's
cross-title screen should judge a share leg, not a median, and weigh that cost.

**Ranking (NOTES.md section 12), titles x gain x P:**
1. L1 `HAKUX_ZETA_D24`: 3 titles measured, ~9 more two-tile on disk; P 0.7. Depth pair passed. Next is lane.local's
   cross-title screen.
2. L4a `HAKUX_VTX_EXACT`, built:
   - Midnight Club 3's `range` downloads are one 256x256 render target, reached only through the vertex sync's page
     rounding: ex 0 of 973 per 60 frames.
   - MC3 is 0.08 under the bar.
   - Its pair is queued, registered as `fpsbelow1012-vtxexact.json`.
3. L4c, a precise `range` completion rule:
   - Forza's 16.6 ms/frame of `range` wait is lookups completing the batch of eviction downloads that forza414 defers.
     At most half of it is removable.
   - The `[sdrfin]` counter is built, and one Forza run is queued. A rule written before that run decides whether a
     switch follows.
4. Then L2, L4b and L5. L3 (per-title sysmem) is superseded by L1.

**Device runs:** 13 done and 3 queued (16 of the 30 cap). All are sweep tier, and none is a retest.

**Checks on this head:**
- `docs/testing/preflight.sh --allow-tracker`: passed on 67e3fcf745.
- `check_android_guards.py`: ok.
- `docs/testing/jobs/selftest.sh`: stopped after 5 of 137 fragments, all ok. The lane touches none of the files its
  workflow watches (NOTES.md section 13).
- NDK: `tools/ndkcheck.py` compiles draw.c, vertex.c and surface.c with their NDK clang lines, as release and as perf
  builds: 6 of 6 rc 0, and no new warnings. The APK for 67e3fcf745 is built by the dispatcher, for the first queued
  run. Earlier refs ran on the device: c1112f2c1a (apk c8ce9a771091, the depth pair), be0239bac8 (apk 47e99f5db99c,
  the six A/B arms), and dbf9dd40cc (apk 64dbb3082354, the `[sdrange]` runs).
- Desktop: not built (this host cannot; see AGENTS.md).

Waiting, outside this PR (sweep tier, behind lane.local's Playable chain; NOTES.md section 14 says how to read each):
- the L4a pair on MC3, B `z-1791810680-fpsbelow1012-567845` and A `z-1791810682-fpsbelow1012-567963`;
- Forza's `[sdrfin]` run, `z-1791810687-fpsbelow1012-568864`.

Release note (none): HAKUX_ZETA_D24, HAKUX_VTX_EXACT and HAKUX_RANGELOG are opt-in switches, off by default, and `[sdrfin]` is a perf-build log; nothing a player runs changes.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
