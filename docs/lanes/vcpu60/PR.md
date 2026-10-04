# lane.vcpu60 (#507): what it takes to get Simpsons, GTA SA, Nightfire and Forza to 60 fps

State: ready

Lane: vcpu60            Issue: #507
Base: master @ 40b62fd533
Files: docs/lanes/vcpu60/NOTES.md, docs/lanes/vcpu60/OUTBOX.md, docs/lanes/vcpu60/PR.md, docs/lanes/vcpu60/decompose4.tsv, docs/lanes/vcpu60/bands.py
Prediction: none: analysis-only
Needs device: no    Needs NDK: no

A planning lane. It gives a frame budget per title, a ranked plan by P x win, and a ceiling per title.

**No ranked combination of JIT items reaches 60 on any of the four titles.**
Priced with memfast's measured ratios, the vcpuplan list is 4-10% of the
vCPU's on-CPU time. Simpsons would need 58% for 60.

| title | target on file | bound (Nova) | ceiling |
|---|---|---|---|
| Simpsons | none (paced for 60 by its flips) | vCPU on-CPU 17.2 ms + vCPU asleep 9.4 ms of a 26.7 ms frame | 45-58 with ranks 1-2; 39-42 without rank 1 |
| GTA SA | 30 (its own limiter) | at the cap in 88% of windows; the drops are the vCPU sleep | 30 held |
| Nightfire | 60 (press) | the render thread, 30.5 of a 33.8 ms frame | 30-40 |
| Forza | 30 (IGN) | the GPU side in its slow half (GPU at 401 MHz) | 30 held more often |

The ranks:
1. Remove the vCPU's sleep on GPU-side work. First candidate: the DMA_PUT
   write under `pfifo.lock`. P 0.4.
2. The JIT program inside TCG: the IBC probe, cross-page chaining and a RAS,
   then regions and SSE. P 0.4.
3. Nightfire's render thread. P 0.35.
4. A static GPU clock floor for Forza. P 0.3.

An independent expert review agrees on the order and ceilings. It disagrees
on the dispatch discount, which rank 2's one-binary pair decides. The lane
lists four profile runs to queue.

Release note (none): docs only.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
