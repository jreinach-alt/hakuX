#!/usr/bin/env bash
#
# The fold job. Runs from hakux-fold.timer every 30 minutes; a script, no
# model session.
#
#   fold.sh          fold the oldest fold-ready PR whose CI is green
#   fold.sh list     what it would fold, and why the rest waits
#   fold.sh resolve-notes <worktree> <branch>
#                    the one conflict resolution below, on an in-progress
#                    merge, so the self-test can run it without a fake gh
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
