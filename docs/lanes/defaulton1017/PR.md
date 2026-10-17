# defaulton1017: S2T_CVT, REPORT_EARLY, FLDCW_CHAIN and IBC on by default, after one default-on screen (#1018)

State: draft

Lane: defaulton1017            Issue: #1018
Base: master @ 15f8524be1 (halo1016's fold, merged)
Files: accel/tcg/cpu-exec.c, hw/xbox/nv2a/pgraph/vk/reports.c, hw/xbox/nv2a/pgraph/vk/surface.c, include/accel/tcg/hakux-ibc.h, target/i386/tcg/translate.c, docs/testing/predictions/defaulton1017-screen.json, docs/testing/predictions/defaulton1017-tsc.json, docs/lanes/defaulton1017/PR.md, docs/lanes/defaulton1017/NOTES.md, docs/lanes/defaulton1017/forgeq.py, docs/lanes/defaulton1017/scratch/
Prediction: docs/testing/predictions/defaulton1017-screen.json @ d1ef1f1f548fe8220b722fd29ad675d2775b53ca54ccba996dd220fb956557e9, docs/testing/predictions/defaulton1017-tsc.json @ feacd0253e4cb6fde8a3945199fe2b1ab71766e1670244882e403283571d8e3c
Needs device: yes    Needs NDK: yes

Release note (performance): Halo: Combat Evolved's opening cinematic holds 30 fps through the hangar briefing (was 8-19 fps for ~47 s)

The four switches that remove Halo CE's opening-cinematic plateau (#1018) read unset as on, and `=0` as off,
each with a log line saying which. None was in the app's "Fast renderer paths" list, so the C getenv default is
what the shipped app reads.

REPORT_EARLY now answers early only an offset whose last GET_REPORT came one guest frame before (Halo's pattern).
An offset re-queued in the same frame (it would get another test's count) or two or more frames later (NFS Most
Wanted's slot ring, which its guest does not wait on) is written as before. Each early answer is compared with its
own test's count once the reader has it: `stale`, `vis` (one is 0 and the other not) and `desync` on the 2 s
`[rearly1018] w` line.

The screen, its rows and what each is looking for: `docs/lanes/defaulton1017/NOTES.md`, "The screen".

🤖 Generated with [Claude Code](https://claude.com/claude-code)
