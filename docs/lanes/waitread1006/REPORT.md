# What each slow title is waiting on (#433, 0.5): report

Offline read of data already on disk. No device time, no requests, no holds.
Evidence rows are in `evidence.tsv` (one row per figure, with its source file
and the tool that reads it). The four measured runs are the 10-05/06 Nova runs
on ref `c3a0c70ace`, apk `c2186cc33daa`, env `PERF_REGIMEN=default
HAKUX_FRAMETRACE=1`.

Figures are ms per frame, medians over the gameplay windows, unless marked.
"Gameplay" starts at the first `route-frames/*-gameplay.png` of each run (the
verdict's own window). Pre-gameplay load and menu windows are excluded from the
gameplay rows and reported separately.

## 0. Corrections to the brief's inputs

| brief said | on disk | consequence |
|---|---|---|
| GTA SA "74.6% play share" | `fps_ok_share` 0.746 (`verdict.json`). That is the share of 1-s windows at or above 30 fps. It is not a play share | the rows below use fps_ok |
| D&D "0%" | `fps_ok_share` 0.0; gameplay wall 79.9 ms (12.5 fps) | as stated |
| Tron "92%" with a "1.06 s hitch" | `fps_ok_share` 0.9199; worst frame 1062.8 ms at 04:01:39.709 (`logcat.txt:39104`) | as stated |
| SW3 "47%" | `fps_ok_share` 0.474 | as stated |
| SW3 "96% at 10-02" | not on disk. The closest 10-02 measurement is the titleroutes survey `1790921690-titleroutes-1082096` at ref `7a090b6fa2`, apk `81768b9f7ed2`, env `[]`: `fps_ok_share` 0.8766, window median 30.0 (`docs/lanes/titleroutes/OUTBOX.md:790`) | §3 uses 87.7% |
| #839-#846 family rows | no dispatch result on disk for NHL 2K3, NFS MW, LOTR RotK or Hulk on 10-06. Spider-Man 2 and Midnight Club II have only gpunonrender's 10-06 runs (`docs/lanes/gpunonrender/NOTES.md`). The issue bodies are on the forge and this session cannot read them | §1 lists these as gaps, not rows |
| Castlevania 1.43 s and #851 1.01 s all-idle stalls | not found on disk. The 10-06 result dirs contain no Castlevania run | §1 lists them as gaps |

## 1. Titles grouped by the named wait (gameplay windows)

| named wait | title | measured figure (gameplay) | source |
|---|---|---|---|
| **Submit back-pressure (CPU blocked in `vkQueueSubmit`)** | D&D Heroes | `Sub` 38.6 of `Fin` 42.3 of `Tot` 74.4 ms/frame. 94% of frames take 4+ vblanks (3214 of 3420) | E-DND-1..3 |
| **Fence (sync/finish) wait, with the GPU nearly as busy** | Star Wars III | `Fen` 9.8 of `Tot` 30.8 ms/frame. `GPU_R` 8.7 + `GPU_X` 1.9 ms by stamps (`sd` 0% of finishes, so the stamps are not inflated; the last-tile caveat applies). 36 render passes per frame. The median frame is 35.1 ms, 1.8 ms over the 33.3 ms two-vblank deadline. 20% of frames take 3+ vblanks | E-SW3-1..4 |
| **Guest-CPU bound (renderer starved for frames)** | GTA SA | `IdleFr` 10.0 + `IdleSt` 7.35 of a 33.8 ms wall. `Draw` 6.5, `Pipe` 3.1, `Fin` 3.5. 81% of frames take 2 vblanks, 12% take 3 | E-GTA-1..3 |
| **Mostly guest-bound, with pipeline-create stalls** | Tron 2.0 | median wall 18.4 ms (54.5 fps), `IdleFr` 6.35 of `Tot` 15.0. Gameplay stalls: 743.9 ms (`dpc` 0), 530.2 ms (`dpc` 0), 1062.8 ms (`dpc` 188.1). See §2 | E-TRN-1..4 |
| **Shader compile, at load (not in gameplay)** | GTA SA | pre-gameplay `dpc` 7,907 ms over the run, one window 3,279 ms (`f=1500`). Gameplay `dpc` sum 38 ms | E-GTA-4 |
| **Pipeline shader-bind CPU (not a compile)** | D&D Heroes | `Pipe.Sh` 8.1 ms/frame. Gameplay `dgl`+`dsnu`+`dpc` sums are 11 ms in total, so this is not compile time | E-DND-4 |
| **Unexplained stall (vCPU-side candidates, see §2)** | GTA SA 513.8 ms (`00:55:15.848`, `dpc` 0); D&D 266 ms | `dsm` 0 in both windows | E-GTA-5, E-DND-5 |

Gaps: NHL 2K3 (#839), NFS MW (#843), LOTR RotK (#845), Hulk (#846): no
10-06 run on disk. Spider-Man 2 (#842) and MC2 (#844) have renderer numbers
from gpunonrender (`S1` `surfupd` 6.0 ms/frame; MC2 `range` 8.0 ms/frame, at
`docs/lanes/gpunonrender/NOTES.md`), not a 10-06 gameplay row. Castlevania
1.43 s and #851 1.01 s: not on disk.

## 2. The 1.06 s Tron stall, and the other two stalls

The stall is one frame in the window ending `04:01:39.709`
(`logcat.txt:39104` pace, `:39105` `[shd413]`, `:39106` phase).

| field | value | reading |
|---|---|---|
| `max` / `ms` | 1062.8 / 7310 ms for 60 frames (121.8 ms/frame average) | the window is 4.7 s slower than its accounted phases |
| `[shd413]` `dsm` / `dpc` / `dsnu` | 49 / 188.1 / 185.2 ms | 18% of the stall is pipeline creation. The verdict classifies the whole stall as "shader" (`classification`) |
| phase `Tot` (per frame, the window) | 43.0 ms. `Draw` 19.9, `Pipe.Sh` 8.5, `Fen` 8.0, `IdleFr` 9.2 | the renderer's accounted time is 2.6 s of 7.3 s |
| `tcg787` `w=236` (`:38763`) | 190,994 TLB fills per 2 s window (`tf`), 51.9 ms of returned fills (`tfus`), 0 `tbf` | TLB refill churn, but ~52 ms, which cannot make up 1 s |
| `hakuX-pages` (`:39101-39102`) | 8,342 blocks discarded by code-page writes in this window (`ev`=8343, `slow stores 9275`) | guest writes into code pages; the cost per discard is not timed in this line |

So the 1.06 s stall is not explained by any one counter here. Pipeline
creation accounts for 188 ms, the TLB churn for ~52 ms, and the rest (~800 ms)
has no counter that reads it. The two other gameplay stalls (744 ms and 530 ms)
have no shader or pipeline work at all (`dpc` 0, `dsm` 0-1).

**The #851 1.01 s all-idle stall and Castlevania's 1.43 s stall cannot be
compared here.** Neither is on disk, and "all-idle" needs the per-frame
`hakuX-stall`/`frametrace` record of the stall, which these runs have only in
`[hakuX-ft]` spans (`logcat.txt:39060-39082`, a different frame set).
What settles it: a frametrace record that covers frame 21240 in the Tron run,
or the same record on the #851 run.

## 3. SW3: why 96% (10-02) became 47% (10-06)

Measured on disk:
- 10-02 survey: `7a090b6fa2` → `fps_ok_share` 0.8766 (apk `81768b9f7ed2`, env `[]`).
- 10-06 measured: `c3a0c70ace` → `fps_ok_share` 0.474 (apk `c2186cc33daa`, env `PERF_REGIMEN=default HAKUX_FRAMETRACE=1`).

**Commit range:** `7a090b6fa2..c3a0c70ace` is 676 commits. 46 of them touch `hw/`, `accel/` or `android/`. The vCPU, PFIFO and pacing candidates in that range:

| commit | date | what it changed | fits SW3? |
|---|---|---|---|
| `012fa08a94` | 10-03 | `user_read` takes no `pfifo.lock` (DMA_PUT/GET/REF acquire loads) | a vCPU-side change; SW3's gameplay frames are renderer-fence bound, so only indirectly |
| `ddbc5f0173` | 10-03 | removes the XBOX load fast path (memfast) | the fast path was not active in gameplay per the memfast notes, so likely neutral |
| `c825e4b24f`, `2344ae1ee2` | 10-04 | async794: pgraph.lock released across SURFACE_DOWN waits; strip fix 2 | the renderer's `Fen` wait is this kind of wait. The strip fix was refuted on NBA |
| `1b8cb9326f` | 10-02 | ibcache probe default OFF | neutral by default |
| `76291926ff`, `537607f767`, `65bd51712b`, `f2763fe4c0` | 10-05 | frametrace instrument, default on in the 10-06 env | confound, not a cause: frametrace's own overhead read is 21-29 µs a frame (`docs/lanes/frametrace/NOTES.md:981`) |

**Read:** the 10-06 SW3 gameplay is renderer-fence bound (`Fen` 9.8 ms of a
30.8 ms `Tot`) with 36 render passes a frame. The first measured candidate is
the async794 fence change (`c825e4b24f`, `2344ae1ee2`), a 10-04 commit. It is
a hypothesis only. A per-frame render-pass and finish count from the 10-02 build
and the 10-06 build would separate it from the vCPU candidates, and an A/B of
`c825e4b24f^` against `c825e4b24f` on SW3 would test it. Neither is in this
lane's offline scope.

**What is missing:** no 10-02 SW3 perflog exists on disk (the survey had no
perflog build), so the 96% figure cannot be checked against a same-build run.

## 4. Fixes ranked by P × win

P is the probability the fix moves the named wait, from the evidence in §1-3.
Win is the title and ms it would move at full scale. Cost is what it takes to
know.

| # | fix or measurement | P | win (titles; ms/frame) | cost |
|---|---|---|---|---|
| 1 | SW3: cut the fence wait by about 2 ms a frame. The median frame sits 1.8 ms over the 30-fps deadline, and 20% of frames take 3 vblanks. Candidates: pass merging (36 passes a frame) or fewer fence points (the async794 path) | 0.4 | SW3 fps_ok 47% → up to ~90% (estimate: holding 30 fps needs ~2 ms, the fence wait is 9.8); 1.8-9.8 ms | one A/B on SW3 (fence count per frame, pass count); fix lane |
| 2 | D&D: decide the GPU truth before any render fix. `GPU_R` 41.3 ms ≈ `Sub` 38.6 ms, but 17.6% of D&D's finishes are `sd` (the stamp over-count, pre-5c35880d0a). A re-read on ≥5c35880d0a settles it | 0.9 that the re-read decides the lane | D&D: the decision for ~41 ms/frame | one perflog run of D&D on a build with 5c35880d0a (lane.local's) |
| 3 | D&D, if the GPU is busy: render-pass cost (GMEM replay, rendermode area) | 0.3 (P the GPU is busy, times P the fix works) | D&D needs Tot ≤ 33 ms, about −41 ms, to reach 30 fps. Not one of the cheap wins | the 5c35880d0a re-read first (row 2) |
| 4 | Shader prebuild for load-time compiles (the shaderprebuild569 lane) | 0.6 | removes ~7.9 s of GTA load `dpc` and up to 188 ms of Tron's 1.06 s stall. Gameplay fps: 0 for GTA | none new; the lane exists |
| 5 | GTA: the vCPU work behind `IdleFr` 10.0 ms and `IdleSt` 7.35 ms (guest-bound). The vCPU plan (memfast, ibcache, vcpuwait) | 0.3-0.4 for a 10%+ vCPU gain | GTA's 12% of 3-vblank frames; fps_ok 75% → 90% if the guest's ~17 ms is the binding path (estimate, not measured) | already dispatched; this lane adds no new cost |
| 6 | Tron's unexplained stalls (744, 530, and ~800 ms of the 1063): a frametrace record over the stall, then a fix on whatever it names. The known candidates are the code-page write storm (8,342 blocks discarded) and TLB churn (191k fills per 2 s) | 0.5 that the record names one of them | Tron: 3 gameplay stalls; hitch bar 500 ms; duration 326 s needs 600 s | one frametrace run of Tron (device; lane.local's) |
| 7 | D&D `Pipe.Sh` CPU shader bind, 8.1 ms/frame (~11% of `Tot`) | 0.4 | 8 ms/frame. D&D stays under 30 fps | read the bind path (`pipe_bind_shd_ns`); no device time |
| 8 | SW3 and GTA "frame-time" per title (the survey's six-title study) | 0.2 | not decided here | not started |

**Ranked:** 1 (highest P×win for a title currently near the bar), then 2 (it
decides 3), then 4 (cheap, certain, but load time, not fps), then 5, 6, 7, 3, 8.
Row 3 is only worth building if row 2 says the GPU is busy.

## 5. Notes on the instruments

- `Fen`, `Sub`, `Fr` and `St` are CPU-clock wall times. They are not affected by the GPU stamp over-count.
- `GPU_R` and `GPU_X` are GPU stamps. `sd` is 0% of finishes in GTA gameplay, 0% in SW3, 0.5% in Tron, and 17.6% in D&D (`tools/sd_share.py`). Only D&D's GPU rows need the re-read. In-pass stamps record only the last tile, so GMEM passes read as `GPU_R` low and `GPU_X` high.
- `Tot` is the sum of the CPU phases, not a GPU span. The `Tot × fps ≤ 1` check from the memory note does not apply to it, so D&D's `Tot` 74.4 at 12.5 fps (0.93 s/s) is a CPU figure, not a GPU one.
- `ms` in `hakuX-pace` is wall time for 60 frames. "Lost time" is not summed here, because a 30-fps title's frames would count as lost against 60 Hz.
- Percentages of frames at N vblanks are frame counts, not removable time.

## 6. Split issues (#747, #746)

Filing these needs the forge API, and this session's `curl` to 127.0.0.1:3330
needs an approval it did not get, and the forge data is outside this
worktree. The bodies are drafted in `issues/` (one file per proposed split
issue) and listed in OUTBOX.md as not filed. They should go under #747 (SW3,
GTA, Tron, the stalls) and #746 (D&D).
