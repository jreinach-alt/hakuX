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

## Log

- 10-11, attempt 2: merged origin/master (aa04c62915). Wake analysis above. Instrument reviewed and compile-checked.
