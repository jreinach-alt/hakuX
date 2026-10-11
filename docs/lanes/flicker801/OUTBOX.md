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

## 10-04 09:55 PDT: the detector separates RalliSport from the negatives

[lane.flicker801] **RalliSport's car flicker is captured and scored. Gate: `p90 > 5` is FLICKER.**

| title | bursts | p90 (blinking px per 1000, 90th percentile triple) | verdict |
|---|---|---|---|
| **RalliSport Challenge, race start, rivals in view** | 3 (3 boots) | **194.1, 14.6, 14.1** | **FLICKER, all 3** |
| Panzer Dragoon Orta | 6 | 0.0-1.47 | clear |
| Halo: Combat Evolved | 3 | 0.77-1.20 | clear (3 more unmeasured: the tutorial camera stood still) |
| Spikeout: Battle Street | 3 | 0.0-0.12 | clear |

- What the flicker is: a rival car beside the camera is drawn in frame N and absent in N-1 and N+1, while its shadow is
  drawn in all three. It alternates for seconds (runs of consecutive hits). Frames:
  `docs/lanes/flicker801/runs/s3/4D53000F-claim-1/b1/worst.jpg` (and `-claim-3`, `s2/4D53000F-claim/b1`).
- Capture: `screenrecord` holds the Nova panel's 60 Hz (59-60 distinct frames/s on 60 fps titles), enough for any
  Xbox title. Back-to-back screencap is 0.7-1.3 s per frame.
- Out of sample (session 3, metric fixed before it): 14.6 and 14.1 against a negative maximum of 0.443.
- Changed after the first session, and recorded: the burst number is p90, not rate. Orta's explosions and a white flash
  put rate as high as no-car RalliSport. The pixel thresholds were never changed.
- Limits: it only sees what is on screen. RalliSport's hold-play drives off alone, and those bursts read clean. An
  object under about 0.5% of the frame is below the gate. Replicates sit 2.8x over the gate, not 30x.

**The one line before a Playable is accepted** (`docs/testing/flicker.md`), with the device held and the title in
play with its action on screen:

    python3 docs/testing/burst_capture.py --device nova --hold-tag <tag> --seconds 8 --out <run>/flicker1

`verdict=FLICKER` means: look at `worst.jpg`/`flicker_worst.png` before accepting. `unmeasured` (a still screen) is not
a pass. The host needs an ffmpeg (`pip install imageio-ffmpeg` in a venv, or `$FFMPEG`); `find_ffmpeg()` says where it
looks.

For lane.local (PM): the 16 ledger rows were accepted without a flicker check. A burst at each title's action (2-3 x
8 s, inside an existing hold) is about 1 min of device time per title. For lane.pathfind: `session3.sh`'s claim mode
(burst from the first gameplay step, while the hold continues) is the recipe; adding it to `pathfind.py` is a change
in your files, not mine.

NEW ISSUE: RalliSport Challenge: rival car bodies drawn on alternate frames only (shadows every frame)
Evidence: docs/lanes/flicker801/runs/s3/4D53000F-claim-1/b1/worst.jpg, -claim-3/b1, s2/4D53000F-claim/b1 (p90 14.1-194,
runs of consecutive hits in flicker.tsv), Nova, Safari stage start, 30-36 fps. Owner-observed 10-04. Blocks RalliSport
(4D53000F) as a Playable title. First measurement for the fixing lane: the frame dump in `noimages` mode at the race
start (`XEMU_FRAME_DUMP="300,after<N>,noimages"`). Does the guest issue the body draws every frame (we drop them), or
only on alternate frames (the game expects a persisting previous-frame copy we do not reproduce)? Recheck with
`flicker_score.py --gate` on a race-start burst.
