[lane.halo1016] #1018 early arms judged: all six (halo1016-early.json; earlyread.py was committed before any arm ran). **With four switches on together, the hangar plateau holds the bar: 33.8 ms/f over [mark+131, mark+191], against 59.3 on the default build.**

| arm (all on `HAKUX_S2T_CVT=1`) | ms/f | spin share of TB time | |
|---|---|---|---|
| B (base) | 42.1 | 0.252 | |
| E (+ `HAKUX_REPORT_EARLY=1`) | 35.9 | 0.010 | 972289 of 972302 armed reports answered at queue |
| EIF (E + `HAKUX_FLDCW_CHAIN=1` + `HAKUX_IBC=1`) | **33.8** | 0.015 | every 10-s window from +100 to +210 is 33.4-34.7 |
| S (+ `HAKUX_REPORT_SUBMIT=2000`) | 38.4 | 0.114 | 4 finishes a frame; reports written 4-8 ms after queue instead of ~28 |
| EV / BV (E / B with frames) | 35.1 / 41.9 | 0.006 / 0.246 | 0.838, repeats E/B's 0.852 |

The legs:
- HIT: EA, EP, XM, SQ.
- MISS: EM by 0.002 (0.852 against 0.85; the replicate pair gives 0.838); EG; XG by 0.4 ms (33.8 against 33.4); SM (0.912 against 0.90).
- The windows still over the bar are +127..+139, at 34-37 ms/f per 2 s. There the guest is busy (idle 0-3%), so the vCPU's remaining work is the bound.

**Root cause: three costs in series, each hidden by the one before it.** All three scale with the hangar shots' 900-1400 draws a frame:
1. 49 `cvt` surface downloads a frame, the #986 MKSM mechanism. `HAKUX_S2T_CVT` (fps1015): 59.3 -> 41.9.
2. The guest spins on ~544 visibility-test reports a frame. The async reader writes each one only after the frame's last finish and the GPU's run of it; the NV2A writes it as it reaches it. `HAKUX_REPORT_EARLY`: 42.1 -> 35.9.
3. The vCPU's own work: 36 k FLDCW block exits and ~900 k helper lookups a frame. `HAKUX_FLDCW_CHAIN` + `HAKUX_IBC` (#507): 35.9 -> 33.8.

Removing any one of them alone leaves the plateau above the bar.

**Pictures.** EV and BV show the same shots with every object present. The cinematic's animation advances per rendered frame, so stills taken at equal wall time are not the same content. They also cannot show REPORT_EARLY's one possible cost, a flare or corona one frame late at a camera cut. That needs frames captured every frame across a cut.

X1 BOX 1.2.9's reports.c is upstream xemu's synchronous path, so there is nothing there to port. `HAKUX_REPORT_SUBMIT` and `HAKUX_REPORT_CATCHUP` lose and stay off.

**To ship in 0.5.2:** all four switches are off by default. They need one by-mechanism default-on screen together: their counters, failure instruments and canaries are in docs/lanes/halo1016/NOTES.md, "What default-on needs". I am requesting it from lane.xbox. This lane's PR (lane/halo1016) carries the two new switches off by default, and it goes to ready now.
