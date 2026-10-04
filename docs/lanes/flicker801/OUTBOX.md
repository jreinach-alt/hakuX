# flicker801 OUTBOX (#801)

## 10-04: inventory (step 1). What we have cannot see flicker

Flicker is a frame-to-frame property: an object is on screen in frame N, gone in frame N+1, and back in frame N+2. Of the
tools below, only the in-emulator frame dump records every guest frame, and its images are mostly missing (see its row).
Every other tool samples seconds apart, or summarises 60 flips into one line.

| tool | what it measures | time resolution | can it see a 1-2 frame blink? |
|---|---|---|---|
| `ab_compare.py` | pgraph test captures against goldens (`differing` pixel count, PNG sha) | one still per test, no time axis | no: these are test captures, not gameplay |
| `title_verdict.py` | fps share from `hakuX-perf` lines, hangs, `contact_sheet()` of up to 36 frames for the frame review | 60 flips per perf line; frames 10-30 s apart | no |
| `hitch_report.py` | pace `max` >= 100 ms, `static_window`, `position_change` | 60 flips; frames 5-30 s apart | no |
| perflog (`pgraph/profile.c`) | `hakuX-perf` (gfps, G/D averages), `hakuX-pace` (v0..v4 vblank buckets, max gap); with `NV2A_PERF_LOG`, `xemu-work` draw counters | one line per 60 flips; `xemu-work` holds only the LAST frame's counters | no: there is no per-frame draw or vertex series and no variance |
| pathfind hold `changed` (`classify.motion`, 160x120 grey, >16 levels) | share of pixels changed between hold cycles | ~7 s (RalliSport `hold.jsonl`: 7.0, 14.1, 21.2 s ...); kept frames every 30 s | no |
| dispatcher `--frames-every`, `drive.py`/`route.sh` | `exec-out screencap -p` | >= 1 s, each screencap ~1-2 s | no |
| `host-tools/fps_overlay.py` | OCR of the FPS overlay | `frames_every` s | no |
| **frame dump** (`pgraph/vk/renderer.c:1691-2500`, `XEMU_FRAME_DUMP` or `frame_dump.on`) | per draw: kind, count, shader, pipeline; per frame: `draws`, `submits_in_frame`, one display PPM | **every guest flip**, up to 600 | **draw count: yes. Images: mostly no.** On Galleon only 8-13% of frames wrote an image, about one in ten (diagsoak77 R3): the rest are `img_sync=-2`, refused as stale. That rules out consecutive-frame image analysis without a change to the flip pre-record. |
| `galleon_flash_rate.py`, `diagsoak77/framedump_correlate.py` | per-frame stipple classification in a region, for #77 | any ordered frames | yes, but tied to Galleon's region and stipple, and it has never had consecutive frames to work on |

Nothing in the harness captures consecutive displayed frames, and nothing anywhere uses `screenrecord`.

## Plan

- **Burst capture, the primary instrument:** `docs/testing/burst_capture.py --method rec`, a `screenrecord` of the display
  at up to the panel's refresh. It sees what the owner sees, presentation included. Its limit is the rate it sustains,
  which gets measured and printed (`unique_fps`, `dt_max_ms`). `--method caps` (back-to-back screencaps) is kept only to
  measure why it is not the default.
- **Detector:** `docs/testing/flicker_score.py <burst>` scores triples of frames: a pixel blinks when frame N differs
  from both neighbours while the neighbours agree. A 3x3 erosion follows. A triple is a hit when the eroded blinking
  pixels exceed 1 per 1000. It prints `rate` (hit triples per 100) and the worst triple, and writes
  `flicker_worst.png`. I fixed the thresholds before any capture, so a positive control cannot be tuned after the fact.
  The selftest (`--selftest`) passes on synthetic bursts: a clean pan with a scene cut gives 0 hits, a car gone 1 frame in
  4 gives 24.1/100, a car gone 2 frames in 6 gives 15.5/100, one muzzle-flash-like effect gives exactly 1 hit, and a
  30-on-60 repeat is de-duplicated at the same rate.
- **Secondary, for diagnosis:** the frame dump in `noimages` mode costs nothing and gives the per-frame `draws` series.
  If our renderer drops draws, the guest's issued count stays flat and only the picture shows it, so this is for
  attribution after a hit, not detection.
- **Device:** the Nova, after lane.pathfind releases its hold. RalliSport (positive control) first, then Panzer Dragoon
  Orta and Halo CE (negatives), 3 bursts of 4 s each during play.
