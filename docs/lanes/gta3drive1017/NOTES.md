# lane.gta3drive1017 -- GTA III drops into the teens while driving (#433)

Status: Step 0 done (this file, committed before any code). Next: locate the wait the PFIFO thread is blocked in. No
emulator code touched.

[lane.gta3drive1017] working: locating the wait (section 4).

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

## 4. Hypotheses

P is lane.xbox's start, then mine after section 3. Each names its section-2 row.

| # | hypothesis | row | start P | P now | evidence that moved it |
|---|---|---|---|---|---|
| D1 | texture work on the PFIFO thread (dirty checks, hash, upload) grows while driving | #461 M1-M3, a1fa1156b9, #992, texscan1010 | 0.35 | 0.20 | walks are us; Tq x1.6; can only explain part of the +9 ms CPU, none of the +22 ms blocked |
| D2 | vertex sync / draw CPU work grows | drawrec1010, fpsbelow1012, 2790e4b700 | 0.25 | 0.10 | vtx walk time is us; spans x5 but bytes unknown; draws per flip not in the capture |
| D3 | the GPU is the limit (GMEM replay, render mode): the PFIFO thread waits on fences | #530, #871, #474 | 0.20 | 0.25 | the blocked time fits a GPU wait; no GPU busy figure yet |
| D6 | synchronous finishes in the draw path: VTX_HAZARD (RenderWare immediate mode) or surface downloads block the PFIFO thread on the GPU per occurrence | gtasagpu1011 263-336, #794/#796, #372 | new | 0.30 | the blocked shape; same engine family as the SA hazard; count not in this capture |
| D7 | lock contention: PFIFO waits for pgraph.lock held across a render-thread GPU wait | #474 tracker 4304-4318 | new | 0.10 | blocked shape; indistinguishable from D3/D6 without a wait split |
| D4 | guest-side cost (JIT invalidation, slow stores) | 72541aa1b3, #864 | 0.15 | 0.05 | the renderer is saturated (Ri ~1), the guest's growth is after the GPU interrupt |
| D5 | real Xbox drops too | targets.toml (no sourced figure) | 0.05 | 0.05 | no console figure |

D6 and D3 are the next measurement's job to separate: one wait split of the PFIFO thread's blocked time (finish waits
by cause, fence waits, lock waits, queue-full waits), on a driving window.

## 5. Plan

1. Read every hakuX tag in the snapshot for pid 21488 for finish/download/hazard counts already logged (no device time).
2. A GTA III driving route (board request): enter the car, throttle, minutes of road. Prove it moves (frames minutes
   apart, minimap moving) before measuring on it.
3. One Nova run with the wait split (the instrument is code: board request for its file first), interleaved
   `HAKUX_VTX_HAZARD=0` and `TU_DEBUG=sysmem` discriminator arms, registered before any device time.
4. Rank remedies by P x win from the located wait; chase the top two.

## Questions

None yet.
