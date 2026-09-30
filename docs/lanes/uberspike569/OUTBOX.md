# lane.uberspike569 outbox (offline; relayed by lane.local)

## #569 -- 2026-09-29 22:15 PDT

[lane.uberspike569] waiting: on the Nova, for the six device arms of the uber pre-raster build. GitHub is suspended, so PR #618 is now `docs/lanes/uberspike569/PR.md` on `lane/uberspike569-gpl` (`State: draft`).

The six were queued after #624 folded, and at 22:11 PDT all six are still in `dispatch/queue/`; none was lost this time. They cannot run yet. The Nova is on the owner's top-up hold, and the Thor has a dead fan and takes no queued runs. The soaks are hard-pinned to the Nova in any case.

| arm | ref | id |
|---|---|---|
| E A (ran 16:49) | 23543417aa | `1790724542-uberspike569-1360739` |
| E H | 6bec23c3f4 | `1790730667-uberspike569-2559646` |
| DOA A / B / H | 23543417aa / 752b4f0f7b / 6bec23c3f4 | `1790730667-uberspike569-2559714`, `1790730668-uberspike569-2559794`, `1790730669-uberspike569-2559870` |
| Kabuki A / B2 | 8b15159b2f / d0152f9c44 | `1790730670-uberspike569-2559946`, `1790730670-uberspike569-2560023` |

This resolves when all seven have result dirs. Then the lane judges E per capture, the DOA soaks with `uberjudge.py` and the Kabuki soaks with `kabjudge.py`, and writes the verdict (BUILD.md section 11).

## #569 -- 2026-09-30 08:50 PDT

[lane.uberspike569] All seven device arms of the uber pre-raster build ran on the Nova overnight and are judged (E A ran on the Thor). Verdict in `docs/lanes/uberspike569/BUILD.md` section 12; PR.md on `lane/uberspike569-gpl` is `State: ready`.

**The ladder (`HAKUX_GPL=3`) gives a first draw with no stall for every miss whose combination already has an uber library.**

| leg | A (GPL 0) | ladder | verdict |
|---|---|---|---|
| E, 36 suites, uber stage held | | 1317/1317 byte-identical, 2103 links | PASS |
| DOA draw-path create | 26.2 s | 2.7 s | PASS (0.10, bound 0.25) |
| DOA first fight load | 2.9 s | 52 ms | PASS |
| DOA stall windows | 25 | 5, all cold combinations | PASS |
| Kabuki fight create | 133 s | 27 ms | PASS |
| Kabuki longest flip gap | 5.0 s | 0.7 s | PASS |
| G: uber held on every draw, GPU ms / gfps | 18.8 / 45 | 70.9 / 13 | FAIL (3.8x, bound 1.5x) |

- **The cost is GPU time while the uber stage stands in.** Held, it is 3.8x per frame. That is an upper bound: the pipelines are fast-linked without LTO, and that link's own cost was never measured apart (gpl569 D1 was void).
- **In ladder use on a cold DOA cache,** the play span runs at 0.79x A's median fps. The dip lasts while new uber links outnumber swaps (about 90 s on the survey route), then fps recovers. A freezes instead.
- **The default stays 0.**

Next, ranked by expected impact:
1. One Nova arm with GPL mode 1 held (specialised libraries, no uber), against A. It separates the link cost from the interpreter cost and says which fix to build.
2. Persist the uber combinations and prebuild them at boot, which removes DOA's 14 cold creates.
3. `NoContraction` on both paths, with its own pixel arm.
4. The default flip for mode 3, on the owner's decision.

## #569 -- 2026-09-30 08:47 PDT

[lane.uberspike569] waiting: on the Nova, for the head smoke that `offline_fold.py` needs before it folds `lane/uberspike569-gpl`. The smoke is DOA, 150 s, GPL default 0, purpose "#569 head smoke at <head>". Thirteen study-tier requests are ahead of it. PR.md is `State: ready`, and the verdict above is final. This resolves when the smoke's result dir exists; the fold needs nothing else from the lane. Please do not commit to the branch before the fold, because a new head orphans the smoke.
