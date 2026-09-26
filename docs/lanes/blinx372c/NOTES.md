# lane.blinx372c: the surface-download site behind Blinx's demo wait (#372)

Base master 6c25a829ef. Title 4D530013 (Blinx: The Time Sweeper), Ayn Thor.
Predecessors: lane.blinx372 (PR #374), lane.blinx372b (PR #381, which added the
allow-list tags).

## 1. Blocked: the live dispatcher still drops `hakuX-stall`

Checked 2026-09-26 04:55-05:20 PDT, before any run was queued:

| where | has `hakuX-stall:I`? |
|---|---|
| master `docs/testing/dispatcher.sh` LOGCAT_SPEC | yes (PR #381) |
| `/home/justin/hakuX` (the dispatcher's `$TREE`), HEAD c4d541bd72 | **no**, 52 commits behind origin/master |
| `$DISPATCH_DIR/bin/dispatcher.sh` (the worker snapshot) | **no** |
| `logcat.spec` of the newest result (`z-b-v040j1-029-Fog_exceptional_value`) | **no** (ends `hakuX-pace:I libc:F ...`) |
| any `logcat*.txt` under dispatch/results or perf/ | 0 files carry a `hakuX-stall` line |

`logs/dispatcher-update.log` shows that the last fast-forward was at 03:17 PDT
(to c4d541bd72), before #381 folded. `LOGCAT_SPEC_OVERRIDE` is part of the
worker's environment, and a request cannot set it. So no request this lane can
queue would carry the line. I did not queue a soak (brief step 1).

**Unblocks it:** `host-tools/dispatcher_update_window.sh`, the host's job (hostops
poll item 1, which runs when the tree is more than 20 commits behind for two
ticks). After it runs, `git -C /home/justin/hakuX merge-base --is-ancestor
<#381 fold> HEAD` succeeds, and a new result's `logcat.spec` contains
`hakuX-stall`.

Queue after that (one run; rerun once if the demo fps falls outside 12-20):
`request.sh --who blinx372c --title 4D530013-Blinx_The_Time_Sweeper.xiso.iso
--seconds 240 --device thor --perflog --frames-every 30 --ref 6c25a829ef
--no-expect "soak; judged by stallread.py against blinx372c-demo-soak.json"`
To read it:
`python3 docs/lanes/blinx372c/stallread.py <logcat> --window 135,265 --spec
<result.json> --prediction docs/testing/predictions/blinx372c-demo-soak.json`

## 2. Registered before the soak

`docs/testing/predictions/blinx372c-demo-soak.json` (sha256 475ff4d9...).
It has instrument legs (M0: the spec, the line count, pres+flip == 60 on every
line) and the impossible row (P1: sd == dl+cDef+pDl+dDl). The remaining legs:
P2 rate 1.2-2.0 per frame, P3 one site >= 80%, P4 a guess that the top site is
**cDef**, and P5 demo fps 12-20. The prediction also maps each site onto the
brief's falsifier, before the data exists.

`stallread.py --selftest` builds a line from draw.c's own format string and
checks the regex, the per-frame normalisation and the P1 mismatch row.

## 3. From the code (6c25a829ef), corrections to what this lane inherited

- **`pDl` is not display-only.** blinx372b's NOTES expected pDl ~ 0 on the Thor
  because it presents through AHB. But `pgraph_vk_process_pending_downloads`
  (surface.c) is also what `surface_access_callback`, the CPU-access watch,
  waits on. Any guest load or store to a surface with
  `draw_dirty && download_generation != draw_generation` sets
  `download_pending`, kicks pfifo and blocks the vCPU until the renderer
  finishes a SURFACE_DOWN (counted as `pDl`). A non-zero pDl on the Thor
  therefore means the guest CPU touched a GPU-drawn surface. That is the brief's
  "own readback" world if the access is a read. If it is a write, it is a
  conservative download before the write. The `hakuX-stall` line has no
  read/write split, so if pDl wins, the next instrument is that split: one
  counter in surface_access_callback, in vk/surface.c, which is
  lane.surfwatch382's file.
- **`S2T:x/0` carries no information in its second field on vk.**
  `NV2A_PROF_SURF_TO_TEX_FALLBACK` is incremented only in `pgraph/gl/surface.c`.
  The vk renderer never increments it, so "6-7/0" does not exclude texture.c's
  incompatible-shape download (`!surface_to_texture && surface->draw_dirty` in
  texture_bind). stallread.py prints that branch as `dif.tex` (dirtyIf minus
  the named dif fields).
- **A fifth GPU wait sits outside `Finish sd`.** The range path
  (`pgraph_vk_download_surfaces_in_range_if_dirty`) calls `vkWaitForFences`
  directly when earlier deferred downloads were already submitted
  (`cDefC`). That wait is not a pgraph_vk_finish, so neither `Sd` nor the
  phase line's `Fen` counts it. If cDefC is non-zero in the demo, the 32 ms
  "two waits" figure understates the total.
- `texture_bind` skips direct s2t when the surface has `upload_pending`
  (a CPU write since the last upload). If the surface is also draw_dirty,
  that sends it down the synchronous `dl` branch. So a CPU write to a render
  target that is later sampled produces `dl` via `dif.tex`, not `pDl`. The
  watch path and the texture path interact, and both live in vk/surface.c
  and vk/texture.c.

## 4. The hunk, by site (named, priced as a bound; no hw/ grant)

Which one applies depends on the soak. All four are written down now so that
the reading cannot choose among them after the fact.

| top site | hunk | overlaps surfwatch382's watch code? |
|---|---|---|
| cDef (dif oth) | texture.c texture_bind: when the texture range lies inside a draw-dirty surface at an offset, sample the VkImage with a subresource offset instead of a deferred download | no (texture.c) |
| dl (dif tex) | texture.c: a GPU-side shape/format conversion copy for the incompatible-shape case, instead of download + re-upload | no (texture.c) |
| pDl, reads | none: the guest reads what the GPU drew. Not removable. | -- |
| pDl, writes | surface.c surface_access_callback: on a write that covers the whole surface, retire the generation without downloading | **yes**, the same function |

Price (bound, not value): lane.blinx372 measured 32.1 ms/frame of synchronous
finish waits in a 62-68 ms frame (Sd2 + St1), with a ceiling near 27 fps if both
go. Removing only the Sd site removes at most the Sd share of the fence time.
That is `Fen` / (sd + stl) per wait from the phase line, so stallread.py
prints `ms_per_wait_upper`, an upper bound. It is not a measured per-reason
time, because the phase line does not split Fen by reason. Waits do not simply
subtract when the renderer is 96% busy: the GPU work still has to finish
before the next dependent read. So the fps gain is bounded above by
68/(68 - 2 x ms_per_wait) and could be much less.

## Do not repeat

- Do not queue the soak until a result's `logcat.spec` shows `hakuX-stall`.
  A merged allow-list is not a deployed one.
- Do not read pDl ~ 0 as expected on AHB devices (section 3).
- Do not read S2T's `/0` as "no fallback" on vk.
