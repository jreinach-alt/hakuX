# usagemode: a usage meter and an auto Low/Normal mode switch (#433)

State: ready

Lane: usagemode              Issue: #433 (0.5: 50 Playable)
Base: origin/master @ 66bce0c222, merged forward to 6c2b801c3b (lane/stopmarker's fold; clean merge, no conflicts)
Files: docs/testing/jobs/window.sh, docs/testing/jobs/selftest.d/88-window-budget.sh,
       docs/testing/jobs/selftest.d/89-usage-mode.sh, docs/testing/jobs/usage/meter.py,
       docs/testing/jobs/usage/mode.sh, docs/testing/jobs/usage/units/hakux-usage-meter.service,
       docs/testing/jobs/usage/units/hakux-usage-meter.timer, docs/lanes/usagemode/NOTES.md,
       docs/lanes/usagemode/PR.md, docs/lanes/usagemode/OUTBOX.md
Prediction: none: no arm (no device, no pixels)
Needs device: no    Needs NDK: no
Release note (none): harness/orchestration only -- no emulator code (hw/ target/ accel/ android/
    tcg/ ui/ audio/) touched; nothing a player would notice.

## Summary

Built the two things the brief asked for:

1. **The meter** (`docs/testing/jobs/usage/meter.py`): model-free, incremental
   (remembers a byte offset per `~/.claude/projects` transcript file so it
   never re-reads what it already priced), week-to-date dollar-equivalent
   spend by actor (lane name, board, cloud audits, hostops, interactive),
   the 1h/6h burn rate, and an estimated percent of the account's week from
   the two calibration readings the owner gave (92% @ 2026-09-30 22:40 PDT,
   16% @ 2026-10-02 10:10 PDT). The two readings imply weekly capacities
   that disagree by 2.2x ($8,241 vs $3,823) -- the owner's own non-harness
   claude.ai use is a different share of the account's week each time, and
   this file cannot see that use directly. The estimate uses the most
   recent calibration point, documented at length in NOTES.md along with a
   `calibrate PCT` command for adding more readings over time. Writes
   `$WORK/usage/state.json` and a one-line `$WORK/usage/summary.txt`.
2. **The mode switch** (`docs/testing/jobs/usage/mode.sh normal|low|auto|status`,
   plus a private `tick` the timer calls): Low sets `LANE_MAX=3`,
   `MODEL_LANE_ESCALATED=claude-sonnet-5`, a new `PATHFIND_MODEL_CALLS_MAX=20`
   dial, forces every EXISTING `briefs/*.model` override to claude-sonnet-5
   (an Opus lane keeps its running session; its next resume reads the
   changed file), and drops the hostops heartbeat from 2h to 4h via a
   systemd timer drop-in. Normal restores every one of those byte-for-byte,
   including deleting a `.model` file that did not exist before Low rather
   than leaving it behind. "Never flaps": `tick` only acts when
   `source=auto`; a manual `mode.sh low`/`mode.sh normal` holds until the
   owner runs `mode.sh auto` again or the week resets.
3. `docs/testing/jobs/window.sh`'s anchor moved from Monday 00:00 UTC to
   **Thursday 21:00 America/Los_Angeles** (the owner's actual decision),
   computed with `zoneinfo` so it does not drift across the DST boundary.
   `selftest.d/88-window-budget.sh`'s fixtures, which hardcoded instants
   tied to the old Monday anchor, moved with it (recomputed against the
   real `window_check` output, not by hand) -- see NOTES.md for why that
   file is in `Files:` even though the brief did not name it.
4. Systemd unit TEXT only (`docs/testing/jobs/usage/units/`): lane.local
   installs these; this lane does not touch host units or host-tools/.

**Known gap, not claimed as done:** "no new lanes started by anything but
lane.local" has no enforcement point inside this lane's granted territory.
`mode.sh low` writes `$WORK/usage/low-active` as the signal; `board.sh`'s
capacity gate (outside `docs/testing/jobs/usage/**`) does not read it yet.
Exact integration point in OUTBOX.md for lane.local.

## Local verification (offline protocol: no CI, no device)

- `docs/testing/jobs/selftest.d/89-usage-mode.sh` alone (`SELFTEST_ONLY=89-usage-mode`):
  **47 passed, 0 failed**, run twice to confirm it is not time-of-day flaky.
- `docs/testing/jobs/selftest.d/88-window-budget.sh` alone, after moving its
  fixtures to the new anchor: **50 passed, 0 failed** (same count as before
  this lane -- the anchor moved, the coverage did not shrink).
- **Full `docs/testing/jobs/selftest.sh` (all ~120 fragments) was started but
  not completed in this session.** It ran fragments 10/20/30/40 to
  completion (74s/141s/60s/340s; `arms.sh`'s queue/error/refusal chain, 20
  checks, 0 failures) before the time budget for this run ran out partway
  into fragment 50; the suite's own `SHARD_SECS` table puts the full run at
  18-25 min on CI and roughly double that on this host, which did not fit
  this session's turn budget. In its place: `grep -rl
  'window\.sh\|WEEK_ANCHOR\|window_check' docs/testing/jobs/selftest.d/`
  finds every fragment that touches the file this lane changed
  (97-board-release.sh, 97-board-priority.sh, 99-board-wt-refresh.sh,
  99-lane-model-file.sh, plus 88 and 89); none of the four outside this
  lane's own files assert anything about the weekly reserve, elapsed
  percent, or a specific `HAKUX_NOW` (checked directly, not assumed) -- they
  only copy `window.sh` alongside `board.sh` so it can be sourced, which the
  anchor change does not affect. `grep -rl 'usage/mode\|usage/state'
  docs/testing/jobs/*.sh` outside this lane's files returns nothing, so
  nothing else in the harness reads the new files yet either. This is
  reasonable confidence, not a substitute for the full run; said plainly
  rather than claimed as "selftest.sh is green."

## Release note

none -- orchestration/harness only.
