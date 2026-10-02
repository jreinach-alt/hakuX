## #433 -- 2026-10-02 10:45 PDT

[lane.usagemode] Built the usage meter and the Low/Normal mode switch the
brief asked for.

**Meter** (`docs/testing/jobs/usage/meter.py`, no device, model-free): reads
`~/.claude/projects` incrementally (a byte offset per file, so a 30-min tick
only reads what is new), prices it from the headless run index's own
`costUSD`, and buckets spend by actor (lane name, board, cloud audits,
hostops, interactive). Writes `$WORK/usage/state.json` and
`$WORK/usage/summary.txt`. Real run against this host's transcripts (dollar
figures and model names only, nothing else printed or kept): $656 since the
2026-10-01 21:00 PDT reset, top actors lane:routedriver2 $122, hostops $69,
lane:titleroutes2 $61; 6h burn rate ~$67/h; that rate projects to ~290% of
the 16%-calibration-point's implied weekly capacity by Thursday's reset. The
two calibration readings you gave imply capacities 2.2x apart ($8,241/week
from the 92% reading, $3,823/week from the 16% one) -- expected, since your
own claude.ai use is a different share of the account's week each time and
this file cannot see that use directly. Full reasoning and the exact numbers
in `docs/lanes/usagemode/NOTES.md`.

**Mode switch** (`docs/testing/jobs/usage/mode.sh normal|low|auto|status`):
Low -> `LANE_MAX=3`, `MODEL_LANE_ESCALATED=claude-sonnet-5`, a new
`PATHFIND_MODEL_CALLS_MAX=20`, every existing lane `.model` override forced
to claude-sonnet-5 (a running Opus lane finishes its session; its next
resume reads the changed file), hostops heartbeat 2h->4h. Normal restores
every one of those exactly, including removing a `.model` file that did not
exist before Low. Never flaps: a manual `low`/`normal` holds until you run
`auto` again or the week resets; the 30-min timer's own tick is a no-op
while that lock is held.

**window.sh's anchor** moved to **Thursday 21:00 America/Los_Angeles**
(your 10:10 PDT decision) from the placeholder Monday 00:00 UTC, computed
with `zoneinfo` so it tracks your wall clock across DST rather than a fixed
UTC hour. `selftest.d/88-window-budget.sh`'s fixtures moved with it.

**Two things this lane could NOT finish inside its own territory** (full
detail in NOTES.md and PR.md; this is not silently claimed as done):

1. **board.sh needs ~3 lines to honor Low's "no new lanes but lane.local."**
   `mode.sh low` writes `$WORK/usage/low-active` (one line, the reason)
   exactly the way `window.sh`'s `WINDOW_DEFER` already works. The gate that
   would read it is `board.sh`'s capacity check, which is outside this
   lane's granted territory (`docs/testing/jobs/usage/**`, `window.sh`,
   `selftest.d/88-window-budget.sh`, `selftest.d/89-usage-mode.sh`).
   Suggested patch, parallel to the existing window check:
   ```
   if [ -s "$WORK/usage/low-active" ] && [ "${LANE:-}" != "local" ]; then
       say "DEFERRING dispatch: Low mode is active ($(cat "$WORK/usage/low-active"))."
       return/continue   # whatever board.sh's own early-exit idiom is at that call site
   fi
   ```
2. **host-tools/ changes, which this lane does not edit:**
   - `host-tools/overnight_mode.sh` should be retired or clearly marked
     superseded: Low mode now covers (and goes further than) its
     `LANE_MAX=1` + timer-stop behavior, and the two running at once would
     fight over the same hostops timer drop-in technique.
   - `host-tools/hourly_report.sh` should add one line printing
     `$WORK/usage/summary.txt` (already written by every meter tick) to the
     hourly/overnight check-in, per the brief's "Report line" item.

**Local verification** (offline protocol -- no CI, no device): the two
fragments this lane added/changed are green (89-usage-mode.sh: 47/47;
88-window-budget.sh: 50/50, same count as before). The full `selftest.sh`
(all ~120 fragments) did not finish inside this session's turn budget (its
own weight table puts a full run at 18-25 min on CI, longer here); checked
by hand instead which OTHER fragments touch `window.sh` or the new
`usage/mode`/`usage/state` paths, and none of them assert anything the
anchor change would move. Said plainly rather than claimed as a green full
run -- see PR.md.

PR is `docs/lanes/usagemode/PR.md` on `lane/usagemode`, `State: draft` for
now (full-suite run still outstanding; will flip to `ready` once that
either completes clean or a lane.local/owner call says the targeted
verification above is sufficient).
