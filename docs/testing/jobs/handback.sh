#!/usr/bin/env bash
#
# The handback job: the actor for a PR a job handed back to its lane.
#
#   handback.sh          resume the lane of every handed-back PR
#   handback.sh list     what it would resume, and why it would skip the rest
#
# WHY THIS EXISTS. `fold.sh` refuses to resolve a merge conflict -- a merge
# resolved by a script that does not understand the code is how a working fix
# was reverted on 2026-09-12 -- so it labels the PR `needs-rebase`, comments
# naming the files, and stops. That label was set by one job, displayed by
# `status.sh`, and acted on by NONE: `roles/board.md` had no rule for it, the
# board only wakes on a `fleet.py` or coverage `FAIL`, and the lane that would
# fix it is a `systemd-run` transient unit that exited when its session ended.
# Complete, tested, green work was parked permanently. Seven of the ten lanes
# open on 2026-09-19 append to `jobs/selftest.sh` and every fold moves master,
# so it was going to fire seven times in an afternoon.
#
# ONE TABLE, NOT ONE SCRIPT PER LABEL. `needs-rebase` is the fourth terminal
# label; `needs-audit-1`, `needs-audit-2` and `needs-remediation` are the
# others (lane.auditoutlet, PR #130). They differ only in what the session is
# told to do, so the label is a ROW in HANDBACK_ROWS below and the work is a
# function that prints the brief. Everything else -- deriving the lane name,
# resuming only on a new cause, the cap, the attempt counter -- is written
# once, here. Adding a label is an edit to that list.
#
# ONE LABEL CAN CARRY TWO CAUSES, AND THE CAUSE FILE SAYS WHICH. `fold.sh`
# also sets `needs-rebase` when a PR's only failing check ran BEFORE the
# trunk's current head was committed -- a red about a base that has moved,
# which GitHub never re-runs and which nothing in the harness could reach
# until then (four PRs at once on 2026-09-19). The action is the same one this
# label's description already names, "bring master into the lane branch", so
# it is the same label and the same row; a second label would have had to be
# added to `board.sh`'s and `fleet.py`'s state-label sets too, or a PR
# carrying only it would read as UNLABELLED to the board and be handed
# `needs-audit-1` on top of already-audited work. What differs is only what
# the lane must be TOLD, so the cause file carries `action=` and the row's
# action is overridden from it, against a whitelist. Telling the truth there
# matters: a lane sent to resolve a conflict that does not exist spends a
# session looking for a defect of its own that is not there.
#
# THE SECOND CAUSE IS NOT A LABEL: A DRAFT PR WHOSE LANE HAS EXITED. Every
# actor filters drafts out, deliberately -- `board.sh` skips `isDraft`,
# `fleet.py` counts only non-draft lane PRs, `fold.sh` refuses to fold one --
# because while the lane is running, draft means exactly what it says. The
# state is only wrong ONCE THE UNIT HAS EXITED, and until this job nothing
# joined those two facts: `isDraft` is read from GitHub, liveness from
# systemd. On 2026-09-19 five open lane PRs (#137, #141, #145, #146, #148)
# were finished, CI-green, in draft, with no lane running and no actor that
# could ever touch them.
#
# AND THEY MOSTLY DID NOT FAIL -- THEY WERE WAITING. CI on a pushed head is
# ~10 minutes, a device arm is ~90, an audit is a different session; a lane
# has no way to sleep and resume, so one that pushes and must wait can only
# burn turns polling until the turn cap cuts it, or end tidily and leave a
# draft. The tidier the lane, the more likely it strands. So this is not a
# lane misbehaving, and the resume must carry the RESOLVED STATE -- CI is
# GREEN on this sha, your arm was judged -- or the new session reads the same
# NOTES.md and the same diff and strands again.
#
# IT RESUMES THE LANE; IT DOES NOT MARK THE PR READY. `roles/lane.md`'s
# definition of done includes things no script can check: NOTES.md written,
# `Files:` matching the diff, the prediction committed with its refs. A job
# that flipped `isDraft` because CI went green would declare finished work
# nobody verified.
#
# AND WAITING IS NOT FAILING, so a strand resume does not spend one of the
# four attempts behind the escalation policy (`lane.sh` counts every resume;
# this job puts the counter back). What bounds it instead is DRAFT_STRAND_MAX
# per lane, plus a once-per-cause key: the head sha for the quiet clock, the
# set of judged verdicts for an arm (see the strand table below).
#
# WHAT IT DOES NOT DO. It resolves nothing and it starts nothing itself: the
# actor is `docs/testing/lane.sh resume`, which already counts the attempt,
# escalates the model on the fourth, and refuses past LANE_MAX_ATTEMPTS so the
# board's `decision-needed` path stays reachable.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"          # docs/testing
LANE_SH="${HAKUX_LANE_SH:-$T/lane.sh}"
. "$(dirname "${BASH_SOURCE[0]}")/gh-label.sh"   # label_add/label_rm: `gh pr edit --add-label` exits 1 here
. "$(dirname "${BASH_SOURCE[0]}")/localtime.sh"  # say_time/local_ts: the display zone
. "$(dirname "${BASH_SOURCE[0]}")/remote-lane.sh" # remote_lane_of: a branch a lane owns from somewhere this host cannot see
H="$WORK/handback"
mkdir -p "$H/done" "$H/cause" "$H/strand" "$WORK/attempts" "$WORK/logs/handback"
LOG="$WORK/logs/handback/tick.log"
# The tick log is read by hand when something jams, so it is display: local.
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
mode="${1:-run}"
comment() { printf '%s\n' "$2" > "$H/comment.md"; gh pr comment "$1" --repo "$GH_REPO" --body-file "$H/comment.md" >/dev/null 2>&1; }

# ------------------------------------------------------------- the table
#
#   <label>  <action>  [<label that means this one is stale>...]
#
# A PR carrying any of the trailing labels is skipped: it has already moved on
# and re-resuming it is the loop this job must not become. A lane that resolves
# its conflict re-applies `fold-ready` and may leave `needs-rebase` behind, and
# its head has moved, so without this the next tick would read a new cause and
# resume a lane whose work is already back in the pipeline.
HANDBACK_ROWS=(
    "needs-rebase   resume_rebase   fold-ready folded"
)

# The strand causes are not labels, so they are not rows in that table: their
# pickup asks GitHub a different question. They share everything below it.
#
#   draft-strand-arm    the arm this lane was waiting for has been judged
#                       (`arms.sh` labels the PR `verified` or `regressed`)
#   draft-strand-runs   every device request of the lane's has finished, at
#                       least one since its last session ended (see
#                       lane_requests_of below; keyed on that set of runs)
#   draft-strand-quiet  nothing has happened on the PR for DRAFT_STRAND_SECS
#
# Two keys, not one, on purpose: a verdict that lands AFTER a quiet resume is
# still a new cause at the same head, while a second quiet tick at that head is
# not. The quiet marker is `$label-$pr-$head`; the arm marker is keyed on the
# VERDICTS, below, because the head is not what an arm resume is about.
#
# A NEW HEAD IS NOT A NEW VERDICT. The arm cause used the head key too until
# 2026-09-25, so a lane that reacted to its verdict by pushing -- registering a
# replicate, committing NOTES, merging master -- was strand-resumed again, with
# nothing new to read, on the next tick. lane.vshnobegin242 (#245) was resumed
# at 16:10Z, 16:29Z and 16:32Z on ONE judged FAIL and labelled
# `blocked:needs-owner` at 16:42Z while the replicate it had correctly
# registered sat queued on the Thor. So the arm marker is a hash of the
# `(prediction sha, verdict)` pairs judged for the branch, and it moves only
# when `arms.sh` judges another one.
ARMS_DIR="$WORK/arms"
DISPATCH_DIR="${DISPATCH_DIR:-$WORK/dispatch}"
VKEY=""; VSET=""
verdicts_of() {   # <branch> -> VKEY (hash) and VSET (short list), or both "" if none judged
    # THE SAME READ `arms.sh state` MAKES, not a second opinion: a pair's
    # branch is the part of its `source` before the colon, its verdict is
    # judged/<sha> as the judge wrote it, and only a line saying FAIL or PASS
    # is a verdict (FAIL first, as there). UNJUDGED and ERROR supersede nothing
    # there and are not new information here. Not by CALLING `arms.sh state`:
    # it rewrites $ARMS_DIR/log/label-index.tsv with `>`, and an arms tick
    # reading that index mid-judge would see it truncated.
    local out
    out=$(python3 - "$ARMS_DIR" "$1" <<'PY'
import glob, hashlib, json, os, sys
A, branch = sys.argv[1:3]
got = []
for pj in sorted(glob.glob(os.path.join(A, "pairs", "*.json"))):
    if pj.endswith(".verdict.json"):
        continue
    try:
        p = json.load(open(pj))
    except Exception:
        continue
    sha, src = p.get("sha"), str(p.get("source") or "")
    if not sha or src.partition(":")[0] != branch:
        continue
    try:
        v = open(os.path.join(A, "judged", sha)).read()
    except Exception:
        continue                           # queued or running; no verdict yet
    cls = "FAIL" if "FAIL" in v else ("PASS" if "PASS" in v else None)
    if cls:
        got.append((sha, cls))
got.sort()
if got:
    print(hashlib.sha256("\n".join("%s %s" % g for g in got).encode()).hexdigest()[:16])
    print(" ".join("%s=%s" % (s[:12], c) for s, c in got))
PY
)
    VKEY=$(sed -n 1p <<< "$out"); VSET=$(sed -n 2p <<< "$out")
}
# THE LANE'S OWN DEVICE WORK: STILL ON ITS WAY, OR FINISHED SINCE IT LAST RAN.
#
# In flight: the lane is waiting, and rightly, so no strand cause resumes it.
# Finished: the third strand cause, `draft-strand-runs` (defect 23 of the
# dispatch-hardening brief). A lane ends its session while its soak or study
# waits on a device -- correctly -- and until 2026-09-25 this job resumed it
# only on a JUDGED ARM or on the two-hour quiet clock, so a lane whose soak
# finished at minute ten sat on its own result for up to two hours. On
# 2026-09-25 23:45Z the Nova had 23 lane requests waiting, perfarch's nine
# soaks among them at ~180 min; each one that finished woke nobody.
#
# WHOSE REQUEST IS IT. First rule that answers wins, most specific first:
#   1. its `lane` field;
#   2. its expect_sha is a registered prediction (arms/pairs): that pair's
#      branch -- how `arms.sh` queues an arm;
#   3. its purpose names a branch, " from lane/<b>:" -- also `arms.sh`'s;
#   4. its requester (or, with none, the owner field of its id,
#      `<epoch>-<who>-<pid>`), less a leading `lane.` or `arms-`: the lane
#      whose name it equals, or the LONGEST known lane it starts with plus
#      `-` (`xbox-subnorm-dry2` is lane.xbox's; `selftesths-x-fix` is
#      lane.selftesths-x's and not lane.selftesths's when both are known).
# An arm (rules 2-3, or `<name>-base`/`-fix` from `ab_run.sh --who`) is
# reported as kind `arm`; anything else as `run`.
#
# WHICH FINISHED RUNS ARE NEW. Those whose DONE/ERROR marker is newer than the
# end of the lane's last session: the mtime of its newest
# `$WORK/logs/lane/<name>.<stamp>.json`, which `lane.sh` has `claude -p` write
# on exit. A run the lane saw finish while it was still running is older than
# that and is not news. With no session log there is no line to draw, and
# nothing counts as new: a lane this host never ran has no result waiting.
# A result whose expect_sha is a registered prediction is left out: the arms
# job judges it, and the verdict -- not the raw run -- is the arm cause's news.
#
# ONE READ, not two: the in-flight gate and the finished set are the same
# question about the same files, and a second reader could attribute them
# differently.
INFLIGHT=""; INFLIGHT_KIND=""; RKEY=""; RSET=""; RLIST=""
lane_requests_of() {   # <branch> <lane name> -> INFLIGHT, INFLIGHT_KIND, RKEY (hash), RSET (short), RLIST (rows)
    local out
    out=$(python3 - "$ARMS_DIR" "$DISPATCH_DIR" "$WORK" "$1" "$2" <<'PY'
import glob, hashlib, json, os, re, sys
A, D, W, branch, name = sys.argv[1:6]
pair_branch = {}
for pj in glob.glob(os.path.join(A, "pairs", "*.json")):
    if pj.endswith(".verdict.json"):
        continue
    try:
        p = json.load(open(pj))
    except Exception:
        continue
    b = str(p.get("source") or "").partition(":")[0]
    if p.get("sha") and b:
        pair_branch[p["sha"]] = b
known = set()
try:
    known |= {d for d in os.listdir(os.path.join(W, "wt")) if os.path.isdir(os.path.join(W, "wt", d))}
except OSError:
    pass
known |= {b[5:] for b in pair_branch.values() if b.startswith("lane/")}
known.add(name)
arm_who = {name + "-base", name + "-fix", "arms-" + name + "-base", "arms-" + name + "-fix"}
from_re = re.compile(r" from (lane/[^:\s]+):")
id_re = re.compile(r"(?:^|-)\d{9,}-(.+)-\d+$")

def owner(r, rid):
    """-> (lane or None, kind)"""
    if r.get("lane"):
        return str(r["lane"]).removeprefix("lane."), "run"
    es = r.get("expect_sha")
    if es and es in pair_branch:
        return pair_branch[es].removeprefix("lane/"), "arm"
    m = from_re.search(str(r.get("purpose") or ""))
    if m:
        return m.group(1).removeprefix("lane/"), "arm"
    who = str(r.get("requester") or "")
    if not who:
        m = id_re.search(rid)
        who = m.group(1) if m else ""
    kind = "arm" if who in arm_who else "run"
    for pre in ("lane.", "arms-"):
        who = who.removeprefix(pre)
    if not who:
        return None, kind
    if who in known:
        return who, kind
    hits = [k for k in known if who.startswith(k + "-")]
    return (max(hits, key=len) if hits else None), kind

def load(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}

for d in ("running", "queue"):
    for rq in sorted(glob.glob(os.path.join(D, d, "*.req"))):
        rid = os.path.basename(rq)[:-4]
        r = load(rq)
        lane, kind = owner(r, str(r.get("id") or rid))
        if lane == name:
            print("INFLIGHT\t%s\t%s/%s" % (kind, d, r.get("id") or rid))
            sys.exit(0)

logs = glob.glob(os.path.join(W, "logs", "lane", name + ".[0-9]*.json"))
if not logs:
    sys.exit(0)
ended = max(os.path.getmtime(p) for p in logs)
got = []
for res in glob.glob(os.path.join(D, "results", "*")):
    t, state = None, None
    for s in ("DONE", "ERROR"):
        try:
            m = os.path.getmtime(os.path.join(res, s))
        except OSError:
            continue
        t = m if t is None else max(t, m)
        state = s if state is None or s == "ERROR" else state   # ERROR wins
    if t is None or t <= ended:
        continue
    rid = os.path.basename(res)
    r = load(os.path.join(res, "request.json"))
    if r.get("expect_sha") and r["expect_sha"] in pair_branch:
        continue                                                # the arm cause's
    lane, _ = owner(r, str(r.get("id") or rid))
    if lane == name:
        got.append((rid, state, res))
got.sort()
if got:
    print("RKEY\t" + hashlib.sha256("\n".join("%s %s" % g[:2] for g in got).encode()).hexdigest()[:16])
    print("RSET\t" + " ".join("%s=%s" % g[:2] for g in got[:6]) + (" (+%d more)" % (len(got) - 6) if len(got) > 6 else ""))
    for g in got:
        print("RUN\t%s\t%s\t%s" % g)
PY
)
    INFLIGHT=$(awk -F'\t' '$1=="INFLIGHT"{print $3}' <<< "$out")
    INFLIGHT_KIND=$(awk -F'\t' '$1=="INFLIGHT"{print $2}' <<< "$out")
    RKEY=$(awk -F'\t' '$1=="RKEY"{print $2}' <<< "$out")
    RSET=$(awk -F'\t' '$1=="RSET"{print $2}' <<< "$out")
    RLIST=$(awk -F'\t' '$1=="RUN"{print $2"\t"$3"\t"$4}' <<< "$out")
}
#
# The stale set is wider than `needs-rebase`'s because every one of these
# labels already has an actor: the rows above, the audit outlet, or a person.
# A draft carrying one of them is not unowned, which is the only thing this
# cause is about.
STRAND_STALE="folded fold-ready needs-rebase needs-audit-1 needs-audit-2 needs-remediation blocked:needs-owner"
# Four fold ticks: long enough to outlast a ~90-minute device arm, so a lane
# that ended while its arm was in flight is not resumed to be told nothing.
DRAFT_STRAND_SECS="${DRAFT_STRAND_SECS:-7200}"
# The bound that replaces the attempt counter this cause does not spend. A
# lane that has been handed the resolved state three times and is still in
# draft is not waiting on anything this job can see.
DRAFT_STRAND_MAX="${DRAFT_STRAND_MAX:-3}"

# ------------------------------------------------------------- the actions
# An action prints the section appended to the lane's brief. It gets:
#   $1 pr  $2 head branch  $3 head sha  $4 lane name  $5 cause detail (may be "")
resume_rebase() {
    cat <<EOF

---

## Handed back $(say_time_s): PR #$1 no longer merges into \`$TIP\`

The fold job could not merge \`$2\` into \`$TIP\` at \`${3:0:10}\`${5:+, conflicting in: $5}.
It resolves nothing itself, on purpose. Resolving it is now the whole task:

\`\`\`
git fetch origin $TIP
git merge origin/$TIP        # MERGE, never rebase: a rebase rewrites every
                             # sha and un-ancestors any registered
                             # prediction's a_ref/b_ref (ORCHESTRATION-DESIGN
                             # 8.1). Merging keeps them bound forever.
# resolve the conflict, keeping BOTH sides' intent, then:
git commit && git push
bash docs/testing/jobs/selftest.sh     # if the conflict was under jobs/
\`\`\`

Then, once CI is green on the new head:

\`\`\`
bash docs/testing/jobs/gh-label.sh rm  $1 needs-rebase
bash docs/testing/jobs/gh-label.sh add $1 fold-ready
\`\`\`

Do not re-open, re-measure or extend the work this PR already carries; it was
audited and green, and only the merge base moved. If the conflict cannot be
resolved without a decision that is not yours, say so in \`NOTES.md\` and in a
PR comment starting \`[lane.$4] blocked:\`, and stop -- that is a finished
outcome.
EOF
}

# The other cause behind the same label: the red is about a base that moved.
# $5 is the failing run and its start time, as `fold.sh` read them.
#
# THE WHOLE POINT OF THIS TEXT IS "IT IS NOT YOURS". The measured failure this
# exists for is a lane opening a session, reading a red `selftest` on its own
# PR, and starting to debug a fragment that was fixed on master hours earlier.
# So the run and its timestamp are named first, and the re-run is ruled out
# explicitly -- it was tried, at 20:37:16Z on 2026-09-19, and came back red
# because the workflows check out the PR's own head.
resume_stale_ci() {
    cat <<EOF

---

## Handed back $(say_time_s): PR #$1's red is about a base that has moved

The fold job did not fold \`$2\` at \`${3:0:10}\`, and **not because of
anything you pushed**. **Every** failing check on that head ran before
\`$TIP\`'s current head was committed${5:+; the most recent of them is \`$5\`}.
GitHub does not re-run a pull request's checks when its base branch moves, so
that FAILURE is a verdict about a tree that no longer exists, and it would
have been refused every tick forever.

**Do not open the failing job and start debugging it.** Read its date first.
Re-running it does not help either: the workflows check out this PR's own
head, not \`refs/pull/$1/merge\`, so the branch's own copy of whatever broke on
the trunk is still the copy that runs. The only thing that refreshes the
verdict is bringing the trunk in:

\`\`\`
git fetch origin $TIP
git merge origin/$TIP        # MERGE, never rebase: a rebase rewrites every
                             # sha and un-ancestors any registered
                             # prediction's a_ref/b_ref (ORCHESTRATION-DESIGN
                             # 8.1). Merging keeps them bound forever.
# resolve anything that conflicts, keeping BOTH sides' intent, then:
git commit && git push
bash docs/testing/jobs/selftest.sh     # if anything under jobs/ moved
\`\`\`

Then, once CI is green on the new head:

\`\`\`
bash docs/testing/jobs/gh-label.sh rm  $1 needs-rebase
bash docs/testing/jobs/gh-label.sh add $1 fold-ready
\`\`\`

Do not re-open, re-measure or extend the work this PR already carries; it was
audited and green, and only the base moved under it. If the merge needs a
decision that is not yours, say so in \`NOTES.md\` and in a PR comment starting
\`[lane.$4] blocked:\`, and stop -- that is a finished outcome.
EOF
}

# The strand brief. $5 is "ci=<STATE> quiet=<secs> arm=<label|none>" -- the
# RESOLVED STATE, and the reason this is worth a session at all. A lane
# resumed with no new information repeats what it did before, which is how a
# PR burns four attempts having never been wrong about anything.
resume_strand() {
    local ci quiet arm hrs
    ci=$(sed -n 's/.*\bci=\([A-Z]*\).*/\1/p' <<< "$5"); ci="${ci:-UNKNOWN}"
    quiet=$(sed -n 's/.*\bquiet=\([0-9]*\).*/\1/p' <<< "$5"); quiet="${quiet:-0}"
    arm=$(sed -n 's/.*\barm=\([A-Za-z:-]*\).*/\1/p' <<< "$5"); arm="${arm:-none}"
    hrs=$(( quiet / 3600 ))
    cat <<EOF

---

## Resumed $(date -u '+%FT%TZ'): PR #$1 is a draft and your lane was not running

Your session ended with #$1 still in draft, and \`hakux-lane-$4\` is not
active. **Nothing else can act on that PR**: \`board.sh\`, \`fleet.py\` and
\`fold.sh\` all skip drafts, correctly, because a draft means a lane is still
working -- and you are not. It would have sat there indefinitely.

**This is not counted as a failed attempt.** If you ended because you were
waiting, you were right to end; the harness had nowhere to put a waiting lane
and this job is that place. Here is what you were waiting for, resolved:

| | |
|---|---|
| head | \`${3:0:10}\` |
| CI on that head | **$ci** |
| arm verdict label | \`$arm\` |
| quiet for | ${hrs}h ($quiet s since the PR last changed) |

EOF
    case "$ci" in
    GREEN) cat <<EOF
CI is **GREEN** on \`${3:0:10}\`. That gate is done arguing with you.
EOF
        ;;
    RED) cat <<EOF
CI is **RED** on \`${3:0:10}\`. Read \`gh pr checks $1\` first: fixing that is
the task, and nothing downstream will look at this PR until it is green.
EOF
        ;;
    NONE) cat <<EOF
**No CI run exists** on \`${3:0:10}\` -- nothing has built this head, so no
gate can pass. The two causes are a merge conflict with \`$TIP\` (GitHub
builds the merge commit, so a PR that does not merge gets no runs at all:
check \`gh pr view $1 --json mergeable\` and \`git merge origin/$TIP\`), and
the retired skip-ci marker in the head commit's message. If it is the marker,
push \`git commit --allow-empty -m 'ci: build this head' && git push\` and do
**not** name the marker in that message -- GitHub matches it in the body too.
EOF
        ;;
    PENDING) cat <<EOF
CI is still **PENDING** on \`${3:0:10}\`, but the PR has been quiet for ${hrs}h,
which is longer than a run takes. Check \`gh pr checks $1\`: a job queued with
no runner never concludes by itself.
EOF
        ;;
    esac
    # THE RUNS CAUSE NAMES ITS RESULT DIRS, because they are the whole of the
    # news: a lane told "your runs finished" without where to read them goes
    # looking in the queue it left, and the requests are not there any more.
    [ -z "${RUNS_BRIEF:-}" ] || {
        cat <<EOF

**Your device requests have all finished** since your last session ended, and
none of yours is still queued or running. Read these before anything else:

| request | state | result dir |
|---|---|---|
EOF
        while IFS=$'\t' read -r rid st dir; do
            [ -n "$rid" ] && printf '| `%s` | %s | `%s` |\n' "$rid" "$st" "$dir"
        done <<< "$RUNS_BRIEF"
        cat <<EOF

An \`ERROR\` is a result too: read its \`run.log\`/\`run1.log\` before re-queueing.
EOF
    }
    [ "$arm" = none ] || cat <<EOF

Your arm has been judged: the arms job labelled this PR \`$arm\` and posted the
verdict as a \`[job.arms]\` comment. **Read that comment before anything else.**
A \`regressed\` PR is not fold-ready; the verdict, not the diff, is the task.
EOF
    cat <<EOF

So: finish \`roles/lane.md\`'s definition of done -- \`docs/lanes/$4/NOTES.md\`
written, the PR body's \`Files:\` matching \`git diff --stat origin/$TIP...HEAD\`,
the prediction registered and committed with its refs or the body saying why
there is none -- and then **\`gh pr ready $1\`**. Do not re-open, re-measure or
extend work this PR already carries.

**If you are still waiting on something**, that is a finished session too, but
say it where a reader can see it: a PR comment starting \`[lane.$4] waiting:\`
naming what you are waiting for and what will resolve it. If it is an arm --
a replicate you registered, say -- this job does not resume you while that arm
is queued or running, and resumes you once when its verdict is judged; a push
of your own is not a verdict. If it is any other device request of yours (a
soak, a study), it resumes you once when the last of them has finished.
Anything else, it finds you again on the quiet clock.
EOF
}

# ------------------------------------------------------------- lane naming
# THE LANE NAME IS NOT THE PR, AND NOT EVERY HEAD BRANCH HAS ONE. `lane/<name>`
# is a local lane with a worktree under $WORK/wt. `lane/cloud-*` is a cloud
# session's branch: no local worktree, and roles/board.md says cloud lanes
# remediate themselves. `claude/hakux-...` is an interactive session's branch
# with no lane at all. Both are live on this repository today, so a guess here
# is a wrong `lane.sh resume` that burns an attempt against the escalation
# budget of a lane that does not exist.
#
# It sets NAME and REASON rather than printing the name: `n=$(lane_name ...)`
# runs the function in a command-substitution subshell, so the REASON it sets
# on the refusing paths is discarded and the PR gets a comment that stops
# mid-sentence at the colon -- which is the whole content of the answer.
#
# A REMOTE LANE IS ELSEWHERE, NOT ABSENT, and that is a different answer. The
# `*)` arm below used to catch `lane.remote`'s `claude/...` head and tell its PR
# "whoever owns this branch merges origin/master into it by hand" -- true of a
# person's branch and wrong about a lane that has been contributing for days.
# The routine that wakes that session picks the handback up on its next fire;
# saying so is the whole fix, because nothing local should act.
#
# IT IS TESTED FIRST, BEFORE THE `lane/*` ARMS. A remote lane whose branch is
# someday named `lane/<name>` would otherwise fall into the local arm and be
# resumed here -- a second agent on a branch a cloud container pushes to, with
# no lock. `lane.sh` refuses that too; this is not the only guard, on purpose.
#
# THE DEPTH IS REAL ONLY BECAUSE THE TWO GUARDS FAIL DIFFERENTLY. This one
# reads a POSITIVE -- "some row names this branch" -- which the fold-lagged
# in-tree territory.toml can still answer truthfully; what it cannot answer is
# the absence, and this arm never asks it to. When the board read is stale and
# the row is missing, the head falls through to the local arm and reaches the
# single resume call site below -- where `remote_authoritative` refuses
# outright (lane.sh's refuse_if_remote). Two guards, two different questions,
# not one question asked twice.
#
# (Not spelling the resume invocation out here is deliberate:
# `99-handback-draft.sh` counts that exact string to prove there is ONE call
# site, and a comment quoting it makes the count read 2. A grep anchored on a
# call matches the prose too.)
NAME=""; REASON=""
lane_name() {   # <head branch> -> 0 with $NAME set, or 1 with $REASON set
    NAME=""; REASON=""
    local rl; rl=$(remote_lane_of "$1")
    if [ -n "$rl" ]; then
        REASON="\`$1\` is \`lane.$rl\`'s branch, and that lane runs somewhere this host cannot see (\`remote\` in \`territory.toml\`). Nothing local resumes it and nothing local should: its routine picks this up on its next fire. The work is unchanged -- merge \`origin/$TIP\` into the branch, resolve, push, then re-apply \`fold-ready\`."
        return 1
    fi
    case "$1" in
        lane/cloud-*)
            REASON="\`$1\` is a cloud session's branch: it has no local worktree, and cloud lanes remediate themselves (\`jobs/roles/cloud.md\`). Nothing local can resume it."
            return 1 ;;
        lane/*/*)
            REASON="\`$1\` has a slash inside the lane name; \`lane.sh\` names a worktree \`\$WORK/wt/<name>\` and a unit \`hakux-lane-<name>\`, neither of which can hold one. Not guessing."
            return 1 ;;
        lane/?*)
            NAME="${1#lane/}"; return 0 ;;
        *)
            REASON="\`$1\` is not a \`lane/<name>\` branch, so there is no local lane to resume. Whoever owns this branch merges \`origin/$TIP\` into it by hand."
            return 1 ;;
    esac
}

# ------------------------------------------------------------- the pickup
prs_for() {   # <label> -> "num<TAB>headRefName<TAB>headRefOid<TAB>labels,comma,separated"
    gh pr list --repo "$GH_REPO" --state open --label "$1" --json number,headRefName,headRefOid,labels \
        --jq 'sort_by(.number)[] | "\(.number)\t\(.headRefName)\t\(.headRefOid)\t\(.labels | map(.name) | join(","))"' 2>/dev/null
}

# THE JOIN NOTHING ELSE MAKES. One query, so the CI state and the quiet clock
# arrive with the row rather than costing a `pr view` per PR: `statusCheckRollup`
# is collapsed to the same four states `fold.sh` uses (its gate is the same
# question), and `quiet` is seconds since the PR last changed, taken from
# GitHub's own `updatedAt` rather than a timestamp on this host -- so the clock
# survives a restart of the timer and does not start over when a job is
# redeployed. The unit-liveness half of the join is below, per row: it is a
# systemd question and gh cannot answer it.
#
# LABELS GO LAST, AND THAT IS NOT COSMETIC. `IFS=$'\t' read` treats tab as IFS
# WHITESPACE, so a run of tabs collapses to one delimiter and an EMPTY INTERIOR
# FIELD silently disappears -- every field after it shifts left by one. Most
# lane PRs carry no labels at all, so with labels in the middle this pickup read
# `isDraft=true ci=...` as the label list and the state as empty, and every
# stranded draft was refused as an unfiltered row. Only the LAST field may be
# empty (a trailing delimiter is dropped harmlessly), so the one field that
# routinely is goes there.
#
# THE CI CLASSIFIER IS ONE jq `def`, shared by this pickup and by `head_ci`
# below, so the two questions "is this draft's head green" and "is this
# resolved head green" cannot drift into two answers. `""` is what gh prints
# for a conclusion still in flight and `//` does not catch it, so it reaches
# the tests below as `""` -- neither all-success nor any-failure -- and reads
# PENDING, which is what it is. NO RUNS AT ALL is NONE and never GREEN: a PR
# that does not merge gets no runs, so an empty rollup is the conflict's
# signature, not a pass.
CI_STATE_JQ='def ci_state: [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
              | if ($c | length) == 0 then "NONE"
                elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
                elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
                else "PENDING" end; '
stranded_drafts() {   # -> "num<TAB>branch<TAB>head<TAB>isDraft=<b> ci=<STATE> quiet=<secs><TAB>labels"
    gh pr list --repo "$GH_REPO" --state open --limit 100 \
        --json number,headRefName,headRefOid,isDraft,labels,updatedAt,statusCheckRollup \
        --jq "$CI_STATE_JQ"'sort_by(.number)[] | select(.isDraft) | select(.headRefName | startswith("lane/"))
              | ci_state as $ci
              | "\(.number)\t\(.headRefName)\t\(.headRefOid)\tisDraft=\(.isDraft) ci=\($ci) quiet=\((now - (.updatedAt | fromdateiso8601)) | floor)\t\(.labels | map(.name) | join(","))"' 2>/dev/null
}

# ------------------------------------------------ is the conflict still there
# THE LANE'S LAST STEP IS A WAIT IT CANNOT MAKE. `resume_rebase` ends "once CI
# is green on the new head, swap needs-rebase for fold-ready"; a lane cannot
# sleep ten minutes, so it pushes the merge and exits with the swap undone.
# The PR still carries `needs-rebase`, its head is new, no unit is running, so
# every guard below reads a fresh cause and resumes it -- for a conflict that
# no longer exists. Each resume spends one of four attempts: #234 wasted one
# on 2026-09-25, and #237 was handed to the owner as `blocked:needs-owner` at
# 14:25Z with a clean head whose CI went green minutes later. So the label
# path first asks the question the label is about, on a fresh fetch.
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
TIP_SHA=""; TIP_FETCHED=""
MERGE_STATE=""
merge_state() {   # <branch> <head> -> MERGE_STATE=CLEAN|CONFLICT|UNKNOWN, TIP_SHA set
    MERGE_STATE=UNKNOWN
    # Once per tick: every row is judged against the same trunk head, and the
    # comment names it. The tracking ref, not FETCH_HEAD, for fold.sh's reason
    # (tip_state): several jobs fetch in this checkout.
    if [ -z "$TIP_FETCHED" ]; then
        TIP_FETCHED=1
        git -C "$REPO" fetch -q origin "+refs/heads/$TIP:refs/remotes/origin/$TIP" 2>/dev/null \
            && TIP_SHA=$(git -C "$REPO" rev-parse -q --verify "refs/remotes/origin/$TIP^{commit}" 2>/dev/null)
    fi
    [ -n "$TIP_SHA" ] || return 0
    # The head the ROW names, not whatever the branch holds now: the CI state
    # is read for that sha too, and a verdict about a neighbouring commit is
    # not one. Fetched only when this object store does not have it already.
    git -C "$REPO" cat-file -e "$2^{commit}" 2>/dev/null \
        || git -C "$REPO" fetch -q origin "+refs/heads/$1:refs/remotes/origin/$1" 2>/dev/null
    git -C "$REPO" cat-file -e "$2^{commit}" 2>/dev/null || return 0
    # merge-tree exits 0 on a clean merge, 1 on a conflict, anything else on
    # an error. Only the first two are answers; the rest keeps UNKNOWN, and
    # UNKNOWN is handled exactly as before this check existed.
    git -C "$REPO" merge-tree --write-tree --no-messages "$TIP_SHA" "$2" >/dev/null 2>&1
    case $? in 0) MERGE_STATE=CLEAN ;; 1) MERGE_STATE=CONFLICT ;; esac
    return 0
}
# The CI state of the head, from the same classifier as the draft pickup, with
# the head it describes so a push between the pickup and this read cannot
# lend one commit's green to another.
head_ci() {   # <pr> -> "<headRefOid>\t<STATE>", or nothing
    gh pr view "$1" --repo "$GH_REPO" --json headRefOid,statusCheckRollup \
        --jq "$CI_STATE_JQ"'"\(.headRefOid)\t\(ci_state)"' 2>/dev/null
}

# ONE STREAM, ONE BODY. The two pickups ask GitHub different questions and
# produce the same eight fields, so everything that follows -- the lane name,
# the once-per-cause key, the worktree check, the liveness check, the cap, the
# attempt counter, the comment -- is written once. `$stale` holds spaces, which
# is why the stream is tab-separated and the rows are built before the loop:
# `while ... | read` would run the body in a subshell and lose `$resumed`.
#
# The same empty-interior-field rule applies here: `labels` is last, and a
# label row's `extra` is "-" rather than "", because tab is IFS whitespace and
# an empty field between two others is not a field at all after `read`.
rows=""
for row in "${HANDBACK_ROWS[@]}"; do
    read -r label action stale <<< "$row"
    while IFS=$'\t' read -r pr branch head labels; do
        [ -n "${pr:-}" ] || continue
        rows+="$label"$'\t'"$action"$'\t'"$stale"$'\t'"$pr"$'\t'"$branch"$'\t'"$head"$'\t'"-"$'\t'"$labels"$'\n'
    done <<< "$(prs_for "$label")"
done
while IFS=$'\t' read -r pr branch head extra labels; do
    [ -n "${pr:-}" ] || continue
    # WHICH WAIT RESOLVED decides the cause, and the cause is the marker key.
    # `verified`/`regressed` is `arms.sh` saying a verdict landed, which is
    # information this lane has never seen; anything else falls to the clock.
    case ",$labels," in
        *,verified,*|*,regressed,*) strand_cause=draft-strand-arm ;;
        *)                          strand_cause=draft-strand-quiet ;;
    esac
    rows+="$strand_cause"$'\t'"resume_strand"$'\t'"$STRAND_STALE"$'\t'"$pr"$'\t'"$branch"$'\t'"$head"$'\t'"$extra"$'\t'"$labels"$'\n'
done <<< "$(stranded_drafts)"

resumed=0; seen=0
while IFS=$'\t' read -r label action stale pr branch head extra labels; do
        [ -n "${pr:-}" ] || continue

        # THE ROW MUST PROVE THE FILTER HAPPENED. Neither pickup is re-checked
        # by anything downstream, so a row that comes back not matching what it
        # was asked for means the filter did not happen -- a `--jq` that stopped
        # emitting a field, a gh that ignored a flag, a shim. The failure mode
        # is not "nothing found", which would be visible; it is resuming the
        # FIRST OPEN PR on the repository, by name, against its lane's attempt
        # budget. Found by the fold-ci checks, whose gh shim answers every
        # `pr list` with one row: every fold tick ran a resume of lane.foldci
        # and commented on #102.
        case "$label" in
        draft-strand-*)
            # `isDraft` and the branch shape are both filtered in the --jq, so
            # a row failing either is a row that bypassed the query. A draft
            # that is not a draft is the whole premise of this cause.
            case "$extra" in
                *"isDraft=true"*) ;;
                *) say "#${pr:-?} came back from the draft pickup without isDraft=true (extra=${extra:-none}); the filter did not happen, so acting on it would resume a lane that is not stranded"
                   continue ;;
            esac
            case "$branch" in
                lane/*) ;;
                *) say "#${pr:-?} came back from the draft pickup on branch ${branch:-none}, which is not lane/*; the filter did not happen"
                   continue ;;
            esac ;;
        *)
            case ",$labels," in
                *",$label,"*) ;;
                *) say "#${pr:-?} came back for --label $label without it (labels=${labels:-none}); the filter did not happen, so acting on it would resume the wrong lane"
                   continue ;;
            esac ;;
        esac

        seen=$((seen+1))
        skip=""
        for s in $stale; do case ",$labels," in *",$s,"*) skip="$s" ;; esac; done
        if [ -n "$skip" ]; then
            [ "$mode" = list ] && echo "#$pr $branch: $label but also $skip; already moved on"
            continue
        fi

        # ------------------------------ needs-rebase: does it still conflict?
        # Before the lane name, the marker, the liveness check, the cap and the
        # resume: the swap needs no lane, and a head that merges cleanly is not
        # a cause for one. Only a CLEAN answer changes anything; CONFLICT and
        # UNKNOWN (no fetch, no object, a merge-tree error) fall through to the
        # resume this job always did.
        merge_note=""; merge_why=""
        if [ "$label" = needs-rebase ]; then
            merge_state "$branch" "$head"
            if [ "$MERGE_STATE" = CLEAN ]; then
                hc=$(head_ci "$pr"); ci_head="${hc%%$'\t'*}"; ci="${hc#*$'\t'}"
                [ -n "$hc" ] && [ "$ci_head" != "$hc" ] || { ci_head=""; ci=UNKNOWN; }
                if [ -n "$ci_head" ] && [ "$ci_head" != "$head" ]; then
                    # The branch moved between the pickup and this read. The next
                    # tick sees the new head as its own row; acting now would
                    # join one commit's merge to another's CI.
                    [ "$mode" = list ] && { echo "#$pr $branch: head moved (${head:0:10} -> ${ci_head:0:10}) during this tick; next tick"; continue; }
                    say "#$pr: head moved from ${head:0:10} to ${ci_head:0:10} during this tick; judged next tick"
                    continue
                fi
                case "$ci" in
                GREEN)
                    # THE LANE'S OWN LAST STEP, done here. No resume, so no
                    # attempt; the head has merged the trunk and been built.
                    [ "$mode" = list ] && { echo "#$pr $branch @ ${head:0:10}: merges cleanly into $TIP ${TIP_SHA:0:10}, CI GREEN; WOULD RELABEL fold-ready (no resume)"; continue; }
                    if label_rm "$pr" needs-rebase && label_add "$pr" fold-ready; then
                        say "#$pr: ${head:0:10} merges cleanly into $TIP ${TIP_SHA:0:10} and CI is GREEN; relabelled needs-rebase -> fold-ready, lane not resumed"
                        comment "$pr" "[job.handback] Relabelled \`needs-rebase\` -> \`fold-ready\`, and **did not resume** the lane: head \`${head:0:10}\` merges cleanly into \`$TIP\` at \`${TIP_SHA:0:10}\` (checked with \`git merge-tree\` on a fresh fetch) and CI on that head is **GREEN**. That swap was the lane's own last step, which it could not wait for; no attempt was spent on it."
                    else
                        say "  WARNING: could not swap needs-rebase -> fold-ready on #$pr; retried next tick"
                    fi
                    continue ;;
                PENDING)
                    # WAITING, NOT FAILING. No marker for the cause and no
                    # resume; the log line is once per head, so a ten-minute
                    # run is one line, not twenty.
                    [ "$mode" = list ] && { echo "#$pr $branch @ ${head:0:10}: merges cleanly into $TIP ${TIP_SHA:0:10}, CI PENDING; waiting (no resume)"; continue; }
                    if [ ! -f "$H/done/pending-$pr-$head" ]; then
                        echo "$TIP_SHA" > "$H/done/pending-$pr-$head"
                        say "#$pr: ${head:0:10} merges cleanly into $TIP ${TIP_SHA:0:10}; CI PENDING, waiting (not resumed)"
                    fi
                    continue ;;
                esac
                # RED, NONE or UNKNOWN: resumed as before, but told the truth.
                # The brief's "no longer merges into" is not it any more, and
                # the cause file says which of the label's two causes this is.
                cause_act=$(sed -n 's/^action=//p' "$H/cause/$pr-$head" 2>/dev/null | head -1)
                case "$ci" in
                RED)
                    if [ "$cause_act" = resume_stale_ci ]; then
                        merge_why="the head merges cleanly into \`$TIP\` at \`${TIP_SHA:0:10}\`, and its red is the stale-CI cause: it ran before the trunk moved, and only bringing \`$TIP\` in refreshes it"
                    elif git -C "$REPO" merge-base --is-ancestor "$TIP_SHA" "$head" 2>/dev/null; then
                        merge_why="the head already contains \`$TIP\` at \`${TIP_SHA:0:10}\` and CI on it is RED: that is a live failure on this branch, not a base that moved, and fixing it is the task"
                    else
                        merge_why="the head merges cleanly into \`$TIP\` at \`${TIP_SHA:0:10}\` (the conflict no longer reproduces) but CI on it is RED; merge \`$TIP\` in and read the failing check"
                    fi ;;
                NONE)
                    merge_why="the head merges cleanly into \`$TIP\` at \`${TIP_SHA:0:10}\` but has NO CI run at all, which is not green: check the head commit's message for the retired skip-ci marker, or push \`git commit --allow-empty -m 'ci: build this head'\`" ;;
                *)
                    merge_why="the head merges cleanly into \`$TIP\` at \`${TIP_SHA:0:10}\`, but its CI state could not be read" ;;
                esac
                merge_note=$'\n'"**Checked before this resume:** $merge_why."$'\n'
            fi
        fi

        # How the cause reads to a person on the PR. A label says itself; the
        # strand causes are not labels and there is nothing on the PR to point
        # at, so they have to be said in words or the comment names a label
        # that does not exist.
        case "$label" in
            draft-strand-*) said="this PR is a draft and lane \`${branch#lane/}\`'s unit is not running" ;;
            *)              said="\`$label\` is set on this PR" ;;
        esac

        if ! lane_name "$branch"; then
            # Say it once per PR, not once per tick: this state does not change
            # by itself, and a comment every 30 minutes is noise on a PR whose
            # owner is a person.
            [ "$mode" = list ] && { echo "#$pr $branch: $label, NO LANE -- $REASON"; continue; }
            if [ ! -f "$H/done/noname-$pr" ]; then
                printf '%s\n' "$REASON" > "$H/done/noname-$pr"
                say "#$pr $branch: $label but no local lane; $REASON"
                comment "$pr" "[job.handback] $said and no local lane can act on it: $REASON"
            fi
            continue
        fi
        name="$NAME"

        # RESUME ONLY ON A NEW CAUSE. Keyed on the head sha the handback was
        # found at, the way fold.sh already keys $F/failed/$pr-$head: a lane
        # resumed twice for the same head has been given no new information,
        # and the second session re-reads the same NOTES.md and the same diff.
        # When the lane pushes, the head moves and a fresh conflict is a fresh
        # cause.
        #
        # EXCEPT THE ARM CAUSE, which is keyed on the verdicts (see the table
        # above): a lane pushes in answer to a verdict, and that push is not a
        # second verdict. With nothing judged on disk for the branch -- the
        # label set by hand, or an arms dir this host cannot read -- there is
        # no verdict set to key on, and it keeps the head key it always had.
        marker="$H/done/$label-$pr-$head"; keyed="at ${head:0:10}"
        if [ "$label" = draft-strand-arm ]; then
            verdicts_of "$branch"
            [ -z "$VKEY" ] || { marker="$H/done/$label-$pr-v$VKEY"; keyed="on verdicts $VSET"; }
        fi
        # THE RUNS CAUSE is found here, not in the pickup: it is a question
        # about the dispatch dir, not about GitHub. It takes a row the quiet
        # clock would otherwise hold, or an arm row whose verdict was already
        # actioned -- a judged verdict that is news still goes first, because
        # it is the more specific answer. Keyed on the SET of finished runs, so
        # a push is not a new cause and a second soak finishing is.
        INFLIGHT=""; INFLIGHT_KIND=""; RKEY=""; RSET=""; RLIST=""; RUNS_BRIEF=""
        case "$label" in draft-strand-*)
            lane_requests_of "$branch" "$name"
            if [ -z "$INFLIGHT" ] && [ -n "$RKEY" ] \
               && { [ "$label" = draft-strand-quiet ] || [ -f "$marker" ]; } \
               && [ ! -f "$H/done/draft-strand-runs-$pr-r$RKEY" ]; then
                label=draft-strand-runs
                marker="$H/done/$label-$pr-r$RKEY"; keyed="on finished runs $RSET"
                RUNS_BRIEF="$RLIST"
            fi ;;
        esac
        if [ -f "$marker" ]; then
            [ "$mode" = list ] && echo "#$pr $branch: $label already actioned $keyed ($(head -1 "$marker"))"
            continue
        fi

        # The cause detail the action prints into the brief. For a label it is
        # whatever the job that set the label wrote down; for a strand it is
        # the resolved state -- which is the entire reason the resume is worth
        # a session rather than a repeat of the last one.
        cause=""; quiet=0; arm=none; act="$action"
        case "$label" in
        draft-strand-*)
            quiet=$(sed -n 's/.*\bquiet=\([0-9]*\).*/\1/p' <<< "$extra"); quiet="${quiet:-0}"
            case ",$labels," in
                *,regressed,*) arm=regressed ;;
                *,verified,*)  arm=verified ;;
            esac
            cause="${extra#isDraft=* } arm=$arm"
            [ -z "$RUNS_BRIEF" ] || cause+=" runs=$(grep -c . <<< "$RUNS_BRIEF")" ;;
        *)
            # `files=` is what fold.sh's conflict branch has always written;
            # `detail=` is the general field a newer cause uses. Either is the
            # one line of detail the action puts in the brief. A strand has no
            # cause file at all, which is why this is only the label arm.
            if [ -f "$H/cause/$pr-$head" ]; then
                cause=$(sed -n 's/^detail=//p;s/^files=//p' "$H/cause/$pr-$head" | head -1)
                # ONE LABEL, TWO CAUSES: `action=` overrides the row's action so
                # the lane is told the truth about why. AGAINST A WHITELIST, never
                # taken as written -- this string comes out of a file and is about
                # to be the command word of an invocation. An unknown value falls
                # back to the row's own action, which is the label's meaning and
                # is never wrong about what to DO, only about why.
                a=$(sed -n 's/^action=//p' "$H/cause/$pr-$head" | head -1)
                case "$a" in
                    resume_stale_ci) act="$a" ;;
                    "") ;;
                    *) say "#$pr: cause names action '$a', which is not one of this job's; using $action" ;;
                esac
            fi ;;
        esac

        if [ ! -d "$WORK/wt/$name" ] || [ ! -f "$WORK/briefs/$name.md" ]; then
            [ "$mode" = list ] && { echo "#$pr $branch: $label, lane $name has no worktree or brief on this host"; continue; }
            echo "no worktree or brief for lane $name" > "$marker"
            say "#$pr: lane $name has no worktree ($WORK/wt/$name) or brief; cannot resume"
            # AND IT IS LABELLED, NOT ONLY COMMENTED. A PR comment is read by
            # whoever opens the PR; nothing polls it. This is the end of the
            # line for a lane that is not merely exited but GONE -- no session
            # can be resumed and this job will never act on this head again --
            # so it gets the label that means the owner's call, the same one
            # the attempts-exhausted path sets, and appears in status.sh's
            # roll-up instead of only in a comment nobody is looking at.
            label_add "$pr" blocked:needs-owner || say "  WARNING: could not label #$pr blocked:needs-owner"
            comment "$pr" "[job.handback] $said and lane \`$name\`'s worktree or brief is gone from this host (\`$WORK/wt/$name\`), so \`lane.sh resume\` cannot run. It needs \`lane.sh start $name <brief>\`, which is the board's call, not this job's. Labelled \`blocked:needs-owner\` so this PR is not waiting in silence: **nothing will act on it until someone does.**"
            continue
        fi

        # A lane whose unit is still running is not stalled, and
        # `systemd-run --unit` on a live unit fails AFTER lane.sh has already
        # counted the attempt -- a wasted attempt against the four the
        # escalation policy allows. No marker: next tick looks again.
        if systemctl --user is-active --quiet "hakux-lane-$name" 2>/dev/null; then
            [ "$mode" = list ] && echo "#$pr $branch: $label, but hakux-lane-$name is still running"
            say "#$pr: lane $name is still active; not resuming"
            continue
        fi

        # ------------------------------------------ the strand's own two gates
        uncounted=""
        case "$label" in draft-strand-*)
            # ITS OWN ARM IS IN FLIGHT: THE LANE IS WAITING, AND RIGHTLY. Its
            # replicate is queued or running on a device, and the verdict that
            # arm produces is the next new cause; resumed now, it is told what
            # it already knew and spends one of DRAFT_STRAND_MAX on it. #245
            # was capped exactly so. No marker for the cause -- the verdict has
            # not landed -- and one log line per request, not one per tick.
            # ANY DEVICE REQUEST OF ITS OWN, not only an arm: a lane whose soak
            # is queued is waiting just as rightly, and its finishing is the
            # runs cause's news. INFLIGHT was read with the runs set, above.
            if [ -n "$INFLIGHT" ]; then
                what="its arm is in flight"; until="it is judged"
                [ "$INFLIGHT_KIND" = arm ] || { what="its device request is in flight"; until="its requests have finished"; }
                [ "$mode" = list ] && { echo "#$pr $branch: draft, lane $name not running, but $what ($INFLIGHT); waiting on it"; continue; }
                inflight_marker="$H/done/inflight-$pr-${INFLIGHT#*/}"
                if [ ! -f "$inflight_marker" ]; then
                    echo "$INFLIGHT" > "$inflight_marker"
                    say "#$pr: lane $name is stranded in draft but $what ($INFLIGHT); not resuming until $until"
                fi
                continue
            fi
            # WAITING IS NOT STRANDED. `draft-strand-quiet` fires on a clock and
            # nothing else, so before it does, the clock has to have run long
            # enough that the thing the lane was waiting for would have landed.
            # An arm is ~90 minutes; resuming at 30 would hand the session the
            # same "still queued" it ended on, and the marker would then keep
            # it from ever being resumed at that head again. No marker here:
            # the cause is unactioned and the clock is still running.
            # `draft-strand-arm` skips this -- a judged verdict IS the landing.
            if [ "$label" = draft-strand-quiet ] && [ "$quiet" -lt "$DRAFT_STRAND_SECS" ]; then
                [ "$mode" = list ] && { echo "#$pr $branch: draft, lane $name not running, but only quiet ${quiet}s of $DRAFT_STRAND_SECS; still waiting"; continue; }
                say "#$pr: lane $name is stranded in draft but only quiet ${quiet}s; waiting for $DRAFT_STRAND_SECS"
                continue
            fi
            # THE BOUND THAT REPLACES THE ATTEMPT THIS CAUSE DOES NOT SPEND.
            # Waiting is not failing, so a strand resume puts the attempt
            # counter back (below) -- which means the escalation policy cannot
            # end this, and something must. A lane handed the resolved state
            # DRAFT_STRAND_MAX times and still in draft is not waiting on
            # anything this job can see; that is a person's question.
            #
            # EXCEPT THE RUNS CAUSE, which neither counts nor is capped. It is
            # bounded by its own events: it fires only on a run that finished
            # after the lane's last session ENDED, and the resume starts a new
            # session, so it cannot recur until the lane queues more device
            # work -- which is the lane making progress, not looping. Counted,
            # a lane with four soaks in a row would be labelled
            # `blocked:needs-owner` for waiting on its own results.
            nstrand=$(cat "$H/strand/$name" 2>/dev/null || echo 0)
            [ "$label" = draft-strand-runs ] && nstrand=-1
            if [ "$nstrand" -ge "$DRAFT_STRAND_MAX" ]; then
                [ "$mode" = list ] && { echo "#$pr $branch: draft, lane $name not running, but already strand-resumed $nstrand times (DRAFT_STRAND_MAX=$DRAFT_STRAND_MAX)"; continue; }
                if [ ! -f "$H/done/strandmax-$pr" ]; then
                    printf '%s\n' "$nstrand" > "$H/done/strandmax-$pr"
                    say "#$pr: lane $name strand-resumed $nstrand times already; handing to the owner"
                    label_add "$pr" blocked:needs-owner || say "  WARNING: could not label #$pr blocked:needs-owner"
                    comment "$pr" "[job.handback] Not resumed -- $said, and this job has already resumed \`lane.$name\` $nstrand times for that (\`DRAFT_STRAND_MAX=$DRAFT_STRAND_MAX\`). Those resumes did **not** spend the lane's attempts, because waiting is not failing, so nothing else was going to stop this.

It wants a person now. Either the lane is waiting on something this job cannot see, or its definition of done is not reachable from the brief it has. Per \`jobs/roles/board.md\`, that is the \`decision-needed\` path; \`rm $H/strand/$name\` on the host clears the count if the answer is just \"resume it again\"."
                fi
                continue
            fi
            uncounted=1 ;;
        esac

        if [ "$mode" = list ]; then echo "#$pr $branch @ ${head:0:10}: WOULD RESUME lane.$name ($label)"; continue; fi
        [ "$resumed" -eq 0 ] || { say "#$pr waits: one resume per tick"; continue; }

        # The handback goes in the brief BEFORE the resume, because that file is
        # what `lane.sh resume` hands the session -- and it is rolled back if the
        # resume does not happen. A capped tick that left the section behind
        # would append another on the next tick and another after that, so the
        # session that finally ran would open with the same paragraph five
        # times and no way to tell which head each one was about.
        size=$(wc -c < "$WORK/briefs/$name.md")
        # WAITING IS NOT FAILING, AND THE COUNTER CANNOT TELL THEM APART.
        # `lane.sh resume` counts every resume as an attempt: the fourth runs
        # on the escalated model and the fifth is refused outright. That is the
        # right policy for a lane that ended without finishing, and the wrong
        # one for a lane that ended because CI takes ten minutes -- re-merges
        # burned two lanes' attempts and escalated one to Fable for no reason
        # of its own on 2026-09-19. So the count is read before and put back
        # after, for the strand causes only. It is safe to do from here: by the
        # time `lane.sh resume` returns 0 the unit is up, and a second
        # `systemd-run --unit hakux-lane-$name` cannot start while it is, so
        # nothing else writes that file in between.
        attempts_before=$(cat "$WORK/attempts/$name" 2>/dev/null || echo 0)
        # `$act`, not `$action`: one label can carry two causes and the cause
        # file's `action=` (whitelisted above) says which brief to print.
        "$act" "$pr" "$branch" "$head" "$name" "$cause" >> "$WORK/briefs/$name.md"
        [ -z "$merge_note" ] || printf '%s\n' "$merge_note" >> "$WORK/briefs/$name.md"
        out=$(bash "$LANE_SH" resume "$name" 2>&1); rc=$?
        [ "$rc" -eq 0 ] || truncate -s "$size" "$WORK/briefs/$name.md"
        if [ "$rc" -eq 0 ] && [ -n "$uncounted" ]; then
            printf '%s\n' "$attempts_before" > "$WORK/attempts/$name"
            [ "$label" = draft-strand-runs ] \
                || printf '%s\n' "$(( $(cat "$H/strand/$name" 2>/dev/null || echo 0) + 1 ))" > "$H/strand/$name"
            echo "resumed (strand, attempt not counted): $out" > "$marker"
            say "#$pr: resumed lane.$name on $label -- $out"
            comment "$pr" "[job.handback] Resumed \`lane.$name\`: $said, so nothing else could act on it -- \`board.sh\`, \`fleet.py\` and \`fold.sh\` all skip drafts, and that is right while a lane is working.

The resolved state went into its brief (\`${head:0:10}\`: \`$cause\`), because a lane resumed with no new information repeats what it did before. **This did not spend one of the lane's attempts**: waiting on a ten-minute CI run or a ninety-minute arm is not a failed pass, and the escalation policy is for failed passes. It is bounded instead at \`DRAFT_STRAND_MAX=$DRAFT_STRAND_MAX\` per lane, at once per head sha for the quiet clock, at once per new judged verdict for an arm, and at once per new set of finished device runs -- pushing in answer to a verdict does not bring you back here, and nor does waiting on a request that is still queued.${RUNS_BRIEF:+ Finished runs this time: \`$RSET\`.}

This job does **not** mark a PR ready: the definition of done includes \`NOTES.md\`, the \`Files:\` line and the prediction refs, none of which a script can check. That call stays with the lane."
            resumed=1
        elif [ "$rc" -eq 0 ]; then
            echo "resumed: $out" > "$marker"
            say "#$pr: resumed lane.$name -- $out"
            # The cause in one clause, in the words of the cause it actually
            # was: "conflicting in ..." on a PR that merges cleanly is the
            # wrong sentence, and it is the sentence a lane acts on.
            case "$act" in
                resume_stale_ci) why="${cause:+ (its red is stale: \`$cause\`, which ran before the current head of \`$TIP\`)}" ;;
                *)               why="${cause:+ (conflicting in \`$cause\`)}" ;;
            esac
            # A clean head says so instead: "conflicting in" is fold.sh's
            # record of an earlier head, and the lane acts on this sentence.
            [ -z "$merge_why" ] || why=" -- $merge_why"
            comment "$pr" "[job.handback] Resumed \`lane.$name\` on \`$label\` at \`${head:0:10}\`$why. The handback was appended to its brief: merge \`origin/$TIP\` (never rebase -- it would un-ancestor any registered prediction), resolve, push, then re-apply \`fold-ready\`. This job resumes a lane once per head sha, so pushing is what makes another handback possible."
            resumed=1
        elif grep -q 'LANE_MAX_ATTEMPTS' <<< "$out"; then
            # THE END OF THE LINE, AND IT MUST STAY REACHABLE. lane.sh refuses
            # after LANE_MAX_ATTEMPTS and the board opens a decision-needed
            # issue (roles/board.md). Marked, so this is said once.
            echo "attempts exhausted: $out" > "$marker"
            say "#$pr: lane $name REFUSED (attempts exhausted): $out"
            label_add "$pr" blocked:needs-owner || say "  WARNING: could not label #$pr blocked:needs-owner"
            comment "$pr" "[job.handback] Not resumed -- \`lane.$name\` has used every attempt:
\`\`\`
$out
\`\`\`
This is the owner's call now. Per \`jobs/roles/board.md\`, the board opens a \`decision-needed\` issue quoting this lane's \`NOTES.md\` and does not start it again; the attempt counter is reset only by the owner, when the brief was the problem."
        elif grep -q 'LANE_MAX=' <<< "$out"; then
            # The fleet cap, not a failure. NO MARKER: the cause is unchanged
            # and still unactioned, and the next tick must try it again. lane.sh
            # checks the cap before it counts the attempt, so nothing was spent.
            say "#$pr: lane $name not resumed, fleet at cap: $out"
        else
            echo "resume failed: $out" > "$marker"
            say "#$pr: lane $name resume FAILED rc=$rc: $out"
            comment "$pr" "[job.handback] \`lane.sh resume $name\` failed (rc=$rc) on \`$label\` at \`${head:0:10}\`:
\`\`\`
$out
\`\`\`
Not retried at this head. Push to the branch, or fix the host, and the next tick reads a new cause."
        fi
done <<< "$rows"

# Say so when there is nothing, the way `fold.sh list` does: an empty run and a
# broken `gh` look identical otherwise, and this job's whole output is one line
# in $WORK/logs/handback/tick.log that somebody reads at a distance. It names
# every cause it looked for, including the two that are not labels -- otherwise
# a draft pickup that silently stopped working reads exactly like a quiet day.
CAUSES="${HANDBACK_ROWS[*]%% *} draft-strand-arm draft-strand-runs draft-strand-quiet"
[ "$seen" -eq 0 ] && { [ "$mode" = list ] && echo "nothing handed back ($CAUSES)" || say "nothing handed back ($CAUSES)"; }
exit 0
