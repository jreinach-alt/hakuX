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
import re
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

    # A `blocked_on` that describes AVAILABLE WORK is not a blocker, and this
    # gate accepted any non-empty string until it let two through. #54's read
    # "the fix is one site in the texture upload path and wants its own arm"
    # and #65's "one constant, wants an arm" -- both of which say the work is
    # ready, in a field whose whole purpose is to say it is not. The board then
    # showed them as covered and they sat.
    #
    # So reject the phrases that mean "dispatchable". This cannot catch a
    # blocker that is merely wrong, but it catches the one shape that has
    # actually occurred: a next step written into the blocker field.
    NOT_A_BLOCKER = ("wants an arm", "wants its own arm", "needs an arm",
                     "wants a lane", "needs a lane", "ready to dispatch",
                     "just needs", "simply needs")
    mislabelled = sorted(k for k, v in blocked.items()
                         if any(p in v.lower() for p in NOT_A_BLOCKER))

    # DRIFT between the tracker's status and GitHub's state. Found twice on
    # 2026-09-13: an audit found six open issues whose fix had landed and been
    # judged while the tracker still read untouched, and later three issues
    # (#56, #57, #61) CLOSED on GitHub that the tracker still called `open` --
    # closed by the orchestrator itself, in the same session, hours earlier.
    #
    # The direction that matters is `gh CLOSED, tracker open`: it makes
    # finished work look available, which is how an issue gets re-dispatched.
    # The reverse (gh OPEN, tracker fixed-verified) matters only when there is
    # no blocker to explain it -- a fixed-part issue with a written blocker is
    # a perfectly ordinary state.
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

    # `issues` is the OPEN set, so anything numeric in the tracker that is not
    # in it is either closed or never existed. Ask gh for the closed ones only
    # if the tracker disagrees, to keep this to one extra call at most.
    live = {str(r["number"]) for r in issues}
    claims_open = sorted(k for k, v in tracker.items()
                         if k.isdigit() and v.get("status") == "open"
                         and k not in live)
    if claims_open:
        print("FAIL: %d tracker entr%s `status = \"open\"` for an issue that "
              "is NOT open on GitHub:" % (len(claims_open),
                                          "y says" if len(claims_open) == 1
                                          else "ies say"),
              file=sys.stderr)
        for k in claims_open:
            print("  #%s  %s" % (k, (tracker[k].get("title") or "")[:66]),
                  file=sys.stderr)
        print("\n  Finished work reading as available is how an issue gets\n"
              "  re-dispatched. Set the real status and the evidence it rests on.",
              file=sys.stderr)
        return 1

    # A BLOCKER THAT NAMES SOURCE FILES IS OFTEN A GRANT REQUEST, and whether
    # it is still a blocker is MECHANICALLY CHECKABLE.
    #
    # Three blockers on 2026-09-13 had the form "the fix needs A and B and C
    # together": #43 (psh.c, vk/draw.c, vk/surface.c), #59 (four files
    # atomically) and #13 (four others). Each read as an impossibility and each
    # was a territory request nobody had granted. #43's dissolved the moment
    # three finished lanes were retired and its files went back to free -- and
    # it was then refuted outright, in two ordinary blend passes.
    #
    # The lesson generalises past files: a blocker phrased as what the work
    # NEEDS goes stale the instant the need is met, and nothing re-reads it.
    # #50's "behind the test-suite fork" and #54's "HAKUX_PERF_LOG is only a
    # Gradle property" went the same way, both retired by a capability rather
    # than by a measurement. Those two are not automatable. THIS shape is: if
    # every path a blocker names is unheld, the obstacle it describes does not
    # currently exist.
    #
    # ADVISORY, not a failure. Files being free does not make the work right,
    # and a lane may be deliberately unspawned. But a board where three issues
    # sit behind a wall that is not there should say so out loud.
    lane_files = [f for m in (terr.get("lane") or {}).values()
                  for f in (m.get("files") or [])]
    # Drop glob entries: a lane may hold `gl/*.c` or `target/**`, whose
    # basename is `*.c` or `**` and matches nothing meaningfully. Keeping them
    # would let a stray `*.c` suppress a real flag.
    heldb = {os.path.basename(f) for f in lane_files if "*" not in f}
    grantable = []
    for k, v in sorted(blocked.items()):
        if k not in live:
            continue
        paths = re.findall(r"[A-Za-z0-9_./-]+\.(?:c|h|cpp)\b", v)
        # Match on basename: blockers write `vk/draw.c` where territory writes
        # the full repo path, and demanding they agree would answer never.
        bases = sorted({os.path.basename(q) for q in paths})
        if len(bases) >= 2 and not (set(bases) & heldb):
            grantable.append((k, bases))
    # PRINTED AFTER THE SUMMARY, NOT BEFORE IT, and that ordering is not
    # cosmetic. `idle-watchdog.sh` takes `sed -n 1p` of this output as its
    # one-line coverage summary, so emitting the note first replaced
    # "coverage ok (27 open: ...)" with a sentence truncated mid-clause --
    # "NOTE: 2 blocker(s) name only files NOBODY HOLDS, so the obstacle".
    #
    # Fourth time in this campaign that adding a capability changed what a
    # CONSUMER of its output computes, after the watchdog's device count, its
    # per-suite cost with --base-iso, and again with --only-tests. The first
    # line of a checker's stdout is an interface.
    note_lines = []
    if grantable:
        note_lines.append(
            "NOTE: %d blocker(s) name only files NOBODY HOLDS, so the obstacle "
            "they describe does not currently exist -- they are grant requests "
            "rather than walls:" % len(grantable))
        for k, bases in grantable:
            note_lines.append("  #%-4s names %s" % (k, ", ".join(bases)))

    bad = [k for k in mislabelled if k in live and k not in owned]
    if bad:
        print("FAIL: %d issue(s) whose `blocked_on` describes AVAILABLE work:"
              % len(bad), file=sys.stderr)
        for k in bad:
            print("  #%s  %s" % (k, blocked[k][:96]), file=sys.stderr)
        print("\n  \"wants an arm\" is a next step, not a blocker. Either give\n"
              "  it a lane, or write what it is actually waiting for.",
              file=sys.stderr)
        return 1

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
    for line in note_lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
