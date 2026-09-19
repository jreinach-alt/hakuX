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
#   fold.sh prune-branch <dir> <branch> <proof>
#                    the one conflict resolution, and the branch deletion,
#                    each on a repository handed in, so the self-test can run
#                    them against a scratch remote without a fake gh
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
# audit). This job checks what the label cannot: the PR is not a draft, its
# head's CI is green, and the merge applies without conflict. A conflict is
# never resolved here -- the lane gets `needs-rebase` and a comment naming
# the files, because a merge resolved by a script that does not understand
# the code is how a working fix was reverted on 2026-09-12.
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
mkdir -p "$F/failed" "$WORK/logs/fold"
LOG="$WORK/logs/fold/tick.log"
say() { echo "$(date -u '+%FT%TZ') $*" | tee -a "$LOG"; }
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

# ------------------------------------------------------------ candidates
cands=$(gh pr list --repo "$GH_REPO" --state open --label fold-ready --json number,title,headRefName,headRefOid,isDraft \
            --jq 'sort_by(.number)[] | "\(.number)\t\(.headRefName)\t\(.headRefOid)\t\(.isDraft)\t\(.title)"' 2>/dev/null)
[ -n "$cands" ] || { [ "$mode" = list ] && echo "nothing labelled fold-ready"; exit 0; }

ci_green() {   # <pr> -> 0 when every check on the head has concluded SUCCESS (or was skipped)
    gh pr view "$1" --repo "$GH_REPO" --json statusCheckRollup --jq '
        [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
        | if ($c | length) == 0 then "NONE"
          elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
          elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
          else "PENDING" end' 2>/dev/null
}

folded=0
while IFS=$'\t' read -r pr branch head draft title; do
    [ -n "$pr" ] || continue
    if [ "$draft" = true ]; then
        say "#$pr is a draft: not folding; label removed"
        [ "$mode" = list ] && { echo "#$pr $branch: DRAFT"; continue; }
        label_rm "$pr" fold-ready || say "  WARNING: could not remove fold-ready from #$pr; it will be re-tried every tick"
        comment "$pr" "[job.fold] Not folded: the PR is still a draft. Mark it ready (\`gh pr ready $pr\`) and re-apply \`fold-ready\`."
        continue
    fi
    ci=$(ci_green "$pr")
    if [ "$ci" != GREEN ]; then
        [ "$mode" = list ] && echo "#$pr $branch: CI $ci"
        say "#$pr $branch: CI is $ci on $head; waiting"
        if [ "$ci" = RED ] && [ ! -f "$F/failed/$pr-$head-ci" ]; then
            touch "$F/failed/$pr-$head-ci"
            comment "$pr" "[job.fold] Not folded: CI is red on \`${head:0:10}\`. The fold waits for a green head; push a fix and the next tick picks it up."
        fi
        continue
    fi
    if [ -f "$F/failed/$pr-$head" ]; then
        [ "$mode" = list ] && echo "#$pr $branch: failed before on this head ($(cat "$F/failed/$pr-$head"))"
        continue
    fi
    if [ "$mode" = list ]; then echo "#$pr $branch @ ${head:0:10}: WOULD FOLD"; continue; fi
    [ "$folded" -eq 0 ] || { say "#$pr waits: one fold per tick"; continue; }

    # ---------------------------------------------------------- the fold
    say "folding #$pr $branch @ ${head:0:10}: $title"
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
        echo "preflight failed" > "$F/failed/$pr-$head"
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
    comment "$pr" "[job.fold] Folded as \`$merge_sha\` on \`$TIP\` (--no-ff; every commit keeps its sha, so registered refs stay bound). CI now runs on $TIP; the arms job picks up any prediction this PR carries.${notes_moved:+

Your branch's root \`NOTES.md\` conflicted with the one already on \`$TIP\` and nothing else did, so it was moved to \`$notes_moved\` rather than merged -- both lanes' records are on $TIP, each at its own path. That is where \`roles/lane.md\` item 3 now asks for it; write it there next time and no fold has to touch it.}"
    say "  folded #$pr as $merge_sha"
    # HEAD is the commit the push above just put on $TIP, so it IS the trunk's
    # tip -- a stronger proof than origin/$TIP, which is one fetch stale here.
    # Only reached after that push succeeded: a branch deleted on a fold that
    # failed to push is work destroyed.
    prune_branch "$WT" "$branch" HEAD
    folded=1
done <<< "$cands"

[ -x "$T/jobs/status.sh" ] && bash "$T/jobs/status.sh" >/dev/null 2>&1
exit 0
