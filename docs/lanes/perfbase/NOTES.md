# lane.perfbase NOTES

Brief: a fresh guest-thread performance baseline at master on the Nova, and a
`hakuX-pace` line with exact late-frame counts (#68 context). PR #310.

## The `hakuX-pace` line (format proposed to lane.titlerun on #307)

`hw/xbox/nv2a/pgraph/profile.c`, logcat tag `hakuX-pace`, INFO, one line per
60 flips, printed right after the unchanged `hakuX-perf` line:

```
f=<frame_count> v0=<n> v1=<n> v2=<n> v3=<n> v4=<n> vb=<n> max=<ms .1f> ms=<ms .1f>
```

| field | meaning |
|---|---|
| `f` | `g_nv2a_stats.frame_count` at the end of the window (a multiple of 60) |
| `vK` | flips in the window that consumed exactly K VBLANKs; `v4` is 4 or more |
| `vb` | total VBLANKs in the window (mean VBLANKs per flip = vb/60) |
| `max` | longest flip-to-flip interval in the window, ms |
| `ms` | the window's wall time, ms; window fps = 60 / (ms / 1000) |

- `v0` is included (a flip with no VBLANK since the previous flip) so that
  v0+...+v4 == 60 always holds.
- Late flips for a title with nominal N VBLANKs per flip (1 at 60 fps, 2 at
  30 fps) = sum of vK for K > N.
- Parse by key, not position. New fields go on the end.
- The first line of each process is not a steady-state window: the first
  VBLANK delta is taken from zero and the first flip has no predecessor.
  `pace_check.py` drops it.
- The counts are exact per flip; `Vpf` and `G` on the `hakuX-perf` line are
  EMAs of the same quantities.

A soak queued through `request.sh --title` does **not** collect this tag
today: `soak_title.sh`'s and `dispatcher.sh`'s `LOGCAT_SPEC` list
`hakuX-perf` and `hakuX-pages` but not `hakuX-pace`. Both files are
lane.titlerun's (#307), which reads the line, so the ask is on #307.
`perf/run_perf.sh` (hand runs) collects it.

## Prediction

`docs/testing/predictions/perfbase-pace.json`, sha256
`b3f01aa17d887fcd80164866a4c686c9dd101e477fd93ef25e914e3a7430c5b8`, a_ref
724a0dd868 (master), b_ref 5c50884181. Judge:
`python3 docs/testing/perf/pace_check.py <log> --nominal 2 --judge`
(`--selftest` checks that each leg fails on its own broken fixture; P3 has no
mutant fixture).

The brief's third leg compared the late-frame share with `Vpf`. Those are
different quantities (a fraction of flips against a mean VBLANK count), so
the leg was registered on the commensurable one, vb/60 against Vpf, and it
is not independent: Vpf is an EMA of the same per-flip count. P4 is the leg
with two independent sources (VBLANK timer count against the flip clock).

## Tooling changes

- `run_perf.sh`: `OUT=` output dir; collects `hakuX-pace`, `hakuX-pages`,
  `hakuX-build` with threadtime; refuses to run if `validation_layers` is on;
  saves the prefs before/as-run to `$OUT/<tag>-prefs-{before,run}.xml` and
  restores the before file on exit, checked by read-back.
- `profile_guest.sh`: `GAME`, `MASH`, `BOOT_S`, `SETTLE_S`, `TAG`, `OUT`;
  records the prefs it ran under and refuses validation layers.
- `bench_ff.sh`: calls the `run_perf.sh` beside it, not the copy in
  `~/hakux-work/perf`.

## Device log

(prefs per run, raw logs under `/home/justin/hakux-work/perf/2026-09-26/`)

## Do not repeat

- lane.tcgchurn (#309) owns `accel/tcg/cputlb.c` and `target/i386/tcg/**`
  and is adding the full-TLB-flush trigger counters; this lane answers "from
  which path" with simpleperf call graphs, not with a second counter.
