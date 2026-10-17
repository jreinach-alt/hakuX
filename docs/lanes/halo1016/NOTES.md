# lane.halo1016 -- NOTES

Halo: Combat Evolved (4D530004), opening cinematic on the Nova. Found on 0.5.1-rc1; the target is now **0.5.2**
(0.5.1 shipped without this lane, owner 10-16 ~22:50 PDT).
Defects: **#938** quiet speech under loud music; **#1018** the cinematic drops to 8-19 fps for ~47 s.

## Status (2026-10-17 01:45 PDT)

- #1018: the census is judged (below, "#1018 census verdict"). **Every plateau download is the texture path's
  `cvt` refusal**: a 16-bit 5/6-bit texture over a 2-byte render target, the #986 MKSM mechanism. K and C HIT,
  O and R MISS. `HAKUX_S2T_CVT=1` takes the downloads from 49.3 a frame to 0 and the plateau from 59.3 to
  41.9 ms a frame. **It does not clear the plateau.** With the downloads gone, the shots still run at 40-61 ms
  a frame, and now the guest never idles: the vCPU itself is the bound in those shots. That is a second cause,
  and it is the next chase ("#1018 the guest-CPU half").
- The cinesplit A/B (below) found the downloads: 61 a frame and 33 ms a frame over the plateau, with the GPU off
  the path and `TU_DEBUG=sysmem` no remedy. That verdict is on #1018 (forge comment 19632).
- #938: the speech legs are judged (below): B, L, N and S all MISS. The HRTF scale is not the lever: raw taps sum
  to l1 ~13, so today's division already cuts the bed, and raw plays it 20 dB louder and clips. Speech does not
  starve. What is over the speech is the 2D music, at the title's own registers through the same ADPCM decoder.
  Scaled to the frames it plays, speech's median margin over the music is +1.9 dB before mark+130 and -1.7 dB after,
  in the score's swells (scratch/mixregs.py). The verdict is on #938 (forge comment 19633).
- Device runs already carry `[surfgpu] on` (the app's Graphics default since lane.surfgpudefault1009), so the
  SURFSPLICE route is live in every arm here. Any remedy for an eviction download has to go past what that covers.

## Why attempt 1 did not finish

Attempt 1's session ended on its turn cap (301 turns) at 23:31:32 PDT. Its work was done:
- the instruments and judges were written before any arm landed;
- the cinesplit pair was queued and ran;
- the speech prediction was registered.

But it was all in commits and scratch files, and this file was never written:
- d9749388d6 (cineread.py reads only this run's CSVs) was left unpushed;
- the speech legs were never queued;
- the account stayed in `scratch/`.

Attempt 2 pushed d9749388d6 first and queued the speech legs at 23:59. It writes this file before each device wait.

## Why attempt 2 did not finish

Attempt 2 also ended on its turn cap (301 turns), at 01:02:49 PDT. It judged the cinesplit and speech legs,
posted both verdicts, built `[ovl1018]`, and queued the census pair, which landed at 00:56:20. `censusread.py`
(committed before either arm ran) wrote `scratch/census-verdict.md` at 00:56. The session then spent its last
turns on a dispatcher table (`scratch/rrtable.py`) before the verdict was in this file, so the verdict and six
scratch files were left uncommitted. Attempt 3 committed the verdict first, before any further analysis.

## #1018 cinesplit verdict (judged with cineread.py as committed before either arm landed)

- A = 0-0-x-1792217277-halo1016-932684: master's emulator (d205bbe2fd), `HAKUX_FRAMETRACE=1 HAKUX_PROBE_WAITS=1`.
- B = 0-0-x-1792217272-halo1016-929680: the same, plus `TU_DEBUG=sysmem`.
- The full output is in `scratch/cinesplit-verdict.md`.

The run is valid. Both arms reached `mark cinematic` with 30 cinematic shots. A's plateau is 11 pace windows, 44 s,
from mark+131 to mark+191, which reproduces the owner's 8-14 gfps plateau.

| Leg | Result | Measured | Threshold |
|---|---|---|---|
| S | MISS | p_run 22.6 ms/f; blocked 65% of the period, of which GPU waits 83%, locks 0%, pidle 17%; run queue 0% | p_run 35-60 |
| G | MISS | gpu/P p50 0.17 (raw timestamps; ~0.11 true) | >= 0.50 |
| W | **HIT** | 61.17 mid-frame non-deferred finishes a frame, **all `sdown`**, 33.01 ms a frame | >= 1.5 |
| P | MISS | B/A period 0.96 (A 65.9 ms, B 63.0 ms); over mark+40..260 the ratio is 1.00 | <= 0.80 |

Read:
- **F2 (host GPU-bound) is refuted.** The GPU executes 10.9 ms (raw) of a 66 ms frame.
- **GMEM binning is off the path.** sysmem moves the plateau 4%, and the whole span 0%.
- **F1 is confirmed, in its surface-download form.** The PFIFO thread's blocked time is 43.2 ms a frame:
  - 7.3 ms waiting for work;
  - 0.8 ms on named fences;
  - 35.0 ms "unhooked", which is the `sdown` finishes' 33.0 ms (probe1010) to within 2 ms.
- p_run missed low: the draw thread's own CPU is 22.6 ms a frame, not 35-60. The owner capture's `[rdc] tcpu` figure
  (~48 ms a frame) was CPU over wall, not over the frame, at a lower frame rate. S was mis-scaled, and the miss is
  read as such.

Caveat: the arms did not run under identical conditions.
- B ran first, with a cleared shader cache (cold). A ran second, with a warm one.
- The cold cache biases B slower, so it cannot hide a sysmem win that big.
- After B landed, cineread.py's input filter changed (`run_csvs()`, d9749388d6): the pulled glob had brought back 31 stale
  frametrace CSVs from 10-11/10-12. No threshold moved, and the change was made before B's numbers were read.

### The plateau, per window (A; t = seconds after `mark cinematic`)

| span | ms/f | sdown/f | draws/f | p_run | p_blk | guest idle |
|---|---|---|---|---|---|---|
| 0-110 | 33.4 | 0-24 | 170-390 | 3.5-8.4 | 24-30 | 0-0.2 |
| 120-129 (edge) | 33-42 | 11-31 | 320-950 | 10-18 | 20-26 | 0-0.02 |
| 131-154 (plateau 1) | 48-77 | 22-77 | 900-1363 | 17.6-28.3 | 33-49 | 0.12-0.34 |
| 156-164 | 33.2-35.2 | 5-48 | 583-838 | 9.7-13.3 | 22-24 | 0 |
| 167-191 (plateau 2) | 48-95 | 19-128 | 692-1091 | 15.5-30.2 | 31-65 | 0.13-0.60 |
| 236-345 (late) | 33.4 | 21.0 | 640-690 | 13.3-13.9 | 19.4-20.2 | 0 |

The frame period tracks p_run + sdown x ~0.5 ms. The guest idles exactly when that sum passes 33 ms.

## #1018 symptoms and their accounts

2. **30 fps for ~1.5 min, then ~47 s at 8-19 gfps.**
   - Before mark+120 the shots draw 170-390 times a frame with 0-24 surface downloads; the draw thread needs 25-30 ms
     and the frame holds the vblank pair.
   - The plateau's shots draw 900-1363 times a frame and download a surface 20-129 times a frame, at 0.45-0.9 ms each
     (one submit plus a fence wait apiece).
   - Downloads plus the draw thread's CPU pass 33 ms, and the period follows their sum.
   - Which surfaces, and why each is downloaded instead of bound on the GPU: OPEN, the perflog census below.
3. **The guest idles up to half of each window.**
   - It is blocked on the emulated GPU: the owner capture's busy spans all begin on the NV2A wake (33.44). The guest code
     (scratch/guestcode.md) waits at 0x18118d (KeWaitForSingleObject, infinite) on the push-buffer token the PFIFO
     thread retires.
   - The PFIFO thread is in the synchronous downloads, so the guest waits on them.
   - Not the disc: `[ide425]` w=0 and rd_sec=0. Not audio: the APU is on its own thread and its windows are unchanged.
     Not vblank: the vbl lines run at 59.94 Hz with drift under 40 us.
   - **`ip` rises while `iq` stays flat** (A: ip 2900 -> 4000-4768, iq ~2800 per 2 s). That is the idle loop, not a new
     interrupt source:
     - `ip` counts every loop exit that finds an interrupt line raised (cpu-exec.c:2270);
     - `iq` counts the ones the CPU takes (2313).
     - The kernel idle loop 0x8001b02e is STI;NOP;NOP;CLI, so a spinning guest polls a pending line mostly with IF=0 and
       takes it only in the STI slot.
     - `iq` is flat because the delivered interrupts (vblank, PGRAPH notify, timer) do not change with the frame rate.
4. **4-5x the draw thread's CPU per frame, off-CPU half the time, backlog 150-230 KB, `drain` 0.**
   - On-CPU: 22.6 ms a frame at ~1000 draws, against 13.5 ms at ~650 in the late 30-fps section. The CPU per draw is
     about the same, and the plateau's shots carry more draws.
   - Off-CPU: the downloads, 33 ms a frame.
   - Backlog with no drain: the thread never finds the ring empty. Each download stops it mid-buffer while the guest
     keeps writing ahead, and the guest then waits on a token behind the backlog.
5. **Single slow frames of 104-343 ms in 30-fps windows.** OPEN.
   - A has max 100 at mark+111 and max 215 at mark+118, both in 30-fps windows, warm shader cache.
   - Next instrument: `[shd413]` dpc_ms and the frametrace row of that frame.
6. **The second slow stretch the owner's capture cut off.**
   - In A, the second plateau is mark+167..191, after a 10-s recovery at 33 ms (mark+156..164). Its peak is 95 ms a
     frame with 128 downloads a frame.
   - It looks like the owner's 21:26:01 stretch (8-s recovery, then 6 gfps). The same mechanism holds, with more
     downloads a frame.
   - From mark+236 to the end of A, the scene holds 30 fps with 21 downloads a frame.
7. **`eo` rises 10-20x at the plateau's edges while frames are near 30 fps.**
   - A: eo ~100 k per 2 s before mark+120, 1.2-2.2 M at the edges (mark+120..129 and 156..164), and 0.8-1.4 M in the core.
   - The top `eo` PC is e:0001ec3a, FLDCW in MSVC's `_control87` (scratch/guestcode.md). A TB ends at each x87
     control-word load.
   - At the edges the guest is busy (idle share 0) and calls it per object, so `eo` counts guest work, not a stall.
     In the core, the same calls are diluted by idle spin.
   - It costs no frames at the edges (33-35 ms).

## #1018 hypotheses (re-ranked on the cinesplit A/B)

| | Hypothesis | P start | P now | Evidence |
|---|---|---|---|---|
| F1 | Synchronous GPU waits on the PFIFO thread | 0.45 | **0.95** (`cvt` downloads, one cause of two) | W hit: 61 sdown/f, 33 ms/f, equal to the unhooked blocked time; census K: all `cvt`; C: S2T_CVT takes them to 0 and the span 0.71 x |
| F7 | The vCPU is the bound in the heavy shots once the downloads go | -- | **0.85** (the second cause) | census B: plateau 40-61 ms/f, guest idle 0, pidle 25-32 ms/f, gpu 17-23 ms/f |
| F6 | The heavy shots really carry more work | 0.3 | 0.6 (contributor) | draws 1000-1363/f against 650; p_run 22.6 against 13.5 ms. Alone it fits in 33 ms |
| F2 | Host GPU-bound | 0.3 | 0.02 | G: gpu/P 0.17; sysmem P 0.96 |
| F3 | Late notifier/interrupt delivery | 0.15 | 0.05 | busy spans begin on the NV2A wake, behind the downloads; iq flat |
| F4 | Idle-spin feedback loop | 0.1 | 0.05 | edges have eo up with no slowdown; p_rq 0% |
| F5 | Disc waits | ~0 | 0 | ide425 w=0 |

## #1018 remedies after the census (ranked by P x win)

The plateau needs both causes removed: the downloads (A: 59.3 ms/f over the span) and the vCPU's excess (B: 41.9
ms/f with no downloads). Neither alone reaches 33.4.

| # | Remedy | P it works | Win at full scale | Evidence |
|---|---|---|---|---|
| R1 | `HAKUX_S2T_CVT` on by default (built, fps1015) | 0.9 measured | span 59.3 -> 41.9 ms/f; whole cinematic 39.3 -> 35.9 | census C HIT; MKSM and Top Spin A/Bs. Blocked on its pixel leg (Texture_shadow_comparator, a vk/draw.c regression on master) and one mechanism screen, both fps1015's |
| R2 | FLDCW ends a TB only when the precision bit flips, and chains when it does | 0.6 | up to the plateau's 11-16% loop time, ~5-8 ms/f of B's 42-61 | rr425: 1-2 M `eo` per 2 s at 0x1ec3a; gapus 11-16% against 2-6% |
| R3 | Name and remove the plateau's `x` longjmps | 0.3 | unknown until named; 96-197 k per 2 s | rr425 `x` triples in the plateau |
| - | `TU_DEBUG=sysmem` | refuted | -- | cinesplit P 0.96 |

R1 is another lane's switch, and its blockers are another lane's files. R2 is this lane's to build: it is the
vCPU half, and it needs only target/i386/tcg/translate.c.

### Earlier ranking (before the census named the refusal)

Win at full scale: up to 33 ms a frame. That is p_run 22.6 plus pidle 7.3, about 30 ms, which puts the plateau back
at the 30-fps pair.

1. **Bind or copy the refused surface on the GPU instead of downloading it.**
   - The texture path: vk/texture.c:2904 (`surface_download_if_dirty` when `check_surface_to_texture_compatiblity`
     refuses a draw-dirty surface) and the range scan at :2969.
   - This is the same refusal class as #986 MKSM. `HAKUX_S2T_CVT` covers only its `cvt` reason: a 5/6-bit texture over
     a 2-byte surface.
   - P is unknown until `[txdl794] why=` names the reason in Halo. The perflog census decides between:
     - `HAKUX_S2T_CVT` as built (why=cvt);
     - a new GPU-side copy for `dim`/`pitch`/`swz`/`bpp`;
     - another caller (vertex.c:175, blit.c, the flip).
2. **Coalesce the downloads.** Record them deferred and complete once per frame or per fence, instead of one finish
   each. This is surface.c's deferred path. P 0.3, win half of the 33 ms. It is only correct if the guest does not read
   the downloaded bytes on the CPU in between; the texture path does read them (its upload follows).
3. **TU_DEBUG=sysmem.** Refuted: P leg 0.96.

## #1018 census: whose downloads (halo1016-census.json, queued 00:27 PDT 10-17)

Where a `SURFACE_DOWN` finish can come from (OPT_SURF_TO_TEX_INLINE = 1):
- a deferred download completed at its consumer (surface.c:2142);
- an inline `download_surface_to_buffer` (2700);
- the pending/dirty fallbacks (3002, 3086).

The consumers that force them:
- the texture path (`txr dl` / `scdl`);
- the CPU range watch (`[sdcall] range`);
- an eviction completed before a new binding uploads (`surfupd`);
- reuse, expire, and the record and flip paths.

What is already known, before the census:
- **Same-address incompatible evictions are not it.** cinesplit A's `[evict372]` line is flat across the plateau:
  - 60 Z<->C role swaps of one 640x480 surface (f130 <-> f44, pitch 2560);
  - every one of them handed off on the GPU;
  - 0 fallbacks.
- **The only perflog soak of this title** (10-03, 1-1791064684-lanelocal-4097992, effb0d001b, the cinematic skipped,
  its slow stretch pre-gameplay at 49 ms/f) puts all of its 2 downloads a frame on evictions:
  - Finish sd 2.0/f (cDef 1.5, sd[dl] 0.5);
  - `dif` ovl 2.0/f, ovlSh 1.0/f;
  - `txr` dl 0, scdl 0;
  - `[sdcall]` surfupd 0.99 fin/f (18.6 ms/f), tobuf 0.49/f.

  That is overlap eviction: a new binding at another address over a draw-dirty one, `invalidate_overlapping_surfaces`.
  Its rate is 1/30 of the plateau's.

The instrument, `[ovl1018]` (214445e90e, surface.c, counters only):
- It counts evictions by overlap and shelf, draw-dirty and clean, by relation:
  - the evicted surface inside the new one, or covering it;
  - a role, format or pitch change;
  - from the shelf, downloaded inline.
- It keeps an 8-pair table of draw-dirty (evicted, new) shapes and the address offset between them.
- It logs every 5 s beside `[evict372]`.

The arms:
- A = 1792222165-halo1016-1341449: perflog, frametrace and probe1010 on 214445e90e.
- B = 1792222171-halo1016-1341994: A plus `HAKUX_S2T_CVT=1`.

Judge: `censusread.py`, exercised on the 10-03 log by `scratch/censusread_mock.py` before either arm ran.

| Leg | Hypothesis | P | Hit |
|---|---|---|---|
| O | overlap eviction | 0.55 | `[ovl1018]` draw-dirty >= 0.6 x Finish sd per frame, and txr dl + scdl + range <= 0.3 x |
| K | the texture path refuses the surface | 0.25 | txr dl + scdl >= 0.6 x Finish sd |
| R | the guest reads the frame back on the CPU | 0.10 | `[sdcall]` range fin >= 0.6 x Finish sd |
| - | expire, fallbacks, reuse | 0.10 | none of O, K, R |
| C | `HAKUX_S2T_CVT` removes them (the #986 MKSM switch) | 0.10 | B's sd/f <= 0.5 x A's, and ms/f <= 0.8 x A's |

What each verdict sends to the remedy:
- **O with a fixed pair shape:** copy the evicted image's overlapping texels into the new binding on the GPU, instead of
  download, VRAM, upload. An alternative is to widen SURFSPLICE (on by default, `spl` in `[sdcall]`) to cover the pair.
- **K:** its `txdl` reason names the GPU route to build. `cvt` is the one `HAKUX_S2T_CVT` already covers, and
  Texture_shadow_comparator is the blocker on making that default-on.
- **R:** the access watch, not the surface cache.

## #1018 census verdict (judged 00:56 PDT 10-17 by censusread.py as committed in 7a960726d8)

- A = 0-0-x-1792222165-halo1016-1341449: 214445e90e, perflog, `HAKUX_FRAMETRACE=1 HAKUX_PROBE_WAITS=1`.
- B = 0-0-x-1792222171-halo1016-1341994: the same, plus `HAKUX_S2T_CVT=1`.
- Full output: `scratch/census-verdict.md` (per-block surface table) and `scratch/census-frametrace.md` (per-window
  pace, guest idle, dispatcher and draw-thread table).
- V valid: both reached `mark cinematic`; A's span [mark+131, mark+191] runs 59.3 ms a frame, B's 41.9.

| Leg | Result | Measured (A over the span unless named) | Threshold |
|---|---|---|---|
| O overlap eviction | MISS | `[ovl1018]` draw-dirty 0.00/f against Finish sd 49.28/f | >= 0.6 x |
| K texture path | **HIT** | txr dl + scdl 49.28/f = 1.00 x Finish sd; txdl reasons: `cvt` 50261, every other reason 0 | >= 0.6 x |
| R CPU range read | MISS | `[sdcall]` range fin 0.00/f | >= 0.6 x |
| C `HAKUX_S2T_CVT` | **HIT** | B/A Finish sd 0.00; B/A ms per frame 0.71 (41.9 / 59.3) | sd <= 0.5, ms <= 0.8 |

Over the whole cinematic from mark+40 to mark+260 (not judged), A runs 39.3 ms a frame with 20.8 downloads a
frame (117018 `cvt`, 187 `pitch`), and B runs 35.9 ms with 0.03. B's `s2tc` (GPU decode copies) is 64.6 a frame
over the span and 29.3 over the whole.

Read:
- **The downloads are #986's.** Each is a draw-dirty 2-byte colour surface sampled as a 5/6-bit texture. #59's guard
  in `check_surface_to_texture_compatiblity()` refuses it, so `surface_download_if_dirty` reads it back with a
  submit and a fence wait, and the texture path uploads it again. Same-address evictions, overlap evictions and
  CPU reads are all zero.
- **They scale with the shot.** A's downloads per 2-s block go from 0-1300 before mark+120 to 2400-4800 in plateau
  1 and 7200-7600 in plateau 2 (mark+176..182, 100 ms a frame).
- **`HAKUX_S2T_CVT` removes every one.** B's span holds 0 downloads, 0 `cvt` refusals and 64.6 GPU copies a frame.
  It is the same switch that took MKSM's cutscene from 28 to 54 fps (fps1015).
- **It does not clear the plateau.** B, per window (census-frametrace.md):

| t-mark s | A ms/f | B ms/f | B guest idle | B p_run | B pidle | B gpu |
|---|---|---|---|---|---|---|
| 0-110 | 33.4 | 33.4 | 0 | 2-10 | 22-31 | 1-10 |
| 123-131 | 50-54 | 39-51 | 0 | 14-21 | 24-28 | 14-19 |
| 134-147 | 66-85 | 46-61 | 0 | 18-22 | 25-32 | 17-23 |
| 149-154 | 52-70 | 36-43 | 0 | 14-16 | 17-24 | 12-16 |
| 156-162 | 33-34 | 33-36 | 0 | 11-13 | 21-23 | 9-12 |
| 164-179 | 41-100 | 40-53 | 0 | 15-19 | 25-31 | 15-21 |
| 181-198 | 33-62 | 34-39 | 0 | 11-16 | 15-22 | 8-14 |
| 200-346 | 33.4 | 33.4 | 0 | 6-16 | 19-28 | 3-14 |

  In A the guest idled 26-58% of each plateau window, waiting on the downloads. In B it never idles, and the draw
  thread waits for work (pidle) 25-32 ms a frame while the GPU's own time is 17-23 ms. **So in B the vCPU is the
  bound**: the guest needs 40-61 ms of emulated CPU a frame in these shots, against 20 ms in the late 30-fps
  section (A's idle share 0.3-0.4 there).

## #1018 the guest-CPU half (B's plateau)

The dispatcher table over B (`scratch/rrtable.py <B> 100 260`; `[rr425]` legend at accel/tcg/cpu-exec.c:1093):

| span | TBs dispatched /2 s | `eo` /2 s | top `eo` pc | `x` longjmps /2 s | loop time (gapus) |
|---|---|---|---|---|---|
| mark+101..115, 30 fps | 0.18-0.35 M | 0.09-0.14 M | 0x1ec3a | 17-70 k | 1.7-3.8% |
| mark+117..197, plateau | 1.9-2.8 M | 1.36-2.16 M | 0x1ec3a (97%) | 96-197 k | 11-16% |
| mark+199..259, 30 fps | 0.39-0.69 M | 0.24-0.40 M | 0x1ec3a | 33-73 k | 2.6-5.9% |

- `eo` is EOB_ONLY: a TB that ends and returns to the main loop with no chaining. 97% of them in the plateau are
  one guest instruction, 0x1ec3a `fldcw [ebp+0xc]` (`d9 6d 0c`), inside the title's CRT `_control87(new, 0xffff)`
  (scratch/guestcode.md). Its 11 callers are MSVC math support: NaN-safe compares and round/classify helpers
  beside `frndint`. The heavy shots call it about 40 k times a frame, against 6.5 k in the late section.
- The TB ends there because of hakuX's FP JIT, not the guest: target/i386/tcg/translate.c:3423 ends every TB after
  FLDCW (`gen_eob(s, DISAS_EOB_ONLY)`), since the native-float code is specialised on the precision-control bit
  (`HF_FPU_PC_MASK`, cpu.h:2825). The FP JIT is on by default on Android (`fp_jit` true).
- The plateau's loop time is 11-16% of the vCPU's wall, against 2-6% at 30 fps. That is the cost of the ~1 M
  unchained exits a second.
- `x` (longjmps into the loop: exceptions, HLT, PAUSE, MMIO recompiles) triples in the plateau. Not yet named.

Offline (scratch/audio/REPORT.md):
- MON_VP plays the dialogue (v65) +4.1 dB over the music at slot0 and +1.0 at slot1, exactly the title's register
  ratio.
- The bed is 3D low-frequency voices (v4/v5/v6, v15) through the HRTF, at about speech level, and +12 dB at slot2.
- Halo's own DSP program would play the bed +4.65 dB louder still.
- So A2 (`use_dsp`) is refuted in the direction that matters, and A1 (max-over-bins) is not this bug.

Speech legs: A = meter on (l1, the default); R = `HAKUX_APU_HRTF_NORM=raw`. Judge: `speechread.py` as committed in
a93db78057.

### Speech verdict (halo1016-speech.json; judged 00:30 PDT 10-17)

- A = 0-0-x-1792220370-halo1016-1204164 (l1); R = 0-0-x-1792220376-halo1016-1205473 (raw); both on 8f70b1e9e0.
- V valid on both: mark, 27 and 29 cine shots, the meter on, the norm logged, 25 and 16 speech windows.

| Leg | Result | Measured | Threshold |
|---|---|---|---|
| B | MISS | A median S-M -4.3 dB over 25 speech windows | >= 0.0 |
| L | MISS | median l1 over A's 795 3D HRIR binds 13.09 (l2 ~3.0, dc ~-4) | < 1.0 |
| N (R) | MISS | R's bed 20.0 dB **over** A's (3d -14.5 against -34.5); S-R 13.9 dB worse; clipped 959161 against 2 | bed >= 3 dB under, S-R >= 3 dB over, no more clipping |
| S | MISS | 0 `sslempty v=65` after mark; 0 v65 pauses in windows under 25 fps | >= 1 |

Read, by the prediction's own text:
- **H1 is refuted.** The guest's taps sum to l1 ~13, so hrtf.h's division cuts the bed by ~22 dB rather than raising it.
  The only other scale on offer, raw, plays the bed 20 dB louder and clips a million samples, which no Xbox does. `cap`
  is the quieter of l1 and raw per voice, so it equals l1 here: the lever is spent in both directions.
- **H3 is refuted.** The dialogue stream never runs dry, in the slow shots or anywhere else.
- **B missed, but not for the reason its text assumed.** "Speech under music against the registers" was the premise.
  The register log (`apumix`, scratch/mixregs.py) shows hakuX holds every register the title writes, and the miss
  comes from the music's content, below. So B refutes REPORT 1.2's whole-cinematic reading (+4.1 / +1.0 dB held at
  two state moments). It does not refute H2.
- R's own S-M is not a reading: `top=` keeps 8 voices, and at raw the 3D voices push the music out of it in two windows
  (M = -200). No leg used it.

### What is over the speech (A's registers and meter, window by window: `scratch/mixregs.py <A>`)

- **Both voice classes take the same path.**
  - Speech v65: 2D mono ADPCM at 22 kHz, bins 0/1 at -13.4 dB, unchanged for the whole cinematic. Its source peaks at
    0 dBFS (RMS -16.4).
  - Music v85/v86/v87/v88: 2D stereo ADPCM at 44 kHz, bins 0/1.
  - In the owner's slot0 and slot2 states, every one has fmode 0 (bypass) and its envelope off (hxs_voices.py). So no
    unemulated filter (ParaEQ, vp.c:2306) or envelope sits on either.
  - One decoder and scale serve both (`adpcm_decode_block`, `int16_to_float`, vp.c:1849-1858), and the bins are the
    same, so Halo's DSP program treats them alike too.
- **The title moves the music itself.** v85/v86 step between -15.1/-9.1 and -12.0/-6.0 dB in step (a 3.1 dB duck).
  v88 enters at mark+118 at -6.0/-9.1.
- **Speech while it runs** (its window level scaled to its active frames n/7500), against the summed music:

| span | windows | median speech - music | range |
|---|---|---|---|
| before mark+130 | 13 | +1.9 dB | -5.1 .. +4.2 |
| from mark+130 | 12 | -1.7 dB | -12.3 .. +4.9 |

  - From mark+133 the score swells: v86's content climbs from about -30 to -7 dBFS by mark+138, and v88's from -31 at
    mark+118 to -16 by mark+208. Speech's content stays at -12 to -20.
  - Speech is never clearly over the music. Its median margin is +2 dB early and -2 dB late. The 3D bed sits at about
    speech level beside both (A's S-B median +1.8 dB, by window).

**Account of the symptom ("voiceovers quiet, music loud"):** hakuX plays Halo's mix as the title sets it: its own
registers, its own content, one decoder, no filter on either path. In that mix the dialogue has no more than ~2 dB
over the music, and loses it in the swell at mark+133..163 and mark+198..243. That is about 2:00-2:35 and 3:05-3:50
into the cinematic: the route marks at LOADING, about 10 s before the first shot. Nothing found between the
registers and the meter separates speech from music. One stage cannot be read here: hardware's own output stage,
and whether Halo's GP program compresses the bus dynamically (the dsp_harness measured static gains at one level).

| | Hypothesis | P start | P now | Evidence |
|---|---|---|---|---|
| H2 | The mix is the title's own | 0.30 | **0.65** | registers held as written; same codec, bins, filter (bypass) and envelope (off) for speech and music; the late swell is in the music's content |
| A7 | Halo's GP program compresses the bus on hardware (level-dependent; static harness gains miss it) | -- | 0.08 | untested: the dsp_harness at two input levels would decide it offline |
| A8 | The register scale (1/64 dB per step, vp.c:450) is wrong | -- | 0.05 | speech's register sits inside the music's range (-6.0 .. -15.1), so an error moves the ratio either way by <= 2 dB |
| A9 | The Nova's own output (small speaker, Android DRC) | -- | 0.10 | perception, not the emulator; untested |
| H1 (A3) | The L1-normalised HRIR plays the 3D bed louder than the guest's taps | 0.20 | 0.01 | L, N: l1 ~13; raw is 20 dB louder and clips |
| H3 | The dialogue stream starves in the slow shots (#1018) | 0.12 | 0.01 | S: 0 sslempty |
| A2 | Halo's DSP mix restores the balance | 0.3 | 0.02 | dsp_harness: bed +4.65 dB further over; speech and music share bins |
| A6 | An unemulated filter on the 2D voices | -- | 0.01 | fmode 0 on v65 and v85-v88 |
| A1 | Max-over-bins | 0.5 | 0.01 | v65 is 2D mono in bins 0/1 |
| A4 | Volume conversion | low | 0.02 | registers held as written; the meter reads gain x content |
| - | other | | 0.04 | |

**#938 remedies.** Two have been chased, and both are null:
- the HRIR scale (raw, refuted; cap, which equals l1 here);
- the #1018 fps fix (H3 refuted: speech does not starve, so a faster cinematic leaves the balance where it is).

Nothing in the emulator plays this mix wrong on present evidence, so this lane does not propose a #938 fix.
- What would decide it is a hardware reference: the Questions below, with the times above.
- A7 can be decided offline: the dsp_harness at two input levels. That is the next instrument if one is wanted.
- A per-title dialogue boost would be a change to the title's mix, not emulation, and is not proposed.

## What the next lane should not repeat

- Do not chase `TU_DEBUG=sysmem` or GPU-bound explanations for this cinematic: the cinesplit A/B refutes both.
- A dispatcher soak with `--pull 'frametrace_*'` brings back old CSVs from the device; read only the run's own
  (cineread.py `run_csvs()`).

## Questions (for the owner; nothing waits on them)

1. On a real Xbox, does the dialogue in the opening cinematic sit clearly over the music? Listen especially from about
   2:00 to 2:35 into the cinematic (the score swells under Keyes and Cortana) and from 3:05 to 3:50. hakuX plays the
   title's own registers and content there with speech level with the music (+2 dB early, -2 dB in the swells). If
   hardware has the voices plainly on top, there is a stage after the voices that hakuX lacks (A7), and the
   dsp_harness is the next instrument. If it sounds the same, #938 is the title's mix.
