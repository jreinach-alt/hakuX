# lane.halo1016 -- NOTES

Halo: Combat Evolved (4D530004), opening cinematic on the Nova. Found on 0.5.1-rc1; the target is now **0.5.2**
(0.5.1 shipped without this lane, owner 10-16 ~22:50 PDT).
Defects: **#938** quiet speech under loud music; **#1018** the cinematic drops to 8-19 fps for ~47 s.

## Status (2026-10-17 03:10 PDT)

- #1018: **where the poll waits is found** ("#1018 reports arms: RT, RC"). Both arms are VOID on their own V:
  the prediction required the synchronous report path. The app's "Fast renderer paths" default sets
  `HAKUX_REPORT_ASYNC=1`, so every arm here, and the owner's play, runs the async reader. That mistake is mine.
  Their traces still read cleanly, descriptively:
  - Each of the ~544 armed GET_REPORTs a frame waits for the frame's last finish (q2e median 8-16.7 ms).
  - It then waits for the GPU to run that whole command buffer (q2w 16.7-33.3 ms for 77%).
  - The guest polls each one about a frame after issuing it, and spins until it lands.
  - The catch-up finish (RC) never fired: 0 a frame.
- Two remedies are built (08fd920b5c, both off by default) and measured in `halo1016-early.json`'s six arms:
  - R8, `HAKUX_REPORT_EARLY=1`: answer each armed report at once, with its offset's last count.
  - R7, `HAKUX_REPORT_SUBMIT=2000`: finish at a report, so the GPU starts earlier.
  - The judge is `earlyread.py`, written before any arm ran.
- Earlier, 02:40:

- #1018: **the heavy shots' "vCPU bound" is the guest polling an occlusion report.** The two hottest TB entries
  are one loop: 0x63482 calls D3D's 0x1810f0 while it returns 0x88760828, which it does at 0x18111b when the
  report's status word is still -1 (a visibility-test result poll). A's span spends 26.7% of TB time in that loop
  and IF's 44.1%: the vCPU work R2 and #507 removed went mostly into polling longer, which is why each bought only
  5% ("#1018 the spin"). The vCPU arms A, F, I, IF are judged (A2 pending): FL, FM, IM HIT; FE, IE, BE, G MISS.
- The next arms (halo1016-reports.json, on the commit with `HAKUX_REPORT_CATCHUP`) measure where the poll's time
  goes (`HAKUX_REPORT_TRACE=1`) and test the remedy for the one mechanism the code shows: a report queued after
  the catch-up finish waits for the next finish of any kind.
- Earlier, 02:10:

- #1018 vCPU half: R2 is built (d70f782f45, `HAKUX_FLDCW_CHAIN=1`, off by default) and #507's inline probe
  (`HAKUX_IBC=1`) is the second remedy. Both are measured on the S2T_CVT base in five arms (A, F, I, IF, A2),
  registered in `halo1016-vcpu.json` and judged by `vcpuread.py`, written before any arm ran ("#1018 vCPU arms").
- Earlier, 01:45:

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

## Why attempt 3 did not finish

Attempt 3 ended on its turn cap (301 turns) at 03:26:49 PDT, with its work committed and pushed (a23ee0cccf):
the reports arms judged and posted on #1018 (03:10), R7/R8 built (08fd920b5c), the six early arms queued with
earlyread.py committed first. Two of the six had landed. Its turns went into the four vCPU and tier-1 arms
(T, FIT, A..A2) and the reports pair, each judged and posted, before the trace located the poll's wait. The
only loose file was scratch/comment-reports.md, whose text was already on #1018. Attempt 4 waits on all six
with one call and judges them with earlyread.py as committed.

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
| F7 | The vCPU is the bound in the heavy shots once the downloads go | -- | 0.85, then **0.35** as the vCPU's own work | census B: plateau 40-61 ms/f, guest idle 0, pidle 25-32 ms/f, gpu 17-23 ms/f. The vcpu arms: removing 45 k main-loop returns (F) or 850 k helper lookups (I) a frame buys 2 ms/f each, and the spin's share of TB time rises |
| F8 | The guest polls a visibility-test report in the heavy shots, and the poll's wait is the bound | -- | **0.85** | 0x63482/0x18111b disassembled ("#1018 the spin"). Spin share of TB time rises 0.267 (A) -> 0.441 (IF) as ms/f falls 3.4. RT: each of 544 armed reports a frame is written 16.7-33.3 ms after it is queued (77%), behind the frame's last finish and the GPU's run of the whole command buffer |
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
| R4 | #507's inline jump-cache probe on (`HAKUX_IBC=1`, built, parked off) | 0.5 | up to ~9 ms/f: 930 k helper lookups a frame, ~10 ns saved per hit | B: hc 930 k/f, miss share 3e-5; GTA: the helper's hit path was 18.4% of the vCPU. Parked because its saving became guest idle spin on GTA/Forza; Halo's plateau never idles |
| R2 | FLDCW ends a TB only when the precision bit flips, and chains when it does (built, d70f782f45) | 0.55 | ~4.3 ms/f: 36 k main-loop returns a frame at ~118 ns of loop each | rr425: 36.2 k/f `eo` at 0x1ec3a of 49.9 k returns; loop 14% of the vCPU wall |
| R3 | Tier-1 promotion off (`HAKUX_TIER1_THRESHOLD=0`, an existing switch): no hot block left CF_INVALID and unchainable | 0.45 | ~0.9 ms/f of loop for 7.9 k `gi` returns, plus their qht lookups; and it keeps R2's `_control87` block chainable | named below ("the `gi` exits are tier-1's"); `promote` lines name 0x19f23 and 0x1ec3d |
| R3b | Name and remove the plateau's `x` longjmps | 0.3 | 2.8 k a frame, ~0.3 ms/f | unnamed |
| R2, R4 measured (10-17 02:20) | F and I alone: 0.951 x A each; IF 0.921 | -- | 2.1 / 2.1 / 3.4 ms/f | the work is gone (eo 0, helper lookups 0.016 x) and the poll absorbs it (F8) |
| R5 measured (10-17 03:00) | `HAKUX_REPORT_CATCHUP=1`: write a queued GET_REPORT at the catch-up finish | **~0** | RC 42.0 ms/f vs RT 43.1 (inside A/A2's 0.023 spread) | 0 catch-up finishes a frame: the FIFO is never caught up with a value report queued. The guest is a frame ahead of the PFIFO |
| **R8** | `HAKUX_REPORT_EARLY=1` (built, 08fd920b5c, off): answer an armed GET_REPORT when it is queued, with the count its offset was last written with; the reader's count goes to the table, not the guest | **0.6** for EM (mechanism 0.8, a frame-stale flare is the cost) | the whole spin: 12-17 ms/f of 39-43, so the span to ~27-31 ms/f, under the bar with IF | RT: every offset reused once a frame (33-66 ms apart), all armed. Precedent: RPCS3 "relaxed ZCULL sync", Dolphin's approximate perf queries |
| **R7** | `HAKUX_REPORT_SUBMIT=<us>` (built, off): finish at an armed GET_REPORT `us` after the last finish, so the GPU starts on the draws before it, as the NV2A writes a report when it reaches it | 0.2-0.35 | the GPU half of q2w, ~15 ms/f at most | fits the hardware. But each finish on the Nova's tiler is a render-pass break (GMEM store and reload) plus a slot rotation wait |
| R6 | Record draws faster so the PFIFO is nearer the guest | 0.15 | partial: the report still waits for the frame's finish and the GPU | RT: the wait is after the PFIFO reaches the report, not before it (q2e >= 2 ms for all of them) |
| - | `TU_DEBUG=sysmem` | refuted | -- | cinesplit P 0.96 |

P x win: R1 (0.9 x 17 ms) first, then R4 (0.5 x 9) and R2 (0.55 x 4.3), then R3 (0.3 x 1.3). B needs 8.5 ms/f off
to reach 33.4, so only R4 + R2 together can reach the bar; that is the IF arm, P 0.15 for the bar. R1 is another
lane's switch, and its blockers are another lane's files. R2 and R4 are measured together on R1's base.

The main-loop returns over B's span, per guest frame (`vcpuread.py`'s table on the census pair):

| | per frame | share of returns |
|---|---|---|
| TBs dispatched from the main loop | 49.9 k | 100% |
| `eo` (EOB_ONLY), all | 37.0 k | 74% |
| `eo` at 0x1ec3a (`fldcw`) | 36.2 k | 73% |
| `g` unpatched goto_tb exits | 9.6 k | 19% |
| `gi` (a CF_INVALID block) | 7.9 k | 16% |
| `x` longjmps | 2.8 k | 6% |
| helper_lookup_tb_ptr calls (not main-loop returns) | 930 k | -- |

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

## #1018 vCPU arms (halo1016-vcpu.json, registered 02:05 PDT 10-17)

R2 as built (target/i386/tcg/translate.c, `gen_fldcw_chain`):
- A TB depends on the control word only through `HF_FPU_PC_MASK`: `fpu_using_double_precision()` picks f32 or
  f64 ops at translation. The rounding mode is not baked in. `gen_bb_epilogue()` runs before every helper call,
  so the call to `helper_fldcw` flushes the FP cache and clears `flcr_set`, and the next FP op reloads the host
  rounding mode from the new `fpuc`.
- So with `HAKUX_FLDCW_CHAIN=1` translation goes on past an FLDCW. A runtime test after the helper compares
  `hflags & HF_FPU_PC_MASK` with the TB's own. Equal: carry on in the TB. Flipped: eip past the FLDCW
  (pc-relative), then `lookup_and_goto_ptr`, which finds the TB for the new flags, through #507's probe when that
  is on. Not under RF/TF/interrupt shadow/CF_NO_GOTO_TB (`jmp_opt`), and not in 64-bit code.
- `helper_fldcw` counts calls and flips and logs `[fldcw1018] n= flips= cw=` every 2^20 calls, in every arm.
  The translator logs `[fldcw1018] chain=` once.

Arms, all on d70f782f45 with `HAKUX_S2T_CVT=1` (census B's configuration), perflog, 420 s, in this order:
A (base), F (+`HAKUX_FLDCW_CHAIN=1`), I (+`HAKUX_IBC=1`), IF (+both), A2 (base again, for drift).
Legs and P: FL flips/n <= 0.05 (0.7); FM F's eo at 0x1ec3a <= 0.1 x A's (0.6); FE F <= 0.93 x base (0.55);
IM I's helper lookups <= 0.3 x A's (0.85); IE I <= 0.93 x base (0.5); BE IF <= 0.87 x base (0.4); G IF <= 33.4
ms/f (0.15); N spread <= 0.08 (0.7).

### The `gi` exits are tier-1's (read from census B, `scratch/vcpuhot.py <B>`)

- In census B's span, `[rr425pc]` puts 380 k of 459 k unpatched goto_tb exits per 2 s at resume pc 0x19f23
  (`test bl,0x20`). `gi` counts the exits left unpatched because the block that started the chain carried
  CF_INVALID.
- The `hakuX-tier1` lines in the same log name 0x19f23 and 0x1ec3d (the block after the FLDCW) in `promote #N`,
  then `dedup ... already pending`, every 10 000 calls.
- Mechanism: `tb_request_tier1_promotion()` (cpu-exec.c:393) marks a block that reached 64 executions
  CF_INVALID and leaves it in the qht. The qht compare masks CF_INVALID (`tb_lookup_cmp`, the #73 pair), so
  the block is found and run on every lookup. `tb_gen_code` never runs, and the request is never consumed:
  the known gap the comment at cpu-exec.c:710 records. What that comment does not count is the cost:
  - `tb_add_jump` refuses a CF_INVALID destination, so nothing chains into the block;
  - the jump cache misses on it every time (stale, then a qht lookup);
  - the main loop drops `last_tb` after running it, so the chains it starts end in exits that stay unpatched.
  Up to 64 hot blocks are pinned like this for a whole run, in every title.
- `HAKUX_TIER1_THRESHOLD=0` (xemu_android.cpp:1201, read after the request env is applied) stops promotion.
  It is measured in `halo1016-tier1.json`: T (tier-1 off) and FIT (tier-1 off + R2 + #507), judged by
  `tier1read.py` against the vcpu arms' A, A2 and IF.
- Where the plateau's TB time goes (`[tpc787]`, sampled): 30% in runs entered at 0x1ec3d (the code after each
  FLDCW, ~0.3 us a run), 17% at 0x18111b and 8% at 0x63482 (long chained loops, ~0.7 ms an entry: the title's
  own work). In the 30-fps window before it, 70% is the idle loop at 0xbb0d4..0xbb0ee.

### Tier-1 arms judged: T, FIT (tier1read.py as committed in 82a151b922, 03:0x PDT 10-17)

| arm | env over A | ms/f | x base 42.1 | gi | it | spin share (reportread.py) |
|---|---|---|---|---|---|---|
| A | -- | 42.6 | 1.012 | 8,005 | 50,088 | 0.267 |
| A2 | -- | 41.6 | 0.988 | 174 | 42,213 | -- |
| T (1781747) | `HAKUX_TIER1_THRESHOLD=0` | 40.8 | 0.969 | 0 | 42,090 | 0.296 |
| IF | FLDCW_CHAIN + IBC | 39.2 | 0.932 | 28 | 5,740 | 0.441 |
| FIT (1783282) | all three | 39.4 | 0.937 (1.005 x IF) | 0 | 6,904 | 0.430 |

- N HIT (spread 0.023). TM HIT: `gi` 0 in T and FIT, so the CF_INVALID pinning is the whole of the `gi` exits.
- TE MISS (0.969, bar 0.96), XS MISS (FIT 1.005 x IF), XE MISS, XG MISS.
- **The three vCPU remedies are measured and the frame has a floor near 39 ms in the span that none of them
  moves.** Splitting each arm's frame by its spin share (TB time is ~96% of the vCPU's wall here, census B), the
  vCPU's own work per frame is A 31.2, T 28.7, IF 21.9, FIT 22.5 ms, and its polling is A 11.4, T 12.1, IF 17.3,
  FIT 16.9 ms. IF removed 9.3 ms of work and the poll grew 5.9 ms. Whatever the poll waits on takes ~39 ms a frame
  in these shots, whatever the vCPU does. That is what halo1016-reports.json's RT trace locates.
- The vCPU remedies stay off-by-default switches. They are real savings, ~9 ms/f of vCPU work, that become
  frame time only once the poll's wait shrinks, so RC and anything after it should be measured with IF on as well.

### vCPU arms judged: all five (vcpuread.py as committed in d70f782f45)

A2 landed at 02:4x: 41.6 ms/f, so N HIT (A/A2 spread 0.023) and the base is 42.1. Against it: FE MISS (F 0.963),
IE MISS (I 0.962), BE MISS (IF 0.932), G MISS. A2's `gi` is 174 a frame against A's 8,005, with the same env and
binary. Which blocks tier-1 promotion pins varies from run to run, and A2's 1.0 ms/f lead over A is about the size
R3 predicted for 7.9 k `gi` returns (~0.9 ms/f). The tier-1 arms T and FIT test that directly.

| arm | ms/f | it | gi | hc | gap |
|---|---|---|---|---|---|
| A2 (1763228) | 41.6 | 42,213 | 174 | 905 k | 12.0% |

The table and bullets below were written on A alone, before A2 landed:

Over [mark+131, mark+191], per guest frame:

| arm | env over A | ms/f | dispatched | eo at 0x1ec3a | gi | helper lookups | loop gap |
|---|---|---|---|---|---|---|---|
| A (1762649) | -- | 42.6 | 50,088 | 36,249 | 8,005 | 863 k | 13.8% |
| F (1762816) | `HAKUX_FLDCW_CHAIN=1` | 40.5 | 5,263 | 0 | 29 | 927 k | 2.9% |
| I (1762962) | `HAKUX_IBC=1` | 40.5 | 50,172 | 36,185 | 7,964 | 13.6 k | 14.5% |
| IF (1763073) | both | 39.2 | 5,740 | 0 | 28 | 13.6 k | 2.9% |

- FL HIT: 0 flips in 106 M FLDCWs (A). FM HIT: F's eo at 0x1ec3a 0 (<= 0.1 x A). IM HIT: I's helper lookups
  0.016 x A.
- FE MISS (F 0.951 x A, bar 0.93), IE MISS (I 0.951), BE MISS (IF 0.921, bar 0.87), G MISS (IF 39.2 > 33.4).
  N waits on A2; the base is A alone until then.
- Both mechanisms are gone in full and the frame barely moves. Per 10-s window, the +140 and +170 shots gain
  2-9 ms and +130 (51-52 ms in every arm) gains nothing. Read with the spin below: the time removed from the
  vCPU's work is spent polling.

## #1018 the spin: the heavy shots poll a visibility test (read 02:20-02:40 PDT 10-17)

Disassembly (`/mnt/d/hakux-staging/halo1016/q5_hot.py`, capstone, the title's own default.xbe):

```
0x00063482: lea edx,[esp+4]; push edx; lea eax,[esp+4]; push eax; push esi
0x0006348d: call 0x1810f0                    ; D3D, 3 args, ret 0xc
0x00063492: cmp eax, 0x88760828
0x00063497: je 0x63482                       ; again while "not ready"
0x001810f0: ... esi = table[idx >> 8]; eax = esi + (idx & 0xff) * 16
0x0018110f: mov ecx,[eax+0xc]; cmp ecx,-1; jne 0x181123   ; status word still -1?
0x0018111b: mov eax, 0x88760828; ret 0xc     ; not ready
0x00181123: *pResult = [eax+8]; *pTimeStamp = [eax], [eax+4]; return 0
```

That is a visibility-test result read (index, result, timestamp) and a spin on it. The 16-byte record is the
NV report layout pgraph writes at GET_REPORT (timestamp, count, status 0). The D3D section's one GET_REPORT
emitter is at 0x181c5d (scratch/guestcode.md Q4).

- **The spin is the bound, not the vCPU's work.** `[tpc787]` share of sampled TB time in the loop's four entry
  pcs (0x63482, 0x63492, 0x1810f0, 0x18111b): A 0.267, IF 0.441 (reportread.py's table). IF removed ~10 ms/f of
  vCPU work (loop gap 13.8% -> 2.9%, 45 k fewer returns) and ms/f fell 3.4; the poll grew by about the rest.
- **Not the NOP callback.** The perflog `cblat` lines (scratch/cblat.py on A): one callback a frame (param
  0x304), `pnop` 0, `pidle` 0 over the span. In the heavy windows its kick-to-dispatch latency is 5-7 ms, spent in
  draws (`mdraw`): the PFIFO runs 5-7 ms behind the guest's kicks there, against 0.4 ms in the calm windows.
- **Where a report waits** (reports.c, draw.c): GET_REPORT only queues (`pgraph_vk_get_report`); every finish
  writes the queue at its tail (`pgraph_vk_finish` -> `pgraph_vk_process_pending_reports_internal`), whether or
  not a command buffer was open. At a caught-up FIFO, `pgraph_vk_process_pending_reports` runs the STALLED finish
  only with a command buffer open **and** a draw since the last STALLED finish. A GET_REPORT the PFIFO reaches
  after that finish (the guest kicked the flare's draw, the PFIFO caught up and finished, then the report came)
  sits in the queue until the next finish of any kind, while the guest spins.

Three places the poll's wait can be, and what separates them (`HAKUX_REPORT_TRACE=1`, reportasync1010's
instrument: per GET_REPORT, queued -> handed to the write (q2e) -> fence -> written (q2w)):

| | Where the poll waits | P | Signature in the trace | Remedy |
|---|---|---|---|---|
| HB | upstream of the PFIFO reaching GET_REPORT: its backlog (5-7 ms in heavy windows) or the guest's kick | 0.5 | q2w < 1 ms for >= 70% | faster PFIFO draw recording, or answer the report without waiting for the PFIFO (stale count) |
| HS | queued, waiting for a finish (above) | 0.25 | q2e >= 2 ms for >= 30% | `HAKUX_REPORT_CATCHUP=1` (built): write it at the catch-up |
| HG | after the handoff, on the GPU and the fence | 0.15 | q2w - q2e >= 2 ms for >= 30% | `HAKUX_REPORT_ASYNC=1` (reportasync1010) or an earlier submit |

HG is low because census B's PFIFO waits on fences 1.25 ms a frame in the span. HB is high because the callback
latency shows the PFIFO 5-7 ms behind the guest in exactly the heavy windows.

`HAKUX_REPORT_CATCHUP=1` (hw/xbox/nv2a/pgraph/vk/reports.c, off unless set): at a caught-up FIFO, a queue holding
a value report (not only clears) gets a STALLED finish even with no command buffer open or no draw since the last.
The value is the one the later finish would write (the running count, after the fences, same code). It logs
`[rcatch1018] on|off` once and `[rcatch1018] w open= closed=` per 2 s while it acts. Syntax-checked with the
nightly tree's arm64 Release compile command (scratch/synck.py, which fails a planted error); not built locally.

## #1018 reports arms: RT, RC (reportread.py as committed in 281ee4685e; judged 03:00 PDT 10-17)

**Both VOID on V.** V required every `[rtrace] w` window to say mode=sync. They say mode=async. MainActivity.kt's
FASTPATHS_VARS turns on `HAKUX_REPORT_ASYNC`, `HAKUX_TEXSCAN`, `HAKUX_DRAWREC`, `HAKUX_UNI_*`, `HAKUX_POSTED_PUT` and
`HAKUX_LOCKFREE_WAKE` with "Fast renderer paths" (on by default). So every arm in this lane, and the owner's play,
used the reportasync1010 reader. I wrote the prediction against the synchronous path without checking the app's
defaults. HS, HG and HB were built for that path, and the judge is not edited after the fact. What follows is
read descriptively (`reportread.py` as committed, `scratch/rtspan.py <RT> 131 191` for the samples):

| arm | ms/f | reports/f | armed | q2e >= 2 ms | q2w >= 2 ms | q2w >= 16.7 ms | spin share | catch-up finishes/f |
|---|---|---|---|---|---|---|---|---|
| RT | 43.1 | 544 | 1.00 | 1.000 | 1.000 | 0.768 | 0.290 | -- |
| RC | 42.0 | 542 | 1.00 | 1.000 | 1.000 | 0.783 | 0.313 | 0.00 |

Histograms over the span (counts; edges 0.25 0.5 1 2 4 8 16.7 33.3 66.7 ms), RT:
- q2e (queued -> handed to the reader): 0,0,73,4762,61431,266806,407227,49144,1014,0
- q2w (queued -> written to the guest): 0,0,0,0,0,1695,181351,457266,150124,21

What the trace says:
- **Every report is armed** (status word -1 when the PFIFO queues it). Each offset comes back 33-66 ms later:
  the guest reuses the same records each frame.
- **A report waits for the frame's last finish, then for the GPU.** In the r-samples, the hand-off comes at the
  next flip's finish (fe - fq = 1 for most). The q2e p25/p50/p75 are 9.1 / 12.6 / 15.6 ms, and q2w's are 19.4 /
  28.4 / 36.4 ms. The ~15 ms between them is the reader's fence wait: the GPU running the frame's whole command
  buffer, since every draw before the report is in it.
- **The guest reads the result about a frame later** (fw - fq = 1; a flip comes before the write for 78%). It
  spins in 0x63482 until the write lands. On the NV2A the report is written when the GPU reaches GET_REPORT,
  long before the next frame asks.
- **The catch-up never fires** (RC: 0 a frame). The FIFO is never empty with a value report queued: the guest is
  a frame ahead.
- HS/HG/HB as named: HS's signature holds (q2e >= 2 ms for all). HG's, defined as a difference of shares, is 0
  only because both shares are 1.0; the gap itself is ~15 ms a report. HB's does not hold (q2w < 1 ms for none).
  The wait is after the PFIFO, not before it.

### The two remedies the trace points at (built in 08fd920b5c; `halo1016-early.json`)

`HAKUX_REPORT_EARLY=1` (R8) and `HAKUX_REPORT_SUBMIT=<us>` (R7) are in hw/xbox/nv2a/pgraph/vk/reports.c. Both are
off unless set, act only on the async reader, and log `[rearly1018] early= submit_us=` once plus a
`[rearly1018] w early= cold= unarmed= submit=` line every 2 s.

R8 works like this:
- When the PFIFO queues an armed GET_REPORT whose offset is in a 4096-entry table, R8 writes the guest's record at
  once, with that offset's last count.
- It marks the queued report with bit 31 of its parameter (the TYPE byte, already asserted).
- The reader still reads the queries. For a marked report it stores the count in the table and does not write it
  to the guest.
- An unmarked report keeps today's path, including the run-now path for an unarmed one. A marked report is skipped
  there, since its status word 0 is ours.
- An offset not yet seen is cold and takes today's path.

R7: after an armed report is queued, R7 finishes (STALLED) if `us` or more have passed since the last finish.

Ranking by P x win:
1. **R8: P 0.6 x 12-17 ms/f.**
   - It removes the wait at its root, which is a result the guest has to wait for. That fits what the hardware
     gives: on the NV2A the result is long ready by the time the guest polls.
   - The cost is a count one test stale: a lens flare or a culled object can lag one frame at a camera cut.
   - RPCS3 ships this trade as "relaxed ZCULL sync", and Dolphin's perf queries are approximate the same way.
2. **R7: P 0.25 x up to ~15 ms/f.**
   - It is the hardware's own order: the result comes when the GPU reaches it.
   - On the Nova's tiler, each finish breaks the render pass (a GMEM store and reload) and rotates a frame slot. At
     2 ms that is up to ~20 a frame.

The arms are B (base), E (+EARLY), EIF (E + FLDCW_CHAIN + IBC), S (+SUBMIT=2000), and EV/BV with frames for the
pictures. All run on S2T_CVT with the trace on. EIF is there because once the poll is gone, IF's 9 ms/f of vCPU
work should finally show up as frame time.

## What the next lane should not repeat

- Before writing a V leg on a code path, read MainActivity.kt's FASTPATHS_VARS: "Fast renderer paths" (on by
  default) turns on eight `HAKUX_*` switches, among them `HAKUX_REPORT_ASYNC`. halo1016-reports.json assumed the
  sync report path and voided both arms on it.
- "Guest idle 0" is not "vCPU-bound": look at the hot entry pcs for a poll loop first (here, a visibility-test
  spin), before building vCPU remedies.
- Do not chase `TU_DEBUG=sysmem` or GPU-bound explanations for this cinematic: the cinesplit A/B refutes both.
- A dispatcher soak with `--pull 'frametrace_*'` brings back old CSVs from the device; read only the run's own
  (cineread.py `run_csvs()`).

## Questions (for the owner; nothing waits on them)

1. On a real Xbox, does the dialogue in the opening cinematic sit clearly over the music? Listen especially from about
   2:00 to 2:35 into the cinematic (the score swells under Keyes and Cortana) and from 3:05 to 3:50. hakuX plays the
   title's own registers and content there with speech level with the music (+2 dB early, -2 dB in the swells). If
   hardware has the voices plainly on top, there is a stage after the voices that hakuX lacks (A7), and the
   dsp_harness is the next instrument. If it sounds the same, #938 is the title's mix.
