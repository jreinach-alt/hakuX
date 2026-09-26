# lane.doa413b -- #413 DOA2U surface_update cost

Base: master @ 7e6a4ac88a, then merged origin/master f63be3d4ab (2026-09-26) and
origin/lane/blinx372d (#396, still open; vk/surface.c is released to this lane at ready).

## Why attempt 1 did not finish

Attempt 1 built the probe (e38f95712e), pushed it, queued the pilot soak
`1790456253-doa413b-520408` (Nova, perflog, `survey` route, 300 s, ref e38f95712e), and then
ended without a `waiting:` comment. The soak was still in the queue with 9 requests ahead of it
when attempt 2 started (21:48Z). So attempt 1 was waiting on a device request, and it did not say so.

## What the probe logs (e38f95712e)

`LOGCAT_SPEC_OVERRIDE` is an environment variable of the dispatcher process only. A request
cannot carry it, so a pilot could not get `xemu-surf:I` from the request. The probe avoids
that: it prints under tag `hakuX`, which every spec carries, with prefix `[surf413]`, once per
60 guest frames (perflog builds only):

- `pre / flush / part / cdef / upl / exp / prn / tail`: wall ms/frame per segment of
  `pgraph_vk_surface_update`. `fin` is the `pgraph_vk_finish` time nested inside those
  segments, so `sum - fin` is what `Surf` reports.
- `realupl / uplKB`: bound surfaces whose `upload_pending` was set, meaning real uploads, not
  the early return.
- `hash / hashKB`: whole-surface hashes taken by `surface_watch_resume`.
- `active / shelved / invalid`: the length of each list, which bounds the linear scans in
  `expire_old_surfaces`, `prune_invalid_surfaces` and `pgraph_vk_surface_get`.
- A second line, `[surf413] xemu-surf ...`, carries profile.c's own sub-split (populate,
  dirty, enrp, lookup, create, bind, upload, download, expire).

The dispatcher.sh hunk adds `xemu-surf:I` to the default spec. It only takes effect after the
host runs its dispatcher update window.

## Candidates, read from the code before the price (not a site yet)

The fight's calls are almost all `upload=true`, from draw.c:1188 and 7096. The `upload=false`
path is only reached from blit.c. At 700 calls/frame and 45 ms, each call costs about 64 µs.
But the shape changes happen only about 6 times per frame, so if the cost sits in them it is
about 7.5 ms per change. That points at work proportional to surface size, not at per-call
overhead:

1. A real upload for each rebind: `upload_pending` set again by the CPU-access callback, then
   `surface_watch_resume` hashes the whole surface plus the CPU conversion or copy
   (`upl`, `realupl`, `hash`).
2. `update_surface_part` creating a new surface for each rebind instead of finding the old one
   (`part`, and xemu-surf `create` against `hit`).
3. `expire_old_surfaces` / `prune_invalid_surfaces` scanning on every call (`exp`, `prn`, the
   list lengths). This is per call, so it would need long lists to reach 64 µs.
4. `complete_deferred` waiting on a fence (`cdef`, `fin`).

The dirty-bitmap scan in `update_surface_part` is `!tcg_enabled()` only, so it does not run on
Android.

## Status

Waiting on the pilot `1790456253-doa413b-520408`. The next step is to read `[surf413]` over
fight 2 and fill in the table below.

| window | gfps | Surf | pre | part | cdef | upl | exp | prn | fin | realupl/fr | hashKB/fr | active/shelved/invalid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| (pending) | | | | | | | | | | | | |
