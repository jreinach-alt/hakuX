#!/usr/bin/env bash
#
# Labels, through the REST API instead of `gh pr edit`.
#
#   . gh-label.sh            then: label_add <n> <label>...  /  label_rm <n> <label>...
#   gh-label.sh add <n> <label>...     as a command, for a string a unit will run
#   gh-label.sh rm  <n> <label>...
#
# MEASURED 2026-09-19 on the host, with `gh version 2.45.0`:
#
#     $ gh pr edit 116 --repo jreinach-alt/hakuX --add-label harness
#     GraphQL: Projects (classic) is being deprecated in favor of the new
#     Projects experience ... (repository.pullRequest.projectCards)
#     $ echo $?
#     1
#
# `gh pr edit` asks for project cards on every edit and GitHub now refuses that
# field, so the command fails and NO label is applied. Every job called it as
# `gh pr edit ... >/dev/null 2>&1`, so the pipeline's whole state machine for
# PRs -- fold-ready, folded, needs-rebase, verified, regressed, claimed:cloud --
# was inert AND silent. The fold job would have folded a PR and left it
# unlabelled, so the next tick would have folded it again; the arms job would
# have judged an arm and marked nothing.
#
# `gh issue edit` does not go through that path and works, and the REST
# endpoint works for both, because a pull request IS an issue as far as labels
# are concerned. Upgrading gh would also fix it -- and a harness that keeps its
# own state through a particular gh version is a harness that loses its state
# on the next host, so this does not depend on the version.
#
# A removal is checked against the labels actually present first: DELETE on a
# label that is not there is a 404, and swallowing 404 would swallow every
# other failure with it.
set -u
GH_REPO="${GH_REPO:-jreinach-alt/hakuX}"

label_add() {   # <number> <label>...  -> 0 when every label is applied
    local n=$1; shift; local l; local -a args=()
    for l in "$@"; do [ -n "$l" ] && args+=(-f "labels[]=$l"); done
    [ "${#args[@]}" -gt 0 ] || return 0
    gh api -X POST "repos/$GH_REPO/issues/$n/labels" "${args[@]}" >/dev/null 2>&1
}

label_rm() {    # <number> <label>...  -> 0 when none of them is on it any more
    local n=$1; shift; local l enc have rc=0
    have=$(gh api "repos/$GH_REPO/issues/$n/labels" --jq '.[].name' 2>/dev/null) || return 1
    for l in "$@"; do
        [ -n "$l" ] || continue
        grep -Fxq -- "$l" <<< "$have" || continue      # not on it: nothing to remove
        enc=$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1],safe=""))' "$l")
        gh api -X DELETE "repos/$GH_REPO/issues/$n/labels/$enc" >/dev/null 2>&1 || rc=1
    done
    return $rc
}

# Sourced: the two functions above are the whole interface. Run directly: a CLI,
# because cloud.sh builds an "unclaim" command as a STRING for the session's
# systemd unit to run when it exits, where nothing is sourced.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    case "${1:-}" in
        add) shift; label_add "$@" ;;
        rm)  shift; label_rm  "$@" ;;
        *)   echo "usage: gh-label.sh {add|rm} <number> <label>..." >&2; exit 2 ;;
    esac
fi
