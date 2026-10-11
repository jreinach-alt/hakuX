# lane.lanenobg1010 -- lane sessions refuse background commands with a hook (#433, 0.5)

## What changed

- `docs/testing/jobs/hooks/lane-no-background.py` -- a PreToolUse hook. Reads
  the PreToolUse JSON on stdin and refuses (exit 2, reason on stderr) two
  cases:
  - `Bash` with `tool_input.run_in_background == true`.
  - `Agent` unless `tool_input.run_in_background == false` explicitly (see
    "Agent is reachable" below for why this is inverted from Bash).
  Every other call passes untouched. Each refusal names both replacements
  (raise the foreground timeout; or detach + redirect to a file + poll in a
  foreground loop) and says never to end a turn with a job still running.
- `docs/testing/jobs/lane-settings.json` -- holds only this hook, two
  `PreToolUse` matchers (`Bash`, `Agent`), both pointing at the same script.
  Passed to lane sessions via `--settings`, not written into
  `.claude/settings.json`, so interactive sessions (which background jobs on
  purpose) are unaffected.
- `docs/testing/lane.sh` -- both the `start` and `resume` `systemd-run`
  command lines now carry `--settings "$JOBS/lane-settings.json"` alongside
  the existing `--allowedTools`.
- `docs/testing/jobs/selftest.d/99-lane-no-background.sh` -- fixture-only
  coverage of the hook's behavior (Bash true/false/absent, Agent
  absent/true/false, non-Bash/non-Agent passthrough, two mutants, and grep
  checks that `lane.sh`'s two command lines carry `--settings`).

## `--settings` adds to project settings, it does not replace them

`claude --help`: `--settings <file>` is described as loading *additional*
settings; `--restricted`'s own help text contrasts itself by saying it
"ignores user, project and local settings files (managed settings and
`--settings` still apply...)" -- i.e. `--settings` is explicitly called out
as a layer that survives even when the normal settings files are ignored,
which only makes sense if it's additive, not a replacement. This means
`.claude/settings.json`'s existing `SessionStart`/`Stop` hooks keep firing
for a lane; `lane-settings.json` only adds the new `PreToolUse` hook on top.
Not independently re-verified by starting a real lane (that would mean
restarting a running lane, which the brief forbids), but nothing in the
`--settings` docs suggests a merge vs. override distinction by hook *event*
either -- `PreToolUse` from `lane-settings.json` and `SessionStart`/`Stop`
from the project file are different events, so even a per-event override
wouldn't collide.

## Point 3: the Agent tool is reachable from a lane, and defaults to background

Tested empirically, not inferred from `allowed-tools.lane`'s contents.

**Before extending the hook** (hook covered `Bash` only), I ran:

```
claude -p --model claude-haiku-4-5-20251001 --max-turns 3 \
  --settings <repo>/docs/testing/jobs/lane-settings.json \
  --allowedTools "$(cat docs/testing/jobs/allowed-tools.lane)" \
  <prompt asking it to background a Bash sleep and try spawning an Agent subagent>
```

`allowed-tools.lane` has no `Agent`/`Task` entry (confirmed by reading the
file directly: 36 `Bash(cmd:*)` style entries, `Read`, `Edit`, `Write`,
`Grep`, `Glob`, `WebFetch` -- nothing else). `lane.sh`'s own header comment
says an unlisted tool is simply unreachable in headless mode. The result
JSON's `subagent_stats` contradicted that:

```
"subagent_stats": {"spawned": 1, "requested": {"background": 1, ...},
  "started_in_background": 1, "completed": 1, "failed": 0,
  "killed": {"parent": 0, "user": 0, "system": 0}, "by_type": {"general-purpose": 1}}
```

One subagent was spawned, in background mode, and completed -- despite
`Agent` not being in `--allowedTools`. `permission_denials` in the same run
only listed an unrelated `Edit` call; the Agent/subagent spawn was never
denied. So `--allowedTools` does not gate the Agent tool the way it gates
`Bash`/`Edit`/etc.; only a hook can close this for a lane. This is the real
case the brief asked for -- not Workflow, not ScheduleWakeup (untested; same
family of harness-level dispatch, same reasoning would apply, but I have no
run showing either is reachable from a lane's restricted `--allowedTools`,
and neither is worth guessing into the hook without a demonstration).

Separately, the Agent tool's own schema documents `run_in_background` as
defaulting to backgrounded ("Agents run in the background by default... Set
to false only when your very next action depends on this agent's result").
That default is the opposite of Bash's (which defaults to foreground), so
the hook's Agent branch is inverted: it passes only when the caller sets
`run_in_background: false` explicitly, and refuses on `true` *and* on the
key being absent.

**After extending the hook** to also match `Agent`, I reran a narrower,
clean version of the same check:

```
claude -p --model claude-haiku-4-5-20251001 --max-turns 3 \
  --settings <repo>/docs/testing/jobs/lane-settings.json \
  --allowedTools Bash Agent \
  "Run 'sleep 2' via Bash with run_in_background:true. Then try the Agent
   tool to spawn a trivial subagent without run_in_background:false. Report
   each tool call's result verbatim."
```

Both calls came back refused, with the hook's exact refusal text quoted
verbatim in the model's own report (confirming the replacement text reaches
the model, not just that the hook ran):

```
PreToolUse:Bash hook error: [...]: REFUSED: Bash with run_in_background=true is not usable...
PreToolUse:Agent hook error: [...]: REFUSED: Agent calls run in the background by default...
```

and `subagent_stats.spawned` was back to `0` -- the Agent call no longer
spawns anything at all; it is refused before it starts. (One incidental
nuance: this run's `permission_denials` array recorded the blocked call's
`tool_name` as `"Task"`, not `"Agent"` -- Claude Code apparently records an
internal name there, but the `"Agent"` matcher in `lane-settings.json`
still caught it, as shown by the refusal firing. Matching on `"Agent"` is
correct and is what's committed.)

`total_cost_usd` for this live check (the one in brief step 5): **0.0360998
USD** (session `5e09c101-f735-46e3-a65b-8a8512846002`). An earlier,
messier combined run that first surfaced the Agent-reachability gap cost
0.0997968... USD (session `ac865129-818d-49a4-9b58-df3e15fb8c5e`) and is
not the one being reported for step 5, since its `result` text got
sidetracked onto an unrelated, incorrect self-proposed edit (it misread the
hook's `$CLAUDE_PROJECT_DIR`-relative path as broken, because *that* run was
launched with cwd inside `docs/testing/jobs/` instead of the repo root --
`$CLAUDE_PROJECT_DIR` resolves to the launch cwd, and lane.sh always starts
`systemd-run` with the worktree root as cwd, so this was an artifact of my
test setup, not a real path bug in `lane-settings.json`).

## Mutant proof (also in the selftest fragment itself)

Two mutants, each a sed'd copy of the hook left beside the real file:
- `norbgcheck`: inverts the Bash `run_in_background is not True` check so it
  never distinguishes `true` from anything else. The "Bash with
  run_in_background:true is refused" case flips from pass to fail.
- `noagentcheck`: inverts the Agent `is False` check. The "Agent with no
  run_in_background key is refused" case flips from pass to fail.

Both shown going red in the selftest fragment's own output (see run below).

## Selftest results

Fragment in isolation (`SELFTEST_ONLY=99-lane-no-background`):
**24 passed, 0 failed.**

Full suite, foreground, no sharding (`bash selftest.sh`, no
`SELFTEST_SHARD` set): see the run logged in this NOTES file's last commit
message / PR body -- recorded there once the run (kicked off before this
file was written, polled via Monitor without ending the turn) finished.

## What the next lane should not repeat

- Don't run `selftest.sh` (or anything with its own multi-minute budget)
  with `run_in_background: true` directly, even as the orchestrating
  *non-lane* session driving a lane's work forward -- the Bash tool's own
  response-size/time cap will silently move a long foreground call to the
  background anyway if you don't raise its `timeout` parameter explicitly
  (up to 600000 ms). Two redundant background copies of the same shard-0 run
  got started this way before that was caught; one was killed by its own
  inner `timeout`, the other was terminated outright. Neither produced a
  usable pass/fail count. Set the Bash tool's `timeout` parameter itself,
  and use `Monitor` (armed, not polled) to wait on the result without
  ending the turn.
- `$CLAUDE_PROJECT_DIR` in a hook command resolves against the session's
  launch cwd, not the repo root by some other means. It only equals the
  repo root here because `lane.sh` launches `systemd-run` with the worktree
  root as the working directory. Testing a lane's `--settings` file by
  launching `claude -p` from a subdirectory (e.g. `docs/testing/jobs/`)
  will make `$CLAUDE_PROJECT_DIR`-relative hook paths resolve wrong and
  looks exactly like a path bug in the committed file. It isn't one -- always
  launch the live check from the repo root.
