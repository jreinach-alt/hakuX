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
