# lane.aufire412 -- #412: 007 Agent Under Fire gameplay at a flat 16 fps on the Nova

Base: master @ dc38b745b8. Title 4541000D, Nova (ee317437).

## 1. The run on disk: `0-0-y-1790433159-titleplay-p1-aufire`

Ref a5b5b628f2 (apk 25abcaccbf45), not perflog, survey route, 420 s. The
logcat has gfps/pace, `[tlb68]`, hakuX-pages, `[surf92]` and
`[watch311]`/`[surfwatch382]` lines. It has no hakuX-phase or hakuX-stall
lines, because those print only in a perflog build. So this run can split
vCPU from renderer, but not Sub from Fen.

Read with `docs/lanes/fps382/timeline.py` and `cpuread.py`. `[surf92]`
updates are counted once per `update_surface_part(upload=true)`, which
`pgraph_vk_surface_update(d, true, ...)` calls from draw_begin
(vk/draw.c:1188) for colour and again for zeta. So updates/frame is between
1x and 2x the draws per frame.

| window (s since start) | what | fps | renderer busy (1-Ri/G) | vCPU ms/2 s | slow stores/s | sd/2 s | surface_update/frame | shapedirty/frame |
|---|---|---|---|---|---|---|---|---|
| 121-209 | front end, 60 fps | 59.9 | 9-20% | ~1970 | ~1,400 | ~2,800 | 124 | 2.00 |
| 228-236 | first scene frames | 43 | 83-100% | 1540-1800 | ~1,000 | 700-2,000 | 1,196 | 1.99 |
| 300-330 | menu rounds over the scene | 27 | 72-89% | ~1950 | ~500 | 800-1,800 | 3,157 | 2.00 |
| 345-423 | mission play (`mark play` 336 s) | 16.2 | **84-90%** | 1850-1980 | **~350** | **~700** | **4,746** | 2.00 |

What this says:

- **Not the fps382 shape.** Slow stores are ~350/s in play, against 2.5M/s
  in 50 Cent's movie. `sd` is ~700 per 2 s. `rdus` (code-arming time) is
  ~9 ms per 2 s, under 0.5% of the vCPU.
- **The renderer is the busy side.** It is 84-90% busy in play, where fps382's
  movie and this title's own 60 fps front end had it 4-20% busy. G is ~62 ms,
  of which Ri (idle) is 6-11 ms. The vCPU burns ~97% in every span, as in
  fps382, so it cannot separate anything.
- **The PR #387 watch is inert here.** `[surfwatch382]` suspends/rearms and
  `[watch311]` inserts are flat for the whole mission (2223/2219 and 2397).
  There are no CPU writes to watched surfaces in play.
- **Probably not the blinx372c shape either, pending the stall line.**
  `addrchg=0` on every `[surf92]` line and shapedirty stays at 2 per frame,
  so there is no colour/zeta rebinding ping-pong per draw. blinx's evictions
  need an incompatible binding at the target address. Whether any
  synchronous `Finish sd` remains is what the perflog soak's stall line says.
- **The per-frame work scales with draws.** surface_update/frame goes from
  124 (60 fps) to 1,196 (43 fps), 3,157 (27 fps) and 4,746 (16 fps). That is
  about 1,200-2,400 draws per frame in play. The renderer's ~54 ms busy per
  frame is then 11-23 us per draw on the renderer thread. The perflog phase
  line has to say whether that is CPU recording (Draw and its sub-phases),
  GPU time, or a wait (Sub/Fen).
- **"A steady per-frame cost, not stalls" holds.** Over 345-423 s, G is
  60-65 ms on every line, the per-line min is 28-37 ms and the max 70-85 ms.
  Vpf is 3.4-3.8. pace max is 70-85 ms: no line has a stall outlier.

## 2. Perflog soak on master (queued)

`1790450038-aufire412-1573805`: master dc38b745b8, Nova, `--perflog`, survey
route (text taken verbatim from the run above's request.json, because
`survey.route` is not on master), 480 s. It is read for the phase line (Surf,
Tex, Shd, Draw [sub-phases], Fin(Sub, Fen), GPU(R, X, RP)), the hakuX-cpu line,
the xemu-work workload line (BE/DA/IE/IB/IA draws, RP renderpasses, PGen/PBnd,
QS, Fin:* reasons) and hakuX-stall, over the mission-play window.

Reader: `splitread.py <logcat> --window A,B` (`--selftest` builds each line
from its format string in profile.c/draw.c and checks the parse). On the
Nova's own perflog run of 50 Cent (1790424433, 170-200 s) it reads 1 draw
per frame, 0.2 ms GPU: that is a movie, and it cannot price a draw.

A scale, not a price: Blinx's demo on the **Thor** (1790425369, 135-265 s)
reads 2,496 draws per frame, Draw 22.9 ms (Pipe 10.8, of which Sh 8.2), renderer
CPU (Tot-Idle-Fin) 29.2 ms = at most 11.7 us per draw, GPU 46.0 ms, Fin 39.9
(Sub 35.2). A Nova frame of 1,200-2,400 draws at the same cost per draw would
be 14-28 ms of CPU. AUF's renderer is busy ~54 ms. So either the Nova costs
more per draw, or the GPU or a wait takes the rest. The soak decides which.
Device differences mean this cannot stand in for the Nova's own figure.

## 3. How the soak will be read (written before it ran)

Window: mission play, from `mark play` + 10 s to soak end. The pause-menu
rounds before it are the matched-scene window for any arm.

| reading | shape | next |
|---|---|---|
| Fin (Sub) >= 25% of Tot, stall `sd` > 0 per frame | blinx372c (synchronous download) | name the dif/evict site; PR #396's reach |
| GPU >= 0.8 x (Tot - Idle), Fin small | GPU-bound | GPU R vs X; RP count (render-pass breaks) |
| Draw >= 0.6 x (Tot - Idle), GPU well under | per-draw renderer CPU | Draw's largest sub-phase (Pipe/Sh/Lu, Desc, Setup, Cmd, Vtx/Syn) names the file |
| slow stores >= 100k/s | fps382 | excluded already (~350/s); a reversal means a different scene |


## 4. The perflog soak: `1790450038-aufire412-1573805`

Master dc38b745b8, apk 853368f2e827, Nova ee317437, 480 s, DONE. The route
reached mission play (`mark play` at 288.7 s; the play frames show the
rooftop). `splitread.py` over three windows:

| window (s) | scene | fps | Tot | Surf | Draw | Desc | Fin (Sub) | Idle | GPU | draws/frame | SBnd/frame | Finish / 60 flips | fin_buf | `buf_detail ds` | sd_* |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 220-285 | pause menu over the scene | 14.7 | 61.2 | 15.4 | 13.1 | 21.7 | 21.4 (21.2) | 9.2 | 38.6 | 2,442 | 1,990 | 102 | 42 | 42-46 | 0 |
| 299-483 | mission play | 15.2 | 61.8 | 17.2 | 12.8 | **23.1** | **23.1 (22.8)** | 8.6 | 40.6 | 2,368 | 1,924 | 99 | 39 | 38-46 | 0 |

(ms per frame, medians of the smoothed phase line; `buf_detail` sampled every
~20 s. `ds` was 0 on every line before ~150 s, i.e. in the front end.)

### The shape: neither known one. The UBO descriptor ring runs out mid-frame

- **Not blinx372c.** Every `sd_*` and `fin_sd` counter is 0, and `Fen` is
  0.2 ms. No synchronous surface download happens.
- **Not fps382.** Slow stores ~350/s (section 1).
- **Every finish wait is inside `Desc`.** `Desc` is timed with the plain
  (non-exclusive) phase timer around `pgraph_vk_update_descriptor_sets`
  (vk/draw.c:4237), so it includes any finish run from inside it. Per phase
  line in play, `Desc` equals `Fin` to within 0.4 ms (24.6/24.4,
  27.6/27.6, 23.9/23.9, ...). The only finishes in that function are
  `VK_FINISH_REASON_NEED_BUFFER_SPACE` when a descriptor ring is full
  (vk/shaders.c:506-511, 557-563, 587-592, 664-667). `buf_detail` names
  which one: `ds` 38-46 per line, `ubo`/`fb`/`stg`/`vtx` all 0.
- **Which ring.** The Nova has `VK_KHR_push_descriptor` (its stderr lists
  it), so textures are pushed and only the UBO set ring
  (`push_ubo_sets`, `NUM_UBO_SETS` = 1024, shaders.c:163) is in play. A new
  UBO set is taken on every `shader_bindings_changed`, and this scene
  rebinds shaders ~1,950 times per frame. The ring resets only at a
  finish with nothing recording (draw.c:3322-3327). So it fills about
  0.65 times per frame between flip finishes (fin_buf 39-42 per 60 flips).
  Each fill is a full `pgraph_vk_finish`: submit, then wait for the GPU
  to drain (`Sub`, as with blinx: [[finish-wait-is-in-sub]]).
- **The grow path the comment promises is dead code.**
  `grow_descriptor_ring()` (shaders.c:386) came in with b6328b1112 and has
  never had a caller (`git log -G grow_descriptor_ring` lists only that
  commit). e7998e7fdd's comment at draw.c:3319-3320 says "a ring that runs
  out mid-buffer grows through the overflow pools until then". It does not.
  Nothing calls the grow, so the ring finishes instead.

### The price, offline

- Renderer CPU (Tot - Idle - Fin) is 30.1 ms per frame and GPU is 40.6 ms. In
  play, 23.1 ms of Sub wait sits in series between them. Each ring fill makes
  the CPU stop and wait for the GPU to drain, so recording and GPU work never
  overlap across that point.
- **Ceiling:** with every ring-fill wait gone and full overlap, the frame is
  bounded by the GPU: 40.6 ms, **24.6 fps** (25.9 in the pause-menu window).
  "16 toward 30" cannot reach 30 with this hunk. Past about 25, the GPU's own
  40 ms per frame is the next thing to price (GR 20 + GX 20; RP 5).
- **Floor: 0.** Per phase line, `Surf` (EXCL timer, 4,700 calls per frame)
  rises when `Desc` falls (Surf 30-35 ms on the lines where Desc is
  11-13 ms), and Tot stays at ~61. So part of the wait can reappear
  elsewhere, in the flip finish or in Surf. Removing the ring finish shows
  whether it does. The bet is that the flip finish can overlap the next
  frame's recording and the mid-frame ring finish cannot.
- **Expected:** fps 15 -> 18-24 in mission play and in the pause-menu window.
  `buf_detail ds` -> 0, with a new grow counter > 0. Fin(Sub) falls by at
  least half.

### The hunk (vk/shaders.c only; not granted yet)

At the two UBO-ring sites (shaders.c:506-511 and 587-592), try
`grow_descriptor_ring(r, r->push_ubo_set_layout, &r->push_ubo_sets,
&r->push_ubo_set_count, false)` before falling back to the finish. Count
it (`buf_ds_grow` in the `buf_detail` line) so the arm can see it fire.
Cap the overflow at a fixed number of pools (e.g. 16 x 4096 sets) and
fall back to the finish past it, so a scene that never reaches a
non-recording finish cannot grow without bound. The reclaim is already in
place and guarded (draw.c:3322-3327, `pgraph_vk_reclaim_descriptor_overflow`
resets `push_ubo_set_count` to the base). The standard-path texture
ring (557-563, 664-667) is not reached on a push-descriptor device. It gets the
same treatment only if a non-push device shows `ds` > 0.

Risks and must-not-move:

- The one way this hunk can change pixels is a set freed while a draw still
  references it: a stale uniform range, #34 finding 1's failure. The reclaim
  runs only with nothing recording and after the finish's wait, so a freed
  overflow set is not bound by live work.
- `Depth_buffer_fixed_function`, `Color_zeta_overlap`, `Surface_format`: a
  few hundred draws per test at most, which never fills 1,024 sets in one
  command buffer, so the grow is not reached there (inert by
  construction). Moving any of them means the grow fires in a golden, or the
  reclaim is wrong. The arm's logcat `buf_detail` line tells the two apart.
- PR #387's arm (watch suspension): no shared code. Inert.
- PR #396 / Blinx's vk/surface.c: untouched.

## Status (2026-09-26, attempt 2)

**Why attempt 1 did not finish:** it ended, correctly, waiting on the perflog
soak `1790450038`, a device request outside the session. The soak has now
run (DONE) and is read above.

**Now waiting on a board grant** for `hw/xbox/nv2a/pgraph/vk/shaders.c`,
requested on #412. No open PR's `Files:` names it (checked #401, #405; #396 is
surface.c). No prediction is registered: there is no code commit to name as
`b_ref` until the grant lands. Once it lands: implement the hunk above, merge
master, register `aufire412-uboring.json` on the pause-menu-over-scene window
(mover fps, must-not-move the three suites above), and push. Master is merged
at 3d40f14389.

Do not repeat: the non-perflog titleplay run cannot split Sub/Fen (no phase
line). A 1,024-set ring looks like a pool-size question, but raising
`NUM_UBO_SETS` only moves the threshold, because the scene takes ~1,950
sets per frame. The overflow pools are the mechanism the code already
intends.
