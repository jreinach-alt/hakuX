# lane.fix311: the surface-watch leak behind #311

## Re-derived on master 21b8c6a80e

The review's account of 21cacb354a holds on master. Line numbers are master's:

- `unregister_cpu_access_callback_if_clean()` (vk/surface.c:2033) keeps a
  retired surface's watch up while it is `draw_dirty`. Both retirement paths
  use it: `invalidate_surface()` (:2110) and `shelve_surface()` (:2139).
- `update_surface_part()` (:3415) does `memset(&target, 0, ...)`, then takes a
  slot from `get_shelved_surface()` (:3690) or
  `get_any_compatible_invalid_surface()` (:3696). Both remove the slot from
  its list and return it with its fields intact, including `access_cb`. Then
  `*surface = target;` (:3706) overwrites `access_cb` with NULL.
- `surface_put()` (:2252) -> `register_cpu_access_callback()` (:2008)
  unregisters first, sees NULL, and inserts a new watch. The old
  `MemAccessCallback` stays on `cpu->mem_access_callbacks` with no pointer
  left to it.
- `mem_access_callback_insert()` (system/physmem.c:880) also does a full
  `tlb_flush_all_cpus_synced` on every insert. The list is walked with no early
  exit by `mem_access_callback_address_matches()` (physmem.c:859), which
  `cputlb.c:1107` calls on every TLB fill, and at physmem.c:955 on the access
  path. Leaked watches keep their old VRAM ranges trapping. Every guest access
  to those pages goes to `surface_access_callback`, which takes `pgraph.lock`
  and walks all three surface lists.
- Every free path (`invalidate_overlapping_surfaces` shelved branch,
  `prune_invalid_surfaces`, `expire_old_surfaces`, finalizer) calls the
  unconditional `unregister_cpu_access_callback()`. The reuse path is the only
  way a watch is dropped without being removed.
- The GL renderer (gl/surface.c) has no `_if_clean` path and is not affected.

## Commits

- `5d2d2e7290` (arm A): a counter only. Every 5 s it logs
  `[watch311] live=<inserts-removes> inserts=<n> cb_count=<xbox_ram_fp.cb_count>
  active= shelved= invalid=` to logcat (tag hakuX). Because each binding holds
  at most one watch, `live > active+shelved+invalid` can only mean leaked
  watches.
- `d5eb83f39e` (arm B): `unregister_cpu_access_callback(surface)` before
  `*surface = target`, and `g_malloc0` for a fresh slot so the call sees NULL
  there.

Why this keeps 21cacb354a's intent: the watch exists so that a guest write
clears the writeback a retired dirty surface still owes. The write handler
(`surface_access_callback`, :1968) does that only for surfaces on the shelved
and invalid lists. A reused slot has just been taken off those lists, and the
assignment replaces its `vram_addr` and `draw_dirty` anyway, so the obligation
the watch guarded is already gone. Surfaces still on the shelf or invalid list
keep their watches exactly as before.

## Prediction and runs

`docs/testing/predictions/fix311-ghoulies-watch-leak.json`. This is a
hand-judged title soak with no golden keys, so arms.sh will skip it
structurally. The requests are queued directly as `0-0-fix311-*`.

Results: see the PR and #311. This section is filled in once the runs are back.
