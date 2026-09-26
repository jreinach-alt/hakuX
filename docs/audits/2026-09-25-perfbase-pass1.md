# Audit pass 1: PR #310, lane/perfbase (#68)

Auditor: job.cloud, 2026-09-25.  Head audited: `16d9fbefaa`.  Read against
`origin/master...HEAD`, which is exactly the ten files on the PR's `Files:`
line: `hw/xbox/nv2a/pgraph/profile.c` (+27), `docs/testing/perf/`
`run_perf.sh`, `profile_guest.sh`, `bench_ff.sh`, `pace_check.py`,
`profile_report.py`, the two predictions, the lane NOTES and
`docs/investigations/perf-baseline-2026-09.md`.

**Result: no HIGH, no MEDIUM, seven LOW.**  Next label: `needs-audit-2`.

## What the diff does, checked

- **`profile.c`: the counters.** `pace_vb[MIN(n, 4)]` and `pace_vsum` are
  updated in the same block that computes `n`, the VBLANKs since the last
  flip.  `n` is unsigned, so the huge first-flip delta lands in `v4` and
  cannot index out of bounds.  `pace_max_us` and `pace_span_us` are updated
  inside `if (prev_flip_us)`, next to the existing `game_frame_*` stats.  The
  reset runs on the same `frame_count % 60 == 0` test as the print, after it.
  `frame_count` goes up once per call at `profile.c:236`, so each window is
  exactly 60 calls.  The reset sits outside `#ifdef __ANDROID__`: on desktop
  the statics are written and cleared but never printed.  That is harmless,
  and `MIN`, `MAX` and `memset` reach the file through `nv2a_int.h`.  Both CI
  build jobs are green on this head.
- **`profile.c`: the existing line is untouched.** The `hakuX-perf` print and
  `nv2a_profile_get_pacing_str` are not edited, which is the prediction's
  `must_not_move`.  The format arguments are `%u` for three `unsigned int`
  counters and `%.1f` for `int64_t / 1000.0` (a double).
- **Per-flip cost.** A handful of integer ops per flip and one extra
  `__android_log_print` per 60 flips.  That is below anything the pace line
  itself can resolve.
- **A second caller.** `pgraph.c:2318` calls `nv2a_profile_flip_stall` from
  `FLIP_INCREMENT_WRITE` when a diag capture is pending.  That double-counts
  one flip into the window, as it already does for every other stat there.
  It is diag-only and not new, so it is not a finding.
- **The judge reproduces.** `pace_check.py --selftest`: 5 of 5 cases ok.
  `--nominal 2 --judge` on `crimson-r1.log` and `crimson-r2.log` in
  `/home/justin/hakux-work/perf/2026-09-26/` gives PASS on every leg, with the
  exact figures in the PR table (P3 0.2% / 0.6%, P5 3.0% / 2.5%).  The
  late-flip counts, v-histograms and window percentages in the investigation
  doc's Crimson, Fuzion Frenzy and Galleon tables all sum and divide
  correctly.
- **Source citations.** `CF_PCREL` is set at `target/i386/cpu.c:9325`,
  `tb_jmp_cache_inval_tb`'s `CF_PCREL` branch flushes the whole cache of every
  CPU (`tb-maint.c:1292-1299`), and `do_tb_phys_invalidate` calls it
  unconditionally (`:1390`).  All three were read at `20a1a20eec`.
- **The 1.7 µs figure.** It is 71 ms/s divided by 43k discards/s, and the doc
  itself labels it a consistency argument, not a count.  That is correct.
- **Profile prefs.** `profile_guest.sh` writes no prefs, but the app's own
  `surface_scale` default is 1 (`xemu_android.cpp:908`).  So the profiles and
  the `run_perf.sh 1` runs ran at the same scale, and there is no mismatch.
- **The arms job.** Both predictions carry `title`, so `arms.sh:778-780`
  skips them as hand-read soaks.  Committing them queues nothing.
- **CI.** build x2 and check are green on this head, and the PR is MERGEABLE.

## Findings

### LOW 1: `run_perf.sh` collects `hakuX-build`, and it can never be in the log

`hakuX-build` prints once, at `frame_count == 1` (`profile.c:254`).
`run_perf.sh:108` runs `logcat -c` after boot and settle, just before
measuring, so that line is cleared before the collector at `:113` runs.
**0 of the 6 logs** in `perf/2026-09-26/` contain it.

**Failure scenario.** A reader checks a `run_perf.sh` log for build identity
and finds none.  The investigation's "apk built from `20a1a20eec`" is
therefore carried only by the lane's word, not by the log.  NOTES lists the
collection as a feature.

**Remediation (suggested).** Dump `-s hakuX-build` to `$OUT/${TAG}-build.txt`
before the second `logcat -c`, or drop the tag from the collector and say
where identity comes from.

### LOW 2: P3 has no failing fixture

The selftest has a mutant for P1, P2, P4 and P5, but not for P3.  NOTES says
so.

**Failure scenario.** A P3 comparison broken so that it always passes (for
example, `mvpf` read from the pace lines) would still pass the selftest.

The lane's own analysis makes P3 weak on stalls anyway.  Decide either to add
a `vpf` mutant or to log that P3 is left unfixtured.

### LOW 3: `pace_check.py` finds process boundaries only when `f` decreases, and has unguarded empty paths

- **Boundaries.** A restart is found only where `f` goes down.  If a process
  printed exactly one line (`f=60`), the next process's first line (`f=60`)
  is not detected as new.  It is scored as a step of 0, which is a P1 FAIL.
- **Empty paths.** If every window is excluded, or every `ms` is 0,
  `100.0 * sum(late) / (60 * n)` raises ZeroDivisionError.
  `statistics.median(fps)` raises StatisticsError the same way.

**Failure scenario.** Both are false FAILs or tracebacks, never a false PASS.
`run_perf.sh` clears logcat after boot, so a captured log rarely spans two
processes.  The failure is conservative, hence LOW.

### LOW 4: `profile_report.py` dies with a bare StopIteration

If no thread is named `qemu_main`, or `--tid` names a thread absent from the
split, the `next(...)` at `:123` or `:126` raises StopIteration.  Its
traceback does not say which of the two happened.

**Failure scenario.** A capture of a build that renamed the thread, or a
mistyped `--tid`, gives a traceback instead of "no qemu_main thread; pass
--tid".

### LOW 5: the PR body's "within 0.2%" is 0.33% on one run

The PR body claims that VBLANK total × period equals the summed wall time
"to within 0.2%" in all six runs.  Recomputed from the six logs with
16.667 ms, the whole-run ratios are 0.9967 to 0.9990: `galleon-r2` is 0.9967,
so 0.33% off.  Single windows range from 0.945 to 1.009.  NOTES states
0.9977-1.0000 against 16.683 ms, which is a different period from the one the
judge's P4 uses (`VBLANK_MS = 1000/60`).

**Failure scenario.** Someone uses 0.2% as a tolerance on a later title and
fails a healthy run.  Correct the body to the figure and the period actually
used.

### LOW 6: "up from the 35-40% read on 09-11" compares against an untraceable grouping

The investigation's summary (`perf-baseline-2026-09.md:28-30`) says the
40.4-40.9% maintenance share is "up from the 35-40% read on 09-11".  No
source for the 09-11 figure is cited in the repo or in #68.  The `tc-maint`
patterns are new in this PR, and they count about 11 points of lookup
(`qht_lookup_custom`, `helper_lookup_tb_ptr`, `tb_lookup_cmp`, `tb_tc_cmp`)
as maintenance.  The doc's own per-symbol table says "the whole list is
within the two-profile spread".

**Failure scenario.** lane.tcgchurn reads two things from this: that
maintenance regressed, and that about 40% of the thread is invalidation
bill.  Neither is shown: the rise may be the grouping, and 11.8 of the
40.4 points in p1b (29%) are lookup.  The doc hints at the lookup half
(item 3's "partly a consequence of item 2", and Galleon's "its maintenance
share is lookup").

**Remediation (suggested).** Cite the 09-11 source, or drop "up from".  State
the lookup sub-share next to the 40%.

### LOW 7: a failed prefs restore does not change the exit status, and the superseded prediction does not point forward

- **The restore.** `restore_prefs` prints `PREFS NOT RESTORED` but returns
  nothing.  An EXIT trap does not alter the script's status, so
  `perfbase_campaign.sh`, or any other wrapper, sees success.
- **The prediction.** `perfbase-pace.json` stays in the predictions
  directory with refs `724a0dd868`/`5c50884181` that were never run.  Only
  `perfbase-pace-2.json` names the relationship.

**Failure scenario.** A batch of runs leaves the device on the run prefs
while every step reports exit 0.  Separately, someone reading
`perfbase-pace.json` alone takes it for an outstanding, unjudged
registration.  Both are bounded: the log line is printed, and the arms job
skips title predictions.

## Decision needed for pass 2

No HIGH or MEDIUM, so nothing blocks the fold on severity.  AGENTS.md's loop
requires a logged decision on every LOW, either fixed or "reviewed, not fixed,
because X".  Pass 2 checks that each of LOW 1-7 has one.
