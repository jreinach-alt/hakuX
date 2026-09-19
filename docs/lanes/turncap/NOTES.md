# lane.turncap -- `$WORK/limits.env` is sourced after the values it overrides are read

Brief: `$WORK/briefs/turncap.md`. Harness defect, no tracker issue.

## What was actually wrong, and the order the brief got half-right

The brief invited me to correct its own account, and it needed correcting.
The source is **below both** variables, not between them; what distinguishes
them is the **shape** of the assignment, not its position.

| file | line (before) | shape | source at | works? |
|---|---|---|---|---|
| `lane.sh` | 40 `TURNS="${LANE_TURNS:-150}"` | expansion of a *different* name | 57 | **no** |
| `lane.sh` | 48 `LANE_MAX=2` | literal assigned to the *same* name | 57 | yes |
| `cloud.sh` | 56 `TURNS="${CLOUD_TURNS:-120}"` | expansion of a *different* name | 68 | **no** |
| `cloud.sh` | 67 `LANE_MAX=$(sed …)` | same name, then `: "${LANE_MAX:=2}"` | 68 | yes |

`limits.env` assigns `LANE_MAX`, so sourcing it *overwrites* the literal above
and the override lands. It assigns `LANE_TURNS`, which is not `TURNS`; the
`${LANE_TURNS:-150}` expansion had already run and nothing re-runs it, so the
source set `LANE_TURNS` for nobody. `grep -n '^TURNS=' lane.sh` returns one
line and that line had already executed.

The same reasoning clears `models.env`: it is sourced at lane.sh:49, above
`limits.env` at 57, and every name in it is a plain assignment — so
`limits.env` overwrites them and its own comment ("overrides any line here")
is true.

## The fix

Moved the single `TURNS=` line in each script to below the `limits.env`
source. Nothing else moved.

**Why that shape and not "source earlier".** `WORK` is what *finds*
`limits.env`, so the source cannot rise above it; `REPO`/`TIP`/`GH_REPO` come
from the process environment and from `systemd-run --setenv`, and moving the
source above them would make `limits.env` able to redefine host paths, which
is new behaviour nobody asked for. Moving one line down changes exactly the
thing that was broken.

**Precedence.** The file now beats the process environment, which is what it
already did for `LANE_MAX` and for every name in `models.env`.
`jobs/window.sh:33` calls `$WORK/limits.env` "the host's dial for every number
below" — one dial. This is asserted, not assumed: see the precedence checks.

## The other four scripts, checked rather than assumed

- **`arms.sh`** — sources at 62 and reads `ARMS_MAX_PAIRS_PER_TICK` /
  `ARMS_QUEUE_MAX` at 63-64, *below*. Correct already.
- **`board.sh`** — `LANE_MAX=2` at 127 with the source at 129 (same-name
  shape, works); `BOARD_TURNS` is read at line 311 **at the point of use**,
  after `positive_gate` has run the source unconditionally at line 302. So
  `BOARD_TURNS` in `limits.env` has always worked. The host's
  `set-environment BOARD_TURNS=120` was never load-bearing.
- **`run-claude-job.sh`** — sources at 38 but takes `turns` as `$4` from its
  caller; no dial of its own.
- **`status.sh` / `board-status.sh`** — source before reading. Correct.

**Are the host-path variables ever expected in `limits.env`?** No, and one of
them cannot be. `HAKUX_WORK` is the variable that locates `limits.env`, so
setting it there is unreachable by construction. `HAKUX_REPO_DIR`,
`HAKUX_TIP`, `DISPATCH_DIR`, `GOLDENS` and `GH_REPO` are set by
`systemd-run --setenv` and by `selftest.sh`'s exports, and no script, role
file or doc mentions `limits.env` as a place to set any of them —
`ORCHESTRATION-DESIGN.md:522` describes it as the concurrency cap,
`window.sh:33` as "the host's dial for every **number**". They read fine
where they are and this change does not move them.

I could not read the live `$WORK/limits.env`: the lane sandbox permits only
this worktree, so `cat /home/justin/hakux-work/limits.env` was refused. Its
contents are taken from the brief's quotation of its comment.

## The check, and the mutant

`docs/testing/jobs/selftest.d/99-limits-env.sh`, ten checks. It asserts on the
**command line `systemd-run` was actually given**, not on `$TURNS` inside the
script — a check that reads the variable passes against the broken version for
free, because by then the source has run and `LANE_TURNS` really is 300. The
global `systemd-run` shim logs its whole argv; `--max-turns N` in that log is
the only place the two versions differ.

Three deliberate guards, each of which caught something while I wrote it:

1. `env -u LANE_TURNS -u CLOUD_TURNS` on every run. The live mitigation on the
   host is `systemctl --user set-environment LANE_TURNS=300`, and the broken
   line read the process environment — a run that inherited it would go green
   against the broken code.
2. The values are **317** and **213**: not the defaults (150, 120), not the
   host's 300, not any number in `models.env`. They are reachable from one
   place only.
3. Each run removes the worktree, prunes, and deletes the local branch first.
   Without that, the second `lane.sh start` exits 3 (worktree exists) or 128
   (`worktree add -b` on an existing branch) **before** `systemd-run`, leaving
   an empty log that every `! grep` reads as a pass.

`turns_on_cmdline` is called in the parent shell, never from inside a
`bash -c`: a shell function is not exported, so `[ "$(turns_on_cmdline …)" = 317 ]`
in a child compares against the empty output of a command-not-found.

**Mutant, run against the committed fix.** Restoring each assignment to its
old position above the source and re-running:

```
  FAIL LANE_TURNS in $WORK/limits.env reaches the lane's --max-turns
  FAIL ...and the 150 default is not what was spawned
  FAIL the file wins over the process environment, as it already did for LANE_MAX
  FAIL lane.sh has exactly one TURNS= assignment and it is below the source
  FAIL CLOUD_TURNS in $WORK/limits.env reaches the audit session's --max-turns
  FAIL ...and the 120 default is not what was spawned
  FAIL the file wins over the process environment for the audit outlet too
  FAIL cloud.sh has exactly one TURNS= assignment and it is below the source
```

and the log shows `--max-turns 150` / `--max-turns 120`. The two
"with no dial set, the default is what is spawned" checks stay green under the
mutant, which is correct and is the point of including them: they pin the
default so "always 317" and "reads the file" are not the same green.

The static ordering check is anchored on `^TURNS=`, not on `TURNS=`: the
comments I added quote the broken line verbatim, so an unanchored grep matches
the prose describing the bug. It also asserts *exactly one* such line, so a
second assignment cannot drift back above the source.

## For the board: two things this lane cannot fix itself

**1. The fragment name in my own territory row is one the runner refuses.**
`[lane.turncap]` grants `docs/testing/jobs/selftest.d/101-limits-env-order.sh`.
`selftest.sh`'s loop matches `[0-9][0-9]-*.sh` and hard-exits 2 on anything
else — not "sorts wrong", *ends the run before a single check*. Measured by
dropping a `101-probe.sh` into `selftest.d/`:

```
selftest: .../101-probe.sh is not selftest.d/NN-<concern>.sh and would never be sourced
```

exit 2, zero checks, and this file is CI's gate for everything under `jobs/`.
I used **`99-limits-env.sh`** instead. `NN` is not unique (`86-` and `97-` each
appear twice on master already), so "the next free number" never required
leaving two digits. Please amend the row's `files` entry to
`docs/testing/jobs/selftest.d/99-limits-env.sh`. I did not edit
`territory.toml` (`roles/lane.md:79`), and per the sandbox note above I cannot
write a dispatch-dir board request either — this section and the PR comment
are the channel.

**2. `[lane.stalecheck]` has the same grant defect and will land it.** Its row
claims `docs/testing/jobs/selftest.d/100-stale-check.sh`, reasoning "99 taken
by lane.desktopchannel's desktop-serve". Same refusal, same blast radius: when
that fragment lands, `selftest.sh` exits 2 and every lane's CI goes red for a
reason belonging to no lane. It needs a two-digit name before it folds.

A cheaper fix than watching for it: `check_territory.py` (or the board's own
grant step) could reject a claimed path under `selftest.d/` that does not match
`[0-9][0-9]-*.sh`, since the runner already encodes the rule. I did not do this
— `check_territory.py` is `lane.toolsmith`'s and outside my grant.

## Neither of my two files was held when I started

`[retired.windowbudget]` (wave 126) released `docs/testing/lane.sh` to this
lane outright, and `[retired.cloudterritory]` released `jobs/cloud.sh`. No
scratch copy was needed.

## Once this is folded

`systemctl --user unset-environment LANE_TURNS BOARD_TURNS` can be run on the
host. **Not before** — until the fix lands, that manager environment is the
only thing holding lanes at 300, and `lane.sh` reading the process environment
at line 40 is exactly why it works. I did not clear it. Note that
`BOARD_TURNS` in that pair was never needed (see `board.sh` above); it is the
`LANE_TURNS` half that was doing the work.

## What the next lane should not repeat

- Do not add a check that reads `$TURNS` from inside `lane.sh`. It is green
  against both versions.
- Do not run the selftest to validate a `limits.env` change without
  `env -u`-ing the dial out of the environment first. The host sets it.
- Do not trust a `selftest.d/` filename handed to you by a territory grant
  without checking it against the runner's `[0-9][0-9]-*.sh` glob.

## Status

- `bash docs/testing/jobs/selftest.sh`: **676 → 686 passed, 0 failed.**
- Prediction: none (harness change, no pixels).
