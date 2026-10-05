# lane.vcpusleep (#507): what the vCPU sleeps on in Simpsons Hit & Run

State: ready

Lane: vcpusleep            Issue: #507
Base: master @ 425ffe1ad1 (origin/master 10f14d301d merged)
Files: docs/lanes/vcpusleep/NOTES.md, docs/lanes/vcpusleep/OUTBOX.md, docs/lanes/vcpusleep/PR.md, docs/lanes/vcpusleep/capture_simpsons_offcpu.sh, docs/lanes/vcpusleep/exact_offcpu.py, docs/lanes/vcpusleep/cpu_switches.py, docs/lanes/vcpusleep/lastrun.py, docs/testing/predictions/vcpusleep-pixels.json, docs/testing/predictions/vcpusleep-simpsons.json
Prediction: docs/testing/predictions/vcpusleep-pixels.json @ a4174c6068119136b3d1287a14fcb2b8130894b8650ac24fe4b7e67ef55f6e22 (PASS); docs/testing/predictions/vcpusleep-simpsons.json @ 92394bb4c3a3014fd2ce60caf78dfba1881b83ae4f92d19ed80d33e1f575ac41 (M, S pass; O1, O2 fail)
Needs device: no (done: 2 pixel arms, 2 host captures by lane.local)    Needs NDK: no

Release note (none): no emulator change lands. The posted DMA_PUT store (c2dfca18a1) is reverted on the branch (f6ac723228).

## What the vCPU sleeps on, and what removing it did

**R1 (simp1, master, free roam):** 79.3% of the vCPU's attributed off-CPU time
is `pfifo.lock` in `user_write`, the guest's DMA_PUT store. That is 11.2 s of
60 s, 5-10 ms a wait. The PFIFO thread holds the lock asleep.

**The fix (c2dfca18a1)** posts the store when the lock is busy, as the
hardware does. **The arm (simp2):**

| | A (master) | B (posted store) |
|---|---|---|
| vCPU off-CPU, s of 60 | 19.99 | **2.54** |
| `pfifo.lock` in USER MMIO, % of attributed | 79.3 | **3.3** |
| v_blk ms/frame | 8.85 | **0.80** |
| v_run ms/frame | 16.13 | 26.67 |
| guest idle ms/frame | 0.62 | 14.93 |
| PFIFO parked (Ri) ms/frame | 9.50 | 0.20 |
| PFIFO long sleep per frame, median ms | 8.0 | 21.3 |
| fps (whole hold) | 40.05 | **36.22** (37.88 mean of rows) |

Pixel arms: 45 of 45 captures byte-identical.

The sleep is gone, and the frames did not come back. The lock was making the
vCPU wait out the GPU. Once the store is posted, the guest finishes its frame
in 12.6 ms and then idles, spinning on the CPU. The PFIFO thread is never idle
and sleeps once per frame, about 21 ms, in what the code path makes the
frame-slot GPU fence wait. Draw work per frame is the same in both arms. The
frame is paced by the GPU side, so the change is reverted rather than folded.

waitsite.py's +-200 us pairing charged the PFIFO thread's long fence sleeps to
the short `wait_frame_submitted` wake before them. `exact_offcpu.py` pairs
exactly. R1's vCPU reading is unchanged by the exact pairing; the holder's
site is corrected.

## Next (P x win, in NOTES)

1. Name Simpsons' GPU-side frame time: per-frame GPU time and the GPU clock on
   master and c2dfca18a1. P 0.7 that it names it; it gates every Simpsons
   gain.
2. Re-arm the posted store on top of a GPU-side cut. P 0.5; vcpu60's
   45-58 fps band.
3. Guest idle without the spin. P 0.2; small in fps, real on battery.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
