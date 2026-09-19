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

WHERE THE FACTS COME FROM, AND WHY NOT FROM A REGISTRY ANY MORE.

Until 2026-09-19 every section below was computed from $DISPATCH_DIR/fleet/
<lane>.json, "written by the ORCHESTRATOR when it dispatches and updated when
a report lands". ORCHESTRATION-DESIGN.md §4 then deleted that role, and
nothing took over this piece: `lane.sh` had never written a registry entry,
so the file set froze on 09-14/09-18 and stayed frozen.

Measured 2026-09-19T06:20Z, with eight lanes running as systemd units: this
script reported four lanes RUNNING, of which two were not running at all and
one had been folded and merged twenty minutes earlier. Not one of the eight
appeared. Because the board wakes on the FAIL lines at the bottom of this
file, and all four were computed from that registry, six consecutive board
ticks logged `nothing actionable` -- and would have logged it just the same
with the fleet idle or with eight lanes in flight. A blind sensor reports
calm.

So every fact that decides a FAIL is now derived from the thing itself:

  RUNNING            systemctl --user list-units 'hakux-lane-*'
  READY, NOT FOLDED  gh pr list: an open lane PR that is not a draft
  BLOCKED            gh pr list: an open lane PR labelled `blocked`
  territory rows     board_files.load("territory.toml")

A unit that is active is running; there is no state for it to be in that a
file could disagree with. A lane that has finished is one whose unit is gone,
and whether its work landed is a question about its PR, which GitHub answers.
Neither fact can go stale, because neither is recorded anywhere.

THE REGISTRY SURVIVES, DEMOTED. $DISPATCH_DIR/fleet/<lane>.json is now
written by `lane.sh` at start and cleared by it at exit, and holds only what
lane.sh knows first-hand: the brief it was handed (`asked`), the issues, the
attempt, the model, the branch and worktree. It carries NO `state` field,
because state is the thing that went stale. Here it is decoration on a lane
that systemd already says is running, plus the issue list that keeps a
running lane's issue out of DISPATCHABLE. An entry whose unit is not active
is ignored outright -- it can never create a lane, revive one, or suppress
work -- so the 38 pre-2026-09-19 entries are inert. `lane.sh fleet-gc`
deletes them; leaving them costs only disk.

  lane, unit, branch, worktree, brief, asked, issues[], attempt, model,
  started_utc   (and ended_utc/rc for the moment between exit and unlink)
"""
import datetime, json, os, subprocess, sys, tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.environ.get("DISPATCH_DIR", "/home/justin/hakux-work/dispatch")
# Overridable so the issue-blind path can be exercised without unplugging the
# network. A gate whose failure branch has never run is not a gate.
REPO = os.environ.get("HAKUX_REPO", "jreinach-alt/hakuX")


def load_fleet():
    """The registry, keyed by lane. Decoration only -- see the header."""
    out = {}
    fdir = os.path.join(D, "fleet")
    if not os.path.isdir(fdir):
        return out
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".json"):
            continue
        try:
            e = json.load(open(os.path.join(fdir, fn)))
        except Exception as e2:
            print("  UNREADABLE %s: %s" % (fn, e2), file=sys.stderr)
            continue
        if isinstance(e, dict) and e.get("lane"):
            out[e["lane"]] = e
    return out


def sc(*args, timeout=15):
    """systemctl --user, or None if the user manager cannot be reached.

    None is NOT an empty fleet. Every caller distinguishes them, because
    reporting "nothing is running" when the question could not be asked is
    exactly the failure this file was rewritten to end: it would empty
    RUNNING, fill LANE CLAIMED WITH NO RUNNING AGENT, and hand DISPATCHABLE
    every issue a live lane already owns.
    """
    try:
        r = subprocess.run(["systemctl", "--user"] + list(args),
                           capture_output=True, text=True, timeout=timeout)
    except Exception:
        return None
    return r.stdout if r.returncode == 0 else None


def lane_units():
    """{lane: seconds-running-or-None}, or None if systemd could not answer.

    Two cheap calls, both under 50ms measured on the host: list-units to
    discover the names, then ONE keyed `show` for all of their start times.
    The board runs this file every twenty minutes under a 60s timeout, so a
    per-lane call is not affordable and is not made.
    """
    out = sc("list-units", "hakux-lane-*", "--state=active,activating",
             "--no-legend", "--plain")
    if out is None:
        return None
    names = [ln.split()[0] for ln in out.splitlines() if ln.split()]
    lanes = {n[len("hakux-lane-"):-len(".service")]: None for n in names
             if n.startswith("hakux-lane-") and n.endswith(".service")}
    if not names:
        return lanes
    # ActiveEnterTimestampMonotonic, not ActiveEnterTimestamp: the latter is
    # local time with a tz ABBREVIATION ("PDT"), which strptime %Z cannot be
    # trusted to read, and --timestamp=utc needs systemd 247.
    show = sc("show", *names, "--property=Id,ActiveEnterTimestampMonotonic")
    try:
        up = float(open("/proc/uptime").read().split()[0])
    except Exception:
        up = None
    if show and up is not None:
        ident = None
        for ln in show.splitlines():
            k, _, v = ln.partition("=")
            if k == "Id":
                ident = v
            elif k == "ActiveEnterTimestampMonotonic" and ident:
                lane = ident[len("hakux-lane-"):-len(".service")]
                try:
                    if lane in lanes and int(v) > 0:
                        lanes[lane] = up - int(v) / 1e6
                except ValueError:
                    pass
    return lanes


def age_s(secs):
    return "?" if secs is None else "%.1fh" % (secs / 3600.0)


def age(iso):
    # `iso` is the registry's started_utc, written and kept in UTC. Nothing
    # here needs converting: the output is a RELATIVE duration, and both sides
    # of the subtraction are tz-aware, so the answer is the same in any zone.
    try:
        t = datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ") \
            .replace(tzinfo=datetime.timezone.utc)
        h = (datetime.datetime.now(datetime.timezone.utc) - t).total_seconds() / 3600
        return "%.1fh" % h
    except Exception:
        return "?"


# A PR the machine has already picked up is not the board's to act on. These
# are exactly the labels roles/board.md names in its own rule: "a PR that is
# not a draft and has no needs-audit-*, needs-remediation, fold-ready or
# folded label -> needs-audit-1". `needs-rebase` and `claimed:cloud` are here
# for the same reason -- another job holds it.
IN_FLIGHT = {"needs-audit-1", "needs-audit-2", "needs-remediation",
             "fold-ready", "folded", "needs-rebase", "claimed:cloud"}


def lane_prs():
    """Open PRs on lane/* branches, or None if gh could not answer.

    One call. Everything the READY-NOT-FOLDED and BLOCKED sections need comes
    out of it, so neither section costs a call per lane.
    """
    try:
        r = subprocess.run(["gh", "pr", "list", "--repo", REPO, "--state", "open",
                            "--limit", "60", "--json",
                            "number,headRefName,isDraft,labels,updatedAt,title"],
                           capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return None
        rows = json.loads(r.stdout or "[]")
    except Exception as e:
        print("gh pr list did not answer (%s)" % e, file=sys.stderr)
        return None
    out = []
    for p in rows:
        ref = p.get("headRefName") or ""
        if not ref.startswith("lane/"):
            continue
        p["lane"] = ref[len("lane/"):]
        p["labelset"] = {l.get("name") for l in (p.get("labels") or [])}
        out.append(p)
    return out


def main():
    fleet = load_fleet()
    # The board lives on the `board` branch when it exists, and in the tree
    # until then; board_files says which was read, so a stale local copy is
    # never quoted as a live one (docs/ORCHESTRATION-DESIGN.md §5).
    sys.path.insert(0, HERE)
    # After HERE, not before it: jobs/ is a supplement to this directory, not
    # a shadow of it.
    sys.path.insert(1, os.path.join(HERE, "jobs"))
    import board_files
    try:
        from localtime import say_time
    except ImportError:
        # THIS FILE IS ALSO RUN FROM A COPY OF ITSELF. selftest.d/93's board
        # fixture copies exactly check_coverage.py, fleet.py and board_files.py
        # into a scratch directory and runs fleet.py there, so anything this
        # file imports must either be one of those three or be optional. An
        # unguarded `from localtime import ...` took out all ten of that
        # fragment's checks at once.
        #
        # Degrade to UTC and SAY UTC. The failure mode this whole change exists
        # to prevent is a clock that is labelled with a zone it is not in; a
        # line that reads "UTC" while being UTC costs a reader nothing.
        def say_time():
            return datetime.datetime.now(datetime.timezone.utc) \
                           .strftime("%Y-%m-%d %H:%M UTC")
    terr = board_files.load("territory.toml")
    tracker = board_files.load("nv2a_issues.toml")["issue"]
    # Everything else this report prints is a RELATIVE duration ("4.2h"), which
    # needs no zone. That is also why it never said when "4.2h ago" was counted
    # back from -- a report pasted into an issue an hour later reads as current.
    # One absolute line, in the display zone, fixes that.
    print("fleet report generated %s" % say_time())
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
        try:
            rows = json.loads(r.stdout or "[]")
        except ValueError:
            rows, ok = [], False
            print("gh issue list returned something that is not JSON; the "
                  "DISPATCHABLE section is EMPTY BECAUSE IT WAS NOT COMPUTED",
                  file=sys.stderr)
        live = {str(x["number"]) for x in rows}
        titles = {str(x["number"]): x["title"] for x in rows}

    # ---------------------------------------------------- the derived fleet
    units = lane_units()
    fleet_blind = units is None
    if fleet_blind:
        units = {}
        print("FLEET-BLIND: systemctl --user did not answer, so the RUNNING "
              "set could not be computed. RUNNING below is EMPTY BECAUSE IT "
              "WAS NOT ASKED, which is not the same as an idle fleet -- and "
              "the sections that subtract it (DISPATCHABLE, LANE CLAIMED "
              "WITH NO RUNNING AGENT, RUNNING WITH NO TERRITORY ROW, BLOCKER "
              "NEVER RECORDED AS TESTED) are suppressed rather than computed "
              "against an empty set.",
              file=sys.stderr)
    running = sorted(units)

    # AND IT IS ITS OWN FAIL, unlike the gh blindness below. board.sh keeps
    # only the lines matching '^FAIL' and drops the rest, so anything said any
    # other way is said to nobody -- which is how this whole file came to
    # report calm for five days. The two are not treated alike on purpose:
    #
    #   gh unreachable   transient, retried in twenty minutes, nothing a board
    #                    tick can do about it. Fails open, as it always has.
    #   systemctl --user unreachable FROM A PROCESS WHOSE JOB IS TO MANAGE
    #                    USER UNITS is a configuration defect. It does not
    #                    self-heal and nobody finds out any other way.
    if fleet_blind:
        print("FAIL: FLEET-BLIND -- systemctl --user did not answer, so this "
              "report cannot say what is running. No other FAIL below was "
              "computed. Check the user manager on the host "
              "(`systemctl --user list-units`); the fleet is unobservable "
              "until it answers.", file=sys.stderr)

    prs = lane_prs()
    pr_blind = prs is None
    if pr_blind:
        prs = []
        print("PR-BLIND: gh pr list did not answer, so READY NOT FOLDED and "
              "BLOCKED were not computed. Fails open like the issue list "
              "above: a network blip is not a board item.", file=sys.stderr)

    # An entry for a lane whose unit is not active is garbage by construction:
    # lane.sh writes one at start and unlinks it at exit. Counted, never shown
    # as a lane, never able to suppress a dispatch. See the header.
    stale_reg = sorted(k for k in fleet if k not in units)

    owned = {}
    for lane, meta in (terr.get("lane") or {}).items():
        for i in meta.get("issues", []):
            owned[str(i)] = lane
    # A RUNNING lane's own issues, from the registry lane.sh wrote at start.
    # This is the one place the registry can withhold work, and it can only do
    # so for a lane systemd says is live this second.
    for lane in running:
        for i in (fleet.get(lane, {}).get("issues") or []):
            owned.setdefault(str(i), lane)
    lanes_with_agent = set(running)

    # REPORTED, NOT FOLDED, asked of GitHub instead of a `state` field: an
    # open lane PR that is not a draft is a lane that has said it is done.
    # Carrying one of IN_FLIGHT means a job already holds it, and that is the
    # pipeline working, not an item for the board.
    unfolded = [p for p in prs
                if not p.get("isDraft") and not (p["labelset"] & IN_FLIGHT)]

    # WAITING. The old section read the registry's `waiting_on` and printed it
    # under "WAITING ON THE ORCHESTRATOR"; there is no orchestrator, nothing
    # has written that field since 09-14, and papercuts.toml bit 245 records
    # that the field conflated four different waiters anyway. A lane that is
    # stuck now says so with the `blocked` label and a `[lane.<n>] blocked:`
    # comment (roles/lane.md), and the board's step 5 acts on the label.
    #
    # WHAT THIS CANNOT SEE: a blocked: COMMENT with no label. Reading comments
    # is a call per PR and the budget here is two calls total, so the label is
    # the contract. A lane that only comments is invisible to the board.
    waiting = [p for p in prs if "blocked" in p["labelset"]]

    # A lane row with no running agent is coverage that does not exist. This is
    # the state territory.toml's own [free] comment warns about, and nothing
    # could detect it before.
    #
    # Empty when fleet-blind, or it would name EVERY territory row: it is the
    # one section here that an empty running set makes maximally wrong rather
    # than merely silent. It sets no rc, so this changes no wake-up -- but a
    # reader acting on a full list of "abandoned" claims would retire the live
    # fleet's rows, and the FLEET-BLIND line promises it is not computed.
    ghost = [] if fleet_blind else sorted(
        lane for lane in (terr.get("lane") or {}) if lane not in units)

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
    # THE RESIDUAL HOLE IS NOW CLOSED, AND THAT IS WHY THIS SECTION FILLED UP.
    # Until 2026-09-19 both sides of this cross-check were orchestrator-written
    # files, so "a lane running with no fleet row EITHER" was invisible here as
    # well -- and after the role was deleted that was EVERY lane. The running
    # side is systemd now. The first run of this version against the live host
    # found nine active units and eleven territory rows with no unit among
    # them: an entirely disjoint pair of sets, six of the nine editing
    # docs/testing/jobs/selftest.sh at the same time. This FAIL is cleared by
    # the board writing the rows, which is AGENTS.md's ordering anyway.
    unclaimed = sorted(lane for lane in running
                       if lane not in (terr.get("lane") or {}))

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
    #
    # DISPATCHABLE IS NOW A STRUCTURED FIELD TOO, AND THE PROSE SNIFF IS GONE.
    # This section used to read `"NOT BLOCKED" in blocked_on.upper()`, which
    # was the right instinct against the wrong schema: check_coverage.py
    # accepted ANY non-empty `blocked_on` as coverage and nothing else, so the
    # board's only way to satisfy preflight for an issue it could not dispatch
    # this tick was to write into the field that means "do not dispatch this" --
    # and six open rows on 2026-09-18 duly opened with the words "NOT BLOCKED".
    # The sniff undid that from this side and cost a false positive to do it:
    # #92's field says "I had written NOT BLOCKED and then left it
    # unallocated", the board recording a wording it had ALREADY corrected,
    # and the substring search reported the row as dispatchable on the
    # strength of that sentence.
    #
    # `dispatch_state = "available"` is now the third state check_coverage.py
    # accepts, so the prose has no job left. "Available" is about the
    # OBSTACLE; whether a lane is on it is territory.toml's, which is why the
    # running-lane skip above still applies on top of it.
    #
    # AN UNCLASSIFIED ROW IS REPORTED SEPARATELY AND STILL SETS rc. No
    # blocker, no `dispatch_state`, no running lane: an empty row is not a
    # dispatch queue, and calling it dispatchable would assert the board is
    # sitting on work it can start -- a stronger claim than an empty row
    # supports, and exactly the "available by default" direction that got
    # finished work re-dispatched before.
    #
    # AND IT MUST NOT STOP COSTING A FAIL, which took a second pass to see. The old
    # code called such a row dispatchable, which was the wrong description AND
    # a non-zero exit; moving it to a note would have been the right
    # description and a SILENT one. #34 and #62 are in exactly this state on
    # the live board today (owned by lane.remote, no blocker, nothing else), so
    # the hole would have opened the moment that lane stopped running. Separate
    # section, accurate words, same exit code.
    dispatchable = []
    untested = []
    unclassified = []
    # fleet_blind: "I could not ask systemd" is not "nothing is running", and
    # the running-lane skip below is what keeps a live lane's rows out of both
    # lists. With no running set there is nothing to skip WITH, so neither
    # section is computed -- see the NOT COMPUTED headings below.
    for n in ([] if fleet_blind else sorted(live, key=int)):

        lane = owned.get(n)
        if lane and lane in lanes_with_agent:
            continue
        ent = tracker.get(n, {})
        b = (ent.get("blocked_on") or "").strip()
        st = (ent.get("dispatch_state") or "").strip()
        if st == "available":
            dispatchable.append((n, lane, "dispatch_state=available",
                                 titles.get(n, "")[:52]))
        elif b and not (ent.get("blocker_tested") or "").strip():
            untested.append((n, lane, (ent.get("blocker_falsifier") or "").strip(),
                             titles.get(n, "")[:52]))
        elif not b and st != "blocked":
            unclassified.append((n, lane, titles.get(n, "")[:52]))

    pr_of = {}
    for p in prs:
        pr_of.setdefault(p["lane"], p)

    print("=== RUNNING (%d)%s" % (len(running),
                                  "  -- NOT COMPUTED, see FLEET-BLIND above"
                                  if fleet_blind else ""))
    for lane in running:
        f = fleet.get(lane, {})
        p = pr_of.get(lane)
        print("  %-12s %-18s #%-10s %-7s %s"
              % (lane,
                 ("attempt %s/%s" % (f.get("attempt", "?"),
                                     (f.get("model") or "?").replace("claude-", "")))[:18],
                 ",".join(str(i) for i in (f.get("issues") or [])) or "-",
                 age_s(units.get(lane)),
                 ("PR #%d%s" % (p["number"], " draft" if p.get("isDraft") else " READY"))
                 if p else "no PR yet"))
        print("      asked: %s" % ((f.get("asked") or
                                    "(no registry entry -- started before "
                                    "lane.sh wrote one, or not by lane.sh)")[:96]))
    if stale_reg:
        print("  (%d registry entr%s for lanes with no active unit, ignored; "
              "`lane.sh fleet-gc` deletes them)"
              % (len(stale_reg), "y" if len(stale_reg) == 1 else "ies"))

    print("\n=== READY, NOT FOLDED (%d)%s"
          % (len(unfolded), "  -- NOT COMPUTED, see PR-BLIND above" if pr_blind else ""))
    for p in unfolded:
        print("  %-12s #%-5d %-9s %s"
              % (p["lane"], p["number"],
                 "unit up" if p["lane"] in units else "finished",
                 (p.get("title") or "")[:60]))
    print("\n=== BLOCKED (labelled `blocked`) (%d)" % len(waiting))
    for p in waiting:
        print("  %-12s #%-5d %s" % (p["lane"], p["number"], (p.get("title") or "")[:70]))
    print("\n=== LANE CLAIMED WITH NO RUNNING AGENT (%d)%s"
          % (len(ghost),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    for lane in ghost:
        print("  %-12s holds %d file(s), issues %s"
              % (lane, len((terr["lane"][lane].get("files") or [])),
                 ",".join(str(i) for i in (terr["lane"][lane].get("issues") or []))))
    print("\n=== RUNNING WITH NO TERRITORY ROW (%d)" % len(unclaimed))
    if unclaimed:
        print("  Invisible to every guard: check_territory.py cannot see a "
              "lane that is not in the file. A row with files = [] still "
              "counts as claimed.")
    for lane in unclaimed:
        f = fleet.get(lane, {})
        print("  %-12s %-7s %s" % (lane, age_s(units.get(lane)),
                                   (f.get("asked") or "(no registry entry)")[:70]))
    print("\n=== DISPATCHABLE NOW, NOT DISPATCHED (%d)%s"
          % (len(dispatchable),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    for n, lane, why, title in dispatchable:
        print("  #%-4s %-12s %-26s %s" % (n, lane or "-", why, title))

    # SEPARATE SECTION, AND DELIBERATELY NOT PART OF THE EXIT CODE. These are
    # not known-dispatchable; they are blockers nobody has recorded testing.
    # Folding them into the FAIL above would say the board is holding work it
    # can start, which is a stronger claim than the evidence supports.
    print("\n=== BLOCKER NEVER RECORDED AS TESTED (%d)%s"
          % (len(untested),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    if untested:
        print("  A blocker is a claim. Five were refuted in two days, two of"
              " them the orchestrator's own.")
    for n, lane, fals, title in untested:
        print("  #%-4s %-12s %-30s %s"
              % (n, lane or "-",
                 ("falsifier: " + fals[:24]) if fals else "NO FALSIFIER WRITTEN",
                 title))

    # NOT A DISPATCH QUEUE, BUT STILL PART OF THE EXIT CODE (see above). These
    # rows say nothing at all: no blocker, no `dispatch_state`, no running
    # lane.
    # The qualifier is master's (ae3712aae1) and applies here for its reason:
    # this list is built by the same running-lane-skipped loop, so under
    # FLEET-BLIND a bare (0) would read as "nothing is unclassified" when what
    # happened is that nothing was looked at.
    print("\n=== NEITHER BLOCKED NOR MARKED AVAILABLE (%d)%s"
          % (len(unclassified),
             "  -- NOT COMPUTED, see FLEET-BLIND above" if fleet_blind else ""))
    if unclassified:
        print("  An empty row is not a dispatch queue -- write "
              "`dispatch_state = \"available\"` if nothing blocks it, or the "
              "blocker if something does. check_coverage.py fails on these.")
    for n, lane, title in unclassified:
        print("  #%-4s %-12s %s" % (n, lane or "-", title))

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

    # EVERY LINE BELOW IS A BOARD WAKE-UP. board.sh greps stdout+stderr for
    # '^FAIL' and starts a model session on any hit, so a FAIL that cannot be
    # cleared by the board spends a window every twenty minutes for nothing.
    # Each one names the actor and the action that clears it.
    rc = 1 if fleet_blind else 0   # the FLEET-BLIND FAIL was printed above
    if waiting:
        print("\nFAIL: %d lane PR(s) labelled `blocked`: %s. Grant the file or "
              "answer the question and remove the label -- 'ask and I will "
              "grant it' is a deadlock (roles/board.md)."
              % (len(waiting), ", ".join("#%d" % p["number"] for p in waiting)),
              file=sys.stderr)
        rc = 1
    if dispatchable:
        print("FAIL: %d issue(s) could be dispatched and are not." % len(dispatchable),
              file=sys.stderr)
        rc = 1
    if unclassified:
        print("FAIL: %d open issue(s) are NEITHER BLOCKED NOR MARKED "
              "AVAILABLE and no lane is running on them -- %s. An empty row "
              "is not a dispatch queue and it is not coverage either: write "
              "the blocker, or `dispatch_state = \"available\"`."
              % (len(unclassified),
                 ", ".join("#" + n for n, _, _ in unclassified)),
              file=sys.stderr)
        rc = 1
    if unfolded:
        print("FAIL: %d lane PR(s) are READY and carry no pipeline label: %s. "
              "A ready PR with no needs-audit-*/needs-remediation/fold-ready/"
              "folded label is stalled -- nothing else will pick it up."
              % (len(unfolded), ", ".join("#%d" % p["number"] for p in unfolded)),
              file=sys.stderr)
        rc = 1
    # NON-ZERO, LIKE THE OTHERS. `ghost` is printed and deliberately does not
    # set rc, because a stale claim OVER-reports coverage and that errs safe.
    # This one UNDER-reports it: the lane is editing files nothing knows it
    # holds, so a second lane can be handed the same file and both preflights
    # will pass.
    if unclaimed:
        print("FAIL: %d lane(s) are RUNNING with no territory row -- %s. "
              "Nothing can see them: check_territory.py cannot detect a "
              "collision with a lane that is not in the file. Write the row "
              "(files = [] is a valid claim), validate, commit, PUSH."
              % (len(unclaimed), ", ".join(unclaimed)), file=sys.stderr)
        rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
