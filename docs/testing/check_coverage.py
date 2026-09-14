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
import datetime
import glob
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
    # MATCH ON PATH SUFFIX, NOT BASENAME, and expand globs against the tree.
    # Both halves are corrections to this detector's first firing in anger,
    # which produced one error in each direction from a single run.
    #
    # Dropping glob patterns (`gl/*.c`, `target/**`) on the grounds that their
    # basename means nothing gave a FALSE POSITIVE: #13 was reported as a grant
    # request while `gl/shaders.c`, one of the four files its blocker names, was
    # held by lane.remote through exactly that glob.
    #
    # Expanding the globs and still comparing basenames then gave a FALSE
    # NEGATIVE: `gl/*.c` expands to include `gl/draw.c`, whose basename
    # `draw.c` suppressed #59 -- whose blocker names `vk/draw.c`, an entirely
    # different file. There are two `draw.c`, two `shaders.c` and two
    # `surface.c` in this tree.
    #
    # So: a blocker's path matches a held path when the held path ENDS WITH it
    # (at a directory boundary). `vk/draw.c` matches
    # `hw/xbox/nv2a/pgraph/vk/draw.c` and not `.../gl/draw.c`. A bare `psh.c`
    # matches any `psh.c`, which is the blocker's own imprecision and the safe
    # direction -- it suppresses a flag rather than inventing one.
    REPO = os.path.join(HERE, "..", "..")
    held_paths = set()
    for f in lane_files:
        if "*" in f:
            for hit in glob.glob(os.path.join(REPO, f), recursive=True):
                if os.path.isfile(hit):
                    held_paths.add(os.path.relpath(hit, REPO))
        else:
            held_paths.add(f)

    def is_held(named):
        named = named.lstrip("./")
        return any(h == named or h.endswith("/" + named) for h in held_paths)

    grantable = []
    for k, v in sorted(blocked.items()):
        if k not in live:
            continue
        paths = re.findall(r"[A-Za-z0-9_./-]+\.(?:c|h|cpp)\b", v)
        # Match on basename: blockers write `vk/draw.c` where territory writes
        # the full repo path, and demanding they agree would answer never.
        named = sorted(set(paths))
        if len(named) >= 2 and not any(is_held(q) for q in named):
            grantable.append((k, [os.path.basename(q) for q in named]))
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

    # AN ISSUE A LANE CLAIMS BUT THE BOARD NEVER DESCRIBES.
    #
    # `owned` is satisfied by a number appearing in some lane's `issues` list.
    # That is a claim of RESPONSIBILITY and it was being read as a claim of
    # KNOWLEDGE. On 2026-09-13 #66, #71 and #72 were listed by lane.remote and
    # had no row in nv2a_issues.toml at all -- no title, no suites, no status,
    # no blocker -- and this checker printed `coverage ok` over them for a full
    # day. Nothing on the board said what they were, and the one artefact whose
    # job is to notice that said everything was fine.
    #
    # Writing those rows then turned up what the silence had been hiding: #72
    # was CLOSED on GitHub with its fix on a branch that had never been merged
    # here, along with seven more hw/ and target/ commits. A lane claim is the
    # weakest possible evidence of coverage precisely because it is the
    # cheapest to write -- one number in a list -- and it suppresses the two
    # gates that would otherwise have fired.
    #
    # So a claim now has to be accompanied by an entry. This is a FAIL rather
    # than a note: it is exactly the shape of hole the script was written for,
    # and it survived the script.
    # A BLOCKER NAMING A LANE THAT NO LONGER EXISTS.
    #
    # This campaign records ordering as "blocked behind lane.foo". Lanes get
    # retired when their agent reports, and their files go back to free --
    # and nothing re-reads the blockers that named them. The issue then sits
    # behind a predecessor that finished, showing as covered, for as long as
    # nobody looks.
    #
    # Found by hand on 2026-09-13 on #59, whose blocker named lane.signfold
    # long after signfold retired; check_coverage's grant-request NOTE had
    # been reporting its files as unheld, which is the same fact arriving
    # through a different door. A sweep for the general case then turned up
    # #13 and #44 in the same state.
    #
    # THE RULE IS "NAMES ONLY DEAD LANES", not "mentions a dead lane". A
    # corrected blocker keeps its history -- #59's now reads "ORDERED BEHIND
    # lane.signfold ... CORRECTED: the current predecessor is lane.stencil" --
    # and flagging that would punish the fix. So an entry passes as soon as it
    # names one live lane.
    live_lanes = {"lane." + k for k in (terr.get("lane") or {})}
    stale_lane = []
    for k, v in sorted(tracker.items()):
        if k not in live:
            continue
        blob = (v.get("blocked_on") or "")
        named = set(re.findall(r"lane\.[a-z0-9_]+", blob))
        # Two ways to be honest about a dead lane, and the second one took a
        # second pass to see. Naming a LIVE lane says "here is the real
        # current predecessor". Saying the word RETIRED says "there is no
        # predecessor any more" -- which for #44 was the true answer, and the
        # first version of this check rejected it, demanding a live lane that
        # does not exist. A gate that only accepts one of two correct answers
        # pushes people toward writing the wrong one.
        acknowledged = "retired" in blob.lower()
        if named and not (named & live_lanes) and not acknowledged:
            stale_lane.append((k, sorted(named)))
    if stale_lane:
        print("FAIL: %d blocker(s) name only lanes that no longer exist:"
              % len(stale_lane), file=sys.stderr)
        for k, names in stale_lane:
            print("  #%-4s %s" % (k, ", ".join(names)), file=sys.stderr)
        print("\n  A retired lane's files went back to free, so the wall it\n"
              "  describes is gone and the issue may be dispatchable now.\n"
              "  Name the real current predecessor, or say the lane RETIRED\n"
              "  and there is none. Keeping the old name as history is fine:\n"
              "  either naming a live lane alongside it, or the word\n"
              "  'retired', clears this.", file=sys.stderr)
        return 1

    # `fixed-unlanded` IS CHECKED, NOT TAKEN ON TRUST.
    #
    # The value exists because #72 was closed on GitHub by a lane that fixed it
    # on its own branch, so `open` was wrong (a fix exists) and every `fixed-*`
    # was wrong (nothing here is fixed). A status invented to resolve a gate's
    # complaint is a status that will be used to silence it, so this one costs
    # something: the entry must list `fixed_by`, and every sha in it must be a
    # real commit that is NOT an ancestor of HEAD. The instant the work is
    # merged, this fails and demands a real status -- which is exactly when
    # somebody needs to go and look at whether it landed intact.
    unlanded_bad = []
    for k, v in tracker.items():
        if v.get("status") != "fixed-unlanded":
            continue
        shas = v.get("fixed_by") or []
        if not shas:
            unlanded_bad.append((k, "no `fixed_by`"))
            continue
        for sha in shas:
            r = subprocess.run(["git", "-C", HERE, "rev-parse", "--verify",
                                "-q", sha + "^{commit}"],
                               capture_output=True, text=True)
            if r.returncode != 0:
                unlanded_bad.append((k, "%s is not a commit here" % sha))
                continue
            r = subprocess.run(["git", "-C", HERE, "merge-base",
                                "--is-ancestor", sha, "HEAD"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                unlanded_bad.append(
                    (k, "%s IS an ancestor of HEAD -- it landed" % sha))
    if unlanded_bad:
        print("FAIL: %d `fixed-unlanded` entr%s that does not hold:"
              % (len(unlanded_bad),
                 "y" if len(unlanded_bad) == 1 else "ies"), file=sys.stderr)
        for k, why in unlanded_bad:
            print("  #%-4s %s" % (k, why), file=sys.stderr)
        print("\n  `fixed-unlanded` means a fix exists somewhere that is not\n"
              "  this branch. If it landed, say what it is worth here: read\n"
              "  the merge and give it a real status.", file=sys.stderr)
        return 1

    unwritten = sorted((str(r["number"]), r["title"]) for r in issues
                       if str(r["number"]) in owned
                       and str(r["number"]) not in tracker)
    if unwritten:
        print("FAIL: %d issue(s) claimed by a lane with NO nv2a_issues.toml "
              "entry:" % len(unwritten), file=sys.stderr)
        for n, t in unwritten:
            print("  #%-4s %-10s %s" % (n, owned[n], t[:60]), file=sys.stderr)
        print("\n  A lane claim says who is responsible. It does not say what\n"
              "  the issue IS, and this check used to accept it as if it did.\n"
              "  Write the row: what moves, what is measured, what is not.",
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

    # AN UNBRIEFED LANE IS AN IDLE LANE, AND IT LOOKS EXACTLY LIKE A COVERED ONE.
    #
    # `owned` is satisfied by a number in a lane's `issues` list. It says a
    # lane is RESPONSIBLE; it cannot say anyone is working. A remote lane that
    # finished its last instruction and was never given another shows here as
    # coverage, permanently, and the watchdog reports nothing uncovered.
    #
    # Found on 2026-09-14: lane.remote held eight issues, FIVE of them open
    # with no `blocked_on` at all, and the session had been idle through
    # several hours of orchestration. Nothing on the board could say so,
    # because a lane claim suppresses the gap gate and a missing blocker is
    # only checked for issues WITHOUT a lane.
    #
    # So: a lane is briefed by writing an ISO-8601 UTC timestamp to
    # $DISPATCH_DIR/lanes/<lane>.lastbrief when it is sent direction, and this
    # reports any lane holding unblocked open issues that has not been briefed
    # recently.
    #
    # IT GOES ON THE SUMMARY LINE, not in the NOTE block below. idle-watchdog.sh
    # takes `sed -n 1p` of this output as its hint and never shows the notes --
    # so a note here would be invisible to the one consumer that needs it. That
    # is the fifth time in this campaign that where output is placed decided
    # whether it was read.
    stale_brief = []
    dispatch = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
    now = datetime.datetime.now(datetime.timezone.utc)
    for lane, meta in sorted((terr.get("lane") or {}).items()):
        idle_issues = [i for i in (meta.get("issues") or [])
                       if str(i) in live and not (tracker.get(str(i), {})
                                                  .get("blocked_on") or "").strip()]
        if not idle_issues:
            continue
        path = os.path.join(dispatch, "lanes", "%s.lastbrief" % lane)
        try:
            with open(path) as fh:
                when = datetime.datetime.strptime(fh.read().strip(),
                                                  "%Y-%m-%dT%H:%M:%SZ")
            hours = (now - when.replace(tzinfo=datetime.timezone.utc)) \
                .total_seconds() / 3600.0
        except Exception:
            hours = None
        if hours is None or hours >= 3.0:
            stale_brief.append((lane, len(idle_issues),
                                "never" if hours is None else "%.1fh" % hours))

    tail = ""
    if stale_brief:
        tail = "; UNBRIEFED: " + ", ".join(
            "%s %d unblocked issue(s), last brief %s" % (l, n, h)
            for l, n, h in stale_brief)
    print("coverage ok (%d open: %d owned by a lane, %d with a written blocker%s)"
          % (len(issues),
             sum(1 for r in issues if str(r["number"]) in owned),
             sum(1 for r in issues if str(r["number"]) in blocked
                 and str(r["number"]) not in owned), tail))
    for line in note_lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
