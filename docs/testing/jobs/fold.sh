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
# and the merge applies without conflict. A conflict is
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
[ -n "$cands" ] || { [ "$mode" = list ] && echo "nothing labelled fold-ready"; exit 0; }

ci_green() {   # <pr> -> 0 when every check on the head has concluded SUCCESS (or was skipped)
    gh pr view "$1" --repo "$GH_REPO" --json statusCheckRollup --jq '
        [.statusCheckRollup[]? | (.conclusion // .state // "PENDING")] as $c
        | if ($c | length) == 0 then "NONE"
          elif ($c | all(. == "SUCCESS" or . == "SKIPPED" or . == "NEUTRAL")) then "GREEN"
          elif ($c | any(. == "FAILURE" or . == "ERROR" or . == "CANCELLED" or . == "TIMED_OUT")) then "RED"
          else "PENDING" end' 2>/dev/null
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
    fi
    if has_label "$labels" regressed && [ -z "$accepted" ]; then
        # `list` stays read-only here: the state it would report is on the PR
        # already, as the label it is reading.
        [ "$mode" = list ] && { echo "#$pr $branch: REGRESSED (a registered prediction FAILED; the owner may accept it with regression-accepted:<issue>)"; continue; }
        say "#$pr $branch: labelled regressed and not accepted; not folding (fold-ready kept)"
        regressed_report "$pr" "$head" "$labels"
        continue
    fi
    ci=$(ci_green "$pr")
    if [ "$ci" != GREEN ]; then
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

This PR is labelled \`regressed\`, and it folded **because the regression is accepted on #$accepted** (\`regression-accepted:$accepted\`), not because the gate missed it. The failing verdict above stands as measured; #$accepted is where the trade it is part of is argued.}${notes_moved:+

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
