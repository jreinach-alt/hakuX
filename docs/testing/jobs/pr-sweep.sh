#!/usr/bin/env bash
#
# The PR sweep. Runs from hakux-pr-sweep.timer every three hours, and never
# starts a model session: it is a script, start to finish, like arms.sh.
#
#   pr-sweep.sh          sweep; repair what is mechanically certain, say the rest
#   pr-sweep.sh list     what it would do, and change nothing
#
# WHY IT EXISTS. Every periodic actor here answers a narrow question and none
# of them asks "is anything stuck?". Measured on 2026-09-19, all real:
#
#   - #141 and #148 sat invisible for 6.5 hours carrying `claimed:cloud` with
#     no unit running. cloud.sh's pickup EXCLUDES a PR with that label and
#     `cloud.sh finish` is the only thing that removes it, so a session whose
#     tail died orphaned them permanently. Nothing noticed; the owner did.
#   - Five PRs sat as unlabelled drafts with their lanes exited. board.sh
#     skips drafts, fleet.py counts only non-drafts, fold.sh refuses them.
#   - Four PRs carried a red required check from a run that predated the fix
#     on master, and no actor at all could reach that state.
#
# fleet.py reports some of this as FAIL lines, but it is a read-only inventory
# that runs only when something invokes it, and its FAILs are addressed to
# whoever happens to read them. This runs on a timer and addresses each
# finding to the PR it is about.
#
# WHAT IT REPAIRS, AND WHY THAT IS ALMOST NOTHING. A sweep that guesses is
# worse than one that reports: it moves a label a person would then have to
# un-move, and it does it unattended. So exactly one class is repaired -- the
# orphaned `claimed:cloud`, whose repair is calling the tail that never ran
# (`cloud.sh finish`, the same command the unit's own ExecStart would have
# run) -- and every other class is REPORTED with the actor that owns it
# named. Two of the five classes here are owned by jobs that already exist
# and are better at them than a sweep could be; this file's value there is
# noticing when that owner has said nothing.
#
# IDEMPOTENT. It runs unattended, so a second pass over the same state must be
# a no-op and not a second comment or a second repair. Every outward action is
# keyed under $WORK/pr-sweep/said/ on the PR and its head sha, the same
# once-per-cause key fold.sh and handback.sh use: when the lane pushes, the
# head moves and the state is a fresh one worth saying again.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
J="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$J/localtime.sh"   # say_time_s: the display zone. Data timestamps below stay `date -u`.
S="$WORK/pr-sweep"; mkdir -p "$S/said" "$WORK/logs/pr-sweep" "$WORK/status"
LOG="$WORK/logs/pr-sweep/tick.log"
REPORT="$WORK/status/pr-sweep.md"
# The tick log is read by hand when something jams, so it is display: local.
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
mode="${1:-run}"

# HOW LONG A CLAIM IS GIVEN BEFORE IT COUNTS AS ORPHANED. cloud.sh labels the
# PR and comments BEFORE it calls systemd-run, so for a moment a live claim
# has no unit. The grace period is what stops this sweep from "repairing" a
# session that is starting; 30 minutes is three orders of magnitude more than
# that window and still two orders less than the 6.5 hours #141 was lost for.
CLAIM_GRACE_SECS="${PR_SWEEP_CLAIM_GRACE_SECS:-1800}"
# How long a PR may sit in a state whose owner is another job before the sweep
# says so out loud on the PR. The board ticks every 20 minutes and fold every
# 30, so six hours is eighteen chances to act, not one.
QUIET_SECS="${PR_SWEEP_QUIET_SECS:-21600}"
[ -f "$WORK/limits.env" ] && . "$WORK/limits.env"

fail_soft() { say "$*"; }

if ! command -v gh >/dev/null 2>&1 || ! timeout 30 gh auth status >/dev/null 2>&1; then
    # FAILS QUIET, like every other gate here. A gh outage that made this file
    # report every PR as stuck would be worse than the silence it replaces.
    fail_soft "no usable gh; this tick is blind and repairs nothing"
    exit 0
fi

# ------------------------------------------------------------- what is alive
#
# LIVENESS COMES FROM systemd AND FROM NOWHERE ELSE, which is the fact
# fleet.py had to relearn: a unit that is active is running, and there is no
# state for it to be in that a file could disagree with. One listing, read by
# every class below.
units=$(systemctl --user list-units 'hakux-lane-*' --state=active,activating --no-legend 2>/dev/null \
        | awk '{print $1}' | sed 's/\.service$//')

# ------------------------------------------------------------ the trunk's head
#
# Read from refs/remotes/origin/$TIP and never from FETCH_HEAD: $REPO is the
# shared checkout, several jobs fetch in it, and a comparison whose whole
# content is a timestamp must not read it from a file another process can
# replace between the fetch and the read. An unreadable trunk time is not
# "nothing is stale" -- it disables the stale class entirely, below.
git -C "$REPO" fetch -q origin "$TIP" 2>/dev/null || true
trunk_time=$(git -C "$REPO" log -1 --format=%ct "refs/remotes/origin/$TIP" 2>/dev/null \
             || git -C "$REPO" log -1 --format=%ct "$TIP" 2>/dev/null || echo "")
case "${trunk_time:-}" in ''|*[!0-9]*) trunk_time="" ;; esac

# WHETHER CLASS 4 HAS AN OWNER. lane.stalecheck (PR #169) teaches fold.sh to
# tell a stale red from a live one and hand it back for a base merge. This
# sweep does NOT duplicate that -- two actors relabelling the same PR from two
# timers is the shape cloud.sh's header is an apology for -- so it reports the
# class and names fold.sh. What it checks here is whether that owner is
# actually present in the trunk it is running from: a class with a named owner
# that is not installed is a class with no owner, and saying "fold.sh has
# this" when fold.sh does not is the failure this whole file exists to catch.
stale_owner=no
grep -q 'stale_red' "$J/fold.sh" 2>/dev/null && stale_owner=yes

# --------------------------------------------------------------- board health
#
# Class 3 is "a ready PR the board owes a label", and the board is the ONLY
# actor that may set that first label. So the useful half of reporting one is
# not the PR -- it is whether the actor is alive, because a dead board makes
# every such PR a symptom of one cause and a live board makes each of them a
# tick's worth of work already queued.
board_health() {
    local t l age
    t=$(systemctl --user is-active hakux-board.timer 2>/dev/null)
    l=$(stat -c %Y "$WORK/logs/board/tick.log" 2>/dev/null || echo 0)
    case "${l:-}" in ''|*[!0-9]*) l=0 ;; esac
    age=$(( $(date +%s) - l ))
    if [ "$t" != active ]; then
        echo "NOT HEALTHY: hakux-board.timer is ${t:-absent}. Nothing will label these PRs until it is enabled: systemctl --user enable --now hakux-board.timer"
    elif [ "$l" = 0 ]; then
        echo "UNKNOWN: hakux-board.timer is active but $WORK/logs/board/tick.log does not exist, so no tick has written anything"
    elif [ "$age" -gt 3600 ]; then
        echo "NOT HEALTHY: hakux-board.timer is active but its tick log has not been written for $(( age / 60 )) minutes (the timer's period is 20)"
    else
        echo "healthy: hakux-board.timer is active and its tick log was written $(( age / 60 ))m ago"
    fi
}

# ------------------------------------------------------------ the classifier
#
# ONE gh CALL, and the interesting half runs here on the raw --json rather
# than inside a --jq, for the reason board.sh gives: a filter that lives in a
# --jq string cannot be tested, and its failure mode is an empty result, which
# reads exactly like "nothing is stuck" -- the one answer this file must never
# give wrongly.
#
# The JSON arrives as ARGV and not on stdin, because `python3 - <<PY` already
# spends stdin on the program: a piped array would be read as source and the
# filter would silently return nothing.
#
# THE PIPELINE STATE LABELS ARE board.sh's LIST, COPIED. There is no way to
# source that function -- board.sh runs a whole tick when sourced -- so the
# set is repeated here and selftest.d/73-pr-sweep.sh asserts the two are
# character-identical. A drift between them would make this sweep report every
# PR in a state board.sh considers labelled.
STATE_LABELS='needs-audit-1 needs-audit-2 needs-remediation fold-ready folded needs-rebase'

classify() {   # <prs json> <active units, newline-separated> <trunk epoch|""> -> class\tnum\thead\tbranch\tdetail
    python3 - "$1" "$2" "${3:-}" "$STATE_LABELS" <<'PY'
import datetime
import json
import sys

raw, units_raw, trunk, state_raw = sys.argv[1:5]
units = set(u.strip() for u in units_raw.splitlines() if u.strip())
STATE = set(state_raw.split())
trunk_epoch = int(trunk) if trunk.isdigit() else None
# A check entry is failing on either spelling. PENDING and SUCCESS are not
# failures, and neither is an entry with no verdict yet.
BAD = {"FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR"}

try:
    prs = json.loads(raw or "[]") or []
except Exception:
    sys.exit(0)                      # unparseable: report nothing, repair nothing

now = datetime.datetime.now(datetime.timezone.utc)


def epoch(s):
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


rows = []


def emit(cls, pr, detail):
    rows.append("\t".join([cls, str(pr.get("number")), pr.get("headRefOid") or "",
                           pr.get("headRefName") or "", detail]))


for pr in prs:
    names = set(l.get("name", "") for l in (pr.get("labels") or []))
    branch = pr.get("headRefName") or ""
    lane = branch[5:] if branch.startswith("lane/") else ""
    quiet = None
    e = epoch(pr.get("updatedAt") or "")
    if e is not None:
        quiet = int(now.timestamp() - e)

    # 1. an orphaned cloud claim. The unit cloud.sh starts is named
    #    hakux-lane-cloud-<kind>-<number>, so liveness is a suffix match on
    #    this PR's number and nothing else -- not on the kind, which is read
    #    from the PR's own claim comment at repair time.
    if "claimed:cloud" in names:
        live = [u for u in units
                if u.startswith("hakux-lane-cloud-") and u.endswith("-%s" % pr.get("number"))]
        if not live:
            emit("orphan-claim", pr, "quiet=%s" % (quiet if quiet is not None else "?"))

    # 2. a draft whose lane has exited. handback.sh owns this and has a quiet
    #    period and a strand budget; the sweep only asks it whether it sees
    #    this PR, which happens in bash below.
    if pr.get("isDraft") and lane and ("hakux-lane-%s" % lane) not in units:
        emit("draft-strand", pr, "lane=%s quiet=%s" % (lane, quiet if quiet is not None else "?"))

    # 3. ready, not a draft, and carrying none of the pipeline's state labels.
    #    The board is the only actor that may set the first one.
    if not pr.get("isDraft") and not (names & STATE):
        emit("no-state-label", pr, "labels=%s quiet=%s"
             % (",".join(sorted(names)) or "none", quiet if quiet is not None else "?"))

    # 4. fold-ready, MERGEABLE, and every failing check started before the
    #    current trunk head was committed -- so the red is about a base that
    #    has moved. Conservative in every direction, and for the same reasons
    #    fold.sh is: no trunk time, no verdict; a rollup with no failing entry
    #    is not stale; a failing entry with no readable timestamp is LIVE, and
    #    so is one that postdates the trunk head. "Cannot tell" is not "stale".
    if trunk_epoch is not None and "fold-ready" in names and pr.get("mergeable") == "MERGEABLE":
        failing = []
        for c in (pr.get("statusCheckRollup") or []):
            verdict = (c.get("conclusion") or c.get("state") or "").upper()
            if verdict in BAD:
                failing.append((c.get("name") or c.get("context") or "check",
                                epoch(c.get("startedAt") or c.get("createdAt") or "")))
        if failing and all(t is not None and t < trunk_epoch for _, t in failing):
            newest = max(t for _, t in failing)
            emit("stale-red", pr, "checks=%s newest_start=%s trunk_head=%s"
                 % (",".join(n for n, _ in failing),
                    datetime.datetime.fromtimestamp(newest, datetime.timezone.utc).strftime("%FT%TZ"),
                    datetime.datetime.fromtimestamp(trunk_epoch, datetime.timezone.utc).strftime("%FT%TZ")))

    # 5. labelled `regressed`. The label is a function of EVERY judged verdict
    #    on the branch, so whether the FAIL still stands is a question only
    #    arms.sh can answer; it is asked in bash below.
    if "regressed" in names and lane:
        emit("regressed", pr, "lane=%s" % lane)

print("\n".join(rows))
PY
}

prs=$(timeout 60 gh pr list --repo "$GH_REPO" --state open --limit 100 \
        --json number,headRefName,headRefOid,isDraft,mergeable,labels,updatedAt,statusCheckRollup,title 2>/dev/null)
if [ -z "$prs" ]; then
    fail_soft "gh returned nothing for the open PR list; this tick is blind and repairs nothing"
    exit 0
fi
rows=$(classify "$prs" "$units" "$trunk_time")

# What handback.sh would do, asked ONCE and not once per draft. `list` acts on
# nothing. An unreadable answer makes the sweep report a draft handback may
# well own -- which is the safe direction for a sweep: over-reporting is noise,
# under-reporting is the defect.
handback_list=""
case "$rows" in *draft-strand*) handback_list=$(timeout 120 bash "$J/handback.sh" list 2>/dev/null) ;; esac

# ----------------------------------------------------------------- the outlet
#
# A finding is delivered to the PR it is about, because that is where the lane
# and the owner are already looking, and a report file nothing reads is the
# same invisibility this file was written to end. Keyed once per (class, PR,
# head) so an unattended three-hourly run does not become a nag.
said() {   # <key> -> 0 if this has already been said
    [ -f "$S/said/$1" ]
}
mark() { date -u +%FT%TZ > "$S/said/$1"; }
comment() {   # <key> <pr> <body>
    if said "$1"; then return 0; fi
    if [ "$mode" = list ]; then echo "  would comment on #$2: ${3:0:110}"; return 0; fi
    gh pr comment "$2" --repo "$GH_REPO" --body "$3" >/dev/null 2>&1 && mark "$1"
}

found=0; repaired=0
: > "$REPORT.tmp"
{
    echo "# PR sweep -- $(date -u +%FT%TZ)"
    echo
    echo "Written by \`docs/testing/jobs/pr-sweep.sh\` on hakux-pr-sweep.timer. Each finding is also a comment on its own PR, said once per head sha."
    echo
} >> "$REPORT.tmp"
note() { printf -- '- %s\n' "$1" >> "$REPORT.tmp"; }

while IFS=$'\t' read -r cls num head branch detail; do
    [ -n "${cls:-}" ] || continue
    found=$((found+1))
    quiet=$(sed -n 's/.*\bquiet=\([0-9]*\).*/\1/p' <<< "$detail"); quiet="${quiet:-0}"
    case "$cls" in

    orphan-claim)
        # THE REPAIR. The tail that never ran is `cloud.sh finish <kind> <n>`,
        # and the kind is read from the PR's own claim comment -- specifically
        # from the UNIT NAME in it, which is the same string the liveness
        # check above matched on, rather than from the prose around it.
        if [ "$quiet" -lt "$CLAIM_GRACE_SECS" ]; then
            say "#$num claimed:cloud with no unit, but the PR changed ${quiet}s ago (< ${CLAIM_GRACE_SECS}s grace); a claim may be starting. Leaving it."
            note "#$num \`claimed:cloud\`, no unit, within the ${CLAIM_GRACE_SECS}s start grace -- not touched this tick."
            continue
        fi
        kind=$(timeout 60 gh pr view "$num" --repo "$GH_REPO" --json comments \
                 --jq '[.comments[] | select(.body | startswith("[job.cloud] claimed"))] | last | .body' 2>/dev/null \
               | sed -n 's/.*unit hakux-lane-cloud-\([a-z0-9]*\)-'"$num"'.*/\1/p' | head -1)
        [ -n "$kind" ] || kind=$(timeout 60 gh pr view "$num" --repo "$GH_REPO" --json comments \
                 --jq '[.comments[] | select(.body | startswith("[job.cloud] claimed for "))] | last | .body' 2>/dev/null \
               | sed -n 's/.*claimed for \([a-z0-9]*\).*/\1/p' | head -1)
        if [ -z "$kind" ]; then
            # NOT A GUESS. `finish` clears the state label only for the kind it
            # is given, so a wrong kind would clear the wrong label -- and the
            # default would be `audit1`, the earliest state, on a PR that may
            # be past it. No comment to read means no repair.
            say "#$num is claimed:cloud with no unit and no readable [job.cloud] claim comment; cannot tell which kind to finish. NOT repairing."
            note "#$num \`claimed:cloud\`, no unit, **no readable claim comment** -- the kind cannot be derived, so the label was left. Clear it by hand with \`bash docs/testing/jobs/cloud.sh finish <kind> $num\`."
            comment "orphan-$num-$head" "$num" "[job.pr-sweep] this PR carries \`claimed:cloud\` and no \`hakux-lane-cloud-*-$num\` unit is running, so the session that held it has ended without running its tail. \`cloud.sh\`'s pickup skips a PR with this label, so nothing will claim it again until the label goes.

The sweep could not repair it: there is no \`[job.cloud] claimed\` comment on this PR to read the kind from, and \`cloud.sh finish\` clears a different state label for each kind. Run it by hand once the kind is known:

\`\`\`
bash docs/testing/jobs/cloud.sh finish <audit1|audit2|remediate|issue> $num
\`\`\`"
            continue
        fi
        if [ "$mode" = list ]; then
            echo "  would repair #$num: cloud.sh finish $kind $num (claimed:cloud, no unit, quiet ${quiet}s)"
            continue
        fi
        say "#$num: claimed:cloud with no hakux-lane-cloud-*-$num unit and quiet ${quiet}s; running the tail that did not -- cloud.sh finish $kind $num"
        if bash "$J/cloud.sh" finish "$kind" "$num" >>"$LOG" 2>&1; then
            repaired=$((repaired+1))
            note "#$num \`claimed:cloud\` with no unit -- **repaired**: \`cloud.sh finish $kind $num\`."
            comment "orphan-$num-$head" "$num" "[job.pr-sweep] this PR carried \`claimed:cloud\` with no \`hakux-lane-cloud-$kind-$num\` unit running for ${quiet}s, so the session that claimed it ended without running its tail. \`cloud.sh\`'s pickup excludes a PR with that label and \`cloud.sh finish\` is the only thing that removes it, so this PR was unclaimable by anything.

Ran the tail on its behalf: \`cloud.sh finish $kind $num\`. That drops the claim and the lane's \`territory.toml\` row, and clears the state label only if the session set a successor -- if it did not, the label stays and the audit outlet will claim this PR again on its next tick, which is the correct next step."
        else
            note "#$num \`claimed:cloud\` with no unit -- \`cloud.sh finish $kind $num\` exited non-zero; see \`$LOG\`."
            say "#$num: cloud.sh finish $kind $num failed; the claim is still on it"
        fi
        ;;

    draft-strand)
        # handback.sh owns this class outright, down to a per-lane strand
        # budget and a once-per-head key. Report only what it is silent about.
        # Anchored on the line start: handback.sh list prints "#<n> <branch>: ..."
        # and a bare "#<n>" match would also hit this number quoted inside a
        # sentence about some other PR, which would silence a real finding.
        if grep -q "^#$num " <<< "$handback_list"; then
            say "#$num is a stranded draft and handback.sh sees it; leaving it to the actor that owns it"
            continue
        fi
        note "#$num (\`$branch\`) is a draft, its lane unit is not running, and \`handback.sh list\` says nothing about it -- so no actor is holding it."
        say "#$num: draft, no lane unit, and handback.sh does not list it"
        comment "strand-$num-$head" "$num" "[job.pr-sweep] this PR is a draft and \`hakux-lane-${branch#lane/}\` is not running, so no lane is working on it -- and \`handback.sh list\`, which owns this state, does not list it either. Every other actor filters drafts out deliberately: \`board.sh\` skips \`isDraft\`, \`fleet.py\` counts only non-drafts, \`fold.sh\` refuses to fold one.

Nothing here marks a PR ready: \`roles/lane.md\`'s definition of done includes things no script can check (NOTES.md written, \`Files:\` matching the diff, the prediction committed with its refs). This comment is the sweep saying the PR has no actor, ${quiet}s after it last changed."
        ;;

    no-state-label)
        health=$(board_health)
        say "#$num is ready with no pipeline state label (quiet ${quiet}s); board $health"
        note "#$num (\`$branch\`) is out of draft with no state label; the board is $health"
        # The board ticks every 20 minutes and only it may set the first
        # label, so a recent one is not a finding -- it is work already
        # queued. Say it on the PR when the actor is down, or when it has had
        # $QUIET_SECS (eighteen ticks) and has not acted.
        case "$health" in
            healthy*) [ "$quiet" -lt "$QUIET_SECS" ] && continue ;;
        esac
        comment "nolabel-$num-$head" "$num" "[job.pr-sweep] this PR is out of draft and carries none of \`needs-audit-1\`, \`needs-audit-2\`, \`needs-remediation\`, \`fold-ready\`, \`folded\`, \`needs-rebase\`. \`board.sh\` is the only actor that may set the first one, and this PR has been in that state for ${quiet}s.

Board health: **$health**

If the board is healthy, this is a tick's worth of work that it has not got to; if it is not, that is the cause of this and of every other unlabelled ready PR on the repository at once."
        ;;

    stale-red)
        # REPORTED, NEVER REPAIRED HERE. lane.stalecheck (PR #169) teaches
        # fold.sh to tell a stale red from a live one and hand it back for a
        # base merge, and two actors relabelling one PR from two timers is
        # worse than the state either of them fixes. What this adds is the
        # case where that owner is absent, or present and silent.
        say "#$num is fold-ready, MERGEABLE, and every failing check predates the trunk head ($detail); fold.sh owner present: $stale_owner"
        note "#$num (\`$branch\`) is a stale red: $detail. Owner: \`fold.sh\` (lane.stalecheck, PR #169), present in this trunk: **$stale_owner**."
        if [ "$stale_owner" = yes ] && [ "$quiet" -lt "$QUIET_SECS" ]; then continue; fi
        comment "stalered-$num-$head" "$num" "[job.pr-sweep] every failing required check on this PR started **before** the current \`origin/$TIP\` head was committed, so the red is about a base that has since moved:

    $detail

GitHub does not re-run a pull request's checks when its base branch moves, and a re-run would not help either: the workflows check out the PR's own head, so they would replay the same tree. The fix is a base merge on the lane branch.

The actor for this class is \`fold.sh\` (lane.stalecheck, PR #169), which hands such a PR back to its lane as \`needs-rebase\`. Present in the trunk this sweep ran from: **$stale_owner**. This sweep never relabels a PR for this class -- two actors moving one PR's labels from two timers is worse than the state either fixes."
        ;;

    regressed)
        # THE LABEL IS A FUNCTION OF EVERY JUDGED VERDICT ON THE BRANCH, not
        # of the last one, and arms.sh recomputes it from the verdicts on
        # disk. Asking it is the only honest way to say whether the FAIL still
        # stands -- and `regression-accepted:` is the owner's to grant, so
        # nothing here writes a label either way.
        st=$(timeout 120 bash "$J/arms.sh" state "$branch" 2>/dev/null | sed -n 's/^STATE=//p' | head -1)
        st="${st:-unreadable}"
        say "#$num is labelled regressed; arms.sh state $branch says $st"
        note "#$num (\`$branch\`) is labelled \`regressed\`; \`arms.sh state $branch\` recomputes **$st**."
        case "$st" in
            regressed)
                comment "regressed-$num-$head-$st" "$num" "[job.pr-sweep] this PR is labelled \`regressed\` and \`arms.sh state $branch\` still recomputes \`regressed\` from the verdicts on disk: the FAIL stands and nothing supersedes it.

\`\`\`
bash docs/testing/jobs/arms.sh state $branch
\`\`\`

This sweep grants no \`regression-accepted:\` label -- that is the owner's alone. The lane's route out is a fix and a fresh prediction registered against the new refs, which supersedes the failing one." ;;
            verified|none)
                comment "regressed-$num-$head-$st" "$num" "[job.pr-sweep] this PR is labelled \`regressed\`, but \`arms.sh state $branch\` recomputes **\`$st\`** from the verdicts on disk -- so the label and the evidence disagree.

\`\`\`
bash docs/testing/jobs/arms.sh state $branch
\`\`\`

\`arms.sh\` sets that label when it judges an arm, so a superseded FAIL leaves the old label in place until the next verdict lands on this branch. The sweep does not move it: \`regressed\` is the arms job's label and \`regression-accepted:\` is the owner's. Read the table the command above prints before acting on the label." ;;
            *)
                note "#$num: \`arms.sh state $branch\` printed no STATE= line, so the label could not be checked." ;;
        esac
        ;;
    esac
done <<< "$rows"

{
    echo
    echo "$found finding(s), $repaired repaired. Trunk head: ${trunk_time:-unreadable}. Stale-red owner in fold.sh: $stale_owner."
    [ -z "$trunk_time" ] && echo
    [ -z "$trunk_time" ] && echo "**The stale-red class did not run this tick**: \`origin/$TIP\`'s commit time could not be read, and a stale verdict with no trunk time is a guess."
} >> "$REPORT.tmp"
if [ "$mode" = list ]; then
    rm -f "$REPORT.tmp"
    [ -n "$rows" ] && printf '%s\n' "$rows" || echo "nothing stuck"
    exit 0
fi
mv -f "$REPORT.tmp" "$REPORT"
say "swept $(printf '%s\n' "$prs" | python3 -c 'import json,sys; print(len(json.load(sys.stdin) or []))' 2>/dev/null || echo '?') open PR(s): $found finding(s), $repaired repaired; report $REPORT"
exit 0
