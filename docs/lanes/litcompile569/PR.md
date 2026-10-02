# lane.litcompile569: gate 4 on the device and the GPU-per-frame replication (#569 B1)

State: ready

Lane: litcompile569          Issue: #569
Base: master @ 56c2a7b4a9 (merged, not rebased)
Files: docs/lanes/litcompile569/NOTES.md, docs/lanes/litcompile569/PR.md, docs/lanes/litcompile569/OUTBOX.md, docs/lanes/litcompile569/doa_energy.py, docs/lanes/litcompile569/doa_gpu_history.py, docs/lanes/litcompile569/doa_gpu_segments.py, docs/lanes/litcompile569/doa_matched.py, docs/testing/predictions/litcompile569-doa-gpu-rep.json
Prediction: docs/testing/predictions/litcompile569-doa-gpu-rep.json (registered 2026-09-29T08:02Z, before the pair ran; refs bf1ecde346 / 87ceac5569)
Needs device: no (the pair has run)    Needs NDK: no

B1 itself, the bit-exact, cheap-to-compile lighting helpers in `vsh-ff.c`, folded as #580
with gates 1-3. This branch adds no emulator code. It carries the device readings for that
fold: gate 4, the cold DOA soak pair, and the registered GPU-per-frame replication. Full
detail is in `NOTES.md`, sections 7 and 11.

## Gate 4: pipeline creation on the Nova (cold DOA soak pair)

| | base | fix | base/fix |
|---|---|---|---|
| 15 matched windows (same `kd` vector, 72 creates each): pipeline create ms | 25,758 | 12,029 | **2.14x** |
| the registered model's fix | | 12,086 | fix/model **1.00** |
| VS stage ms | 16,271 | 3,957 | 4.11x |
| whole run, ms per create (L1) | 359.1 | 180.9 | 1.98x |

- **B1 halves DOA's pipeline creation time on the device.** On the same content, the
  registered model predicts the fix exactly.
- **L4 (VS 4.8-8.1x) fails at 3.48x.** The feedback API attributes stage time differently
  from the host. The pipeline total still meets the model.

## Replication: GPU time per frame (registered `litcompile569-doa-gpu-rep.json`)

Pair: fix `1-1790728885-litcompile569-2295720`, base `1-1790728890-litcompile569-2296232`.
Nova, cold, no thermal pause, GPU at 615-680 MHz in play, 75 and 66 fight lines.

| leg | reading | verdict |
|---|---|---|
| R1: fight Tot fix/base <= 0.90, refuted at >= 0.95 | 26.4 / 28.6 = 0.923 | not decided (in the registered band) |
| R2: fight fps >= 1.10 | 35.0 / 31.1 = 1.125 | PASS |
| R3: mean with gate 4's pair <= 0.90 | (0.821 + 0.923) / 2 = 0.872 | PASS |

The survey route drew a different opponent again, and a different blend of two fights in
each arm. Per scene (spans placed from the route frames, unregistered):

| scene | fps b -> f | GPU ms/frame b -> f | J/frame b -> f |
|---|---|---|---|
| clock tower fight | 31.9 -> 45.1 | 28.6 -> 20.4 (0.71) | 0.247 -> 0.201 (0.81) |
| Ryu fight | 20.7 -> 33.3 | 46.2 -> 28.1 (0.61) | 0.335 -> 0.273 (0.82) |

- **The sign held on every reading across both pairs.** B1 cut GPU time per frame in every
  case: 0.61-0.92 across scenes and pools.
- **It is an energy lever as well as a compile-stall fix.** Energy per frame falls 13-19%
  per scene. Over the whole run, `title_verdict.py` reads 0.309 -> 0.268 J/frame.
- **Its size is not pinned down.** No pair has had the same content in both arms. That
  needs a fixed-fighter, fixed-stage route, and a new registration.

## Local checks (no CI while GitHub is suspended)

- `docs/testing/preflight.sh --allow-tracker` on the head: rc 0, "preflight passed". Every gate
  passed except coverage, which did not run because it needs gh, and gh returns 403.
- `python3 -m py_compile` on the four `doa_*.py` scripts: OK.
- No harness file and no emulator file changed, so there is no selftest or dispatch-run
  requirement for the fold.

Release note (none): device measurements of the already-folded B1 (#580); no emulator code
changes in this branch.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
