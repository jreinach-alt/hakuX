# lane.halo1016 -- NOTES

Halo: Combat Evolved (4D530004), opening cinematic on the Nova. Found on 0.5.1-rc1; the target is now **0.5.2**
(0.5.1 shipped without this lane, owner 10-16 ~22:50 PDT).
Defects: **#938** quiet speech under loud music; **#1018** the cinematic drops to 8-19 fps for ~47 s.

## Status (2026-10-17 00:20 PDT)

- #1018: the cinesplit A/B is judged (below). The PFIFO thread's off-CPU half is synchronous surface downloads
  (`VK_FINISH_REASON_SURFACE_DOWN`, 61 a frame, 33 ms a frame over the plateau). The GPU is not on the path, and
  `TU_DEBUG=sysmem` is no remedy. Next: name which refusal makes them, with a perflog census run. Then the remedy legs.
- #938: the speech legs (docs/testing/predictions/halo1016-speech.json) are on the Nova:
  A = 0-0-x-1792220370-halo1016-1204164, R = 0-0-x-1792220376-halo1016-1205473.

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
| F1 | Synchronous GPU waits on the PFIFO thread | 0.45 | **0.90** (download form) | W hit: 61 sdown/f, 33 ms/f, equal to the unhooked blocked time; scales with the shot |
| F6 | The heavy shots really carry more work | 0.3 | 0.6 (contributor) | draws 1000-1363/f against 650; p_run 22.6 against 13.5 ms. Alone it fits in 33 ms |
| F2 | Host GPU-bound | 0.3 | 0.02 | G: gpu/P 0.17; sysmem P 0.96 |
| F3 | Late notifier/interrupt delivery | 0.15 | 0.05 | busy spans begin on the NV2A wake, behind the downloads; iq flat |
| F4 | Idle-spin feedback loop | 0.1 | 0.05 | edges have eo up with no slowdown; p_rq 0% |
| F5 | Disc waits | ~0 | 0 | ide425 w=0 |

## #1018 remedies (ranked by P x win; P is provisional until the census names the refusal)

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

## #938 (speech)

Offline (scratch/audio/REPORT.md):
- MON_VP plays the dialogue (v65) +4.1 dB over the music at slot0 and +1.0 at slot1, exactly the title's register
  ratio.
- The bed is 3D low-frequency voices (v4/v5/v6, v15) through the HRTF, at about speech level, and +12 dB at slot2.
- Halo's own DSP program would play the bed +4.65 dB louder still.
- So A2 (`use_dsp`) is refuted in the direction that matters, and A1 (max-over-bins) is not this bug.

| | Hypothesis | P start | P now | Evidence / leg |
|---|---|---|---|---|
| H2 | The mix is the title's own; speech over music matches the registers | -- | 0.30 | REPORT 1.2; leg B |
| H1 (A3) | The L1-normalised HRIR plays the 3D bed louder than the guest's taps | 0.2 | 0.20 | leg L, N (HRTF_NORM=raw) |
| H3 | The dialogue stream starves in the slow shots (#1018) | -- | 0.12 | leg S (sslempty) |
| A2 | Halo's DSP mix restores the balance | 0.3 | 0.03 | the dsp_harness ran Halo's GP/EP: bed +4.65 dB further over |
| A1 | Max-over-bins | 0.5 | 0.03 | v65 is 2D mono in bins 0/1 |
| A4 | Volume conversion | low | 0.05 | the register ratio is reproduced exactly |

Speech legs: A = meter on (l1, the default); R = `HAKUX_APU_HRTF_NORM=raw`. Judge: `speechread.py` as committed in
a93db78057.

## What the next lane should not repeat

- Do not chase `TU_DEBUG=sysmem` or GPU-bound explanations for this cinematic: the cinesplit A/B refutes both.
- A dispatcher soak with `--pull 'frametrace_*'` brings back old CSVs from the device; read only the run's own
  (cineread.py `run_csvs()`).

## Questions (for the owner; nothing waits on them)

1. On a real Xbox, does the dialogue in the opening cinematic sit clearly over the low hum/engine bed, or is it close
   to it? The offline account says hakuX reproduces the title's own register ratios; your ear on hardware decides H2.
