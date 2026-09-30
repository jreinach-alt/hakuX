# lane.uberspike569: uber pre-raster libraries under GPL, the no-stall first draw (#569)
State: draft

Lane: uberspike569            Issue: #569
Base: master @ a3681ccb0b
Files: docs/lanes/uberspike569/BUILD.md, docs/lanes/uberspike569/NOTES.md, docs/lanes/uberspike569/OUTBOX.md, docs/lanes/uberspike569/PR.md, docs/lanes/uberspike569/host/find_results.py, docs/lanes/uberspike569/host/k1_windows.txt, docs/lanes/uberspike569/host/pr_body.py, docs/lanes/uberspike569/host/predinfo.py, docs/lanes/uberspike569/host/register_gpl_kabuki.py, docs/lanes/uberspike569/host/register_gpl_soak.py, docs/lanes/uberspike569/host/requeue3.sh, docs/lanes/uberspike569/host/smoke_read.py, docs/lanes/uberspike569/host/typecheck.py, docs/lanes/uberspike569/host/vsh_fields.py, docs/lanes/uberspike569/host/vshuber/.gitignore, docs/lanes/uberspike569/host/vshuber/Makefile, docs/lanes/uberspike569/host/vshuber/vcarve.py, docs/lanes/uberspike569/host/vshuber/vshcheck.py, docs/lanes/uberspike569/host/vshuber/vshhost.c, docs/lanes/uberspike569/host/vshuber/vsrender.c, docs/lanes/uberspike569/host/waiting-note.md, docs/lanes/uberspike569/host/wipe-note.md, docs/lanes/uberspike569/kabjudge.py, docs/lanes/uberspike569/results/kabjudge-k1-self.json, docs/lanes/uberspike569/results/vshcheck-doa-rand300.tsv, docs/lanes/uberspike569/uberjudge.py, docs/testing/nv2a_index.json, docs/testing/predictions/uberspike569-gpl-doa-soak.json, docs/testing/predictions/uberspike569-gpl-kabuki-soak.json, docs/testing/predictions/uberspike569-gpl-pixels.json, hw/xbox/nv2a/pgraph/glsl/meson.build, hw/xbox/nv2a/pgraph/glsl/vsh-ff.c, hw/xbox/nv2a/pgraph/glsl/vsh-ff.h, hw/xbox/nv2a/pgraph/glsl/vsh-prog.c, hw/xbox/nv2a/pgraph/glsl/vsh-prog.h, hw/xbox/nv2a/pgraph/glsl/vsh-uber.c, hw/xbox/nv2a/pgraph/glsl/vsh-uber.h, hw/xbox/nv2a/pgraph/glsl/vsh.c, hw/xbox/nv2a/pgraph/glsl/vsh.h, hw/xbox/nv2a/pgraph/vk/compile_worker.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/instance.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/uberspike569-gpl-pixels.json @ c5c0e63aed4e03cc3a7329f381d244b4be579590c3188c5751810ea9d782eeaa; docs/testing/predictions/uberspike569-gpl-doa-soak.json @ 642189382de2d3efb358120b51dc491ca6fc064c94217489c1dd4340026ab7ba; docs/testing/predictions/uberspike569-gpl-kabuki-soak.json @ dad936499521e81662f0fa53b678eacb27c5d38d9576fd6ad5bbfb958eaea6e6
Needs device: yes    Needs NDK: yes

Stands in for PR #618 while GitHub is suspended. The design, the build and the host checks are in
`docs/lanes/uberspike569/BUILD.md`. The spike (fragment ubershader, state-space map, E/P/C) is in
`NOTES.md` beside it.

**What it builds.** `HAKUX_GPL` gets two more values; the default stays 0, as on master.
- **3, the ladder.** On a pipeline miss whose vertex state the uber stage covers, the draw
  fast-links a prebuilt uber pre-raster library (`glsl/vsh-uber.c`: a vertex-program interpreter
  plus a uniform fixed-function path, one module per family) and draws this frame. The worker
  then builds the specialised monolithic pipeline, and it is swapped in at the next bind.
- **4, held.** The uber link is kept for every covered draw. For the exactness and GPU-cost arms
  only.

**Host checks.** NDK clang type-check of every changed C file: rc 0, no new warnings. Lavapipe
exactness (`host/vshuber/vshcheck.py`): DOA's 46 vertex states 46/46 byte-identical, 150 random
fixed-function states 150/150, and 150 random programs 117/150. The 33 that differ are signed
zeros or 1-2 ulp, from constant folding the interpreter cannot see (BUILD.md 4.1).

**Device legs, registered, waiting on the Nova** (BUILD.md sections 6-11):

| leg | arms | state |
|---|---|---|
| E, pixel-inert with the uber stage held (36 suites, 2 runs) | A 23543417aa, H 6bec23c3f4 | A ran (`1790724542-uberspike569-1360739`); H queued |
| N1-N3, G: DOA cold soak, draw-path create and uber GPU cost | A / B 752b4f0f7b / H | queued |
| K1-K3: Kabuki cold fight, create and longest flip gap | A 8b15159b2f / B2 d0152f9c44 | queued |

**Local checks in place of CI:** NDK type-check (`host/typecheck.py`) rc 0; `uberjudge.py
--selftest` and `kabjudge.py --selftest` pass. No harness files are changed, so
`selftest.sh` does not apply. A dispatch run at the head commit is queued before `State: ready`.

Release note (none): debug-only switch, default off

🤖 Generated with [Claude Code](https://claude.com/claude-code)
