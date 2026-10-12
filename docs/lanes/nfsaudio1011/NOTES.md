# nfsaudio1011 -- NFS Most Wanted audio stutter (#433, 0.5)

The symptom: ~15% of NFS MW's loud APU output (4541007B) is a bit-exact copy of
the output 2400 frames (50 ms) earlier. The four lane.local runs are listed in
the brief (`/home/justin/hakux-work/briefs/nfsaudio1011.md`).

## Attempt 1 (10-11), and why it did not finish

lane.local stopped the session at 18:18 PDT to add Addendum 1 ("the guest CPU is not the cause; read the wake keys
before the identify run"). At that point the `HAKUX_APU_VOICELOG` instrument in vp.c was written but uncommitted and
uncompiled, and nothing had been queued. Attempt 2 picks the instrument up as it was. It now compiles clean against
the NDK (aarch64, the arm64-v8a compile line of the host's Release build, `-Wall`).

## Addendum 1: what wakes the guest (no device time)

`tools/wake_by_vector.py <result id>` sums the `[rr425w]` wake keys per vector (0x30 + IRQ) per 10 s bin.

| run | APU 0x35 wakes from idle | APU taken busy | PIT 0x30 | USB0 0x31 | NV2A 0x33 | IDE 0x3e | ACI 0x36 |
|---|---|---|---|---|---|---|---|
| 837057 (default) | **0** | 0 | 39910 | 9458 | 4779 | 448 | 1 |
| 836907 (256 samples) | **0** | 2 | | | | | |

In the idle windows of 837057 (80-110 s and 170-180 s, ~88% idle), the guest is woken ~900/s by the PIT, ~200/s by
USB0 and ~110/s by NV2A. The APU never wakes it. So the game's audio writer is not paced by APU interrupts:
DirectSound notifications that bunch up when the VP runs in bursts cannot be the mechanism. A writer that wakes on
the PIT (a timer or a polling thread) and reads the VP's position from voice memory, or keeps time some other
way, is still open. So are a VP that reads the wrong place (H-B), and a guest whose writes stall (H-C).

Run 651467's slow intro (30.6%, the first capture) is CPU-bound and a separate matter. It is not chased here.

## What the emulator does that the hardware may not (from reading apu.c / vp.c)

- On Android, `throttle()` (apu.c ~137-145) returns right after the high-watermark wait and never paces at the low
  watermark. It runs only every 8 VP frames (one 256-sample EP frame). So the VP runs in bursts that refill the
  monitor fifo, then idles. With the default 2048-sample device buffer, the high watermark is 6144 frames (128 ms).
- A voice's CBO lives in guest RAM and the VP writes it back each VP frame. Between bursts it stands still; during a
  burst it moves by up to a whole device period (2048 samples, 43 ms) in a few ms of host time.
- A guest that places its writes by the CBO it reads, with a 2400-sample ring and a lead of a few hundred samples,
  falls a lap behind whenever one burst moves the CBO past its write head. 2048 + a lead of >352 > 2400. But the
  256-sample run still showed 20%, so the burst size alone does not explain it.

## Identify run: what it must separate

The instrument (`HAKUX_APU_VOICELOG=1`, logcat tag `hakuX-audio`, lines prefixed `apuvoice`; the brief said
`hakuX-apuvoice`, but LOGCAT_SPEC is an exact tag list and carries `hakuX-audio`):

- `stale v= ...` -- a run of loud 32-sample source blocks the VP read with the same content as on its previous lap at
  that address. Carries the lap time, the age of the last PIO, and (for the scanner's voice) the guest's write head
  and when it last wrote this block.
- `sec ...` once a second -- VP pacing (lead over real time, bursts, maxgap) and the ring stale share.
- `voice ...` -- the top 3 loud voices: buffer or stream, loop, BA/LBO/EBO/CBO, SSL A/B, and fresh, stale and share.
- `sslsw ... replay=1` -- the VP entering an SSL that nothing reprogrammed since it last played it.
- `scan v= ...` -- the guest's writes into the focus ring, every 1 ms, with the CBO at each.

Discriminators:

| hypothesis | what the lines show |
|---|---|
| H-A' (VP bursts outrun a regular guest writer) | stale runs start inside VP bursts; the guest's scan writes are regular; `blk_wr_age` ≈ one lap; `sslrep`=0 |
| H-B (VP plays the wrong place) | `sslrep`>0 or `sslempty` on the music voice; CBO jumps nobody wrote; stale with the guest's write head well ahead |
| H-C (guest writer stalls) | gaps in the scan writes that line up with stale runs while the VP runs steadily |

## Where replays sit in the drain cycle (no device time)

Stale output (lag-2400 copies, runs ≥ 16 frames, loud) by phase of the output sample index, from the three
lane.local captures. Depth is (max − min) / max of the stale share across 16 phase bins.

| run | setting | strongest period | depth | next |
|---|---|---|---|---|
| 837057 | default (2048) | 2048 | 0.75 | 4096: 0.73 |
| 836907 | 256 samples | 3840 | 0.41 | 1920: 0.37, 960: 0.18 |
| 836989 | 512 samples | 3840 | 0.23 | 1920: 0.20, 960: 0.18 |

837057, stale share of loud output by phase within the 2048 cycle (16 bins of 128 samples, %):
`2 0 0 0 0 0 0 0 70 75 60 16 10 9 6 5`. Half the cycle is clean; the stale part starts abruptly and fades.

So the replays follow the device's real drain cycle. At 256 and 512 that cycle is 1920 samples (two 960-sample HAL
periods, 40 ms), not 256 or 512: the setting changed the requested buffer, not how much the device takes per
callback, and so not how far the VP runs per burst. **This corrects the brief's reading of the 256 run**: "a 256
burst is 5 ms against a 50 ms ring" assumed the burst shrank, and it did not. A burst that outruns the writer
(H-A') is not refuted by that run. The lock at P256 that Addendum 2 measures in all three runs is structural:
`throttle()` only looks at the fifo every 8th VP frame (`ep_frame_div % 8`), so every burst starts on a 256-sample
boundary at any setting.

## Attempt 2: the first identify request was withdrawn

I queued `1-1791768531-nfsaudio1011-1598447` (ref 89667f015c) before I had read Addendum 2, which asks for more in the
instrument before the identify run. I withdrew it from the queue (`queue/withdrawn/`) before it was claimed. No
device time was spent.

## Addendum 2 instrument: what the guest did in the APU's wait

Added to `HAKUX_APU_VOICELOG` (vp.c only):

- **Bursts.** A burst starts at a VP frame that began ≥ 300 µs after the previous one ended. At each start:
  - the guest FE methods (VOICE_LOCK included) on every voice since the last frame ended, and VOICE_LOCK methods on
    any voice;
  - a `burst` line (25/s budget) for the loudest voice. It gives the wait, split into `th` (what throttle() added to
    `sleep_acc_us`) and `x` (the rest), the FE and lock counts in the wait, the CBO, and the scanner's guest write
    head. `ahead` is how far the guest's newest write is past the CBO, in samples. `prev=frames/off` is the previous
    burst's length and how many VP frames into it that voice's first stale run started (−1: none).
- **Stale lines** gain `burst boff wait wfe wlock wlockall`: the burst the run started in, the VP frames into it, the
  wait before it, and the guest's FE and lock methods in that wait (on this voice, and locks on any voice).
- **Sec lines** gain:
  - `bx=a/b/c/d`: bursts of the loudest voice, split by "a stale run started in it" and "the guest addressed the voice
    in the wait before it". The order is stale&upd, stale&!upd, !stale&upd, !stale&!upd. `bxl` is the same for any
    voice and any VOICE_LOCK.
  - `lockwait=n/us/max`: the VP stalled in `voice_work_acquire_voice_lock_for_processing` on a voice the guest held.
  - `locked=` (µs the guest held voices locked) and `lockops=`.
  - `throttle=` and `gapx=sum/max/unsplit`.
- **bql_lock is bounded, not timed.** `bql_lock()` is in apu.c, which this lane does not hold. `gapx` is the APU
  thread's time between VP frames that throttle() did not account for: bql_lock + update_irq, the DSP frame, and the
  FIFO push. It is an upper bound on time blocked in bql_lock. If it comes back small, bql is ruled out. If not, an
  apu.c.patch build times bql_lock itself.

Reader: `tools/voiceread.py`, leg W. It prints:

- the two 2×2 tables as "share of bursts with a stale start that followed an update" against the same share for
  bursts without one, and the lift;
- the lock stall and gapx totals;
- for stale starts, `32*boff − ahead`. H-A' predicts about 0: the run starts where the VP passes the guest's head.

## Identify run `1-1791770282-lane.nfsaudio1011-2057093`: the mechanism is H-A'

Ref 234b269b99, `HAKUX_APU_VOICELOG=1`, Nova, 180 s, apk 0b953f53f9a3. Readers: `tools/voiceread.py`,
`tools/replay_share.py`, `tools/fixjudge.py` (slope and PSA window).

**The VP runs ahead of the game's writer inside each burst.** The PSA's audio is a 5.1 PCM ring of 2400 frames, played
by three stereo voices that move together: v=244, 245 and 246, `buf loop=1 ebo=2399 spb=6`, at BA 0x1f40, 0x1f44 and
0x1f48. It is a looping buffer, not a stream, so the scanner covers it (Addendum 3's question). The game keeps its
write head **exactly 992 samples ahead of the CBO it last read**: `ahead=992` at 2937 of 2950 burst starts. On the
hardware the CBO moves 32 samples every 0.67 ms, so a 992-sample lead (21 ms) is ample. Here, after each drain, the VP
runs 64 VP frames (2048 samples, 60% of bursts) or 128 (4096, 40%) back to back, in a few ms of host time, and then
waits 45-52 ms. A burst passes the guest's head 992 samples in. From there to the burst's end the VP reads the ring as
the guest left it a lap (50 ms) earlier, which is the replay. A 128-frame burst also passes its own start (2400 samples
in) and reads that stretch a second time within ~9 ms (`lap=8853`).

```
apuvoice burst n=74 f=4928 t=6932987 wait=44244 th=44228 x=16 v=244 fe=10 lock=10 lockall=10 feall=10 cbo=1440 ebo=2399 head=0 ahead=992 hd_age=40928 prev=128/32 lockwait_prev=0
apuvoice burst n=75 f=4992 t=6993056 wait=51735 th=51710 x=25 v=244 fe=10 lock=10 lockall=10 feall=10 cbo=1088 ebo=2399 head=64 ahead=992 hd_age=50944 prev=64/32 lockwait_prev=0
apuvoice stale v=244 region=0x1f40 cbo=32 blocks=23 ssl=A0 f=4960 t=6937751 lap=54384 pio_age=3064873 wr_head=0 wr_age=45692 blk_wr_age=6937751 burst=74 boff=32 wait=44244 wfe=10 wlock=10 wlockall=10
apuvoice stale v=244 region=0x1f40 cbo=864 blocks=13 ssl=A0 f=4236 t=6462361 lap=8853 pio_age=2589483 wr_head=-1 wr_age=-1 blk_wr_age=-1 burst=66 boff=76 wait=51153 wfe=12 wlock=12 wlockall=12
apuvoice voice v=244 buf loop=1 cs=1 st=1 ba=0x1f40 lbo=0 ebo=2399 cbo=2176 ssl=A0 A=0/0 B=0/0 samples=49152 blocks=1536 loud=618 fresh=404 stale=214 first=0 share=34.6% sslsw=0 sslrep=0 sslempty=0 pio=0 notify=0
```

Burst 74 starts with the head at block 0 and the CBO at 1440: (0+1)×32 − 1440 mod 2400 = 992. Its first stale run
starts at `boff=32`, which is 1024 samples in, the first block past the head. `hd_age` ≈ `wait`, and `wait − hd_age`
has p50 5.8 ms: the guest writes within a few ms after each burst moves the CBO, then has nothing to do while the CBO
stands still. Over the run, the paired `32*boff − ahead` is exactly +32 in 1587 of 2828 bursts (56%), within ±256 in
67.9%. `sslrep=0` and `sslempty=0` on every voice line, so the VP reads the right place (not H-B). The lead is constant
at 992 at every burst start, so the writer is never behind when a burst begins (not H-C).

| leg | registered | measured | verdict |
|---|---|---|---|
| V | `on` once, ≥ 150 sec lines, ≥ 150 s PCM | 1, 178, 180.2 s; event lines 63% dropped by the 30/s budget (burst lines 0 dropped) | PASS; M's timing from stale lines is "partial" per the leg, burst lines are complete |
| A | \|VP − output\| ≤ 5 pts | VP 32.6% (v=244; 245: 32.8%, 246: 32.7%), output 31.2% | PASS (1.4) |
| output range | 8-30% | 31.2% | MISS by 1.2: a slow-content run (below) |
| M | H-A' P 0.5 | H-A' | named above |
| W | ≥ 80% after an update and lift ≥ 20 pts | top voice 90% vs 45%, +46 | PASS on its letter, **refuted as a cause** (below) |
| B | gapx median < 2 ms/s | 28.2 ms/s | FAIL as registered; the sum was the wrong statistic (below) |
| O | \|32·boff − ahead\| ≤ 256 in ≥ 60% | 67.9% (n 2828), mode +32 | PASS |
| P | reported | vpframes 1536 per sec line (~1.02-1.04 s, so real time), bursts 39/s, maxgap p50 54 ms | |

**W, why the coincidence is not the cause.** The guest addresses v=244 with VOICE_LOCK pairs 10-12 times in every
wait (lockops ~200/s), and never addresses v=245 or v=246. Those two replay just as much: 32.8% and 32.7% against
32.6%. Every one of their 2771 stale lines has `wfe=0 wlock=0`. And a guest update in the wait would make the replay
start at the burst's first frame. Only 102 of 5061 stale runs (2%) start in the first 32 frames of a burst. My reading
of W's lift on the top voice (not measured): the guest updates v=244 while it is sounding, and a quiet voice has
neither updates nor loud stale blocks. The any-voice VOICE_LOCK row is 100% vs 89% (+11): not separated, as the
prediction allowed.

**B.** The per-second sum of non-throttle time is the per-frame work: ~18 µs per VP frame for the DSP frame, the FIFO
push, and bql_lock + update_irq. It is not a wait. At burst starts, which are what Addendum 2 asked about, `x = wait −
th` has p50 19 µs and max 97 µs over 2950 bursts. The voice-lock stall is 23 stalls and 0.2 ms over the run. So
neither bql_lock nor the voice lock is where the APU waits before a replay. The wait is throttle(), all of it. No
apu.c build timing bql_lock is needed.

**Slow-content run.** This run's content slope against 837057 is 0.754 over 0-25 s (RANSAC, 75/196 inliers), like
651467 (0.707). In 836907, 836989 and 837057 it is 0.996-1.000. With the VP at real time, a slope of ~0.75 means the
writer's stream was delayed by the replays rather than cut by them: content that should have played took ~1.3× as long
to come out. 1 − slope (0.25) is the same order as the share (31%), but I have not shown the one accounts for the
other. Two of the five NFS captures so far behaved this way, and both ran at ~31%. This changes how much is replayed, not where the replay starts or why. The fix arm's T leg reports each
run's slope.

**PSA window (Addendum 3).** Output 2.97-22.3 s (837057's 2.27-17.27 s through this run's 0.775 fit): 28.5% replayed
on the output side; v=244 is 33.1% stale on the VP side. 837057's PSA by the same window is 11.2%.

So the fix-shaped arm is the right next step: it removes the burst that outruns a 992-sample lead.

## Fix-shaped arm (Addendum 2): pacing at the low watermark on Android

The pacing lives in `throttle()` (apu.c ~115-175). `apu.c.patch` (here) wraps the Android early return in
`if (!apu_pace_on())`, so `HAKUX_APU_PACE=1` runs the low-watermark pacing that non-Android builds always run. Off by
default: the shipped path is unchanged. The switch is read once and logged once (`hakuX-audio: apu_pace: on|off`).
Until Addendum 4 apu.c was lane.snapshot1011's, so the arms ran the patch from a scratch tree. Attempt 3 commits it
(below).

## Fix arms: the replays are gone with `HAKUX_APU_PACE=1`

One binary, scratch build `9c054c1714` (lane head 39760cebf5 + `apu.c.patch`), apk c2254f79408a. Nova, NFS MW, 180 s from
boot, no route, no VOICELOG. The env is the only difference. Prediction `docs/testing/predictions/nfsaudio1011-fix.json`
(registered before any arm). Judge: `tools/fixjudge.py`, which compares against 837057 for slope and the PSA window.

| arm | result id | switch | lag-2400 share | PSA window | any-lag share | slope 0-25 s | level dBFS | gfps | starve after 30 s |
|---|---|---|---|---|---|---|---|---|---|
| 1 OFF | `1-1791771146-lane.nfsaudio1011-2189879` | off | 15.7% | 15.4% | 15.0% (all at lag 2400) | 0.997 | -22.99 | 59.0 | 0% |
| 2 ON | `1-1791771148-lane.nfsaudio1011-2189996` | on | **0.0%** | **0.0%** | 0.0% | 0.996 | -23.03 | 59.0 | 0% |
| 3 ON | `1-1791771149-lane.nfsaudio1011-2190142` | on | **0.0%** | **0.0%** | 0.0% | 0.996 | -23.00 | 59.0 | 0% |
| 4 OFF | `1-1791771151-lane.nfsaudio1011-2190384` | off | 15.9% | 13.4% | 15.2% (all at lag 2400) | 0.997 | -23.01 | 59.0 | 0% |

| leg | registered | measured | verdict |
|---|---|---|---|
| V | `apu_pace: on/off` as labelled | all four | PASS |
| S | each ON ≤ 2% | 0.0, 0.0 (OFF 15.7, 15.9) | PASS |
| S-PSA | each ON ≤ 2% | 0.0, 0.0 (OFF 15.4, 13.4) | PASS |
| T | each ON 1.00 ± 0.02 | 0.996, 0.996 (OFF 0.997, 0.997) | PASS |
| L | \|ON − OFF\| < 0.5 dB | −0.01 dB | PASS |
| F | ON ≥ OFF − 1.0 | 59.0 vs 59.0 | PASS |
| Z | ON 0% past the first 30 s | 0, 0 | PASS |
| phase | P2048 lock < 0.2 if ≥ 100 ON starts | 0 ON starts (OFF 0.75, 0.81) | not applicable |

None of the four ran slow (all slopes 0.996-0.997), so this pair does not test whether the fix also removes the
slow-content mode. In both slow runs (651467, 2057093) the replays were what delayed the content, so I expect it does,
but no slow run happened here. The first 30 s window's starvation (boot, before the first loud audio) is 19.1% in both
ON runs and 44.2% / 16.7% in OFF. It is not judged.

**What the share cannot see, checked.** A VP that ran slower than the writer would read blocks the guest had already
overwritten. That shows as forward skips, not replays, and the lag-2400 share would be blind to it. So I aligned ON arm
3, and the OFF arms, against ON arm 2 window by window: bit-exact 32-frame windows with the replay mask off, the
offset mode per 5 s segment, and the share of loud windows at that mode.

- **ON3:** 97-100% of windows sit at one offset in every segment. The offset steps by 16 ms, one video frame, twice: at
  5 s and at 80 s, the boundaries between the logo, the PSA and the attract loop. Then it wraps by the attract loop's
  45.8 s period. Inside a segment there is no skip and no replay.
- **OFF1 and OFF4:** only 31-80% of windows sit at the mode, and the rest sit 50 ms (one ring lap) away. Seen from the
  clean side, that is the replay.

**Why it works** (H-A', above). Paced, the VP moves the CBO 256 samples per 5.33 ms instead of 2048-4096 in a few ms.
The game's 992-sample lead is never overrun, so the VP never reaches blocks the writer has not refilled.

**Device time choice.** Addendum 3 says `--seconds 40` covers the PSA at a quarter of the device time. I kept 180 s
because the brief's step 3 asks for the arms in step 2's shape. Legs S, T and F are defined over the whole capture and
the 12-95 s window, and the slow-content mode in 2057093 showed over the whole run. The PSA window is judged inside the
same runs (S-PSA).

## No-harm check on two other titles

Amendment `docs/testing/predictions/nfsaudio1011-fix-titles.json`, registered after NFS arms 1-2 and before any run of
these titles. Same binary and run shape. S becomes "no increase": ON at most 1 point above OFF on the lag-2400 share
and on an any-lag share. The any-lag share counts bit-exact 32-frame windows that repeat at 32-24000 frames, so it sees
a ring of any size. On the NFS arms it agrees with the lag-2400 share (15.0 vs 15.7, 15.2 vs 15.9), and 100% of its
hits are at lag 2400. `fixjudge.py --other --ref <the title's OFF run>`.

- **The Simpsons Hit & Run** (56550015), for speech. With no input it plays its logos and then an intro cinematic with
  dialogue. Its first loud audio is at 4.56 s or 8.9 s in today's Nova runs (hakuX-audio level lines). Speech is
  where the owner hears the NFS stutter. Android skips the pacing in the first place because speech sounded dragged
  out, so a speech title is where the fix's known risk would be heard. It also uses a different engine (Radical).
- **Crimson Skies: High Road to Revenge** (4D530021), for music. Its first loud audio is at 6.2-8.1 s. Its route
  waits 75 s for the intro before any input. It uses a third engine (FASA), and the game paces itself to 30 fps.

**Correction to the Simpsons reason.** The run's frames show that with no input the game never reaches the intro
cinematic. The route's START press is what leads there. Without it the game cycles through the publisher and studio
logos (with the 20th Century Fox fanfare), the PRESS START title and its theme, and gameplay demos, then repeats. So
this check covers music and the demos' in-game sound, not verified dialogue. The registered amendment keeps the wrong
reason as registered. Speech is still covered on NFS itself: the PSA is a spoken announcement, and ON plays it with
0.0% replays.

| title | arm | result id | switch | lag-2400 | any-lag | slope 0-25 s (vs its OFF) | level dBFS | gfps | starve after 30 s |
|---|---|---|---|---|---|---|---|---|---|
| Simpsons | OFF | `1-1791771680-lane.nfsaudio1011-2270853` | off | 0.0% | 0.0% | (reference) | -24.40 | 59.0 | 0% |
| Simpsons | ON | `1-1791771681-lane.nfsaudio1011-2270912` | on | 0.0% | 0.0% | 0.999 (198/198 inliers) | -24.34 | 59.0 | 0% |

| Crimson Skies | ON | `1-1791772129-lane.nfsaudio1011-2350844` | on | 0.0% | 0.0% | 1.004 (205/248 inliers) | -15.24 | 29.0 | 0% |
| Crimson Skies | OFF | `1-1791772130-lane.nfsaudio1011-2351431` | off | 0.0% | 0.0% | (reference) | -15.25 | 29.0 | 0% |

- **Simpsons:** V yes. S +0.0 / +0.0. T 0.999. L +0.06 dB. F 59.0 vs 59.0. Z 0 vs 0. Every leg passes.
- **Crimson Skies:** V yes. S +0.0 / +0.0. T 1.004. L +0.01 dB. F 29.0 vs 29.0. Z 0 vs 0. Every leg passes.
- **Content:** the Crimson Skies frames show the Xbox and Microsoft Game Studios logos, the intro movie (newsreel-style
  footage), the title screen, and the movie again. Its first-window starvation is boot (44.5% OFF, 54.3% ON) and is
  not judged.
- **Neither title replays at any lag in either arm,** so neither title's writer is outrun even in shipped behaviour.
  The fix changes nothing there that these legs can see.

**The Android early return's own reason, checked.** apu.c says the pacing is skipped on Android because "scheduler
granularity is often too coarse for the extra low-watermark pacing below and can make speech sound dragged out". Dragged
out would show here in two ways: content slower than real time (a slope below 1 against an unpaced run) and starvation
gaps in the device output. Neither appears in any of the four ON runs across three titles on the Nova. All four have
slopes 0.996-1.004, and none starves after the boot window. Not tested: the Thor, which is out of service, and a CPU-
bound slow-content NFS run under ON (none of the six runs here went slow).

## For the next lane

- **The fix is proven on NFS and harmless on two others. The next step is apu.c's owner making it the default.** On
  Android that means deleting the early return (the patch's `if (!apu_pace_on())`). That is a default-on change for
  every title. Per the owner's 10-11 rule, it goes in the one screen for every default-on in flight, not in a screen
  of its own. The brief forbids a cross-title screen in this lane.
- **Do not re-derive the mechanism.** The identify run's burst and stale lines above name it.
- `fixjudge.py` judges any title. `--other --ref <OFF dir>` gives the no-increase form. Its any-lag share sees replays
  at any ring size up to 0.5 s.
- **Not done:** a slow-content NFS run under ON; the career cutscenes (the owner's other report: no route reaches them
  in this lane); and the Thor.

## Log

- 10-11, attempt 2: merged origin/master (aa04c62915). Wake analysis above. Instrument reviewed and compile-checked.
- Identify prediction `docs/testing/predictions/nfsaudio1011-identify.json` committed at b5cfe2c1b5, before any device
  run. Reader: `tools/voiceread.py <result>`; its output-side share reproduces 837057's 15.1% exactly.
- Queued, then withdrew, `1-1791768531-nfsaudio1011-1598447` (above).
- Addendum 2 instrument added and compile-checked (NDK clang, aarch64, `-Wall`: clean but for target_page.h's existing
  warning). Reader tested on synthetic lines. The prediction is re-registered on the new ref with Addendum 2's claim
  as leg W.
- Identify run `1-1791770282-lane.nfsaudio1011-2057093` (queued 01:58Z, done 02:03Z): mechanism H-A', legs above.
  `apu.c.patch` committed at 1fd570f434. Fix-arm judge `tools/fixjudge.py`, dry-run on 836907/836989/837057/651467/2057093.
- Fix prediction `docs/testing/predictions/nfsaudio1011-fix.json` registered 02:12Z at 1cd5a7c434, before any arm. Scratch
  build 9c054c1714 (lane head 39760cebf5 + apu.c.patch, commit-tree, on no branch). Arms queued 02:19Z on the Nova:
  1 OFF `1-1791771146-lane.nfsaudio1011-2189879`, 2 ON `1-1791771148-lane.nfsaudio1011-2189996`,
  3 ON `1-1791771149-lane.nfsaudio1011-2190142`, 4 OFF `1-1791771151-lane.nfsaudio1011-2190384`.
- All four done and judged: every leg PASSES (table above). `fixjudge.py` gained an any-lag share, `--other` and a Z
  line at 6726d994c5. That commit also registered the two-title amendment.
- No-harm arms queued on the Nova: 1 Simpsons OFF `1-1791771680-lane.nfsaudio1011-2270853`, 2 Simpsons ON
  `1-1791771681-lane.nfsaudio1011-2270912`. Crimson Skies 3 ON `1-1791772129-lane.nfsaudio1011-2350844`, 4 OFF
  `1-1791772130-lane.nfsaudio1011-2351431` (shipped value last). All four are judged, and every leg passes (above).
  The eight fix-stage runs took ~36 min of device time (estimated at 270 s each). I queued them so that queued plus
  running time never passed the 30-min pilot gate.
- origin/master 13e0590809 already in the branch; preflight passed; PR.md State: ready.

## Attempt 3 (10-11): apu.c granted (Addendum 4)

**Why attempt 2 did not finish:** it did finish the brief as written then. It pushed e19b43b94a with PR.md
`State: ready` and the apu.c part as a patch, with a NEED line for apu.c. At 19:48 PDT lane.local granted apu.c
(board 199b27283b; lane.snapshot1011 released it at ready) and added Addendum 4: commit the patch. That is attempt
3's only work. No device runs.

- origin/master is still 13e0590809, already in the branch. lane/snapshot1011 has not folded. Its apu.c change is
  5 lines in `mcpx_apu_pre_load()` (~1179), well away from `throttle()`, so the two merge without conflict.
- `git apply docs/lanes/nfsaudio1011/apu.c.patch`. The resulting apu.c is byte-identical to the one in scratch build
  `9c054c1714`, which every fix arm and no-harm arm ran. `HAKUX_APU_PACE` stays off by default.
- **Compile check:** apu.c alone, NDK 29 clang, the arm64-v8a compile line of the host's Release build
  (`android/app/.cxx/Release/135r5t6d`, `-O3 -march=armv8.2-a`), with the worktree's source include paths and `-Wall`.
  Exit 0. The one warning is target_page.h's existing `-Wshift-negative-value`. The object imports `getenv` and
  `__android_log_print` and holds `apu_pace_on.on`. The host (non-Android) build is unchanged: all the new code is
  under `#ifdef __ANDROID__`.
- PR.md: the NEED line is gone, and apu.c and OUTBOX.md are in `Files:`. The release note stays `none`, because the
  switch is off by default. Its text changed only to drop the reference to the NEED line; the future note is verbatim.
- Committed at aa0d594a10. `docs/testing/preflight.sh` passes (territory ok with apu.c). `docs/testing/jobs/selftest.sh`,
  run once, whole: 3377 passed, 0 failed, all 136 fragments (~70 min under host load, 19:57-21:07 PDT).
- **While the selftest ran, lane.local folded the previous head.** e19b43b94a is master's 3ce6b6ac96 (PR #935, merged).
  So this push is a follow-up fold of one code file (apu.c) and the lane's docs.
- **I did not merge the newer origin/master (3ce6b6ac96) into the branch.** Addendum 4 asks for the merge only if
  snapshot1011 has folded, and it has not. The reason not to: `offline_fold.py` folds emulator code only with a
  finished, non-void dispatch run whose ref has the same emulator code as the branch head (`same_emulator_code`). This
  head's emulator code is byte-identical to `9c054c1714` (`git diff 9c054c1714 HEAD` outside docs/ is empty), so the
  fix arms `2189996` and `2190142` (ref `9c054c1714`, finished) already satisfy that gate. Merging master would bring in
  gtasagpu1011's renderer code and require a new device run, which Addendum 4 rules out. The branch merges into
  3ce6b6ac96 without conflict (`git merge-tree`), and the fold merges it there anyway.
- The memory "fold's head run is the exact sha" is out of date: since 10-06 the fold accepts any run whose emulator
  code matches the head's, not only a run at the head's own sha.
