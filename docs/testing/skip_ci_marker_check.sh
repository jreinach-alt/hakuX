#!/usr/bin/env bash
#
# Refuse a branch whose history carries the retired CI-skip marker.
#
# WHY THIS EXISTS
#
# The marker is retired: preflight.sh:338 records that this repository is
# public, that Actions is free on it, and that "CI now runs on every lane PR
# and every push to master and is the gate that matters". The marker's only
# remaining effect is to suppress that gate.
#
# Nothing prevents it. fold.sh:343 names it as "the usual cause" when a fold
# lands with no CI, and selftest.d/85-fold-ci.sh checks that the explanation is
# emitted -- both DIAGNOSE it after it has already cost a fold. It has bitten
# twice: #139 for real, and lane.remote's 14312cb34f, which carries it inside a
# sentence recording that it had been retired, and is inert only by luck of how
# GitHub reads a push and how fold.sh merges.
#
# THIS IS NOT THE GATE preflight.sh RETIRED. That one permitted or required the
# marker back when CI was scarce. This is its complement: a check that the
# marker is ABSENT, which matters precisely because CI is now what gates.
#
# READS EVERY BODY IN THE RANGE, NOT THE HEAD. GitHub matches the marker
# anywhere in a commit message, subject or body, and a fold can promote any
# commit to a head. Checking only the tip is how 14312cb34f survived review.
#
# WHAT TO DO WHEN IT FIRES
#
# Usually: reword the commit. But NOT if a registered prediction names that
# commit or a descendant of it as a ref -- rewording rewrites history the
# prediction depends on, which roles/lane.md forbids outright. In that case the
# honest answer is to record it on the PR, establish that it is inert (the
# head of every push has run CI, and fold.sh merges rather than squashes), and
# leave it. This script reports; it does not rewrite anything.
#
#   usage: skip_ci_marker_check.sh [<range>]   (default origin/master..HEAD)
#          skip_ci_marker_check.sh --selftest
#
# exit 0 clean, 1 marker found, 2 bad usage

set -uo pipefail

# Assembled rather than written out, so this file does not itself trip the
# check it implements -- which is the same trap 14312cb34f fell into.
MARKER="[skip""ci]"
MARKER="${MARKER/skipci/skip ci}"

scan() {
    local range="$1" found=0 c
    while read -r c; do
        [ -n "$c" ] || continue
        if git log -1 --format='%B' "$c" | grep -qF -- "$MARKER"; then
            printf '  %s\n' "$(git log -1 --format='%h %s' "$c")"
            found=1
        fi
    done < <(git log --format='%H' "$range" 2>/dev/null)
    return $found
}

selftest() {
    local td rc=0
    td=$(mktemp -d) || return 2
    (
        cd "$td" || exit 2
        git init -q . && git config user.email t@t && git config user.name t
        git commit -q --allow-empty -m "base"
        git branch -q -M main
        git checkout -q -b topic
        git commit -q --allow-empty -m "clean one"
        git commit -q --allow-empty -m "$(printf 'subject line\n\nbody mentioning %s in prose\n' "$MARKER")"
        git commit -q --allow-empty -m "another clean one, and it is the HEAD"
    ) || { rm -rf "$td"; return 2; }

    local out
    out=$(cd "$td" && scan main..topic)
    if printf '%s' "$out" | grep -q 'subject line'; then
        echo "ok   finds a marker in a BODY, with a clean commit as the head"
    else
        echo "FAIL did not find a marker buried in a commit body"; rc=1
    fi
    if [ "$(printf '%s\n' "$out" | grep -c .)" = 1 ]; then
        echo "ok   reports only the commit that carries it"
    else
        echo "FAIL reported $(printf '%s\n' "$out" | grep -c .) commits, expected 1"; rc=1
    fi
    out=$(cd "$td" && scan main..main)
    if [ -z "$out" ]; then
        echo "ok   silent on a range with no marker"
    else
        echo "FAIL reported something on a clean range"; rc=1
    fi
    rm -rf "$td"
    [ $rc = 0 ] && echo "all fixtures pass" || echo "FIXTURES FAILED"
    return $rc
}

[ "${1:-}" = "--selftest" ] && { selftest; exit $?; }

RANGE="${1:-origin/master..HEAD}"
git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repository" >&2; exit 2; }

echo "scanning every commit body in $RANGE for the retired CI-skip marker"
if scan "$RANGE"; then
    echo "clean"
    exit 0
fi
cat <<MSG

Those commits carry the retired marker. GitHub matches it anywhere in a
message, so any of them promoted to a head suppresses the CI that is now the
gate that matters (preflight.sh:338, fold.sh:343).

Reword them -- UNLESS a registered prediction names one of them, or a
descendant, as a ref. Rewriting history a live prediction depends on is worse
than the marker; record it on the PR instead and show that it is inert.
MSG
exit 1
