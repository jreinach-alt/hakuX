# ralli2audio1018: RalliSport Challenge 2 audio dropouts: producer timing, and the audio threads at audio priority

State: draft

Lane: ralli2audio1018            Issue: #433
Base: master @ 343221f6fc
Files: docs/lanes/ralli2audio1018/PR.md, docs/lanes/ralli2audio1018/NOTES.md, docs/lanes/ralli2audio1018/tools/timeline.py, docs/lanes/ralli2audio1018/routes/ralli2audio1018-drive.route, hw/xbox/mcpx/apu/apu.c
Prediction: none: audio-only change; no golden renders audio (pixels are untouched)
Needs device: yes    Needs NDK: yes
Selftest: none -- device-side C in apu.c with no host tool or script to exercise

Release note (stability): RalliSport Challenge 2 and other titles lose less audio while shaders compile, because the audio threads now run at audio priority.

In the owner's 10-18 RalliSport Challenge 2 session, the audio was short
in 1.34% of output. That loss is the APU frame thread falling behind real
time. The sink does not drain in bursts. The level meter's produced-audio
count fell 916 ms short of wall time in the 5 s window that zero-filled
912 ms. The two big windows sat on shader-compile bursts: 6 s of
background compile in 3 s, and 28 fragment-library compiles on the draw
thread. The 1403 ms freeze, a JIT re-translation after a code reload,
starved nothing.

This branch:

- adds a `prod:` line beside each starve line, giving producer
  wall/CPU/run-queue/BQL timing and the sink's worst short;
- runs the APU frame thread and its voice workers at nice -16 (Android's
  audio priority; `HAKUX_APU_PRIO=0` turns it off);
- adds an opt-in deeper FIFO cushion (`HAKUX_APU_CUSHION`).

Device verification on the Nova is queued. Numbers are in
`docs/lanes/ralli2audio1018/NOTES.md`.

| Measure (owner capture) | Value |
|---|---|
| audio_starve_share | 0.0134 (bar 0.001) |
| worst producer deficit, 5 s window | 916 ms |
| starve during the 1403 ms freeze | 1 short / 456 callbacks |
| tail (109-420 s) | 1-4 shorts per window, producer wobble +-45 ms |

🤖 Generated with [Claude Code](https://claude.com/claude-code)
