# CLAUDE.md

Instructions for this repository live in **[`AGENTS.md`](AGENTS.md)**, which is
the canonical file for all coding agents. Read it before making changes.

It is kept as a single file deliberately: two sets of agent instructions drift,
and a stale one is worse than none.

Claude Code specifics:

- The Android build is long-running. Prefer `run_in_background` with a wait loop
  on `GRADLE_EXIT=` rather than blocking a foreground call.
- Device work needs `adb`. Read the "Working with a device" table in `AGENTS.md`
  before injecting input — the obvious approach terminates the emulator.
- Avoid `pkill -f <pattern>` where the pattern can match your own shell; it
  will kill the tool call. Kill by PID. `pgrep -f` has the same blind spot:
  the pattern is in your own shell's command line, so a wait loop on it waits
  for yourself. Wait on a PID, or on a line in the job's log.
- Do not put a scratch script in the working directory with a stdlib module's
  name. A file called `bisect.py` or `dis.py` next to your work will shadow the
  standard library and be executed by unrelated imports.
