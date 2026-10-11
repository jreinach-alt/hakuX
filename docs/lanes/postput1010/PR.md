postput1010: post the guest's DMA_PUT store when pfifo.lock is busy, behind HAKUX_POSTED_PUT=1 (#433, 0.5)
State: not ready (Addendum 1's full-switch pair waits on drawrec1010's fold; see WAITING)

Lane: postput1010       Issue: #433 (umbrella), none filed
Base: master @ 6052ff98d4 (merged in at b9b36d655c; reportasync1010 is folded). The A/B ran on c63ec9774f.
Files: hw/xbox/nv2a/user.c, hw/xbox/nv2a/nv2a_int.h, hw/xbox/nv2a/pfifo.c, docs/lanes/postput1010/**, docs/testing/predictions/postput1010-*.json
Prediction: docs/testing/predictions/postput1010-nfs.json @ 1987085cd7bf0642c4678302bef5b9b9f9157bad3d9a6a341b318fec7446d7a5 (race start, A/B/B/A, plain build, ref c63ec9774f): FAIL (P, T, G fail; C passes)
Prediction: docs/testing/predictions/postput1010-ftpair.json @ 45cb51e232b56881d4eb20f03dc5214f05db490463f6f8adea009865377849de (race-start frametrace pair, perflog, ref c63ec9774f): FAIL (L, Q fail on A's side: the wait is not on this base)
Prediction: docs/testing/predictions/postput1010-nfsall.json (Addendum 1, full-switch base): not yet registered; it needs HAKUX_DRAWREC on master
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

## Pending: Addendum 1's full-switch pair

The pair is A2' = REPORT_ASYNC + TEXSCAN + DRAWREC + UNI_BULK/UBERCACHE/FOGCACHE, B2' = A2' + POSTED_PUT,
checks P2/F2/C2/H2. `HAKUX_DRAWREC` is only on lane/drawrec1010 until it folds, so `WAITING` says `fold drawrec1010`.
`ppread.py` already judges those legs (NOTES.md 4.6). The prior, stated before the runs, is low (~10 % for P2 and
C2): at this base the guest is idle once freed, and DRAWREC shortens the PFIFO thread's lock hold too.

Recommendation (provisional, pending the full-switch pair): **drop**, unless P2/F2/C2 pass. The switch is posted on
12-32 % of kicks and moves nothing at the scene it was built for. Default-on would also need a GPU-paced title
re-checked: The Simpsons Hit & Run in free roam, a plain A/B on fps. That is the title that lost 40.05 -> 36.22
with `c2dfca18a1`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
