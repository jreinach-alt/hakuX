Lane: async794            Issue: #794 #796
Base: master @ 425ffe1ad1 (merged; branched from 5e4196fefd)
Files: docs/lanes/async794/NOTES.md, docs/lanes/async794/OUTBOX.md, docs/lanes/async794/PR.md, docs/lanes/async794/cc_check.py, docs/lanes/async794/make-predictions.py, docs/lanes/async794/make-routes.py, docs/lanes/async794/routes/async794-cs.route, docs/lanes/async794/routes/async794-topspin.route, docs/lanes/async794/sdcallers.py, docs/lanes/async794/shim/android/log.h, docs/testing/predictions/async794-burnoutrev-soak.json, docs/testing/predictions/async794-cs-soak.json, docs/testing/predictions/async794-download-paths-must-not-move.json, docs/testing/predictions/async794-fix2-must-not-move.json, docs/testing/predictions/async794-mc3-soak.json, docs/testing/predictions/async794-nba2005-soak.json, docs/testing/predictions/async794-topspin-soak.json, hw/xbox/nv2a/pgraph/vk/draw.c, hw/xbox/nv2a/pgraph/vk/renderer.h, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/texture.c
Prediction: docs/testing/predictions/async794-fix2-must-not-move.json @ 9715a5a775b7a57e (golden arm on the fold form, a 425ffe1ad1 / b 2344ae1ee2); earlier: async794-download-paths-must-not-move.json @ 5a9978ab62adf5f9 (PASS), soaks -nba2005-, -topspin- (hand-read below)
Needs device: yes    Needs NDK: yes

Release note (none): no player-visible change measured; the CPU no longer waits on the graphics lock while the GPU finishes a surface download.

## Result

| title | arm | run id | fps median | share >= 28.5 | ph_Fin ms | lockw ms | download wait |
|---|---|---|---|---|---|---|---|
| NBA Live 2005 | A master | 1791128020-lane.async794-3209876 | 25.89 (mean) | 0.20 | 13.40 | 3.38 | `reuse` 1/frame, 11.18 ms |
| NBA Live 2005 | B c825e4b24f | 1791128026-lane.async794-3210567 | 25.34 (mean) | 0.19 | 13.80 | 0.27 | `surfupd` 1/frame, 11.48 ms |
| Top Spin | A master | 1791135713-lane.async794-3678571 | 36.50 | 0.963 | 12.30 | 10.50 | txr dl 27/frame, all `cvt` |
| Top Spin | B c825e4b24f | 1791135717-lane.async794-3678947 | 35.82 | 0.963 | 12.60 | 0.40 | txr dl 27/frame, all `cvt` |

- **Fix 1 (defer the download to the guest's sync point) is refuted on NBA.**
  The wait moved. The one finish a frame went from `reuse` to `surfupd` at the
  same size: the rebound surface uploads from VRAM, so the download has an
  emulator-side consumer (image -> VRAM -> image) before any guest sync point.
  It is stripped from the fold form.
- **Fix 2 (release pgraph.lock across the SURFACE_DOWN wait) acts and moves no
  fps.** On Top Spin the vCPU's PGRAPH read wait falls 10.14 -> 0.41 ms/frame
  (0xb10, rd_unl 0 -> 308k). The freed time goes to the guest's timer idle
  (gidle 0.56 -> 15.67 ms), so the frame was not lock-bound. Every leg of
  `async794-topspin-soak.json` holds and its falsifier does not fire, but P2
  holds only because the control already passed.
- **Top Spin clears the bar on master** with the fixed route (no step-24
  START): 36.5 fps median, 0.963 share over 640 s of live play. The earlier
  0.89 came from a paused match. It is a Playable candidate pending the held
  run, the frame review and the flicker check.
- **The texture-bind download class is a format conversion.** `txdl[]` says
  Top Spin's 27 downloads a frame are all refused for `cvt`: a 64x128
  swizzled colour surface sampled as texture format 0x5. A GPU-side converting
  copy is what would remove that class's wait in other titles. That needs its
  own brief.

## Changes (fold form 2344ae1ee2, 118 lines against master)

- **#796**: on the PFIFO thread, `pgraph_vk_finish(SURFACE_DOWN)` and the
  deferred-download fence waits wait for the GPU with pgraph.lock released.
  This extends the #474 mechanism (`wait_frame_fence`), and the staged copies
  still land in VRAM after the lock is retaken.
- **Instrument**: `txdl[...]` on the hakuX-stall `txr` line and `[txdl794]`
  shape lines name the compatibility test that refused each texture-bind
  download.

Compiles with the desktop flags, plain and perflog+`__ANDROID__`. The first
form (c825e4b24f, fix 1 included) passed its golden arm byte-identical over
all 266 captures (`1791129309-arms-async794-fix-3307191`). The fold form is a
subset of that code, and its own golden arm is registered for the arms job.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
