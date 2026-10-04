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
