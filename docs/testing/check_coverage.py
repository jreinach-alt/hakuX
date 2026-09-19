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

An issue is covered if ANY of:

  - some lane in territory.toml lists it in `issues`, or
  - its nv2a_issues.toml entry carries a non-empty `blocked_on`, or
  - its entry carries `dispatch_state = "available"`.

THE THIRD ONE IS NEW AND IT IS THE POINT OF THE SCHEMA. For as long as there
were only two, a backlog's NORMAL condition -- open, unblocked, nobody on it
yet, waiting for capacity -- could not be expressed at all. This gate makes
`preflight` red for every lane on the repository, and the board is the only
writer of the tracker, so the pressure to fill a field was absolute and
`blocked_on` was the only field that would answer. On 2026-09-18 six open
issues carried a `blocked_on` whose FIRST WORDS were "NOT BLOCKED", and two
more (since deleted) carried "Blocked on local dispatch capacity this tick,
not on anything technical." Honest bookkeeping, in the one field that means
"do not dispatch this".

So `blocked_on` now means blocked, `dispatch_state = "available"` means
nothing blocks it, and the two are mutually exclusive and checked to be.
"Available" is about the OBSTACLE, not about the owner: whether a lane is on
it is territory.toml's business, and fleet.py combines the two.

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


def commits_behind():
    """How far this checkout is behind the campaign tip, or None if unknown.

    AGENTS.md names THIS SCRIPT as the example of the failure it prevents: it
    reads the open-issue list from GitHub, live, and the tracker from the
    working tree, so a lane a few commits behind sees a real issue with no
    tracker row and reports -- soundly, from where it stands -- that the board
    is broken and shared infrastructure is blocking its push. That happened
    three times on 2026-09-13 from two lanes, and the prescribed check is
    `git rev-list --count HEAD..<campaign tip>`. It was never added. This is
    it.

    A worktree shares the object database, so the campaign ref resolves here
    without a fetch and this costs nothing.
    """
    tip = os.environ.get("HAKUX_TIP",
                         "master")
    try:
        out = subprocess.run(["git", "-C", HERE, "rev-list", "--count",
                              "HEAD..%s" % tip],
                             capture_output=True, text=True, timeout=15)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    try:
        return int(out.stdout.strip())
    except ValueError:
        return None


def fleet_tail():
    """The fleet registry's states, from DISK ONLY -- no `gh` call.

    WHY THIS LIVES HERE AND NOT IN THE WATCHDOG. `idle-watchdog.sh` is a bash
    `while` loop, so it parses its body once and a running instance keeps the
    version it started with; a lane-aware branch added to it on 2026-09-14 had
    no effect for the rest of that session. But the loop re-invokes THIS SCRIPT
    fresh on every poll and prints `sed -n 1p` of the output as its hint. So
    the summary line is the only channel that reaches a RUNNING watchdog, and
    anything that needs to take effect tonight has to arrive through it. That
    asymmetry is why the UNBRIEFED note above works and the watchdog's own edit
    did not.

    The watchdog spent a session advising "fold a FINISHED lane, claim a free
    file" while three lanes were mid-flight, because coverage can see a lane
    that is CLAIMED and not one that is WORKING. The registry can, so this
    reports it.

    Deliberately no `gh`: every state here comes from
    $DISPATCH_DIR/fleet/*.json, so adding it to a script the watchdog already
    runs costs no API call and cannot stall on the network.
    """
    dispatch = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
    fdir = os.path.join(dispatch, "fleet")
    if not os.path.isdir(fdir):
        return ""
    rows = []
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(fdir, fn)) as fh:
                rows.append(json.load(fh))
        except Exception:
            # An unreadable row is not nothing -- it is a lane whose state is
            # unknown, and silence would read as "no lanes running".
            rows.append({"lane": fn[:-5], "state": "UNREADABLE"})
    if not rows:
        return ""
    running = [r for r in rows if r.get("state") == "running"]
    reported = [r for r in rows if r.get("state") == "reported"]
    waiting = [r for r in rows if (r.get("waiting_on") or "").strip()]
    unreadable = [r for r in rows if r.get("state") == "UNREADABLE"]

    bits = []
    # Ordered worst-first: a lane blocked on the orchestrator is the one state
    # only the orchestrator can clear, and it is reading this line.
    if waiting:
        bits.append("WAITING ON YOU: " + ", ".join(
            "%s (%s)" % (r.get("lane", "?"), (r.get("waiting_on") or "")[:60])
            for r in waiting))
    if reported:
        bits.append("%d lane(s) REPORTED AND NOT FOLDED (%s) -- their claim "
                    "still reads as coverage"
                    % (len(reported),
                       ", ".join(r.get("lane", "?") for r in reported)))
    if unreadable:
        bits.append("%d fleet row(s) UNREADABLE (%s)"
                    % (len(unreadable),
                       ", ".join(r.get("lane", "?") for r in unreadable)))
    if running:
        bits.append("%d lane(s) RUNNING (%s) -- do not claim their files or "
                    "advise folding them"
                    % (len(running),
                       ", ".join(r.get("lane", "?") for r in running)))
    return ("; " + "; ".join(bits)) if bits else ""


def main():
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

    owned = {}
    for lane, meta in (terr.get("lane") or {}).items():
        for i in meta.get("issues", []):
            owned[str(i)] = lane
    blocked = {k: v["blocked_on"] for k, v in tracker.items()
               if (v.get("blocked_on") or "").strip()}

    # THE THIRD STATE. `dispatch_state` is an explicit enum and the only value
    # that satisfies this gate on its own is "available". "blocked" is
    # accepted, and redundant with a non-empty `blocked_on`, because a board
    # that has classified a row should be able to say so in one place.
    #
    # AN UNRECOGNISED VALUE IS A FAILURE, NOT A SHRUG. A typo that fell
    # through would read as "classified" to a human and as "unclassified" to
    # every consumer, which is the exact asymmetry this schema exists to
    # remove.
    #
    # "done" IS HERE BECAUSE THE BOARD WROTE IT BEFORE THIS LANE FOLDED, and
    # that is evidence, not pressure. The first version of this enum was
    # ("available", "blocked") and rule (3) below tells a board closing a row
    # that `available` no longer holds -- while giving it no word to put
    # there instead. Its two options were to delete the field, losing the
    # record that the row was ever classified, or to invent a word. On
    # 2026-09-19 it closed #84 and wrote `dispatch_state = "done"`, which is
    # the right word; refusing it would have made preflight red for every
    # lane on the repository over a row nobody will ever dispatch.
    #
    # It costs the same as the others. "done" satisfies NOTHING on its own --
    # the coverage gate below counts only `available`, and fleet.py dispatches
    # only `available` -- and `done` on a `status = "open"` row is a FAIL,
    # exactly mirroring `available` on a closed one. The two cannot be used to
    # silence anything, because each contradicts the `status` it is written
    # against.
    STATES = ("available", "blocked", "done")
    state = {k: (v.get("dispatch_state") or "").strip()
             for k, v in tracker.items()}
    available = {k for k, v in state.items() if v == "available"}

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
    # THE STALENESS QUALIFIER GOES ON EVERY FAIL, NOT JUST THE SUMMARY.
    #
    # Every FAIL below compares LIVE GitHub state against the WORKING TREE's
    # two toml files. If this checkout is behind the campaign tip, a real
    # disagreement between them is evidence about the CHECKOUT and not about
    # the board -- and the report that comes out of it is a sound argument run
    # against the wrong inputs, which is how three false "infrastructure is
    # blocking me" reports were filed from two lanes in one day.
    #
    # So compute it once, before anything is judged, and attach it to whatever
    # is printed. A lane that reads "FAIL ... and you are 979 commits behind"
    # rebases; a lane that reads "FAIL" files a report.
    behind = commits_behind()
    if behind:
        stale = ("\n  YOU ARE %d COMMIT(S) BEHIND THE CAMPAIGN TIP. This "
                 "check reads the open-issue list LIVE from GitHub and the "
                 "tracker from your working tree, so a disagreement between "
                 "them is evidence about THIS CHECKOUT first. Rebase, then "
                 "re-run, and only then report the board as broken."
                 % behind)
    else:
        stale = ""

    issues, err = open_issues()
    if issues is None:
        print("coverage NOT CHECKED: %s%s" % (err, fleet_tail()))
        print("  (failing open -- a network blip must not make this unpushable)")
        # Said even here, because "NOT CHECKED" plus a stale tree is the state
        # in which a lane is most likely to conclude something about the board.
        if stale:
            print(stale)
        return 0

    gaps = []
    for r in issues:
        n = str(r["number"])
        if n in owned or n in blocked or n in available:
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
        if stale:
            print(stale, file=sys.stderr)
        return 1

    # `dispatch_state` COSTS SOMETHING, and it has to, because it is a value
    # invented to satisfy a gate and those get used to silence it. Four ways
    # to write it wrong, all failures:
    #
    #   1. a value that is not in STATES -- a typo reads as classified to a
    #      human and as unclassified to every consumer;
    #   2. "available" ALONGSIDE a non-empty `blocked_on` -- the contradiction
    #      this schema exists to end, in one row;
    #   3. "available" on an entry whose `status` is not `open`.
    #
    # (3) IS THE GUARD ON THE OPPOSITE FAILURE, and that one is not
    # hypothetical: "finished work reading as available is how an issue gets
    # re-dispatched" is this script's own sentence about #56/#57/#61, and it
    # cost real sessions. So the moment work is judged done -- any `fixed-*`
    # status -- "available" stops holding and somebody has to re-classify the
    # row. Same design as `fixed-unlanded` below: a status that is cheap to
    # write is worthless.
    #
    #   4. "blocked" with an EMPTY `blocked_on` is a claim with no content.
    bad_state = []
    for k in sorted(tracker, key=lambda x: int(x) if x.isdigit() else 0):
        v, s = tracker[k], state[k]
        if not s:
            continue
        if s not in STATES:
            bad_state.append((k, "dispatch_state = %r is not one of %s"
                              % (s, ", ".join(STATES))))
            continue
        b = (v.get("blocked_on") or "").strip()
        if s == "available" and b:
            bad_state.append((k, "`available` with a non-empty `blocked_on`: "
                              + b[:60]))
        if s == "available" and (v.get("status") or "") != "open":
            bad_state.append((k, "`available` with status = %r -- if it is "
                              "done it is not available"
                              % (v.get("status") or "")))
        if s == "blocked" and not b:
            bad_state.append((k, "`blocked` with no `blocked_on` to say what "
                              "it is blocked on"))
        if s == "done" and (v.get("status") or "") == "open":
            bad_state.append((k, "`done` on a row whose status is still "
                              "`open` -- close the row or say what state it "
                              "is really in; a second field that contradicts "
                              "`status` is how the two drift"))
    if bad_state:
        print("FAIL: %d entr%s whose `dispatch_state` does not hold:"
              % (len(bad_state), "y" if len(bad_state) == 1 else "ies"),
              file=sys.stderr)
        for k, why in bad_state:
            print("  #%-4s %s" % (k, why), file=sys.stderr)
        print("\n  `dispatch_state` is one of %s. `available` means NOTHING\n"
              "  BLOCKS IT -- not that nobody owns it, which is\n"
              "  territory.toml's business -- and it requires an empty\n"
              "  `blocked_on` and `status = \"open\"`. `done` is its mirror\n"
              "  and requires a status that is NOT open. Neither satisfies\n"
              "  this gate by itself: only `available` covers a row, and\n"
              "  only an open row needs covering." % ", ".join(STATES),
              file=sys.stderr)
        if stale:
            print(stale, file=sys.stderr)
        return 1

    # A `blocked_on` WHOSE OPENING CLAIM IS THAT IT IS NOT BLOCKED.
    #
    # This is the migration's enforcement, and it is anchored at the START of
    # the field on purpose. A free-text search for the same phrases over the
    # whole value is wrong in both directions, measured over all 81 rows on
    # 2026-09-19:
    #
    #   - #91 says "#84 AND ITS M1 REMEDIATION ARE EXPLICITLY NOT BLOCKED BY
    #     THIS", which is about a DIFFERENT issue;
    #   - #92 says "I had written NOT BLOCKED and then left it unallocated,
    #     which is the state that reads as coverage and is not" -- the
    #     board recording that it had already corrected the wording;
    #   - "CLEARED" matches "test-and-cleared" (#44) and "audit pass 2 cleared
    #     them" (#91), neither of which is about this field at all.
    #
    # fleet.py used exactly that substring search to undo the damage from the
    # other side, and #92 is the false positive it produced: a row the board
    # had deliberately written as an assignment was reported dispatchable on
    # the strength of a sentence describing a wording it no longer used.
    #
    # What is load-bearing is whether the field's OWN LEADING CLAIM asserts
    # non-blockage. That is a position, not a phrase, and it is what all six
    # real cases had in common.
    #
    # LIVE-OPEN ONLY. A closed row's `blocked_on` is history and rewriting it
    # would destroy the record for no gain; six of the fourteen matching rows
    # are already closed.
    # CASE MATTERS FOR EXACTLY ONE OF THESE, and the asymmetry is the point.
    # "not blocked", "not a blocker" and "unblocked" have no innocent reading as
    # a blocker's opening claim, whatever their case. "cleared" does: "Blocked
    # until the audit has cleared the held fold" is a perfectly good blocker,
    # and #44's "test-and-cleared" and #91's "audit pass 2 cleared them" are
    # both real. So CLEARED is matched only SHOUTED, which is how the board
    # writes its own status markers and how #89 wrote this one.
    LEAD = 90
    LEAD_ANY_CASE = (r"\bNOT BLOCKED\b", r"\bNOT A BLOCKER\b", r"\bUNBLOCKED\b")
    LEAD_SHOUTED = (r"\bCLEARED\b", r"\bNO LONGER BLOCKED\b")
    ANYWHERE_CLAIMS = (r"not on anything technical", r"dispatch capacity")
    not_blocked = []
    for k, v in sorted(blocked.items(), key=lambda x: int(x[0])
                       if x[0].isdigit() else 0):
        if k not in live:
            continue
        lead = " ".join(v.split())[:LEAD]
        hit = next((p for p in LEAD_ANY_CASE if re.search(p, lead, re.I)), None) \
            or next((p for p in LEAD_SHOUTED if re.search(p, lead)), None) \
            or next((p for p in ANYWHERE_CLAIMS
                     if re.search(p, v, re.I)), None)
        if hit:
            not_blocked.append((k, lead))
    if not_blocked:
        print("FAIL: %d `blocked_on` that OPENS BY SAYING IT IS NOT BLOCKED:"
              % len(not_blocked), file=sys.stderr)
        for k, lead in not_blocked:
            print("  #%-4s %s" % (k, lead), file=sys.stderr)
        print("\n  `blocked_on` means blocked. An honest note saying the work\n"
              "  is available made THIS CHECKER count the row among \"N with a\n"
              "  written blocker\" and print `coverage ok` over it, and left\n"
              "  fleet.py undoing it with a substring search on the prose.\n"
              "  Move the text to `status_note` and write\n"
              "  `dispatch_state = \"available\"`. That state satisfies this\n"
              "  gate on its own; there is no longer any reason to reach for\n"
              "  `blocked_on` to get a green preflight.", file=sys.stderr)
        if stale:
            print(stale, file=sys.stderr)
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
        if stale:
            print(stale, file=sys.stderr)
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
        if stale:
            print(stale, file=sys.stderr)
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
        if stale:
            print(stale, file=sys.stderr)
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
        if stale:
            print(stale, file=sys.stderr)
        return 1

    if gaps:
        print("FAIL: %d open issue(s) with neither a lane nor a blocker:"
              % len(gaps), file=sys.stderr)
        for n, t in gaps:
            print("  #%s  %s" % (n, t[:72]), file=sys.stderr)
        print("\n  THREE WAYS TO CLEAR THIS, and the third is the one that\n"
              "  used to be missing. Give it a lane in territory.toml; or\n"
              "  write `blocked_on` saying what it is waiting for -- a\n"
              "  blocker is a claim, so state it as the measurement that\n"
              "  would refute it, not as a reason to stop; or, if nothing\n"
              "  blocks it and it is simply waiting for capacity, write\n"
              "  `dispatch_state = \"available\"` and leave `blocked_on`\n"
              "  empty. What is NOT acceptable is an unclassified row: this\n"
              "  gate exists because finished work reading as available is\n"
              "  how an issue gets re-dispatched.", file=sys.stderr)
        if stale:
            print(stale, file=sys.stderr)
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
    # So: a lane is briefed by a `[job.deliver] lane.<name>` comment on the
    # thread the work lives on (docs/testing/jobs/deliver.sh), and this reports
    # any lane holding unblocked open issues that has not been briefed
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
        # THE LAST-BRIEF TIME IS THE TIMESTAMP OF AN ACTUAL DELIVERY COMMENT,
        # not a stamp somebody has to remember and not the mtime of a file the
        # recipient cannot open.
        #
        # It has been both of those. First `$DISPATCH_DIR/lanes/<lane>.lastbrief`,
        # which fired on lane.remote at 3.1h on 2026-09-14 while the
        # orchestrator had briefed it TWICE in that window -- writing the stamp
        # was a second thing to remember and was forgotten both times. Then the
        # mtime of `$DISPATCH_DIR/deliveries/<lane>.md`, which fixed the
        # remembering and left the fatal half untouched: that file is on this
        # host's disk, on no ref and no remote, and ORCHESTRATION-DESIGN.md §5
        # says in as many words that the cloud sessions cannot see the dispatch
        # directory. A CHANNEL THE RECIPIENT CANNOT READ MEASURES NOTHING, and
        # a freshly appended file would have reported this gate green while no
        # brief had reached anyone at all. Both stamps were four days older
        # than the delivery files they backed, on both lanes that had one.
        #
        # So the channel is a GitHub comment (docs/testing/jobs/deliver.sh) and
        # the time read here is GitHub's own `created_at` for a comment that
        # exists, cached at `$DISPATCH_DIR/delivery-cache/<lane>.json` by the
        # POST that created it and refreshed by comment_sweep.sh's hourly pass.
        #
        # THE CACHE IS NOT A SECOND CHANNEL, and this is the distinction that
        # keeps the old defect from coming back: nothing reads it to learn what
        # was routed -- `deliver.sh inbox <lane>` reads GitHub for that -- and
        # no local clock reading ever enters it. It is an index of one field so
        # that this gate, which runs inside every lane's preflight, costs no
        # network call. A missing or unreadable cache reads as "never", which
        # is the safe direction: it reports a lane as unbriefed rather than
        # reporting a brief nobody sent.
        #
        # WHAT THIS CANNOT SEE: whether the delivery said anything useful, or
        # whether the lane read it. It measures routing, not receipt -- the
        # same limit the file had, carried forward rather than quietly
        # dropped. It also cannot see a delivery posted by hand until the next
        # sweep folds it in, so the note names the cache's own age whenever
        # that age is old enough to be the thing you are actually looking at.
        cache = os.path.join(dispatch, "delivery-cache", "%s.json" % lane)
        hours, src = None, "no delivery comment on record"
        scanned_h = None
        try:
            with open(cache) as fh:
                blob = json.load(fh)
            when = datetime.datetime.strptime(blob["delivered"],
                                              "%Y-%m-%dT%H:%M:%SZ")
            hours = (now - when.replace(tzinfo=datetime.timezone.utc)) \
                .total_seconds() / 3600.0
            src = "the newest [job.deliver] comment, on #%s" % (
                blob.get("delivered_thread") or "?")
            try:
                seen = datetime.datetime.strptime(blob["scanned"],
                                                  "%Y-%m-%dT%H:%M:%SZ")
                scanned_h = (now - seen.replace(tzinfo=datetime.timezone.utc)) \
                    .total_seconds() / 3600.0
            except Exception:
                scanned_h = None
        except Exception:
            hours = None
        # A CACHE NOBODY IS REFRESHING CANNOT REPORT A FRESH BRIEF, so say so
        # rather than letting an hours figure stand on its own. comment_sweep.sh
        # runs hourly; three times that is stopped, not slow.
        if scanned_h is not None and scanned_h >= 3.0:
            src += " (cache last refreshed %.1fh ago -- is hakux-comments.timer running?)" % scanned_h
        if hours is None or hours >= 3.0:
            stale_brief.append((lane, len(idle_issues),
                                "never" if hours is None else "%.1fh" % hours,
                                src))

    tail = ""
    if stale_brief:
        tail = "; UNBRIEFED: " + ", ".join(
            "%s %d unblocked issue(s), last brief %s per %s" % (l, n, h, s)
            for l, n, h, s in stale_brief)
    # THE AVAILABLE COUNT GOES ON THIS LINE, not in the note block, for the
    # same reason the UNBRIEFED note does: idle-watchdog.sh takes `sed -n 1p`
    # of this output as its hint and never shows the notes. A backlog of
    # unblocked work that only shows up on line two is the defect this schema
    # was written for, one layer out.
    #
    # AND IT IS COUNTED OVER ALL OPEN ISSUES, NOT ONLY THE UNOWNED ONES. The
    # first version of this line kept the old shape -- owned, then
    # available-and-not-owned, then blocked-and-not-owned, three buckets
    # summing to the total -- and printed "0 AVAILABLE" on a board where all
    # seven available rows existed, because every one of them was also held by
    # a lane. A number that reads zero exactly when the state is in use is
    # worse than no number.
    #
    # So the counts OVERLAP and the line says so. That costs the sum property,
    # which carried no information anyway: the gate above FAILS on an
    # unclassified row, so coverage being complete is already established by
    # getting here.
    print("coverage ok (%d open: %d AVAILABLE, %d blocked, %d owned by a lane "
          "-- available and owned overlap%s)%s%s"
          % (len(issues),
             sum(1 for r in issues if str(r["number"]) in available),
             sum(1 for r in issues if str(r["number"]) in blocked),
             sum(1 for r in issues if str(r["number"]) in owned), tail,
             fleet_tail(),
             "" if not behind else
             "; STALE CHECKOUT: %d commit(s) behind the campaign tip, so this "
             "`ok` is about a tree that is not the branch" % behind))
    for line in note_lines:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
