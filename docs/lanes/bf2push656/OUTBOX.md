# lane.bf2push656 outbox

## #656 -- 2026-10-02 16:40 PDT

[lane.bf2push656] I built the push-constant fix and measured it. It removes half of BF2's UBO binds and saves no GPU time, so the per-draw rebind is not what makes BF2's draws slow. The change is reverted on the branch; it stays in history at 2d0d03edb6.

**What was built:** the vertex uniform block stays bound at its last upload. Rows that changed since then go to the vertex shader as push constants: up to 12 (key, value) pairs, read through `ov4()`/`ov3()` in the generated GLSL. A UBO bind that repeats the last one is skipped. The prediction `docs/testing/predictions/bf2push656-bf2-soak.json` was registered before the runs.

**Pilot pair, Nova, bf2mc 420 s, perflog** (A `1790983118-lane.bf2push656-3848423` master 7e1b471ef1, B `...-3848741`):

| | A | B |
|---|---|---|
| UBO binds per draw, heavy views | 0.916 | 0.453 |
| heavy-view GPU ms, median | 38.3 | 42.3 |
| GPU ms per draw (fit) | 0.0153 | 0.0149 |
| light-view GPU ms | 17.8 | 21.0 |

- The Nova's `maxPushConstantsSize` is 256 B (read off the device at init).
- Per registered leg: P0 PASS. M1 FAIL on the rebind rate (0.57 against 0.45); its binds-per-draw half passes (0.495). P1, reported only: heavy GPU B/A 1.10. R1 PASS, C0 PASS.
- Bound: one UBO bind costs at most ~1-4 us of a heavy-view draw's ~15 us. bf2stall433's hypothesis U is refuted as the main cause.
- Side finding (CPU, not chased): `shader_bindings_changed` stays set after a shader switch until the next shader-state change. Every draw in between gets a new UBO descriptor set and misses the super fast path.

**Next:** measure whether the GPU front end is busy or waiting per draw (Adreno CP/SP busy counters, one read-only soak) before trying another lever. Details are in docs/lanes/bf2push656/NOTES.md sections 5-6.

Runs used: 2 of 6. The pixel and GTA arms were never registered and never queued.
