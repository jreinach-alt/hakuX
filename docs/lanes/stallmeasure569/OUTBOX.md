# lane.stallmeasure569 outbox (offline; relayed by lane.local)

## #569 -- 2026-10-02 15:10 PDT

[lane.stallmeasure569] Read from disk, no device time spent. Full tables and method in
`docs/lanes/stallmeasure569/NOTES.md`.

**Does the shipped shader pre-build (`shaderprebuild569`, folded `b1cea467c6`, default on) remove
first-play compile stalls? No, and it was not designed to.** A title's first launch on a device has
no recorded pipelines to pre-build, so it still pays full cold compile cost: Kabuki's first launch
on the pre-build code (32 hitches, worst 4.80 s) reads the same as a cold baseline from before the
mechanism existed (37 hitches, worst 4.99 s). Two titles played for the first time today, ToeJam &
Earl III and Tron 2.0, both still hitch on shader compiles in their first two minutes.

**It does remove most of the stall on a replay of a title the device has already recorded.**
Kabuki's second launch (fixed route, same-content pair, the only clean one on disk) cut
whole-window hitches 34% (32 -> 21) and its single worst stall 86% (4.80 s -> 665 ms). What is left
on replay is content the one prior launch did not happen to meet (random opponent/arena inside the
fixed route) -- genuinely new pipelines, not engine overhead. DOA's pair moved the same direction
but cannot be read for size: its route is blind and meets a different opponent/stage every launch
(shaderprebuild569's own W1b finding, confirmed again here).

None of this exercises the uber ladder (`HAKUX_GPL`): every run read is at the shipped default,
`HAKUX_GPL=0`.

**Next step, ranked:** `uberspike569/BUILD.md` section 12.4's own ranking stands, with one change.
Its #2, "persist the uber combinations and pre-build them at boot," was explicitly **not built by
decision** there -- a cold soak clears caches, so persisting would make "cold" look warm, and the
ladder's own legs depend on a true cold reading. That concern is real, but `shaderprebuild569`
already shipped the exact pattern this needs (a compile-worker pool, a per-title append-only
record file, a boot-time resolve-and-build step) **and already solved this concern**, with a
falsifier leg that wipes the pipeline-cache file but keeps the records, so cold and warm are
measured apart. Section 3 of NOTES.md is the first production evidence that the pattern delivers
at this size (86% off the worst stall, 34% off the hitch count) on a real device log, not an
estimate. Promoting it to **#1** on that evidence. uberspike569's own #1 (split link cost from
interpreter cost, one Nova arm) is still worth one cheap arm, now #2: it is a diagnostic, not a
stall fix, and decides between two follow-on optimisations rather than removing a stall itself.
`NoContraction` (#3) and the default flip (#4, owner's decision) are unchanged.

The successor brief for the persisted-combinations build is below, for dispatch as
`briefs/uberpersist569.md`.

**Board note, not acted on here (lanes do not edit the tracker):** `nv2a_issues.toml`'s `#569` row
has a stale `blocked_on` from 2026-09-30T00:42Z naming `lane.litcompile569` as attempt-capped.
`git log --all` shows litcompile569 folded (`47bfcdc9b7`) and retired (`43902dab17`) that same day,
and uberspike569/shaderprebuild569/gpl569 have all folded or retired since. Needs a board request
to correct, not an edit from this lane.

---

## Successor brief: `briefs/uberpersist569.md` (candidate text, for lane.local to dispatch)

```
Lane: uberpersist569          Issue: #569
Base: origin/master

# Persist the uber ladder's (family, GS, raster, formats) combinations and pre-build them at boot

## Why
`uberspike569` built the uber pre-raster ladder (`HAKUX_GPL=3`, default off): on a pipeline miss
whose vertex state an uber library covers, the draw fast-links the uber stand-in and keeps playing
while the specialised monolithic pipeline compiles on the worker pool, then swaps in. Its own
measured cost is GPU time while the uber stage stands in (3.8x per frame held; 0.79x median fps
over a cold DOA play span, recovering as swaps land). Its own ranked next step #2, "persist the
combinations and pre-build them at boot," was explicitly not built: BUILD.md section 4 worried that
persisting would contaminate the "cold" reading its own legs (N1-N3, G, K0-K3) depend on.

That concern has since been answered by a sibling lane, not by this one. `shaderprebuild569`
(folded `b1cea467c6`) shipped the identical pattern for monolithic draw-path pipelines: a
compile-worker pool (`compile_worker.c`), a per-title append-only record file
(`pipeline_keys/<title id>.bin`), a pre-build at renderer init that rebuilds a title's already-
recorded pipelines before PFIFO draws need them, and a falsifier leg (W4) that wipes the pipeline-
cache file but keeps the records, so "cold" (no compiled cache) and "has records" are tested apart
without losing the ability to measure true-cold behaviour. `docs/lanes/stallmeasure569/NOTES.md`
section 3 reads that mechanism's production effect on Kabuki: 86% off the worst stall, 34% off the
hitch count, on a real device log. The ask here is to apply the same pattern to the uber ladder's
own miss set, not to redesign it.

## What to build
- Extend (or reuse, behind its own key type) `shaderprebuild569`'s per-title record file and
  compile-worker pool to record a (family, GS, raster, formats) combination the ladder links for
  the first time, and to pre-build the matching specialised monolithic pipeline at renderer init
  for every combination the title's record file already has -- bypassing the uber-interpreter
  stand-in entirely for a combination the device already knows, the same way shaderprebuild569's
  pre-build bypasses a cold compile for a known monolithic pipeline today.
- Keep `HAKUX_GPL`'s default at 0. This is infrastructure for the ladder (modes 3/4), not a default
  change; no player sees different behavior until the ladder itself defaults on (uberspike569's #4,
  a separate owner decision).
- A falsifier leg in the same shape as shaderprebuild569's W4: the same title, cache file wiped,
  records kept, so a true-cold reading stays available after this lands. `uberjudge.py` and
  `kabjudge.py` (uberspike569) already have the N1-N3/G/K0-K3 legs to extend; do not redesign them,
  add a "records present, cache wiped" variant.

## Proof
Reuse DOA and Kabuki, the same two titles and routes uberspike569 and shaderprebuild569 already
measured, with `HAKUX_GPL=3`:
- A: cold, no records (today's ladder, as measured).
- B: cold cache, records present from a prior launch (the new falsifier leg).
- Compare B against A on: draw-path create ms, worst stall, GPU ms/frame while the combination
  would otherwise be held in the interpreter, and count of uber-interpreter detours avoided.
Expect B to remove DOA's 14 cold combinations (uberspike569 N3) and Kabuki's fight almost entirely,
mirroring shaderprebuild569's own size of win on the monolithic path.

## Files (expect contention; coordinate before editing)
`hw/xbox/nv2a/pgraph/vk/compile_worker.c`, `draw.c`, `renderer.c`, `renderer.h`, `shaders.c` are
live in both `uberspike569`'s and `shaderprebuild569`'s folded history. Read both lanes' NOTES
section on thread safety and the worker's job-rank switch before touching the pool; shaderprebuild
left its state behind one opaque pointer (`r->compile_worker`) for exactly this reason.

## Notes
- Needs device (Nova) and NDK.
- Territory: propose `hw/xbox/nv2a/pgraph/vk/**` (compile_worker.c, draw.c, renderer.c, renderer.h,
  shaders.c) plus `docs/lanes/uberpersist569/**`; request via board, do not self-grant.
```
