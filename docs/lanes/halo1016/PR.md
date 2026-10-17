# halo1016: Halo CE cutscenes on the Nova -- quiet speech under loud music (#938), cinematic at 8-19 fps (#1018)

State: draft

Lane: halo1016            Issue: #938, #1018
Base: master @ 61ae61dd91
Files: docs/lanes/halo1016/**, docs/testing/predictions/halo1016-*.json, hw/xbox/mcpx/apu/vp/hrtf.h, hw/xbox/mcpx/apu/vp/vp.c, hw/xbox/nv2a/pgraph/vk/surface.c, hw/xbox/nv2a/pgraph/vk/reports.c, target/i386/tcg/translate.c, target/i386/tcg/fpu_helper.c
Prediction: docs/testing/predictions/halo1016-cinesplit.json @ 88edbbdfa3e0c12241ab27e0191bd39169bc5f22821408686c6415fdc40d92b8 (judged), docs/testing/predictions/halo1016-speech.json @ 397046c508a1ef966ecbbf8a9f7cd1742d5e156d6af31b3e196a9624ba56d04e (judged), docs/testing/predictions/halo1016-census.json @ 1cb4052f9a4ef54af2a29497ca18fb5144a7f7119a26f556014e9737b40fe179 (judged), docs/testing/predictions/halo1016-vcpu.json @ 607a0b0b8b389b5769c6132a0d54c8e9328ffeec350c9022bf31b934256c3727 (judged), docs/testing/predictions/halo1016-tier1.json @ 3f87d2ed401c97a8a548b75ac42b57b0cf30d678daf3b0404cb18a982fbbc59c (judged), docs/testing/predictions/halo1016-reports.json @ 5c7a0d0f6b92f22cb8cbb1e7164e77de23cd744c0b96b7fa20b4d8d1ef90768f (judged: both arms VOID on V, read descriptively), docs/testing/predictions/halo1016-early.json @ 755fc958688ea7c02c01e8b32179cb31c8e475157b7ac1963b03f6603ce09325 (judged)
Needs device: yes    Needs NDK: yes

Release note (none): instrumentation and off-by-default switches. An APU per-voice mix meter (HAKUX_APU_METER) and HRIR scale switch (HAKUX_APU_HRTF_NORM), an overlap-eviction census line ([ovl1018]) in the Vulkan surface cache, an FLDCW call counter, HAKUX_FLDCW_CHAIN (FLDCW keeps its translation block unless the precision bit flips), HAKUX_REPORT_CATCHUP (an occlusion report is written as soon as the GPU FIFO catches up), HAKUX_REPORT_EARLY (an occlusion report the game waits on is answered at once with that test's previous count), and HAKUX_REPORT_SUBMIT (the GPU is started at an occlusion report); nothing a player sees or hears changes by default.

This is a deep dive into two defects in Halo: Combat Evolved's opening cinematic on the Nova,
targeting 0.5.2. The owner hit both while playing 0.5.1-rc1 by hand: the dialogue is quiet under
loud music (#938), and a ~47 s stretch runs at 8-19 fps (#1018). Each symptom's account, the
hypothesis tables and the remedies are in `docs/lanes/halo1016/NOTES.md`.

## #1018: what the cinesplit A/B found (judged by cineread.py, committed before either arm landed)

| leg | claim | result |
|---|---|---|
| S | the PFIFO thread is on-CPU for most of the plateau | MISS (the threshold was mis-scaled; see NOTES) |
| G | the GPU is the bottleneck (gpu/P high) | MISS: gpu/P 0.17 |
| W | the off-CPU time is synchronous SURFACE_DOWN finishes | HIT: 61.17 sdown/f, 33.01 ms/f |
| P | sysmem-backed surfaces shorten the period | MISS: period ratio 0.96 |

On the plateau, the draw thread spends ~33 ms a frame blocked in `pgraph_vk_finish(SURFACE_DOWN)`,
at 61 to 129 calls a frame. The guest sits in its idle loop while it waits, and the GPU's own time
is small.

## #1018: whose downloads (census, judged by censusread.py, committed before either arm ran)

| leg | claim | result |
|---|---|---|
| O | overlap eviction fills the plateau | MISS: `[ovl1018]` 0.00/f |
| K | the texture path fills it | HIT: 49.28 txr dl/f, every one reason `cvt` |
| R | CPU range reads | MISS: 0.00/f |
| C | `HAKUX_S2T_CVT` removes them | HIT: 0 downloads, 59.3 -> 41.9 ms/f |

Every download is the #986 MKSM mechanism: a 2-byte colour surface sampled as a 5/6-bit texture.
With them gone, the shots are still 40-61 ms a frame and the guest never idles: the vCPU is the
second bound. 73% of its main-loop returns are one guest instruction, `fldcw` in the CRT's
`_control87`, because the FP JIT ends every translation block after FLDCW.

## #1018: the vCPU half (`halo1016-vcpu.json` and `halo1016-tier1.json`, judged)

Two remedies, alone and together, on the `HAKUX_S2T_CVT` base:
- `HAKUX_FLDCW_CHAIN=1` (this PR, off by default): FLDCW stays in its translation block unless it
  flips the precision bit, the only part of the control word a block is specialised on;
- `HAKUX_IBC=1` (#507, parked off): the inline jump-cache probe, against 930 k helper lookups a
  frame in those shots.

| arm | ms/f over the span | x A | what it removed |
|---|---|---|---|
| A | 42.6 | 1.000 | -- |
| F | 40.5 | 0.951 | the FLDCW returns at 0x1ec3a: 36 k a frame to 0 |
| I | 40.5 | 0.951 | helper lookups: 863 k a frame to 13.6 k |
| IF | 39.2 | 0.921 | both |
| A2 | 41.6 | 0.977 | -- (the base again) |
| T | 40.8 | 0.958 | `HAKUX_TIER1_THRESHOLD=0`: the 8 k CF_INVALID exits a frame to 0 |
| FIT | 39.4 | 0.925 | all three |

Both mechanisms are removed in full, and the frame gains only 2-3 ms. The reason is that the
heavy shots' two hottest blocks are one loop. The guest polls a visibility-test (occlusion) result
through D3D until its status word leaves -1. That poll is 27% of A's translated-code time and 44% of
IF's, so the vCPU time the remedies saved went into polling longer.

## #1018: the poll (`halo1016-reports.json`: both arms VOID on V; read descriptively)

The prediction assumed the synchronous report path. The app's "Fast renderer paths" default turns
on the async reader (`HAKUX_REPORT_ASYNC=1`), so both arms void on their own V leg. Read without
the legs, the trace shows where the wait is:

| arm | ms/f | reports/f | queued -> handed off >= 2 ms | queued -> written >= 16.7 ms | spin share |
|---|---|---|---|---|---|
| RT (trace) | 43.1 | 544 | 100% | 77% | 0.290 |
| RC (+ `HAKUX_REPORT_CATCHUP=1`) | 42.0 | 542 | 100% | 78% | 0.313 |

Every one of the ~544 occlusion reports a frame is armed. Each waits for the frame's last
submit, and then for the GPU to run that whole command buffer; the median is ~28 ms from queued
to written. The game reads each result about a frame later and spins until it lands. The
catch-up submit never fired (0 a frame): the FIFO is never empty with a report queued.

## #1018: the remedies the trace points at (`halo1016-early.json`, judged by earlyread.py, committed before any arm ran)

- `HAKUX_REPORT_EARLY=1` (this PR, off by default) answers an armed report when it is queued,
  with the count its offset was last written with. The reader's own count goes to that table,
  not to the game. This is RPCS3's "relaxed ZCULL sync" trade: a result one test stale.
- `HAKUX_REPORT_SUBMIT=<us>` (this PR, off by default) submits at an armed report, so the GPU
  starts on the draws before it, nearer to when the NV2A writes one.

All arms run on the `HAKUX_S2T_CVT` base, over [mark+131, mark+191]:

| arm | ms/f | spin share | |
|---|---|---|---|
| B (base) | 42.1 | 0.252 | |
| E (`HAKUX_REPORT_EARLY=1`) | 35.9 | 0.010 | 972289 of 972302 armed reports answered early |
| EIF (E + `HAKUX_FLDCW_CHAIN=1` + `HAKUX_IBC=1`) | **33.8** | 0.015 | every 10-s window 33.4-34.7 |
| S (`HAKUX_REPORT_SUBMIT=2000`) | 38.4 | 0.114 | 4.07 finishes a frame; reports written 4-8 ms after queue |
| EV / BV (E / B with frames) | 35.1 / 41.9 | 0.006 / 0.246 | 0.838, repeats E/B's 0.852 |

The legs:
- EA, EP, XM and SQ HIT.
- EM MISSES by 0.002 (0.852 against 0.85).
- EG and XG MISS. XG is EIF 33.8 against 33.4; the windows still over the bar are +127..+139, where
  the vCPU is the bound.
- SM MISSES (S 0.912 against a 0.90 bar).

The pictures show the same shots with every object present. They cannot show R8's one possible
cost: a flare one frame late at a camera cut. The animation advances per rendered frame, so
20-s stills are not equal content. Checking for that needs frames captured every frame across a cut.

## #1018: root causes, and what shipping it takes

There are three causes in series. Each one hid the one after it:

| cause | switch | over the span |
|---|---|---|
| 49 `cvt` surface downloads a frame (#986's mechanism) | `HAKUX_S2T_CVT` (fps1015) | 59.3 -> 41.9 ms/f |
| the guest spins on ~544 visibility-test reports a frame | `HAKUX_REPORT_EARLY` (this PR) | 42.1 -> 35.9 |
| the vCPU's own work (FLDCW exits, helper lookups) | `HAKUX_FLDCW_CHAIN` (this PR) + `HAKUX_IBC` (#507) | 35.9 -> 33.8 |

All four switches are off by default, so this PR changes nothing a player sees. Shipping the fix in
0.5.2 means turning all four on together through one by-mechanism default-on screen. The screen is
specified in NOTES.md ("What default-on needs"), and it is requested from lane.xbox. The release
note for that flip:

`Release note (performance): Halo: Combat Evolved's opening cinematic holds 30 fps through the hangar briefing (was 8-19 fps for ~47 s)`

`HAKUX_REPORT_SUBMIT` and `HAKUX_REPORT_CATCHUP` are measured and lose. They stay off and are not proposed.

## Selftest fragments this change needs (read from the diff)

- `10-arms-list.sh` and `20-arms-queue.sh`: the diff adds seven committed predictions, and
  `arms.sh list` / `run` parse every committed one. Both fragments require them to be fenced
  behind the watermark, so the live fixture stays the only pair queued.
- `75-nv2a-index.sh` and `75-nv2a-index-drift.sh`: the diff inserts lines in `vk/reports.c` and
  `vk/surface.c`, which `docs/testing/nv2a_index.json` cites by file:LINE. The index is not
  regenerated; its check passes on anchor matching across line shifts, and that is what these
  two fragments pin.
- `99-release-note-line.sh`: the body carries a `Release note (none):` line for the emulator code
  under hw/ and target/.

The APU (vp.c, hrtf.h) and TCG (translate.c, fpu_helper.c) changes have no selftest fragment.
Nothing under jobs/ reads them.

## #938: what the speech legs found (judged by speechread.py, committed before either leg ran)

| leg | claim | result |
|---|---|---|
| B | speech sits over music in hakuX, as the registers at two state moments put it | MISS: median -4.3 dB |
| L | the guest's HRIR taps sum under 1, so today's L1 division raises the 3D bed | MISS: l1 ~13 |
| N | the raw HRIR scale lowers the bed 3 dB and lifts speech | MISS: bed 20 dB louder, clips |
| S | the dialogue stream starves in the slow shots | MISS: 0 sslempty |

The HRIR scale and stream starvation are refuted. The music, not the 3D bed, is what sits over
the speech, and hakuX plays it at the title's own registers:
- through the same ADPCM decoder as the speech;
- on the same bins;
- with no filter or envelope on either voice.

The dialogue's margin is +2 dB in the first two minutes and -2 dB in the score's swells. This
PR proposes no #938 change. A hardware listen at the named times decides what is left.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
