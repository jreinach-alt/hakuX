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

# Resolve the range before scanning it. `git log <bad-range>` writes to stderr
# and produces no commits, so a loop over it runs zero times and a `found`
# counter stays 0 -- which reads as "clean" and is really "scanned nothing".
# Audit pass 2b, P1.
#
# Sets RANGE_COUNT and returns non-zero on failure. It does NOT exit: the first
# attempt at this fix had `resolve` call `exit 2` and the caller invoke it as
# `N=$(resolve ...)`, where the exit killed the COMMAND SUBSTITUTION SUBSHELL
# and the script carried on to print "clean" and exit 0 -- the guard firing and
# the code proceeding anyway, which is the very shape P1 is. Caught by re-running
# the reproduction after fixing rather than by reading the patch.
RANGE_COUNT=""
resolve() {
    local range="$1" n
    if ! n=$(git rev-list --count "$range" 2>&1); then
        printf 'cannot resolve range %s: %s\n' "$range" "$n" >&2
        printf 'nothing was scanned. This is not a clean result.\n' >&2
        return 2
    fi
    RANGE_COUNT="$n"
    return 0
}

# NO PIPE. `git log … | grep -q` looks equivalent and is not: grep exits at the
# first match and closes the pipe, git is killed by SIGPIPE, the pipeline's
# status becomes 141, and `set -o pipefail` propagates that -- so a body larger
# than the 64 KB pipe buffer reports NOT FOUND for the one reason that it WAS
# found. Measured before fixing: 4/16/32/60/64 KB found, 128 KB missed 10 runs
# out of 10. Audit pass 2b, P2. A shell case on a captured string has no pipe
# and no buffer.
scan() {
    local range="$1" found=0 c msg
    while read -r c; do
        [ -n "$c" ] || continue
        if ! msg=$(git log -1 --format='%B' "$c"); then
            printf 'cannot read the message of %s\n' "$c" >&2
            exit 2
        fi
        case "$msg" in
            *"$MARKER"*)
                printf '  %s\n' "$(git log -1 --format='%h %s' "$c")"
                found=1
                ;;
        esac
    done < <(git rev-list "$range")
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

    # P1. Exercises the SCRIPT, not scan(), because the defect was the main
    # body treating an unresolved range as an empty one -- and the first fix
    # for it was itself swallowed by a command-substitution subshell, which
    # scan() alone would never have shown.
    local self out2 st
    self=$(cd "$(dirname "$0")" && pwd)/$(basename "$0")
    out2=$(cd "$td" && bash "$self" main..nosuchref 2>&1); st=$?
    if [ $st = 2 ]; then
        echo "ok   an unresolvable range exits 2"
    else
        echo "FAIL unresolvable range exited $st, expected 2"; rc=1
    fi
    # Anchored: the refusal text itself contains the word "clean" in the
    # sentence "This is not a clean result", so a loose grep matches the
    # refusal and reports a failure that is not there. The verdict is the only
    # line that STARTS with it.
    if ! printf '%s\n' "$out2" | grep -q '^clean'; then
        echo "ok   and never gives the clean verdict for it"
    else
        echo "FAIL gave the clean verdict for a range it could not resolve"; rc=1
    fi
    out2=$(cd "$td" && bash "$self" main..topic 2>&1)
    if printf '%s' "$out2" | grep -qE 'scanning [0-9]+ commit bodies'; then
        echo "ok   reports how many bodies it read"
    else
        echo "FAIL did not report a commit count -- 'read 24' and 'read 0' look alike"; rc=1
    fi

    # P2. A body past the 64 KB pipe buffer. This passed with `git log | grep -q`
    # only because the pipeline's SIGPIPE status was read as "not found".
    (
        cd "$td" && git checkout -q -b big main &&
        { printf 'subject\n\n%s in the body\n' "$MARKER"; head -c 131072 /dev/zero | tr '\0' 'x'; echo; } > big.txt &&
        git commit -q --allow-empty -F big.txt
    ) || { echo "FAIL could not build the large-body fixture"; rc=1; }
    out2=$(cd "$td" && bash "$self" main..big 2>&1); st=$?
    if [ $st = 1 ]; then
        echo "ok   finds a marker in a body past the pipe buffer"
    else
        echo "FAIL a 128 KB body exited $st, expected 1 (the marker is in it)"; rc=1
    fi

    rm -rf "$td"
    [ $rc = 0 ] && echo "all fixtures pass" || echo "FIXTURES FAILED"
    return $rc
}

[ "${1:-}" = "--selftest" ] && { selftest; exit $?; }

RANGE="${1:-origin/master..HEAD}"
git rev-parse --git-dir >/dev/null 2>&1 || { echo "not a git repository" >&2; exit 2; }

resolve "$RANGE" || exit 2
echo "scanning $RANGE_COUNT commit bodies in $RANGE for the retired CI-skip marker"
if scan "$RANGE"; then
    echo "clean: $RANGE_COUNT commit bodies read, none carried it"
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
