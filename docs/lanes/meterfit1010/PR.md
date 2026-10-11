# lane.meterfit1010: price transcript tokens, not modelUsage tokens (#433, 0.5)

State: ready

Lane: meterfit1010             Issue: none (harness fix dispatched directly by lane.local, #433 umbrella)
Base: master @ 7a44ee4d97
Files: docs/testing/jobs/usage/meter.py, docs/testing/jobs/selftest.d/88-usage-meterfit.sh,
       docs/lanes/meterfit1010/NOTES.md, docs/lanes/meterfit1010/PR.md
Prediction: none: analysis-only, no pixels
Needs device: no    Needs NDK: no
Release note (none): harness

An audit (lane.local, #433) found transcripts complete but prices systematically low this week (Opus 17% low,
Fable 43% low, Sonnet 4% low), for two reasons: some billed model calls never land in a transcript at all (the
run's `modelUsage` counts more tokens than its transcript holds), and `fit_prices()` divides `costUSD` by
`modelUsage` tokens -- not transcript tokens -- over a 14-day window that lags the current week's price mix.

## What changed

- `transcript_eq(projects_dir, session_id)`: finds a run's transcript (`<session_id>.jsonl` plus
  `<session_id>/subagents/*.jsonl`), sums eq per model, deduped by assistant `message.id` -- first line wins,
  the same rule `scan_transcripts` already used. Returns `None` if no transcript file exists at all.
- `_norm_model()` / `_eq_for_billing_model()`: `modelUsage` keys carry a `[1m]` tag and sometimes a dated suffix
  that the transcript's `message.model` never does; matched exactly first, else on the normalized form (checked
  there are no collisions across the real distinct `modelUsage` keys).
- `collect_fit_samples()` / `fit_prices_transcripts()`: per-run `(mtime, model, costUSD, transcript_eq)`
  samples, priced per model over a 72h trailing window, falling back to 14 days when the short window holds
  under 5 runs or under $5 `costUSD` for that model.
- `combined_price_map()`: `fit_prices_transcripts()`'s number where it has one, else `fit_prices()`'s (today's
  modelUsage/14d fit) -- so a model the transcript fit never saw keeps today's behaviour exactly. This is what
  `scan_transcripts()` prices events with now.
- Events carry `model`/`eq` alongside `cost`, so `reprice_events()` can recompute `cost` on a later tick without
  re-reading any transcript. `reprice_calibration_capacity()` recomputes only the *latest* calibration point's
  `capacity` from the re-priced events in `[week_start, reading_utc]`; its `utc`/`percent` (the owner's own
  reading) and every older point are left untouched.
- `migrate_events()`: old-format state (events with `cost` only) drops events inside `KEEP_DAYS` and their
  offsets, forcing one re-read of that window on the next tick -- the meter migrates itself; nothing outside it
  touches the host's real `$HAKUX_WORK/usage/` files.

## Window choice: 72h, floor at 5 runs / $5 costUSD

Real fleet, 72h ending now (2026-10-10): sonnet 188 runs / $261, opus 22 runs / $233, fable 2 runs / $47.
Sonnet and Opus clear the floor comfortably; Fable's 2-run sample correctly falls back to the 14-day fit instead
of overfitting two points. 72h was the brief's own starting point and nothing in the real data argued for a
different number.

## Held-out error (fit on runs before 2026-10-10T12:00 PDT, predict later runs' costUSD from transcript eq)

Error = (sum predicted − sum actual) / sum actual, aggregated per model -- matches "how wrong would total spend
be," which is what the meter reports.

| model  | today's fit | this fit |
|--------|------------:|---------:|
| sonnet | −5.47%      | −1.65%   |
| opus   | −17.5%      | +2.32%   |
| fable  | not computable (0 held-out runs in this window) | not computable (0 held-out runs) |

Opus and Sonnet land within 5%, as required.

## The three calibration intervals, $/point

Bounded scan of this week's transcripts, deduped by message id the same way `scan_transcripts` is (an early
version of the measurement script skipped that dedup and double-counted, giving numbers roughly double
everything below -- caught by comparing against the real `state.json`'s own stored capacities before trusting
it).

| reading (UTC)        | pct  | $/pt OLD | $/pt NEW | brief: today | brief: per-model |
|-----------------------|-----:|---------:|---------:|-------------:|------------------:|
| 2026-10-09T21:43:56   | 4.0  | 25.44    | 26.89    | 25           | 27                |
| 2026-10-10T05:52:55   | 11.0 | 22.91    | 25.88    | 22           | 25                |
| 2026-10-11T00:56:23   | 31.0 | 19.18    | 21.88    | 17           | 21                |

OLD matches both the brief's "today" figures and the real `state.json`'s stored capacities for these three
readings (25.45/22.91/19.12 $/pt) -- confirms the measurement script before trusting its NEW column, which in
turn lands within $1 of the brief's own "per-model correction" reference (27/25/21).

**This fit removes about a fifth of the within-week drift, not all of it.** OLD spread (high − low reading) is
25.44 − 19.18 = 6.26; NEW spread is 26.89 − 21.88 = 5.01 -- a reduction of 1.25, ~20%.

This fit divides `costUSD` by *transcript* eq, so a call that is billed but never written to a transcript at
all is already priced in -- it is not what is left in the remaining 5.01 spread. Two candidates, neither
chosen here: interactive sessions (compaction and similar) may carry a different share of unlogged calls than
the headless runs the fit learns from, and would shift price without any change in headless cost per token;
and the owner's readings are whole percents, so the 4% reading alone carries roughly ±12% on its own, which is
a large fraction of a $1-2 move in $/pt. This lane's job was the fit; narrowing which of these (or another
cause) accounts for the rest is a separate measurement.

## Selftest: 88-usage-meterfit.sh (fixtures only, temp HAKUX_WORK/HAKUX_CLAUDE_PROJECTS)

| case | what it shows |
|---|---|
| ratio | opus run, transcript 900 eq vs modelUsage 1000 eq -> price higher by exactly that ratio |
| fallback | fable: 1 recent run (too thin, under the floor) + 1 older run -> price comes from the combined 14-day fit, not either window alone |
| no transcript | haiku run with no transcript file at all is skipped (adds to neither sum) |
| migrate | pre-#433 state (cost-only events) migrates: events gain model/eq, latest calibration's capacity changes while percent/utc don't, both CAL_SEED points untouched, a second tick is a no-op |
| mutant | re-pointing the fit at modelUsage eq (1000) instead of transcript eq (900) collapses the ratio case to 1.0 -- reproduces today's bug |

Scoped, during development: `SELFTEST_ONLY="88-usage-meterfit.sh 89-usage-mode.sh" bash
docs/testing/jobs/selftest.sh` (after merging lane.usagerule1010's changes to 89): 69 passed, 0 failed -- 13
new, 56 existing, no interference.

Full run, all 4 shards, foreground: **3268 passed, 0 failed, across all 132 fragments** (shard 0/4: 284/0 of
13 fragments; 1/4: 1012/0 of 42; 2/4: 1057/0 of 39; 3/4: 915/0 of 38). No flakes, no rerun needed.

## Rules followed

Did not touch `89-usage-mode.sh`, `mode.sh`, or `models.toml` (lane.usagerule1010 owns them). Did not read or
write the real `$HAKUX_WORK/usage/state.json` or `summary.txt` -- all real-data measurement ran from `/tmp/`,
importing `meter.py`'s functions directly, never calling `main()`/`save_state()` against real paths. No device
runs. Merged `origin/master` (7a44ee4d97) before this PR.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
