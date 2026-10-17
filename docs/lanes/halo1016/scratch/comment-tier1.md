[lane.halo1016] #1018 tier-1 arms judged (halo1016-tier1.json, tier1read.py as committed before either ran). Span [mark+131, mark+191], `HAKUX_S2T_CVT=1` in every arm, base 42.1 ms/f (mean of A and A2):

| arm | env | ms/f | x base | gi/f | spin share of TB time |
|---|---|---|---|---|---|
| A | -- | 42.6 | 1.012 | 8,005 | 0.267 |
| T | `HAKUX_TIER1_THRESHOLD=0` | 40.8 | 0.969 | 0 | 0.296 |
| IF | FLDCW_CHAIN + IBC | 39.2 | 0.932 | 28 | 0.441 |
| FIT | all three | 39.4 | 0.937 | 0 | 0.430 |

**Legs**

- **HIT:** N, TM. Every `gi` exit came from tier-1's CF_INVALID pinning.
- **MISS:** TE (0.969, bar 0.96), XS (FIT 1.005 x IF), XE, XG.

All three vCPU remedies remove their mechanism, but the span has a floor near 39 ms a frame that none of them moves. Split by spin share (TB time is ~96% of the vCPU's wall here):

| arm | vCPU work, ms/f | occlusion poll, ms/f |
|---|---|---|
| A | 31.2 | 11.4 |
| IF | 21.9 | 17.3 |

The work went down 9.3 ms/f and the poll went up 5.9. Whatever the poll waits on takes ~39 ms a frame in these shots. The RT/RC arms (1792230024, 1792230026) locate that wait.
