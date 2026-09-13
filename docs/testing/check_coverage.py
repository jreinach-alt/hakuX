#!/usr/bin/env python3
"""Fail if an open issue has neither a lane nor a written blocker.

    check_coverage.py            # needs `gh`; FAILS OPEN without it

An issue with no owner and no recorded reason it cannot proceed reads as
unfinished work nobody picked up. That is not a bookkeeping nicety: an
orchestrator scanning the board sees a gap and either re-dispatches work that
is genuinely blocked, or skips work that is genuinely available.

WHY THIS IS A SCRIPT. On 2026-09-13 an ad-hoc audit of 24 open issues found
exactly one in that state -- #53 -- whose blocker was real, established, and
recorded only in conversation. The orchestrator had asserted "every issue has
a lane or a blocker" and was wrong by one. A claim like that should be checked,
not asserted, which is the rule the rest of this campaign runs on.

An issue is covered if EITHER:

  - some lane in territory.toml lists it in `issues`, or
  - its nv2a_issues.toml entry carries a non-empty `blocked_on`.

FAILS OPEN on no `gh` and no network, deliberately. A blip must not make this
unpushable, and the same choice is made by backlog-gate.sh for the same
reason. It says which of the two happened rather than printing a bare pass.
"""
import json
import os
import subprocess
import sys
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("HAKUX_REPO", "jreinach-alt/hakuX")


def open_issues():
    try:
        out = subprocess.run(
            ["gh", "issue", "list", "--repo", REPO, "--state", "open",
             "--limit", "200", "--json", "number,title"],
            capture_output=True, text=True, timeout=40)
    except Exception as e:
        return None, "could not run gh: %s" % e
    if out.returncode != 0:
        return None, (out.stderr or "gh failed").strip().splitlines()[0]
    try:
        return json.loads(out.stdout), None
    except Exception as e:
        return None, "could not parse gh output: %s" % e


def main():
    with open(os.path.join(HERE, "territory.toml"), "rb") as fh:
        terr = tomllib.load(fh)
    with open(os.path.join(HERE, "nv2a_issues.toml"), "rb") as fh:
        tracker = tomllib.load(fh)["issue"]

    owned = {}
    for lane, meta in (terr.get("lane") or {}).items():
        for i in meta.get("issues", []):
            owned[str(i)] = lane
    blocked = {k: v["blocked_on"] for k, v in tracker.items()
               if (v.get("blocked_on") or "").strip()}

    issues, err = open_issues()
    if issues is None:
        print("coverage NOT CHECKED: %s" % err)
        print("  (failing open -- a network blip must not make this unpushable)")
        return 0

    gaps = []
    for r in issues:
        n = str(r["number"])
        if n in owned or n in blocked:
            continue
        gaps.append((n, r["title"]))

    if gaps:
        print("FAIL: %d open issue(s) with neither a lane nor a blocker:"
              % len(gaps), file=sys.stderr)
        for n, t in gaps:
            print("  #%s  %s" % (n, t[:72]), file=sys.stderr)
        print("\n  Give it a lane in territory.toml, or write `blocked_on` on\n"
              "  its nv2a_issues.toml entry saying what it is waiting for.\n"
              "  A blocker is a claim: state it as the measurement that would\n"
              "  refute it, not as a reason to stop.", file=sys.stderr)
        return 1

    print("coverage ok (%d open: %d owned by a lane, %d with a written blocker)"
          % (len(issues),
             sum(1 for r in issues if str(r["number"]) in owned),
             sum(1 for r in issues if str(r["number"]) in blocked
                 and str(r["number"]) not in owned)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
