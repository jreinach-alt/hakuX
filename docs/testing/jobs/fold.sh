#!/usr/bin/env bash
#
# The fold job. Runs from hakux-fold.timer every 30 minutes; a script, no
# model session.
#
#   fold.sh          fold the oldest fold-ready PR whose CI is green
#   fold.sh list     what it would fold, and why the rest waits
#   fold.sh prune    what the one-time sweep WOULD delete (a dry run)
#   fold.sh prune --apply
#                    sweep every lane ref already fully merged into the trunk
#   fold.sh resolve-notes <worktree> <branch>
#                    the one conflict resolution below, on an in-progress
#                    merge, so the self-test can run it without a fake gh
#   fold.sh prune-branch <dir> <branch> <proof>
#                    the branch deletion, on a repository handed in, so the
#                    self-test can run it against a scratch remote, same reason
#   fold.sh preflight-verdict <preflight log>
#                    `board` or `tree`: whose failure that log describes, for
#                    the same reason -- a decision worth testing on its own
#
# A FOLD IS A --no-ff MERGE OF THE LANE BRANCH INTO master, so every commit
# keeps its sha and every prediction's b_ref stays an ancestor forever
# (docs/ORCHESTRATION-DESIGN.md §8.1). It happens in a private worktree that
# nothing else touches; the owner's checkout is never dirtied and never
# detached. One fold per tick: each fold is a new tree and runs CI on master,
# and two folds ten seconds apart cannot be told apart in that run.
#
# WHAT MAKES A PR FOLD-READY is the label, and the label is set by the
# auditor (pass 2 clean) or by the board (a docs/NOTES-only PR needs no
# audit). This job checks what the label cannot: the PR is not a draft, it
# does not carry an unaccepted `regressed` verdict, its head's CI is green,
# and the merge applies without conflict. A conflict is never resolved here
# -- the lane gets `needs-rebase` and a comment naming the files, because a
# merge resolved by a script that does not understand the code is how a
# working fix was reverted on 2026-09-12.
#
# A RED VERDICT ABOUT A BASE THAT HAS MOVED IS STILL REFUSED, BUT NOT IN
# SILENCE. When a required check breaks on the trunk, every open PR keeps the
# FAILURE it got from the broken tree -- GitHub never re-runs a PR's checks
# when its base moves -- and this job used to refuse such a head every tick
# forever. It now compares the failing runs' start times against the trunk
# head's commit time and hands a stale one back for a base merge. See "a red
# about a base that moved" below; nothing there ever folds on a stale verdict.
#
# THE ONE EXCEPTION IS A ROOT NOTES.md, AND IT IS A RENAME, NOT A MERGE.
# roles/lane.md used to ask every lane for `NOTES.md` in the branch root.
# master has none, so the first fold lands one and EVERY fold after it
# conflicts on that exact path -- permanently, since master then holds lane
# A's notes and lane B's are a conflicting rewrite of the same file. The
# instruction is now `docs/lanes/<lane>/NOTES.md`, but the lanes that were
# already running never saw it. So: when the ONLY unmerged path is root
# NOTES.md, the incoming copy is moved to the lane's own path and the fold
# continues. There is no content decision in that -- both sides are kept,
# each at its own path, and nothing is discarded. Any other conflicting
# path, alone or alongside NOTES.md, still returns the PR to its lane.
#
# THE INDEX IS REGENERATED, NEVER MERGED. nv2a_index.json records line
# numbers, so a merge of two edits to it is stale by construction. If
# nv2a_index.py check fails after the merge the index is rebuilt from the
# test sources and committed on top, in the same push.
#
# AND THEN THE BRANCH IS DELETED. See prune_branch below: the fold is the one
# moment that has just PROVED every commit is on the trunk, and nothing else
# in the harness ever removed a lane ref.
set -u
WORK="${HAKUX_WORK:-/home/justin/hakux-work}"
REPO="${HAKUX_REPO_DIR:-/home/justin/hakuX}"
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"
TIP="${HAKUX_TIP:-master}"
WT="$WORK/fold-wt"
F="$WORK/fold"
T="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$(dirname "${BASH_SOURCE[0]}")/gh-label.sh"   # label_add/label_rm: `gh pr edit --add-label` exits 1 here
. "$(dirname "${BASH_SOURCE[0]}")/localtime.sh"  # say_time/local_ts: the display zone. Data timestamps below stay `date -u`.
. "$(dirname "${BASH_SOURCE[0]}")/remote-lane.sh" # is_remote_branch: a branch this host must never delete
mkdir -p "$F/failed" "$WORK/logs/fold"
LOG="$WORK/logs/fold/tick.log"
# The tick log is read by hand when something jams, so it is display: local.
say() { echo "$(say_time_s) $*" | tee -a "$LOG"; }
mode="${1:-run}"

find_repo() { for d in "$HOME/$1" /home/justin/"$1" /home/user/"$1"; do [ -d "$d/.git" ] && { echo "$d"; return; }; done; }
TESTS="${TESTS:-$(find_repo nxdk_pgraph_tests)}"; SUPPORT="${SUPPORT:-$(find_repo pbkitplusplus)}"

comment() { printf '%s\n' "$2" > "$F/comment.md"; gh pr comment "$1" --repo "$GH_REPO" --body-file "$F/comment.md" >/dev/null 2>&1; }

# ------------------------------------------------- the one resolution
notes_path() {   # <branch> -> the per-lane notes path roles/lane.md asks for
    local b="${1#lane/}"; printf 'docs/lanes/%s/NOTES.md' "${b//\//-}"
}
resolve_root_notes() {   # <worktree> <branch> -> 0 when the merge is left fully staged
    local wt="$1" branch="$2" dest; dest=$(notes_path "$branch")
    # ONLY a root NOTES.md. One unmerged path, and that path exactly.
    [ "$(git -C "$wt" diff --name-only --diff-filter=U)" = "NOTES.md" ] || return 1
    # The lane's copy is moved, never dropped: its record is the point. If
    # the destination is already occupied -- the lane wrote both paths, or
    # folded once before -- then moving it WOULD be a content decision, and
    # this job does not make those: hand it back like any other conflict.
    [ ! -e "$wt/$dest" ] || return 1
    git -C "$wt" cat-file -e MERGE_HEAD:NOTES.md 2>/dev/null || return 1
    mkdir -p "$wt/$(dirname "$dest")" || return 1
    git -C "$wt" show MERGE_HEAD:NOTES.md > "$wt/$dest" || return 1
    git -C "$wt" add -- "$dest" || return 1
    # The root path takes master's side unchanged -- this end of the merge
    # decides nothing about content it did not write.
    if git -C "$wt" cat-file -e HEAD:NOTES.md 2>/dev/null; then
        git -C "$wt" checkout HEAD -- NOTES.md && git -C "$wt" add -- NOTES.md || return 1
    else
        git -C "$wt" rm -q -f -- NOTES.md || return 1
    fi
    [ -z "$(git -C "$wt" diff --name-only --diff-filter=U)" ] || return 1
}
if [ "$mode" = resolve-notes ]; then
    resolve_root_notes "${2:?worktree}" "${3:?branch}"; exit $?
fi

# ------------------------------------------- deleting a folded lane branch
# Nothing in the harness ever removed a lane ref. arms.sh's collect() walks
# refs/remotes/origin/lane/* on every tick, and its fetch refspec
# (+refs/heads/lane/*:refs/remotes/origin/lane/*) does NOT prune, so the cost
# of every arms tick and every board tick grew monotonically with the number
# of lanes the project had ever run -- 25 refs on 2026-09-19, 8 of them long
# since folded -- and none of that growth is work.
#
# THIS IS SAFE FOR A REGISTERED b_ref, AND IT IS CHECKED, NOT ASSUMED. Folds
# are --no-ff so every commit keeps its sha; deleting a ref whose every commit
# is already on the trunk orphans nothing, which is exactly what "fully
# merged" means, and the arms job's "is the b_ref an ancestor of a live tip"
# test still passes against the trunk afterwards. Getting it wrong silently
# un-arms predictions, so the ancestry is tested against the commit that was
# just pushed rather than against a remote-tracking ref that is one fetch
# stale, and against what origin holds NOW rather than what the fold fetched:
# a lane that pushed after the merge's fetch has commits the fold never saw,
# and deleting that ref would destroy them.
#
# THREE REFS, AND THEY ARE NOT THE SAME THING:
#   the remote ref           origin's lane/<name>       deleted here
#   the remote-tracking ref  refs/remotes/origin/lane/  deleted here -- and it
#                            is the one that matters, because nothing prunes
#                            it and IT is what arms.sh walks
#   the local branch         refs/heads/lane/<name>     `branch -d`, which git
#                            refuses while a lane worktree holds it. That
#                            refusal is the wanted answer: the ref is left and
#                            the log says so. Never -D, never --force. The
#                            worktree is lane.sh rm's business, not a fold's.
# $WT is a worktree OF $REPO, so both share one ref store: deleting the
# tracking ref through either directory deletes it for both.
prune_branch() {   # <dir sharing $REPO's ref store> <branch> <proof commit> -> 0 when the remote ref is gone
    local d="$1" branch="$2" proof="$3" tracking="refs/remotes/origin/$2" rc remote_sha
    # lane/* and nothing else, ever: not $TIP, not board, not claude/*.
    case "$branch" in
        lane/?*) ;;
        *) say "  NOT pruning '$branch': only lane/* refs are ever deleted"; return 1 ;;
    esac
    # ...AND NOT A REMOTE LANE'S, even when it is named lane/*. A row marked
    # `remote` in territory.toml belongs to a session in a container this host
    # cannot see, which pushes to that branch about once an hour. Deleting the
    # ref of a long-lived cloud lane is not the recoverable kind of mistake:
    # the branch comes back on its next push carrying whatever that container's
    # local copy holds, and anything folded in the meantime is a conflict
    # nobody is watching for. No remote lane is named `lane/*` today, so this
    # is the exemption for the day one is -- which is exactly when nobody will
    # be thinking about it.
    #
    # TARGET NARROWED, NEVER WIDENED: this can only ever refuse. And a board it
    # cannot read is also a refusal -- an un-pruned ref costs a few bytes, and
    # "I could not check" is not "it is safe to delete".
    #
    # `remote_authoritative`, NOT `remote_readable`: the question here is
    # whether NO row names this branch, and the fold-lagged in-tree copy
    # board_files falls back to cannot answer it -- that copy gets a marker
    # only when some later fold carries it over, so it is precisely the one
    # missing the row the board wrote this morning. board.sh fetches
    # `origin/board` before re-execing this job (board.sh:161); a checkout
    # where that has not happened gets this refusal and one fetch fixes it.
    if ! remote_authoritative; then
        say "  NOT pruning '$branch': the board read came back \`$(remote_source)\` (not origin/board), so whether it belongs to a remote lane is unknown. \`git fetch origin board\` in this checkout."
        return 1
    fi
    if is_remote_branch "$branch"; then
        say "  NOT pruning '$branch': it is lane.$(remote_lane_of "$branch")'s, marked \`remote\` in territory.toml -- a session this host cannot see pushes to it"
        return 1
    fi
    # ...and a plain ref path, so nothing in it can read as an option to push
    # or expand into a second ref. check-ref-format refuses .., ~, ^, :, *, a
    # trailing lock and a leading dash for us.
    git check-ref-format "refs/heads/$branch" 2>/dev/null \
        || { say "  NOT pruning '$branch': check-ref-format refuses that name"; return 1; }

    git -C "$d" ls-remote --exit-code origin "refs/heads/$branch" > "$F/lsremote" 2>/dev/null; rc=$?
    if [ "$rc" -eq 2 ]; then
        # Already gone from origin (deleted by hand, or a re-run of the sweep).
        # The tracking ref is then pointing at nothing live and is pure cost.
        git -C "$d" update-ref -d "$tracking" 2>/dev/null
        say "  $branch: origin has no such ref; dropped the stale tracking ref"
    elif [ "$rc" -ne 0 ]; then
        say "  $branch: cannot reach origin to read the ref (ls-remote exit $rc); kept"
        return 1
    else
        remote_sha=$(cut -f1 < "$F/lsremote")
        # Fetch so the object is present locally; then judge the LIVE sha.
        git -C "$d" fetch -q origin "+refs/heads/$branch:$tracking" 2>/dev/null \
            || { say "  $branch: fetch failed; kept"; return 1; }
        if ! git -C "$d" merge-base --is-ancestor "$remote_sha" "$proof" 2>/dev/null; then
            say "  $branch @ ${remote_sha:0:10} is NOT fully merged into $proof; ref KEPT (pushed after the fold's fetch?)"
            return 1
        fi
        git -C "$d" push -q origin --delete "$branch" 2>"$F/prune.log" \
            || { say "  $branch: delete on origin rejected: $(tail -1 "$F/prune.log"); kept"; return 1; }
        git -C "$d" update-ref -d "$tracking" 2>/dev/null
        say "  deleted origin's $branch @ ${remote_sha:0:10} (every commit is on $proof) and its tracking ref"
    fi

    # The local branch, last and never forced. It is not what costs a tick
    # anything -- no job walks refs/heads/lane/* -- so a refusal is logged and
    # the sweep moves on.
    if git -C "$d" rev-parse -q --verify "refs/heads/$branch" >/dev/null 2>&1; then
        if git -C "$d" branch -d "$branch" >"$F/prune.log" 2>&1; then
            say "  deleted local refs/heads/$branch"
        else
            say "  local refs/heads/$branch KEPT: $(tr -d '\n' < "$F/prune.log" | tail -c 160)"
            say "    (if that lane is finished: lane.sh rm ${branch#lane/})"
        fi
    fi
    return 0
}
if [ "$mode" = prune-branch ]; then
    prune_branch "${2:?dir}" "${3:?branch}" "${4:?proof commit}"; exit $?
fi

# --------------------------------------------------------------- the sweep
# One pass over every lane ref, for the backlog that accumulated before the
# fold job learned to clean up after itself. A dry run by default: this
# deletes refs on the shared remote, so doing it takes saying so.
if [ "$mode" = prune ]; then
    git -C "$REPO" fetch -q origin "$TIP" '+refs/heads/lane/*:refs/remotes/origin/lane/*' 2>/dev/null \
        || { say "prune: fetch failed; refusing to judge ancestry from a stale object store"; exit 1; }
    total=0; merged=0
    for ref in $(git -C "$REPO" for-each-ref --format='%(refname:short)' 'refs/remotes/origin/lane/*'); do
        branch="${ref#origin/}"; total=$((total+1))
        if ! git -C "$REPO" merge-base --is-ancestor "$ref" "refs/remotes/origin/$TIP" 2>/dev/null; then
            [ "${2:-}" = --apply ] || echo "keep       $branch (commits not yet on $TIP)"
            continue
        fi
        merged=$((merged+1))
        if [ "${2:-}" = --apply ]; then
            say "pruning $branch"
            prune_branch "$REPO" "$branch" "refs/remotes/origin/$TIP"
        else
            echo "would prune $branch @ $(git -C "$REPO" rev-parse --short "$ref") (fully merged into $TIP)"
        fi
    done
    echo "total lane refs: $total, fully merged into $TIP: $merged"
    [ "${2:-}" = --apply ] || echo "(a dry run; pass --apply to delete them)"
    exit 0
fi

# ------------------------------------ a preflight failure that is not the PR's
# `$F/failed/$pr-$head` is PERMANENT: that head is never tried again. It is the
# right record for a failure the merged tree causes, and the wrong one for
# preflight's `coverage` and `territory` gates, which read the BOARD -- both go
# through docs/testing/board_files.py, which loads from `origin/board` -- and
# not this PR's changes at all.
#
# On 2026-09-19 the board opened a `decision-needed` issue, the coverage gate
# went red for every fold, and #123, #124 and #130 -- all complete, green and
# innocent -- were each marked permanently failed on a head with nothing wrong
# with it. The board fixed its own row one tick later and the gate went green
# again, so the failure was transient BY CONSTRUCTION and only the marker
# outlived it; the three PRs folded when a person deleted the markers by hand.
#
# So: a failure in ONLY those gates is logged and retried next tick. Any other
# failed gate, alone or alongside them, still earns the marker, because a mixed
# failure contains a real one. Note that `board files` is NOT in this set
# despite its name -- it is a gate about what this checkout edited, which is
# exactly the thing a lane can cause. (It is also already answered here:
# preflight runs with --allow-tracker below, because at fold time the tree
# legitimately carries board edits.)
#
# WHICH GATE FAILED IS READ FROM THE COLUMN, NOT FROM PROSE. preflight.sh has
# no per-gate exit code -- it exits 0, 1 or 2 for the whole run -- and it is
# not this job's file to give it one. What it does have is `step()` and
# `bad()`: one line per gate, the gate's name padded to 28 columns, then `ok`
# or `FAILED` and nothing else on the line. That column IS the report. Keying
# on a line that begins with the name and ends with FAILED is also what keeps
# the gates' own indented output -- which quotes the word often enough -- from
# being read as a gate name.
BOARD_GATES="${FOLD_BOARD_GATES:-coverage territory}"
TRACKER_FILES="docs/testing/nv2a_issues.toml docs/testing/territory.toml"

preflight_failed_gates() {   # <preflight log> -> one failed gate's name per line
    sed -n 's/^\([^[:space:]].*[^[:space:]]\)[[:space:]][[:space:]]*FAILED[[:space:]]*$/\1/p' "$1" 2>/dev/null
}
preflight_board_only() {   # <preflight log> -> 0 when every failed gate is the board's
    local g gates
    gates=$(preflight_failed_gates "$1")
    # NO gate line at all is not "nothing failed", it is a log this job cannot
    # read: preflight died before the gates, or on `exit 2` for a bad argument,
    # or the run was cut off. An unreadable failure is treated as the tree's --
    # the marker, and a person, are the conservative direction.
    [ -n "$gates" ] || return 1
    while IFS= read -r g; do
        case " $BOARD_GATES " in *" $g "*) ;; *) return 1 ;; esac
    done <<< "$gates"
}
if [ "$mode" = preflight-verdict ]; then
    if preflight_board_only "${2:?preflight log}"; then echo board; else echo tree; fi
    exit 0
fi

# A board gate that stays red is no longer transient, and a PR parked in
# silence is the #102 failure again, so it is said on the PR -- once per head,
# and only after it has outlived the board's own repair time.
BOARD_GATE_STUCK_SECS="${BOARD_GATE_STUCK_SECS:-7200}"   # 4 ticks
board_gate_report() {   # <pr> <head> <gates>
    local pr=$1 head=$2 gates=$3 m="$F/failed/$1-$2-board" seen now
    now=$(date +%s)
    seen=$(awk '$1=="first"{print $2; exit}' "$m" 2>/dev/null)
    [ -n "$seen" ] || { printf 'first %s\n' "$now" >> "$m"; return; }
    [ $((now - seen)) -ge "$BOARD_GATE_STUCK_SECS" ] || return
    grep -qx said "$m" 2>/dev/null && return
    printf 'said\n' >> "$m"
    say "  #$pr: reported a stuck board gate on ${head:0:10}"
    comment "$pr" "[job.fold] Not folded, and **this is not your PR's fault**: preflight's board-side gates failed on the merged tree (\`$gates\`). Those gates read the board through \`board_files.py\` (\`origin/board\`), not your diff, so nothing you pushed caused this and nothing you push fixes it.

**Your head is not marked failed.** The fold retries it every tick and folds it as soon as the board's own row is right again; you do not need to push anything, and you do not need to re-apply \`fold-ready\`.

It has now been failing for more than $((BOARD_GATE_STUCK_SECS / 3600))h, which is far longer than the board takes to repair itself, so it wants a person: run \`python3 docs/testing/check_coverage.py\` and \`python3 docs/testing/check_territory.py\` against \`origin/master\` with \`origin/board\` fetched. This is the only comment this job will make about this head."
}

# ------------------------------------------------------------ candidates
# `labels` rides along on the one list call this job makes, and the title stays
# LAST: it is the only free-text field, and the read below gives the last
# variable everything after its own tab, so free text in any other position
# would end up inside a field a gate keys on.
cands=$(gh pr list --repo "$GH_REPO" --state open --label fold-ready --json number,title,headRefName,headRefOid,isDraft,labels \
            --jq 'sort_by(.number)[] | "\(.number)\t\(.headRefName)\t\(.headRefOid)\t\(.isDraft)\t\([.labels[].name] | join(","))\t\(.title)"' 2>/dev/null)
# NOTHING TO FOLD IS NOT NOTHING TO DO. This used to `exit 0` here, which also
# skipped the `handback.sh` tail call at the bottom of this file -- and none of
# handback's causes is the `fold-ready` label. A PR handed back carries
# `needs-rebase` and has had `fold-ready` REMOVED; a lane stranded in draft
# never had it. So the one state in which nothing folds -- every open PR is
# handed back, or waiting, or a draft nobody will touch -- was exactly the
# state in which the actor for all of them did not run either. Fall through:
# the loop below reads an empty `$cands` as zero candidates and the tail runs.
if [ -z "$cands" ]; then
    [ "$mode" = list ] && echo "nothing labelled fold-ready"
fi

ci_green() {   # <pr> -> 0 when every check on the head has concluded SUCCESS (or was skipped)
    gh pr view "$1" --repo "$GH_REPO" --json statusCheckRollup --jq '
        [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
        | if ($c | length) == 0 then "NONE"
          elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
          elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
          else "PENDING" end' 2>/dev/null
}

# --------------------------------------------- a red about a base that moved
# GITHUB DOES NOT RE-RUN A PULL REQUEST'S CHECKS WHEN THE BASE BRANCH MOVES.
# So when a REQUIRED check breaks on $TIP -- `selftest.d/86-fold-regressed.sh`
# was broken on master for most of 2026-09-19, because its fixture reused a
# `lane/foldreg` ref that prune_branch() above deletes -- every open PR that
# ran against the broken tree keeps reporting FAILURE forever, about a tree
# that no longer exists. PR #167 fixed it and the push run on `bb4b78689e`
# came back success at 19:47:52Z; #152, #153, #155 and #163 still read
# `selftest:FAILURE` from runs that started at 17:14:32Z and 18:59:47Z.
#
# NOTHING IN THE HARNESS COULD REACH THEM. The CI gate below refuses --
# correctly, on the data it has, since it cannot tell a stale red from a live
# one. `handback.sh` resumes a lane only on `needs-rebase`, and these had no
# conflict; they were MERGEABLE. `board.sh` only picks up PRs carrying no
# pipeline label, and these were labelled. So four complete, audited PRs sat
# `fold-ready` and refused every tick until a person pushed over them -- and
# that recurs EVERY time a required check breaks on the trunk.
#
# A RE-RUN DOES NOT FIX IT, AND THAT WAS MEASURED BEFORE THIS WAS WRITTEN.
# #152's failed `selftest` was re-run at 20:37:16Z, 50 minutes after the fix
# folded, and came back `failure` with the same ten checks: the workflows
# check out the PR's OWN HEAD, not `refs/pull/N/merge`, so the branch's own
# copy of the broken fragment is still the one that runs. `FR_LANE_SHA` -- the
# fix -- appears twice on master and ZERO times on all four branches. There is
# therefore deliberately NO re-run path here, and none should be added: the
# only thing that refreshes the verdict is bringing $TIP INTO the branch,
# which is the lane's work and is exactly what `handback.sh` already asks for.
# It is also why this costs no CI minutes of its own; the one run it causes is
# the one the lane's own push triggers.
#
# THE TEST IS A TIMESTAMP, AND IT CAN ONLY EVER ADD AN ACTOR. Every failing
# check's run started before the current `origin/$TIP` head was committed =>
# that verdict is about a base that has moved. If ANY failing check started
# after it, the red is live and nothing changes: the PR waits, reported
# exactly as before. A timestamp that cannot be read is LIVE too -- "I could
# not tell" is not "it is stale" -- and so is a rollup with no failing check
# in it at all.
#
# A STALE RED IS NOT LICENCE TO FOLD. Nothing here folds on this verdict. The
# head is handed back so that a FRESH verdict exists, and that fresh verdict
# is what the gate reads next tick. The gate stays; only "forever" goes.
#
# MERGEABILITY IS NOT CHECKED, ON PURPOSE, although the four PRs that prompted
# this were all MERGEABLE. This gate runs BEFORE the merge attempt, so a PR
# that is both stale-red and conflicting never reaches the conflict path
# either and has no actor for the same reason. The answer to both is the same
# base merge, so gating on MERGEABLE would have left half the jam in place and
# bought one more `gh` call for it.
#
# IT IS `needs-rebase`, NOT A NEW LABEL, AND THAT IS A DELIBERATE CHOICE.
# The label's own description is already the action -- "bring master into the
# lane branch" -- and it is the only thing a stale red needs. A new label
# would have to be added to `ensure-labels.sh`, to `board.sh`'s state-label
# set and to `fleet.py`'s, or a PR carrying only it would read as UNLABELLED
# to the board and be handed `needs-audit-1` on top of work that was already
# audited; those three files belong to three other lanes. The cause file below
# carries `action=resume_stale_ci` so `handback.sh` tells the lane the truth
# about WHY -- the red is not its defect -- rather than asking it to hunt for
# a conflict that is not there.
STALE_LABEL="${FOLD_STALE_LABEL:-needs-rebase}"

# `$TIP`'s head, read once per tick and only when a red candidate exists: a
# tick with nothing red must not pay for a fetch.
#
# THIS MAKES `list` FETCH, which nothing else in `list` did. That is the one
# thing `list` now costs, and it is deliberate: without the trunk's head there
# is no answer to give, and "CI RED" where the truth is "CI RED but STALE" is
# the wrong answer in the one report a person reads when something is jammed.
# A fetch writes refs and nothing else -- no label, no comment, no session --
# so `list` remains read-only in every sense that decides anything.
TIP_SHA=""; TIP_EPOCH=""
tip_state() {   # -> 0 with TIP_SHA and TIP_EPOCH set for origin/$TIP
    [ -n "$TIP_EPOCH" ] && return 0
    if [ -n "${FOLD_TIP_SHA:-}" ] && [ -n "${FOLD_TIP_EPOCH:-}" ]; then
        TIP_SHA="$FOLD_TIP_SHA"; TIP_EPOCH="$FOLD_TIP_EPOCH"; return 0
    fi
    # The TRACKING REF, not FETCH_HEAD. `$REPO` is the shared checkout and
    # several jobs fetch in it; FETCH_HEAD is one file they all overwrite, so
    # another job's fetch landing between this one and the read below would
    # silently hand this gate a different commit's timestamp. An explicit
    # refspec writes the ref this then reads by name.
    git -C "$REPO" fetch -q origin "+refs/heads/$TIP:refs/remotes/origin/$TIP" 2>/dev/null || return 1
    TIP_SHA=$(git -C "$REPO" rev-parse "refs/remotes/origin/$TIP" 2>/dev/null)
    TIP_EPOCH=$(git -C "$REPO" log -1 --format=%ct "refs/remotes/origin/$TIP" 2>/dev/null)
    [ -n "$TIP_SHA" ] && [ -n "$TIP_EPOCH" ]
}

# `""` IS PENDING AND `//` DOES NOT CATCH IT. `gh` prints an EMPTY conclusion
# for a run still in flight, and jq's `//` falls through only on null and
# false, so `.conclusion // .state` yields `""` and a running check would read
# as a concluded one. Tested for emptiness explicitly, in both positions.
#
# In a variable because the self-test's `gh` shim answers `pr view` directly
# and would never exercise a typo in this: the fragment pulls this line out
# and runs it through the real jq against a canned rollup.
CHECK_ROWS_JQ='.statusCheckRollup[]? | [ (.name // .context // "check"), (if (.conclusion // "") != "" then .conclusion elif (.state // "") != "" then .state else "PENDING" end), (.startedAt // .createdAt // "") ] | @tsv'
check_rows() {   # <pr> -> "<name>\t<conclusion>\t<started>", one line per check
    gh pr view "$1" --repo "$GH_REPO" --json statusCheckRollup --jq "$CHECK_ROWS_JQ" 2>/dev/null
}

# STALE_RUN is SET, not printed: `$(stale_red ...)` would run this in a
# command-substitution subshell and the caller would post a comment with an
# empty run name in it -- the trap `handback.sh`'s lane_name() documents, where
# the discarded variable IS the content of the answer.
STALE_RUN=""
stale_red() {   # <pr> <tip epoch> -> 0 when EVERY failing check predates it
    STALE_RUN=""
    local name concl started ts newest=0 failing=0
    while IFS=$'\t' read -r name concl started; do
        [ -n "$name" ] || continue
        case "$concl" in FAILURE|ERROR|CANCELLED|TIMED_OUT|STARTUP_FAILURE) ;; *) continue ;; esac
        failing=$((failing+1))
        # An EMPTY string is not an unparseable date to `date -d`: it is
        # MIDNIGHT TODAY, at exit 0. A rollup entry with no timestamp would
        # therefore read as "started today", which on most days is after the
        # trunk's head and on some days is before it. Refused by hand.
        [ -n "$started" ] || { STALE_RUN=""; return 1; }
        ts=$(date -u -d "$started" +%s 2>/dev/null) || { STALE_RUN=""; return 1; }
        [ -n "$ts" ] || { STALE_RUN=""; return 1; }
        if [ "$ts" -gt "$newest" ]; then newest=$ts; STALE_RUN="$name, started $started"; fi
    done <<< "$(check_rows "$1")"
    # No failing check at all means the rollup does not say what `ci_green`
    # said, or `gh` answered nothing. Either way this cannot judge it.
    [ "$failing" -gt 0 ] || { STALE_RUN=""; return 1; }
    [ "$newest" -lt "$2" ]
}

# THE LEDGER IS KEYED ON (PR, TRUNK HEAD). The only thing that can change this
# verdict is $TIP moving, so acting twice on one pair is acting on no new
# information -- and each action removes a label, writes a cause and starts a
# lane session. Same `$F/failed/<pr>-<head>` shape as every other record here,
# holding the trunk shas already acted on, one per line.
stale_handback() {   # <pr> <branch> <head> <run>
    local pr=$1 branch=$2 head=$3 run=$4 m="$F/failed/$1-$3-stale"
    if grep -qxF "$TIP_SHA" "$m" 2>/dev/null; then
        say "#$pr $branch: stale red already handed back at $TIP ${TIP_SHA:0:10}; waiting for the lane"
        return
    fi
    printf '%s\n' "$TIP_SHA" >> "$m"
    say "#$pr $branch: CI is RED on ${head:0:10} but its failing run ($run) predates $TIP ${TIP_SHA:0:10}; handing back for a base merge"
    mkdir -p "$WORK/handback/cause"
    # at=: UTC, like the conflict cause below -- a recorded field in a host
    # state file, never shown to anyone.
    printf 'label=%s\naction=resume_stale_ci\nbranch=%s\nhead=%s\ndetail=%s\ntip=%s\nat=%s\n' \
        "$STALE_LABEL" "$branch" "$head" "$run" "$TIP_SHA" "$(date -u '+%FT%TZ')" \
        > "$WORK/handback/cause/$pr-$head"
    label_rm "$pr" fold-ready
    label_add "$pr" "$STALE_LABEL" || say "  WARNING: could not label #$pr $STALE_LABEL"
    comment "$pr" "[job.fold] Not folded, and **the red is not yours**: **every** failing check on \`${head:0:10}\` ran **before** \`$TIP\`'s current head \`${TIP_SHA:0:10}\` was committed -- the most recent of them is \`$run\`. That verdict is about a base that has since moved, and GitHub does not re-run a PR's checks when its base moves.

Do not go looking for a defect of your own here -- re-read the failing run's date above first. Re-running it would not help either: the workflows check out this PR's own head, not \`refs/pull/$pr/merge\`, so the branch's own copy of whatever broke is still the copy that runs.

What refreshes the verdict is bringing the trunk in:

\`\`\`
git fetch origin $TIP
git merge origin/$TIP        # MERGE, never rebase -- a rebase un-ancestors
                             # any registered prediction's a_ref/b_ref.
git push
\`\`\`

Then, once CI is green on the new head, re-apply \`fold-ready\` (\`bash docs/testing/jobs/gh-label.sh add $pr fold-ready\`). \`fold-ready\` has been removed and \`$STALE_LABEL\` set so \`jobs/handback.sh\` has an actor for this; it is the label whose description is exactly this action. **This is the only comment this job will make about this head at \`${TIP_SHA:0:10}\`** -- if the trunk moves again and the red is still stale, it says so once more against the new trunk."
}

# ------------------------------------------------- reporting a stopped fold
# A fold that stops must say so ON THE PR, exactly once per head and state.
# Until 2026-09-18 only RED spoke. A head with NO run at all mapped to NONE,
# waited forever and left no trace off this host: #102 sat a full day that way,
# its only record a line in $WORK/logs/fold/tick.log that no lane can read.
# None of this folds anything -- NONE is still a gate, and folding a head
# nothing built would be the worse bug.
#
# The marker is a LEDGER of states already reported, not a boolean, because a
# NONE seen first must not silence the RED that follows it -- that would move
# the silence one state over instead of closing it. An EMPTY marker is one the
# pre-09-18 job touched, and it only ever touched it for RED.
PENDING_STUCK_SECS="${PENDING_STUCK_SECS:-7200}"   # 4 ticks; below this a pending run is just running
ci_report() {   # <pr> <head> <state>
    local pr=$1 head=$2 ci=$3 m="$F/failed/$1-$2-ci" body='' seen now
    case "$ci" in RED|NONE|PENDING) ;; *) return ;; esac
    [ -f "$m" ] && [ ! -s "$m" ] && echo RED > "$m"
    now=$(date +%s)
    if [ "$ci" = PENDING ]; then
        # A run in flight is not news; ticks are 30 minutes and the Android
        # build is long. Only a pending that outlives $PENDING_STUCK_SECS from
        # its first sighting is stuck, and only that is worth a comment.
        seen=$(awk '$1=="PENDING-seen"{print $2; exit}' "$m" 2>/dev/null)
        [ -n "$seen" ] || { printf 'PENDING-seen %s\n' "$now" >> "$m"; return; }
        [ $((now - seen)) -ge "$PENDING_STUCK_SECS" ] || return
    fi
    grep -qxF "$ci" "$m" 2>/dev/null && return
    printf '%s\n' "$ci" >> "$m"
    case "$ci" in
    RED)  body="[job.fold] Not folded: CI is red on \`${head:0:10}\`. The fold waits for a green head; push a fix and the next tick picks it up." ;;
    NONE) body="[job.fold] Not folded: **no CI run exists** on \`${head:0:10}\`. This is not a failure -- nothing has built this head at all, so the fold cannot verify it. The PR keeps its \`fold-ready\` label and keeps waiting; it will fold as soon as a green run appears, and it will not fold unverified.

The usual cause is a \`[skip ci]\` marker in the head commit's message, left over from a standing instruction that \`AGENTS.md\`'s transition note retired (CI runs on every PR now: it is free on this public repository). It is *not* a path-filter gap -- \`android.yml\` and \`desktop.yml\` both trigger on \`pull_request:\` with no \`paths:\`, so every PR gets them.

To unblock, push a new head whose message does not carry the marker:

\`\`\`
git commit --allow-empty -m 'ci: build this head' && git push
\`\`\`

**Do not quote the marker in that message.** GitHub matches it anywhere in the commit message, body included, so an empty commit that explains the problem by naming the marker suppresses the very run it was pushed to trigger. That cost a cycle on 2026-09-18." ;;
    PENDING) body="[job.fold] Not folded: CI has been **pending** on \`${head:0:10}\` for more than $((PENDING_STUCK_SECS / 3600))h -- long enough that it is stuck rather than running. The fold gate waits for a green head, so this PR is parked until it resolves.

Check \`gh pr checks $pr\`: a job queued with no runner, or held on a workflow approval, never concludes by itself. Re-run it or push a new head. This is the only comment this job will make about this head." ;;
    esac
    say "  #$pr: reported $ci on ${head:0:10}"
    comment "$pr" "$body"
}

# ------------------------------------------------ an unaccepted regression
# `regressed` is the arms job's verdict that a registered prediction FAILED on
# the device. Until 2026-09-19 the only thing enforcing it was a sentence in
# `roles/board.md` -- "a `regressed` PR is not fold-ready" -- which is prose,
# read by whichever model session decides to set `fold-ready`, and this job is
# a script that cannot read it. That day PR #102 folded as `3d072c6ea6` with
# `Color_zeta_overlap/Swap 165,447 -> 304,750` live and its `regressed` label
# set twenty minutes earlier precisely to stop the fold. It stopped nothing.
#
# THIS GATE READS THE LABEL AND DECIDES NOTHING ABOUT IT. What `regressed`
# means -- which verdicts count, which supersede which -- is arms.sh's
# (#144), and a second opinion here would be a second state machine over one
# word. So there is no verdict parsing, no `$WORK/arms` read and no "is the
# FAIL still live" judgement in this file: the label is the interface.
# Clearing it is likewise arms.sh's, from the verdicts; this job never
# touches it.
#
# IT IS NOT A REQUIREMENT TO BE `verified`. Most PRs carry no prediction at
# all and must keep folding; only the FAIL stops one.
#
# THE OVERRIDE IS THE OWNER'S, AND IT NAMES AN ISSUE. Some regressions are a
# measured trade someone accepted -- #91 exists to hold exactly the delta
# above under #88's colour-wins policy -- and a gate with no way through turns
# every such trade into a permanently unfoldable PR. `regression-accepted:<issue>`
# folds it. The number is not decoration: the issue is where the trade is
# argued, so an override without one is an assertion with no argument and is
# refused out loud, with the spelling. No job sets a label in this family and
# `ensure-labels.sh` creates no member of it (see the note there): the owner
# creates the one they mean, which is what "the owner accepted it" has to
# mean if it means anything.
has_label() {   # <labels csv> <label>
    case ",$1," in *",$2,"*) return 0 ;; esac; return 1
}
accepted_issue() {   # <labels csv> -> the issue a well-formed override names
    local l; local -a ls=()
    IFS=, read -r -a ls <<< "$1"
    for l in "${ls[@]:-}"; do
        [[ "$l" =~ ^regression-accepted:#?([0-9]+)$ ]] && { printf '%s\n' "${BASH_REMATCH[1]}"; return 0; }
    done
    return 1
}
malformed_accept() {   # <labels csv> -> an override-shaped label that names no issue
    local l; local -a ls=()
    IFS=, read -r -a ls <<< "$1"
    for l in "${ls[@]:-}"; do
        case "$l" in regression-accepted*) accepted_issue "$l" >/dev/null || { printf '%s\n' "$l"; return 0; } ;; esac
    done
    return 1
}

# Said on the PR, once per head AND per state -- a ledger, like ci_report's,
# for the same reason: an owner who adds a malformed override after the first
# comment has acted and must be answered, and a boolean would swallow that
# answer. Parking a PR in silence is the #102 failure wearing the other face.
regressed_report() {   # <pr> <head> <labels>
    local pr=$1 head=$2 labels=$3 m="$F/failed/$1-$2-regressed" state=REGRESSED body bad=''
    bad=$(malformed_accept "$labels") && state=ACCEPT-MALFORMED
    grep -qxF "$state" "$m" 2>/dev/null && return
    printf '%s\n' "$state" >> "$m"
    case "$state" in
    REGRESSED) body="[job.fold] Not folded: this PR is labelled \`regressed\` -- the arms job judged a registered prediction **FAILED** on the device. Folding it would put a measured regression on \`$TIP\`, which is how \`3d072c6ea6\` landed on 2026-09-19.

**Your \`fold-ready\` label is kept and your head is not marked failed.** This gate removes nothing and writes off nothing: the fold re-tries every tick and folds the moment the label clears, so there is nothing to re-apply.

Two ways forward, and both are decisions rather than chores:

- **Fix it.** Push the fix and re-register the prediction. The arms job re-judges and clears \`regressed\` itself -- it is computed from the verdicts, so do not remove it by hand; that would clear the label without clearing the regression.
- **Accept it.** If the regression is a measured trade that someone owns, the **owner** adds a \`regression-accepted:<issue>\` label naming the issue where that trade is argued -- e.g. \`regression-accepted:91\` for the \`Color_zeta_overlap\` trade under #88's colour-wins policy. A lane must not set it and no job sets it.

This is the only comment this job will make about this head." ;;
    ACCEPT-MALFORMED) body="[job.fold] Still not folded, and this one is a spelling: the PR carries \`$bad\`, which is override-shaped but names no issue, so the \`regressed\` gate does not take it.

The override is \`regression-accepted:<issue>\` -- the issue number is the point of it. An accepted regression is a trade, the issue is where the trade is argued, and an override with no issue is an assertion with no argument; a year from now the label is all that is left to read. For the \`Color_zeta_overlap\` trade that is #91:

\`\`\`
gh label create regression-accepted:91 --repo $GH_REPO --color b60205 \\
    --description 'owner: the regression on this PR is the trade argued on #91'
bash docs/testing/jobs/gh-label.sh add $pr regression-accepted:91
\`\`\`

Remove \`$bad\` when you add it. This is the only comment this job will make about that." ;;
    esac
    say "  #$pr: reported $state on ${head:0:10}"
    comment "$pr" "$body"
}

folded=0
while IFS=$'\t' read -r pr branch head draft labels title; do
    [ -n "$pr" ] || continue
    if [ "$draft" = true ]; then
        say "#$pr is a draft: not folding; label removed"
        [ "$mode" = list ] && { echo "#$pr $branch: DRAFT"; continue; }
        label_rm "$pr" fold-ready || say "  WARNING: could not remove fold-ready from #$pr; it will be re-tried every tick"
        comment "$pr" "[job.fold] Not folded: the PR is still a draft. Mark it ready (\`gh pr ready $pr\`) and re-apply \`fold-ready\`."
        continue
    fi
    # The regression gate, before the CI call: it costs nothing (the labels
    # came with the candidate list) and a PR stopped here needs no `pr view`.
    # `accepted` is an override that is actually overriding something: a
    # stray `regression-accepted:` on a PR with no verdict accepts nothing,
    # and must not make the fold comment announce a regression there is no
    # record of.
    accepted=""
    if has_label "$labels" regressed; then
        accepted=$(accepted_issue "$labels") || accepted=""
        if [ -z "$accepted" ]; then
            # `list` stays read-only here: the state it would report is on the
            # PR already, as the label it is reading.
            [ "$mode" = list ] && { echo "#$pr $branch: REGRESSED (a registered prediction FAILED; the owner may accept it with regression-accepted:<issue>)"; continue; }
            say "#$pr $branch: labelled regressed and not accepted; not folding (fold-ready kept)"
            regressed_report "$pr" "$head" "$labels"
            continue
        fi
    fi
    ci=$(ci_green "$pr")
    if [ "$ci" != GREEN ]; then
        # A RED whose every failing run predates the trunk's head is a verdict
        # about a base that has moved: the one state this job used to refuse
        # forever. Handed back for a base merge; never folded on.
        if [ "$ci" = RED ] && tip_state && stale_red "$pr" "$TIP_EPOCH"; then
            [ "$mode" = list ] && { echo "#$pr $branch: CI RED but STALE ($STALE_RUN predates $TIP ${TIP_SHA:0:10})"; continue; }
            stale_handback "$pr" "$branch" "$head" "$STALE_RUN"
            continue
        fi
        [ "$mode" = list ] && echo "#$pr $branch: CI $ci"
        say "#$pr $branch: CI is $ci on $head; waiting"
        ci_report "$pr" "$head" "$ci"
        continue
    fi
    if [ -f "$F/failed/$pr-$head" ]; then
        [ "$mode" = list ] && echo "#$pr $branch: failed before on this head ($(cat "$F/failed/$pr-$head"))"
        continue
    fi
    if [ "$mode" = list ]; then echo "#$pr $branch @ ${head:0:10}: WOULD FOLD${accepted:+ (regression accepted on #$accepted)}"; continue; fi
    [ "$folded" -eq 0 ] || { say "#$pr waits: one fold per tick"; continue; }

    # ---------------------------------------------------------- the fold
    say "folding #$pr $branch @ ${head:0:10}: $title"
    [ -n "$accepted" ] && say "  it is labelled regressed; folding on regression-accepted:#$accepted"
    if [ ! -e "$WT/.git" ]; then
        git -C "$REPO" fetch -q origin "$TIP" && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD || { say "cannot create $WT"; exit 1; }
    fi
    git -C "$WT" fetch -q origin "$TIP" "$branch" || { say "fetch failed"; continue; }
    git -C "$WT" reset -q --hard && git -C "$WT" clean -qfd && git -C "$WT" checkout -q --detach "origin/$TIP"
    notes_moved=""
    if ! git -C "$WT" merge --no-ff --no-edit -m "fold: PR #$pr $branch -- $title" "origin/$branch" >"$F/merge.log" 2>&1; then
        files=$(git -C "$WT" diff --name-only --diff-filter=U | tr '\n' ' ')
        if resolve_root_notes "$WT" "$branch"; then
            notes_moved=$(notes_path "$branch")
            git -C "$WT" commit -q -m "fold: PR #$pr $branch -- $title" \
                -m "The lane's root NOTES.md conflicted with master's and nothing else did; its copy is at $notes_moved (roles/lane.md item 3). No content was merged or dropped." \
                || { git -C "$WT" merge --abort 2>/dev/null; say "#$pr NOTES.md resolved but the merge would not commit"; continue; }
            say "  only root NOTES.md conflicted; the lane's copy is at $notes_moved"
        else
            git -C "$WT" merge --abort 2>/dev/null
            say "#$pr CONFLICT in: $files"
            # RECORD THE CAUSE; DO NOT ACT ON IT. `needs-rebase` was set by this
            # job, shown by status.sh, and acted on by nothing -- the lane it hands
            # the PR back to is a transient unit that exited with its session. The
            # actor is jobs/handback.sh, called at the end of this tick. This job
            # knows the conflicting files and nothing downstream does, so it writes
            # them down here; handback.sh works without the file (a PR labelled by
            # hand, or by a fold from before this line existed) and quotes it when
            # it is there. Keyed on the head sha, so a lane that pushes produces a
            # new cause and an unchanged branch does not.
            mkdir -p "$WORK/handback/cause"
            # at=: UTC. A recorded field in a host state file, like queued_utc
            # -- handback.sh reads only files= from here and never shows this
            # line to anyone, so it stays in the zone the records are kept in.
            printf 'label=needs-rebase\nbranch=%s\nhead=%s\nfiles=%s\nat=%s\n' \
                "$branch" "$head" "$files" "$(date -u '+%FT%TZ')" > "$WORK/handback/cause/$pr-$head"
            label_rm "$pr" fold-ready; label_add "$pr" needs-rebase || say "  WARNING: could not label #$pr needs-rebase"
            comment "$pr" "[job.fold] Not folded: merging \`$branch\` into \`$TIP\` conflicts in: \`$files\`. The fold job resolves nothing (a merge it does not understand is how a fix was reverted on 09-12). Merge \`origin/$TIP\` into the lane branch, resolve there, push, then re-apply \`fold-ready\`."
            continue
        fi
    fi
    # The index: regenerate if the merge moved it, never hand-merge it.
    if [ -n "$TESTS" ] && [ -n "$SUPPORT" ]; then
        if ! (cd "$WT" && python3 docs/testing/nv2a_index.py check --tests "$TESTS" --support "$SUPPORT" >"$F/index.log" 2>&1); then
            say "  index stale after merge; regenerating"
            (cd "$WT" && python3 docs/testing/nv2a_index.py build --tests "$TESTS" --support "$SUPPORT" >>"$F/index.log" 2>&1) \
                && git -C "$WT" add docs/testing/nv2a_index.json \
                && git -C "$WT" commit -q -m "nv2a index: regenerate after folding #$pr" \
                || { echo "index regeneration failed" > "$F/failed/$pr-$head"; say "  index regeneration FAILED"; comment "$pr" "[job.fold] Not folded: the nv2a index did not regenerate cleanly after the merge (see the host's \$WORK/fold/index.log). Needs a person."; continue; }
        fi
    else
        say "  note: test sources not found on this host; index gate skipped (CI runs it on master)"
    fi
    # The fast local gates. The tracker gate is the board's, not this PR's.
    if ! (cd "$WT" && bash docs/testing/preflight.sh --allow-tracker >"$F/preflight.log" 2>&1); then
        gates=$(preflight_failed_gates "$F/preflight.log" | tr '\n' ' '); gates="${gates% }"
        # The second half of "the PR's own tree cannot cause it": board_files
        # PREFERS `origin/board` and FALLS BACK to the worktree copy, so for as
        # long as that transition lasts a PR that edits those two files could
        # in fact fail these gates by itself. It is barred from editing them
        # and --allow-tracker has already stopped asking -- so ask here, where
        # the answer decides whether a head is written off forever.
        if preflight_board_only "$F/preflight.log" \
           && [ -z "$(git -C "$WT" diff --name-only "origin/$TIP...origin/$branch" -- $TRACKER_FILES 2>/dev/null)" ]; then
            say "  preflight: only the board's own gates failed ($gates); NOT marking this head, retrying next tick"
            board_gate_report "$pr" "$head" "$gates"
            continue
        fi
        echo "preflight failed${gates:+: $gates}" > "$F/failed/$pr-$head"
        say "  preflight FAILED: $(grep -m3 FAILED "$F/preflight.log" | tr '\n' ' ')"
        comment "$pr" "[job.fold] Not folded: preflight fails on the merged tree:
\`\`\`
$(grep -B1 -A3 FAILED "$F/preflight.log" | head -30)
\`\`\`
Fix on the lane branch and push; the next green head is re-tried."
        continue
    fi
    if ! git -C "$WT" push -q origin "HEAD:$TIP" 2>"$F/push.log"; then
        say "  push to $TIP rejected (it moved?): $(tail -1 "$F/push.log"); next tick retries"
        continue
    fi
    merge_sha=$(git -C "$WT" rev-parse --short HEAD)
    git -C "$REPO" fetch -q origin "$TIP" 2>/dev/null
    label_rm "$pr" fold-ready; label_add "$pr" folded || say "  WARNING: #$pr is folded but could not be labelled folded; remove fold-ready by hand or the next tick folds it again"
    comment "$pr" "[job.fold] Folded as \`$merge_sha\` on \`$TIP\` (--no-ff; every commit keeps its sha, so registered refs stay bound). CI now runs on $TIP; the arms job picks up any prediction this PR carries.${accepted:+

This PR is labelled \`regressed\`, and it folded **because the regression is accepted on #$accepted** -- a \`regression-accepted\` label naming that issue -- and not because the gate missed it. The failing verdict above stands as measured; #$accepted is where the trade it is part of is argued.}${notes_moved:+

Your branch's root \`NOTES.md\` conflicted with the one already on \`$TIP\` and nothing else did, so it was moved to \`$notes_moved\` rather than merged -- both lanes' records are on $TIP, each at its own path. That is where \`roles/lane.md\` item 3 now asks for it; write it there next time and no fold has to touch it.}"
    say "  folded #$pr as $merge_sha"
    # HEAD is the commit the push above just put on $TIP, so it IS the trunk's
    # tip -- a stronger proof than origin/$TIP, which is one fetch stale here.
    # Only reached after that push succeeded: a branch deleted on a fold that
    # failed to push is work destroyed.
    prune_branch "$WT" "$branch" HEAD
    folded=1
done <<< "$cands"

# The handed-back PRs get their actor, on this tick's timer. It is a separate
# script on purpose: THIS job merges and must never start a model session, and
# a job that starts model sessions has a cap, an attempt counter and an
# escalation policy that have nothing to do with merging. `$mode` is passed
# through so `fold.sh list` stays read-only and resumes nobody.
[ -f "$T/jobs/handback.sh" ] && bash "$T/jobs/handback.sh" "$mode" >/dev/null 2>&1
[ -x "$T/jobs/status.sh" ] && bash "$T/jobs/status.sh" >/dev/null 2>&1
exit 0
