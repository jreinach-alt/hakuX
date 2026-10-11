# Flicker check before a Playable (#801)

An fps pass and a frame review of stills taken 10-30 s apart cannot see flicker. Flicker is an object that is drawn
in frame N, gone in N+1 and back in N+2. On 10-04 RalliSport Challenge drew its rivals' car bodies on alternate frames
(their shadows on every frame), at a clean fps. This check runs before a title is accepted.

## The one line

With the device held by you (`docs/testing/jobs/hold.sh take <dev> <tag> <why> && hold.sh wait-idle <dev> 900`) and
the title in live play, **with the things that matter on screen** (rival cars at a race start, enemies in a fight,
not an empty corridor):

    python3 docs/testing/burst_capture.py --device nova --hold-tag <tag> --seconds 8 --out <run>/flicker1

It prints `flicker: p90=...`. **p90 > 5 is FLICKER**: open `<run>/flicker1/flicker_worst.png` (the worst triple of
frames, then the middle frame with the blinking pixels in red) and do not accept the title until a person has looked.
p90 <= 5 is clear for what was on screen. Take 2-3 bursts at different moments; one clear burst of an empty scene
proves nothing.

To re-score a burst offline, or gate in a script: `python3 docs/testing/flicker_score.py <burst.mp4|frames dir> --gate`
exits 1 over the gate.

## How to read it

- `p90`: the 90th-percentile triple score, in blinking pixels per 1000 after a 3x3 erosion. A defect recurs, so most
  triples score. A legitimate one-frame effect (an explosion, a muzzle flash, a white transition frame) is an event,
  so it raises `max` and `rate` and leaves p90 low.
- `unique_fps`, `dup_share`: what the capture actually got. screenrecord runs at the panel's 60 Hz. A 30 fps title
  shows dup_share ~0.5. If unique_fps is far below the title's fps (a capture that could not keep up), a clear result
  is not a result.
- `rate`, `max`: kept for diagnosis, not gated.

## What it cannot see

- An object smaller than about 0.5% of the frame (a far car, about 80x80 px of the Nova's 1280x960) blinking on
  alternate frames is under the gate.
- Anything that is not on screen during the burst. RalliSport's hold-play drives off alone in bumper view, and those
  bursts read clean: the cars are only in view at the race start.
- A 60 fps title whose defect alternates faster than the panel can show it.

## Results that set the gate (Nova, 10-04)

| title | role | bursts | p90 |
|---|---|---|---|
| RalliSport Challenge, race start (rivals in view) | positive (owner saw the cars flicker) | 3 | 194.1, 14.6, 14.1: FLICKER |
| Panzer Dragoon Orta | negative (in the ledger) | 6 | 0.0-1.47 |
| Halo: Combat Evolved | negative (in the ledger) | 3 (+3 unmeasured, still camera) | 0.77-1.20 |
| Spikeout: Battle Street | negative (in the ledger) | 3 | 0.0-0.12 |

The gate (5) is about 3x the highest negative. Every burst is in `docs/lanes/flicker801/TABLE.md`; the method and its
history, including the change from `rate` to `p90` after the first session, are in `docs/lanes/flicker801/NOTES.md`.

## Exit codes

`flicker_score.py --gate`: 0 clear, 1 FLICKER, 2 unmeasured (fewer than 20 distinct-frame triples: a still screen,
which proves nothing). `burst_capture.py` exits 3 when the device is not held by `--hold-tag`.
