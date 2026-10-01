# lane.shaderprebuild569: P3, pre-build known pipelines on a compile pool; save the pipeline cache during play (#569)
State: draft

Lane: shaderprebuild569       Issue: #569, for #433
Base: master @ cb98d0dedc (merged as 262e30e6de)
Files: docs/lanes/shaderprebuild569/NOTES.md, docs/lanes/shaderprebuild569/OUTBOX.md, docs/lanes/shaderprebuild569/PR.md, docs/lanes/shaderprebuild569/doa_judge.json, docs/lanes/shaderprebuild569/pbjudge.py, docs/lanes/shaderprebuild569/typecheck.py, docs/testing/predictions/shaderprebuild569-doa-soak.json, docs/testing/predictions/shaderprebuild569-kabuki-soak.json, hw/xbox/nv2a/pgraph/vk/compile_worker.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/shaderprebuild569-doa-soak.json @ 79fa745ea324732947d4780217b75300d83dbf39ab43f00b5fdcaf6c55663c28; docs/testing/predictions/shaderprebuild569-kabuki-soak.json @ f3cef856a43a415495f448b53ca97e772ffb326bdb7f8119d4b2c85339204269
Needs device: yes    Needs NDK: yes

P3 of `docs/lanes/shaderplan569/NOTES.md`, items 1-5. Item 6 (shipped per-title sets) is
designed in NOTES section 6 for the second PR.

**Item 5, read first: in sync mode (the default) the pipeline cache is saved during play and
works on the next launch.** The plan's grep for "Saved pipeline cache" cannot work, because
`VK_LOG` is compiled out on Android. `[shd413]`'s `W=` climbs in all 224 soak and arm logcats
read. A later same-apk launch loads the file (`L=Y`): Arctic Thunder's 43 creates cost 4,661 ms
cold and 1-2 ms on the next three launches. What does lose the warm state:
- async mode, which never saved from the worker;
- the last 30 s of a session;
- a driver change (it wiped everything);
- any update that changes the GLSL generators.

**Built (54865a3521):**
- a pool of 3 compile workers, with pipeline jobs first and condvar waits;
- per-title pipeline records (`pipeline_keys/<title id>.bin`, module-key hashes plus the create
  state; the title id is read from the disc);
- a pre-build at renderer init that rebuilds the title's recorded pipelines into the
  VkPipelineCache on the pool, behind every draw-path job;
- pipeline cache saves on a worker: on VM stop (app pause), after a load goes quiet, at most
  every 30 s, and after a pre-build;
- a driver-only change now wipes only the pipeline cache.

Details and thread-safety reading are in NOTES section 2.

**Proof:** W1-W4 as two-launch soak pairs on the Nova, DOA then Kabuki. Both launches run with
`HAKUX_PLC_WIPE=1`, so launch 2 has the records but no cache file (W4, the falsifier). Legs are
in NOTES section 3; the judge is `pbjudge.py`.

**DOA (54865a3521; `1790791301-...-118449` cold, `1790791306-...-118725` with the pre-build):**

| leg | read | verdict |
|---|---|---|
| W4: a recorded pipeline's create with no cache file, vs cold | 32 us vs 171 ms (0.0002) | PASS |
| W1: whole-run create time | 12.6 s vs 108.9 s (0.116) | PASS |
| W1b: first fight load after `mark play` | 3.16 s vs 2.74 s (1.16) | FAIL: the route loaded a different fight |
| W2: pre-build done before `mark booted` | 640/640 in 57 s, 8.7 s before the mark | PASS |
| W3: boot fps | 59 vs 59 | PASS |

W1b's failure is the route, not the pre-build. The survey route presses START/A blind, so the
two launches reached different opponents and stages, and the frames show it. All 131 launch-2
creates after `mark play` were pipelines launch 1 never made. No recorded pipeline was slow
(NOTES section 5, attempt 3).

**Merged** `origin/master` after the uberspike569 fold (262e30e6de). NDK type-check of the
changed C files: rc 0 each.

**Waiting on:** the Kabuki pair on 262e30e6de, `1790814605-shaderprebuild569-748505` (L1) and
`1790814611-shaderprebuild569-750364` (L2). As of 2026-09-30 17:35 PDT they are queued on the
Nova behind two Nova requests. Then a head smoke, and `State: ready`.

Release note (performance): a game you have played before no longer freezes the first time a scene loads.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
