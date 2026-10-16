nfsaudio1011: HAKUX_APU_PACE in apu.c, off by default -- pacing at the low watermark removes NFS Most Wanted's audio replays (#433, 0.5)
State: ready

Lane: nfsaudio1011      Issue: #433 (umbrella), none filed
Base: master @ 13e0590809 (the lane's earlier head e19b43b94a is in master as 3ce6b6ac96; this head adds apu.c)
Files: hw/xbox/mcpx/apu/apu.c, docs/lanes/nfsaudio1011/NOTES.md, docs/lanes/nfsaudio1011/OUTBOX.md, docs/lanes/nfsaudio1011/PR.md
Prediction: docs/testing/predictions/nfsaudio1011-fix.json @ daa1d9f2c147153a1c2f28ce53ce901db11ecb5dfb2194bb90ce9fa849b5c588; docs/testing/predictions/nfsaudio1011-fix-titles.json @ 546962020bb6a16aa078efd64d118fb2b4dc961ad995f747f5aee6cb935727d1; docs/testing/predictions/nfsaudio1011-identify.json @ 4a986123485b7c1b7a83e95542f89e655be1e8487a56a70e665c1d9d9170475d
Needs device: yes (Nova)    Needs NDK: yes
Release note (none): the fix is HAKUX_APU_PACE in apu.c and the rest is an APU voice log (HAKUX_APU_VOICELOG); both are off by default. Once the pacing is on by default, its note is "Need for Speed Most Wanted: fixed stuttering audio in movies and speech".

This head adds one code file to what master already has from this lane (fold 3ce6b6ac96, PR #935): the pacing switch
in apu.c, which the first fold carried only as `docs/lanes/nfsaudio1011/apu.c.patch`. apu.c's emulator code here is the
code the fix arms ran (ref `9c054c1714`; `git diff 9c054c1714 HEAD` outside docs/ is empty). Checks on this head:
`preflight.sh` passes; `docs/testing/jobs/selftest.sh`: 3377 passed, 0 failed, all 136 fragments.

**The fix.** `HAKUX_APU_PACE=1` (apu.c, `throttle()`) wraps the Android early return in `if (!apu_pace_on())`, so
Android runs the low-watermark pacing that every other build already runs. It is off by default, so the shipped path is
unchanged. The switch is read once and logged once (`hakuX-audio: apu_pace: on|off`). The committed apu.c is
byte-identical to the one in scratch commit `9c054c1714` (this lane's head plus `docs/lanes/nfsaudio1011/apu.c.patch`),
which every arm below ran. Compile check: apu.c alone with NDK 29 clang and the host Release build's arm64-v8a flags,
`-Wall`, clean but for target_page.h's existing warning. The new code is all under `#ifdef __ANDROID__`.

**What goes wrong.** NFS MW plays its movie and PSA audio from a looping 2400-sample (50 ms) 5.1 PCM ring. Three stereo
voices move together: v=244/245/246, `buf loop=1 ebo=2399`. The game keeps its write head **exactly 992 samples ahead
of the read position (CBO) it last saw**: `ahead=992` at 2937 of 2950 burst starts. On the hardware the CBO advances 32
samples every 0.67 ms, so 992 samples is a 21 ms lead and plenty. In this emulator on Android, `throttle()` returns
before its low-watermark pacing. So after each drain of the output fifo, the VP runs 64 or 128 VP frames (2048 or 4096
samples) back to back in a few ms of host time, then waits 45-52 ms. Each burst passes the game's write head 992
samples in, and from there to its end it plays what the ring held a lap earlier. That is the 50 ms-old audio the owner
hears.

From the identify run `1-1791770282-lane.nfsaudio1011-2057093` (`HAKUX_APU_VOICELOG=1`):

```
apuvoice burst n=74 f=4928 t=6932987 wait=44244 th=44228 x=16 v=244 ... cbo=1440 ebo=2399 head=0 ahead=992 hd_age=40928 prev=128/32
apuvoice stale v=244 region=0x1f40 cbo=32 blocks=23 ssl=A0 f=4960 t=6937751 lap=54384 ... burst=74 boff=32 wait=44244
```

Burst 74 starts with the CBO at 1440 and the game's newest write at block 0: (0+1)·32 − 1440 mod 2400 = 992 samples
ahead. The first stale read is at `boff=32`, 1024 samples into the burst: the first block past the head. Over the run,
`32·boff − ahead` is exactly +32 in 56% of bursts and within ±256 in 67.9%. Other causes were checked and ruled out:

- the VP reading the wrong place: `sslrep=0`, `sslempty=0`;
- a writer that fell behind: the lead is a constant 992 at every burst start;
- a guest voice update before the burst (Addendum 2): v=245/246 are never addressed and replay as much as v=244;
- bql or the voice lock: the wait before a burst is all throttle(), with x p50 19 µs.

NOTES.md has the full legs table.

**The fix arms.** One binary, `9c054c1714`, on the Nova: NFS MW, 180 s from boot, no route, no VOICELOG. The env is
the only difference. Arms were queued OFF, ON, ON, OFF. Judge: `tools/fixjudge.py`, which compares against lane.local's
837057 for slope and the PSA window.

| arm | result id | lag-2400 share | PSA window | any-lag share | slope 0-25 s | level dBFS | gfps | starve after 30 s |
|---|---|---|---|---|---|---|---|---|
| 1 OFF | `1-1791771146-lane.nfsaudio1011-2189879` | 15.7% | 15.4% | 15.0% | 0.997 | -22.99 | 59.0 | 0% |
| 2 ON | `1-1791771148-lane.nfsaudio1011-2189996` | **0.0%** | **0.0%** | 0.0% | 0.996 | -23.03 | 59.0 | 0% |
| 3 ON | `1-1791771149-lane.nfsaudio1011-2190142` | **0.0%** | **0.0%** | 0.0% | 0.996 | -23.00 | 59.0 | 0% |
| 4 OFF | `1-1791771151-lane.nfsaudio1011-2190384` | 15.9% | 13.4% | 15.2% | 0.997 | -23.01 | 59.0 | 0% |

Every registered leg passes:

- S: each ON ≤ 2%.
- S-PSA: each ON ≤ 2%.
- T: slope 1.00 ± 0.02.
- L: level −0.01 dB.
- F: gfps 59 vs 59.
- Z: no starvation past the first 30 s.

The share would not see forward skips. A VP slower than the writer would skip ahead rather than replay, so I aligned the
runs window by window against ON arm 2:

- **ON arm 3:** 97-100% of loud 32-frame windows sit at one offset in every 5 s segment. The offset steps by one video
  frame (16 ms) at the logo/PSA/attract boundaries. There is no skip and no replay.
- **The OFF arms:** 31-80% of windows sit at the mode, and the rest sit one 50 ms lap away.

**No harm on two other Playable titles.** These used amendment `nfsaudio1011-fix-titles.json`, registered before
their runs. They had the same binary and shape, and were run OFF and ON once each. S is "no increase": ON at most 1
point above OFF on the lag-2400 share and on an any-lag share (32..24000 frames, so a ring of any size). T is against
the same title's OFF capture.

| title | arm | result id | lag-2400 | any-lag | slope 0-25 s | level dBFS | gfps | starve after 30 s |
|---|---|---|---|---|---|---|---|---|
| The Simpsons Hit & Run | OFF | `1-1791771680-lane.nfsaudio1011-2270853` | 0.0% | 0.0% | (ref) | -24.40 | 59.0 | 0% |
| The Simpsons Hit & Run | ON | `1-1791771681-lane.nfsaudio1011-2270912` | 0.0% | 0.0% | 0.999 | -24.34 | 59.0 | 0% |
| Crimson Skies | ON | `1-1791772129-lane.nfsaudio1011-2350844` | 0.0% | 0.0% | 1.004 | -15.24 | 29.0 | 0% |
| Crimson Skies | OFF | `1-1791772130-lane.nfsaudio1011-2351431` | 0.0% | 0.0% | (ref) | -15.25 | 29.0 | 0% |

Every leg passes on both titles: level within 0.06 dB, gfps unchanged, no starvation.

- **Why these two:** both are on the Playable list, were run on the Nova today, and have loud audio from 4-8 s. They
  use two engines other than EA's (Radical; FASA), and Crimson Skies runs at 30 fps where the other two run at 59.
- **Correction:** I chose Simpsons for its intro dialogue, but with no input it never reaches that cinematic. It
  cycles through the logos (the Fox fanfare), the title theme and gameplay demos. So it covers music and in-game
  sound. Crimson Skies covers its intro movie and title music.
- **Speech is covered on NFS:** the PSA is spoken, and ON plays it with no replays.

apu.c's comment gives the reason the pacing is skipped on Android: it "can make speech sound dragged out". That would
show as a content slope below 1 or as starvation after boot. Neither appears in any of the four ON runs across three
titles.

**Not covered:**

- the Thor, which is out of service;
- an NFS run in the slow-content mode (2 of the 5 captures before the arms; none of the 4 OFF arms);
- the career cutscenes.

**What is left:** making the pacing the default (deleting the early return). That is default-on for every title, so it
belongs in the one screen for every default-on in flight, which lane.local runs. This lane did not run a cross-title
screen, as the brief says.

The vp.c code in this PR is the `HAKUX_APU_VOICELOG` instrument, and it is off by default. The four NFS arms ran with
it compiled in and off, and they reproduce lane.local's shipped figures: 15.7% and 15.9% against 15.1%, and level
-23.0 against -23.03 dBFS.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
