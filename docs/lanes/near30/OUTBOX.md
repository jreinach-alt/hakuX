## #433 -- 2026-10-02 16:50 PDT

[lane.near30] Why near-30 titles miss 28.5 fps: Tron 2.0 decomposed. Blinx 2 is waiting on the save.

**Tron 2.0 (Nova, 7 plain soaks plus 1 perflog soak today): CPU-bound on the vCPU thread.** The guest never reaches the kernel idle loop. In windows below the bar (median frame ~43 ms):

| ms per frame | at the bar (~27) | slow (~43) |
|---|---|---|
| vCPU running guest code | 21-25 | 32.7 |
| vCPU asleep, waiting on the GPU side | 5-6 | 10.3 |
| vCPU waiting for a core | < 0.1 | < 0.1 |
| renderer idle (overlapping) | 13-15 | 17.6 |
| GPU (perflog) | ~15 | ~22 |

- Frame time follows the vCPU's running time (r = 0.95).
- The vCPU's sleep follows GPU ms per frame (r = 0.64), not the renderer's CPU work (r = 0.08). For about a quarter of every slow frame, CPU and GPU take turns instead of overlapping, which is also why the GPU clock sat at its 401 MHz floor on every plain run.
- Measured out as the cause of that sleep: pgraph.lock (#474's lock, 0.37 ms), the fifo skew bound (off), read-downloads (< 0.2 ms).
- BF2's perflog shows the same unexplained sleep: 21 ms of a 64 ms frame.
- Gap to the bar on the median slow window is 8 ms (10 ms to a full 33.3).

**ToeJam & Earl III (the control) holds**: 11 ms of guest work per 16.7 ms frame, and the guest idles every frame.

**Levers by probability x size:**
1. Name and remove the vCPU's sleep: 10 ms of 43 on Tron, 21 of 64 on BF2. P 0.3. The first step is one off-CPU trace.
2. Faster JIT, starting with memfast phase 2 (fastmem): 20-25% of the vCPU's running time on every CPU-bound title. P 0.5. It is held up by board grants, not by evidence.
3. GPU clock. 4. vCPU on the prime core (Nova only). 5. ibcache. 6. Push constants and the ubershader, which don't reach Tron's critical path.

Successor brief for lever 1 is in docs/lanes/near30/NOTES.md.

**Blinx 2: waiting.** lane.local's addendum confirming the owner's save past Test 1 had not arrived by 16:50 PDT, so the capture is not queued. I have used 1 of 3 Nova runs. When the addendum arrives: one perflog run that loads the save, then ~600 s of play, then the same decomposition.

## #433 -- 2026-10-03 09:10 PDT

[lane.near30] Blinx 2 on the owner's "Jaguars" save: the ocean dip is GPU-side, from draw count. Scored window partial.

**Ocean (perflog, held Nova session, perflog build of master, golden 377a8488c7c5):**

| window | fps | draws/frame | GPU ms | vCPU on-CPU |
|---|---|---|---|---|
| sea out | 25.0 | 26 | 35 | 0.88 |
| sea in | 19.0 | 44 | 50 | 0.88 |

- The sea adds draw calls (+70%). GPU ms per draw falls (1.36 -> 1.13), so the count is the cost.
- The vCPU does not change. The guest is idle about half the time. Texture uploads are zero in both windows, so this dip is not texture loading.
- Verdict: GPU-side, draw-count-driven. The owner's read ("not one-time texture loading") holds for the steady dip. The first-appearance texture dips are not measured here.

**Scored window (Playable input): partial.** A checkpoint retry prompt and a scripted dialogue interrupted the walk. Valid gameplay is 314 s, and the share of rows at or above 28.5 fps is 0.115 (median 22.2). The first 98 s alone was 0.44. The 600-s bar is not met.

**Levers (P x win):**
1. Cut the ocean's draw count on the GPU path. P 0.35. The next step is a per-draw frame dump at sea in and sea out.
2. Memfast (fastmem). P 0.15 on this title (the guest is not the long pole here).
3. Ubershader / shader compiles. P 0.05 (TexU 0, already default).
4. Texture upload on first appearance. P 0.2, not yet measured.
5. GPU clock regimen. P 0.2, GPU MHz not read.

Full table, budget, and the successor brief are in docs/lanes/near30/NOTES.md, step 2c.
