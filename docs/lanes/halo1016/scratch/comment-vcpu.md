[lane.halo1016] #1018 vCPU arms judged (halo1016-vcpu.json, vcpuread.py as committed before any arm ran). Over the span [mark+131, mark+191], with `HAKUX_S2T_CVT=1` in every arm:

| arm | env | ms/f | x base (42.1) | what it removed |
|---|---|---|---|---|
| A | -- | 42.6 | 1.012 | -- |
| A2 | -- | 41.6 | 0.988 | -- |
| F | `HAKUX_FLDCW_CHAIN=1` | 40.5 | 0.963 | FLDCW returns at 0x1ec3a: 36 k a frame to 0 |
| I | `HAKUX_IBC=1` | 40.5 | 0.962 | helper lookups: 863 k a frame to 13.6 k |
| IF | both | 39.2 | 0.932 | both |

**Legs**

- **HIT:** N (A/A2 spread 0.023), FL (0 precision flips in 106 M FLDCWs), FM, IM.
- **MISS:** FE, IE, BE, G.

Both mechanisms are removed in full, but the frame gains only 2-3 ms. The cause is that the heavy shots' two hottest blocks are one loop:
- 0x63482 calls D3D 0x1810f0;
- 0x1810f0 returns 0x88760828 at 0x18111b while a visibility-test record's status word is still -1.

The guest is polling an occlusion result. The poll takes 27% of A's sampled translated-code time and 44% of IF's, so the vCPU time the remedies saved went into polling longer.

**Next arms (halo1016-reports.json, on 7da5534b6b; queued 1792230024 and 1792230026)**

- **RT** traces each report from queued to handed-off to written (`HAKUX_REPORT_TRACE=1`). That separates three places the wait can be:
  - the FIFO's backlog before it reaches the report (P 0.5);
  - a queued report waiting for a finish (P 0.25);
  - the GPU and fence (P 0.15).
- **RC** adds `HAKUX_REPORT_CATCHUP=1` (new, off by default), which writes a queued report at the caught-up FIFO.

The tier-1 arms T and FIT (halo1016-tier1.json) run first. A2's `gi` count was 174 a frame against A's 8 k, which suggests tier-1 pinning varies from run to run.
