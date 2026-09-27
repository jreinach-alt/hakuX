# Audit pass 1: PR #480, lane.remote, #461 memo retirement (M1)

Head audited: `a53261f9`. Base: master `f131dd11`; origin/master is 2 commits
ahead of it, both in `docs/testing/titles/targets.toml`, which this PR does not touch.

**Verdict: no HIGH, no MEDIUM, two LOWs.** The code comment's claim that
`check_texture_dirty()` is the only consumer omits the RAM-resize clear. That
gap has no failure scenario, because a resize then marks everything dirty, so
it is not listed as a finding. The PR goes to `needs-audit-2`.

## What was read

- The full diff of `hw/xbox/nv2a/pgraph/vk/texture.c`, `draw.c`, `renderer.h`,
  `docs/lanes/remote/tex461_read.py` and the two prediction files.
- The code the fix depends on, beyond the diff:
  - `create_texture()`'s memo read (`skip_dirty_check`) and its confirmed-clean drop;
  - `pgraph_vk_mark_textures_possibly_dirty()`, `check_texture_dirty()`,
    `resolve_possibly_dirty_textures()` and `pgraph_vk_poll_bound_textures()`;
  - the SFP fast path's memo read (`draw.c` ~4058);
  - active-list insertion and removal (`texture.c` ~2988 and ~3177);
  - the render thread's full-VRAM mark on `RCMD_FLUSH` and on pending flush;
  - every `DIRTY_MEMORY_NV2A_TEX` site in `hw/`, `system/` and `include/`.

## The fix's safety argument, checked

The claim is that retiring the memo (`dirty_check_frame = frame_time - 1`) after
a hash cannot lose a write. It holds.

- **Every write sets a bit.** Every `DIRTY_MEMORY_NV2A_TEX` site in `vk/`
  outside `texture.c` is a `set_client_dirty`: `surface.c` 895, 972, 1578,
  1776 and 1860, and `blit.c` 749 and 922.
- **Only two places clear the bits:**
  - `check_texture_dirty()`;
  - `physical_memory_clear_dirty_range()`, called only from the RAM-resize path (`physmem.c:2229`).

  `draw.c` 4571 is compiled only under `HAKUX_VRAM_RACE_PROBE`, and that
  defaults to 0. It does not clear either: `vram_range_dirty_checked()`
  (`draw.c:190`) reads the bitmap and never clears it. So the PR body's
  "reader ... which is off" is, if anything, stronger than it needs to be.
- **A consumed bit still reaches the node.** `check_texture_dirty()` marks every
  binding on `texture_active_list` over the range. A cached node leaves that list
  only on eviction (`texture.c` ~3177). So a write consumed by another binding's
  check marks this node: `possibly_dirty` is set and the memo is stamped for this
  flip, which forces the next hash.
- **The reset is placed correctly.**
  - On the found path it sits in the non-surface-to-texture `else`, guarded by
    `possibly_dirty`, and that guard is exactly "a hash ran".
  - On the miss path, `possibly_dirty` is always true for a non-s2t node, so the
    hash ran there too.
  - A surface-to-texture miss is excluded, as it should be.
- **No reader treats the previous flip specially.** Nothing compares
  `dirty_check_frame` with `frame_time - 1`: every reader tests `== frame_time`.
  So `frame_time - 1` reads as "no verdict this flip". A freshly initialised node
  (`dirty_check_frame = 0`) reads the same way from flip 1 on.
- **A side effect that helps.** Before the fix, a miss in flip 0 left an LRU-reset
  node at `dirty_check_frame == 0 && !dirty_check_result`. That was a false
  "confirmed clean" for the rest of flip 0, and the miss path's reset removes it.
- **Writes during the found path's flush and upload.** A deferred download that
  completes inside `pgraph_vk_flush_all_frames()` sets the bits. Those bits are
  still in the bitmap at the next bind, so that bind hashes. The render thread's
  full mark runs at a synchronised flush, before the rebind that hashes.

The refs are right as well:

- `b_ref 8f9c74f0` has the same `hw/` tree as the head; `git diff 8f9c74f0 HEAD -- hw/` is empty.
- `a_ref f131dd11` is the branch base.
- All 21 suites in `remote-461-memo-texture.json` have goldens under `/home/justin/goldens/results`.
- `remote-461-memo-perf-crimson.json` carries `title`, so `arms.sh` (line ~847)
  skips it with an announced "hand-read" reason instead of queueing it. That
  matches the PR body.

`tex461_read.py --selftest` passes on the head.

`nv2a_index.py check --tests /home/justin/nxdk_pgraph_tests` reports no
symbol or site problem. It does report 5 suites whose content differs, and none
of them is touched by this PR. That comes from the host's tests-tree checkout
(its `provenance.tests_commit` date), not from this diff.

## Findings

### LOW-1: a diagnostic VRAM write sets no texture-dirty bit, and no rehash covers it any more

- **Where:** `hw/xbox/nv2a/pgraph/vk/renderer.c:377`, `diag_download_surface()`.
- **Problem:** it writes the colour surface into `d->vram_ptr` with `memcpy` and
  sets no dirty bit. Before this PR, a node already hashed in the flip was hashed
  again on every later bind in that flip, which incidentally picked such a write
  up. After this PR, nothing does.
- **Failure scenario:** with an RT dump path set
  (`nv2a_dbg_set_rt_dump_path`), a texture non-s2t-bound over the colour
  surface's range, and rebound after the dump in the same flip, samples the
  pre-dump VRAM image.
- **Why LOW:** the path runs only with RT dump on. It was already invisible
  across flips before this PR, so the gap is pre-existing.
- **Remedy:** none needed for this PR. If the dump path is ever used for
  correctness work, it should `set_client_dirty` like the real download paths do.

### LOW-2: `tex461_read.py` crashes on a 29 February stamp read in the neighbouring year

- **Where:** `docs/lanes/remote/tex461_read.py`, `parse()`.
- **Problem:** a `02-29` stamp more than 183 days from `t0` falls into the
  `abs(t - t0) > HALF_YEAR` branch. That re-reads it in 1999 or 2001, and
  `strptime` raises `ValueError` on `2001-02-29`.
- **Failure scenario:** the input contains `02-29` lines together with a
  `hakuX-perf` first line more than half a year away from them, which takes a
  logcat spanning over six months.
- **Why LOW:** unreachable for a 240 s soak. It is a crash only on input the tool
  is never given.
- **Remedy:** none needed, or pick the neighbouring leap year when the stamp is `02-29`.

## What pass 2 must verify

No HIGH or MEDIUM findings need a fix. Pass 2 should confirm:

1. The head it reads still has `git diff 8f9c74f0 <head> -- hw/` empty, so
   the registered `b_ref` is the code under review. If a later push changes
   `hw/`, both predictions must be re-registered on the new ref.
2. Whether the correctness arm (`remote-461-memo-texture.json`, 3 runs per arm)
   has reported by then. If it has, `Texture_signed_component_tests/txt_A8R8G8B8_ADD`
   must fall inside its measured band. This PR's own desktop leg already failed on
   that capture as registered. The capture is nondeterministic on both binaries,
   and it sits in the one suite where the fix changes the hash count, so the arm's
   verdict there is the evidence that decides.
