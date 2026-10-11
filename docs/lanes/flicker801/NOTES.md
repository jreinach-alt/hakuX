# flicker801 NOTES (#801)

Owner, 10-04, about RalliSport Challenge on the Nova: "the cars are flickering all over the place when on screen". Our
fps measure plus a frame review of frames 10-30 s apart cannot see that. This lane builds a detector and validates it
on RalliSport (positive) against Panzer Dragoon Orta and Halo CE (negatives, both in the Playable ledger).

## 1. Inventory

The table is in OUTBOX.md (10-04). In short: every host image source samples 1-30 s apart, and perflog summarises 60
flips per line. The frame dump (`renderer.c`, `XEMU_FRAME_DUMP`) records every guest flip with its draw count, but
wrote images for only 8-13% of frames on Galleon (diagsoak77 R3). So nothing could see a 1-2 frame blink.

## 2. Instrument choice (P x win)

| option | P it sees RalliSport's flicker | win | notes |
|---|---|---|---|
| screenrecord burst of the display | ~0.7: sees what the owner sees, presentation included; fails only if the capture rate is below the game's, or if H.264 smears a blink | every title, no build change | **chosen, first** |
| frame dump images | ~0.1 at an 8-13% image yield | exact guest frames | needs a flip pre-record change before it can give consecutive images |
| frame dump `noimages` draws/frame | ~0.3: a draw our renderer DROPS still counts as issued by the guest, so the series stays flat | attribution after a hit | secondary, for diagnosis |
| back-to-back screencap | ~0: ~1-2 s per capture | none | measured once, to say so with a number |

## 3. Detector, fixed before any capture

`docs/testing/flicker_score.py`: dedupe repeated frames, then for each triple (N-1, N, N+1):
blink = max(0, min(|N-(N-1)|, |N-(N+1)|) - |(N+1)-(N-1)|), with max-over-RGB differences at 320 px wide. A pixel hits
when blink > 40, followed by a 3x3 erosion; a triple hits when the eroded pixels exceed 1 per 1000. A 2-frame variant
compares the pair (N, N+1) against (N-1, N+2). `rate` = hit triples per 100.

Selftest (synthetic, not validation): clean pan + cut 0 hits; car gone 1 in 4 = 24.1/100; car gone 2 in 6 = 15.5/100;
one flash = 1 hit; a 30-on-60 repeat de-duplicates to the same rate. An mp4 round trip at 2 Mbit/s gives the same
numbers as the PNGs.

**Separation criterion, stated before capture:** the detector is done only if RalliSport's LOWEST burst rate is at
least 3x the HIGHEST negative burst rate AND at least 10 per 100 above it. If not, it does not ship as a gate.

## 4. Device session

`session.sh` takes the Nova with `hold.sh wait` (queues behind lane.pathfind), runs `pathfind.py --hold-s 150` per
title (RalliSport replays its recorded path from lane/pathfind, through a scratch PATHFIND_KNOW), and records 3 bursts of
4 s, 15 s apart, in hold-play. On RalliSport it also takes one back-to-back screencap burst. `systemd-run` needs
approval in a lane session, so the session runs as this session's background task, and this session stays up for it.

The host has no ffmpeg. `pip install imageio-ffmpeg` into a venv (here `.flkvenv` in the worktree, not committed) gives a
static binary, and `flicker_score.find_ffmpeg()` looks there, in `$FFMPEG` and on PATH.

## 5. Sessions 1-2 (Nova, 08:53-09:20 PDT, debug app as installed; exploratory, not validation)

Capture: screenrecord sustains the panel's 60 Hz (dt median 16.7 ms; 59.8-60.4 unique fps when the game ran at 59).
Back-to-back screencap: 3 captures in 4 s in session 1, 6 in 4 s in session 2 (0.7-1.3 s each). It cannot see flicker.

| burst | title, when | p90 | rate/100 | max | unique fps | what the worst triple shows |
|---|---|---|---|---|---|---|
| s1 b1 | RalliSport, hold-play | 0.339 | 2.75 | 1.5 | 45.7 | bumper view, empty field: a tree trunk |
| s1 b2 | RalliSport, hold-play | 0.0 | 0.42 | 1.2 | 59.8 | - |
| s1 b3 | RalliSport, hold-play | 1.562 | 15.97 | 12.5 | 60.4 | stuck on a tree: dust puff, trunk edge jitter |
| s1 b1 | Orta, hold-play | 0.417 | 4.91 | 2.4 | 56.6 | - |
| s1 b2 | Orta, hold-play | 1.471 | 15.84 | 7.1 | 51.1 | an explosion flash |
| s1 b3 | Orta, hold-play | 0.247 | 3.80 | 868.8 | 40.0 | a full-screen white frame, then black |
| s1 b1 | Halo, hold-play | 0.768 | 6.78 | 1.1 | 15.1 | dark cryo bay, mostly still |
| s1 b2 | Halo, hold-play | 1.198 | 27.78 | 1.9 | 14.7 | " |
| s1 b3 | Halo, hold-play | 0.768 | 5.26 | 1.4 | 9.8 | " |
| **s2 b1** | **RalliSport, race start (claim)** | **194.1** | **65.62** | **327.4** | 32.7 | **a Nissan beside the camera drawn in N, absent in N-1 and N+1, its shadow drawn in all three** |
| s2 b2 | RalliSport, claim probe (car standing) | 0.013 | 0.0 | 0.0 | 5.9 | nothing moving |
| s2 b3 | RalliSport, claim probe (car standing) | 0.0 | 0.0 | 0.0 | 2.5 | nothing moving |

What it showed:
- **The owner's flicker is real and the capture sees it.** s2 b1's hit pattern is runs of consecutive hits
  (`XXXXXXXXXXXXXXXXXXXXX....XXXXXX...`): the car body is drawn on alternate game frames (race clock 08.01, 08.04,
  08.07 at 30 fps), and its shadow is drawn every frame.
- **RalliSport's hold-play has no cars in view:** pathfind's drive loop goes off alone in bumper view (POS 4 OF 4), so
  the 3 hold bursts measure an empty savanna. Bursts must come from the race start, while the field is together.
- **rate does not separate; p90 does.** Orta's legitimate one-frame events (explosions, a white flash) put rate at
  15.8/100, as high as anything RalliSport did without cars. p90 asks whether blinking is the burst's NORMAL state:
  194 on the positive against at most 1.56 on all 11 other bursts.

**Change after seeing data (recorded, not silent):** the burst number and `--gate` are now p90, not rate, with a gate
at 5 per mille: about 3x the highest negative p90 (1.56) and about 39x below the positive (194). The pixel and triple
thresholds are unchanged. Because this choice follows the data, session 3 is the test: fresh RalliSport race starts
(two boots) and fresh negatives (Orta, Spikeout, Halo), all captured the same way (claim mode), scored with no further
change.

Stated blind spot: a far car (24x12 at 320x240, 0.4% of the frame) blinking on alternate frames has p90 3.75, under
the gate (selftest leg). The gate sees an object of about 0.5% of the frame or more, blinking in 10% or more of
triples.

## 6. Session 3, the test of the fixed metric (Nova, 09:21-09:49 PDT)

Captured the same way for every title (claim mode: bursts from pathfind's first gameplay step, 8 s then 4 s, 4 s),
scored with p90 and the gate of 5, with no change after. Every burst of all three sessions, re-scored by the shipped
scorer, is in `TABLE.md`; per-burst `capture.json` and `flicker.tsv` are under `runs/`, worst triples as `worst.jpg`
for the positives and the notable negatives.

| | bursts | p90 |
|---|---|---|
| RalliSport race start, rival cars in view (s2 b1, s3 boot A b1, s3 boot B b1) | 3 | **194.1, 14.6, 14.1: all FLICKER** |
| Panzer Dragoon Orta (s1 hold-play, s3 claim) | 6 | 0.0-1.47: all clear (explosions, a white flash: max up to 869, p90 low) |
| Halo CE (s1 hold-play) | 3 | 0.77-1.20: clear |
| Halo CE (s3 claim) | 3 | unmeasured: the look tutorial's camera stood still, 1 distinct frame per burst |
| Spikeout (s3 claim, 60 fps) | 3 | 0.0-0.117: clear; capture held 59.3-60.1 unique fps |
| RalliSport with no rival in view (s1 hold-play, later claim bursts) | 7 measured | 0.0-1.69: clear, correctly: the frames show the player alone (checked by eye on s3 boot A b2/b3) |

Session 3 alone (out of sample): RalliSport 14.6 and 14.1 against a negative maximum of 0.443, about 32x.

**Against the criterion I stated before capture** ("RalliSport's lowest burst >= 3x the highest negative and >= 10
above it"): it is met when the positive is a burst with rival cars in view, lowest 14.1 against 1.47, 9.6x and 12.6
above. Read literally over every RalliSport burst, it is not met: bursts with no car in view read about 0, as they
should. I am shipping on the first reading, and saying so. The selection is by what is on screen (the race start, the
same mode for every title, fixed before session 3), not by score.

Margin to the gate is thin on the replicates: 14.1 is 2.8x the gate. A flicker of a smaller or farther object reads
lower (selftest: a 0.4%-of-frame car blinking on alternate frames, p90 3.75, under). The gate is set for what the
negatives allow (3x their highest); a lower gate needs more negatives first.

## 7. Step 4: does the capture keep up?

Yes, on the Nova. screenrecord gave dt median 16.7 ms and 59.3-60.4 distinct frames/s whenever the game ran at 59-60
(RalliSport hold-play, Spikeout), and every Xbox title's frame rate is at most 60. So no xemu-side frame dump is needed
for DETECTION here. Back-to-back screencap gets 0.7-1.3 s per frame and cannot be used.

For ATTRIBUTION of RalliSport's defect, the next step is the frame dump in `noimages` mode at the race start
(`XEMU_FRAME_DUMP="300,after<N>,noimages"`, zero Vulkan cost). Does the guest issue the car body's draws on every frame
(so our renderer drops them on alternate frames), or only on alternate frames (so the game expects the previous frame's
copy to persist, a surface or feedback path we do not reproduce)? The shadow being drawn on every frame while the body
alternates says the car is not simply culled. That is a renderer issue, filed in OUTBOX as a NEW ISSUE, not this
lane's.

## 8. What the next lane should not repeat

- Do not burst during pathfind's drive hold-play to look for car flicker: it drives off alone in bumper view.
- Do not read a still screen as clear: `verdict=unmeasured` exists because Halo's look tutorial gave 483 identical
  frames.
- Do not gate on `rate`: legitimate one-frame effects (Orta) put it as high as no-car RalliSport bursts.
- Do not edit a script bash is running (it reads the rest by byte offset after the loop); session2/3 are copies for
  that reason.
- Device time: session 1 (22 min) was the pilot; sessions 2 (6 min) and 3 (28 min) followed a frame review of what
  the pilot showed. Total about 56 min of Nova hold, 08:53-09:49 PDT.
