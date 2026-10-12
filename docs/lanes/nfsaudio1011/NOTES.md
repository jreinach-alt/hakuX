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

## Log

- 10-11, attempt 2: merged origin/master (aa04c62915). Wake analysis above. Instrument reviewed and compile-checked.
- Identify prediction `docs/testing/predictions/nfsaudio1011-identify.json` committed at b5cfe2c1b5, before any device
  run. Reader: `tools/voiceread.py <result>`; its output-side share reproduces 837057's 15.1% exactly.
- Queued, then withdrew, `1-1791768531-nfsaudio1011-1598447` (above).
- Addendum 2 instrument added and compile-checked (NDK clang, aarch64, `-Wall`: clean but for target_page.h's existing
  warning). Reader tested on synthetic lines. The prediction is re-registered on the new ref with Addendum 2's claim
  as leg W.
