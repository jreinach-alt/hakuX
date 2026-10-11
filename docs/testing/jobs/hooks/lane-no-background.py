#!/usr/bin/env python3
"""PreToolUse hook: refuse backgrounded Bash and Agent calls inside a lane session.

    docs/testing/jobs/hooks/lane-no-background.py   (reads the PreToolUse JSON on stdin)

WHY. A lane is a headless `claude -p` session; its turn ending kills the
systemd unit's cgroup, and anything still running dies with it, with no
notification ever arriving (lane.sh's LANE_SESSION_FOOTER says so in every
lane's prompt). Three lanes (surfgpudefault1009, restoreleak1009,
meterfit1010 attempt 1) backgrounded a long Bash job and ended their turn to
wait anyway, each costing a resume. A prompt is a request; this refuses the
call itself.

Agent calls are covered too: a live check (docs/lanes/lanenobg1010/NOTES.md)
showed the Agent tool is reachable and spawns in the background by default
even though "Agent" is not in jobs/allowed-tools.lane -- the allowlist does
not gate it, so only a hook can. Unlike Bash, Agent's default (the key
absent) IS background, so the check is inverted: refuse unless the caller
set run_in_background: false explicitly.

Exit code 2 is what the Claude Code docs give for "block this tool call and
feed stderr back to the model", in both interactive and -p sessions -- unlike
the JSON permissionDecision form, it needs no stdout contract to get this
refusal in front of the model as something to react to, which is the point:
a refusal with no replacement just gets retried another way.
"""
import json
import sys

BASH_REFUSAL = """REFUSED: Bash with run_in_background=true is not usable in a lane session. A lane is a headless `claude -p` session: when its turn ends, the unit's cgroup is killed, and anything backgrounded dies with it -- no notification ever arrives. Instead:
  - run it in the foreground, raising timeout (up to 600000 ms) if it needs longer; or
  - start it detached with its own output redirected to a file (e.g. `setsid nohup <cmd> > logfile 2>&1 < /dev/null &`), then poll that file in a foreground loop, within this turn, until it is done.
Never end a turn while a job of yours is still running."""

AGENT_REFUSAL = """REFUSED: Agent calls run in the background by default, and a lane session cannot wait for one that way. A lane is a headless `claude -p` session: when its turn ends, the unit's cgroup is killed, and a subagent still running dies with it -- no notification ever arrives. Instead:
  - pass run_in_background: false on the Agent call, and let it finish in the foreground before the turn ends; or
  - do the work directly in this session instead of delegating it to a subagent.
Never end a turn while a subagent of yours is still running."""


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input") or {}
    if tool_name == "Bash":
        if tool_input.get("run_in_background") is not True:
            return 0
        sys.stderr.write(BASH_REFUSAL + "\n")
        return 2
    if tool_name == "Agent":
        if tool_input.get("run_in_background") is False:
            return 0
        sys.stderr.write(AGENT_REFUSAL + "\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
