# lane.gta3drive1017 -- GTA III drops into the teens while driving (#433)

Status (attempt 2, 10-17 16:40 PDT): the wait is located (section 6). R1 is built (c6ca5296fd, section 7). Its arms
are registered and queued behind lane.local's Nova hold (section 8). The driving route has a new gate (section 6.3);
the first drive pair is also its proof.

**Why attempt 1 did not finish.** It ended its session on purpose, waiting on two Nova pilots queued behind lane.local's
hold:
- `1-1792275531-lane.gta3drive1017-343857` (perflog + FRAMETRACE + GPUXFR), finished ~15:42;
- `1-1792275540-lane.gta3drive1017-346093` (plain build), finished ~15:51.

Their data was the next step, and a headless session cannot sleep through a device wait. Nothing was left half-done.

## 1. What was searched (Step 0)

| where | how | result |
|---|---|---|
| tracker | `git show origin/board:nv2a_issues.toml`, read rows #461 #474 #482 #517 #548 #794 #796 #807 #864 #871 #992 #994 #995 #1021; grep texture/dirty/vertex/inline/download/sysmem/GMEM/GTA | rows in section 2 |
| forge issues | API at 127.0.0.1:3330: refused without a signed-in token ("Only signed in user is allowed to call APIs") | **not read**; the tracker rows and the lanes' NOTES stood in for them |
| git, pickaxe | `git log --all -S tex_dirty_queries`, `-S renderer_idle` | a1fa1156b9 (Tq), 8882890b84 (Ri), and their later users |
| git, grep | `git log --all --grep` texture dirty / texture upload / vertex upload / streaming / GTA | rows in section 2 |
| lanes named in the brief | docs/lanes/gtaroutes1011, gtawedge1012, gta482, slowdown462 | the GTA III route (on foot); the SA lanes |
| lanes the search led to | remote (#461), dirtytlb (#548), rendermode474 (#530), async794, gtasagpu1011, fpsbelow1012, drawrec1010, texscan1010, fps1015, perdraw1009, collapse433; perflog1016 by commit (not folded) | rows in section 2 |
| code | pfifo.c:2440-2547 (Ri), profile.c:754-770/977-996 (Tq, Ri), physmem.c:1110-1370 ([rdc]), render_thread.c, renderer.c:566-598, draw.c:5612-5670 (finish), draw.c:8589-8626/9740-9800 (vertex sync walk), cpu-exec.c:1168-1352 ([rr425w]) | the instruments' meanings, section 3 |

## 2. Already tried

| approach | where (commit, lane, NOTES line) | verdict | what it means here |
|---|---|---|---|
| Per-flip memo of the texture dirty query (M1) | #461; 8f9c74f016; docs/lanes/remote/NOTES.md 2484-2493, 2810-2826, 3492-3504; tracker 4164-4178 | landed: TxH 6.93 -> 3.23 ms | Tq here is post-memo. M2 (page-granular dirt) and M3 (surface write-backs dirty fewer textures) were **never built** |
| Snapshot-and-clear of the texture dirty bitmap | a1fa1156b9 (proposed with Tq) | never built | open lever if D1 holds |
| TLB dirty walk only over live MMU modes | #548; PR #575, c77cb29eed; docs/lanes/dirtytlb | fixed: render-side walk 3.70 -> 0.77 ms/flip | why the `[rdc]` walk times here are microseconds |
| Owe the vertex sync's TLB walk to the flip (DRAWREC) | b10dcdb737, 060f165208; docs/lanes/drawrec1010 | on with the fast-paths toggle | `[rdc]` vtx = 8.0 calls per flip throughout gameplay reads like its run cap; its pages are merged spans, not bytes copied |
| Exact vertex ranges (VTX_EXACT) | 67e3fcf745, 4080a29d41; docs/lanes/fpsbelow1012 | off by default | a lever only if vertex sync bytes are the cost |
| Vertex-hazard finish (VTX_HAZARD) | a6ee1c58fe, ccb2749973; docs/lanes/gtasagpu1011 263-336 | on by default since 10-11; costs ~1-1.5 finishes/frame on foot in SA | **same engine family (RenderWare immediate mode).** A synchronous finish blocks the PFIFO thread on the GPU; driving may raise the count. A/B with `HAKUX_VTX_HAZARD=0` |
| Per-title sysmem render mode | #474; PR #530, c173400130; docs/lanes/rendermode474 | AUF 16 -> 24, DOA 13 -> 21 gfps; Kabuki stalls, Blinx ZPASS changes (#527) | untested on GTA III; a discriminator for D3 (`TU_DEBUG=sysmem`), not a remedy until the mechanism is shown |
| pgraph.lock held across the flip-stall GPU wait | #474, tracker 4304-4318; gmem474 / PR #582 | open, deferred; #582 closed no change | if the PFIFO thread's blocked time is this lock, the fix lives here |
| GMEM scene-pass replay, D32S8 two tiles | #871, tracker 6046-6051; ede7c891c5, 40c67b354c (`HAKUX_ZETA_D24`, off) | open; the switch is drafted | a D3 lever if GTA III's pass is two-tile |
| Synchronous SURFACE_DOWN finishes serialise the render thread | #794/#796, tracker 5665/5673; docs/lanes/async794 | folded; NBA Live/CS 13.8 ms/frame | the same blocked-in-a-method shape; count downloads per flip here |
| Two synchronous downloads per frame (Blinx) | #372; PR #467 | quadrant copy refuted | a download fix must remove the wait, not shrink the copy |
| bind_textures drain | PR #517 | AUF bind 4.55 -> 0.10 ms/flip, +1.7% fps | binds were already cheap once drained |
| Uniform hash skip | PR #543 | fps-neutral | not a lever here |
| Display pre-download deferral | PR #518 | outcome not recorded | -- |
| Texture-dirty cost spike | #992 (Top Spin), tracker 6277 | open | same counter family as Tq |
| inline_array growth | #994 (Batman Begins), #995 (Halo 2) | open | inline vertex data; GTA III's vtx column is DIRECT vertex RAM syncs, not inline |
| Vertex fetch as the per-draw cost | 2790e4b700 (bf2stall433), collapse433 | refuted on BF2: serialised draws | -- |
| Texture bind cost probes | 77f5b26344 (txh/txu/txr), 26936d9639 (txw[]), aa208a2938 (TxH), 27b5b6af6a (Tx 5.85 ms, #54) | instruments, perf builds | ready to split PFIFO CPU time if D1 survives |
| Texture rewritten behind unchanged registers | ad1caa0788, 054e1c065b, 91742b407b, 25493a599b | landed (correctness) | the polling Tq counts |
| Texture cache budget / S3TC threads | 1666e81d7a, 82b66c5f29, e022d97b57 | landed | -- |
| Car env cube map rendered and downloaded every other frame | docs/lanes/texscan1010 (NFS) | measured on NFS | a car-only render-to-texture is a driving-only cost; check GTA III for it |
| Top Spin replay render-thread-bound, binds x3 | docs/lanes/fps1015 1132-1165 | bind 0.6 -> 12.2 ms | a scene-dependent bind blow-up is possible |
| GTA SA: thermal pause (Thor) | #482; docs/lanes/gta482 | thermal | not this: the Nova, and the renderer is saturated, not paused |
| GTA SA: vCPU sleeps on GPU-side work | #807 | open | the guest's busy-after-interrupt growth here may be the same wait seen from the guest |
| GTA SA: guest-bound, renderer starved | #864; 72541aa1b3 (waitread1006); docs/lanes/slowdown462 (superseded) | measured | **the opposite of GTA III's dips** (renderer saturated, Ri ~1) |
| GTA SA: 624 ms stall | #1021 | open | spikes, not a sustained drop |
| GTA VC on foot cost | a000daf9e5 (perflog1016, not folded) | tcpu 259.6 ms/s, Ri 23.5 | a sibling's on-foot PFIFO load, ~8.7 ms/flip, matches GTA III's 7.9 at 30 fps |
| GTA III route | docs/testing/titles/routes/gta-3.route; gtaroutes1011 96-138; gtawedge1012 27-91 | on foot only (LY, A sprint, LX/RX); never enters a car | a driving route is new work: enter the car (Y untested) and find the throttle (RT per nfs-mw.route; unverified for GTA III) |
| GTA SA drive route throttle | gta-sa-drive.route | never proven | do not copy its throttle untested |

## 3. The capture, read

`tools/owner_play.py` joins the owner's tag-filtered capture (gfps/pace/rdc/shd413/pages, per 60-flip window) to the
full snapshot (`[rr425w]`, `[idlehalt]`, `[ide425d]`, per 2 s window). Output: `owner_play.tsv`, one row per window.

What the instruments mean (read in the code, not taken from the brief):

- **Ri** (pfifo.c:2476-2526): the PFIFO thread's time parked waiting for a kick, EWMA per flip. Ri near 0 does not say
  the thread is on a CPU; it can be blocked inside a method.
- **Tq** (texture.c:652): `check_texture_dirty()` calls per flip, EWMA.
- **`[rdc]`** (physmem.c:1119-1300): printed by whichever non-vCPU thread walks first past 60 flips. The walks here are
  the vertex sync (draw.c:9778, 8610) and the texture dirty test (texture.c:664), both in the draw path, so the printing
  thread (tid 21543 on every line) is the **PFIFO thread** that runs pgraph methods, not `pgraph.vk.render`. The brief's
  "render thread" is the code comment's older name for it. `tcpu` is its CPU ms over the window.
- **pf_blk** = wall ms per flip - Ri - tcpu per flip: the PFIFO thread neither parked nor on a CPU. Caveats: Ri is an
  EWMA, not the window mean; runnable-but-not-scheduled time also lands here.
- **`[rr425w]`** (cpu-exec.c:1168-1352): the guest's idle-loop time vs busy, by wake vector; key 33.44 is the NV2A
  interrupt, so its busy is the guest's work after a GPU interrupt.

Gameplay windows (from the load at 14:37:40, Tq >= 100; the Tq 1-4 windows at 14:39:58-14:40:02 and 14:40:19 are
menus), medians per band:

| band | n | fps | Ri | Tq | PFIFO cpu ms/flip | **PFIFO blocked ms/flip** | tex walks/flip (us) | vtx walk pages/call | guest busy ms/flip | of it after NV2A irq | vCPU off-CPU ms/flip |
|---|---|---|---|---|---|---|---|---|---|---|---|
| >= 28.5 | 60 | 29.9 | 18.8 | 804 | 7.9 | 6.2 | 3.1 (30) | 60 | 16.2 | 14.7 | 2.7 |
| 26-28.5 | 16 | 27.5 | 10.6 | 966 | 11.2 | 15.7 | 3.8 (46) | 263 | 21.5 | 18.8 | 7.1 |
| < 26 | 19 | 21.2 | 1.2 | 1305 | 16.8 | **28.6** | 5.3 (68) | 295 | 32.0 | 26.1 | 7.7 |

Readings:

1. **In the dips the PFIFO thread is blocked ~28 ms per flip**, more than it is on a CPU (16.8). The extra frame time
   (47 - 33 ms) is mostly that blocked time, and secondly CPU (+9 ms).
2. **Texture walks are microseconds** (68 us per flip in the dips). Tq grows 1.6x but each query is a bitmap test;
   the cost of a dirty hit (hash, upload) would be inside PFIFO cpu, not in the walk.
3. The guest is busy twice as long per flip in the dips, and the growth sits in the time after an NV2A interrupt. That
   reads as the guest waiting on the GPU side (as in #807), downstream of the PFIFO thread's wait, not ahead of it.
4. Vertex walk spans per call grow 5x (60 -> 295 pages) at a constant 8 calls per flip: the dirty vertex pages are
   spread over more VRAM while driving. The bytes copied are not in this capture.
5. DVD reads rise (3 -> 12 DMAs per 2 s) in the dips: streaming happens, at ~140 KB/s; small as a cost in itself.
6. The worst stretch (14:40:47-14:41:16, ~17-21 fps) has Tq 1500-1900, PFIFO cpu ~20 ms/flip and blocked ~30 ms/flip.

Further readings of the snapshot (every other tag pid 21488 printed: `fifoskew`, `[shd413]`, `[gpl569]`/`[uber569]`,
`[rr425pc]`, `[tlb68]`, `[mf0]`, `[jc425]`; a release build prints no finish, download or hazard count):

7. **14:37:40 is the load into the city.** That window lasts 6.3 s, with 1810 ms of pipeline compile, and fifoskew kicks
   rise from ~186 per 2 s (menus, backlog ~1.3 KB, drain ~1.1 ms) to 800-2500. This is the Tq jump the brief asked to
   place.
8. **In gameplay the guest stays about one frame of pushbuffer ahead of the PFIFO thread, at 30 fps too.**
   - Backlog mean ~85-110 KB (max ~500 KB) in both bands. At 14:37:51 (30 fps) the drain count is 0: the FIFO never
     emptied in the window.
   - In the dips (14:38:15-23, 14:40:48-52) the drain p50 sits at the 51.25 ms overflow bin.
   - So the backlog does not tell the bands apart. It says the PFIFO thread is the pace-setter all through gameplay, and
     the dips are that thread getting slower.
9. **Pipeline creation is not the wait.**
   - `[shd413]` dpc_ms (pipeline compile per ~2 s window) during gameplay is 0-87 ms.
   - In the worst stretch (14:40:47-14:41:16) it is 0.1-12 ms per 3 s.
   - Against ~28 ms per flip of blocked time, that is at most ~2 ms per flip, in two windows.
10. **The guest polls one spot harder in the dips.** `[rr425pc]` samples at `g:00265ffe` (`cmp edx, imm32`) rise from
    ~3-5k per 2 s at 30 fps to 26-49k in the 14:38:20-58 dip. The kernel idle loop (`e:8001b02e/f`) falls from 20-27M
    to 7-19M samples. What the loop polls was not read in the guest code. It fits reading 3: the guest waits on
    GPU-side progress.

The on-foot baseline, from the Playable run `1-1791792686-lane.local-32437` (Nova, 10-12 build, gta-3.route on foot,
read with `tools/drive_split.py` after its `mark gameplay`):

| run | windows | at >= 28.5 | fps | Ri | Tq | PFIFO cpu ms/flip | **PFIFO blocked ms/flip** | hazard finishes/flip | backlog KB | drain p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|
| on foot (32437) | 325 | 99.7% | 30.0 | 23.3 | 902 | 9.1 | **0.6** | 0.1 | 99 | 51.2 (overflow) |
| owner, driving dips (<26) | 19 | -- | 21.2 | 1.2 | 1305 | 16.8 | **28.6** | not in the capture | ~95 | 51.2 |

11. **On foot the PFIFO thread is almost never blocked (0.6 ms per flip). In the driving dips it is blocked 28.6.**
    - The builds differ (10-12 vs 0.5.2-rc1), so this is a direction, not a paired A/B.
    - Backlog and drain p50 are the same on foot at a steady 30 fps. Reading 8 holds: the frame-ahead pushbuffer is
      normal for this title and not a symptom.
12. **The vertex hazard's finishes are always logged.** vk/vertex.c:201 prints `vtx_hazard: N finishes` on I/hakuX at
    most every 10 s, in every build, and the dispatcher's spec keeps `hakuX:I`.
    - On foot it is 0.1 finish per flip.
    - The owner's capture was filtered to W/hakuX, so it is not in it.
    - The plain pilot gives the driving count without perflog. `drive_split.py` reads it as `hz`.

## 4. Hypotheses

P is lane.xbox's start, then mine after section 3. Each names its section-2 row.

| # | hypothesis | row | start P | after the capture | after the pilots | evidence that moved it |
|---|---|---|---|---|---|---|
| D1 | texture work on the PFIFO thread grows while driving | #461 M1-M3, a1fa1156b9, #992, texscan1010; **#474 drain (PR #517 row)** | 0.35 | 0.20 | **0.85, as D1' below** | the texture path is where the wait is, but as a wait, not as CPU: section 6 |
| D1' | **new:** the #474 drain ahead of each surface-to-texture colour copy (texture.c:3290) blocks the PFIFO thread on the GPU's fences, once per copy of a node sampled in the last 3 submits | #474 tracker 4304-4318; PR #517 (bind drain); texscan1010 (skips this drain for its cube) | -- | -- | 0.85 | pilot 1, <26 band: 71.9 drains per flip, 11.6 ms per flip in them, against 2.0 and 2.5 at >=28.5; fence wait 14.3 vs 2.4 ms per flip; dose-response over all 220 windows |
| D2 | vertex sync / draw CPU work grows | drawrec1010, fpsbelow1012, 2790e4b700 | 0.25 | 0.10 | 0.15 | prun +10 ms per flip in the dips (perflog doubles it); draws 500-634 per frame. Real, but second to the wait |
| D3 | the GPU is the limit | #530, #871, #474 | 0.20 | 0.25 | 0.05 | gpu50 21.9 ms per frame in the dips against a 47 ms frame: the GPU idles half the frame |
| D6 | synchronous finishes in the draw path (VTX_HAZARD, downloads) | gtasagpu1011 263-336, #794/#796, #372 | new | 0.30 | 0.02 | `vtx_hazard` ~0.3 finishes per flip driving (0.1 on foot); finish counts flat across bands |
| D7 | pgraph.lock contention on the PFIFO thread | #474 tracker 4304-4318 | new | 0.10 | 0.02 | ft1 lw = 0 in every band. The vCPU does wait on the lock (7.5 ms per flip in the dips), because the drain holds it |
| D4 | guest-side cost | 72541aa1b3, #864 | 0.15 | 0.05 | 0.03 | vgw (guest work per frame) 19.9 -> 23.3 ms: under 33 ms in every band |
| D5 | real Xbox drops too | targets.toml (no sourced figure) | 0.05 | 0.05 | 0.05 | no console figure |
| D8 | pipeline creation stalls | #569, #413 | new | 0.02 | 0.02 | reading 9 |

The next measurement separates D6, D3 and D7. It is one split of the PFIFO thread's blocked time on a driving window:
finish waits by cause, fence waits, lock waits and queue-full waits. **It needs no code.** A `--perflog` build
(`-Pperflog=true`) with `HAKUX_FRAMETRACE=1 HAKUX_GPUXFR=1` prints:

- `hakuX-stall Finish:N(vtx sc sd buf fb pres flip flu stl)`: finishes per window by cause, plus the `txdl[...]`
  download reasons;
- `hakuX-phase ... Fin:(Sub Fen) ... GPU:(R X)`: ms per frame;
- `hakuX-cpu Lw`: lock wait;
- `[hakuX-ft1] prun pblk pidle gpu50 lw fw=<site>`: the PFIFO thread's run/blocked/idle per frame and its top wait
  site.

fps1015 located MKSM's wait (#986) with the same lines.

What each outcome means, decided before the data:

| the split shows, in the <26 band | reads as | next |
|---|---|---|
| fin_vtx carries the extra finishes (>= 2 per frame over the >=28.5 band), or `hz` (both runs) >= 1 per flip against 0.1 on foot | D6, the vertex hazard | arm `HAKUX_VTX_HAZARD=0` (discriminator), then a hazard that does not wait |
| fin_sd / txdl downloads carry them | D6, a render-to-texture read back | the download's reason (cvt, swz, pitch); a remedy like #1018's |
| few finishes; ph_fen or fw1 is a fence and gpu50 >= 30 ms | D3, the GPU is the limit | arm `TU_DEBUG=sysmem` (discriminator); GPU pass split |
| lw (Lw / ft1 lw) carries it | D7, the lock | the lock's holder |
| pblk small and prun large | D1/D2, CPU on the PFIFO thread | the perflog's txr/vtx split by cost |

## 5. Plan

1. Done: every hakuX tag in the snapshot for pid 21488 read (readings 7-10). A release build logs no finish, download
   or hazard counts.
2. The driving route draft is `routes/gta-3-drive.route`, crop `routes/refs/gta-3-drive/fist-hud.png` (a copy of
   gta-3's).
   - Boot as gta-3.route, then one Y press (enters the Kuruma 3 m away), then a throttle loop with equal left/right
     steering and a reverse every third lap.
   - `mark gameplay` comes after the entry.
   - It is queued from untracked copies in `docs/testing/titles/routes/`, moved aside after.
   - It lands there by board request once a run's frames prove the car moves.
3. Pilot, two Nova requests (2 x (540 + 90) s = 21 min, under the 30-min pilot gate):
   - a. `--perflog --env HAKUX_FRAMETRACE=1 --env HAKUX_GPUXFR=1`: route proof plus the wait split.
   - b. the plain shipped build: route proof plus timing without perflog's cost. Queued last, so the device's env pref
     ends clean.

   The reader `tools/drive_split.py` was committed before the data. It checks Turnip first, then gives per-window rows
   after the mark and band medians.
4. From the located wait (the outcome table in section 4): register the discriminator arms in
   `docs/testing/predictions/gta3drive1017-*`, run them paired and interleaved, rank remedies by P x win, and chase the
   top two.

## 6. The pilots (attempt 2)

Both runs are on Turnip: `[gpl569] ... mode=3` is in each logcat (64 and 80 matching lines). Ref cf0318d210, 540 s each.
The perflog run is apk 4e5896bfefee and the plain run is e10dd136f0ee.

`tools/ft_waits.py` reads the perflog pilot's `txw[]` (texture-bind wall time by part), `hakuX-ft1` wait split and
GPUXFR lines per 60-flip window. **It was written after the data arrived.** `drive_split.py`, committed before, does
not parse those fields. The route's `mark gameplay` fell on the game's intro drive (6.3), so these use every window
of the run (`--all`): intro, cutscenes, on foot and driving together. The question is per window: what does the
PFIFO thread wait on when the frame is long? Scene does not change that.

Outputs: `pilot343857_waits.tsv` / `.bands`, `pilot346093_waits.tsv` / `.bands`.

### 6.1 The wait split, perflog pilot 343857, band medians

| band | windows | fps | Ri | **faf ms/flip** | **faf calls/flip** | cp calls/flip | up calls/flip | bind ms/flip | s2t/frame (GPUXFR) | PFIFO run | PFIFO blocked | **PFIFO fence wait** | vCPU lock wait | guest work | guest idle | GPU ms (p50) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| >= 28.5 | 78 | 29.9 | 12.7 | 2.5 | 2.0 | 2.0 | 0.1 | 3.2 | 1.2 | 16.7 | 16.4 | 2.4 | 1.5 | 19.9 | 9.7 | 14.1 |
| 26-28.5 | 31 | 27.5 | 0.9 | 7.4 | 13.0 | 13.2 | 0.0 | 8.6 | 3.6 | 23.3 | 12.5 | 8.5 | 3.5 | 20.9 | 10.3 | 16.2 |
| < 26 | 111 | 21.2 | 0.2 | **11.6** | **71.9** | 72.8 | 0.0 | 13.3 | 30.5 | 27.1 | 18.5 | **14.3** | 7.5 | 23.3 | 13.9 | 21.9 |

- `faf` is `pgraph_vk_flush_all_frames` called from create_texture ahead of a copy or an upload (txw FAF). `cp` is
  `copy_surface_to_texture` (txw CP); `up` is `upload_texture_image`. Times are ms per flip unless named.
- GPUXFR's s2t count undercounts: its ring logged `dropped N` in the dips. txw cp is the exact count.
- The plain pilot 346093 prints only the pace fields: >= 28.5 113 windows (30.0 fps, Ri 18.8); 26-28.5 33 (27.1, Ri
  6.5); < 26 45 (22.9, Ri 3.6). The same three bands, at higher fps: the perflog build roughly doubles the PFIFO
  thread's CPU. So perflog figures are for the wait split, not for timing.

### 6.2 The located wait

**In the dips the PFIFO thread sleeps in vkWaitForFences inside `pgraph_vk_flush_all_frames`
(vk/draw.c:5136). The caller is create_texture's #474 drain, vk/texture.c:3290-3295, ahead of each
`copy_surface_to_texture` colour copy.**

```
} else {                       /* surface sampled as a texture, not direct-bindable */
    if (snode->submit_time + r->num_active_frames > r->submit_count) {
        pgraph_vk_flush_all_frames(pg);     /* waits every submitted frame's fence */
    }
    copy_surface_to_texture(pg, surface, snode);
}
```

- **Dose-response.** Drain calls go 2.0 -> 13.0 -> 71.9 per flip across the bands. Their time goes 2.5 -> 7.4 -> 11.6
  ms per flip. The PFIFO thread's fence wait (ft1 pw[5]) goes 2.4 -> 8.5 -> 14.3, and the drain is ~80% of it.
- **How one drain costs several ms.** The drain does not submit the command buffer being recorded. It waits for the
  frames already submitted, up to NUM_SUBMIT_FRAMES = 3, which are the GPU's whole backlog. So the PFIFO thread
  cannot record frame N+1 while the GPU runs frame N.
  - The first drain of a frame pays for the GPU's backlog; later ones are cheap until the next submit.
  - Windows with only 3-5 drains per flip still lose ~10 ms of faf (15:41:50-15:42:01, ~27.5 fps).
- **Serialization, not a GPU bound.** The GPU's busy time is 21.9 ms (p50) of a 47 ms frame in the dips. drain474's
  lesson applies: a drain is worth removing only when the GPU idles during it, and here it does.
- **The vCPU's lock wait follows from it.** The drain runs inside a pgraph method, under pgraph.lock. The vCPU's
  PGRAPH register reads wait on that lock: 1.5 -> 7.5 ms per flip (ft1 vw[2]). That is reading 3's "guest waits on
  the GPU side", now with its mechanism.
- **Why the drain fires.** A colour surface is sampled as a texture after being drawn to again since its last copy
  (`surface->draw_time != snode->draw_time`), and `surface_view_decodes_as_texture()` refuses a direct bind. The node
  was bound within the last 3 submits, so the drain runs. While driving this happens ~73 times a flip.
- **Ruled out in the same windows:**
  - D6, the vertex hazard and downloads: finish counts flat, `vtx_hazard` ~0.3 per flip.
  - D7, the lock on the PFIFO side: ft1 lw = 0.
  - D8, pipeline compile: reading 9.
  - Texture dirty walks: microseconds, readings 2 and 7.
  - The guest's own work: 23.3 ms, under a 33 ms frame.

The PFIFO thread's CPU also grows (prun 16.7 -> 27.1 ms per flip in the perflog build, about half that in the shipped
build). The growth comes from draws (500-634 per frame), render passes (22-30 per frame, each copy breaks one) and
the copies' recording. That cost is real and is R2/R3's (section 7), but it is second to the wait.

### 6.3 The route: why it did not drive, and the new gate

- **The fist-hud gate matched too early.** In both pilots `waitfor fist-hud` matched at 0 s on the game's own intro
  drive: Chinatown, clock 05:23, $0, HUD up (`154632-fist-hud.png`).
  - That sequence runs *before* the "Give Me Liberty" cutscene (`154716-drive.png`). The cutscene sets the mission
    clock to ~04:10, which is why it looked like a restart.
  - The single Y press landed on the intro, and `mark gameplay` with it.
  - Claude reached the Kuruma only later: pilot 2 shows "Enter or exit a vehicle: Y" at 15:48:30 and 15:49:07, then
    drives Chinatown at 15:49:44-15:50:21 with the money rising. Pilot 1 drove from the alley to Eddie's,
    ~15:38:27-15:40:24.
  - The weapon icon is up on every in-game screen, so it cannot say "on foot next to the car".
- **The host's adb dropped presses.** Both pilots logged `UtilAcceptVsock accept4 failed 110` (13 in pilot 1, one in
  pilot 2). A press-until with a retry covers that for the entry.
- **The new gate is the tutorial box.** `routes/refs/gta-3-drive/enter-help.png` is cut from `154830-drive.png` at
  104,84,380,88. `tools/route_gate.py` scores that region on every frame of both pilots and of the Playable run
  32437, by waitfor_match.py's own `region_score`:
  - 0.00 and 4.45 on the two frames with the box;
  - 31.45 and up on the 26 frames without it, including the same box with other text ("Brake or reverse", 31.62).
  - Threshold 15.
- **The route now** waits up to 240 s for the box, then `press-until Y enter-help 3 5` (pressing Y until the box
  changes), waits 6 s, and marks gameplay. `route.sh --check` passes.
- **Still unproven.** The first run with it must show the car moving minutes apart before any arm counts. The arms
  below carry that proof in their own frames: an arm whose frames do not show driving is void, not a result.

## 7. Remedies, ranked by P x win

The win is the share of the dip the remedy can remove. In the shipped build the < 26 band is 22.9 fps (43.7 ms); the
bar is 35.1 ms (28.5 fps), so the dip needs ~9 ms.

| # | remedy | P(it removes its cost) | win at full scale | P(clears the bar alone) | expected impact | evidence |
|---|---|---|---|---|---|---|
| R1 | Skip the #474 drain ahead of a **plain colour** surface-to-texture copy (vkCmdCopyImage). The barrier out of SHADER_READ_ONLY already orders the copy after every earlier fragment read on the queue. Keep the drain for zeta (its own copy path, not read for this), HAKUX_S2T_CVT (a compute pass with its own finish) and uploads. Kill switch `HAKUX_S2T_DRAIN=1` | 0.85 | ~11.6 ms per flip of faf in the dips (perflog); in the shipped build the wait is GPU time, so about the same; about 9-12 of the 9 needed | 0.5 | **0.85 x (9-12 ms) -- top** | 6.2; the same copy already runs with no drain for any node older than 3 submits; texscan1010 skips this drain on the same argument (texture.c:2253-2260) |
| R2 | Direct-bind the surfaces the copies come from: count the refusal reasons in `surface_view_decodes_as_texture` (format, swizzle, pad alpha, component map) and widen the one GTA III hits | 0.4 (only if one reason dominates and is safe to widen) | the copies themselves, ~73 per flip: their recording CPU and the render-pass break each one costs (rpc 22-30 per frame); a few ms of PFIFO CPU and GMEM load/store | 0.2 | 0.4 x (3-6 ms) | 6.2; bind_surface_as_texture also breaks the render pass, so the GMEM half of the win is smaller than the copy count says |
| R3 | Copy once per surface draw_time, not per sampling node: share one copy between nodes that sample the same surface state | 0.3 (not yet known whether several nodes sample one surface) | part of R2's | 0.1 | 0.3 x (2-4 ms) | needs the per-surface count; same instrument as R2 |
| -- | sysmem render mode, a faster clock or a performance mode | -- | -- | -- | not remedies | the GPU idles half the frame (D3 0.05); the brief forbids clock and mode fixes |

R1 goes first because it is the largest expected impact, not because it is cheap: it removes the measured wait
itself. R2 is the second chase if R1 lands short of the bar. Its first step is one refusal-reason counter (perflog
only), which decides between R2 and R3.

**R1's correctness argument, read in the code:**
- vk/image.c:137-142: SHADER_READ_ONLY -> TRANSFER_DST uses srcStage FRAGMENT_SHADER. A barrier's first scope is
  every command earlier in submission order on the queue, across submits.
- There is one VkQueue (instance.c:1428).
- The PFIFO thread records; finished command buffers go to the render thread's FIFO (draw.c:5612-5651), and only
  that thread submits frames. So every frame recorded before the copy is submitted before it.
- The in-flight frames' descriptors keep pointing at the node's image view, which is not destroyed or recreated here.
  Those frames read the image before the barrier lets the copy write it.
- The drain's side work (deferred framebuffer, texture and surface releases; staging resets; the descriptor ring
  reclaim) is per slot. It runs anyway at the slot's own fence wait when the slot comes round again; skipping it here
  only delays it.
- The no-drain copy already runs today whenever the node is older than 3 submits. R1 makes that the rule for the
  plain colour path.

## 8. R1's arms (registered 10-17 23:31-23:33 UTC, before any of their data)

R1's build is c6ca5296fd: b7d7243392's change, master merged, plus a once-per-process `[s2tdrain] first skip` line.
That line shows the skip acted, not only that the env was read. Every arm uses this one build, so it is an env A/B:

- **A**: `HAKUX_S2T_DRAIN=1`, the drain ahead of every copy. This is master's behaviour; the condition reduces to
  master's.
- **B**: no env.
- The shipped-behaviour arm, A, is queued last in each pair, so the device is left in it.

| step | prediction | requests | what it decides |
|---|---|---|---|
| 1 | gta3drive1017-pixels.json | B, then A: drain474's seven surface-as-texture suites, ~1 min each | a capture moving in B only means the barrier does not order the copy: R1 is wrong, stop |
| 2 | gta3drive1017-drive.json | B1, A1: gta-3-drive, 600 s, FRAMETRACE (CSV off) | the pilot: does the route drive (shots minutes apart, the car moving), and P0/P1 on one pair |
| 3 | same | B2, A2 | the second pair: the spread, P2/P3 |
| 4 | same | on foot B, A: gta-3.route, 600 s, frames every 30 s | P4, on foot not regressed |

- Steps 1-2 are ~29 min by request.sh's estimate. That is the 30-min pilot.
- Steps 3-4 are queued after the pilot verdict is written to `pilots/lane.gta3drive1017.ok`.
- The judge is `tools/drive_judge.py`. It was committed with the predictions, and smoke-tested on the two old pilots:
  pilot 2 came out VOID, with no ft1 lines and no switch, as it should.

The legs are in the JSON. In short:
- **V**: Turnip; the switch as set; >= 60 windows and >= 60 ft1 lines; the car moving in the shots.
- **P0**: A's fence wait >= 4 ms/frame and A's best share <= 0.80.
- **P1**: B's fence wait <= 3 ms/frame and <= 0.4 x A's.
- **P2**: every B run >= 0.90 of its moving seconds at >= 28.5 fps.
- **P3**: B's worst run beats A's best.
- **P4**: on foot, B's median fps >= A's - 0.5.
- **F**: no B-only texture defects in the shots, and no new error lines.
- **X**: P1 passes but B stays under 0.75. The wait moved; chase R2.

## Questions

None yet.
