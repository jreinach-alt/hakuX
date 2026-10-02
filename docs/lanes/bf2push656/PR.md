# bf2push656: pushing BF2's changed uniform rows halves its UBO binds and saves no GPU time (#656)

State: ready

Lane: bf2push656            Issue: #656 [#433]
Base: master @ 7e1b471ef1
Files: docs/lanes/bf2push656/NOTES.md, docs/lanes/bf2push656/OUTBOX.md, docs/lanes/bf2push656/PR.md, docs/lanes/bf2push656/push656_read.py, docs/testing/predictions/bf2push656-bf2-soak.json
Prediction: docs/testing/predictions/bf2push656-bf2-soak.json (registered at 5e2d4e8f70 before the runs; judged in NOTES.md section 5)
Needs device: yes (2 Nova soaks, done: 1790983118-lane.bf2push656-3848423, 1790983118-lane.bf2push656-3848741)    Needs NDK: no (the emulator change is reverted)

## What was tried

The fix bf2ubosize433 sized: keep Battlefield 2's vertex uniform block bound
at its last upload, pass the rows that changed since then as push constants
(up to 12 keyed vec4, read through `ov4()`/`ov3()` in the generated vertex
shader), and skip a UBO bind that repeats the last one in the command buffer.
It was built (2d0d03edb6: vk/shaders.c, vk/draw.c, glsl/vsh.c), checked on the
host (NDK type-check; glslangValidator on fixed-function and program shaders
with and without the overlay), and measured in one A/B pair on the Nova.

| heavy views (BE >= 1800) | A master | B overlay |
|---|---|---|
| UBO binds per draw | 0.916 | 0.453 |
| GPU ms, median | 38.3 | 42.3 |
| GPU ms per draw (fit) | 0.0153 | 0.0149 |
| light-view GPU ms | 17.8 | 21.0 |

Half of the binds went and the per-draw GPU cost did not move. One UBO bind
is worth at most ~1-4 us of a ~15 us draw, so the per-draw rebind is not
BF2's serialized cost (bf2stall433's hypothesis U). The Nova's
`maxPushConstantsSize` is 256 B. The emulator change is reverted here and
stays in history; this PR carries the write-up, the prediction and its
reader. NOTES.md section 6 names the next measurement, the Adreno CP/SP busy
counters per draw, and the candidates it would separate.

Local checks: `python3 docs/lanes/bf2push656/push656_read.py` on the pair
and on a synthetic B logcat (constructed values read back); the prediction
JSON parses. No harness files changed, so selftest.sh does not apply. No
emulator code, so no head-commit run is needed.

Release note (none): no player-visible change; the measured change is not shipped.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
