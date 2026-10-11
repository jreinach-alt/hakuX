postput1010: post the guest's DMA_PUT store when pfifo.lock is busy, behind HAKUX_POSTED_PUT=1 (#433, 0.5)
State: not ready (all runs read; waiting on drawrec1010's fold, then one merge of origin/master, then ready; see WAITING)

Lane: postput1010       Issue: #433 (umbrella), none filed
Base: master @ 6052ff98d4 (merged in at b9b36d655c; reportasync1010 is folded), + origin/lane/drawrec1010 @ f3d0e45979 merged at 772429156c (Addendum 2; not folded yet). The first A/B ran on c63ec9774f, the full-switch pair on 772429156c.
Files: hw/xbox/nv2a/user.c, hw/xbox/nv2a/nv2a_int.h, hw/xbox/nv2a/pfifo.c, docs/lanes/postput1010/**, docs/testing/predictions/postput1010-*.json
Prediction: docs/testing/predictions/postput1010-nfs.json @ 1987085cd7bf0642c4678302bef5b9b9f9157bad3d9a6a341b318fec7446d7a5 (race start, A/B/B/A, plain build, ref c63ec9774f): FAIL (P, T, G fail; C passes)
Prediction: docs/testing/predictions/postput1010-ftpair.json @ 45cb51e232b56881d4eb20f03dc5214f05db490463f6f8adea009865377849de (race-start frametrace pair, perflog, ref c63ec9774f): FAIL (L, Q fail on A's side: the wait is not on this base)
Prediction: docs/testing/predictions/postput1010-nfsall.json @ 5b11550a770622fbe27bbc6fafae1ea6791d88891d749baa7858185ca57b5df7 (Addendum 1, full-switch base, A2'/B2'/B2'/A2', plain, ref 772429156c): FAIL (P2, H2 fail; F2 passes but A passes too; C2 passes, -2.17 ms)
Needs device: yes (Nova, used)
Needs NDK: yes

Release note (none): opt-in switch, off by default.

Step 2b of docs/lanes/nfs30plan1010/PLAN.md. `HAKUX_POSTED_PUT=1` re-arms lane.vcpusleep's posted store
(`c2dfca18a1`, reverted in `f6ac723228`) as a runtime switch. When pfifo.lock is busy, the guest's DMA_PUT store is
posted, the way the hardware posts it, and the lock is taken only to wake a parked PFIFO thread. With the switch off,
`user_write`, the pusher and the PFIFO thread's wait run master's statements. NOTES.md section 2.1 explains how every
wakeup is kept. `selftest_postput.sh` passes with the switch on and off, and each of its five mutants goes red,
including one per barrier.

## Result: at NFS's race start the posted store does not move the period

Pace, plain build, A = `HAKUX_REPORT_ASYNC=1 HAKUX_TEXSCAN=1`, B = A + `HAKUX_POSTED_PUT=1`, A/B/B/A, ms per frame,
each arm the mean of its runs:

| | A1 `…1949730` | B2 `…2642454` | B1 `…1954673` | A2 `…2643101` | A | B | B - A | check |
|---|---|---|---|---|---|---|---|---|
| warm countdown | 33.90 | 34.0 | 33.99 | 34.0 | 33.96 | 34.01 | **+0.06** | P <= -2.0 FAIL; T B <= 34.0 FAIL |
| post-GO warm | 33.50 | 33.5 | 33.49 | 33.5 | 33.49 | 33.51 | **+0.02** | G <= -1.5 FAIL |
| cold start 1 | 41.4 | 41.1 | 41.5 | 40.1 | 40.77 | 41.28 | +0.52 | C <= +3.0 PASS |

(Run ids `1-1791680038-postput1010-1949730`, `1-1791682037-postput1010-2642454`,
`1-1791680039-postput1010-1954673`, `1-1791682038-postput1010-2643101`.) Every run has 12 of 12 valid starts and
a moving car in all of its `s*-g11` frames. B posts 12-16 % of the countdown's kicks.

Frametrace pair (perflog; A `1-1791682044-postput1010-2647298`, B `1-1791682045-postput1010-2647896`), warm
countdown, all frames, ms per frame:

| | reportasync1010 trace (`…3857196`, a21a3361d9) | A | B |
|---|---|---|---|
| period | 44.81 | 39.77 | 39.49 |
| PFIFO `p_run` / `pidle` | 27.08 / 13.56 | 27.03 / 10.72 | 27.00 / 10.60 |
| GPU busy | 18.85 | 12.81 | 12.81 |
| guest `lockw` | 6.27 | **1.85** | **1.09** |
| guest idle | 11.9 | 13.1 | 13.9 |
| guest busy past 2 VBLANKs | 46 % | 9 % | 6 % |
| v2/v3/v4+ | 41/55/3 % | 63/35/1 % | 63/35/1 % |

Where the 7.3 ms went:
- **Most of it was gone before this change.** The only emulator difference between the trace the brief cites and
  this lane's base is NFS's sysmem row in `kTitleRenderModes` (`81ab5f3418`, gpupass1010). Between the two traces,
  GPU busy fell 6.0 ms, the guest's lock wait fell 6.27 -> 1.85 ms, and plain pace fell 37.5 -> 34.0 ms. The guest
  had been waiting for the lock while the PFIFO thread held it across GPU fence waits.
- **The posted store removes what was left only partly** (warm 1.85 -> 1.09, cold 5.36 -> 2.29). The guest
  spends what it saves idle (+0.8 ms warm, +3.0 cold).
- **The PFIFO thread sets the period.** Its `p_run` is unchanged (27.0 warm, 33.0-33.4 cold). Cold, its busy time
  is past 2 VBLANKs on 74-80 % of frames in both arms. Warm, the plain countdown is 0.5 ms over the 33.5 ms
  vblank floor.

So a recorder thread or anything else that cuts the PFIFO thread's own cold work is the lever. On this base the
warm countdown is near the floor. P fails, so the pixel leg is not run. NOTES.md sections 4.3-4.5 have the full
tables.

## Addendum 1's full-switch pair: warm unchanged, cold start 1 -2.2 ms on two starts per arm

A2' = REPORT_ASYNC + TEXSCAN + DRAWREC + UNI_BULK/UBERCACHE/FOGCACHE, B2' = A2' + POSTED_PUT, plain, ref
772429156c (origin/lane/drawrec1010 merged in, per Addendum 2), ms per frame, each arm the mean of its runs:

| | A2'a `…3732954` | B2'a `…3733954` | B2'b `…3736342` | A2'c `…417368` | A2' | B2' | B2' - A2' | check |
|---|---|---|---|---|---|---|---|---|
| warm countdown | 33.7 | 33.6 | 33.6 | 33.8 | 33.76 | 33.59 | **-0.18** | P2 <= -0.5 FAIL; F2 B <= 33.8 PASS (A passes too) |
| post-GO warm | 33.4 | 33.4 | 33.4 | 33.4 | 33.4 | 33.4 | 0.0 | |
| cold start 1 | 38.1 | 35.8 | 34.9 | 36.9 | 37.49 | 35.32 | **-2.17** | C2 <= -2.0 PASS |
| warm v2 share | 77 % | 73 % | 75 % | 78 % | 77.4 % | 73.9 % | -3.5 points | H2 >= +10 FAIL |

(Run ids `1-1791685180-postput1010-3732954`, `1-1791685199-postput1010-3733954`,
`1-1791685200-postput1010-3736342`, `1-1791687762-postput1010-417368`.) Each run has 12 of 12 valid starts and
a moving car in all of its g11 frames. A fifth run, A2'b `1-1791685202-postput1010-3737568`, is void. A pad.sh
hang (rc 124, adb stalling) at the boot's save prompt sent the blind route into career mode, and its g11 frames
show menus and a parked BMW. `ppread.py`'s V now fails a run whose boot inputs failed. A2'c replaced it.
`route.sh` still carries on after a failed boot input. Ending the run VOID at that point is a harness guard for
lane.local (NOTES 4.9).

C2 passes by 0.17 ms. Both B2' cold starts fall below both A2' cold starts. That ranking happens 1 time in 6 by
chance, and it rests on one cold start per run. Warm, both arms sit 0.1-0.3 ms over the 33.5 ms floor, and the
store moves nothing.

## Verdicts and recommendation

| prediction | verdict |
|---|---|
| `postput1010-nfs.json` (REPORT_ASYNC + TEXSCAN) | FAIL: P +0.06, T 34.01, G +0.02 (C passes) |
| `postput1010-ftpair.json` (same, frametrace) | FAIL: L, Q fail on A's side; the lock wait was not on this base |
| `postput1010-nfsall.json` (all six switches) | FAIL: P2 -0.18, H2 -3.5 points (F2 passes, uninformative; C2 passes, -2.17) |

**Recommendation: keep opt-in.** The store passes only a narrow cold-start leg on the full-switch base. Before
default-on, two checks, neither run here: (1) a GPU-paced title, The Simpsons Hit & Run in free roam, a plain fps
A/B with the store, because it lost 40.05 -> 36.22 fps with `c2dfca18a1`; (2) NFS race start 1 measured cold,
several boots per arm, on the full-switch base, to put a size on C2. The pixel leg (brief step 5) was gated on P
and is not run.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
