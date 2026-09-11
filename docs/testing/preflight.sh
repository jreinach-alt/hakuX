#!/usr/bin/env bash
# Run the gates CI runs, here, before pushing.
#
# The workflows that fire on a pull request are Android, Desktop build and
# NV2A index -- about thirteen minutes of hosted runner time per push, and
# Actions minutes are a limited monthly budget. Two of those three gates are
# reproducible locally in seconds, so a push that has passed this script
# should not need CI to tell it anything.
#
#   docs/testing/preflight.sh [--tests DIR] [--support DIR]
#
# Exits non-zero and says which gate failed. Run it before every push; put
# [skip ci] in the commit message when it passes and the change cannot affect
# a platform this script does not build (Android, macOS, Windows).

set -u
cd "$(dirname "$0")/../.." || exit 2

# The test sources live wherever the lane put them; $HOME differs between the
# desktop container and a workstation, so look rather than assume.
find_repo() {
    for d in "$HOME/$1" /home/user/"$1" /home/justin/"$1" "$PWD/../$1"; do
        [ -d "$d/.git" ] && { echo "$d"; return; }
    done
}
TESTS=${TESTS:-$(find_repo nxdk_pgraph_tests)}
SUPPORT=${SUPPORT:-$(find_repo pbkitplusplus)}
while [ $# -gt 0 ]; do
    case "$1" in
        --tests) TESTS="$2"; shift 2 ;;
        --support) SUPPORT="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

fail=0
step() { printf '%-28s' "$1"; }
ok()   { echo "ok"; }
bad()  { echo "FAILED"; fail=1; }

# 1. psh_differ, as .github/workflows/desktop.yml runs it. carve.py refuses to
#    carve a function it was not told about, so a new PGRAPHState reader in
#    psh.c stops the build here rather than on a runner.
step "psh_differ build"
if make -C docs/testing/psh_differ >/tmp/preflight-make.log 2>&1; then ok; else
    bad; tail -5 /tmp/preflight-make.log
fi

if [ $fail -eq 0 ]; then
    step "psh_differ report"
    ./docs/testing/psh_differ/build/psh-differ >/tmp/preflight-differ.log 2>/tmp/preflight-differ.err
    if grep -q 'does not generate' /tmp/preflight-differ.err; then
        bad; echo "  a baseline no longer generates a shader:"; head -5 /tmp/preflight-differ.err
    elif ! grep -q '^TOTAL' /tmp/preflight-differ.log; then
        bad; echo "  produced no report"; tail -5 /tmp/preflight-differ.log
    else
        ok; grep -E '^TOTAL' /tmp/preflight-differ.log | sed 's/^/  /'
    fi
fi

# 2. The nv2a index, as .github/workflows/nv2a-index.yml runs it. It records
#    site line numbers, so ANY commit touching hw/xbox has to carry a
#    regenerated index or this goes red on the next push.
step "nv2a index"
if [ -z "$TESTS" ] || [ ! -d "$TESTS" ]; then
    bad
    echo "  cannot find nxdk_pgraph_tests, so this gate did not run."
    echo "  Pass --tests DIR. Do not push on an unchecked index: it is the"
    echo "  gate that fails most often, because it records source line numbers."
elif python3 docs/testing/nv2a_index.py check --tests "$TESTS" \
        ${SUPPORT:+--support "$SUPPORT"} >/tmp/preflight-index.log 2>&1; then
    ok
else
    bad
    sed 's/^/  /' /tmp/preflight-index.log
    echo "  regenerate: python3 docs/testing/nv2a_index.py build --tests $TESTS --support $SUPPORT"
fi

echo
if [ $fail -eq 0 ]; then
    echo "preflight passed - safe to push"
else
    echo "preflight FAILED - fix before pushing, do not spend a CI run finding out"
fi
exit $fail
