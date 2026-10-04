Lane: async794            Issue: #794 #796
Base: master @ 5e4196fefd
Files: docs/lanes/async794/NOTES.md, docs/lanes/async794/PR.md, docs/lanes/async794/cc_check.py, docs/lanes/async794/make-predictions.py, docs/lanes/async794/make-routes.py, docs/lanes/async794/routes/async794-cs.route, docs/lanes/async794/routes/async794-topspin.route, docs/lanes/async794/sdcallers.py, docs/lanes/async794/shim/android/log.h, docs/testing/predictions/async794-burnoutrev-soak.json, docs/testing/predictions/async794-cs-soak.json, docs/testing/predictions/async794-download-paths-must-not-move.json, docs/testing/predictions/async794-mc3-soak.json, docs/testing/predictions/async794-nba2005-soak.json, docs/testing/predictions/async794-topspin-soak.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: docs/testing/predictions/async794-download-paths-must-not-move.json @ 5a9978ab62adf5f9 (golden arm); soaks docs/testing/predictions/async794-nba2005-soak.json @ 9e8fa53fa86938fa, -topspin-, -cs-, -mc3-, -burnoutrev-soak.json (hand-read)
Needs device: yes    Needs NDK: yes

Release note (performance): NBA Live 2005 and other titles that ping-pong render targets no longer stall the renderer once a frame on a surface download; Top Spin's CPU no longer waits on the graphics lock behind texture-bind downloads.

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

## Device (Nova), queued, waiting behind the pathfind hold

Pilot: NBA Live 2005, A master `1791128020-lane.async794-3209876`, B fix
`1791128026-lane.async794-3210567`. The other four titles' pairs follow the
pilot's review. The golden arm runs from the arms job.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
