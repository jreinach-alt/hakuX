# lane.surfwatch382 -- stop trapping every guest store to a surface the GPU is not owed (#382)

Issue: #382 (game-visible: 50 Cent: Bulletproof's boot movies run at 10-16 fps on the Nova, floor is 20). Base: master c481e893ad.
Files: hw/xbox/nv2a/pgraph/vk/surface.c, docs/testing/predictions/surfwatch382-*.json, docs/lanes/surfwatch382/**.
Needs device: yes (Nova; Thor is free). Needs NDK: yes (this is a hw/ hunk; build the apk in a worktree, commit, request the ref).
Prediction: yes, register before the A/B, after the last rebase.

## What is known (lane.fps382, PR #385 folded; read docs/lanes/fps382/NOTES.md sec 2 and 2c first)
- Native movie rate is 30 fps (MPEG-1 640x480). The player drops every B picture when the vCPU cannot keep up.
- Renderer is 4% busy; the vCPU thread is 97% busy. Sofdec writes each picture into the colour surface at VRAM 0x021A4F80,
  which carries a CPU-access watch: every store traps (2.5M slow stores/s in the slow span vs 4k/s in the 30 fps span),
  through `surface_access_callback` under `pgraph.lock` and a `tlb_set_dirty` that cannot clear (TLB_FORCE_SLOW).
- `mem_dirty` is hard-wired false under TCG (vk/surface.c ~3473), so the watch cannot simply be dropped: it must be re-armed.

## Goal
Implement the hunk NOTES sec 2c names: on a write to a surface that owes no download, set `upload_pending`, unregister the
CPU-access callback and mark `watch_suspended`; re-register before `pgraph_vk_upload_surface_data` reads VRAM and wherever the
GPU draws to the surface. Decide, and write down, whether the re-arm is synchronous (`run_on_cpu`) or accepts at most one stale
picture (NOTES states the race). Only vk/surface.c is granted; if a second file is needed, board-request it, do not take it.

## Falsifier / arm (register before running)
A: master. B: your build. Both 240 s Nova soaks of the intro, same session, perflog apk. Must move: slow stores over 58-172 s
<= 50,000/s AND fps over that window >= 1.5x arm A's from the same session. Must not move: Texture_CPU_Update and
Texture_render_update_in_place captures (byte-identical). A stale-picture leg: no frame in the soak differs from arm A's by a
half-written picture. If slow stores fall and fps does not, say what the vCPU is doing instead (that is a result).

## Notes
- The title was reported gone from the Nova on 2026-09-26 (fps382 rerun could not run). Check first; restaging is the host's
  (stage_xiso.py, see the console game inventory), so if it is absent, say so in NOTES and do the desktop/suite half meanwhile.
- The fps of this intro varied 10.5/16.0 across runs with the same code: judge on slow stores/s and same-session ratios.
- #372 (Blinx) reads the same file for its Sd2 surface-download site (lane.blinx372c names it, does not edit): keep the hunk local.

## Done when
PR (out of draft, CI green, arm verdict posted) with the hunk, prediction and NOTES.md; #382 commented with the numbers. If the
race cannot be closed without a second file, the PR is the analysis and the board request.
