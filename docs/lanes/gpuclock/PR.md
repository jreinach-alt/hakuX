# lane.gpuclock (#433): is the GPU clock-limited? GPU ms per frame against the Adreno clock, per title

State: draft

Lane: gpuclock              Issue: #433
Base: master @ 8522288a77 (merged; branched from d32c35d3ce)
Files: docs/lanes/gpuclock/NOTES.md, docs/lanes/gpuclock/OUTBOX.md, docs/lanes/gpuclock/PR.md, docs/lanes/gpuclock/WAITING, docs/lanes/gpuclock/align.py, docs/lanes/gpuclock/align_decomp.py, docs/lanes/gpuclock/capture_simpsons_gpuclock.sh, docs/lanes/gpuclock/clockdist.py, docs/lanes/gpuclock/cpu7share.py, docs/lanes/gpuclock/fixture.py, docs/lanes/gpuclock/forza-gpuclock.route, docs/lanes/gpuclock/forza-nova-gpuclock.route, docs/lanes/gpuclock/gpuclock.py, docs/lanes/gpuclock/out/cpu7share.out, docs/lanes/gpuclock/out/forza-pair1.adecomp.out, docs/lanes/gpuclock/out/forza-pair1.align.out, docs/lanes/gpuclock/out/forza-pair1.decomp.out, docs/lanes/gpuclock/out/forza-pair1.decomp.tsv, docs/lanes/gpuclock/out/forza-pair1.out, docs/lanes/gpuclock/out/forza-pair1.tsv, docs/lanes/gpuclock/out/nightfire-pair1.decomp.out, docs/lanes/gpuclock/out/nightfire-pair1.decomp.tsv, docs/lanes/gpuclock/out/nightfire-pair2.adecomp.out, docs/lanes/gpuclock/out/nightfire-pair2.align.out, docs/lanes/gpuclock/out/nightfire-pair2.decomp.out, docs/lanes/gpuclock/out/nightfire-pair2.decomp.tsv, docs/lanes/gpuclock/out/nightfire-pair2.out, docs/lanes/gpuclock/out/nightfire-pair2.tsv, docs/lanes/gpuclock/out/tron-pair1.adecomp.out, docs/lanes/gpuclock/out/tron-pair1.align.out, docs/lanes/gpuclock/out/tron-pair1.decomp.out, docs/lanes/gpuclock/out/tron-pair1.decomp.tsv, docs/lanes/gpuclock/out/tron-pair1.out, docs/lanes/gpuclock/out/tron-pair1.tsv, docs/lanes/gpuclock/queue.py, docs/lanes/gpuclock/readpairs.py, docs/lanes/gpuclock/survey.py, docs/lanes/gpuclock/synchk.py, docs/lanes/gpuclock/tron-gpuclock.route, hw/xbox/nv2a/pgraph/profile.c
Prediction: none (a measurement lane; the criteria are registered in NOTES 3 and 3b before the runs they judge)
Needs device: yes (Nova, queued in pathfind's gaps; one host session for Simpsons)    Needs NDK: no

Release note (none): telemetry only. A `[gpuclk433]` log line (GPU ms per frame; the Adreno clock and busy share, and the CPU clocks and the vCPU's core, sampled at 10 Hz); nothing a player sees changes.

## Status

Knobs (NOTES 1): `performance_mode` 0/1/2 sets the kgsl floor to 401/550/615 MHz and raises the CPU
floors as well. Nothing a shell or the app can reach sets the GPU ceiling (680) or pins the clock.
A shipped app cannot write the vendor key. The platform's Game Mode and fixed-performance paths are
probed in the Simpsons host session.

Floor 401 (stock) vs 615, Nova, same build and route (NOTES 5-6):

| title | GPU ms/frame | e | fps | J/frame | reading |
|---|---|---|---|---|---|
| Nightfire (2 pairs) | 11.24 -> 7.38 | 0.98 / 0.89 | 34.5 -> 40.0 | 0.220 -> 0.212 | clock-limited, fps follows the GPU 1:1 |
| Forza race | 24.47 -> 19.02 | 0.59 | 24.7 -> 26.9 | 0.322 -> 0.305 | on the line; replicate queued |
| Tron intro | 5.50 -> 4.02 | 0.73 (matched 0.95) | 47.4 -> 57.7 | 0.137 -> 0.151 | fps gain shared with the prime core's clock; re-run on the CPU-side build |

The stock governor held 401 MHz in every stock arm, and GPU busy never reached 90% in any of
~10,700 samples. The frame is serialized: CPU work plus a wait for the GPU. Ranked next steps are in
NOTES 6.

Waiting on: four Nova runs at 84c718ecdd (Tron pair, Forza replicate), the Simpsons host session
(lane.local), and the profile.c grant.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
