Lane: async794            Issue: #794 #796
Base: master @ 5e4196fefd
Files: docs/lanes/async794/NOTES.md, docs/lanes/async794/OUTBOX.md, docs/lanes/async794/PR.md, docs/lanes/async794/WAITING, docs/lanes/async794/cc_check.py, docs/lanes/async794/make-predictions.py, docs/lanes/async794/make-routes.py, docs/lanes/async794/routes/async794-cs.route, docs/lanes/async794/routes/async794-topspin.route, docs/lanes/async794/sdcallers.py, docs/lanes/async794/shim/android/log.h, docs/testing/predictions/async794-burnoutrev-soak.json, docs/testing/predictions/async794-cs-soak.json, docs/testing/predictions/async794-download-paths-must-not-move.json, docs/testing/predictions/async794-mc3-soak.json, docs/testing/predictions/async794-nba2005-soak.json, docs/testing/predictions/async794-topspin-soak.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: docs/testing/predictions/async794-download-paths-must-not-move.json @ 5a9978ab62adf5f9 (golden arm); soaks docs/testing/predictions/async794-nba2005-soak.json @ 9e8fa53fa86938fa, -topspin-, -cs-, -mc3-, -burnoutrev-soak.json (hand-read)
Needs device: yes    Needs NDK: yes

Release note (performance): Top Spin's CPU no longer waits on the graphics lock behind texture-bind downloads.

## What the logs say first: three callers, not one

fps20786 filed every SURFACE_DOWN wait under one name. Split by caller
(`docs/lanes/async794/sdcallers.py` over the existing runs):

| title | caller | per frame | wait | consumer of the bytes |
|---|---|---|---|---|
| NBA Live 2005 | `reuse` (unshelve of a struct a pending download names) | 1 | 11.4 ms | none yet: bookkeeping |
| Counter-Strike, Top Spin, ToeJam, BloodRayne, Burnout, Nightfire, MM3 | texture bind, surface refused by the compatibility check (`txr dl`) | 1-26 | 13.7 / 16.4 ms (CS / Top Spin) | the texture upload, on the CPU, at once |
| Midnight Club 3, Nightfire | `range` reader over a dirty surface | 1 | 6.9 / 6.3 ms | the reader, at once |

Deferring a wait to the guest's next sync point removes it only where nobody
consumes the bytes first: NBA's `reuse` (and Azurik's). The texture-bind class
needs a GPU-side surface-to-texture path; which conversion depends on why the
bind refuses the surface, which this PR instruments.

## Changes (c825e4b24f)

- **#796**: SURFACE_DOWN finishes and the deferred-download fence waits release
  pgraph.lock on the PFIFO thread (the #474 mechanism, extended).
- **#794 at NBA's site**: staged downloads carry their own submission's frame
  slot and complete as a prefix in record order, so recording a download no
  longer completes the previous submitted batch (which would have moved NBA's
  wait to the next frame's first eviction); the `reuse` site detaches instead
  of finishing; staging is a ring.
- **Instrument**: `txdl[...]` on the `txr` line and `[txdl794]` shape lines name
  the refusing test for each texture-bind download.

Compiles with the desktop flags, plain and perflog+`__ANDROID__`.

## Device (Nova)

Pilot, NBA Live 2005 (A `1791128020-lane.async794-3209876`, B `1791128026-lane.async794-3210567`):

| | fps | ph_Fin ms | ph_Tot ms | lockw ms | share >= 28.5 | download wait |
|---|---|---|---|---|---|---|
| A master | 25.89 | 13.40 | 27.40 | 3.38 | 0.20 | `reuse` 1/frame, 11.18 ms |
| B fix | 25.34 | 13.80 | 28.10 | 0.27 | 0.19 | `surfupd` 1/frame, 11.48 ms |

**Fix 1 is refuted: the wait moved.** Its falsifier fires: ph_Fin stays above
8 ms, and the one finish a frame moved from `reuse` to `surfupd`. The rebound
struct uploads from VRAM, so `surface_update_may_defer_downloads` completes
the detached download on the spot. The bytes go image -> VRAM -> image within
the frame. The Counter-Strike, Midnight Club 3 and Burnout Revenge pairs were
fix-1 tests and are not run.

Fix 2 acts: the vCPU's lock wait falls by 3.1 ms/frame on NBA. Its test is
Top Spin (`async794-topspin-soak.json`), queued: A
`1791135713-lane.async794-3678571`, B `1791135717-lane.async794-3678947`.
The golden arm runs from the arms job.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
