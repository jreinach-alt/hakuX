# lane.lanepath1009: lane.sh gives each lane unit a shim-first PATH with --setenv (#433, 0.5)

State: ready

Lane: lanepath1009          Issue: none (#433 umbrella)
Base: master @ 96852d8144 (origin/master merged in at 2711f2ba15 for Addendum 3)
Files: docs/testing/lane.sh, docs/testing/jobs/selftest.sh, docs/testing/jobs/selftest.d/99-lane-path.sh, docs/lanes/lanepath1009/NOTES.md, docs/lanes/lanepath1009/OUTBOX.md, docs/lanes/lanepath1009/PR.md
Prediction: none: harness fix; the evidence is the selftest and its mutants
Needs device: no    Needs NDK: no
Release note: none. Harness/test-infrastructure only (docs/testing/lane.sh and its selftest fragment); no emulator code, no player-facing change.

A lane unit's PATH came from whatever the systemd --user manager held when the unit spawned. On
2026-10-09 a WSL crash at 16:58 restarted the manager without the forge shim on its PATH, and two live
lanes (surfgpu1009, nightlynotes1009) ran part of their sessions with the real `gh` instead of the local
shim. The interim host fix (`systemctl --user set-environment` plus `~/.config/environment.d/`) only
covers spawns after a manager that has read it.

1. `docs/testing/lane.sh` adds `lane_path()`, built from two variables set once --
   `LANE_SHIM_BIN="${HAKUX_SHIM_BIN:-$WORK/forge/shim/bin}"` (an explicit override hook, added for
   Addendum 3's selftest fixtures below) and a fixed `LANE_PATH_TAIL` -- called from both `start)` and
   `resume)` before either does anything stateful. It sets `LANE_PATH` for both `systemd-run` blocks'
   `--setenv=PATH="$LANE_PATH"`, or refuses with **exit 78** and a message naming the missing directory
   if the shim dir does not exist. The caller's own `$PATH` is never read -- that was the weaker rule
   this replaces.
2. Addendum 1: a fixed `LANE_SESSION_FOOTER`, appended once to both the start and resume prompts, telling
   the spawned session it is headless and ends the moment its turn ends, so it must run long commands in
   the foreground and never end a turn with a job still running. Prompted by two Sonnet lanes
   (surfgpudefault1009, restoreleak1009) stranding uncommitted work the same night by backgrounding a job
   and ending their turn to "report back."
3. `docs/testing/jobs/selftest.d/99-lane-path.sh`, new: 29 checks against the real `lane.sh` (via the
   selftest's `systemd-run` logging shim) -- shim-first PATH in both start's and resume's logged
   `--setenv=PATH=`, byte-identical between the two, the footer present in both, four "exactly one
   assignment" structural guards, the refusal path (missing shim -> exit 78, `systemd-run` never
   reached, both directions), and the four mutants required at the time: (a) `--setenv=PATH` dropped
   from resume only, (b) the weaker rule reinstated (`--setenv=PATH="$PATH"`), (c) the shim dir moved
   after `/usr/bin`, (d) Addendum 1's footer dropped from resume only (a fifth, (e), added in Addendum 3
   below). Each mutant's literal `FAIL` output (captured via a throwaway positive-assertion harness, not
   just read off my own if/else) is in `NOTES.md`.
4. A real `systemd-run --user --unit hakux-lanepath-probe --collect` run (stub command, `--collect`,
   never a Claude session) confirms `command -v gh` inside the spawned unit resolves into the forge shim
   on the actual systemd --user manager, not just the selftest's own shim. Transcript in `NOTES.md`.
5. Per Addendum 2 (lane.local, 00:40 PDT, also relayed via a cross-session message while a full run I'd
   started was mid-flight): the brief's step 3 (run the full ~60-min selftest locally) is replaced --
   a second full suite on this host slows the fold already running tonight and flaked its
   timing-sensitive fragments under load. I killed the in-progress background run by exact PID on seeing
   the instruction and ran only `99-lane-path.sh` plus every existing fragment confirmed to exercise
   `lane.sh` (`96-fleet-registry.sh`, `88-window-budget.sh`, the `99-handback-*.sh` family), each checked
   against the unmodified baseline `lane.sh` too, to separate genuine regressions from pre-existing or
   isolation-artifact failures.

**Selftest.** `99-lane-path.sh` alone (`SELFTEST_ONLY="99-lane-path.sh"`): **32 passed, 0 failed**,
including all five mutants correctly going red.

6. Addendum 3 (lane.local, 04:50 PDT): the fold ran the full suite on `69aa814fe1` at 03:13 and found
   112 failures, all inside the 15 lane.sh-dependent fragments this PR had already identified (prior
   revision's `OUTBOX.md`) -- `lane_path()`'s refusal is correct, but no fixture's `$WORK` had a shim
   directory. Addendum 3 put `docs/testing/jobs/selftest.sh` in territory and asked for the fix applied
   directly, preferring one mechanism over three separate edits:
   - `lane.sh`: `LANE_SHIM_BIN="${HAKUX_SHIM_BIN:-$WORK/forge/shim/bin}"`, an explicit override hook.
   - `selftest.sh`: one stub shim dir under the run's `$T`, one `export HAKUX_SHIM_BIN` pointing at it,
     inherited by every fragment that calls real `lane.sh` (shared `$HAKUX_WORK` or a private one) with
     no further per-fragment edits.
   - `99-lane-path.sh`: pins its own `HAKUX_SHIM_BIN` in `lp_start`/`lp_resume` to keep full control over
     the happy/refusal paths, and adds mutant (e) -- the refusal itself dropped from `lane_path()` --
     with its own verbatim `FAIL` output in `NOTES.md`.

   Verified on exactly the 16 `SELFTEST_ONLY` fragment names the fold's failures came from: **495
   passed, 0 failed**. `OUTBOX.md` now records this as resolved rather than an open ask; no
   `~/.config`/systemd-unit edit, no real lane started/stopped/resumed.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
