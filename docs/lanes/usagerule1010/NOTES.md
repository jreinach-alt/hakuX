# lane.usagerule1010

Issue: none (dispatched directly by lane.local, #433 umbrella). No device.

## What was wrong

`mode.sh`'s `evaluate()` entered Low on EITHER line (`pct >= low_pct (80) or p >= low_proj (90)`). On 10-10 at
09:30 PDT that put the project into Low at 19% of the week used, purely because the trailing-rate projection read
134%. The owner (10-10 ~10:30 PDT): "I do not want low enabled at all this weekend. Bad call there. It only
should trigger when we're at 80 percent for the week and projected to go over 100."

## The fix

One rule, stated once in `mode.sh`'s header comment and once in `models.toml`'s `[usage]` comments:

- **enter Low**: `estimated% >= low_pct (80)` **AND** `projected-at-reset% > low_proj (100)` (strict: "over", not
  "at or over" -- the owner's own word).
- **back to Normal**: `estimated% < low_pct` **OR** `projected-at-reset% < normal_proj (95)`.

`models.toml`'s `[usage]` defaults: `low_pct = 80` (unchanged), `low_proj` moved 90 -> 100, `normal_proj` moved
75 -> 95 (keeps the same 5-point hysteresis gap below the new `low_proj`, just re-anchored to it; the gap's
purpose -- stop a Low that just started from flapping on one quiet hour -- doesn't change, only where the line
sits).

`evaluate()`'s python block now computes `entering = pct >= low_pct and p > low_proj` and
`leaving = pct < low_pct or p < normal_proj`, and picks the printed reason (and hence the mode transition) from
those two booleans plus the current mode, instead of the old single `or` chain. The printed reason always names
both numbers and both lines, e.g. `85% used >= 80 and 101% projected > 100` (the shell strips a leading `low `/
`normal ` word that only exists to route the case statement -- see `apply_low`'s `${out#low }`, unchanged).

## Why `normal_proj` moved too, not just `low_proj`

The brief fixed all three dial values explicitly (`low_pct = 80`, `low_proj = 100`, `normal_proj = 95`), so this
isn't a judgment call -- just noting the reasoning for later readers. The old hysteresis gap was 15 points
(`low_proj` 90 down to `normal_proj` 75); the new one is 5 points (100 down to 95). That shrink is the brief's
own numbers, not something this lane chose -- flagging it so a future lane doesn't assume the gap size carried
over unchanged along with the gap's purpose.

## Verification

`SELFTEST_ONLY=89-usage-mode bash docs/testing/jobs/selftest.sh`: 56 passed, 0 failed (fresh run after the edits;
see PR.md for the case list).

Two mutants applied by hand to a scratch copy of `mode.sh`'s `entering` line, selftest re-run, then reverted
(diff confirmed clean afterward):

1. `entering = pct >= low_pct and p > low_proj` -> `... or p > low_proj` (reinstate OR on the entry line): 2
   checks go red -- "19% used, 134% projected stays normal" and "85% used, 100% projected stays normal" (the
   latter because OR also lets `pct >= low_pct` alone trigger Low at 85%, regardless of the strict-projection
   mutant not yet being applied).
2. `p > low_proj` -> `p >= low_proj` (reinstate the non-strict comparison): 1 check goes red -- "85% used, 100%
   projected stays normal" (the owner's own word was "over", not "at or over").

Both mutants are caught; reverting either alone is enough to turn at least one case red, so the suite is not
vacuously passing.

Full `docs/testing/jobs/selftest.sh` run (whole, no `SELFTEST_ONLY`): 3255 passed, 0 failed, all 131 fragments --
no unrelated regression. Took ~65 minutes wall clock; waited on it in foreground chunks under the Bash tool's
10-minute limit rather than detaching, per this lane's own headless-session rule.

## A process note for the next lane sharing this host

Mid-session, a `timeout`-wrapped foreground selftest run of mine appeared to return "Terminated" (exit 143) while
its child processes kept running server-side, and a `nohup ... &`-detached rerun escaped the harness's own
task-tracking (no completion notification). Neither is this lane's defect to fix, but worth naming: prefer
`run_in_background: true` on the bash tool call itself over manual `nohup`/`&`, since only the former gets a
tracked completion notification here. Also found, while diagnosing stray PIDs: a separate, legitimate
`foldqueue.sh` / `offline_fold.py lane/reportasync1010` process tree happened to share the generic command name
`bash docs/testing/jobs/selftest.sh` (different cwd, different pgid) -- confirmed by `ps -eo pid,ppid,pgid,cmd`
before touching anything, and left entirely alone.
