#!/usr/bin/env python3
"""What every agent is doing, what is waiting on the orchestrator, and what
could be dispatched right now and is not.

WHY THIS EXISTS. The orchestrator tracked the fleet in its own context. That
fails in four ways, all of which happened on 2026-09-14:

  - `ListAgents` ages out completed subagents. Six ran; three were listed.
  - A report says what an agent DID. Nothing recorded what it was ASKED, so
    after a context compaction the brief is gone and the work cannot be
    judged against it.
  - Nothing recorded that an agent was BLOCKED ON THE ORCHESTRATOR.
    lane.padwrite needed one line in vk/instance.c -- a file outside its
    four -- and said so in its final report. It sat until somebody read prose.
  - Nothing recorded whether a lane's output had been FOLDED. A lane that has
    reported and not been folded is invisible: territory still shows its claim,
    coverage still shows its issues owned, and the branch does not have its work.

And the failure that prompted this: #54 and #77 were reported as Nova-blocked
for a whole session on a claim -- "Galleon lives only on that handheld" --
that one read-only `device_titles thor` refutes. Nothing on disk could say
"these are dispatchable and nobody has dispatched them", so nobody asked.

THE REGISTRY is $DISPATCH_DIR/fleet/<lane>.json, written by the ORCHESTRATOR
when it dispatches and updated when a report lands. It is deliberately not
written by agents: an agent cannot be trusted to record that it is stuck, and
the whole point is to make the orchestrator's own bookkeeping checkable.

  lane, agent, issues[], asked, dispatched_utc, state, waiting_on, worktree

  state: running | reported | folded | retired
  waiting_on: "" or one line naming what the ORCHESTRATOR owes it
"""
import datetime, json, os, subprocess, sys, tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
REPO = "jreinach-alt/hakuX"


def load_fleet():
    out = []
    fdir = os.path.join(D, "fleet")
    if not os.path.isdir(fdir):
        return out
    for fn in sorted(os.listdir(fdir)):
        if fn.endswith(".json"):
            try:
                out.append(json.load(open(os.path.join(fdir, fn))))
            except Exception as e:
                print("  UNREADABLE %s: %s" % (fn, e), file=sys.stderr)
    return out


def age(iso):
    try:
        t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=datetime.timezone.utc)
        h = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600
        return "%.1fh" % h
    except Exception:
        return "?"


def main():
    fleet = load_fleet()
    with open(os.path.join(HERE, "territory.toml"), "rb") as fh:
        terr = tomllib.load(fh)
    with open(os.path.join(HERE, "nv2a_issues.toml"), "rb") as fh:
        tracker = tomllib.load(fh)["issue"]

    r = subprocess.run(["gh", "issue", "list", "--repo", REPO, "--state", "open",
                        "--limit", "80", "--json", "number,title"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("cannot reach gh; fleet report is issue-blind", file=sys.stderr)
        live, titles = set(), {}
    else:
        rows = json.loads(r.stdout)
        live = {str(x["number"]) for x in rows}
        titles = {str(x["number"]): x["title"] for x in rows}

    owned = {}
    for lane, meta in (terr.get("lane") or {}).items():
        for i in meta.get("issues", []):
            owned[str(i)] = lane
    lanes_with_agent = {f["lane"] for f in fleet if f.get("state") == "running"}

    running = [f for f in fleet if f.get("state") == "running"]
    unfolded = [f for f in fleet if f.get("state") == "reported"]
    waiting = [f for f in fleet if (f.get("waiting_on") or "").strip()]

    # A lane row with no running agent is coverage that does not exist. This is
    # the state territory.toml's own [free] comment warns about, and nothing
    # could detect it before.
    ghost = sorted(lane for lane in (terr.get("lane") or {})
                   if lane not in {f["lane"] for f in fleet}
                   or next((f for f in fleet if f["lane"] == lane), {})
                   .get("state") in ("reported", "retired"))

    # DISPATCHABLE: open, not owned by a lane with a running agent, and with
    # no blocker -- or a blocker that has never been tested. A blocker is a
    # claim (AGENTS.md), and two of this campaign's were false this week.
    dispatchable = []
    for n in sorted(live, key=int):
        lane = owned.get(n)
        if lane and lane in lanes_with_agent:
            continue
        b = (tracker.get(n, {}).get("blocked_on") or "").strip()
        why = "no blocker" if not b else None
        if b and "NOT BLOCKED" in b.upper():
            why = "blocker says NOT BLOCKED"
        if why:
            dispatchable.append((n, lane, why, titles.get(n, "")[:52]))

    print("=== RUNNING (%d)" % len(running))
    for f in running:
        print("  %-12s %-18s #%-14s %s" % (f["lane"], f.get("agent", "")[:18],
                                           ",".join(f.get("issues") or []) or "-",
                                           age(f.get("dispatched_utc", ""))))
        print("      asked: %s" % (f.get("asked", "")[:96]))
    print("\n=== REPORTED, NOT FOLDED (%d)" % len(unfolded))
    for f in unfolded:
        print("  %-12s #%-14s reported %s" % (f["lane"],
                                              ",".join(f.get("issues") or []),
                                              age(f.get("reported_utc", ""))))
    print("\n=== WAITING ON THE ORCHESTRATOR (%d)" % len(waiting))
    for f in waiting:
        print("  %-12s %s" % (f["lane"], f["waiting_on"][:100]))
    print("\n=== LANE CLAIMED WITH NO RUNNING AGENT (%d)" % len(ghost))
    for lane in ghost:
        print("  %-12s holds %d file(s), issues %s"
              % (lane, len((terr["lane"][lane].get("files") or [])),
                 ",".join(str(i) for i in (terr["lane"][lane].get("issues") or []))))
    print("\n=== DISPATCHABLE NOW, NOT DISPATCHED (%d)" % len(dispatchable))
    for n, lane, why, title in dispatchable:
        print("  #%-4s %-12s %-26s %s" % (n, lane or "-", why, title))

    rc = 0
    if waiting:
        print("\nFAIL: %d lane(s) are blocked on the orchestrator." % len(waiting),
              file=sys.stderr)
        rc = 1
    if dispatchable:
        print("FAIL: %d issue(s) could be dispatched and are not." % len(dispatchable),
              file=sys.stderr)
        rc = 1
    if unfolded:
        print("FAIL: %d lane(s) have reported and been left unfolded -- their "
              "claim still reads as coverage." % len(unfolded), file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
