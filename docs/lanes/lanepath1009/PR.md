# lane.lanepath1009: lane.sh gives each lane unit a shim-first PATH with --setenv (#433, 0.5)

State: ready

Lane: lanepath1009          Issue: none (#433 umbrella)
Base: master @ 96852d8144
Files: docs/testing/lane.sh, docs/testing/jobs/selftest.d/99-lane-path.sh, docs/lanes/lanepath1009/NOTES.md, docs/lanes/lanepath1009/OUTBOX.md, docs/lanes/lanepath1009/PR.md
Prediction: none: harness fix; the evidence is the selftest and its mutants
Needs device: no    Needs NDK: no
Release note: none. Harness/test-infrastructure only (docs/testing/lane.sh and its selftest fragment); no emulator code, no player-facing change.

A lane unit's PATH came from whatever the systemd --user manager held when the unit spawned. On
2026-10-09 a WSL crash at 16:58 restarted the manager without the forge shim on its PATH, and two live
lanes (surfgpu1009, nightlynotes1009) ran part of their sessions with the real `gh` instead of the local
shim. The interim host fix (`systemctl --user set-environment` plus `~/.config/environment.d/`) only
covers spawns after a manager that has read it.

1. `docs/testing/lane.sh` adds `lane_path()`, built from two variables set once --
   `LANE_SHIM_BIN="$WORK/forge/shim/bin"` and a fixed `LANE_PATH_TAIL` -- called from both `start)` and
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
   reached, both directions), and all four required mutants: (a) `--setenv=PATH` dropped from resume
   only, (b) the weaker rule reinstated (`--setenv=PATH="$PATH"`), (c) the shim dir moved after
   `/usr/bin`, (d) Addendum 1's footer dropped from resume only. Each mutant's literal `FAIL` output
   (captured via a throwaway positive-assertion harness, not just read off my own if/else) is in
   `NOTES.md`.
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

**Selftest.** `99-lane-path.sh` alone (`SELFTEST_ONLY="99-lane-path.sh"`): **29 passed, 0 failed**,
including all four mutants correctly going red.

**Outside this lane's territory, named in `OUTBOX.md` rather than edited here** (territory is
`docs/lanes/lanepath1009/**`, `docs/testing/lane.sh`, `docs/testing/jobs/selftest.d/99-lane-path.sh`
only): the new exit-78 refusal is correct and asked for, but it breaks 32 checks across
`96-fleet-registry.sh`, `88-window-budget.sh` and five `99-handback-*.sh` fragments, each of which calls
the real `lane.sh start`/`resume` against a fixture `$WORK` with no `forge/shim/bin` directory --
confirmed as a genuine regression (not pre-existing) by running each against the unmodified baseline
`lane.sh` too, where it is clean. Each fix is a one-line `mkdir -p` addition; full table and exact lines
in `OUTBOX.md` and `NOTES.md`.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
