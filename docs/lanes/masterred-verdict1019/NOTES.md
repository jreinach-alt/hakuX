# masterred-verdict1019 (#433): two selftest fixes for the 10-19 11:14 master-red, and the jam-title misattribution

## What was actually red

`master-health.json` (host-side, `/home/justin/hakux-work/offline-git/`)
named the jam `master-red:99-verdict-10min.sh`. That is the LAST fragment
printed by shard 3/4 (which itself passed, 1117/1117) -- the two real
failures are in shards 1 and 2 of the same run
(`offline-git/fold-logs/master-health-20261019T1114-913e1524ff.log`):

- shard 1 (`SELFTEST_SHARD=0/4`) line 754: `FAIL case 2 (fallback)` in
  `88-usage-meterfit.sh`
- shard 2 (`SELFTEST_SHARD=1/4`) line 2927: `FAIL (c) a 1-* request 59s old
  does not yield yet (exit 0)` in `99-hold-tiers.sh`

## 1. `docs/testing/jobs/usage/meter.py` + `88-usage-meterfit.sh` -- the time bomb

`collect_fit_samples()` cut off at real `time.time() - 14*86400`, ignoring
the fixture's pinned `UF_NOW`. `fable-older`'s fixture mtime
(`UF_NOW - 5d` = 2026-10-05 18:00Z) crossed that real cutoff at
2026-10-19 10:40 PDT (9 real days after `UF_NOW`'s calendar date), at which
point `collect_fit_samples` silently dropped it and the fallback fit
collapsed to the thin recent-only $1/100.

Fix: `collect_fit_samples(work_dir, projects_dir, max_age_days=14, now=None)`
-- cutoff is `(now if now is not None else time.time()) - max_age_days*86400`,
so the one production caller (`combined_price_map`, which already requires
a `now` argument) is unaffected when it doesn't pass one, and every caller
that does gets a deterministic cutoff. `combined_price_map` now threads its
own `now` through to `collect_fit_samples` (previously dropped on the floor
-- the actual bug). `fit_prices()` is untouched per the brief: it has no
fixture caller that crosses this edge and its own production caller
(`scan_transcripts`, `price_for`) still wants real wall-clock.

All three cases in the fixture, plus the `combined_price_map` check, now
pass `now=$UF_NOW` explicitly to `collect_fit_samples`.

**Falsifier added** (new checks after case 3, before the migration section):
a second fixture tree (`$T/usagemeterfit-faredge`) whose own clock
(`UH_NOW`) is computed at run time as `$(date +%s) - 30*86400` -- 30 real
days in the past, so the gap between the fixture clock and wall-clock is
always comfortably past the 14-day edge no matter what calendar date this
selftest actually runs on (unlike case 2's fixed `UF_NOW_ISO`, whose gap to
wall-clock only grows and will cross the edge again on its own, exactly as
it did on 10-19). The check confirms the combined 14-day fit still comes
out correctly against that fixture; the paired MUTANT check re-implements
the pre-fix `collect_fit_samples` (cutoff always `time.time()`, inline,
same style as case 1's existing MUTANT) and confirms the far-past
fixture's model drops out of the fit entirely under it (`KeyError`-shaped
assertion: `'claude-fable-5-1' not in fit`).

## 2. `docs/testing/jobs/selftest.d/99-hold-tiers.sh` leg (c) -- the clock race

The fixture read `htr_now=$(date +%s)` once, then named requests `59s old`
and `61s old` against `HOLD_YIELD_S=60`. `yield-check` reads the clock
again when it runs; under a loaded 4-shard run more than 1s can pass
between the two reads, so the "59s old" request is sometimes already 60s+
by the time `yield-check` looks, and the "does not yield yet" assertion
(exit 0 expected) sees exit 7 instead.

Fix: young = 30s, old = 90s, `HOLD_YIELD_S` left at its default 60 --
30s of margin on both sides of the edge is far more than a selftest
shard's scheduling jitter can eat. No other fixture in this fragment names
an age at the edge of `HOLD_YIELD_S` (the `0-*` case yields immediately
regardless of age, by design).

Not added as a new check: the brief's "MUTANT: HOLD_YIELD_S read as 20"
is a sanity check on the margin choice, not a new assertion -- the existing
"(c) a 1-* request 30s old does not yield yet" check already fails under
`HOLD_YIELD_S=20` (30 >= 20, so it would yield), so the fragment's own
structure (an env var the fixture's `htr()` passes through) remains a live
discriminator at the new margins without more code.

## 3. The jam title itself -- `master-health.json`'s `fragment` field

The code that builds the `master-red:<fragment>` jam row is
`host-tools/driver_tick.py`'s `master_red_status()`, which just reads
`fragment` out of `offline-git/master-health.json` verbatim. That file is
written by `/home/justin/hakux-work/offline-git/master_health_check.sh`,
run host-side after every fold -- **outside this git repository** (not
under `/home/justin/hakuX`, no `.git` in `offline-git/`, no copy anywhere
in this tree). A lane cannot fix it through a PR; territory.toml/the board
have no row for it either.

It was taking the fragment name from `grep -oE '...\.sh' "$log" | tail -1`
-- the last fragment name anywhere in the whole 4-shard-concatenated log,
which is shard 3's last fragment (`99-verdict-10min.sh`, which passed)
regardless of which shard actually failed. Confirmed by hand: that is
exactly what produced today's `master-health.json` (`"fragment":
"99-verdict-10min.sh"`, written 11:47 -07:00, stale).

**This was already fixed on the host, independently, before this lane
started**: `master_health_check.sh`'s mtime is 12:13 (after the 11:47
stale verdict), there is a dated backup
`master_health_check.sh.bak-20261019-fragattr`, and the new code's own
comment names the incident (`"10-19, nova-tiers1019 false-attribution"`).
The fix now tracks FAIL lines and attributes each to the NEXT
`selftest: NAME.sh took Ns` marker (the fragment still running when a FAIL
prints), collecting the distinct set in order instead of grabbing the
log's last fragment overall. Replayed by hand against the real
`fold-logs/master-health-20261019T1114-913e1524ff.log`:

```
$ awk '<the new script's logic>' fold-logs/master-health-20261019T1114-913e1524ff.log
88-usage-meterfit.sh,99-hold-tiers.sh
```

-- the correct pair, matching this brief's own shard/line pointers. No
further action needed from this lane; `master-health.json` itself will
refresh (and the jam clear) once `master_health_check.sh` next runs against
a green master, which this lane's fold will trigger.

## Verification

- `SELFTEST_ONLY="88-usage-meterfit.sh"`: 15 passed, 0 failed (includes
  both new falsifier checks).
- `SELFTEST_ONLY="99-hold-tiers.sh"`: 35 passed, 0 failed.
- Full `SELFTEST_SHARD=0/4` (shard 1): PASSED (see below).
- Full `SELFTEST_SHARD=1/4` (shard 2): PASSED (see below).
