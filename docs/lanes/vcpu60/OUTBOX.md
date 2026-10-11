## #507 -- 2026-10-04 13:10 PDT

**The arithmetic:**
- No ranked combination of JIT items reaches 60 on any of the four titles.
- The vcpuplan list, priced with memfast's measured ratios, is 4-10% of the
  vCPU's on-CPU time.
- Simpsons would need that time cut by 58% to reach 60 with today's sleep
  left in place, so the list is about 48-54 points short.

**The premise holds for one title of four** (Nova; `docs/lanes/vcpu60/NOTES.md` section 1):

| title | target on file | what bounds it |
|---|---|---|
| Simpsons: Hit & Run | none (no `targets.toml` row). It flips on single vblanks 65% of the time, so it is paced for 60 | vCPU on-CPU 17.2 ms + **vCPU asleep 9.4 ms** of a 26.7 ms frame. The guest never idles, but the host thread sleeps a third of each frame |
| GTA San Andreas | **30**, from the game's own limiter | at its cap in 88% of windows; the slow 12% add 8.2 ms of the same vCPU sleep |
| 007 Nightfire | 60 (press, medium) | the **render thread**: 30.5 of a 33.8 ms frame (draw path 11.9, in-frame finishes 10.3, GPU 9.1) |
| Forza Motorsport | **30** (IGN) | the **GPU side** in its slow half: guest idle 20 ms per frame, renderer never parked, fence waits 32 ms, GPU at 401 of 680 MHz all run |

**Ranking (P x win; effort breaks ties only):**

| rank | item | P | win |
|---|---|---|---|
| 1 | **Name and remove the vCPU's sleep on GPU-side work.** First candidate, from the code: the guest's DMA_PUT write takes `pfifo.lock` (`hw/xbox/nv2a/user.c:93`), which the PFIFO thread holds across a GPU finish. This is the decoupling Dolphin's dual-core mode makes | 0.4 | Simpsons 37 -> 45 (half the sleep) to 55-58 (all of it); GTA's sub-30 windows back to 30 |
| 2 | **The JIT program** (FEX/Box64 class, inside TCG): the indirect-branch probe on by default + chaining for cross-page direct jumps + RAS, then regions, then inline SSE | 0.4 | 8-18% of v_run; +4-9 fps on Simpsons after rank 1. Decider: a one-binary `HAKUX_IBC` pair on Tron |
| 3 | **Nightfire's render thread** (in-frame finishes, draw path) | 0.35 | Nightfire 30 -> 36-42 |
| 4 | **A static GPU clock floor** (a regimen, not a governor), Forza first | 0.3 | Forza's slow half 21 -> 25-28 fps |

**Ceiling per title:**

| title | expected | 60 fps |
|---|---|---|
| Simpsons | **45-58** with ranks 1-2; 39-42 if rank 1 fails | only if all of the sleep goes and the GPU fences shrink, at about P 0.1 |
| GTA | **30 held** in about 95% of windows | not its rate; needs a game patch and about 2x the vCPU |
| Nightfire | **30-40** | needs about 1.8x on the renderer |
| Forza | **30 held more often** (share at 30: 46% -> 60-75%) | not its rate |

A native-60 bar is reachable for none of the four with the listed levers.
An independent expert review (NOTES section 4) reached the same order and
ceilings within a few fps. It called a FEX-class rewrite wrong scope for a
full-system guest: years of work for 1.3-1.5x on v_run, with no effect on
the sleep, the renderer or the GPU.

**Profile runs** (not queued; NOTES section 7):
- R1: Simpsons off-CPU capture, which names the sleep;
- R2: Simpsons perflog;
- R3: Nightfire perflog with `[tpc787]`;
- R4: Forza at `perf_mode=2`, to see whether the GPU leaves 401 MHz.

NEW ISSUE: vCPU sleeps on GPU-side work: 9.4 ms of Simpsons' 26.7 ms frame, and all of GTA SA's sub-30 excess; name the site and remove it
Evidence:
- Simpsons pathfind hold 2026-10-04 (Nova, 606 s): v_blk 9.4 ms/frame, r 0.96 with frame time; `[tlb68]` on-CPU 61.5% of wall time.
- GTA `1790875419-autoverdict-2123622`: v_blk 1.5 -> 9.7 ms in the 12% of windows below 30, with v_run flat.
- The first candidate, by code: the DMA_PUT write takes `pfifo.lock` (`hw/xbox/nv2a/user.c:92-95`), held by the PFIFO thread across `pgraph_process_pending_reports`. vcpuwait433 (`bc2bced563`) removed only the DMA_GET read's wait.
- Decider: an off-CPU capture of Simpsons gameplay (`capture_offcpu.sh` + `waitsite.py`).
- It blocks 45 fps on Simpsons and a held 30 on GTA.
- Plan: `docs/lanes/vcpu60/NOTES.md` rank 1.

