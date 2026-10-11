Lane: modelpolicy1010       Issue: #433 (umbrella, dispatched directly)
Base: master @ 1878dbf06d; merged origin/master @ c271f515b4 (clean, no conflicts) before this push
Files: docs/testing/jobs/models.toml, docs/testing/jobs/models.py, docs/testing/jobs/models.sh,
       docs/testing/jobs/models.env (deleted), docs/testing/jobs/cloud.sh,
       docs/testing/jobs/ops/ops_tick.py, docs/testing/jobs/run-claude-job.sh,
       docs/testing/jobs/usage/mode.sh, docs/testing/lane.sh,
       docs/testing/titles/pathfind.py, docs/testing/titles/drive.py,
       docs/testing/jobs/selftest.d/87-ops-tick.sh, docs/testing/jobs/selftest.d/89-usage-mode.sh,
       docs/testing/jobs/selftest.d/99-lane-model-file.sh, docs/testing/dispatcher.sh,
       docs/lanes/modelpolicy1010/NOTES.md, docs/lanes/modelpolicy1010/PR.md
Prediction: none: harness only, no pixels
Needs device: no
State: ready
Release note (none): harness only

One table (`docs/testing/jobs/models.toml`), one reader (`models.py`/
`models.sh`), consulted by every current in-repo caller: `lane.sh`,
`cloud.sh`, `ops/ops_tick.py`, `titles/pathfind.py`, `titles/drive.py`, and
`run-claude-job.sh` (a ninth caller the brief's own inventory did not name --
see NOTES.md). `models.env` is deleted. `$WORK/limits.env` (host) still needs
its model/usage lines removed by hand -- see below, it is not a committed
file this lane can touch.

`dispatcher.sh` ships `jobs/models.py` and `jobs/models.toml` in the run
snapshot (`SCRIPT_DEPS` and `snapshot_scripts`). `titles/drive.py` now imports
`models` from `../jobs`, and a route's `drive` step runs from the snapshot, so
without them every `drive` step on a device run would stop on the import.

Low (`$WORK/usage/low-active`) is unchanged as the one switch; `mode.sh`
writes only that file and `usage/mode`/`switches.log`, same as before this
lane. The dead `PATHFIND_MODEL_CALLS_MAX` dial (brief item 6) is deleted,
not wired -- grepping the repo and host-tools twice found no reader for it
anywhere, so there was nothing live to preserve.

Escalation is unchanged in shape (one step up `haiku -> sonnet -> opus`,
capped at Opus, applied only after a FAILED attempt) -- `lane.sh`'s
`next_attempt()` and `cloud.sh` both resolve through `models.sh resolve`
now instead of reading `MODEL_LANE_ESCALATED` directly, but the attempt
counting itself (which resumes count, which don't) is `handback.sh`'s own
logic and out of this lane's territory, per the brief.

Full detail -- the dead-cap justification, the ninth caller and why it was a
hard break rather than a degraded default, the four more `models.env`
readers found and left alone, a fixture-ordering bug this lane's own change
surfaced and fixed, and the selftest-by-selftest rundown -- is in
`docs/lanes/modelpolicy1010/NOTES.md`.

## Addenda from lane.local (both addressed this session)

**Addendum 1** (clock-step clamp in `ops_tick.py`): already landed in the
head this lane started from (`_lane_idle_min()` clamps at `max(0.0, ...)`,
with the fixture leg in `87-ops-tick.sh` -- "(addendum 1) a commit a few
seconds ahead of NOW is still named under grace 0" plus its mutant leg).
Re-ran `87-ops-tick.sh` this session: 54/54, mutant leg confirmed red
without the clamp.

**Addendum 2** (head `2b7d7cc063` broke `97-board-priority.sh` at fold,
twice, both times shard 2, `HAKUX_WORK: unbound variable`): cause was
`89-usage-mode.sh`'s end-of-fragment `unset HAKUX_WORK HAKUX_CLAUDE_PROJECTS
HAKUX_SYSTEMD_USER_DIR` -- `selftest.sh` exports `HAKUX_WORK` exactly once,
at the top of the whole run, so removing it instead of restoring it left
every fragment sourced afterward in the same shell (97, 98, 99) with no
`$HAKUX_WORK` under `set -u`. Fixed in `89-usage-mode.sh`: save each of the
three vars (and whether each was set at all) before this fragment overrides
them, restore the same way at the end, and a new check asserts `HAKUX_WORK`
is back to the harness's own value afterward. Verified by reinstating the
old bare `unset` as a mutant -- it reproduces the exact `97-board-
priority.sh` failure from the fold logs -- then restoring the fix, which
clears it.

## Verified

| fragment | result |
|---|---|
| 87-ops-tick.sh | 54/54 |
| 88-window-budget.sh | 50/50 |
| 89-usage-mode.sh | 49/49 (18 old + the new HAKUX_WORK-restored check) |
| 99-lane-model-file.sh | 36/36 |
| 97-board-priority.sh | 18/18 |
| 87+88+89+99 together (post-merge) | 218/218 |
| 89+97 together, after reinstating the old bare-unset mutant | reproduces the exact fold failure (`HAKUX_WORK: unbound variable` in 97) |
| 89+97 together, fix restored | both green |
| 96-fleet-flush.sh, 99-lane-path.sh (lanepath1009's own new fragments, merged from master) | 36/36 |
| 78-sweep-remote.sh, 99-handback.sh, 99-limits-env.sh, 98-lane-shape.sh, 98-audit-outlet.sh, 99-handback-waiter.sh | 269/269 |
| `--check-shards 4` | shards 0..3 cover all 131 fragments, each once |
| shard 2/4 in full (`SELFTEST_SHARD=2/4`, the exact shard that failed at fold) | run by the fold selftest (all four shards) |

A full, no-`SELFTEST_ONLY` run was tried under a short timeout from this
session; it only reached the `arms.sh` fragments (well before 87-/88-/89-/
99- alphabetically) before being killed, so it adds nothing beyond the
targeted runs above. The brief's own words: run the fragments you touch
before `State: ready` (done, table above) -- the full ~60 minute run is
lane.local's job at fold, not something a headless session can complete
within one turn. Shard 2 in full (36 fragments, the exact shard that failed
twice at the previous fold) is the one exception worth running end to end,
since addendum 2 asked specifically for the shard-2 result with fragments
in order, not 89/97 in isolation.

## For lane.local after the fold

1. **`$WORK/limits.env` (host, uncommitted) -- checked, exactly one live
   line to remove**: `/home/justin/hakux-work/limits.env:50` still carries
   ```
   MODEL_LANE_ESCALATED=claude-opus-5-5
   ```
   (with its 2026-09-29 recalibration comment above it, lines 44-49 --
   delete the comment too, it explains a line that is gone). `MODEL_LANE`/
   `MODEL_AUDIT` are already commented out (lines 57-58, retired 2026-10-10
   07:04 PDT per their own comment, before this lane started) -- delete
   those two dead lines as well while in there, they document a prior state
   nothing reads either way. No `USAGE_LOW_PCT`/`USAGE_LOW_PROJ`/
   `USAGE_NORMAL_PROJ`/`USAGE_LOW_LANE_MAX`/`PATHFIND_MODEL_CALLS_MAX` lines
   exist in the file today (grep-confirmed) -- there is nothing to remove
   for those, only `models.toml`'s `[usage]` table to keep in mind for
   future tuning. `LANE_MAX`/`BOARD_TURNS`/`LANE_TURNS`/`BOARD_FOCUS_LABEL`
   (unrelated to model choice) stay exactly as they are.

2. **The 77 legacy `$WORK/briefs/<lane>.model` files** (45 `claude-sonnet-5`,
   32 `claude-opus-5-5`): `models.sh resolve` already accepts a bare model
   id as well as a kind name (see `resolve()` in `models.py`), so **none of
   these need to change for correctness** -- Low-capping and escalation both
   already apply to a literal the same way they apply to a kind. The only
   reason to convert them: a literal freezes today's answer, so if
   `models.toml`'s `engineering`/`harness` rows ever diverge from each other
   in the future (they are both Opus/Sonnet today only because that is what
   the owner approved for both), a lane still pinned to a bare
   `claude-opus-5-5` will not follow that change the way a lane pinned to
   the kind name `engineering` would. If converting: the 32 Opus files are
   very likely `engineering` kind (JIT/renderer/shader lanes); the 45
   Sonnet files are a mix of `harness`/`audit`/`bookkeeping` work and need
   the brief (not just the model id) read to tell which -- there is no way
   to recover "kind of work" from a bare model id alone, which is exactly
   why brief item 3 asks for a kind name on every NEW `.model` file lane.sh
   writes from here on (it already does, via `token` in `next_attempt()`).

3. **`host-tools/hostops.sh:74`** (read, not edited -- host-only, outside
   this lane's territory):
   ```
   --model "${HOSTOPS_MODEL:-claude-sonnet-5}" --max-turns 80 --output-format json \
   ```
   becomes
   ```
   --model "${HOSTOPS_MODEL:-$(bash docs/testing/jobs/models.sh model bookkeeping)}" --max-turns 80 --output-format json \
   ```
   (the script already `cd`s to `/home/justin/hakuX` first, so the relative
   path resolves). Same value either way today (`bookkeeping` is Sonnet in
   both modes) -- this is for the single point of truth, not a behavior
   change.

4. **`host-tools/pm_tick.sh:16`**, same shape:
   ```
   timeout 40m /usr/bin/claude -p "$task" --model "${PM_MODEL:-claude-sonnet-5}" --max-turns 60 --output-format json \
   ```
   becomes
   ```
   timeout 40m /usr/bin/claude -p "$task" --model "${PM_MODEL:-$(bash docs/testing/jobs/models.sh model bookkeeping)}" --max-turns 60 --output-format json \
   ```
   Noticed in passing: `pm_tick.sh`'s own header comment says "Model: Opus"
   (line 2) but the code has always defaulted to `claude-sonnet-5` -- that
   comment was already stale before this lane; `bookkeeping` (Sonnet in both
   modes) matches what the code actually does today, not what the comment
   claims.

5. **Cosmetic, optional, not in this lane's territory**: `status.sh:55`
   sources the now-deleted `models.env` (`2>/dev/null`, so it does not
   error) and its lane table / footnote fall back to hardcoded display text
   `${MODEL_LANE:-opus}` / `${MODEL_LANE_ESCALATED:-fable}` -- always
   showing "opus" and "fable" (Fable is retired) rather than a real answer.
   Nothing crashes; this is a status page reading stale labels, not a wrong
   decision anywhere. Worth a one-line follow-up (read the real answer
   through `models.sh` the way every other caller now does) whenever
   `status.sh` is next touched for something else.

6. **Also found and fixed in this lane, not brief-listed**:
   `docs/testing/jobs/run-claude-job.sh` unconditionally sourced
   `jobs/models.env`; deleting that file without fixing this caller would
   have broken every scheduled job outright (`set -u` turns the unbound
   `$MODEL_AUDIT`/`$MODEL_BOOKKEEPING` into a hard abort before `claude` is
   even invoked). Fixed the same way `cloud.sh` was: resolves the `audit`/
   `bookkeeping` kind through `models.sh`, `HAKUX_MODEL` still wins. See
   NOTES.md for the four OTHER `models.env` readers that were checked and
   left alone because they already degrade to a working default.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
