# lane.ibcache (#507): inline indirect-branch cache and return-address stack

Plan rank 2 of lane.vcpuplan (PR #589, `docs/lanes/vcpuplan/NOTES.md`).
Base: master @ be05285c44.

## R1: the go/no-go, registered before the run (2026-09-28)

The run: GTA SA on master, Thor, cold start (xo-therm <= 50 C), the `gta`
alley route as gta482 s4, `capture_gta.sh` (on-CPU simpleperf of the vCPU
plus the code-buffer dump), read with `symsplit.py` and `jitmix.py`
(both on PR #589, `docs/lanes/vcpuplan/`).

**Registered threshold.** The reading is `symsplit.py`'s `lookup` bucket as a
share of the vCPU thread's on-CPU samples (the bucket that read 22.8% on
a593d8eb85: `tb_lookup`, `helper_lookup_tb_ptr`, `qht_lookup_custom`,
`tb_lookup_cmp`, `x86_get_tb_cpu_state`).

- **Go:** lookup >= 8.0% of the vCPU thread.
- **No-go:** lookup < 8.0%. Rank 2 is demoted below rank 5 (the plan's rule),
  and this lane stops with the reading.
- **Void:** the run paused thermally (`thermal-pause` in the log, or fps
  5-7x down), the display was not focused, or fewer than 10,000 vCPU
  samples. A void run is re-run, not read.

Recorded alongside, not gating: the split of the lookup bucket into the hit
path (`tb_lookup`, `helper_lookup_tb_ptr`, `tb_lookup_cmp`,
`x86_get_tb_cpu_state`) and the miss path (`qht_lookup_custom`), because the
inline cache removes the first and the JC default already cut the second;
`jitmix.py`'s `tlb` and `preamble` roles (lane.memfast ranks 1 and 3); `pw`
from the perflog.
