# lane.slowdown462 -- per-title frame-time attribution (#462)

Five slow titles, one protocol, one device (Nova ee317437, MAX). Measure and
attribute only; fixes go to the per-title lanes.

## The build and the instruments (same for every title)

- **Soaks:** ref `e5db66fa37` (master when this lane started), `--perflog`,
  survey route, 420 s, Nova, release priority (`HAKUX_RELEASE_PRIO=1`), MAX
  regimen (soak_title.sh's default; `perf_regimen.json` in each result).
- **Profiles:** `capture_profile.sh` (this dir), a held Nova session per title,
  APK `builds/a593d8eb85.apk` (not perflog). a593d8eb85 and e5db66fa37 build
  the same emulator: `git diff --stat a593d8eb85 e5db66fa37 -- ':!docs'` is
  empty. Asked of the host in `dispatch/board-requests/slowdown462.md`.
- **Window:** from the route's `mark play` + 30 s to 10 s before `soak end`.
  The survey route writes `mark play`, not `mark gameplay`; that the window is
  gameplay is checked from the route's `play` shots.
- **Readers:** `titleread.py <result-id>` runs, over that one window, the
  readers earlier lanes validated: aufire412's `splitread.py` (phase, cpu,
  work, stall medians), aufire412b's `pace.py` and `vbl.py` (VBLANKs per flip,
  VBLANK rate, clamps), tbchurn424's `churn.py` (#424 churn). Checked on
  `1790470425-aufire412b-4161655` (AUF, 53a9b91df3 perflog, MAX): it
  reproduces aufire412b's mission numbers (15.0 fps, Vpf 3.82, vCPU 86%).
- `waitres.py`: bounded wait on result ids, printing queue position and holds.

## What is already known, and what it does not answer

| title | prior evidence | open |
|---|---|---|
| DOA1U | doa413 (dc38b745b8, default regimen): fight 14-15 fps, `Surf` 33-52 of 55-67 ms, GPU 31-44 ms. doa413b's lazy-surface cut refuted (14.9 off vs 13.6 on) and ships default-off (PR #440, must-not-move PASS). | which part of `surface_update`: `xemu-surf` is not in the dispatcher's LOGCAT_SPEC |
| AUF | aufire412b: vCPU 54% in `cpu_exec_loop` (37% at one barrier), 26% guest JIT; renderer `Surf` 26.5, Draw 16.7, GPU 29.3 ms (1790470425, MAX) | the return causes (retreason425 in queue) |
| Blinx | blinx372d/c: attract demo, Sub 25-35 ms of 57-71 (synchronous zeta downloads); gameplay not read | gameplay split |
| Blinx 2 | nothing | everything |
| Forza | forza414 (Thor): race `Sub` 26-37 of 43-63 ms, ~5.5 uncoalesced `sd_complete_def` finishes/frame | Nova numbers; which caller |

## Windows: pick them from the frames, not from `mark play`

The pilot (DOA1U) showed that the survey route's `mark play` can fall AFTER the
gameplay: DOA fights during the 14 menu rounds (from about the 8th `press
START`, ~87-91 s after `mark booted`, in all three DOA runs) and by `mark play`
is on the replay, CONTINUE and title screens. `timeline.py <result-id>` prints
every 60-frame phase line with the route events; each title's window is picked
from it and checked against the route's shots. AUF's mission does start after
`mark play` (aufire412b's reading holds).

## DOA1U (54430006, #413)

**Soak** `1-1790481863-slowdown462-3154279` (e5db66fa37 perflog, apk
c4b30cf46bd6, Nova, MAX restored), fight window 151-288 s after logcat line 1
(PDT 21:20:31-21:22:47; shots 212038-212205 show stage 1 with the route's
START toggling the pause menu over it; the fight costs the same paused or not).

| | ms/frame | share of 75.8 ms |
|---|---|---|
| fps (gfps cadence) | 13.19 | |
| PFIFO Tot (renderer, never idle: Idle 0.1) | 70.8 | 93% |
| `Surf` (`pgraph_vk_surface_update`, exclusive timer) | 59.8 | 79% |
| Draw (Pipe 3.1, Sh 2.1, Syn 2.0) | 9.0 | 12% |
| Fin (Sub 0.1 / Fen 1.5) | 1.6 | 2% |
| GPU (Rnd 19.4, Xfr 19.3; 9 render passes) | 38.3 | 51%, overlapped |
| vCPU busy (`[tlb68]`) | 25% | not the bound |

Render-pass breaks 541/60 flips, 420 of them for a surface reason (7 per
frame); draws 729/frame. VBLANK 17.1 Hz with 1786 clamps: the timer is
starved while the PFIFO is busy (doa413 saw 21-25 Hz). #424 churn 1.8%.

**Profile** `perf/2026-09-26-slowdown462/doa2/doa2.data` (apk a593d8eb85, not
perflog, fight 21:57:58-21:58:29 PDT, 11-19 fps, shot 215809 = fight under the
pause menu). Session #1 (`doa/`) missed the fight and is not used.

- **The fight is not CPU-bound on any thread.** 30 s of cpu-clock: vCPU (tid
  12202) 8,048 ms on-CPU (27%), PFIFO (tid 12213) 6,875 ms (23%). The perflog
  line says the PFIFO thread is never idle and 60 ms of its 71 are in
  `surface_update`. So most of `Surf` is **blocked time** inside
  `surface_update`, not work. What it blocks on needs an off-CPU capture
  (board request Ask 2; `OFFCPU=1`).
- PFIFO on-CPU, top self: `memcpy_opt` 25.5% (36% of it from
  `pgraph_vk_finish` at FLIP_STALL, 20% `pgraph_vk_snapshot_state` per draw
  pass, 12% `complete_staged_downloads` under `surface_update`, 10%
  `apply_uniform_updates`), `tlb_reset_dirty` 8.3% (95% from
  `sync_vertex_ram_buffer` -> `tlb_reset_dirty_range_all`),
  `rewrite_indices` 4.9%. Under `pgraph_vk_surface_update` inclusive: 4.7% of
  on-CPU (~0.3 ms of CPU per 1000/15 ms frame against 60 ms of `Surf` wall).
- vCPU on-CPU: 40% guest JIT, `cpu_exec_loop` 12%, TB lookup (`tb_lookup`,
  `helper_lookup_tb_ptr`, qht) ~22%.
- doa413b's lazy-surface cut (PR #440) was refuted on this fight (14.9 fps
  off vs 13.6 on) and ships default-off. That fits: it cut work inside
  `surface_update`, and the time there is a wait.

## Log

- 2026-09-26 21:04 PDT: pilot queued, DOA1U, `1-1790481863-slowdown462-3154279`,
  behind three titlebench soaks. Nova at 36%, on a 500 mA port.
