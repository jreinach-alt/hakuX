#!/usr/bin/env bash
#
# The issue sweep. Runs from hakux-issue-sweep.timer twice a day, and never
# starts a model session of its own: it is a script, start to finish.
#
#   issue-sweep.sh          sweep; write the findings where the board reads them
#   issue-sweep.sh list     the findings, on stdout, writing nothing
#
# WHY IT DOES NOT DECIDE, AND WHY IT DOES NOT START A SESSION EITHER.
#
# Four things about the backlog are decidable from files: whether a row is
# still `unclassified`, whether the lane a row names still exists, whether an
# open issue has a tracker row at all, and whether a row's own `status` says
# the work is done while the issue is open. Those are the classes below.
#
# "Is this blocker still true?" and "can this `decision-needed` be settled?"
# are NOT decidable from files -- they need someone to read the issue and the
# code. This harness already has exactly one actor for that: the board tick
# (jobs/board.sh, roles/board.md), which is also the ONLY actor permitted to
# write nv2a_issues.toml at all. A second model session on a second timer
# would be a second writer of the same two files, reaching the same
# conclusions from a worse vantage point, and cloud.sh's header is a long
# apology for the last time this harness grew a second mechanism that differed
# from the first only in which labels it read.
#
# So the findings go into a file the board's gate reads, and the board's next
# tick decides. The handoff is at $WORK/board/issue-sweep.findings; board.sh
# reads it as a fifth gate, keys it on the file's sha256 so one set of
# findings wakes at most one tick, and marks it seen only when that tick
# actually ran. Unchanged findings therefore go quiet on their own, which is
# the property board.sh demands of every trigger: "a gate that always fires is
# this defect with its sign flipped".
#
# WHAT IT DELIBERATELY DOES NOT REPORT. check_coverage.py already runs on
# every lane's preflight and in the board's own tick, and it already fails on:
# a tracker row saying `open` for an issue closed on GitHub, a `dispatch_state`
# that does not hold, a `blocked_on` whose leading claim is that it is not
# blocked, and a `fixed-unlanded` sha that is now an ancestor. None of that is
# repeated here. This file is about the states that gate is silent on.
#
# IT WRITES NO BOARD FILE AND OPENS NO ISSUE. roles/lane.md forbids a lane
# touching territory.toml or nv2a_issues.toml and the owner's standing rule
# forbids opening a GitHub issue for a harness defect; this script is bound by
# both. It writes two files under $WORK and nothing else.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTING="$(dirname "$J")"
. "$J/localtime.sh"   # say_time_s: the display zone. Data timestamps below stay `date -u`.
# NOT A BARE `.`, for lane.sh's reason: without the guard a missing file leaves
# remote_authoritative undefined, the command-not-found does not stop a script
# with no `set -e`, and the gate below would run to completion having checked
# nothing -- on the one question whose wrong answer hands a live lane's
# territory to the board as stale.
. "$J/remote-lane.sh" || {
    echo "issue-sweep: could not load $J/remote-lane.sh, so this tick cannot tell a remote lane from a dead one; it writes nothing." >&2
    exit 0
}
mkdir -p "$WORK/logs/issue-sweep" "$WORK/status" "$WORK/board"
LOG="$WORK/logs/issue-sweep/tick.log"
REPORT="$WORK/status/issue-sweep.md"
FINDINGS="$WORK/board/issue-sweep.findings"
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
mode="${1:-run}"

# How long an `available` row may sit with nobody on it before the sweep calls
# it unpicked. The board ticks every 20 minutes, so three days is well over
# two hundred chances to dispatch it; anything shorter reports the ordinary
# condition of a backlog under a lane cap.
AVAIL_SECS="${ISSUE_SWEEP_AVAIL_SECS:-259200}"
# How long a REMOTE lane's branch tip may sit unmoved before the sweep is
# willing to call its territory claim stale. Same three days, and set HERE
# beside its neighbour rather than at its point of use: $WORK/limits.env is
# sourced on the next line, and a dial assigned after it is one the owner's
# file cannot raise.
REMOTE_QUIET_SECS="${ISSUE_SWEEP_REMOTE_QUIET_SECS:-259200}"
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"

if ! command -v gh >/dev/null 2>&1 || ! timeout 30 gh auth status >/dev/null 2>&1; then
    # Fails quiet, exactly as check_coverage.py fails open: this compares LIVE
    # GitHub state against the board's files, and with one side missing every
    # row would read as a finding.
    say "no usable gh; this tick is blind and writes nothing"
    exit 0
fi

# THE BOARD LIVES ON THE `board` BRANCH. board_files.load() prefers
# origin/board and falls back to the working tree, and master's copy is
# fold-lagged behind it by whole waves -- so a sweep that read the tree would
# report rows the board fixed hours ago. Fetch the ref before reading it, the
# way board.sh does, and print which source was used.
#
# TWO FETCHES, NOT ONE COMMAND WITH TWO REFSPECS. `git fetch origin master
# board` fails the WHOLE invocation with exit 128 when either name matches no
# remote ref, and updates NOTHING -- so a host whose origin has no `board`
# branch yet would silently not fetch the trunk either. One refspec per call
# means one missing ref costs only itself.
git -C "$REPO" fetch -q origin "$TIP" 2>/dev/null || true
git -C "$REPO" fetch -q origin board 2>/dev/null || true

# ------------------------------------------- the lanes this host cannot see
#
# WHY THIS GATE IS THE FIRST THING AFTER THE FETCH. The `ghost` class below
# decides that a territory claim is stale, and it decides it from an ABSENCE:
# no unit, no open PR. `lane.remote` is a cloud session that has neither by
# design -- no local systemd unit ever, and no open PR between PRs -- so the
# absence test called it dead and handed three of its live claims to the board
# as stale. Releasing a live lane's territory is how two agents end up editing
# one file, which is the single thing territory.toml exists to prevent.
#
# THE MAP HAS TO BE THE BOARD'S, AND `remote_authoritative` IS THE ONLY
# PREDICATE THAT SAYS SO. remote-lane.sh's header spells out the third outcome:
# board_files.load() falls back to the fold-lagged IN-TREE territory.toml when
# origin/board cannot be read, and returns it SUCCESSFULLY. That copy reaches a
# tree only when some later fold carries it over, so it is exactly the copy
# guaranteed to be missing a `remote` marker the board has just written. Read
# through `remote_readable` this tick would proceed on a map missing the one
# row it exists for -- the same findings, the same release, and no symptom.
#
# So a map that is not the board's disables the WHOLE tick, not just the ghost
# class. This sweep's every class compares live GitHub against the board's
# files; on a stale board it reports rows the board fixed hours ago, in every
# class at once. It already says as much four paragraphs up. This enforces it.
# The cure is one command and the refusal names it.
if ! remote_authoritative; then
    say "the board read came back \`$(remote_source)\` rather than origin/board, so this tick cannot tell a remote lane from a dead one, and every class it reports would be read from a fold-lagged copy. It writes nothing and leaves any existing findings alone. Cure: \`git fetch origin board\` in $REPO."
    exit 0
fi

# WHAT THIS HOST CAN ACTUALLY SEE OF A REMOTE LANE. Not a unit -- there never
# is one -- so: an open PR on ITS branch (not on `lane/<name>`, which is not
# its branch and never will be), and the commit time of that branch's tip. A
# lane that has pushed is unambiguously working, and a push is the one thing a
# remote session does that this host can read for free.
#
# ITS COMMENTS ARE THE OTHER SIGNAL AND ARE DELIBERATELY NOT HERE. There is no
# cheap query for "has lane.X commented anywhere recently": it is a search
# across every open issue and PR, per lane, twice a day, and the answer it
# gives is strictly weaker than the branch tip -- a session can comment without
# having done anything, and cannot push without having. The tip is the
# evidence; if it ever stops being enough, the thing to add is the search, and
# this paragraph is what to re-read first.
#
# A TIP THAT CANNOT BE READ IS NOT AN OLD TIP. The branch may not be on this
# origin at all (a fork, a ref nobody fetched). "Cannot tell" is not "dead",
# and the safe direction here is silence: the cost of a claim held a day too
# long is a file nobody else may edit, and the cost of the other direction is
# two agents on one.
remote_rows=""
while IFS=$'\t' read -r rbranch rlane; do
    [ -n "${rbranch:-}" ] && [ -n "${rlane:-}" ] || continue
    git -C "$REPO" fetch -q origin "+refs/heads/$rbranch:refs/remotes/origin/$rbranch" 2>/dev/null || true
    rtip=$(git -C "$REPO" log -1 --format=%ct "refs/remotes/origin/$rbranch" 2>/dev/null || echo "")
    case "${rtip:-}" in ''|*[!0-9]*) rtip="" ;; esac
    remote_rows="${remote_rows}${rlane}	${rbranch}	${rtip}
"
done <<< "$(remote_map)"

issues=$(timeout 60 gh issue list --repo "$GH_REPO" --state open --limit 300 \
           --json number,title,labels,updatedAt 2>/dev/null)
if [ -z "$issues" ]; then
    say "gh returned nothing for the open issue list; this tick is blind and writes nothing"
    exit 0
fi
# Open PR head branches: one of the three independent ways a lane can still
# exist. Asked once, here, rather than per finding.
pr_heads=$(timeout 60 gh pr list --repo "$GH_REPO" --state open --limit 100 \
             --json headRefName --jq '.[].headRefName' 2>/dev/null)
units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null \
        | awk '{print $1}' | sed 's/\.service$//')

report=$(python3 - "$TESTING" "$issues" "$pr_heads" "$units" "$AVAIL_SECS" "$remote_rows" "$REMOTE_QUIET_SECS" <<'PY'
import datetime
import os
import sys

testing, issues_raw, heads_raw, units_raw, avail_raw, remote_raw, rquiet_raw = sys.argv[1:8]
sys.path.insert(0, testing)
import json
import board_files

heads = set(h.strip() for h in heads_raw.splitlines() if h.strip())
units = set(u.strip() for u in units_raw.splitlines() if u.strip())
AVAIL = int(avail_raw) if avail_raw.isdigit() else 259200
RQUIET = int(rquiet_raw) if rquiet_raw.isdigit() else 259200

# lane -> (branch, tip epoch or None), built in bash from remote-lane.sh's map
# and this repository's refs. Empty is the ordinary case and means every lane
# is local; it is NOT the "could not read" case, which never reaches here --
# the tick refuses before this runs.
REMOTE = {}
for line in remote_raw.splitlines():
    parts = line.split("\t")
    if len(parts) == 3 and parts[0] and parts[1]:
        REMOTE[parts[0]] = (parts[1], int(parts[2]) if parts[2].isdigit() else None)

try:
    terr = board_files.load("territory.toml")
    tracker = board_files.load("nv2a_issues.toml")["issue"]
except Exception as e:
    print("SWEEP-BLIND: could not read the board files: %s" % e)
    sys.exit(0)
src = "territory.toml <- %s, nv2a_issues.toml <- %s" % (
    board_files.source("territory.toml"), board_files.source("nv2a_issues.toml"))

lanes = terr.get("lane") or {}
owned = {}
for lane, meta in lanes.items():
    for i in meta.get("issues", []):
        owned.setdefault(str(i), []).append(lane)

try:
    issues = json.loads(issues_raw or "[]") or []
except Exception:
    print("SWEEP-BLIND: the open-issue list did not parse")
    sys.exit(0)

now = datetime.datetime.now(datetime.timezone.utc)


def age(s):
    try:
        return int(now.timestamp()
                   - datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except Exception:
        return None


def days(sec):
    return "%.1fd" % (sec / 86400.0) if sec is not None else "unknown"


def lane_absence(name):
    """None when the lane still exists; otherwise the phrase that says how it is gone.

    The facts that are NOT a board file: a running unit, or an open PR.
    fleet.py had to relearn that one -- liveness comes from systemd and the
    rest from GitHub, never from a file that records what was true once.

    A REMOTE LANE HAS NEITHER OF THOSE FACTS AND IS NOT DEAD. `lane.remote` is
    a cloud session: no local unit ever, and no open PR between PRs. Asking
    systemd about it is asking the wrong host, and asking for `lane/<name>` is
    asking for a branch that is not its branch. What this host can see of it is
    an open PR on the branch its territory row names, and that branch's tip.

    It returns a PHRASE rather than a bool because the phrase goes on the
    finding: a reader handed "no unit and no open PR" about a cloud lane is
    being told something true of every cloud lane at every moment, and would
    reasonably release the claim.
    """
    r = REMOTE.get(name)
    if r is None:
        if ("hakux-lane-%s" % name) in units:
            return None
        if ("lane/%s" % name) in heads:
            return None
        return "has no unit and no open PR"
    branch, tip = r
    if branch in heads:
        return None
    if tip is None:
        # The branch is not on this origin, or could not be fetched. "Cannot
        # tell" is not "dead"; see the header above the fetch loop in bash.
        return None
    quiet_for = int(now.timestamp() - tip)
    if quiet_for <= RQUIET:
        return None
    return ("is a REMOTE lane on `%s` (it has no local unit by design, so that "
            "is not evidence), and that branch's tip has not moved in %s and it "
            "has no open PR" % (branch, days(quiet_for)))


def lane_live(name):
    return lane_absence(name) is None


def lane_exists(name):
    """Three independent ways a lane can still exist; any one is enough.

    A territory row counts HERE because a row is the board's live allocation:
    an issue labelled for a lane the board still has a row for is allocated,
    not orphaned. It deliberately does NOT count for the territory-row shape
    below, where the row is the thing under suspicion -- a claim cannot be the
    evidence for itself, and letting it be made that whole class unreportable.
    """
    return lane_live(name) or name in lanes


unclassified, ghost, closable, norow, unpicked = [], [], [], [], []

for r in issues:
    n = str(r.get("number"))
    title = (r.get("title") or "").strip()
    names = [l.get("name", "") for l in (r.get("labels") or [])]
    quiet = age(r.get("updatedAt") or "")
    row = tracker.get(n)

    # 1. NO TRACKER ROW AT ALL. This is #164's state on 2026-09-19, and it is
    #    not a private inconvenience: check_coverage.py counts it as a gap, so
    #    preflight goes red for EVERY lane and every fold at once until the
    #    board writes the row. Reported here anyway, with that consequence
    #    said out loud, because the coverage gate reports it as one line in a
    #    list of gaps and this says what it costs.
    if row is None:
        norow.append((n, title, quiet, names))
        continue

    status = (row.get("status") or "").strip()
    disp = (row.get("disposition") or "").strip()
    dstate = (row.get("dispatch_state") or "").strip()

    # 2. UNTRIAGED. `unclassified` is a legal disposition and check_coverage.py
    #    accepts it, correctly -- the tracker's own header says a guess there
    #    is worse than an admission of ignorance. But an issue can then sit
    #    untriaged indefinitely with nothing ever asking, which is what this
    #    line is for. Triage is a judgement, so it goes to the board.
    if disp in ("", "unclassified"):
        unclassified.append((n, title, disp or "(absent)", quiet))

    # 3. AN OWNER THAT NO LONGER EXISTS. Two shapes, one meaning: the row or
    #    the label says somebody holds this and nobody does.
    #
    #    The `lane:` LABEL is the dangerous one. board_filter's SKIP_PREFIX
    #    drops every issue carrying one, so an issue labelled for a lane that
    #    has exited is invisible to the board's capacity trigger FOREVER --
    #    the same shape as an orphaned `claimed:cloud`, and with no `finish`
    #    to run. `cloud.sh finish` does not remove it either: the issue path
    #    adds `lane:cloud-<n>` at claim and clears only `claimed:cloud`.
    #
    #    A THIRD SHAPE WAS ASKED FOR AND IS DELIBERATELY NOT HERE: a
    #    `blocked_on` that NAMES a lane which no longer exists. It was
    #    implemented, then measured against the live board on 2026-09-19, and
    #    it is a false-positive generator: it produced 11 of 16 findings and
    #    every one of them was the field doing its job. #91's reads "PR #102
    #    (lane.blitsafe, folded into master 3d072c6ea6) did NOT deliver a fix
    #    here"; #13's records a tracker note written at lane.lows' request;
    #    #68's attributes a three-arm re-run. A blocker NAMES the lane that
    #    established it, and that lane having finished is the normal case --
    #    naming it is history, not a claim of ownership.
    #
    #    Narrowing it to "waiting on lane.X" rather than dropping it was the
    #    obvious alternative and was rejected: there is not one positive
    #    example on the live board to calibrate such a phrase list against, so
    #    it would be a classifier whose only tested case is the negative one.
    #    A gate that is wrong eleven times out of sixteen on its first real
    #    run teaches its reader to skip the section, which costs more than the
    #    shape is worth.
    ghosts = []
    for lbl in names:
        if lbl.startswith("lane:") and not lane_exists(lbl[5:]):
            ghosts.append("label `%s` (no territory row, and the lane %s)"
                          % (lbl, lane_absence(lbl[5:])))
    for lane in owned.get(n, []):
        # `standing` rows are a deliberate long-lived reservation and are not
        # tied to a session at all, so "no unit" says nothing about them.
        if (lanes.get(lane) or {}).get("standing"):
            continue
        gone = lane_absence(lane)
        if gone is not None:
            ghosts.append("territory row `lane.%s` claims it and that lane %s"
                          % (lane, gone))
    if ghosts:
        ghost.append((n, title, ghosts, quiet))

    # 4. THE ROW SAYS THE WORK IS DONE AND THE ISSUE IS OPEN. The tracker's
    #    own header calls `fixed-verified` and `unmodellable` Closable, and
    #    both carry their evidence in the row. check_coverage.py checks the
    #    OPPOSITE direction only (tracker `open`, GitHub closed), because that
    #    is the one that causes re-dispatch; this one merely leaves finished
    #    work on the board looking like work. Closing is the board's call --
    #    a `fixed-part` remainder can hide behind either value -- so this
    #    reports and closes nothing.
    if status in ("fixed-verified", "unmodellable"):
        closable.append((n, title, status, (row.get("status_note") or "")[:150]))

    # 5. AVAILABLE, AND NOBODY PICKED IT UP. `available` means nothing blocks
    #    it. With capacity under LANE_MAX the board's positive gate dispatches
    #    one such issue per tick, so a row that has been available and
    #    unowned for days is either starved by the cap (fine, and the board
    #    should say so) or invisible to that gate for some other reason.
    if (dstate == "available" and not owned.get(n)
            and not any(l.startswith("lane:") for l in names)
            and quiet is not None and quiet > AVAIL):
        unpicked.append((n, title, quiet))

out = []
w = out.append
w("Board source: %s" % src)
# SAID EVEN WHEN NOTHING IS WRONG WITH THEM, because the reader of a finding
# about a remote lane needs to know the sweep knew it was one -- and because a
# tick that has stopped seeing them at all (a marker dropped from the board,
# say) reads exactly like a tick where there are none.
if REMOTE:
    w("Remote lanes, judged by branch tip and not by a unit: %s"
      % ", ".join("lane.%s on `%s`%s" % (l, b, "" if t else " (tip unreadable here)")
                  for l, (b, t) in sorted(REMOTE.items())))
w("")
if norow:
    w("### %d open issue(s) with NO tracker row" % len(norow))
    w("")
    w("`check_coverage.py` counts each of these as a coverage gap, and that gate "
      "runs in every lane's `preflight.sh` AND in your own tick -- so until the "
      "row exists, **every lane's push and every fold is red on this**. You are "
      "the only actor permitted to write `nv2a_issues.toml`. Clear these first.")
    w("")
    for n, t, q, names in norow:
        w("- #%s %s -- open %s, labels: %s" % (n, t[:70], days(q), ", ".join(names) or "none"))
    w("")
if ghost:
    w("### %d open issue(s) owned by a lane that no longer exists" % len(ghost))
    w("")
    w("A lane exists if it has an active `hakux-lane-*` unit, a `territory.toml` "
      "row, or an open PR on `lane/<name>` -- or, for a lane whose row carries "
      "`remote`, an open PR on the branch that row names or a branch tip that "
      "has moved inside %s. None of these has any of those. "
      "An issue carrying a `lane:` label is skipped by your own capacity filter "
      "(`board_filter`'s SKIP_PREFIX), so a label for a dead lane makes the "
      "issue invisible to dispatch permanently -- the same shape as an orphaned "
      "`claimed:cloud`, with no `finish` to run. Decide per issue: the work "
      "landed (close it, or set the status), or it did not (drop the stale "
      "label and the stale row, and it becomes dispatchable again)." % days(RQUIET))
    w("")
    for n, t, gs, q in ghost:
        w("- #%s %s -- quiet %s" % (n, t[:70], days(q)))
        for g in gs:
            w("  - %s" % g)
    w("")
if unclassified:
    w("### %d open issue(s) whose tracker row is untriaged" % len(unclassified))
    w("")
    w("`disposition = \"unclassified\"` is legal and `check_coverage.py` accepts "
      "it -- the tracker's header is explicit that a guess there is worse than "
      "an admission of ignorance. Nothing else ever asks about one, which is "
      "why it is here. Triage each against the goldens, or say in the row what "
      "measurement would settle it. Do not invent a disposition to clear this "
      "list: an untriaged row that is honestly untriaged is a correct row.")
    w("")
    for n, t, d, q in unclassified:
        w("- #%s %s -- disposition %s, quiet %s" % (n, t[:70], d, days(q)))
    w("")
if closable:
    w("### %d open issue(s) whose tracker row already says the work is done" % len(closable))
    w("")
    w("The tracker's header calls both `fixed-verified` and `unmodellable` "
      "closable, and each row carries its own evidence. This is the direction "
      "`check_coverage.py` does NOT check (it fails on `open` rows for closed "
      "issues, because that is what causes re-dispatch). Read the note before "
      "closing: a `fixed-part` remainder can be described in either row.")
    w("")
    for n, t, s, note in closable:
        w("- #%s %s -- status `%s`%s" % (n, t[:70], s, (" -- " + note) if note else ""))
    w("")
if unpicked:
    w("### %d `available` issue(s) nobody has picked up" % len(unpicked))
    w("")
    w("Each is `dispatch_state = \"available\"` (so nothing blocks it), carries "
      "no `lane:` label, is claimed by no `territory.toml` row, and has not "
      "changed in over %s. Either the lane cap has starved it, which is a fine "
      "answer worth saying once in the row, or something is keeping it off your "
      "capacity list." % days(AVAIL))
    w("")
    for n, t, q in unpicked:
        w("- #%s %s -- quiet %s" % (n, t[:70], days(q)))
    w("")
# COUNTED ON THE HEADINGS, NOT ON THE LENGTH. `len(out) <= 2` meant "only the
# two header lines", which is true until the header grows a line -- and then
# the quiet verdict is never printed and a clean sweep reads as an unfinished
# one. The thing being asked is "did any class speak", and `### ` is how a
# class speaks; it is also what `n_find` counts in bash, so the two agree by
# construction rather than by both being edited at the same time.
if not any(line.startswith("### ") for line in out):
    w("Nothing stuck: every open issue has a tracker row, a live owner or none, "
      "a triaged disposition, and no row claims finished work on an open issue.")
print("\n".join(out))
PY
)

n_find=$(grep -c '^### ' <<< "$report" || true)
case "${n_find:-}" in ''|*[!0-9]*) n_find=0 ;; esac
blind=$(grep -c '^SWEEP-BLIND' <<< "$report" || true)
case "${blind:-}" in ''|*[!0-9]*) blind=0 ;; esac

if [ "$mode" = list ]; then
    printf '%s\n' "$report"
    exit 0
fi

{
    echo "# issue sweep -- $(date -u +%FT%TZ)"
    echo
    echo "Written by \`docs/testing/jobs/issue-sweep.sh\` on hakux-issue-sweep.timer."
    echo "Every class here is decided from files; nothing in it is repaired by the"
    echo "sweep, because \`nv2a_issues.toml\` has exactly one writer and it is the"
    echo "board. The same findings are handed to the board's gate at"
    echo "\`$FINDINGS\`, keyed on their sha256 so one set wakes at most one tick."
    echo
    printf '%s\n' "$report"
} > "$REPORT"

# THE HANDOFF. The file is the trigger, so it exists only while there is
# something to trigger on: a findings file that is always present is a gate
# that always fires. A blind tick writes NOTHING and removes nothing -- it
# established no facts, and deleting the last good findings on a gh outage
# would discharge them without anyone having read them.
if [ "$blind" -gt 0 ]; then
    say "the board files or the issue list could not be read; leaving any existing findings alone"
    exit 0
fi
if [ "$n_find" -eq 0 ]; then
    rm -f "$FINDINGS"
    say "nothing stuck across $(python3 -c 'import json,sys; print(len(json.loads(sys.argv[1]) or []))' "$issues" 2>/dev/null || echo '?') open issue(s); report $REPORT"
    exit 0
fi
printf '%s\n' "$report" > "$FINDINGS"
say "$n_find class(es) of stuck issue; findings at $FINDINGS for the board's next tick, report $REPORT"
exit 0
