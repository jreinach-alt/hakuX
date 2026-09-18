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
# Overridable so the issue-blind path can be exercised without unplugging the
# network. A gate whose failure branch has never run is not a gate.
REPO = os.environ.get("HAKUX_REPO", "jreinach-alt/hakuX")


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
    # The board lives on the `board` branch when it exists, and in the tree
    # until then; board_files says which was read, so a stale local copy is
    # never quoted as a live one (docs/ORCHESTRATION-DESIGN.md §5).
    sys.path.insert(0, HERE)
    import board_files
    terr = board_files.load("territory.toml")
    tracker = board_files.load("nv2a_issues.toml")["issue"]
    print("board read from: territory.toml <- %s, nv2a_issues.toml <- %s"
          % (board_files.source("territory.toml"),
             board_files.source("nv2a_issues.toml")))

    # A TIMEOUT, BECAUSE THE RISK HERE IS A STALL AND NOT THE RATE LIMIT.
    #
    # Measured 2026-09-14: the token's core and graphql limits are both
    # 5,000/hour with 0 used, and `gh issue list` returns in well under a
    # second. Even a call per watchdog poll could not approach the limit --
    # and the watchdog does not poll this anyway, because check_coverage.py
    # only runs once the session has been idle and armed, not every 20s.
    #
    # So caching would solve a problem that does not exist. What DID need
    # fixing is that this call had no timeout at all: a hung `gh` -- an auth
    # prompt, a wedged connection -- blocks forever, and anything that invokes
    # this from a poll loop then stops reporting the fleet at exactly the
    # moment the fleet is stuck. Fail fast and say the report is issue-blind.
    try:
        r = subprocess.run(["gh", "issue", "list", "--repo", REPO,
                            "--state", "open", "--limit", "80",
                            "--json", "number,title"],
                           capture_output=True, text=True, timeout=30)
        ok = r.returncode == 0
    except Exception as e:
        r, ok = None, False
        print("gh did not answer (%s)" % e, file=sys.stderr)
    if not ok:
        print("cannot reach gh; fleet report is issue-blind -- the "
              "DISPATCHABLE section below is EMPTY BECAUSE IT WAS NOT "
              "COMPUTED, which is not the same as nothing being dispatchable",
              file=sys.stderr)
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

    # THE OTHER DIRECTION, AND IT IS THE WORSE ONE: an agent that is RUNNING
    # with no row in territory.toml at all.
    #
    # `ghost` above catches a claim with no agent -- coverage asserted that
    # does not exist, which over-reports and is conservative. This catches an
    # agent with no claim, and that one is invisible to EVERY guard, because
    # check_territory.py cannot see a lane that is not in the file. None of
    # the checks that caught real collisions on 2026-09-13 could have fired
    # for it.
    #
    # Three occurrences in one night, each a different variant, which is why
    # it is bit=3 in papercuts.toml and a rule in AGENTS.md rather than three
    # corrections: no row written at all (lane.padwrite, which then edited
    # three files, and nothing collided only because nothing else wanted them
    # that hour); a row written and validated but COMMITTED AFTER DISPATCH, so
    # the lane fast-forwarded to a tip that predated it and spent its whole
    # life against a table where its files sat in [free] (lane.tcginval); and
    # no row because an auditor claims no files (lane.audit-tcg). AGENTS.md:
    # "the brief is not the claim, and an uncommitted claim is not a claim
    # either."
    #
    # A LANE WITH `files = []` STILL COUNTS AS CLAIMED. The row is what
    # matters, not the territory -- an auditor that edits nothing still has to
    # be visible to the board, and requiring files would re-create the third
    # variant exactly.
    #
    # WHAT THIS CANNOT SEE: a lane running with no fleet row EITHER. Both
    # sides of this cross-check are written by the orchestrator, so an agent
    # dispatched without touching either file is as invisible here as it is to
    # check_territory.py. That is the residual hole, it is not closable from
    # this side, and it is why AGENTS.md orders the steps "write the row,
    # validate, commit, PUSH, then dispatch".
    unclaimed = sorted(f["lane"] for f in fleet
                       if f.get("state") == "running"
                       and f["lane"] not in (terr.get("lane") or {}))

    # DISPATCHABLE: open, not owned by a lane with a running agent, and with
    # no blocker -- or a blocker that has never been tested. A blocker is a
    # claim (AGENTS.md), and five of this campaign's were false this week.
    #
    # I TRIED TO DETECT AN UNTESTED BLOCKER FROM ITS PROSE AND IT DOES NOT
    # WORK. Measured 2026-09-14 over all 23 blockers in the tracker, scoring
    # each for six candidate signals of having been tested -- the words
    # MEASURED/REFUTED/VERIFIED, an ISO date, a quantity with units, a capture
    # key, a named tool, a source file:
    #
    #     MEASURED/REFUTED/verified     5 of 23
    #     an ISO date                  13 of 23
    #     a number with units/px        8 of 23
    #     names a capture key           7 of 23
    #     names a tool/command          8 of 23
    #     names a source file           15 of 23
    #     NO signal at all              3 of 23
    #
    # Twenty of 23 carry at least one signal, so the rule flags almost
    # nothing. Worse, it flags the WRONG three: #68, #69 and #73 are the only
    # signal-free blockers and all three are sound scope decisions ("belongs
    # to the tier-1 owner; blast radius is every guest instruction"), not
    # guesses. The signals separate TECHNICAL prose from POLICY prose, which
    # is not the question.
    #
    # And there is a reason no text rule can work: THE TRACKER RECORDS A
    # REFUTATION IN THE SAME FIELD AS THE CLAIM. Once a blocker is disproved
    # the field is rewritten to say so, so the refuted ones read as the
    # best-evidenced ones afterwards -- #59's now opens "NOT A TERRITORY
    # PROBLEM AT ALL, MEASURED 2026-09-14". Before the test it read
    # confidently too. A classifier cannot see a tense.
    #
    # So this asks for a STRUCTURED claim instead of sniffing prose, which is
    # what AGENTS.md already asks for in words: "Write the blocker down in the
    # form of the measurement that would refute it". An entry carries
    # `blocker_falsifier` (what would show the blocker is false) and
    # `blocker_tested` (when it was last run) or it does not, and only the
    # absence is reportable. nv2a_issues.toml is the ORCHESTRATOR's file, so
    # this reads those keys and does not invent them: until they are written
    # every blocker reports UNTESTED, which is accurate -- none of them has
    # ever been recorded as tested -- and is listed separately from the
    # genuinely unblocked so it cannot be mistaken for a dispatch queue.
    dispatchable = []
    untested = []
    for n in sorted(live, key=int):
        lane = owned.get(n)
        if lane and lane in lanes_with_agent:
            continue
        ent = tracker.get(n, {})
        b = (ent.get("blocked_on") or "").strip()
        why = "no blocker" if not b else None
        if b and "NOT BLOCKED" in b.upper():
            why = "blocker says NOT BLOCKED"
        if why:
            dispatchable.append((n, lane, why, titles.get(n, "")[:52]))
        elif b and not (ent.get("blocker_tested") or "").strip():
            untested.append((n, lane, (ent.get("blocker_falsifier") or "").strip(),
                             titles.get(n, "")[:52]))

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
    print("\n=== RUNNING WITH NO TERRITORY ROW (%d)" % len(unclaimed))
    if unclaimed:
        print("  Invisible to every guard: check_territory.py cannot see a "
              "lane that is not in the file.")
    for lane in unclaimed:
        f = next(x for x in fleet if x["lane"] == lane)
        print("  %-12s %-18s #%-14s %s"
              % (lane, f.get("agent", "")[:18],
                 ",".join(f.get("issues") or []) or "-",
                 age(f.get("dispatched_utc", ""))))
        print("      asked: %s" % (f.get("asked", "")[:96]))
    print("\n=== DISPATCHABLE NOW, NOT DISPATCHED (%d)" % len(dispatchable))
    for n, lane, why, title in dispatchable:
        print("  #%-4s %-12s %-26s %s" % (n, lane or "-", why, title))

    # SEPARATE SECTION, AND DELIBERATELY NOT PART OF THE EXIT CODE. These are
    # not known-dispatchable; they are blockers nobody has recorded testing.
    # Folding them into the FAIL above would say the board is holding work it
    # can start, which is a stronger claim than the evidence supports.
    print("\n=== BLOCKER NEVER RECORDED AS TESTED (%d)" % len(untested))
    if untested:
        print("  A blocker is a claim. Five were refuted in two days, two of"
              " them the orchestrator's own.")
    for n, lane, fals, title in untested:
        print("  #%-4s %-12s %-30s %s"
              % (n, lane or "-",
                 ("falsifier: " + fals[:24]) if fals else "NO FALSIFIER WRITTEN",
                 title))

    # SAME LIVE-PLUS-DISK MIX AS check_coverage.py, SO THE SAME QUALIFIER.
    # This reads open issues live from GitHub and territory.toml/
    # nv2a_issues.toml from whatever checkout it is standing in. Run from a
    # stale worktree, every section above is a statement about that checkout,
    # and "DISPATCHABLE NOW" is the one most likely to be acted on.
    try:
        out = subprocess.run(
            ["git", "-C", HERE, "rev-list", "--count", "HEAD..%s"
             % os.environ.get("HAKUX_TIP",
                              "master")],
            capture_output=True, text=True, timeout=15)
        behind = int(out.stdout.strip()) if out.returncode == 0 else None
    except Exception:
        behind = None
    if behind:
        print("\nSTALE CHECKOUT: %d commit(s) behind the campaign tip. The "
              "issue list above is live and the two toml files are from this "
              "tree, so rebase before acting on any of it." % behind)

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
    # NON-ZERO, LIKE THE OTHERS. `ghost` is printed and deliberately does not
    # set rc, because a stale claim OVER-reports coverage and that errs safe.
    # This one UNDER-reports it: the lane is editing files nothing knows it
    # holds, so a second lane can be handed the same file and both preflights
    # will pass.
    if unclaimed:
        print("FAIL: %d lane(s) are RUNNING with no territory row -- %s. "
              "Nothing can see them: check_territory.py cannot detect a "
              "collision with a lane that is not in the file. Write the row, "
              "validate, commit, PUSH."
              % (len(unclaimed), ", ".join(unclaimed)), file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
