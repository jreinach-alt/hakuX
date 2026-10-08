# Split issues for #747 and #746: drafts (not filed)

Filing needs the forge API. This session could not make that call (the
forge call needs an approval it did not get, and the forge data is outside
this worktree). Each draft below is a complete issue: title, parent, body.
Evidence rows are in `../evidence.tsv`; the reader is `../tools/run_waits.py`.

---

## 1. [#747] Star Wars III: gameplay is fence-bound at 36 render passes a frame; the median frame is 1.8 ms over the 30-fps deadline

Parent: #747. Run: `1791267038-hostops-measured-starwars3` (ref c3a0c70ace).

- Gameplay (from 04:07:23): frame wall median 35.07 ms (28.5 fps). `Tot` 30.8 ms per frame.
- `Fen` 9.8 ms per frame (the finish's fence wait). `Sub` 1.6. `GPU_R` 8.7 and `GPU_X` 1.9 by stamps (sd 0%, so not inflated; last-tile caveat applies).
- `RP` 36 render passes per frame.
- Vblanks per frame: 553 at 1, 6338 at 2, 1667 at 3, 20 at 4+. 20% of frames take 3+ vblanks.

Ask: an A/B on SW3 of (a) fence points per frame and (b) pass count per
frame. Hypotheses: async794's fence path (`c825e4b24f`, `2344ae1ee2`) and pass
merging. A win is a median frame under 33.3 ms.

Evidence: `evidence.tsv` rows E-SW3-1..4.

---

## 2. [#747] GTA SA: gameplay is guest-bound (renderer starved for frames); shader compile is a load-time cost, not a gameplay one

Parent: #747. Run: `1791272940-hostops-2038851-c3a0` (ref c3a0c70ace).

- Gameplay (from 00:53:29): frame wall 33.79 ms (29.6 fps). `Tot` 29.0. `IdleFr` 10.0 and `IdleSt` 7.35 ms per frame, i.e. the renderer waits for the guest.
- Vblanks per frame: 584 at 1, 7782 at 2, 1134 at 3. 12% of frames take 3 vblanks.
- Shader compile (`dpc` sum): 7,945 ms over the run, 38 ms in gameplay. One load-time window carries 3,279 ms.
- One gameplay stall, 513.8 ms at 00:55:15.848, with no shader or pipeline work (dpc 0, dsm 0).

Ask: (a) the vCPU work behind `IdleFr`, using the vCPU plan's candidates; (b) the 513.8 ms stall, through a frametrace record over that frame; (c) load-time compiles, through shaderprebuild569.

Evidence: E-GTA-1..5.

---

## 3. [#747] Tron 2.0: three gameplay stalls, 744 / 530 / 1063 ms; two have no shader work

Parent: #747. Run: `1791267037-hostops-measured-tron` (ref c3a0c70ace).

- Gameplay (from 03:57:27): frame wall median 18.35 ms (54.5 fps). `IdleFr` 6.35 of `Tot` 15.0.
- Stalls: 04:00:00.545 at 743.9 ms (dpc 0); 04:00:02.149 at 530.2 ms (dpc 0); 04:01:39.709 at 1062.8 ms (dpc 188.1, dsm 49).
- At 04:01:39.709 the window's phases cover 2.6 s of 7.3 s. TLB fills 190,994 per 2 s window (51.9 ms of returned fills). Code-page block discards 8,342.
- None of these counters sums to 1 s.

Ask: a frametrace record over frame 21240 (and frames 15960 and 16020), so the unaccounted ~800 ms is named. Then a fix for what it names. The verdict also fails Tron on duration (326 s of 600 s).

Evidence: E-TRN-1..5.

---

## 4. [#746] D&D Heroes: gameplay is submit-bound (vkQueueSubmit blocks 38.6 ms a frame); the GPU time behind it is unverified

Parent: #746. Run: `1791272941-hostops-2039487-c3a0` (ref c3a0c70ace).

- Gameplay (from 04:55:39): frame wall 79.94 ms (12.5 fps). `Tot` 74.4. `Sub` 38.6 (CPU clock), `Fen` 3.7, `Draw` 15.7, `Pipe` 10.6.
- Vblanks: 3214 of 3420 frames take 4+ vblanks (94%).
- `GPU_R` 41.3 ms by stamps. 17.6% of D&D's finishes are `sd` (non-deferred PFIFO finishes), so the stamps are in the pre-5c35880d0a over-count. The run's ref does not contain 5c35880d0a.

Ask: one D&D perflog run on a build with 5c35880d0a (lane.local's device queue). That settles whether the GPU is busy ~41 ms a frame (then render-pass cost is the lever) or whether the submit wait has another cause.

Evidence: E-DND-1..3, E-DND-5.

---

## 5. [#746] D&D Heroes: CPU shader bind is 8.1 ms a frame (not compile)

Parent: #746. Run: as §4.

- `Pipe.Sh` (pipe_bind_shd) 8.1 ms per frame in gameplay (about 11% of `Tot`).
- Gameplay shader compile sums: dpc 11 ms, dgl 10 ms, dsnu 11 ms over 57 windows. So the 8.1 ms is CPU bind work, not a compile.

Ask: read the bind path (`pipe_bind_shd_ns` in `hw/xbox/nv2a/pgraph/`) for the work it does per draw. No device time.

Evidence: E-DND-2, E-DND-4.
