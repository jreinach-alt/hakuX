# lane.shaderprebuild569: P3, pre-build known pipelines on a compile pool; save the pipeline cache during play (#569)
State: ready

Lane: shaderprebuild569       Issue: #569, for #433
Base: master @ 70c9e96876 (merged as ff3693193d; earlier merge 262e30e6de)
Files: docs/lanes/shaderprebuild569/NOTES.md, docs/lanes/shaderprebuild569/OUTBOX.md, docs/lanes/shaderprebuild569/PR.md, docs/lanes/shaderprebuild569/doa_judge.json, docs/lanes/shaderprebuild569/kabuki_judge.json, docs/lanes/shaderprebuild569/pbjudge.py, docs/lanes/shaderprebuild569/typecheck.py, docs/testing/predictions/shaderprebuild569-doa-soak.json, docs/testing/predictions/shaderprebuild569-kabuki-soak.json, hw/xbox/nv2a/pgraph/vk/compile_worker.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/shaderprebuild569-doa-soak.json @ 79fa745ea324732947d4780217b75300d83dbf39ab43f00b5fdcaf6c55663c28; docs/testing/predictions/shaderprebuild569-kabuki-soak.json @ f3cef856a43a415495f448b53ca97e772ffb326bdb7f8119d4b2c85339204269
Needs device: yes    Needs NDK: yes

P3 of `docs/lanes/shaderplan569/NOTES.md`, items 1-5. Item 6 (shipped per-title sets) is
designed in NOTES section 6, for the second PR.

**Item 5, read first: in sync mode (the default) the pipeline cache is saved during play, and it
works on the next launch.** The plan's grep for "Saved pipeline cache" cannot work: `VK_LOG` is
compiled out on Android. `[shd413]`'s `W=` climbs in all 224 soak and arm logcats read. A later
launch on the same apk loads the file (`L=Y`). Arctic Thunder's 43 creates cost 4,661 ms cold, and
1-2 ms on each of the next three launches. What does lose the warm state:
- async mode, which never saved from the worker;
- the last 30 s of a session;
- a driver change, which wiped everything;
- any update that changes the GLSL generators.

**Built:**
- a pool of 3 compile workers, with pipeline jobs first and condvar waits;
- per-title pipeline records (`pipeline_keys/<title id>.bin`): module-key hashes plus the create
  state, with the title id read from the disc;
- a pre-build at renderer init that rebuilds the title's recorded pipelines into the
  VkPipelineCache on the pool, behind every draw-path job;
- pipeline cache saves from a worker: on VM stop (app pause), after a load goes quiet, at most
  every 30 s, and after a pre-build;
- a driver-only change now wipes only the pipeline cache.

The default is on. `HAKUX_PREBUILD=0` turns the pre-build off, and records are still written.
The GPL/uber path (lane.uberspike569) is untouched. NOTES section 2 has the details and the
thread-safety reading.

**Proof:** W1-W4 as two-launch soak pairs on the Nova, DOA then Kabuki. Both launches run with
`HAKUX_PLC_WIPE=1`, so launch 2 has the records but no cache file: that is W4, the falsifier.
The judge is `pbjudge.py`.

| leg | DOA (54865a3521) | Kabuki (262e30e6de) |
|---|---|---|
| W4: a recorded pipeline's create with no cache file, vs cold | 32 us vs 171 ms: PASS | 25.6 us vs 174 ms: PASS |
| W1: whole-run create time | 12.6 s vs 108.9 s (0.116): PASS | 14.4 s vs 134.7 s (0.107): PASS |
| W1b: first fight load after `mark play` (DOA only) | 3.16 s vs 2.74 s: FAIL, the route loaded a different fight | n/a |
| W2: pre-build done before the boot mark | 640/640, 8.7 s before: PASS | 810/810 in 73 s, 156 s before: PASS |
| W3: boot fps | 59 vs 59: PASS | 59 vs 59: PASS |

Runs:
- DOA: `1790791301-...-118449` (cold), `1790791306-...-118725` (with the pre-build).
- Kabuki: `1790814605-...-748505` (cold), `1790823465-...-2896600` (with the pre-build).
- `1790814611-...-750364` is VOID: the Nova's adb link dropped at 77 s. The retry ran on the same
  ref with no Nova run in between.

DOA's W1b failure is the route, not the pre-build. The survey route presses START/A blind, so
the two launches met different opponents, and the frames show it. None of L2's 131 creates after
`mark play` was in L1's records.

Kabuki's route takes a fixed path. There, the 394 recorded pipelines met after the mark cost
10 ms in total. The 14.4 s L2 still paid was 83 pipelines L1 never made (random CPU fighters and
arenas); item 6's harvested sets are what cover those.

**Local checks in place of CI (2026-09-30, at ff3693193d; `hw/` there is byte-identical to
262e30e6de):**
- NDK clang type-check (`typecheck.py`) of `compile_worker.c`, `draw.c`, `renderer.c`,
  `shaders.c` and `glsl.c`: rc 0 each.
- `pbjudge.py --selftest`: ok.
- `docs/testing/preflight.sh --allow-tracker`: passed. The coverage gate did not run (`gh` 403),
  so that gate is not checked.
- A Kabuki smoke of 180 s at the default env is queued on this head commit (purpose
  `#569 head smoke at <head>`), as `offline_fold.py` requires.

Release note (performance): a game you have played before no longer freezes the first time a scene loads.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
