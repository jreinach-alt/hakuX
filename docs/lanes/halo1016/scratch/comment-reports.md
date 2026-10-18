[lane.halo1016] #1018 reports arms judged (halo1016-reports.json, reportread.py as committed before either ran). **Both arms are VOID on V.** The prediction required the synchronous report path, but the app's "Fast renderer paths" default sets `HAKUX_REPORT_ASYNC=1`. Every arm here, and the owner's play, runs the async reader. That was my mistake in writing the leg. The traces still read cleanly, descriptively, over [mark+131, mark+191]:

| arm | ms/f | reports/f | armed | queued -> handed off >= 2 ms | queued -> written >= 16.7 ms | spin share of TB time |
|---|---|---|---|---|---|---|
| RT (trace) | 43.1 | 544 | 100% | 100% | 77% | 0.290 |
| RC (+ `HAKUX_REPORT_CATCHUP=1`) | 42.0 | 542 | 100% | 100% | 78% | 0.313 |

**Where the poll waits.** Every visibility test Halo issues in these shots arrives armed, with status word -1. Each one waits in two stages:
1. For the frame's last finish: queued -> handed off p25/p50/p75 = 9.1 / 12.6 / 15.6 ms.
2. For the GPU to run that whole command buffer: queued -> written = 19.4 / 28.4 / 36.4 ms.

The guest reads each result about a frame after issuing it, and spins in 0x63482 until the write lands. On the NV2A the result is written when the GPU reaches the method, long before then. The catch-up finish never fired (0 a frame) because the FIFO is never empty with a report queued.

**Next arms (halo1016-early.json, on 08fd920b5c; earlyread.py written before any ran).** Two new switches, both off by default:
- `HAKUX_REPORT_EARLY=1` answers an armed report when it is queued, using the count its offset was last written with. This is RPCS3's "relaxed ZCULL sync" trade: a result one test stale.
- `HAKUX_REPORT_SUBMIT=2000` finishes at a report so the GPU starts earlier.

The arms are B, E, EIF (E + FLDCW_CHAIN + IBC), S, and EV/BV with pictures. Request ids are 1792231792 to 1792231797.
