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

## Results (2026-09-26, dispatch results under `$DISPATCH_DIR/results/`)

The leak is #311's cause. One hunk takes Ghoulies from a median of 2 gfps to
29 on both handhelds, over 90-240 s.

| run | device | arm | gfps median 90-240 s | gfps min 90-240 s | live watches at end | bindings at end |
|---|---|---|---|---|---|---|
| 0-0-c-1790381627-lane.fix311-1789927 | thor | A | 2 | 1 | 1,719 | 14 |
| 0-0-c-1790381627-lane.fix311-1789982 | nova | A | 2 | 1 | 1,783 | 14 |
| 0-0-c-1790381627-lane.fix311-1789954 | thor | B | 29 | 8 (one line, 128 s) | 4 | 13 |
| 0-0-c-1790381628-lane.fix311-1790009 | nova | B | 29 | 15 | 4 | 13 |

All four runs used apk A `80d3b6e119ce` and apk B `a4af97540969`.
`cb_count` equalled `live` on every line, so nothing else holds watches.

Counter curve, arm A (live watches on Thor / Nova): +1 s 78/114, +21 s
268/300, +31 s 406/540, +62 s 946/1003, +92 s 1082/1139, +154 s 1240/1318,
+214 s 1574/1670, +250 s 1719/1783. Arm B holds 3-6 live on every line on
both devices, while its inserts reach 9,777 (Thor) and 10,682 (Nova). The
fixed build does about 6x more slot reuse, because it runs 15x faster. Arm A
gfps (Thor): 29-30 to 15 s, 14 at 20 s, 9 at 31 s, 5 at 49 s, 3 at 59 s, 1-3
from 136 s on. The Nova curve is the same shape.

Legs as registered:

- W1: arm A live exceeds its bindings by the first line: PASS. Arm A last
  line >= 200: PASS. **Arm A last >= 5x the 30 s line: FAIL** (Thor 4.2x,
  Nova 3.3x). The leak rate is highest in the first minute (about 20/s) and
  then slows to about 5/s, so the ratio I registered was the wrong shape;
  the count still climbs on every line. Arm B live <= bindings on every line:
  PASS. Arm B 120-240 s max <= 2x the 30-90 s max: PASS (5 vs 6).
- F1: arm B median >= 25 on both: PASS (29, 29). **No arm B line below 15:
  FAIL on Thor** (one 8 at 128 s, 29 on both sides of it). Nova's minimum is
  15, which passes.
- F2: arm A median <= 12 on both: PASS (2, 2).
- X1: arm B live never negative: PASS.
- Must not move (arm B):
  - Crimson Skies 120 s: Thor `0-0-c-1790383804-lane.fix311-2708137` and
    Nova `...-2708587` both held to the end, gfps median 29, no crash lines.
  - JSRF 120 s, Thor `0-0-c-1790384403-lane.fix311-2911280`: held, median
    51, no crash lines.
  - The first Crimson run (`...-1790036`, Thor) read "guest never appeared"
    with 0 logcat lines. Not one line means the process never logged at
    all, not a crash in this code, and the same apk booted Crimson on both
    reruns. I read it as a void run.
  - The first JSRF request used a wrong title and was refused ("title not
    on device"). The staged file is `JSRF - Jet Set Radio Future
    (USA).xiso.iso`.

## For the next lane

- Do not chase the TLB-arming walk, or `accel/tcg`, for #311. The time goes
  into leaked watches: 1,700 stale ranges, each trapping guest accesses into
  `surface_access_callback` under `pgraph.lock`. The arming walk only grows
  1.4x.
- `[watch311]` stays in the fix PR as a cheap regression tripwire. A
  `live > active+shelved+invalid` line in any logcat means a watch leaked.
- `read_soak.py` here prints a soak result's gfps series and counter curve.
