# bf2ubosize433: size Battlefield 2's per-draw uniform-block churn before the push-constant fix (#433)

State: ready

Lane: bf2ubosize433            Issue: #433
Base: master @ 66bce0c222
Files: docs/lanes/bf2ubosize433/NOTES.md, docs/lanes/bf2ubosize433/OUTBOX.md, docs/lanes/bf2ubosize433/PR.md, docs/lanes/bf2ubosize433/ubosz_read.py, docs/lanes/bf2ubosize433/ubosz_selftest.py, docs/testing/predictions/bf2ubosize433-bf2-ubosz.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/bf2ubosize433-bf2-ubosz.json (registered before the run; judged PUSH -- F16 0.917, R16 0.413, see NOTES.md section 6)
Needs device: yes (one Nova soak, done: 1790958948-lane.bf2ubosize433-1976093)    Needs NDK: yes (perflog build)

## What this adds

A perflog-only counter of how much of the uniform block changes between
consecutive uploads (`ubosz[...]` on hakuX-stall, every 60 flips). It reports
histograms of changed 16-byte chunks of the VS+PS layouts and of changed
vertex-constant rows, the binding switches, a replayed 8/16-vec4
push-constant policy, and UBO binds. It is checked on the host
(`ubosz_selftest.py`), and the judge (`ubosz_read.py`) is checked against a
synthetic logcat. See NOTES.md sections 1-3.

## Result

One Nova soak (bf2mc route, 420 s, ref d9729d6250, no `hw/` change since)
judged **PUSH**: in BF2's heavy views, 92% of same-binding uniform uploads
change <= 16 vec4 (median 3-4), and even counting shader-binding switches
(36% of uploads) a 16-vec4 push-constant policy would leave only 41% of
uploads still forcing a UBO rebind. The push-constant fix bf2stall433 named
is justified. This lane does not build it: a successor brief is posted to
`OUTBOX.md` (forge #656) naming the files, the budget (Nova
`maxPushConstantsSize`, believed 256 B, unverified), the concrete registers
that churn (`c112`-`c115`, `c96`-`c105`, the `ltc*` uniforms), and the
switch-share caveat. NOTES.md section 6 has full numbers.

Release note (none): instrumentation, compiled only in NV2A_PERF_LOG builds.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
