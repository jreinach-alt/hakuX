# lane.meterfit1010 — fit prices against transcript tokens (#433, 0.5)

## What changed in meter.py

- `transcript_eq(projects_dir, session_id)`: globs `<session_id>.jsonl` plus
  `<session_id>/subagents/*.jsonl`, dedups assistant messages by `message.id`
  (first line wins — same rule `scan_transcripts` already used), returns
  `{model: eq}` or `None` if no transcript file exists at all.
- `_norm_model()` / `_eq_for_billing_model()`: `modelUsage` keys carry a
  `[1m]` context-window tag and sometimes a dated suffix
  (`claude-haiku-4-5-20251001`) that the transcript's `message.model` never
  does. Exact match first, else match on the normalized form. Checked there
  are no collisions across the real distinct `modelUsage` keys before
  relying on this.
- `collect_fit_samples()` / `fit_prices_transcripts()` / `combined_price_map()`:
  per-run `(mtime, model, costUSD, transcript_eq)` samples, a short trailing
  window with a floor, a 14-day fallback per model, merged over
  `fit_prices()` (today's modelUsage/14d fit) so a model the transcript fit
  never saw keeps today's number exactly.
- Events now carry `model` and `eq` (`scan_transcripts`), so a later tick can
  reprice them without re-reading transcripts (`reprice_events`).
- `migrate_events()`: old-format state (events with `cost` only) drops events
  older than `KEEP_DAYS` and their matching offsets, forcing one re-read of
  the kept window on the next scan. Runs unconditionally in `main()`; a
  no-op once every event already carries `model`/`eq`.
- `reprice_calibration_capacity()`: after repricing, recomputes only the
  latest calibration point's `capacity` from the window `[week_start,
  reading_utc]` of (now re-priced) events. `utc` and `percent` are the
  owner's reading and are never touched. Older points are left alone.

## Window choice: 72h, floor at 5 runs / $5 costUSD

Checked against the real fleet in the 72h ending now (2026-10-10, see
`/tmp/meterfit_real.py` — not committed, exploratory only):

| model  | runs (72h) | costUSD (72h) |
|--------|-----------:|--------------:|
| sonnet | 188        | $261          |
| opus   | 22         | $233          |
| fable  | 2          | $47           |

Sonnet and Opus clear 5 runs / $5 comfortably inside 72h — a window that
short is enough to track this week's price mix for the two models that
dominate spend. Fable's 72h sample (2 runs) is too thin on its own, which is
exactly what the floor is for: it falls back to the 14-day fit instead of
overfitting to 2 points. 72h was the brief's own starting point and nothing
in the real data argued for a different number, so it stayed.

## Held-out validation

Fit on runs whose log mtime is before 2026-10-10T12:00:00-07:00, predict
`costUSD` of later runs from their transcript eq (`/tmp/meterfit_heldout.py`,
exploratory, not committed). Train 2339 samples, test 30 (18 sonnet, 12
opus, 0 fable — Fable had no runs in the held-out window at all, so its
held-out error is not computable; see brief's own allowance for a small
Fable sample).

Error = (sum predicted costUSD − sum actual costUSD) / sum actual costUSD,
aggregated across the held-out runs per model (this is "how wrong would
total spend be," which is what the meter reports; a per-run mean-absolute
error is dominated by small noisy runs and does not match that question).

| model  | today's fit (modelUsage/14d) | this lane's fit (transcript/72h+fallback) |
|--------|------------------------------:|-------------------------------------------:|
| sonnet | −5.47%                        | −1.65%                                     |
| opus   | −17.5%                        | +2.32%                                     |
| fable  | not computable (0 held-out runs) | not computable (0 held-out runs)        |

Opus and Sonnet are within 5% for this lane's fit, as required.

## The three calibration intervals — STILL BEING VERIFIED

Measuring the three owner readings' $/point under both fits. An early
version of the measurement script double-counted (it didn't dedup assistant
messages by id across the scanned window), giving $/point roughly double
both the brief's own reference numbers and the real `state.json`'s stored
capacities for the same three readings. Re-running with the same
first-line-wins dedup `scan_transcripts`/`transcript_eq` use everywhere
else. Numbers to follow in this section and in the PR body once confirmed.

## Selftest: 88-usage-meterfit.sh

Fixtures only, temp `HAKUX_WORK`/`HAKUX_CLAUDE_PROJECTS`. Cases:

1. **ratio** — an opus run whose transcript (900 eq) holds fewer tokens than
   its `modelUsage` (1000 eq); the transcript-fit price is higher than
   today's fit by the 1000/900 ratio.
2. **fallback** — fable has one recent run (72h, $1/eq100) and one 5-day-old
   run ($9/eq1800); the recent-only sample is too thin (under the run/cost
   floor), so the price must come from the combined long-window fit
   (10/1900), not the thin short-window number (1/100) and not the
   older-only number (9/1800).
3. **no transcript** — a haiku run (`session_id = sid-haiku-missing-xyz`)
   with no transcript file at all is skipped by `collect_fit_samples` (adds
   to neither sum).
4. **migrate** — pre-#433 state (events with `cost` only, offsets already
   fully scanned, three calibration points including the two `CAL_SEED`
   entries) is migrated by a real `meter.py` subprocess run: events get
   `model`/`eq`, the stale event is replaced by a rescanned one, the latest
   calibration's `percent`/`utc` are unchanged but its `capacity` changes,
   and the two seed calibration points are untouched. A second tick is a
   no-op on the event list (nothing left to migrate).
5. **mutant** — re-pointing `fit_prices_transcripts` at the opus run's
   `modelUsage` eq (1000) instead of its transcript eq (900) collapses the
   price ratio to 1.0, reproducing today's bug and showing case 1 actually
   depends on the fix.

Verified: `SELFTEST_ONLY="88-usage-meterfit.sh 89-usage-mode.sh" bash
docs/testing/jobs/selftest.sh` → 69 passed, 0 failed (13 new + 56 existing,
after merging in lane.usagerule1010's changes to 89). 89's behavior is
untouched by this lane.

## Rules followed

- Did not touch `89-usage-mode.sh`, `mode.sh`, or `models.toml`.
- Did not read or write the real `$HAKUX_WORK/usage/state.json` or
  `summary.txt`; all real-data measurement scripts ran from `/tmp/`,
  imported `meter.py`'s functions directly, and never called `main()`/
  `save_state()` against real paths.
- No device runs.
