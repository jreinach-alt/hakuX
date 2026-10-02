# bf2ubosize433: size Battlefield 2's per-draw uniform-block churn before the push-constant fix (#433)

State: draft

Lane: bf2ubosize433            Issue: #433
Base: master @ 66bce0c222
Files: docs/lanes/bf2ubosize433/NOTES.md, docs/lanes/bf2ubosize433/OUTBOX.md, docs/lanes/bf2ubosize433/PR.md, docs/lanes/bf2ubosize433/ubosz_read.py, docs/lanes/bf2ubosize433/ubosz_selftest.py, docs/testing/predictions/bf2ubosize433-bf2-ubosz.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/bf2ubosize433-bf2-ubosz.json (registered before the run; not yet judged)
Waiting: Nova soak 1790958948-lane.bf2ubosize433-1976093 (ref d9729d6250), queued behind lane.pathfind's Nova hold
Needs device: yes (one Nova soak)    Needs NDK: yes (perflog build)

## What this adds

A perflog-only counter of how much of the uniform block changes between
consecutive uploads (`ubosz[...]` on hakuX-stall, every 60 flips). It reports
histograms of changed 16-byte chunks of the VS+PS layouts and of changed
vertex-constant rows, the binding switches, a replayed 8/16-vec4
push-constant policy, and UBO binds. It is checked on the host
(`ubosz_selftest.py`), and the judge (`ubosz_read.py`) is checked against a
synthetic logcat. See NOTES.md sections 1-3.

Release note (none): instrumentation, compiled only in NV2A_PERF_LOG builds.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
