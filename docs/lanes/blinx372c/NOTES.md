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

### Why attempt 1 did not finish

Attempt 1 stopped at the block above, which was correct. It then waited on its own
background poll for the host's update window, and that poll died when the
session ended. At 05:10 PDT hostops ran dispatcher_update_window.sh (dispatcher
tree to 6c25a829ef, which includes #381) and resumed this lane.

### Attempt 2 (2026-09-26 PDT)

- `$DISPATCH_DIR/bin/dispatcher.sh` names `hakuX-stall` 3 times, so the snapshot is current.
- Queued `1790424874-blinx372c-754046` (the command above, `--purpose` added)
  on ref 6c25a829ef, pinned to the Thor. It sits ahead of the `z-b-v040j1-*`
  sweep. request.sh warns that `--frames-every` costs frame rate, so P5 (fps)
  compares only against soaks that also captured frames.

## 0. Result (attempt 2): the site is `vk/surface.c:update_surface_part`, the incompatible-binding eviction

Two Thor soaks on master 6c25a829ef (apk 0550f75e2024). Both have a `logcat.spec`
that names `hakuX-stall:I`:

| result | frames | stall lines in window | sd/frame | cDef share | demo fps (reader) | verdict |
|---|---|---|---|---|---|---|
| `1790424874-blinx372c-754046` | every 30 s | 23 | 2.0 | 1.00 | 12.6 | 8/8 PASS |
| `1790425369-blinx372c-1062368` | none | 23 | 2.0 | 1.00 | 12.4 | 8/8 PASS |

The fps was off the ~16 median, so the brief's one rerun was spent, without frame capture. The
counters are identical, so frame capture did not cause the low fps. This apk runs the demo at 12-14 fps.

**Every line in the demo stretch (24 per run) reads exactly this:**
`Finish sd120 ... sd[dl0 cDef120 cDefC0 pDl0 dDl0] dlSrc[0 0 0] dif[all 0]` and
`evict[dl:120 unshelve:0 stale:120]`, per 60 flips. So there are two finishes per frame, and every one is:

1. `update_surface_part()` (vk/surface.c) finds a binding at the target address that
   fails `check_surface_compatibility()` (a different `color` role, `vk_format` or `pitch`,
   or smaller than the target). The binding is draw-dirty, so it takes the "incompatible"
   branch: `OPT_STAT_INC(sd_eviction_dl)`, then `download_surface_deferred()`, then `shelve_surface()`.
2. `pgraph_vk_surface_update()` then calls `pgraph_vk_download_surface_complete_deferred()`.
   No earlier submit exists, so it counts `sd_complete_def` and calls a synchronous
   `pgraph_vk_finish(SURFACE_DOWN)`. That is the Sd wait.
3. The same `update_surface_part` unshelves the partner binding for the new target.
   It is `vram_newer`/`mem_dirty` (the download just wrote its memory), so it is counted
   `sd_shelved_stale` and set `upload_pending`. The new binding re-uploads from VRAM what the old one drew.

This is the lookup-and-evict path through `update_surface_part`. It is not the overlap path:
`dif[ovl]` is 0, so it is not `invalidate_overlapping_surfaces`. It is not expiry: `dif[exp]` is 0.
It is not the texture range path either: `dlSrc dirtyIf` and every `dif` are 0. Two surfaces share
one VRAM address under incompatible host formats and ping-pong twice a frame (A to B, B to A).
Each switch moves the image GPU to VRAM to GPU, with a CPU wait in the middle.

**Falsifier verdict: removable in kind, not the demo's own readback.** pDl is 0 and dl is 0, so no
guest CPU access requests any of these downloads. The guest never reads the VRAM. The emulator
uses VRAM as the transfer medium between two host images of one guest surface. The contents
*are* consumed, though: the stale unshelve uploads them. So the hunk has to carry the pixels
GPU-side. It cannot simply skip the download.

**P4 passed on its label, and its stated mechanism was wrong.** The prediction guessed cDef
"from the texture range path (dif oth, texture_bind)". dif oth is 0. The cDef came from the
eviction in surface_update. The label leg could not tell these two apart. Next time, register the
`evict[dl]` == cDef identity as its own leg.

**The reader's price leg measured the wrong timer.** `stallread.py`'s `ms_per_wait_upper`
uses `Fen` (0.9 ms median). But for a non-deferred finish from the pfifo thread,
`pgraph_vk_finish` waits in `qemu_event_wait` inside the `finish_submit` timer
(draw.c, the `!deferred` branch). So the wait is in `Sub`, not `Fen`. The demo's other
finishes are deferred (`stl == stlDef`), so `Sub` bounds the eviction waits from above.

### Price (bound, not value): `demobound.py`

`demobound.py <logcat>` prints per demo line Tot, Sub, Fen, GPU and
`floor = max(Tot - Sub, GPU)`, with the fps cap 1000/floor:

| run | Tot | Sub (wait, upper) | Fen | GPU | floor | cap | now |
|---|---|---|---|---|---|---|---|
| 754046 (median of 24) | 64.0 | 34.5 | 0.9 | 41.8 | 44.2 | 22.6 fps | 15.6 |
| 1062368 (median of 24) | 69.7 | 34.8 | 0.9 | 45.0 | 46.6 | 21.5 fps | 14.3 |

("now" is 1000/median Tot, i.e. renderer-busy frames. The reader's gfps-cadence fps is 12.4-12.6.)
Removing both waits while GPU work stays the same leaves a GPU-bound frame. The ceiling is
**about 21-23 fps at the median line**, just over the 20 floor. It is a ceiling, and the real
gain could be much less. GPU includes `X` (transfer, 1-32 ms). The download half of each switch
is in X, so a hunk that also cuts the transfer raises the cap. That cap is bounded by
1000/(Tot - Sub), about 30 fps.

### The hunk (named, not edited; no hw/ grant)

`vk/surface.c:update_surface_part`, the incompatible branch. When the evicted binding is
draw-dirty and the next binding at the same `vram_addr` comes off the shelf (or is created) for
the same memory, record a GPU-side copy old image -> staging buffer -> new image, re-swizzled or
converted as the upload path would, in the same command buffer. Leave the old surface's VRAM
dirty and owed, with `draw_dirty` kept on the shelved binding, instead of completing a download
and re-uploading. The CPU-side copy, and so the synchronous finish, happens only if the CPU
actually touches the memory.

- **It overlaps vk/surface.c's CPU-access watch, and it depends on it.** The CPU-access
  watch (`surface_access_callback`, which walks the shelved and invalid lists) becomes the
  only thing standing between a later guest CPU read and stale VRAM. That is lane.surfwatch382's
  code and file. So this hunk is a surfwatch382 follow-on, or needs its grant. It is not
  independent of it.
- The golden risk is the one the comment above the branch records: Depth buffer fixed function
  flips Z16/Z24 and differed in 42 of 80 captures when this download was skipped.
  A GPU copy keeps the pixels; a skip does not.
- Cheapest first step, with no pixels moved: one counter that says which compatibility field
  fails (color role, vk_format, pitch or size). A pitch-only or size-only mismatch between two
  same-format images is a plain `vkCmdCopyImage`. A color/zeta role swap needs a format
  conversion pass.

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
- Do not price a pfifo-thread finish from `Fen`. The wait is inside `Sub` (qemu_event_wait).
- Do not re-soak to find the site. It is 120/120 on all 48 demo lines of two runs. The next
  measurement is which compatibility field fails (section 0).
- Section 4's table below was written before the data. Its cDef row (texture_bind) is **refuted**.
  Section 0 is the hunk.
