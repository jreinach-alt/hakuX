# lane.shaderprebuild569: P3, pre-build known pipelines on a compile pool; save the pipeline cache during play (#569)
State: draft

Lane: shaderprebuild569       Issue: #569, for #433
Base: master @ 2c59b7bbba
Files: docs/lanes/shaderprebuild569/NOTES.md, docs/lanes/shaderprebuild569/OUTBOX.md, docs/lanes/shaderprebuild569/PR.md, docs/lanes/shaderprebuild569/pbjudge.py, docs/lanes/shaderprebuild569/typecheck.py, docs/testing/predictions/shaderprebuild569-doa-soak.json, docs/testing/predictions/shaderprebuild569-kabuki-soak.json, hw/xbox/nv2a/pgraph/vk/compile_worker.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/shaderprebuild569-doa-soak.json @ 79fa745ea324732947d4780217b75300d83dbf39ab43f00b5fdcaf6c55663c28; docs/testing/predictions/shaderprebuild569-kabuki-soak.json @ 4bd7cdb383d595e71b847af7acb37e5b54b2d8cea316c44f5848255f830d8cf4
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
in NOTES section 3; the judge is `pbjudge.py`. The DOA pair is queued (NOTES section 4); no result yet.

**Waiting on:** (a) DOA requests `1790791301-shaderprebuild569-118449` and
`1790791306-shaderprebuild569-118725`, still queued on the Nova as of 2026-09-30 14:16 PDT;
(b) the fold of `lane/uberspike569-gpl`, which holds `compile_worker.c` until then. A trial
merge resolves in three edits and type-checks clean (NOTES section 4, "Attempt 2").

Release note (performance): a game you have played before no longer freezes the first time a scene loads.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
