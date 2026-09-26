# lane.blinx372b -- which SURFACE_DOWN site is Blinx's `Sd2` (#372)

Base master 7a2036020d. Title 4D530013 (Blinx: The Time Sweeper), Ayn Thor.
Predecessor: lane.blinx372 (PR #374, docs/investigations/perf-blinx-372.md).

## 1. Allow-list (done, this PR)

dispatcher.sh LOGCAT_SPEC now names `hakuX-stall hakuX-rpbrk hakuX-cpu
xemu-gpu xemu-sfp` (all :I, all NV2A_PERF_LOG-only, one line per 60 guest
frames). `hakuX-pace` was already there (lane.titlerun, #307). The workers run
from `$TREE/docs/testing` (dispatcher.sh:65), i.e. master's tree, so **no
dispatched soak can carry these lines until this PR folds**. The soak is
therefore after the fold, not in this PR's first session.

Selftest: `docs/lanes/blinx372b/run_selftest.sh` runs jobs/selftest.sh;
fragment 51's LOGCAT_SPEC checks pass (198 ok, 0 bad before the 580 s local
timeout; CI runs the whole thing).

## 2. The SURFACE_DOWN sites, read from the code (not "seven")

`python3 docs/lanes/blinx372b/sites.py` lists every
`pgraph_vk_finish(..SURFACE_DOWN..)`. With `OPT_SURF_TO_TEX_INLINE 1`
(renderer.h:182) and the diag/fdump dumpers off, exactly FOUR can fire in a
normal run, and each has its own counter on the `hakuX-stall` line:

| counter (`sd[...]`) | site | path |
|---|---|---|
| `dl`   (sd_dl_to_buf)    | surface.c:1511 download_surface_to_buffer | every synchronous `download_surface()` |
| `cDef` (sd_complete_def) | surface.c:957 complete_deferred | deferred downloads recorded in the open CB, now needed |
| `pDl`  (sd_pending_dl)   | surface.c:1762 process_pending_downloads | display thread asked for a surface (non-AHB display) |
| `dDl`  (sd_dirty_dl)     | surface.c:1846 download_dirty_surfaces | guest-wide flush (savevm, scale change) |

Dead in this build: surface.c:1108, texture.c:858/1151 (`#else` of
OPT_SURF_TO_TEX_INLINE), renderer.c:1399/2352 (diag dumper). `SURFACE_DOWN_FLUSH`
has no caller at all. So `Finish sd` = dl + cDef + pDl + dDl exactly.

Who asked for a `dl` is on `dlSrc[defFb ppdFb dirtyIf]`, and for `dirtyIf`
(`pgraph_vk_surface_download_if_dirty`) on `dif[...]`:
`ovl/ovlSh` surface.c:2240/2272 (new surface overlaps a dirty one), `exp/expSh`
2734/2755 (expiry), `blt` blit.c, `flu` 4097/4103, `dds` dirty-surfaces
fallback. `oth` counts the range path (`download_surfaces_in_range_if_dirty`:
texture.c:1882 texture overlapping a surface, blit.c:558/900, vertex.c:50),
which completes through `cDef`, not `dl`. **texture.c:1842 (a texture at a
surface's address whose shape is incompatible with direct binding) has no
`dif` counter**: it is `dirtyIf` minus the sum of the other `dif` fields.

pDl is not expected: the Thor presents through AHB (`AHB interop: available`,
`display: AHB image created` in 1790409543-blinx372-195142), so the forced
per-vblank download in wait_for_surface_download (surface.c:1690) is not on
this path.

## 3. What the predecessor's perflog already says (no new run)

`python3 docs/lanes/blinx372b/workread.py <logcat>` on
1790409543-blinx372-195142 (xemu-work is ONE sampled frame per line):

| window | samples | Fin | S2T | QS |
|---|---|---|---|---|
| menus (<130 s) | 111 | St1 x97, St2 x13, Fl1 x1 | 1/0 | 1/0 or 2/0 |
| demo (130-270 s) | 29 | Sd2 St1-4 x22, St1 x7 | 6-7/0 on every Sd2 row, 1/0 on every St1 row | 3-6/0 |

`Sd` is exactly 2 on every row where it is non-zero, and those are exactly
the rows with 6-7 surface-to-texture binds. Two per frame, not a spread.

## 4. Pre-registered (before any soak; this commit)

Soak: perflog build of master, Thor, 240 s hands-off, read `hakuX-stall` over
the 135-265 s window, summed over lines.

- P1 (instrument check, impossible row): sum(dl + cDef + pDl + dDl) equals
  sum(`Finish sd`) on every line. A line where they differ means a fifth site
  and voids the site split.
- P2 (brief's falsifier): one of dl / cDef / pDl / dDl carries >= 80% of
  `Finish sd` over the window. If not, rank them and name no single site.
- P3 (my guess, stated so it can be wrong): the site is `dl` via
  `dlSrc dirtyIf`, from the texture path (texture.c:1842, i.e. `dirtyIf` not
  covered by `dif`) or from `cDef` via `dif oth` (texture.c:1882). Rival: a
  blit (`dif blt`). pDl ~ 0 (AHB). dDl ~ 0.
- Rate: `Finish sd` / 60 frames between 1.2 and 2.0 in the demo (29 samples:
  22 x 2 + 7 x 0 = 1.52 mean).

A zero `hakuX-stall` line count is VOID (filter or non-perflog apk), never
"no downloads".

## Do not repeat

- Do not queue the soak before this PR is folded: the worker's LOGCAT_SPEC
  comes from master's tree.
- The "seven sites" count in #372 includes dead `#else`/diag sites; four are live.
