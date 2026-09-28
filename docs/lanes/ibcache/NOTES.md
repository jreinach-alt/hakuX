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

Requested from lane.local on #507 (issuecomment-5878355210), 20:54Z;
OUT=/home/justin/hakux-work/perf/2026-09-28-ibcache-r1.

## The change (built while R1 waits): an inline jump-cache probe

Commit 27554f7145. At the one `lookup_and_goto_ptr` site in the x86 front
end (`gen_eob`, `DISAS_JUMP`: RET, JMP/CALL r/m, a direct jump to another
page), `gen_ibc_probe()` emits `tb_lookup()`'s hit test as TCG IR before the
helper call. A hit does `goto_ptr tb->tc.ptr`, and a miss falls through to the
unchanged `helper_lookup_tb_ptr`.

- **Why the existing jump cache, not a new table.** The probe reads
  `cpu->tb_jmp_cache` with the same hash, and compares the same key
  (pc, cs_base, flags, cflags) against the same fields. So it inherits every
  invalidation `tb_lookup` already honours: a wiped slot (tlb flush,
  `tcg_flush_jmp_cache`, `tb_flush`) is empty, and a discarded TB left in a
  slot by the JC default carries `CF_INVALID`, which fails the cflags compare.
  A new table would need its own invalidation hooks in tb-maint.c and
  cputlb.c, the correctness risk the brief's first leg is about.
- **Every key field is read at run time.** eip and the CS base come from
  their TCG globals, flags are rebuilt as `x86_get_tb_cpu_state()` builds them
  from `env->hflags`/`env->eflags`, and cflags come from `cpu->tcg_cflags`.
  None of them is assumed to be the source TB's. (This TB's own cflags can
  carry `CF_TIER1`/`CF_SUPERBLOCK` while it is translated, and the stored TBs
  have them stripped.)
- **Left to the helper:**
  - breakpoints and gdb single-step, checked at run time;
  - 64-bit code (`HF_CS64`);
  - TBs made with a count, `CF_NO_GOTO_TB`/`CF_NO_GOTO_PTR`/`CF_SINGLE_STEP`, or `-d exec,cpu,nochain`, decided at translate time.
- **Known gap, host-debug only.** Turning `one-insn-per-tb` or `-d nochain` on at run time
  from the monitor is not seen by probes already translated. Android has no
  monitor. Guest exceptions and interrupts are unaffected: the probe can
  neither fault nor skip the target TB's own exit check.
- **Not touched:** `tcg/aarch64/tcg-target.c.inc`. The probe is generic IR,
  so lane.memfast has that file to itself. The one new primitive is
  `tcg_gen_goto_ptr()` in `tcg/tcg-op.c`.
- **Switch:** `HAKUX_IBC`. Unset or `1` is on, `0` is off, and `2` is on
  with a hit counter (`[ibc507] hits=` at the `[jc425]` cadence). One
  `[ibc507] on=… layout=ok` line at the first translation. `hakux_ibc_enabled()`
  checks the probe's hash formula against `tb_jmp_cache_hash_func()` and
  refuses on a mismatch.
- **Checked by compiling:** `ccheck.py` compiles the three files with the
  NDK command lines of the host's last Android build. No new warnings.

### Return-address stack: not built. Ranked below the probe, and why

The probe already serves RET: a return target is a TB start that sits in the
jump cache after its first execution. A RAS would save only the hash and the
key compares on a return (about 10 of the probe's host instructions; ~35 in all, counted from the
IR, not from emitted code), and
it needs its own invalidation. By probability times win it comes after the
probe's measured hit rate. If the B profile shows returns missing the jump
cache (`[jc425]` `ip` collisions on returns), that is the evidence for it.

## Legs, registered 2026-09-28 before any run of 27554f7145

1. **Share (profile; R1b).** The same session as R1, on 27554f7145 (a debug
   build, default switch). The `lookup` bucket share of the vCPU thread is
   **at most half of R1's**, and `helper_lookup_tb_ptr` self time is at most
   a third of R1's. The void rules are R1's.
2. **Counter (the same R1b logcat).** `[rr425]` `hc` (helper calls) per
   second of the vCPU is **down at least 70%** against R1's, and the
   `[ibc507]` line reads `on=1 layout=ok`.
3. **Pixels (pgraph, registered with `ab_compare.py --register` only after
   R1 is go).** The full sweep, all 100 golden suites, `must_not_move` every
   suite: every capture identical between master and B. The probe changes
   only how the next TB is found, never which TB runs.
4. **Title soaks.** At least three titles reach gameplay, with no new crash
   or hang against their last master soak.
5. **J/frame and fps.** GTA, and Forza after #583. Registered with the pixel
   leg once R1b gives the share.

## State at 21:10Z, 2026-09-28: waiting on R1 and R1b

- R1 (master) and R1b (5a018cd42c) were asked of lane.local on #507
  (issuecomment-5878355210 and -5878537162). A lane cannot run
  `capture_gta.sh`: it drives adb under a hold, and `request.sh` has no
  simpleperf/code-buffer mode.
- `preflight.sh --allow-tracker` passes on 5a018cd42c.
- **Next, on resume:** read R1 with `symsplit.py`/`jitmix.py` from PR #589's
  `docs/lanes/vcpuplan/`, post the go or no-go on #507, and share OUT with
  lane.memfast. If go: read R1b against legs 1-2, then register the pixel
  leg with `ab_compare.py --register` (a_ref be05285c44, b_ref the probe's
  head) and commit it, which queues the arm.

## Attempt 2 (resumed 2026-09-28, after R1 landed)

**Why attempt 1 did not finish.** It ended on a `waiting:` for R1 and R1b,
which only lane.local could run (a held Thor, `capture_gta.sh`, a cold start).
That was the right place to stop. R1 landed at 21:20Z (PR #591 comment), and
the handback resumed this lane. R1b has not been run yet.

### R1, read: GO

Session `/home/justin/hakux-work/perf/2026-09-28-ibcache-r1`: master
01e62d8d1c (JC default on), Thor, cold start (xo-therm 49.9 C, battery 36.0 C),
no `thermal-pause`, focused. Outputs: `out/sym-r1.out` (`symsplit.py`),
`out/jitmix-r1.out` (`jitmix.py`), `out/counters-r1.out` (`counters.py`, new here).

| reading (vCPU tid 19768, 21,168 samples) | share of thread |
|---|---:|
| **lookup bucket (the gate: >= 8.0% is go)** | **24.9%** |
| hit path: `tb_lookup` 10.81, `helper_lookup_tb_ptr` 7.15, `tb_lookup_cmp` 1.55, `x86_get_tb_cpu_state` 0.85 | 20.4% |
| miss path: `qht_lookup_custom` | 4.4% |
| JIT (the TCG code buffer) | 50.9% |
| softmmu helpers | 7.0% |
| scalar SSE helpers | 5.2% |

**Go: 24.9% is three times the threshold, and higher than the plan's 17-20%
estimate for master.** The JC default did not shrink the lookup, because the
hit path is the cost, not the QHT. That is the part an inline probe removes.

Jump-cache counters over the profile window (`[jc425]`, last 40 windows, 81 s):
5.19M helper lookups/s, **92.5% hits**, 6.4% PC collisions, 1.1% empty slots,
and 0.04% key mismatches. `[rr425]` `hc` is 5.27M/s. So the probe can take
about 92% of those calls off the helper. The remaining 7.5% go to the QHT, and
PC collisions are most of them. A larger or 2-way jump cache is the lever for
that 4.4%, after the probe.

`pw` (13 samples in the hold): the battery supplied 3.49 W and the 500 mA USB
port 2.13 W (medians).

For lane.memfast (`jitmix-r1.out`, at-ip by role, share of the disassembled
JIT samples): tlb 34.4%, preamble 14.3%, body 45.5%. The XBOX preamble was
armed 0 times and off 43 times.

### The pixel leg: registered

`docs/testing/predictions/ibcache-probe-pixels.json`: a_ref master 4e3d69a69b,
b_ref a6ec5ec0ab (the probe merged onto that master). The full sweep: every
capture must not move, and better = 0 and worse = 0. Committing it queues the
arm.

### Leg 5 (J/frame and fps): the numbers, registered now

The share leg (1) and counter leg (2) above stand as written, measured against
R1's 24.9% and `hc` 5.27M/s. Leg 5, on the `gta` survey route (Thor) and on
Forza after #583, with the same regimen in both arms:
- **median fps up by at least 5%;**
- **J/frame down by at least 4%.**

Why these numbers: the hit path is 20.4% of a vCPU-bound thread. The probe
keeps about a quarter of that cost inline, a hash plus compares of about 35
host instructions. GTA's guest idle share is <= 0.06 (energymap507), so the
vCPU time saved shows up as frames.

Not repeating: the RAS stays unbuilt (see above). The probe covers RET, and
the jump cache already hits 92.5% of lookups.
