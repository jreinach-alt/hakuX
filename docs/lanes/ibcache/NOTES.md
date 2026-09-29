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

## State at 21:30Z, 2026-09-28: waiting on the pixel arm and R1b

- **The pixel arm** (`ibcache-probe-pixels.json`, A 4e3d69a69b, B a6ec5ec0ab)
  is committed on 911e7321a3. `[job.arms]` runs it and posts its verdict on
  PR #591.
- **R1b** is re-requested from lane.local on a6ec5ec0ab (#507
  issuecomment-5878932501, delivered), with
  OUT=/home/justin/hakux-work/perf/2026-09-28-ibcache-r1b. Read it with
  `symsplit.py`, `jitmix.py` and `counters.py` against legs 1-2.
- `preflight.sh --allow-tracker` passes on 911e7321a3.
- **Next, on resume:**
  - If both pass, queue leg 4 (title soaks on three titles) and leg 5 (GTA
    fps and J/frame, A/B), then mark the PR ready.
  - A moved capture or a failed share leg is a diagnosis. Read the probe's
    key against `tb_lookup()` first.

## Attempt 3 (resumed 2026-09-28, hostops addendum 14:36 PDT)

**Why attempt 2 did not finish.** It ended correctly on a `waiting:` for the
pixel arm and R1b, but the arm it waited on could never be queued:
`arms.sh list` skipped `ibcache-probe-pixels.json` with "no suite with goldens
in its keys or disc". A bare `"*"` in `must_not_move` names no suite, so the
arms job cannot derive a sweep, and lane.local's R1b waited on that pair
being claimed.

**Fix.** `must_not_move` is now one `<Suite>/*` key for each of the 100
suites with goldens, plus `disc.suites` listing the same suites. Both are
copied from lane.memfast's `memfast-drop-pixels.json`, along with its
`skip_tests` (`Texture_render_target::RenderTextureLoop`). The refs
(a 4e3d69a69b, b a6ec5ec0ab), the claim, and `expect_counts` (better 0,
worse 0) are unchanged. Master has not moved since the merge (0 behind), so
nothing was rebased.

Do not repeat: a prediction key has to name a suite. The arms job does not
expand `"*"`.

## State at 21:45Z, 2026-09-28: waiting on the pixel arm and R1b

- `bash docs/testing/jobs/arms.sh list` prints `WOULD QUEUE d357732ea1…
  lane/ibcache:…/ibcache-probe-pixels.json a=4e3d69a69b b=a6ec5ec0ab`
  with 100 suites. The PR body carries the new sha256.
- R1b (a6ec5ec0ab, lane.local, #507 issuecomment-5878932501) waits on
  the arms job claiming that pair.
- **Next, on resume:** unchanged from attempt 2. Read R1b against legs 1-2,
  and the `[job.arms]` verdict against the pixel leg. If both pass, queue
  legs 4-5 and mark the PR ready.

## Attempt 4 (resumed 2026-09-28 16:24 PDT, hostops addendum: both waits resolved)

**Why attempt 3 did not finish.** It ended on a `waiting:` for the pixel arm
and R1b, both outside the session. The arm was judged 90 minutes late: its
request ids were renamed when lane.local promoted the pair, and the arms job
no longer matched them (hostops fixed that at 16:25 PDT). R1b finished at
16:08 PDT. Nothing of this lane's was wrong or lost.

### The pixel arm (FAIL, 9 of 3381 checks): read as run-to-run noise, with the evidence

Verdict `arms/pairs/d357732ea1….verdict.txt`, A `…arms-ibcache-base-2313748`
(4e3d69a69b), B `…arms-ibcache-fix-2313775` (a6ec5ec0ab), one run per arm,
Thor. 3379 captures compared: **3369 byte-identical, 10 differing**. Eight are
in Stencil (REPLACE/ZERO with DT, ST, ZB) and two in
Vertex_shader_rounding_tests (`GeometrySuperscreen_0.5000`, `_0.9990`). Seven
changed score (4 better, 3 worse), and three held their score and moved bytes.

The addendum also names `Clear/SFC_X1R5G5B5_Z1R5G5B5`. It did not move: all 32
Clear captures are byte-identical. The name is in the verdict's explanatory
text (#59's example), not in its movers.

**The probe did run in arm B.** B's logcat has `[ibc507] on=1 layout=ok`, and
`[jc425] ih=0` in all 682 windows (A: non-zero in all 732): no helper lookup
hits the jump cache, because the inline probe takes every hit first. Over the
whole sweep `[rr425] hc` is 31,354 helper calls per second against A's
1,198,992 (-97.4%). So the 3369 identical captures are a measurement of the
probe, not of a switch that was off.

**Why the 10 are noise** (`noisecheck.py`, `out/noisecheck-pixels.out`; 51
other pgraph result dirs, 59 runs, none at a6ec5ec0ab):

| capture | B image drawn by builds without the probe | apks without the probe that drew both the A and the B image |
|---|---:|---:|
| Stencil_REPLACE_DT | 1 run | 1 |
| Stencil_REPLACE_ST_DT | 3 runs, 3 refs | 3 |
| Stencil_REPLACE_ST_DT_ZB | 9 runs, 6 refs | 3 |
| Stencil_ZERO_DT | 16 runs, 7 refs | 1 |
| Stencil_ZERO_ST | 2 runs, 2 refs | 1 |
| Stencil_ZERO_ST_DT | 5 runs, 5 refs | 2 |
| Stencil_ZERO_ST_DT_ZB | 8 runs, 6 refs | 3 |
| Stencil_ZERO_ST_ZB | 7 runs, 6 refs | 3 |
| GeometrySuperscreen_0.5000 | 4 runs, 4 refs | 2 |
| GeometrySuperscreen_0.9990 | 8 runs, 8 refs | 4 |

- Every B image is byte-identical to an image a build without the probe drew.
- For every one of the 10, at least one apk without the probe drew both this
  arm's A image and its B image in repeated runs. For example apk
  8d38739bc784 (rendermode474's base, 59d478911e) drew
  `Stencil_ZERO_ST_DT_ZB` as the A image 3 times and the B image twice.
- Stencil REPLACE/ZERO and GeometrySuperscreen captures are movers in 17
  other arms' verdicts under `arms/pairs/`, in both directions. rendermode474
  registered around "the run-to-run band flip474 measured (Stencil
  REPLACE/ZERO, Blend spot_0_ADD, GeometrySuperscreen)".
- The direction is not the probe's either: 4 better and 3 worse.

This is evidence for noise, not a measurement of the band in this pair. One
run per arm cannot give that. So the band is now a registered arm.

**Do not repeat:** a full-sweep `must_not_move` at one run per arm. These two
suites flip between runs of one binary, so that arm can fail whatever the
change. Register the flip band's suites at three runs per arm from the start.

### The band leg, registered on the merged refs

Master was merged first (2c950e0a1e, battadmit: harness files only). The head
is c8e95ed539, and `git diff a6ec5ec0ab c8e95ed539` is empty over accel/, tcg/,
target/, include/, hw/, ui/, audio/ and android/. So the full sweep's 3369
identical captures carry over to this head.

`docs/testing/predictions/ibcache-probe-band.json` (sha256 d7a7ddaa4c…):
- A 2c950e0a1e, B c8e95ed539, suites Stencil and
  Vertex_shader_rounding_tests, **three runs per arm**.
- Legs: no capture moves outside the band measured in the arms (better 0,
  worse 0), and no capture that is self-identical in each arm differs between
  them.
- What kills the change: a capture self-identical in A, self-identical in B,
  and different between them.
- What leaves the question open: neither arm flips in three runs. Then the
  band on this two-suite disc is unmeasured, and the noise reading rests on
  the table above.

### R1b, read: legs 1 and 2 PASS

Session `/home/justin/hakux-work/perf/2026-09-28-ibcache-r1b`: a6ec5ec0ab,
Thor, cold start (xo-therm 43.6 C, battery 34.0 C), regimen max, no
`thermal-pause`, focused, 427 s of device time, 21,911 vCPU samples. Outputs:
`out/sym-r1b.out`, `out/jitmix-r1b.out`, `out/counters-r1b.out`.

| leg | registered | R1 (master) | R1b (probe) | |
|---|---|---:|---:|---|
| 1 share: `lookup` bucket, of the vCPU thread | at most half of R1's (12.45%) | 24.9% | **7.3%** | PASS |
| 1 `helper_lookup_tb_ptr` self | at most a third of R1's (2.38%) | 7.15% | **0.83%** | PASS |
| 2 counter: `[rr425] hc` | down at least 70% | 5.27M/s | **0.39M/s (-92.6%)** | PASS |
| 2 `[ibc507]` | `on=1 layout=ok` | - | `on=1 layout=ok` | PASS |

What is left in the lookup bucket is the miss path: `qht_lookup_custom` 4.17%
(R1 4.39%), `tb_lookup_cmp` 1.51%, `helper_lookup_tb_ptr` 0.83%, `tb_lookup`
0.54%. Of the helper calls that remain, **97.9% are pc collisions** in the
jump cache (`ip`), 1.5% empty slots, 0.6% key mismatches.

`pw`: the battery supplied 3.83 W and the USB port 2.11 W (medians, 13
samples).

### Is it a net win? The share cannot say, so two more readings

The JIT share rose from 50.9% to 70.7%. Removing 17.6 points of lookup
renormalises 50.9 to 61.8, so about 9 points are new JIT time. That is either
the probe's inline cost or guest code that ran more. Two readings separate
them.

**1. The frame limiter's spin** (`spinshare.py`, `out/spinshare-r1-r1b.out`).
GTA SA caps itself at 30 fps by spinning on a word until the second vblank
(guest 0x273686 / 0x27368e; vcpuplan NOTES section 4, targets.toml). Time
spent there is time the frame did not need.

| profile window (rec-on, 25 s) | R1 (master) | R1b (probe) |
|---|---:|---:|
| samples in the limiter's spin, of the vCPU thread | 0.35% (75) | **8.42% (1845)** |
| gfps, median (`out/gfps-r1-r1b.out`) | 22.5 | **27.0** |

Under the profiler's load master was vCPU-bound below the cap and never
waited. The probe build reached the cap's neighbourhood and still had 8.4% of
the vCPU left over. `tbmap.py` prints `FAIL` on its "share of frequent deltas"
check in both sessions (76.9%, 77.0%). That is the known over-strict check
(gta482 NOTES:273); its known-answer check passes, 7 of 7.

**2. fps without the profiler** (the 67 s between the mark and `prof start`):
median 29.0 against 28.0, mean 27.6 against 27.4. **No difference.** Both
builds sit at the cap there, so fps cannot show a saving on this route. Guest
idle is under 0.7% in both over the last 75 windows
(`out/rrcmp-r1-r1b-75.out`): the guest spins, it does not halt.

This is one pair of captures taken two hours apart, not an A/B. It says the
saving is real where the title is vCPU-bound, and that on a capped scene it
goes into the guest's spin, where neither fps nor J/frame can see it.

### Leg 5, amended before any A/B run

Leg 5 as registered in attempt 2 (median fps up 5%, J/frame down 4%, on the
`gta` route) assumed GTA was below its cap on that route. R1 shows it is not:
29.0 fps median against a cap of 30. A rise of 5% is not available to any
change there, so the leg as written would fail whether the probe works or
not. It is replaced, before any A/B has run:

- **5a, GTA SA (capped on this route): no regression.** `gta-sa` route, Thor,
  one binary (c8e95ed539), `HAKUX_IBC=0` against unset, 430 s each. Over the
  window from the mark plus 10 s to the end: time-weighted fps with the probe
  is no lower than 0.5 fps under the arm without, and J/frame no higher than
  +3.6% (the Thor's J/frame spread over 5 Crimson runs, energymap507; GTA's
  own spread is not measured). The gain on this title is the spin share
  above, which a soak cannot see.
- **5b, a title below its cap: the original numbers stand.** Median fps up at
  least 5% and J/frame down at least 4%. Forza is the brief's title and waits
  on #583, which is still open. Crimson Skies (near-bound: vCPU share 0.94,
  guest idle 0.15) runs now on the same env A/B, and is reported as a
  near-bound title, not as a substitute for Forza.
- An env A/B has one binary, so arms.sh cannot queue it (it compares refs).
  These go through `request.sh`, as lane.idlehalt's did.

### The next lever, ranked: jump-cache collisions, then the RAS

| option | P | win | evidence |
|---|---:|---|---|
| A larger or 2-way jump cache (`TB_JMP_CACHE_BITS` is 12) | 0.6 | up to 5% of the vCPU | 97.9% of the 0.39M/s remaining helper calls are pc collisions, and they carry the 7.3% that is left. 4096 slots against 148,834 TBs in the buffer |
| Return-address stack | 0.3 | under 2% of the vCPU | A return that hits the jump cache already stays inline. The RAS would save only the returns that collide, which the larger cache also removes |

The larger cache costs a bigger wipe on every `tcg_flush_jmp_cache`. The JC
default already replaced most wipes with `CF_INVALID`, and `[jc425] ie` (empty
slots, 1.5%) bounds what wipes cost today. It is a second change with its own
legs, so it goes on a stacked branch (`lane/ibcache-jcsize`) after this PR's
legs are in, not into this head.

## State at 23:55Z, 2026-09-28: waiting on the band arm and the GTA pilot pair

- **The band arm** (`ibcache-probe-band.json`, A 2c950e0a1e, B c8e95ed539,
  three runs per arm) is committed on 1ecd644937. `arms.sh list` prints
  `WOULD QUEUE d7a7ddaa4c… suites=[Stencil,Vertex_shader_rounding_tests]`.
  `[job.arms]` posts its verdict on PR #591.
- **The GTA pilot pair** (leg 5a, and GTA for leg 4), queued with
  `request.sh`, Thor, c8e95ed539, `gta-sa` route, 450 s, `--perflog`:
  - A, probe off (`HAKUX_IBC=0`): `1-1790638705-lane.ibcache-66240`
  - B, probe on (unset): `1-1790638712-lane.ibcache-67880`
  - That is 18 min of device time, inside the 30 min a requester has before a
    reviewed pilot. About 30 requests were ahead of it in the queue, and the
    Thor was under a hold.
- `preflight.sh --allow-tracker` passes on 1ecd644937.
- **Next, on resume:**
  1. Read the band arm's verdict against the three outcomes named above.
  2. Read the pilot pair with `title_verdict.py` on copies of the result
     dirs, and `gfps.py`: both reach the `gameplay` mark, no crash or hang,
     fps and J/frame against leg 5a. Check `[ibc507] on=0` in A's logcat and
     `on=1` in B's, or the pair measured nothing.
  3. Write the pilot's verdict to `$DISPATCH_DIR/pilots/lane.ibcache.ok`
     (with `python3`), then queue the rest: the GTA pair again in the order
     B, A; Crimson Skies (`crimson-skies`, 240 s) and Otogi (`otogi`, 240 s)
     as env pairs, for leg 4's three titles and leg 5b's near-bound title.
  4. Forza (leg 5b as the brief names it) waits on #583.
  5. Then the jump-cache size, on `lane/ibcache-jcsize`.

## Attempt 5 (resumed 2026-09-29, handback)

**Why attempt 4 did not finish.** It ended on a `waiting:` for the band arm
and the GTA pilot pair, both outside the session. That was correct. Both have
landed since: the band arm's result dirs exist, but `[job.arms]` has not
posted a verdict on them yet. The pilot pair finished at 04:13 device time.

### The band arm, read by hand (`bandread.py`, `out/bandread.out`)

A `1-1790639762-arms-ibcache-base-184395` (2c950e0a1e, no probe), B
`1-1790639763-arms-ibcache-fix-184418` (c8e95ed539, probe), Thor, three runs
per arm, 67 captures each, none missing.

| reading | count |
|---|---:|
| captures that flip between runs **inside A (master, no probe)** | 5 |
| captures that flip between runs inside B | 2 |
| captures whose image sets differ between A and B | 4 (Stencil_ZERO, Stencil_ZERO_DT, GeometrySuperscreen_0.0010, _0.4999) |
| **self-identical in each arm and different between them (the kill outcome)** | **0** |

All four captures that differ between the arms are ones A itself flipped in
three runs. In each of them, B's image is also one of A's images, except one
of B's Stencil_ZERO_DT runs. That capture flips inside B too. None of the 10
captures that moved in the full-sweep FAIL differs between the arms here. They
are self-identical in both arms and match between them. So the band reading
holds: the pgraph movers are run-to-run noise that master shows on its own.
The official verdict is `[job.arms]`'s on PR #591. It supersedes the `regressed`
label only if it PASSes.

### The GTA pilot pair: void, both arms paused at the same point

`1-1790638705-lane.ibcache-66240` (A, `HAKUX_IBC=0`, logcat `[ibc507] on=0`)
and `1-1790638712-lane.ibcache-67880` (B, unset, `on=1 layout=ok`). Thor,
c8e95ed539, 450 s. Both reach `mark gameplay`, and neither has a crash.
`title_verdict.py` (`out/tv-pilot.out`) voids both: `thermal-pause-F8` began
74 s after the mark in both arms. It flags `hang=True` in both, and that comes
from the pause, not from the probe.

The 64 s before the pause (`gfps.py`, `out/gfps-pilot.out`) give gfps medians
of 26.0 (A) and 28.0 (B). **That is not a leg-5a reading.** It is one pair.
A cleared the shader cache and B kept it, and the registered window is from
the mark plus 10 s to the end. Recorded only.

**Do not repeat:** a warm 450 s GTA soak on the Thor. The route reaches
gameplay at about +210 s and the pause comes at +291 s. Leg 5a needs a cold
start, as R1 and R1b had, so it went to lane.local (#507
issuecomment-5893447927, `out/coldslot-5a-request.md`).

### Leg 4 and 5b, queued (pilot verdict in `pilots/lane.ibcache.ok`)

Otogi's route reaches gameplay only at about +246 s, which is too close to the
pause. So the three titles for leg 4 are GTA (the pilot above: gameplay, no
crash in B), Crimson Skies (gameplay at about +105 s, the near-bound title for
leg 5b), and Alien Hominid (about +101 s). Each soak is 240 s, so it ends
before +291 s. They are env pairs on c8e95ed539, pinned to the Thor, with the
probe arm queued first so a title's first-run shader compiles land against the
probe (`queue_leg4.sh`, `out/queue_leg4.out`):

| title | B (probe on) | A (`HAKUX_IBC=0`) |
|---|---|---|
| Crimson Skies | `1-1790696069-lane.ibcache-2131018` | `1-1790696070-lane.ibcache-2131529` |
| Alien Hominid | `1-1790696071-lane.ibcache-2131813` | `1-1790696071-lane.ibcache-2132071` |

### Master merged

Master is merged at this head. The only change it brought under accel/, tcg/
or target/ is `cputlb.c`'s `HAKUX_TCG68_RD` default (#548, the dirty-TLB
walk). That code does not invalidate the jump cache. The soaks above name
c8e95ed539, whose apk is already built.

## State at 15:40Z, 2026-09-29: waiting on three things outside this session

1. `[job.arms]`'s verdict on `ibcache-probe-band.json` (both result dirs are
   DONE). Leg 3b.
2. The four soak requests in the table above. Legs 4 and 5b.
3. lane.local's two cold GTA soaks (#507 issuecomment-5893447927). Leg 5a.

**Next, on resume:** read each against its leg with `title_verdict.py` on
copies and `gfps.py`. Check `[ibc507] on=` in every logcat. If legs 3b, 4 and
5a pass, mark the PR ready with the release note. 5b on Forza still waits on
#583, and the jump-cache size goes on `lane/ibcache-jcsize`.

## Attempt 6 (resumed 2026-09-29, lane.local addendum 12:10 PDT)

**Why attempt 5 did not finish.** It ended correctly on a `waiting:` for the
band arm, four Thor soaks and lane.local's cold GTA soaks. Two of those
resolved and one was withdrawn:
- the band arm PASSed (`[job.arms]`, 08:43 PDT, all 69 checks, PR #591), and
  the PR's label moved from `regressed` to `verified`. Leg 3 is done;
- the owner moved fps, J/frame and profile runs off the Thor at 11:20 PDT
  (15 of 66 Thor title runs paused thermally, 0 of 85 on the Nova). lane.local
  withdrew the four Thor soaks (Crimson `-2131018`/`-2131529`, Alien Hominid
  `-2131813`/`-2132071`) before they ran.

### Legs 4, 5a and 5b move to the Nova

- **5b, Crimson Skies:** queued on the Nova (`queue_leg4.sh`, now parameterised
  by device, length and arm order; `out/queue_crimson_nova.out`). c8e95ed539,
  360 s, `--perflog`, in the order B A A B, so each arm has two runs and
  neither arm always runs first:
  `1-1790708501-lane.ibcache-1378207` (B), `-1378258` (A),
  `1-1790708502-lane.ibcache-1378332` (A), `-1378456` (B). The request files
  read back `device: nova`. The Thor's 240 s cap existed only to end before
  its pause at +291 s, so it does not apply on the Nova.
- **4 and 5a, Alien Hominid and GTA SA:** these are Thor-only titles. Their
  Nova copies were requested at 12:10 PDT, and neither is in
  `hardware/titlepush/listing-nova.txt` yet. They are queued the same way when
  they land.
- **5a amended (device only, before any run):** the Nova replaces the Thor.
  The thresholds stand (probe-on fps no more than 0.5 under probe-off, J/frame
  no more than +3.6% over it). The cold start was there only to avoid the
  Thor's pause, so the cold-slot request to lane.local (#507
  issuecomment-5893447927) is withdrawn.
- Every logcat is still checked for `[ibc507] on=0` in A and `on=1` in B, or
  the pair measured nothing.

### Master merged

Merged at 4eab8867c6. Master brought the ubershader under hw/xbox/nv2a/pgraph
and nothing under accel/, tcg/, target/ or include/. The soaks still name
c8e95ed539, whose apk is built.

## State at 18:25Z, 2026-09-29: waiting on the Nova soaks and two title copies

1. The four Crimson requests above (legs 4 and 5b).
2. The Nova copies of Alien Hominid (5A440004) and GTA SA (54540082), then
   their env pairs (leg 4, and 5a on GTA).

**Next, on resume:** read the Crimson pairs with `title_verdict.py` on copies
and `gfps.py`, checking `[ibc507] on=` in each. Queue Alien Hominid and GTA on
the Nova with `queue_leg4.sh nova 360 BAAB ...` once
`listing-nova.txt` names them. When legs 4 and 5a pass, mark the PR ready with
the release note. 5b on Forza still waits on #583, and the jump-cache size
still goes on `lane/ibcache-jcsize`.

## Attempt 7 (resumed 2026-09-29 12:10 PDT, handback)

**Why attempt 6 did not finish.** It ended on a `waiting:` for the four
Crimson requests on the Nova and the Nova copies of Alien Hominid and GTA SA,
all outside the session. At 12:10 PDT one of the four had run. The other three
are still queued, and `listing-nova.txt` is not on master yet, so neither copy
has landed.

### Crimson on the Nova: the first run (A1)

`1-1790708501-lane.ibcache-1378258`, arm A (`HAKUX_IBC=0`), the Nova,
c8e95ed539, 360 s. It was backfilled ahead of its B partner, so it ran first.
Logcat `[ibc507] on=0 layout=ok`, and `mark gameplay` at +113 s.
`title_verdict.py`: 250.7 s of gameplay, fps_ok 0.941, no crash, no hang,
**J/frame 0.2448**, battery 5.19 W. The FAIL it prints is the 600 s screening
length, which is not a leg here. This row is kept for the pair read once B
runs.

### The next lever, sized offline: jump-cache collisions (`jcmodel.py`)

The model maps each live TB in the code-buffer dump to its vCPU samples
(tbmap.py's mapping), puts it in its slot under the softmmu hash at each
`TB_JMP_CACHE_BITS`, and counts misses with the independent-reference model
(`out/jcmodel-r1.out`, `out/jcmodel-r1b.out`):

| bits | array per vCPU | modelled misses, R1 | R1b | ratio to 12 bits (R1, R1b) |
|---:|---:|---:|---:|---|
| 12 (today) | 64 KB | 26.7% | 30.8% | 1.00, 1.00 |
| 14 | 256 KB | 9.7% | 14.6% | 0.36, 0.48 |
| 16 | 1 MB | 3.9% | 7.7% | 0.15, 0.25 |

The model's absolute is about 4x the measured pc-collision share (7.3% of
R1's lookups), because samples measure time in a TB, not how often the jump
cache is consulted for it. **Only the ratio is read.** Applied to the 7.3% of
the vCPU that the probe build still spends in lookup, 14 bits would save about
3.8-4.7 points and 16 bits about 5.5-6.2. From that, 16 bits pays for its host
cache footprint (1 MB of randomly probed slots, the size of a big core's L2)
and 14 bits does not have to. The flush cost is small at either size:
`[tlb68]` `jcus` is about 4 us per full wipe of 4096 slots at ~60 wipes/s
(0.02%), so 16x is about 0.4%.

The cache has to stay a compile-time constant. A runtime size would change
`tb_jmp_cache_clear_page()` in `cputlb.c`, which lane.memfast (PR #590) holds.
`tb-jmp-cache.h`'s constant reaches `cputlb.c` through its macros without an
edit there. So the two sizes are two refs, stacked on c8e95ed539 so that each
differs from the probe build by one constant, and each is compared on the Nova
against the Crimson B runs of c8e95ed539.

### The jcsize pilot, registered before it is queued

Branch `lane/ibcache-jcsize` (stacked, not yet a PR): **X a987e375db**
(`TB_JMP_CACHE_BITS` 14 under XBOX) and **Y 9808982fa7** (16), each one
constant away from c8e95ed539. `ccheck.py` compiles cpu-exec.c, cputlb.c,
translate-all.c and translate.c at both sizes with no new warnings. An offline
check of the hash at 12, 14 and 16 bits (200k random pcs) finds no pc whose
slot falls outside the `TB_JMP_PAGE_SIZE` block that
`tb_jmp_cache_clear_page()` wipes for its page. So TLB invalidation still
reaches every slot, and the probe's layout check follows the constant.

Pilot: Crimson Skies, the Nova, 360 s, `--perflog`, probe on (default), one run
each of X and Y. The comparison rows are the two B runs of c8e95ed539 (12 bits,
probe on) already queued on the same device. The readings cover the window
from `mark gameplay` + 10 s to the end:
- **Correctness gate:** `[ibc507] on=1 layout=ok` in both logcats, and no
  crash or hang (`title_verdict.py`). A `layout=MISMATCH` means the probe was
  off, and the run measures nothing.
- **Counter leg:** the median `[rr425] hc` per second, against the mean of
  the two 12-bit B runs. **X at most 0.7x, Y at most 0.5x.** The GTA model
  says 0.36-0.48 for X and 0.15-0.25 for Y. Crimson's pages are not GTA's,
  so the bars sit well above the model.
- **Kill:** neither size brings `hc` below 0.7x. Then the leftover lookups are
  not the page hash's collisions, and the lever is dropped.
- **Size choice (for the multi-run A/B that follows the pilot):** Y if it
  passes its bar and its J/frame is not above X's. Otherwise X. J/frame and
  fps at one run each are recorded, not gated.

Queued (`queue_jcsize.sh`, `out/queue_jcsize.out`; the request files read
back `device: nova`, no env):
- X, 14 bits: `1-1790709325-lane.ibcache-1530225`
- Y, 16 bits: `1-1790709326-lane.ibcache-1530486`

## State at 19:25Z, 2026-09-29: waiting on the Nova queue and two title copies

1. Crimson on c8e95ed539: B `1-1790708501-lane.ibcache-1378207`, A
   `1-1790708502-lane.ibcache-1378332`, B `-1378456` (legs 4 and 5b). A1 is
   read above.
2. The jcsize pilot, X `-1530225` and Y `-1530486`.
3. The Nova copies of Alien Hominid (5A440004) and GTA SA (54540082), then
   `queue_leg4.sh nova 360 BAAB ...` for each (leg 4, and 5a on GTA).

**Next, on resume:** read the Crimson pairs with `title_verdict.py` on copies
(`scratch/`, not /tmp) and check `[ibc507] on=` in each. Read the jcsize pilot
against its registered legs. If it passes, open the stacked PR from
`lane/ibcache-jcsize` (merge `lane/ibcache` into it first) and queue its
multi-run A/B. Mark #591 ready when legs 4 and 5a pass.
