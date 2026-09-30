# lane.uberspike569: uber pre-raster libraries under GPL, the no-stall first draw (#569)
State: ready

Lane: uberspike569            Issue: #569
Base: master @ 2c59b7bbba (merged in at 8b15159b2f; #581 and #594 folded)
Files: docs/lanes/uberspike569/BUILD.md, docs/lanes/uberspike569/NOTES.md, docs/lanes/uberspike569/OUTBOX.md, docs/lanes/uberspike569/PR.md, docs/lanes/uberspike569/host/doa_series.py, docs/lanes/uberspike569/host/find_results.py, docs/lanes/uberspike569/host/k1_windows.txt, docs/lanes/uberspike569/host/list_results.py, docs/lanes/uberspike569/host/pr_body.py, docs/lanes/uberspike569/host/predinfo.py, docs/lanes/uberspike569/host/register_gpl_kabuki.py, docs/lanes/uberspike569/host/register_gpl_soak.py, docs/lanes/uberspike569/host/requeue3.sh, docs/lanes/uberspike569/host/show_result.py, docs/lanes/uberspike569/host/smoke_read.py, docs/lanes/uberspike569/host/typecheck.py, docs/lanes/uberspike569/host/vsh_fields.py, docs/lanes/uberspike569/host/vshuber/.gitignore, docs/lanes/uberspike569/host/vshuber/Makefile, docs/lanes/uberspike569/host/vshuber/vcarve.py, docs/lanes/uberspike569/host/vshuber/vshcheck.py, docs/lanes/uberspike569/host/vshuber/vshhost.c, docs/lanes/uberspike569/host/vshuber/vsrender.c, docs/lanes/uberspike569/host/waiting-note.md, docs/lanes/uberspike569/host/wipe-note.md, docs/lanes/uberspike569/kabjudge.py, docs/lanes/uberspike569/results/ab-e.txt, docs/lanes/uberspike569/results/doa-series.txt, docs/lanes/uberspike569/results/kabjudge-k.json, docs/lanes/uberspike569/results/kabjudge-k1-self.json, docs/lanes/uberspike569/results/uberjudge-doa.json, docs/lanes/uberspike569/results/vshcheck-doa-rand300.tsv, docs/lanes/uberspike569/uberjudge.py, docs/testing/nv2a_index.json, docs/testing/predictions/uberspike569-gpl-doa-soak.json, docs/testing/predictions/uberspike569-gpl-kabuki-soak.json, docs/testing/predictions/uberspike569-gpl-pixels.json, hw/xbox/nv2a/pgraph/glsl/meson.build, hw/xbox/nv2a/pgraph/glsl/vsh-ff.c, hw/xbox/nv2a/pgraph/glsl/vsh-ff.h, hw/xbox/nv2a/pgraph/glsl/vsh-prog.c, hw/xbox/nv2a/pgraph/glsl/vsh-prog.h, hw/xbox/nv2a/pgraph/glsl/vsh-uber.c, hw/xbox/nv2a/pgraph/glsl/vsh-uber.h, hw/xbox/nv2a/pgraph/glsl/vsh.c, hw/xbox/nv2a/pgraph/glsl/vsh.h, hw/xbox/nv2a/pgraph/vk/compile_worker.c, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/instance.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/shaders.c
Prediction: docs/testing/predictions/uberspike569-gpl-pixels.json @ c5c0e63aed4e03cc3a7329f381d244b4be579590c3188c5751810ea9d782eeaa; docs/testing/predictions/uberspike569-gpl-doa-soak.json @ 642189382de2d3efb358120b51dc491ca6fc064c94217489c1dd4340026ab7ba; docs/testing/predictions/uberspike569-gpl-kabuki-soak.json @ dad936499521e81662f0fa53b678eacb27c5d38d9576fd6ad5bbfb958eaea6e6
Needs device: yes    Needs NDK: yes

This PR stands in for PR #618 while GitHub is suspended. The design, the build, the host checks
and the device verdict are in `docs/lanes/uberspike569/BUILD.md` (section 12 has the verdict).
The spike (the fragment ubershader, the state-space map, and legs E/P/C) is in `NOTES.md` beside
it.

**What it builds.** `HAKUX_GPL` gets two more values; the default stays 0, as on master.
- **3, the ladder.** On a pipeline miss whose vertex state the uber stage covers, the draw
  fast-links a prebuilt uber pre-raster library and draws this frame. The library is
  `glsl/vsh-uber.c`: a vertex-program interpreter plus a uniform fixed-function path, one module
  per family. The worker then builds the specialised monolithic pipeline, and it is swapped in at
  the next bind.
- **4, held.** The uber link is kept for every covered draw. This is for the exactness and GPU-cost
  arms only.

**Device legs, all on the Nova except E's A arm (Thor):**

| leg | registered | measured | verdict |
|---|---|---|---|
| E: 36 suites, uber stage held | every capture inside its band | 1317/1317 byte-identical; links=2103, uncovered=0 | **PASS** |
| N1: DOA draw-path create, B/A | <= 0.25 | 0.10 (26.2 s -> 2.7 s) | **PASS** |
| N2: DOA first fight load, B/A | <= 0.20 | 0.018 (2.9 s -> 52 ms) | **PASS** |
| N3: DOA stall windows | <= cold 14 + 2 | 5 | **PASS** |
| G: uber held, GPU ms and gfps vs A | <= 1.5x, >= 0.8x | 3.77x, 0.29x | **FAIL** |
| K1: Kabuki longest flip gap | < 5 s | 0.70 s (A 4.99 s) | pass (not discriminating) |
| K2: Kabuki fight create, B/A | <= 0.25 | 0.0002 (133 s -> 27 ms) | **PASS** |
| K3: Kabuki longest flip gap, B/A | <= 0.50 | 0.14 | **PASS** |

**The verdict.** The ladder gives a first draw with no stall for every miss whose (family, GS,
raster, formats) combination already has an uber library. That covers all of Kabuki's fight and
all of DOA's misses except its 14 cold combinations. While the uber stage stands in, it costs GPU
time. Held on every draw, DOA runs at 3.8x the GPU ms per frame. That is an upper bound, because
the non-LTO fast link's own cost is inside it and was never measured apart (gpl569 D1 was void).
In ladder use on a cold cache, DOA's play span runs at 0.79x the median fps, recovering as the
swaps land. The default is unchanged. Next, ranked: an arm that splits link cost from interpreter
cost; persisted uber combinations; `NoContraction`; then the default flip, on the owner's
decision (BUILD.md 12.4).

**Result dirs:**
- E: `1790724542-uberspike569-1360739` (A) and `1-1790730667-uberspike569-2559646` (H).
- DOA A/B/H: `1-1790730667-uberspike569-2559714`, `1-1790730668-uberspike569-2559794`,
  `1-1790730669-uberspike569-2559870`.
- Kabuki A/B2: `1-1790730670-uberspike569-2559946`, `1-1790730670-uberspike569-2560023`.

**Local checks in place of CI (2026-09-30, at this head):**
- NDK clang type-check of all eight changed C files (`host/typecheck.py`): rc 0. The only
  warnings are in lines that predate this branch.
- `uberjudge.py --selftest` and `kabjudge.py --selftest`: ok.
- No harness files are changed, so `selftest.sh` does not apply.
- A DOA smoke at the default (GPL 0) is queued on this head commit, as `offline_fold.py`
  requires.

Release note (none): debug-only switch, default off

🤖 Generated with [Claude Code](https://claude.com/claude-code)
