# lane.jcache425 -- #425: fewer jump-cache flushes, and the lookup path

Base: master @ 9f34d60036. PR #443.

## Pilot (2026-09-26): the premise holds on the route, and only there

### Counters: the wipes on master, per soak (90-240 s from the first `hakuX-perf` line)

`[tlb68]` times each `tcg_flush_jmp_cache()` body (`jcus`) against the guest
thread's CPU time (`cpu`). Read with `perfsum.py` (this directory).

| run | device | route | ref | gfps med / p10 | G ms med / p90 | guest cpu/wall | wipes/s (`jci`) | wipe time / guest CPU |
|---|---|---|---|---|---|---|---|---|
| `1790455170-buildflags427-4117276` | nova | crimson-skies | `15d9406b81` | 29 / 27 | 33.5 / 39.2 | 0.901 | 53,168 | **8.90%** |
| `1790455170-buildflags427-4117310` | nova | crimson-skies | `6cd1a58b64` | 29 / 27 | 33.4 / 36.2 | 0.911 | 52,498 | **8.85%** |
| `1790454357-vcpuprime428-3938872` | thor | crimson-skies (`HAKUX_TOPO=200,10`) | `15d9406b81` | 29 / 24 | 33.7 / 39.8 | 0.893 | 50,647 | **8.75%** |
| `0-0-c-1790377875-lane.tcgchurn-101077` | thor | none (hands-off) | `ea1e9f5a0d` | 29 / 27 | 33.3 / 34.4 | 0.977 | 668 | 0.18% |

So lane.tcgchurn's "0.2-0.3%" and perfbase's "8.5%" are both right. They
measured different workloads. Without the route, Crimson discards about 80 times
fewer blocks. The route (sticks centred, level flight) is the workload this
issue is about. Each wipe costs 1.7 us (4,096 stores).

### Profile: the guest thread's lookup path, counted per sample

`price_lookup.py` over perfbase's two valid 09-26 Crimson heavy-flying
captures (Nova, `20a1a20eec`). The guest thread is the `qemu_main` tid with
the most samples: seven threads share that name, so a by-name count dilutes
every share by about half.

| share of the guest thread's samples | p1b (tid 3376, 19,814) | p2 (tid 17701, 19,613) |
|---|---|---|
| `tcg_flush_jmp_cache` | 6.73% | 6.76% |
| lookup path, total | 11.50% | 11.58% |
| ... entered from `helper_lookup_tb_ptr` (indirect branches) | 10.38% | 10.27% |
| ... entered from `cpu_exec_loop` (unchained exits) | 0.83% | 0.99% |
| ... entered from `tb_gen_code` (recycle probe) | 0.28% | 0.30% |
| of which `qht_lookup_custom` + `tb_lookup_cmp` + `tb_htable_lookup` (a jump-cache miss) | 6.40% | 6.42% |
| of which `helper_lookup_tb_ptr` self (the hit path) | 3.97% | 4.03% |
| lazy-flags helpers (`helper_cc_compute_*`, `helper_read_eflags`) | 0.23% | 0.27% |

`tcg_flush_jmp_cache` reads 6.7% here against perfbase's 8.5% for the same
files. The counters' 8.8% (a direct timing) is the number I use. The
difference is how the report is taken: this counts records of one tid, while
`simpleperf report` weights each record by its cpu-clock period.

## Pricing the owner's two inputs

- **Chaining lost vs genuinely indirect.** Direct jumps chain through
  `goto_tb` patches, and the jump cache does not hold those chains. A
  jump-cache wipe does not unchain anything. Unchaining happens in
  `tb_jmp_unlink` for the discarded block only. The exec loop's lookups (an
  exit that was not chained) are 0.8-1.0% of the thread. Indirect branches
  (`RET`, `JMP r/m`, `CALL r/m`, through `helper_lookup_tb_ptr`) are 10.3-10.4%.
  So **"aggressive block chaining" is worth at most about 1% here**. The
  lookup cost is indirect branches, and 6.4 of their 10.3 points are misses
  into the qht. The wipes empty the jump cache 50,000 times a second, so they
  should cause most of those misses. The `[jc425]` counters below split
  misses by cause to test that.
- **Native EFLAGS -> NZCV.** The lazy-flags helpers are 0.23-0.27% of the
  guest thread on Crimson. Flag work that TCG emits inline (cc_op
  materialisation in generated code) is in the JIT's `unknown` DSO and cannot
  be split out of the 28.5% of guest code by a profile. On Fuzion Frenzy's
  (menu) profile `helper_cc_compute_c` is 6.1-6.5% (perf-baseline), but that
  window is a spin loop. **Not a 0.5 lever on Crimson**, and not built.

## What was built, and what was not

- **The per-discard wipe fix already existed.** lane.tcgchurn wrote it as
  `HAKUX_TCG68_JC` in `tb_jmp_cache_inval_tb()` (tb-maint.c), argued it
  exact (NOTES there, "JC"), and the 09-25 audit (pass 1) found the argument
  holds for every reader. It shipped **default off** and was never measured:
  no dispatch result on disk has ever set it (`fx=...jc1` appears in no
  logcat). So this lane does not write a second one. It measures that one on
  the workload where it matters.
- **The inline probe the brief asks for already exists.** `tb_lookup()`
  (cpu-exec.c) reads the jump-cache slot before any qht lookup, from both
  the indirect-branch helper and the exec loop. No further probe is built
  until a counter says what misses. "Tune before a counter moves" is the
  rule, and the profile cannot tell a wiped slot from a collision.
- **Built: `[jc425]`**, one line every 2 s beside `[tlb68]` (`1b43be6b3a`,
  cpu-exec.c only). It counts each `tb_lookup()` probe per caller
  (`i` indirect helper, `l` exec loop, `a` atomic step) as a hit (`h`), or a
  miss by cause: empty slot (`e`, never filled or wiped), another pc in
  the slot (`p`, a collision), same pc but a discarded block (`s`, what
  JC=1 leaves behind), or same pc with another key (`k`). For each miss it
  also counts whether the qht found a block (`f`) or not (`n`). It also
  prints the JC switch state. Counters only, no control-flow change.
  Compiled for arm64 Android against the existing build tree's flags.

## Arms (queued 2026-09-26 ~22:10 UTC, 15:10 PDT)

One binary, `1b43be6b3a`. A: no env. B: `--env HAKUX_TCG68_JC=1`. The legs
are registered in `docs/testing/predictions/jcache425-crimson.json`
(`d7669c10`) and the pixel must-not-move in `jcache425-pixels-inert.json`
(master `9f34d60036` vs `1b43be6b3a`, 8 suites; the arms job queues it).

| arm | request id |
|---|---|
| A1 soak, JC off | `1790460549-lane.jcache425-232585` |
| B1 soak, JC=1 | `1790460549-lane.jcache425-232641` |
| A2 soak, JC off | `1790460549-lane.jcache425-232746` |
| B2 soak, JC=1 | `1790460550-lane.jcache425-232807` |
| pixels, JC off (8 suites) | `1790460551-lane.jcache425-232905` |
| pixels, JC=1 (8 suites) | `1790460551-lane.jcache425-232934` |

**After the verdict:** if F1, F2 and S1 hold and the pixel pairs are
identical, turning JC on by default is a one-line change in `cputlb.c`
(`hakux_tlb68_jc_on()`, e.g. treating unset as on). That file is not this
lane's. It goes to the host as a board request, to be sequenced with
lane.tbchurn424. If F2 is refuted (misses are mostly collisions), the next
lever is the jump cache's shape (`tb-jmp-cache.h`: size or a second way),
armed on its own.
