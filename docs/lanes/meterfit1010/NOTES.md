# lane.meterfit1010 — fit prices against transcript tokens (#433, 0.5)

## Attempt 2: why attempt 1 didn't finish

Attempt 1 implemented the fit, wrote the targeted selftest case, and verified it with
`SELFTEST_ONLY="88-usage-meterfit.sh 89-usage-mode.sh"` (69 passed, 0 failed) — but never ran the *full*
`selftest.sh` (132 fragments, 4 shards, 18-25 min whole per the CI workflow's own comment). It started that
full run with `run_in_background` and then ended the session to wait for a notification. This is a headless
`claude -p` session: a `run_in_background` command is a child of the session process, and when the turn/session
ends, the process group is killed with it — so the background run died with no completion notification ever
coming, and the PR was left in draft with the full-suite result unknown. Addendum 1 names this exact trap.
Fixed here by running each of the four `SELFTEST_SHARD` shards in the foreground, one per tool call, inside the
10-minute per-call limit.

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

## The three calibration intervals

Measured with `/tmp/meterfit_intervals.py` (exploratory, not committed): a
bounded scan of every `~/.claude/projects/**/*.jsonl` file whose mtime falls
at or after this week's start (`week_bounds()`, Thu 21:00 PT), deduped by
assistant `message.id` globally — the same rule `scan_transcripts` uses (the
first draft of this script skipped that dedup and double-counted, giving
$/point roughly double every number below; fixed before reporting). `$/pt
OLD` runs `meter.fit_prices()` (today's modelUsage/14d fit) over this scan's
events; `$/pt NEW` runs this lane's `combined_price_map()` the same way.

| reading (UTC)        | pct  | $/pt OLD | $/pt NEW | brief: today | brief: per-model |
|-----------------------|-----:|---------:|---------:|-------------:|------------------:|
| 2026-10-09T21:43:56   | 4.0  | 25.44    | 26.89    | 25           | 27                |
| 2026-10-10T05:52:55   | 11.0 | 22.91    | 25.88    | 22           | 25                |
| 2026-10-11T00:56:23   | 31.0 | 19.18    | 21.88    | 17           | 21                |

The OLD column lines up with both the brief's "today's" figures and the
real `state.json`'s stored calibration capacities for these same three
readings (2544.55/2291.23/1912.34, i.e. 25.45/22.91/19.12 $/pt) — confirming
this measurement script reproduces production's actual numbers before
trusting its NEW column. The NEW column lines up with the brief's own
"per-model correction" reference (27/25/21) within $1.

$/point drops across the week in both fits (the model mix shifts as the
week goes on) — that drop is the "spread" the brief asks about. OLD spread
(high reading − low reading) is 25.44 − 19.18 = 6.26; NEW spread is 26.89 −
21.88 = 5.01. **This fit removes about a fifth of the within-week drift
(1.25 of 6.26, ~20%) — it does not remove all of it.**

Addendum 1 correction: this fit divides `costUSD` by *transcript* eq, so a
call that is billed but never written to a transcript at all is already
priced in — the missing-call cause from the brief's "Why" section cannot be
what's left in the remaining 5.01 spread (the first draft of this note
claimed it was; that was wrong, since `fit_prices_transcripts()` prices
transcript tokens, and a run with no transcript is excluded from both sums,
not split unevenly against them). Two candidates for the remainder, neither
chosen here:
- interactive sessions (compaction and similar) may carry a different share
  of unlogged-but-billed calls than the headless runs the fit learns from,
  which would shift the effective price without any change in headless
  cost-per-token;
- the owner's readings are whole percents, so the 4.0% reading alone
  carries roughly ±12% of its own noise — a sizeable fraction of a $1-2
  move in $/pt.

Narrowing which of these (or another cause) accounts for the rest is a
separate measurement; this lane's job was the fit.

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

Verified (attempt 1, scoped): `SELFTEST_ONLY="88-usage-meterfit.sh
89-usage-mode.sh" bash docs/testing/jobs/selftest.sh` → 69 passed, 0 failed
(13 new + 56 existing, after merging in lane.usagerule1010's changes to 89).

## Full selftest (attempt 2, addendum 1): all 4 shards, foreground

`docs/testing/jobs/selftest.sh` is 132 fragments across 4 `SELFTEST_SHARD`
shards (the CI workflow's own comment: 18-25 min whole). Ran each shard to
its own log, in the foreground within this turn (see "why attempt 1 didn't
finish" above), and waited on all four before proceeding:

| shard | fragments | passed | failed |
|------:|----------:|-------:|-------:|
| 0/4   | 13        | 284    | 0      |
| 1/4   | 42        | 1012   | 0      |
| 2/4   | 39        | 1057   | 0      |
| 3/4   | 38        | 915    | 0      |
| **total** | **132 (all)** | **3268** | **0** |

No failures, so no flake rerun was needed. (The `fail:`/`FAIL`/`failed`
strings in the raw logs are all test *names* and fixture content describing
what a failing case should look like — e.g. `fail:
1791690579-rqp-fail-1467741`, `ok mutant caught by '...rate_fail.logcat':
ignore the per-minute bar` — not selftest failures; the authoritative line
per shard is `selftest: N passed, 0 failed, ...`, confirmed above for all
four.) 89's behavior is untouched by this lane.

## Rules followed

- Did not touch `89-usage-mode.sh`, `mode.sh`, or `models.toml`.
- Did not read or write the real `$HAKUX_WORK/usage/state.json` or
  `summary.txt`; all real-data measurement scripts ran from `/tmp/`,
  imported `meter.py`'s functions directly, and never called `main()`/
  `save_state()` against real paths.
- No device runs.
