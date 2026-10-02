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
