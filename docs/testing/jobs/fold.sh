#!/usr/bin/env bash
#
# The fold job. Runs from hakux-fold.timer every 30 minutes; a script, no
# model session.
#
#   fold.sh          repair or hand back every conflicting PR in the pipeline,
#                    then fold up to FOLD_MAX_PER_TICK fold-ready PRs whose CI
#                    is green and whose files are disjoint
#   fold.sh list     what it would do, and why the rest waits
#   fold.sh prune    what the one-time sweep WOULD delete (a dry run)
#   fold.sh prune --apply
#                    sweep every lane ref already fully merged into the trunk
#   fold.sh resolve-notes <worktree> <branch>
#                    the one conflict resolution below, on an in-progress
#                    merge, so the self-test can run it without a fake gh
#   fold.sh resolve-index <worktree>
#                    the index-only resolution, the same way and for the same
#                    reason; its refusal reason goes to stderr
#   fold.sh regen-index <worktree> [pr]
#                    the index gate over the pinned trees, on a committed merge
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
# detached. Up to three folds per tick, and only of PRs whose files are
# disjoint -- see "more than one fold per tick" below for why, and for what
# happens when master's CI goes red after such a tick.
#
# WHAT MAKES A PR FOLD-READY is the label, and the label is set by the
# auditor (pass 2 clean) or by the board (a docs/NOTES-only PR needs no
# audit). This job checks what the label cannot: the PR is not a draft, it
# does not carry an unaccepted `regressed` verdict, its head's CI is green,
# and the merge applies without conflict. A conflict is never resolved here
# -- the lane gets `needs-rebase` and a comment naming the files, because a
# merge resolved by a script that does not understand the code is how a
# working fix was reverted on 2026-09-12. The two exceptions below, a root
# NOTES.md and the generated index, are the ones with no content to decide.
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
# test sources and committed on top, in the same push. And when that file is
# the ONLY conflict, master's copy is staged and the same rebuild replaces it:
# a derived file has no content to decide. The test sources are the ones CI
# checks against, pinned (see resolve_index_only), never the host's live
# checkouts. Anything the rebuild cannot vouch for goes back to the lane.
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

hand_back() {   # <pr> <branch> <head> <files> -> the lane's PR labelled needs-rebase, its cause recorded
    local pr=$1 branch=$2 head=$3 files=$4
    mkdir -p "$WORK/handback/cause"
    # at=: UTC. A recorded field in a host state file, like queued_utc
    # -- handback.sh reads only files= from here and never shows this
    # line to anyone, so it stays in the zone the records are kept in.
    printf 'label=needs-rebase\nbranch=%s\nhead=%s\nfiles=%s\nat=%s\n' \
        "$branch" "$head" "$files" "$(date -u '+%FT%TZ')" > "$WORK/handback/cause/$pr-$head"
    label_rm "$pr" fold-ready; label_add "$pr" needs-rebase || say "  WARNING: could not label #$pr needs-rebase"
    T_HANDED+=("#$pr")
}

# ------------------------------------------ the second: the generated index
# Every PR that moves a line under hw/ regenerates nv2a_index.json, which
# records a line number per register site. So each fold of one such PR left
# every other open hw PR conflicting with master in that file alone, and each
# went back to its lane for a resolution that is pure mechanism (2026-09-25:
# #234, #235, #237 in one hour, four lane sessions). When the index is the
# WHOLE conflict, master's copy is staged and the index gate below rebuilds it
# over the merged tree. That is not a content decision: the file is derived,
# and the derivation is rerun rather than either side's copy being trusted.
#
# BUT ONLY OVER THE TREES CI CHECKS IT AGAINST. CI regenerates nothing; it
# checks the index against nxdk_pgraph_tests at the index's own
# provenance.tests_commit and pbkitplusplus at PBKIT_SHA in the workflow. A
# rebuild over whatever the host's checkouts hold can drop a suite while
# fixing line numbers, or turn master's CI red. So the rebuild runs in
# detached worktrees of the host checkouts at exactly those commits, under
# $WORK/fold-pins/, and a commit that is not here is a hand-back, never a
# fetch of something else. Two sides naming different tests_commits is a
# refresh somebody chose: also a hand-back.
INDEX=docs/testing/nv2a_index.json
PINS="$WORK/fold-pins"
index_json() {   # <wt> <rev|:stage> <python expr over d> -> its value, "" when absent or unreadable
    git -C "$1" show "$2:$INDEX" 2>/dev/null | python3 -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: sys.exit(0)
print(eval(sys.argv[1]) or "")' "$3" 2>/dev/null
}
tests_commit_of() { index_json "$1" "$2" '(d.get("provenance") or {}).get("tests_commit")'; }
suites_of()       { index_json "$1" "$2" 'str(len(d.get("suites") or {}))'; }
pbkit_pin() {   # <wt> -> PBKIT_SHA as the nv2a-index workflow pins it; "" unless exactly one
    local s; s=$(grep -oE 'PBKIT_SHA: *[0-9a-f]{40}' "$1/.github/workflows/nv2a-index.yml" 2>/dev/null \
                 | grep -oE '[0-9a-f]{40}' | sort -u)
    [ "$(printf '%s\n' "$s" | grep -c .)" = 1 ] && echo "$s"
}
pin_one() {   # <host checkout> <name> <sha> -> 0 with $PINS/<name> clean and detached at <sha>
    local src=$1 dst="$PINS/$2" sha=$3
    [[ "$sha" =~ ^[0-9a-f]{40}$ ]] || { WHY="no pinned $2 commit to rebuild over (got '${sha}')"; return 1; }
    [ -n "$src" ] && git -C "$src" rev-parse --git-dir >/dev/null 2>&1 \
        || { WHY="no host checkout of $2 to pin from"; return 1; }
    git -C "$src" cat-file -e "$sha^{commit}" 2>/dev/null \
        || { WHY="$2 @ ${sha:0:12} is not in $src; this job does not fetch a substitute"; return 1; }
    # Refresh in place when the pin moved; recreate when that fails (the
    # worktree belongs to another checkout, or was half-deleted).
    if ! { [ -e "$dst/.git" ] && git -C "$dst" checkout -q -f --detach "$sha" 2>/dev/null; }; then
        rm -rf "$dst"; git -C "$src" worktree prune 2>/dev/null; mkdir -p "$PINS"
        git -C "$src" worktree add -q --detach "$dst" "$sha" >/dev/null 2>&1 \
            || { WHY="could not create the $2 pin at $dst"; return 1; }
    fi
    git -C "$dst" clean -qfdx 2>/dev/null
    [ "$(git -C "$dst" rev-parse HEAD 2>/dev/null)" = "$sha" ] && [ -z "$(git -C "$dst" status --porcelain 2>/dev/null)" ] \
        || { WHY="the $2 pin at $dst is not clean at ${sha:0:12}"; return 1; }
}
pin_trees() {   # <wt> <tests_commit> -> 0 with PIN_TESTS/PIN_SUPPORT set
    PIN_TESTS=""; PIN_SUPPORT=""
    local pb; pb=$(pbkit_pin "$1")
    [ -n "$pb" ] || { WHY="no single PBKIT_SHA in .github/workflows/nv2a-index.yml"; return 1; }
    pin_one "$TESTS" nxdk_pgraph_tests "$2" && pin_one "$SUPPORT" pbkitplusplus "$pb" || return 1
    PIN_TESTS="$PINS/nxdk_pgraph_tests"; PIN_SUPPORT="$PINS/pbkitplusplus"
}
resolve_index_only() {   # <worktree> -> 0 when the merge is left fully staged with master's index
    local wt="$1" ours theirs
    WHY=""
    # ONLY the index. One unmerged path, and that path exactly.
    [ "$(git -C "$wt" diff --name-only --diff-filter=U)" = "$INDEX" ] || return 1
    ours=$(tests_commit_of "$wt" :2); theirs=$(tests_commit_of "$wt" :3)
    [ -n "$ours" ] && [ -n "$theirs" ] \
        || { WHY="a side of the index conflict names no provenance.tests_commit"; return 1; }
    [ "$ours" = "$theirs" ] \
        || { WHY="master's index is built from tests ${ours:0:12}, the branch's from ${theirs:0:12}; which one is a decision"; return 1; }
    pin_trees "$wt" "$ours" || return 1
    # The worktree is detached at origin/$TIP, so master's side is --ours.
    git -C "$wt" checkout --ours -- "$INDEX" && git -C "$wt" add -- "$INDEX" || { WHY="could not stage master's index"; return 1; }
    [ -z "$(git -C "$wt" diff --name-only --diff-filter=U)" ] || return 1
}
regen_index() {   # <wt> <pr> [commit message] -> 0 index checks (committed on top if rebuilt); 2 cannot pin; 1 refused
    local wt=$1 pr=$2 msg="${3:-nv2a index: regenerate after folding #$2}" tc have n p
    WHY=""
    git -C "$wt" cat-file -e "HEAD:$INDEX" 2>/dev/null || { WHY="no $INDEX in the merged tree"; return 2; }
    tc=$(tests_commit_of "$wt" HEAD)
    pin_trees "$wt" "$tc" || return 2
    (cd "$wt" && python3 "$INDEX_PY" check --tests "$PIN_TESTS" --support "$PIN_SUPPORT" >"$F/index.log" 2>&1) && return 0
    say "  index stale after merge; regenerating over tests ${tc:0:12}, pbkitplusplus $(git -C "$PIN_SUPPORT" rev-parse --short=12 HEAD)"
    (cd "$wt" && python3 "$INDEX_PY" build --tests "$PIN_TESTS" --support "$PIN_SUPPORT" >>"$F/index.log" 2>&1) \
        || { WHY="the rebuild failed"; return 1; }
    (cd "$wt" && python3 "$INDEX_PY" check --tests "$PIN_TESTS" --support "$PIN_SUPPORT" >>"$F/index.log" 2>&1) \
        || { WHY="the rebuilt index does not check"; return 1; }
    have=$(python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get("suites") or {}))' "$wt/$INDEX" 2>/dev/null)
    [ -n "$have" ] || { WHY="the rebuilt index does not parse"; return 1; }
    for p in HEAD^1 HEAD^2; do
        n=$(suites_of "$wt" "$p"); [ -n "$n" ] || continue
        [ "$have" -ge "$n" ] || { WHY="the rebuilt index has $have suites, $p's has $n"; return 1; }
    done
    git -C "$wt" add -- "$INDEX" && git -C "$wt" commit -q -m "$msg" \
        || { WHY="the rebuilt index would not commit"; return 1; }
}
INDEX_PY=docs/testing/nv2a_index.py
if [ "$mode" = resolve-index ]; then
    resolve_index_only "${2:?worktree}"; rc=$?; [ -n "$WHY" ] && echo "refused: $WHY" >&2; exit $rc
fi
if [ "$mode" = regen-index ]; then
    regen_index "${2:?worktree}" "${3:-0}"; rc=$?; [ -n "$WHY" ] && echo "refused: $WHY" >&2; exit $rc
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

# ------------------------------------------------ what this tick did, in one place
# Every tick ends with ONE summary line in tick.log naming each PR it touched
# and what became of it: repaired, folded, handed back, or waiting and on
# what. The per-PR lines above it stay; this is the line a person reads first.
T_REPAIRED=(); T_FOLDED=(); T_HANDED=(); T_WAITING=()
tick_summary() {
    local j; j() { local IFS=' '; printf '%s' "${*:-none}"; }
    say "tick: repaired $(j "${T_REPAIRED[@]}"); folded $(j "${T_FOLDED[@]}"); handed back $(j "${T_HANDED[@]}"); waiting $(j "${T_WAITING[@]}")"
}

# ------------------------------------------ a conflict is not a CI wait
# GITHUB RUNS NO CI ON A PULL REQUEST THAT DOES NOT MERGE. So the CI gate below
# read a conflicting PR as `NONE`, logged "CI is NONE on <sha>; waiting" every
# tick and waited forever: the conflict path is only reached after a GREEN.
# On 2026-09-26 four PRs holding the hot pgraph files -- #268 (psh.c), #321
# (vsh-ff.c, geom.c), #330 (pgraph.c), #332 (vk/draw.c) -- conflicted with
# master in the generated index and nothing else, and every issue that needed
# one of those files waited behind them: 31 dispatchable issues, 4 lanes
# running. The host repaired all four by hand in five minutes. This is that
# repair, as the first thing every tick does.
#
# IT COVERS THE WHOLE PIPELINE, NOT ONLY fold-ready. A lane holds its files
# until its PR folds, so a PR in audit that conflicts holds them exactly as
# long as a fold-ready one does. Every open, non-draft PR carrying one of
# $PIPELINE_LABELS is asked.
#
# WHETHER IT CONFLICTS is GitHub's `mergeable` (the list API says UNKNOWN until
# something asks, so an UNKNOWN is asked again per PR) and WHERE is `git
# merge-tree` against a fresh fetch of the trunk. merge-tree has the last word:
# a CONFLICTING that merge-tree reads clean is a stale answer, and waits.
#
#   the index alone      repaired ON THE LANE BRANCH: master merged in, the
#                        index resolved and regenerated over the pins exactly
#                        as a fold does, then a fast-forward push. Refused
#                        when the lane's unit is running (it will do this
#                        itself), when its branch moved during the repair,
#                        and wherever the resolver refuses -- two
#                        tests_commits, no pins. A MERGE, never a rebase: the
#                        lane's commits keep their shas, so every registered
#                        prediction's refs stay ancestors.
#   anything else        handed back THIS tick: needs-rebase, the cause file
#                        naming the files, and handback.sh -- called at the
#                        end of this tick -- resumes the lane with them. A lane
#                        that has spent its attempts is not resumed into a
#                        refusal; the PR gets a decision-needed comment.
#
# Each PR is acted on once per head: a lane that pushes produces a new head
# and a new answer, an unchanged branch does not produce a second comment.
PIPELINE_LABELS="fold-ready needs-audit-1 needs-audit-2 needs-rebase"
LANE_MAX_ATTEMPTS="${LANE_MAX_ATTEMPTS:-$(sed -n 's/^LANE_MAX_ATTEMPTS=\([0-9][0-9]*\).*/\1/p' "$(dirname "${BASH_SOURCE[0]}")/models.env" 2>/dev/null)}"
LANE_MAX_ATTEMPTS="${LANE_MAX_ATTEMPTS:-4}"

CX_TIP=""
cx_tip() {   # -> 0 with CX_TIP the trunk head on a fresh fetch, once per tick
    [ -n "$CX_TIP" ] && return 0
    git -C "$REPO" fetch -q origin "+refs/heads/$TIP:refs/remotes/origin/$TIP" 2>/dev/null || return 1
    CX_TIP=$(git -C "$REPO" rev-parse -q --verify "refs/remotes/origin/$TIP^{commit}" 2>/dev/null)
    [ -n "$CX_TIP" ]
}
CX_FILES=""
merge_conflicts() {   # <branch> <head> -> 0 clean; 1 conflict, CX_FILES "a b "; 2 cannot tell
    CX_FILES=""
    cx_tip || return 2
    git -C "$REPO" cat-file -e "$2^{commit}" 2>/dev/null \
        || git -C "$REPO" fetch -q origin "+refs/heads/$1:refs/remotes/origin/$1" 2>/dev/null
    git -C "$REPO" cat-file -e "$2^{commit}" 2>/dev/null || return 2
    local out rc
    out=$(git -C "$REPO" merge-tree --write-tree --name-only --no-messages "$CX_TIP" "$2" 2>/dev/null); rc=$?
    case $rc in
    0) return 0 ;;
    1) CX_FILES=$(printf '%s\n' "$out" | sed 1d | grep . | sort -u | tr '\n' ' ')
       [ -n "$CX_FILES" ] && return 1 ;;
    esac
    return 2
}
lane_of() {   # <branch> -> the lane name, for lane/<name> with no further slash
    local b="${1#lane/}"
    [ "$b" != "$1" ] && [[ "$b" =~ ^[A-Za-z0-9._-]+$ ]] && printf '%s\n' "$b"
}
unit_active() { systemctl --user is-active --quiet "hakux-lane-$1" 2>/dev/null; }

REPAIRED_SHA=""
repair_index_conflict() {   # <pr> <branch> <head> -> 0 pushed; 1 refused, hand it back; 3 wait (WHY either way)
    local pr=$1 branch=$2 head=$3 name live rc pins
    WHY=""; REPAIRED_SHA=""
    # A lane/<name> branch has a unit to check; a claude/* cloud branch has
    # none on this host, and the fast-forward-only push below is what keeps a
    # session pushing to it at the same moment from losing anything.
    name=""
    case "$branch" in
        lane/*)   name=$(lane_of "$branch") || { WHY="\`$branch\` has a slash inside the lane name; no unit \`hakux-lane-<name>\` can be checked for it"; return 1; } ;;
        claude/*) ;;
        *)        WHY="\`$branch\` is neither lane/* nor claude/*"; return 1 ;;
    esac
    if is_remote_branch "$branch" 2>/dev/null; then
        WHY="\`$branch\` is a remote lane's branch; a session this host cannot see pushes to it"; return 1
    fi
    [ -n "$name" ] && unit_active "$name" && { WHY="lane.$name's unit is running; it brings $TIP in itself"; return 3; }
    if [ ! -e "$WT/.git" ]; then
        git -C "$REPO" fetch -q origin "$TIP" && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD \
            || { WHY="cannot create $WT"; return 3; }
    fi
    git -C "$WT" fetch -q origin "+refs/heads/$TIP:refs/remotes/origin/$TIP" "+refs/heads/$branch:refs/remotes/origin/$branch" 2>/dev/null \
        || { WHY="fetch failed"; return 3; }
    live=$(git -C "$WT" rev-parse -q --verify "refs/remotes/origin/$branch^{commit}" 2>/dev/null)
    [ "$live" = "$head" ] || { WHY="$branch moved (${head:0:10} -> ${live:0:10}) since the PR was read"; return 3; }
    git -C "$WT" reset -q --hard && git -C "$WT" clean -qfd && git -C "$WT" checkout -q --detach "refs/remotes/origin/$TIP" \
        || { WHY="cannot reset $WT"; return 3; }
    # 1. the trunk's tree, with the lane merged into it and nothing committed
    if git -C "$WT" merge --no-ff --no-commit "$head" >"$F/repair.log" 2>&1; then
        git -C "$WT" merge --abort 2>/dev/null
        WHY="it merges cleanly into $TIP now"; return 3
    fi
    # 2. the resolver the fold uses, unchanged: master's index staged
    if ! resolve_index_only "$WT"; then
        live=$(git -C "$WT" diff --name-only --diff-filter=U | tr '\n' ' ')
        [ -n "$WHY" ] || WHY="the conflict is not the index alone: $live"
        git -C "$WT" merge --abort 2>/dev/null; return 1
    fi
    pins="nxdk_pgraph_tests @ $(git -C "$PIN_TESTS" rev-parse --short=12 HEAD) and pbkitplusplus @ $(git -C "$PIN_SUPPORT" rev-parse --short=12 HEAD)"
    git -C "$WT" commit -q -m "Merge $TIP into $branch: only $INDEX conflicted (fold job)" \
        -m "The fold job's repair of PR #$pr: $TIP's copy of the index was taken and is regenerated over $pins in the next commit if it is stale. Nothing in it was hand-merged, and nothing else conflicted." \
        || { git -C "$WT" merge --abort 2>/dev/null; WHY="the resolved merge would not commit"; return 1; }
    # 3 and 4. regenerate over the pins; regen_index runs the check itself
    regen_index "$WT" "$pr" "nv2a index: regenerate after merging $TIP into $branch (#$pr)"; rc=$?
    [ "$rc" = 0 ] || { WHY="the index did not regenerate: $WHY"; return 1; }
    # 5. the lane's head is an ancestor, and origin still holds it
    git -C "$WT" merge-base --is-ancestor "$head" HEAD \
        || { WHY="the repaired commit does not descend from ${head:0:10}"; return 1; }
    live=$(git -C "$WT" ls-remote origin "refs/heads/$branch" 2>/dev/null | cut -f1)
    [ "$live" = "$head" ] || { WHY="$branch moved during the repair (now ${live:0:10})"; return 3; }
    [ -n "$name" ] && unit_active "$name" && { WHY="lane.$name's unit started during the repair"; return 3; }
    # Never forced: a push that is not a fast-forward of $head is rejected by
    # origin, which is the last guard against a lane that pushed just now.
    git -C "$WT" push -q origin "HEAD:refs/heads/$branch" 2>"$F/push.log" \
        || { WHY="push rejected: $(tail -1 "$F/push.log")"; return 3; }
    REPAIRED_SHA=$(git -C "$WT" rev-parse HEAD)
    REPAIR_PINS="$pins"
}

conflict_handback() {   # <pr> <branch> <head> <files> [why]
    local pr=$1 branch=$2 head=$3 files=$4 why="${5:-}" m="$F/failed/$1-$3-conflict" name n
    if [ -f "$m" ]; then
        T_WAITING+=("#$pr(handed-back:lane)"); return 0
    fi
    name=$(lane_of "$branch"); n=0
    [ -n "$name" ] && n=$(cat "$WORK/attempts/$name" 2>/dev/null || echo 0)
    [[ "$n" =~ ^[0-9]+$ ]] || n=0
    if [ -n "$name" ] && [ "$n" -ge "$LANE_MAX_ATTEMPTS" ]; then
        echo "decision-needed $CX_TIP" > "$m"
        say "#$pr $branch: CONFLICT in $files; lane.$name has used $n of $LANE_MAX_ATTEMPTS attempts, so decision-needed, not handed back"
        T_WAITING+=("#$pr(decision-needed)")
        comment "$pr" "[job.fold] decision-needed: merging \`$branch\` into \`$TIP\` at \`${CX_TIP:0:10}\` conflicts in \`$files\`${why:+ ($why)}, and lane \`$name\` has used $n of its $LANE_MAX_ATTEMPTS attempts, so a resume would be refused. The owner decides whether to reset its attempts (\`lane.sh reset $name\`) or resolve this by hand. This is the only comment this job will make about this head."
        return 0
    fi
    echo "handed-back $CX_TIP" > "$m"
    say "#$pr $branch: CONFLICT in $files${why:+($why)}; handed back this tick"
    hand_back "$pr" "$branch" "$head" "$files"
    comment "$pr" "[job.fold] Not folded: merging \`$branch\` into \`$TIP\` at \`${CX_TIP:0:10}\` conflicts in: \`$files\`${why:+ -- $why}. GitHub runs no CI on a PR that does not merge, so this would otherwise wait on \`CI NONE\` forever. The fold job resolves only the generated index; this needs the lane. Merge \`origin/$TIP\` into the lane branch (merge, never rebase), resolve, push, then re-apply \`fold-ready\` if this PR had it (an audit label was left in place)."
}

declare -A CX_SEEN=()   # PRs the conflict pass answered for this tick; the CI gate skips them
conflict_pass() {
    local rows pr branch head draft mg labels rc l inpipe
    rows=$(gh pr list --repo "$GH_REPO" --state open --limit 200 --json number,headRefName,headRefOid,isDraft,mergeable,labels \
               --jq 'sort_by(.number)[] | "\(.number)\t\(.headRefName)\t\(.headRefOid)\t\(.isDraft)\t\(.mergeable)\t\([.labels[].name] | join(","))"' 2>/dev/null)
    while IFS=$'\t' read -r pr branch head draft mg labels; do
        [[ "$pr" =~ ^[0-9]+$ ]] && [[ "$head" =~ ^[0-9a-f]{40}$ ]] && [ "$draft" = false ] || continue
        inpipe=""
        for l in $PIPELINE_LABELS; do has_label "$labels" "$l" && inpipe=1; done
        [ -n "$inpipe" ] || continue
        [ "$mg" = UNKNOWN ] && mg=$(gh pr view "$pr" --repo "$GH_REPO" --json mergeable --jq .mergeable 2>/dev/null)
        [ "$mg" = CONFLICTING ] || [ "$mg" = UNKNOWN ] || continue
        merge_conflicts "$branch" "$head"; rc=$?
        if [ "$rc" = 0 ]; then
            [ "$mg" = CONFLICTING ] && say "#$pr $branch: GitHub says CONFLICTING, but it merges cleanly into $TIP ${CX_TIP:0:10}; GitHub's answer is stale, next tick"
            continue
        fi
        if [ "$rc" = 2 ]; then
            [ "$mg" = CONFLICTING ] && CX_SEEN[$pr]=1
            [ "$mg" = CONFLICTING ] && { say "#$pr $branch: CONFLICTING, and this host cannot read where (no fetch or no object)"; T_WAITING+=("#$pr(conflict:unread)"); }
            continue
        fi
        CX_SEEN[$pr]=1
        if [ "$CX_FILES" = "$INDEX " ]; then
            if [ "$mode" = list ]; then echo "#$pr $branch @ ${head:0:10}: CONFLICTS in $INDEX alone; WOULD REPAIR on the lane branch"; continue; fi
            if [ -f "$F/failed/$pr-$head-conflict" ]; then T_WAITING+=("#$pr(handed-back:lane)"); continue; fi
            say "#$pr $branch @ ${head:0:10}: conflicts with $TIP ${CX_TIP:0:10} in $INDEX alone; repairing on the lane branch"
            repair_index_conflict "$pr" "$branch" "$head"; rc=$?
            case $rc in
            0)  say "  repaired #$pr: $branch ${head:0:10} -> ${REPAIRED_SHA:0:10} ($TIP merged in, index regenerated over $REPAIR_PINS)"
                T_REPAIRED+=("#$pr")
                comment "$pr" "[job.fold] Repaired: \`$branch\` conflicted with \`$TIP\` only in \`$INDEX\`, so the fold job merged \`$TIP\` @ \`${CX_TIP:0:10}\` into it and regenerated the index over $REPAIR_PINS (\`${head:0:10}\` -> \`${REPAIRED_SHA:0:10}\`, a fast-forward: no commit of yours changed sha). Pull before you next push: \`git pull --ff-only\`." ;;
            3)  say "  #$pr not repaired this tick: $WHY"; T_WAITING+=("#$pr(repair-deferred)") ;;
            *)  say "  #$pr not repaired: $WHY"
                conflict_handback "$pr" "$branch" "$head" "$INDEX " "$WHY" ;;
            esac
            continue
        fi
        # A code conflict. A PR that already carries needs-rebase is handback.sh's.
        if has_label "$labels" needs-rebase; then
            [ "$mode" = list ] || T_WAITING+=("#$pr(needs-rebase:lane)")
            continue
        fi
        if [ "$mode" = list ]; then echo "#$pr $branch @ ${head:0:10}: CONFLICTS in $CX_FILES; WOULD HAND BACK"; continue; fi
        conflict_handback "$pr" "$branch" "$head" "$CX_FILES"
    done <<< "$rows"
}

# ------------------------------------------------------------ candidates
# `labels` rides along on the one list call this job makes, and the title stays
# LAST: it is the only free-text field, and the read below gives the last
# variable everything after its own tab, so free text in any other position
# would end up inside a field a gate keys on.
# (read below, after the conflict pass: a repair moves a head)

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

# ------------------------------------------------ more than one fold per tick
# ONE FOLD PER TICK WAS THE BACKLOG'S CLOCK. A lane holds its files until its
# PR folds, and nearly every accuracy fix touches one of about nine hot pgraph
# files, so every fold-ready PR queued behind the one before it at one per
# 30-minute tick ("#350 waits: one fold per tick") while issues needing those
# files could not be dispatched at all.
#
# So a tick folds up to $FOLD_MAX_PER_TICK, sequentially, each on the trunk
# the previous one pushed and through every gate a single fold passes -- CI
# green on its head, the merge, the index, preflight on the merged tree, the
# push. Only PRs whose diffs touch DISJOINT files share a tick; the generated
# index is not counted, since it is regenerated on every fold and never
# merged. A PR whose files cannot be read folds only as a tick's first.
#
# THE ORDER is how many dispatchable issues wait on the PR's files: for each
# issue the board marks `dispatch_state = "available"` and no lane row claims,
# its files are the ones nv2a_index.json places its suites' registers in, and
# a PR scores one per such issue its diff touches. It is a proxy -- the index
# knows registers, not the fix an issue will need -- and ties keep PR order.
#
# TWO PRS GREEN APART CAN BE RED TOGETHER. Each PR's CI ran on its own head,
# not on the trunk with the other folds of its tick in it. So a tick that
# folds more than one records them in $F/multi/<the trunk head it left>, and
# each later tick reads master's CI on that head:
#   GREEN        done.
#   pending      at most ONE fold this tick, so the attribution below still
#                has a tick to attribute.
#   RED          and the trunk before the tick was not already red: the LAST
#                fold of the tick is reverted first, and nothing folds until
#                the revert's CI answers. GREEN names that PR, red together
#                with the others, and hands it back; RED re-lands it and
#                names the others as the suspects, for a person.
FOLD_MAX_PER_TICK="${FOLD_MAX_PER_TICK:-3}"
MULTI="$F/multi"; mkdir -p "$MULTI"
HOLD=""    # "" | one | all: what attribute_multi leaves this tick allowed to fold

# CANCELLED is dropped, not counted red: a newer push cancelling an older run
# is concurrency, not a verdict about this commit. Any failure is RED even
# while other runs are still going. In a variable so the self-test runs this
# exact text through the real jq; its gh shim never would.
TRUNK_CI_JQ='[.check_runs[]? | if .status != "completed" then "PENDING" else ((.conclusion // "") | ascii_upcase) end
         | select(. != "CANCELLED")] as $c
        | if ($c | length) == 0 then "NONE"
          elif ($c | any(. == "FAILURE" or . == "TIMED_OUT" or . == "STARTUP_FAILURE" or . == "ACTION_REQUIRED")) then "RED"
          elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
          else "PENDING" end'
trunk_ci() {   # <sha> -> GREEN|RED|PENDING|NONE for the push runs on a trunk commit
    gh api "repos/$GH_REPO/commits/$1/check-runs" --jq "$TRUNK_CI_JQ" 2>/dev/null
}

trunk_wt() {   # -> 0 with $WT clean and detached at a fresh origin/$TIP
    if [ ! -e "$WT/.git" ]; then
        git -C "$REPO" fetch -q origin "$TIP" && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD || return 1
    fi
    git -C "$WT" fetch -q origin "+refs/heads/$TIP:refs/remotes/origin/$TIP" 2>/dev/null || return 1
    git -C "$WT" reset -q --hard && git -C "$WT" clean -qfd && git -C "$WT" checkout -q --detach "refs/remotes/origin/$TIP"
}
REVERT_SHA=""
REVERT_BEFORE=""
revert_range() {   # <pr> <before> <after> <subject> <body> -> 0 with the revert pushed to $TIP as REVERT_SHA
    local pr=$1 before=$2 after=$3 c rc
    REVERT_SHA=""; REVERT_BEFORE=""; WHY=""
    trunk_wt || { WHY="cannot prepare $WT"; return 1; }
    REVERT_BEFORE=$(git -C "$WT" rev-parse HEAD)
    # Newest first, first-parent only: the fold's merge and the index commit
    # on top of it, and nothing the lane brought with it separately.
    for c in $(git -C "$WT" rev-list --first-parent "$before..$after"); do
        if git -C "$WT" rev-parse -q --verify "$c^2" >/dev/null 2>&1; then
            git -C "$WT" revert --no-commit -m 1 "$c" >>"$F/revert.log" 2>&1
        else
            git -C "$WT" revert --no-commit "$c" >>"$F/revert.log" 2>&1
        fi || { git -C "$WT" revert --abort 2>/dev/null; git -C "$WT" reset -q --hard; WHY="the revert of ${c:0:10} does not apply to $TIP"; return 1; }
    done
    git -C "$WT" commit -q -m "$4" -m "$5" || { WHY="the revert would not commit"; return 1; }
    regen_index "$WT" "$pr" "nv2a index: regenerate after reverting #$pr"; rc=$?
    [ "$rc" = 1 ] && { WHY="the index did not regenerate after the revert: $WHY"; return 1; }
    git -C "$WT" push -q origin "HEAD:$TIP" 2>"$F/push.log" || { WHY="push rejected: $(tail -1 "$F/push.log")"; return 1; }
    REVERT_SHA=$(git -C "$WT" rev-parse HEAD)
}

attribute_multi() {
    local rec sha st base pr branch before after others rpr rv rvb rest p
    for rec in "$MULTI"/*; do
        [ -f "$rec" ] || continue
        grep -q '^done' "$rec" && continue
        sha=${rec##*/}
        others=$(awk '$1=="fold"{printf "#%s ", $2}' "$rec"); others="${others% }"
        read -r _ pr branch before after <<< "$(grep '^fold ' "$rec" | tail -1)"
        if ! grep -q '^reverted ' "$rec"; then
            st=$(trunk_ci "$sha")
            case "$st" in
            GREEN)
                echo "done green" >> "$rec"
                say "master CI GREEN on ${sha:0:10} after folding $others in one tick" ;;
            RED)
                base=$(awk '$1=="base"{print $2}' "$rec")
                if [ "$(trunk_ci "$base")" = RED ]; then
                    echo "done base-red" >> "$rec"
                    say "master CI RED on ${sha:0:10} after folding $others, but it was already red at ${base:0:10} before that tick; not attributed to the tick"
                    continue
                fi
                HOLD=all
                say "master CI RED on ${sha:0:10} after folding $others in one tick; reverting the last, #$pr, to attribute it"
                if ! revert_range "$pr" "$before" "$after" "fold: revert #$pr to attribute master's red at ${sha:0:10}" \
                     "master's CI went red on ${sha:0:10}, the tip after one tick folded $others. Each was green on its own head; the last fold of the tick is reverted first and the next CI run says whether it was this one."; then
                    echo "done revert-failed" >> "$rec"
                    say "  could not revert #$pr: $WHY. Needs a person: master is red after folding $others"
                    continue
                fi
                echo "reverted $pr $REVERT_SHA $REVERT_BEFORE" >> "$rec"
                say "  reverted #$pr as ${REVERT_SHA:0:10}; nothing folds until its CI answers"
                comment "$pr" "[job.fold] Reverted from \`$TIP\` as \`${REVERT_SHA:0:10}\`: master's CI went red on \`${sha:0:10}\`, the tip after one tick folded $others. This was the last fold of that tick, so it is reverted first to attribute the red; master's next CI run says whether it was this PR. Nothing needs doing yet." ;;
            *)
                [ -n "$HOLD" ] || HOLD=one
                say "master CI ${st:-UNREAD} on ${sha:0:10} after folding $others in one tick; at most one fold until it reports" ;;
            esac
            continue
        fi
        read -r _ rpr rv rvb <<< "$(grep '^reverted ' "$rec" | tail -1)"
        rest=$(printf '%s\n' $others | grep -vx "#$rpr" | tr '\n' ' '); rest="${rest% }"
        st=$(trunk_ci "$rv")
        case "$st" in
        GREEN)
            echo "done culprit $rpr" >> "$rec"
            # NAMED, NOT HANDED BACK. The fold deleted the lane branch and
            # GitHub closed this PR as merged when its commits reached $TIP, so
            # a needs-rebase label here would sit on a closed PR that nothing
            # reads. Re-landing is new work: a new PR from the lane's local
            # branch, which the board dispatches like any other.
            say "master CI GREEN on the revert ${rv:0:10}: ATTRIBUTED #$rpr, red together with $rest (each green apart); re-landing it is new work"
            comment "$rpr" "[job.fold] **Attributed: this PR is red together with $rest.** Each was green on its own head, and one tick folded them all; master's CI went red on \`${sha:0:10}\`, and reverting this PR (\`${rv:0:10}\`) turned it green again. So the red is the combination, not this PR alone and not the others alone.

This PR is closed as merged and its branch was deleted by the fold, so re-landing it is a new PR. From the lane's worktree:

\`\`\`
git fetch origin $TIP && git merge origin/$TIP   # brings in the revert; merge, never rebase
git revert ${rv:0:10}                              # restores this PR's changes
# fix the interaction with $rest, push, open a new PR
\`\`\`" ;;
        RED)
            echo "done not $rpr" >> "$rec"
            say "master CI still RED on the revert ${rv:0:10}: the red after folding $others is not #$rpr's alone; re-landing it"
            if revert_range "$rpr" "$rvb" "$rv" \
                   "fold: re-land #$rpr; reverting it did not turn master green" "Reverting #$rpr (${rv:0:10}) left master red, so the red after the tick that folded $others is not its alone."; then
                say "  re-landed #$rpr as ${REVERT_SHA:0:10}; suspects: $rest, or the trunk itself. Needs a person."
            else
                say "  could not re-land #$rpr: $WHY. Needs a person."
            fi
            comment "$rpr" "[job.fold] Not this PR: reverting it (\`${rv:0:10}\`) left master red, so the red after the tick that folded $others is not its alone. ${REVERT_SHA:+It is re-landed as \`${REVERT_SHA:0:10}\`.}${REVERT_SHA:-The re-land did not apply; the revert stands until a person re-lands it.}"
            for p in $rest; do
                comment "${p#\#}" "[job.fold] master's CI went red on \`${sha:0:10}\` after one tick folded $others, and reverting #$rpr did not turn it green. This PR is one of the remaining suspects ($rest, or the trunk itself); a person decides."
            done ;;
        *)
            HOLD=all
            say "master CI ${st:-UNREAD} on the revert ${rv:0:10} of #$rpr; nothing folds until it answers" ;;
        esac
    done
}

fold_priority() {   # stdin "pr<TAB>file file ..." -> stdout "pr<TAB>score", same order
    python3 -c '
import json, subprocess, sys
sys.path.insert(0, sys.argv[1])
rows = [l.rstrip("\n").split("\t", 1) for l in sys.stdin if l.strip()]
score = {r[0]: 0 for r in rows}
try:
    from board_files import load
    issues = load("nv2a_issues.toml").get("issue", {})
    terr = load("territory.toml")
    claimed = {str(i) for row in (terr.get("lane") or {}).values() for i in (row.get("issues") or [])}
    idx = json.loads(subprocess.run(["git", "-C", sys.argv[2], "show", sys.argv[3] + ":docs/testing/nv2a_index.json"],
                                    capture_output=True, check=True).stdout)
    for n, e in issues.items():
        if (e.get("dispatch_state") or "") != "available" or n in claimed:
            continue
        fs = set()
        for s in (idx.get("issues", {}).get(n) or e).get("suites") or []:
            for sym in (idx.get("suites", {}).get(s) or {}).get("symbols") or []:
                for site in idx.get("sites", {}).get(sym) or []:
                    fs.add(site["loc"].rsplit(":", 1)[0])
        for r in rows:
            if len(r) > 1 and fs & set(r[1].split()):
                score[r[0]] += 1
except Exception:
    pass
for r in rows:
    print("%s\t%d" % (r[0], score[r[0]]))
' "$T" "$REPO" "refs/remotes/origin/$TIP" 2>/dev/null
}

pr_files() {   # <branch> -> the files the PR changes against the trunk, the index excepted; non-zero when unreadable
    git -C "$REPO" fetch -q origin "+refs/heads/$TIP:refs/remotes/origin/$TIP" "+refs/heads/$1:refs/remotes/origin/$1" 2>/dev/null || return 1
    local out; out=$(git -C "$REPO" diff --name-only "refs/remotes/origin/$TIP...refs/remotes/origin/$1" 2>/dev/null) || return 1
    printf '%s\n' "$out" | grep -vxF "$INDEX" | grep . | tr '\n' ' '
    return 0
}

FOLD_BEFORE=""; FOLD_AFTER=""; tick_tip=""
fold_one() {   # <pr> <branch> <head> <accepted|-> <title> -> 0 folded and pushed, FOLD_BEFORE/FOLD_AFTER set
    local pr=$1 branch=$2 head=$3 accepted=$4 title=$5 notes_moved index_taken files rc gates merge_sha
    [ "$accepted" = - ] && accepted=""
    FOLD_BEFORE=""; FOLD_AFTER=""
    # ---------------------------------------------------------- the fold
    say "folding #$pr $branch @ ${head:0:10}: $title"
    [ -n "$accepted" ] && say "  it is labelled regressed; folding on regression-accepted:#$accepted"
    if [ ! -e "$WT/.git" ]; then
        git -C "$REPO" fetch -q origin "$TIP" && git -C "$REPO" worktree add --quiet --detach "$WT" FETCH_HEAD || { say "cannot create $WT"; return 1; }
    fi
    git -C "$WT" fetch -q origin "$TIP" "$branch" || { say "fetch failed"; return 1; }
    git -C "$WT" reset -q --hard && git -C "$WT" clean -qfd && git -C "$WT" checkout -q --detach "origin/$TIP"
    FOLD_BEFORE=$(git -C "$WT" rev-parse HEAD)
    notes_moved=""; index_taken=""
    if ! git -C "$WT" merge --no-ff --no-edit -m "fold: PR #$pr $branch -- $title" "origin/$branch" >"$F/merge.log" 2>&1; then
        files=$(git -C "$WT" diff --name-only --diff-filter=U | tr '\n' ' ')
        if resolve_root_notes "$WT" "$branch"; then
            notes_moved=$(notes_path "$branch")
            git -C "$WT" commit -q -m "fold: PR #$pr $branch -- $title" \
                -m "The lane's root NOTES.md conflicted with master's and nothing else did; its copy is at $notes_moved (roles/lane.md item 3). No content was merged or dropped." \
                || { git -C "$WT" merge --abort 2>/dev/null; say "#$pr NOTES.md resolved but the merge would not commit"; return 1; }
            say "  only root NOTES.md conflicted; the lane's copy is at $notes_moved"
        elif resolve_index_only "$WT"; then
            index_taken=1
            git -C "$WT" commit -q -m "fold: PR #$pr $branch -- $title" \
                -m "$INDEX conflicted with master's and nothing else did. master's copy was taken, and the index gate below checks it over nxdk_pgraph_tests @ $(git -C "$PIN_TESTS" rev-parse --short=12 HEAD) and pbkitplusplus @ $(git -C "$PIN_SUPPORT" rev-parse --short=12 HEAD) and regenerates it on top if it is stale. Nothing in it was hand-merged." \
                || { git -C "$WT" merge --abort 2>/dev/null; say "#$pr index resolved but the merge would not commit"; return 1; }
            say "  only $INDEX conflicted; master's copy taken, to be regenerated over the pinned trees"
        else
            [ -n "$WHY" ] && say "  $INDEX is the only conflict, but not resolved here: $WHY"
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
            hand_back "$pr" "$branch" "$head" "$files"
            comment "$pr" "[job.fold] Not folded: merging \`$branch\` into \`$TIP\` conflicts in: \`$files\`. The fold job resolves nothing (a merge it does not understand is how a fix was reverted on 09-12). Merge \`origin/$TIP\` into the lane branch, resolve there, push, then re-apply \`fold-ready\`."
            return 1
        fi
    fi
    # The index: regenerate if the merge moved it, never hand-merge it, and
    # only over the pinned trees (see resolve_index_only). A clean merge that
    # cannot pin skips the gate, as a host without the sources always has; an
    # index conflict that was resolved above may not, since its copy is known
    # to be master's and not this merge's.
    regen_index "$WT" "$pr"; rc=$?
    if [ "$rc" = 2 ] && [ -z "$index_taken" ]; then
        say "  note: $WHY; index gate skipped (CI runs it on master)"
    elif [ "$rc" != 0 ]; then
        echo "index regeneration failed: $WHY" > "$F/failed/$pr-$head"; say "  index regeneration FAILED: $WHY"
        if [ -n "$index_taken" ]; then
            hand_back "$pr" "$branch" "$head" "$INDEX "
            comment "$pr" "[job.fold] Not folded: the nv2a index did not regenerate cleanly after the merge (see the host's \$WORK/fold/index.log): $WHY. It was the only conflicting file, so master's copy was taken to be rebuilt over the pinned trees, and that rebuild is what failed. Merge \`origin/$TIP\` into the lane branch, regenerate the index there, push, then re-apply \`fold-ready\`."
        else
            comment "$pr" "[job.fold] Not folded: the nv2a index did not regenerate cleanly after the merge (see the host's \$WORK/fold/index.log). Needs a person."
        fi
        return 1
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
            return 1
        fi
        echo "preflight failed${gates:+: $gates}" > "$F/failed/$pr-$head"
        say "  preflight FAILED: $(grep -m3 FAILED "$F/preflight.log" | tr '\n' ' ')"
        comment "$pr" "[job.fold] Not folded: preflight fails on the merged tree:
\`\`\`
$(grep -B1 -A3 FAILED "$F/preflight.log" | head -30)
\`\`\`
Fix on the lane branch and push; the next green head is re-tried."
        return 1
    fi
    if ! git -C "$WT" push -q origin "HEAD:$TIP" 2>"$F/push.log"; then
        say "  push to $TIP rejected (it moved?): $(tail -1 "$F/push.log"); next tick retries"
        return 1
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
    FOLD_AFTER=$(git -C "$WT" rev-parse HEAD)
    return 0
}

# ------------------------------------------------------------------ the tick
[ "$mode" = list ] || attribute_multi
conflict_pass

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

READY=()
while IFS=$'\t' read -r pr branch head draft labels title; do
    [ -n "$pr" ] || continue
    if [ "$draft" = true ]; then
        say "#$pr is a draft: not folding; label removed"
        [ "$mode" = list ] && { echo "#$pr $branch: DRAFT"; continue; }
        label_rm "$pr" fold-ready || say "  WARNING: could not remove fold-ready from #$pr; it will be re-tried every tick"
        comment "$pr" "[job.fold] Not folded: the PR is still a draft. Mark it ready (\`gh pr ready $pr\`) and re-apply \`fold-ready\`."
        continue
    fi
    # A PR the conflict pass answered for this tick -- repaired onto a head
    # with no CI yet, handed back, or deferred -- would read here as CI NONE,
    # and NONE's comment blames a skip marker. The conflict pass has said what
    # is true about it already.
    [ -n "${CX_SEEN[$pr]:-}" ] && continue
    # STILL IN AUDIT IS NOT FOLD-READY, whatever else the PR carries. A PR in
    # audit that conflicts is handed back above with its audit label kept, and
    # handback.sh relabels a resolved needs-rebase as fold-ready without
    # asking about audit; the audit label is the truth. Nothing is removed:
    # the audit that clears its label leaves the fold-ready it finds.
    inaudit=""
    for l in needs-audit-1 needs-audit-2 needs-remediation; do has_label "$labels" "$l" && inaudit=$l; done
    if [ -n "$inaudit" ]; then
        [ "$mode" = list ] && { echo "#$pr $branch: still in audit ($inaudit)"; continue; }
        say "#$pr $branch: carries $inaudit as well as fold-ready; waits for the audit"
        T_WAITING+=("#$pr(audit:$inaudit)")
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
        T_WAITING+=("#$pr(CI:$ci)")
        ci_report "$pr" "$head" "$ci"
        continue
    fi
    if [ -f "$F/failed/$pr-$head" ]; then
        [ "$mode" = list ] && echo "#$pr $branch: failed before on this head ($(cat "$F/failed/$pr-$head"))"
        continue
    fi
    READY+=("$pr"$'\t'"$branch"$'\t'"$head"$'\t'"${accepted:--}"$'\t'"$title")
done <<< "$cands"

# ------------------------------------------------ fold what is ready, in order
max=$FOLD_MAX_PER_TICK
case "$HOLD" in one) max=1 ;; all) max=0 ;; esac
declare -A PFILES=()
prio_in=""
for row in "${READY[@]}"; do
    IFS=$'\t' read -r pr branch _ <<< "$row"
    if f=$(pr_files "$branch"); then PFILES[$pr]="$f"; else PFILES[$pr]="?"; fi
    prio_in+="$pr"$'\t'"${PFILES[$pr]}"$'\n'
done
declare -A PSCORE=()
if [ "${#READY[@]}" -gt 1 ]; then
    while IFS=$'\t' read -r pr sc; do [ -n "$pr" ] && PSCORE[$pr]=$sc; done <<< "$(printf '%s' "$prio_in" | fold_priority)"
fi
# Highest score first; `sort -s` keeps the PR order the candidate list had for ties.
ORDERED=()
while IFS= read -r row; do [ -n "$row" ] && ORDERED+=("${row#*$'\t'}"); done <<< "$(
    for row in "${READY[@]}"; do printf '%s\t%s\n' "${PSCORE[${row%%$'\t'*}]:-0}" "$row"; done | sort -s -t $'\t' -k1,1nr)"

folded=0; FOLDED_FILES=" "; tick_base=""; tick_rec=""
for row in "${ORDERED[@]}"; do
    IFS=$'\t' read -r pr branch head accepted title <<< "$row"
    files="${PFILES[$pr]:-?}"; why=""
    if [ "$folded" -ge "$max" ]; then
        case "$HOLD" in
            all) why="master's CI after a multi-fold tick is being attributed" ;;
            one) why="master's CI after a multi-fold tick has not reported; one fold this tick" ;;
            *)   why="$max folds this tick" ;;
        esac
    elif [ "$folded" -gt 0 ]; then
        if [ "$files" = "?" ]; then
            why="its files could not be read, so it folds only first in a tick"
        else
            for f in $files; do
                case "$FOLDED_FILES" in *" $f "*) why="it shares $f with a PR folded this tick"; break ;; esac
            done
        fi
    fi
    if [ -n "$why" ]; then
        [ "$mode" = list ] && { echo "#$pr $branch: WOULD WAIT: $why"; continue; }
        say "#$pr waits: $why"
        T_WAITING+=("#$pr(next-tick)")
        continue
    fi
    if [ "$mode" = list ]; then
        acc="${accepted#-}"
        echo "#$pr $branch @ ${head:0:10}: WOULD FOLD (score ${PSCORE[$pr]:-0})${acc:+ (regression accepted on #$acc)}"
        folded=$((folded+1)); FOLDED_FILES+="$files "; continue
    fi
    if fold_one "$pr" "$branch" "$head" "$accepted" "$title"; then
        folded=$((folded+1)); FOLDED_FILES+="$files "
        T_FOLDED+=("#$pr")
        [ -n "$tick_base" ] || tick_base=$FOLD_BEFORE
        tick_rec+="fold $pr $branch $FOLD_BEFORE $FOLD_AFTER"$'\n'
        tick_tip=$FOLD_AFTER
    else
        T_WAITING+=("#$pr(fold-refused)")
    fi
done
if [ "$folded" -ge 2 ] && [ "$mode" != list ]; then
    { echo "base $tick_base"; printf '%s' "$tick_rec"; } > "$MULTI/$tick_tip"
    say "folded $folded PRs in one tick; master's CI on ${tick_tip:0:10} is read next tick to attribute any red"
fi
[ "$mode" = list ] || tick_summary

# The handed-back PRs get their actor, on this tick's timer. It is a separate
# script on purpose: THIS job merges and must never start a model session, and
# a job that starts model sessions has a cap, an attempt counter and an
# escalation policy that have nothing to do with merging. `$mode` is passed
# through so `fold.sh list` stays read-only and resumes nobody.
[ -f "$T/jobs/handback.sh" ] && bash "$T/jobs/handback.sh" "$mode" >/dev/null 2>&1
[ -x "$T/jobs/status.sh" ] && bash "$T/jobs/status.sh" >/dev/null 2>&1
exit 0
