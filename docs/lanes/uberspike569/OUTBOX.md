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
