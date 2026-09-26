# lane.fps382 -- 50 Cent: Bulletproof intro FMV at ~14 fps on the Nova (#382)

Master 2dc2b5c49a. Nova (ee317437). All claims are about the hands-off boot
movies, not gameplay.

## 1. The movies' native rate: 30 fps (read off the disc, no device)

The disc's movies are Sofdec (`.sfd`, MPEG-1 program streams, decoded in
software on the guest CPU). The boot set lives in `ark/Movies/`. Each file was
read over the console's FTP (read-only: CWD/LIST/RETR, the same access as
`titles/bin/stage_xiso.py`, with no staging batch running) and parsed with
`sfdinfo.py` here.

| file | size | rate (sequence header) | pictures | duration |
|---|---|---|---|---|
| legal.sfd | 640x480 | 30.000 | 120 | 4.0 s |
| claimer.sfd | 640x480 | 30.000 | 120 | 4.0 s |
| DolbyN.sfd | 640x480 | 30.000 | 121 | 4.0 s |
| sierra.sfd | 640x480 | 30.000 | 211 | 7.0 s |
| GGLogo.sfd | 640x480 | 29.970 | 251 | 8.4 s |
| havok.sfd | 640x480 | 30.000 | 120 | 4.0 s |
| inter.sfd | 640x480 | 29.970 | 582 | 19.4 s |
| teaser.sfd | 640x480 | 30.000 | 2910 | 97.0 s |

The video PTS agree: teaser's run 0 to 96.90 s over 2908 pictures, which is
30.01 pictures/s. **No picture is a coded repeat.** In every 10 s bucket of
teaser.sfd, 0% of pictures are under 1% of the median I picture (45.7 KB),
except the fade-out in the last 7 s (28%). The mean is 19-28 KB per picture
throughout. So 10 fps is not in the content. At 10 Hz the player shows about
two pictures in five.

## 2. What the soaks show (two runs on 6561442869, read from disk)

`timeline.py` and `cpuread.py` here read runs `0-0-y-1790409600-titlebench-9`
(which exited at 92 s) and `0-0-y-1790411511-titlebench-9r` (240 s). The two
runs track each other line for line. Every gfps line lands within 0.4 s of
its twin, and the G medians agree to within 1 ms.

The spans below are from `judge.py` on the 9r run. Slow is the longest run of
gfps-line intervals at or below 12 fps. Fast is the longest run at or above 25.

| | slow span (58-172 s) | fast span (172-202 s) | 204-265 s |
|---|---|---|---|
| fps (gfps-line cadence) | 10.5 | 30.2 | ~20 |
| G (flip-to-flip, ms) | 99.5 (85-107) | 33.4 | 40-52 |
| VBLANKs per flip | 5.9-6.00 | 2.00 | 2.5-3.0 |
| renderer busy (1 - Ri/G) | **4%** | **4.5%** | 5-8% |
| vCPU thread CPU (ms per 2 s) | 1944 | 1963 | ~1940 |
| slow stores/s (hakuX-pages) | **2,505,844** | **4,034** | ~1,250,000 |
| tlb_set_dirty (sd) per 2 s | **5,085,704** | **8,065** | ~2,500,000 |
| audio zero-filled | 0% | 0% | 0% |

What this says:

- **The renderer is not the cost.** It is 95% idle in the 10 fps span, just
  as it is in the 30 fps one. GPU time, recording time and per-site stall
  counters cannot explain a span in which the renderer thread waits 95 ms of
  every 100.
- **The guest never idles.** The vCPU thread burns 97% of wall time in every
  span. Blinx showed the same in its 60 fps menus (blinx372), so this alone
  says nothing about cause.
- **Guest stores separate the spans.** While a movie is decoding, stores into
  seven 4 KB pages at guest va 0x821A5000-0x82260000 (contiguous memory, about
  a 640x480 frame's planes) take the notdirty slow path, about 2.5M per
  second. Every one of them calls `tlb_set_dirty` (sd is roughly equal to the
  slow-store count), and the next store to the page takes the slow path
  again. Each page's slot has over 1.1M slow stores, with offsets covering the
  whole page (0..1000). The rate runs inverse to fps: 2.5M/s at 10 fps,
  1.25M/s at 20 fps, and 4k/s at 30 fps. The 30 fps span is the only span
  with no movie decoding in it. It follows the teaser, and the slow span's
  114 s is the teaser's 97 s stretched 1.18x, so the fast span is probably the
  in-engine front end.
- **The 114 s slow span is the teaser.** It shows 1,200 flips against 2,910
  coded pictures, 41% of them, over 1.18x the teaser's own length. The player
  both drops pictures and runs late. That is a decoder that cannot keep up.

Verdict so far: **not content-paced. The emulator is the cost, on the vCPU,
not the renderer.** The brief's falsifier looks only at the renderer, so on
its own terms it would read "content-paced" (the present interval is at most
111 ms and the renderer is under 60% busy). The disc refutes that reading.
The brief's "guest idle-waiting" is false (vCPU 97%). The renderer-based
emulator-cost leg is false too, because the cost is not on the renderer.

## 3. Soak on master (registered before it ran)

Prediction: `docs/testing/predictions/fps382-intro-soak.json`. Judge:
`judge.py <logcat> --prediction <json>`. Status: queued.

## Do not repeat

- Do not read the renderer to decide this title. It idles in every span.
- Do not look for the ISO on the host. The title pipeline deletes the local
  XISO once the handheld copy is verified. The files are on the console
  under `/G/Games/50Cent/ark/Movies/`.
- Do not treat vCPU busy % as evidence of "decode-bound" by itself. It is 97%
  at 30 fps too.
