## #569 -- 2026-10-01 21:30 PDT

[lane.litcompile569] B1 GPU-per-frame replication read (registered `litcompile569-doa-gpu-rep.json`, refs bf1ecde346 / 87ceac5569, order reversed from gate 4).

Pair: fix `1-1790728885-litcompile569-2295720`, base `1-1790728890-litcompile569-2296232`. Nova, both cold, no thermal pause, GPU 615-680 MHz in play. V holds.

| leg | reading | verdict |
|---|---|---|
| R1: fight Tot fix/base <= 0.90 (refuted >= 0.95) | 26.4 / 28.6 = 0.923 | not decided |
| R2: fight fps >= 1.10 | 35.0 / 31.1 = 1.125 | PASS |
| R3: mean with gate 4's 0.821 <= 0.90 | 0.872 | PASS |

The survey route again drew different opponents in each arm, and a different blend of two fights. Per scene, unregistered:

| scene | GPU ms/frame base -> fix | J/frame base -> fix |
|---|---|---|
| clock tower fight | 28.6 -> 20.4 (0.71) | 0.247 -> 0.201 (0.81) |
| Ryu fight | 46.2 -> 28.1 (0.61) | 0.335 -> 0.273 (0.82) |

- **B1 cut GPU time per frame on every reading across both pairs:** 0.61-0.92.
- **Energy per frame fell 13-19% per scene,** so B1 is an energy lever as well as a compile-stall fix.
- **The size is not pinned down.** No pair has had the same content in both arms. A fixed-fighter, fixed-stage route would settle it.
- Gate 4's compile reading stands: pipeline creation is 2.14x faster on matched loads, and the model reads 1.00.
- The PR is `docs/lanes/litcompile569/PR.md`, now ready. Details are in NOTES.md section 11.
