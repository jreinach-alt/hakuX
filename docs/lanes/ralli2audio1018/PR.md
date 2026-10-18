# ralli2audio1018: RalliSport Challenge 2 audio dropouts: the voice processor's guest-memory overhead, producer timing, audio thread priority

State: draft

Lane: ralli2audio1018            Issue: #433
Base: master @ f98feca3ba
Files: docs/lanes/ralli2audio1018/PR.md, docs/lanes/ralli2audio1018/NOTES.md, docs/lanes/ralli2audio1018/FINDINGS.md, docs/lanes/ralli2audio1018/tools/timeline.py, docs/lanes/ralli2audio1018/routes/ralli2audio1018-drive.route, hw/xbox/mcpx/apu/apu.c, hw/xbox/mcpx/apu/vp/vp.c
Prediction: none: audio-only change; no golden renders audio (pixels are untouched)
Needs device: yes    Needs NDK: yes
Selftest: none -- device-side C in apu.c and vp.c with no host tool or script to exercise; the vp.c change is checked by its device arm (`vp=` per frame in the `prod:` line)

Release note (performance): Fewer audio dropouts in scenes with many sounds playing (RalliSport Challenge 2's races), because the audio voice processor spends far less time on each sound.

In the owner's 10-18 RalliSport Challenge 2 session, 1.34% of the audio
output was short. That loss is the APU producer falling behind real time.
The sink does not drain in bursts: the produced-audio count fell 916 ms
short of wall time in the 5 s window that zero-filled 912 ms.

The `prod:` line this branch adds names the cause. In the race, about 120
voices are active per 32-sample frame, against 5 in the menus. The four
voice workers take 542-642 us of each 667 us frame, so the producer runs at
86-104% of real time with no slack. Any other load tips it under: a
shader-compile burst, or a run-queue wait.

In a voice-heavy race profile, 36.9% of the voice workers' CPU is the
guest-memory accessor path: RCU lock, translate, and dirty bookkeeping.

| Measure | Value |
|---|---|
| audio_starve_share (owner capture) | 0.0134 (bar 0.001) |
| worst producer deficit, 5 s window | 916 ms |
| active voices per VP frame, menus / race | 5 / about 120 |
| voice fork-join per 667 us frame, menus / race | 103-106 / 542-642 us |
| wall per 5.33 ms block in the race | 4.6-5.5 ms |
| guest-memory API share of voice-worker CPU (NFS MW race profile) | 36.9% |

This branch:

- `vp.c`: voice registers and SSL entries are read straight from guest RAM.
  It is the same bounds-checked access the sample and PRD reads already
  use, with a fallback above RAM. A register store whose value is unchanged
  is skipped. The output is byte-identical, so there is no flag.
- `apu.c`: a `prod:` line beside each starve line, with producer
  wall/CPU/run-queue/lock timing, the voice fork-join time, and the sink's
  worst short.
- `apu.c`: the APU voice workers run at nice -16, Android's audio priority.
  The frame thread was already at -16. `HAKUX_APU_PRIO=0` turns this off.
- `apu.c`: an opt-in deeper FIFO cushion (`HAKUX_APU_CUSHION`).

Expected:

- voice-worker time falls to about 390-450 us per frame;
- the producer runs at about 65-75% of real time.

Device verification on the Nova follows: one cold-cache arm, then the same
race twice for the bar. Detail is in `docs/lanes/ralli2audio1018/NOTES.md`
and `FINDINGS.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
