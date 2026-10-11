lane.lanenobg1010 -- lane sessions refuse background commands with a hook, not a footer (#433, 0.5)
State: ready

Lane: lanenobg1010      Issue: #433 (umbrella), none filed
Base: master @ 9dc20e31f9
Files: docs/testing/lane.sh, docs/testing/jobs/hooks/lane-no-background.py, docs/testing/jobs/lane-settings.json, docs/testing/jobs/selftest.d/99-lane-no-background.sh, docs/lanes/lanenobg1010/**
Prediction: none: harness fix, no arm
Needs device: no
Needs NDK: no

Release note (none): harness/testing-infra change, not emulator code.

A PreToolUse hook (`lane-no-background.py`) refuses two calls from a lane
session: `Bash` with `tool_input.run_in_background == true`, and `Agent`
unless `tool_input.run_in_background == false` is given explicitly (Agent
defaults to background, confirmed by an empirical run showing a subagent
spawned and completed in background mode even though `Agent`/`Task` is not
in `allowed-tools.lane`). Every other call passes untouched. Each refusal
names both replacements -- run it in the foreground with `timeout` raised
(up to 600000 ms), or detach it with output redirected to a file and poll
that file in a foreground loop -- and says never to end a turn with a job
still running. `lane-settings.json` holds only this hook and is passed via
`--settings` on both `lane.sh`'s start and resume command lines; `--settings`
adds to project settings rather than replacing them (per `claude --help`'s
description of `--settings` as additive, and `--restricted`'s help text
calling out `--settings` as a layer that survives even when other settings
files are ignored), so `.claude/settings.json`'s own hooks are unaffected.
`.claude/settings.json`, `roles/lane.md` and `allowed-tools.lane` are
untouched. `LANE_SESSION_FOOTER` is unchanged; the hook enforces it, it
does not replace it.

Live check (brief step 5, haiku, `--max-turns 3`, `--settings
docs/testing/jobs/lane-settings.json`, prompt asking it to background a
`sleep 2`): the hook refused the call and the model's own report quoted the
refusal's replacement text verbatim. `total_cost_usd`: **0.0360998 USD**
(session `5e09c101-f735-46e3-a65b-8a8512846002`).

Selftest: fragment in isolation (`SELFTEST_ONLY=99-lane-no-background`),
**24 passed, 0 failed**. Full suite, foreground, four shards
(`SELFTEST_SHARD=N/4`): **3279 passed, 0 failed, 132 of 132 fragments**.
Mutant proof: two sed'd copies of the hook, each inverting one of its two
checks (`norbgcheck` inverts the Bash `run_in_background is not True`
check; `noagentcheck` inverts the Agent `is False` check) -- both flip the
corresponding selftest case from pass to fail, shown in the fragment's own
output.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
