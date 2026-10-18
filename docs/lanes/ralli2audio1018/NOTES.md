# ralli2audio1018 notes

RalliSport Challenge 2 (4D530039) on the Nova, owner hand-play 2026-10-18
10:19-10:29 PDT. Scorer: fps_ok 0.9873, window median 59.76, gameplay 514 s,
audio_starve_share 0.0134 (bar 0.001), 3 hitches after warm-up, worst 1403 ms.

## Step 0: already tried (read before doing anything)

| Source | What was tried | Measured | Concluded / do not repeat |
|---|---|---|---|
| docs/investigations/audio-baseline.md s4 (383-505) | starve counter design; Galleon on the Thor, 120 s | 21/2936 short, all empty, all at startup; steady state 0/704 x4 | a merely-late producer gives PARTIAL fills; sink asks 8192 B; callback waits <= ~5 ms. Not a stress title, not the Nova |
| docs/investigations/audio-voice-headroom.md F1 | level meter on the audio thread | steady state 0.0000% on Galleon/DOA3/Crimson; startup windows 15-55% (empty calls) | startup starve is expected and excluded; steady starve is title/load specific |
| docs/investigations/audio-harness.md | PCM capture to FUSE from the APU thread | | capture itself can starve; the `starve:` line says `capture ARMED/off` (off in this run) |
| docs/lanes/nfsaudio1011 | buffer 256/512 samples; lock waits; `HAKUX_APU_PACE` | AAudio drains 1920 (2x960) regardless; BQL/voice-lock waits p50 19 us, max 97 us; pace cut NFS replays 15.7% -> 0.0% | pacing is now default on (apu.c:128-140). Shrinking the device buffer does nothing. Do not re-derive the burst mechanism |
| docs/lanes/audio1016 | MON_VP downmix; DSP path on MKSM | DSP path util 0.68 vs 0.26, starve 0.0% | the Nova keeps up with the DSP path on MKSM; do not expect DSP cost alone to starve |
| docs/lanes/forza414 | regime step (2-3 fps) | zero-fill 0.06% -> 40-47% in the same 2 s as the stall; perflog rerun did not reproduce (0%) | lock-step suspected (BQL or guest GPU wait), never named |
| docs/lanes/kabukistall | 20-130 s PFIFO compile stalls | `starve: 0/703` through the stall | a PFIFO/render stall ALONE does not starve audio |
| docs/lanes/idlehalt*, idlehaltdefault | `HAKUX_IDLE_HALT` (opt-in, off by default) | starve 0 on AUF/Blinx; DOA1U flipless 0.0048 on / 0.0077 off | idle halt is not an audio lever; off in this run (`[idlehalt] on=0`) |
| docs/lanes/fabledip1018 FINDINGS | Fable cold start | 2570 ms frame + 75.7% starve in one 5 s window, render idle, no compile | one-time cold-start cost, unnamed (asset I/O suspected) |
| docs/lanes/pipeline413, shaderfb569, shaderplan569 | `[shd413]` creation timing | 96% of a miss is Turnip inside vkCreateGraphicsPipelines on PFIFO; ~350-400 ms/create | async_compile as built still waits; module warm-up < 1%. Ranked plan in shaderplan569 s7 |
| docs/lanes/shaderprebuild569 | compile pool (3 workers), per-title key records, pre-build at renderer init (default on), cache save off PFIFO; GPL ladder `HAKUX_GPL=3` | warm cache: 43 creates 4661 ms -> 1-2 ms (Arctic Thunder); DOA pre-build 640 jobs/57 s | pre-build works on the SECOND run of a title once keys are recorded; new content still compiles cold. Shipped key sets designed, not built |
| pathfind rallisport2-1006 (compatrefresh1013/registry.tsv:578) | 10-06 route run | audio 0.230% short, fps_ok 0.9646, 602.6 s | failed on audio before this capture too |

Device env in this run (from the capture): `apu_pace: on (default)`,
`apu_meter: off`, `capture off`, device buf 8192 B, FIFO 49152 B,
`[idlehalt] on=0`, driver `PurpleVK-public Adreno (TM) 740` (not stock).

Correction to the brief: the `starve:` line is emitted at most every 5 s and
only when its interval had a short callback (or as a 30 s heartbeat); each
line is the DELTA since the previous line, not cumulative (apu.c:366-381).

## Board

Files claimed: (pending; analysis is offline so far)

## Stop rule

The same failure twice for one cause: stop and report.

## Status

[lane.ralli2audio1018] working: offline analysis of the owner capture.
