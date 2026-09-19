#!/usr/bin/env bash
#
# Fixtures for pgraph_capture_run.sh's refusals. No emulator, no firmware, no
# disc, no X server: every external part is a stub, so this runs on a cloud
# lane's container in under a second.
#
# WHY THIS EXISTS
#
# Audit pass 2 on PR #162 (N2, MEDIUM) found the runner naming the
# mislabelled-renderer hazard in a comment and then not failing on it: it
# checked that SOME renderer was reported and never compared it to the one
# requested. A run that asked for OPENGL and came up on Vulkan exited 0 with
# 236 captures under the OPENGL tag.
#
# The fix is six lines. This file is the part that makes it a check rather than
# a claim, because the fix was first asserted in a commit message and a commit
# message is not a fixture. The three cases are deliberately a mutant/control
# set: case 1 needs the comparison to fire, and case 2 needs it NOT to fire, so
# a blanket `die` -- the cheapest way to pass case 1 -- fails case 2. Each case
# asserts on the words in the message, not the exit status: the runner exits
# non-zero for a dozen other reasons, so an exit code cannot tell which refusal
# happened (or whether any did).
#
# Usage:
#   docs/testing/pgraph_capture_run_selftest.sh
#
# Environment:
#   SELFTEST_TMP  scratch directory to use instead of `mktemp -d`, for a
#                 sandbox that permits writes only under the worktree. It is
#                 emptied on entry, so pass a directory you own.
#   RUNNER        the script under test, for pointing these fixtures at a
#                 mutant copy. That is how the fixtures themselves were
#                 checked: with the six-line comparison deleted from a scratch
#                 copy, case 1's three message assertions go red and cases 2
#                 and 3 are unmoved -- so the set catches the defect it was
#                 written for and is specific to it. `mismatch-never-extracts`
#                 stayed green on that mutant and is the weakest of the four:
#                 a mutant runner cannot reach the extractor anyway. The three
#                 that name words in the message are the discriminating ones.
#
# exit 0 all fixtures pass, 1 a fixture failed.

set -u

HERE=$(cd "$(dirname "$0")" && pwd)
RUNNER="${RUNNER:-$HERE/pgraph_capture_run.sh}"
[ -x "$RUNNER" ] || { echo "selftest: no runner at $RUNNER" >&2; exit 1; }

if [ -n "${SELFTEST_TMP:-}" ]; then
    T="$SELFTEST_TMP"
    rm -rf "$T"; mkdir -p "$T" || exit 1
else
    T=$(mktemp -d) || exit 1
    trap 'rm -rf "$T"' EXIT
fi
# Absolute, for the same reason the runner absolutises BIN and ISO: it cd's
# into the binary's directory, so a relative `$T/stub` on PATH stops resolving
# the moment the run starts. That cost this file one debugging cycle, and the
# symptom was case 3 passing for the wrong reason -- no renderer was reported
# because xvfb-run could not be found, not because the stub was silent. Hence
# the stub-actually-ran assertion on every case below.
T=$(cd "$T" && pwd) || exit 1

mkdir -p "$T/stub" "$T/fw" "$T/out"

# xvfb-run, minus the X server: drop the two flags the runner passes and exec
# the rest. The runner's `command -v xvfb-run` precondition is satisfied by
# this file existing on PATH, which is the point -- a machine with no xvfb-run
# can still exercise the refusals.
cat > "$T/stub/xvfb-run" <<'STUB'
#!/usr/bin/env bash
while [ $# -gt 0 ]; do
    case "$1" in
        -a|--auto-servernum) shift ;;
        --server-args=*) shift ;;
        --server-args) shift; shift ;;
        *) break ;;
    esac
done
exec "$@"
STUB
chmod +x "$T/stub/xvfb-run"

# The emulator, reduced to the one line the runner parses. $1 is the renderer
# name to claim -- xemu prints the SELECTED one (pgraph.c, after the fallback
# chooser), which is exactly why a stub can stand in for it here.
make_xemu() {
    cat > "$T/xemu-$1" <<STUB
#!/usr/bin/env bash
echo 'nv2a: init'
$2
echo 'nv2a: shutdown'
exit 0
STUB
    chmod +x "$T/xemu-$1"
}
make_xemu reports-vulkan "echo 'nv2a: renderer: Vulkan'"
make_xemu reports-opengl "echo 'nv2a: renderer: OpenGL'"
make_xemu reports-nothing ":"

: > "$T/fw/mcpx_1.0.bin"; : > "$T/fw/flash.bin"; : > "$T/fw/eeprom.bin"
echo iso > "$T/disc.iso"
echo hdd > "$T/pristine.qcow2"

run_case() {   # run_case <tag> <binary> <RENDERER>
    PATH="$T/stub:$PATH" \
    RENDERER="$3" OUTDIR="$T/out" XEMU_DATA="$T/fw" \
    PRISTINE="$T/pristine.qcow2" TIMEOUT=30 \
        bash "$RUNNER" "$2" "$T/disc.iso" "$1" > "$T/$1.out" 2> "$T/$1.err"
    echo $?
}

failed=0
check() {      # check <name> <file> <want|want-not> <pattern>
    local name=$1 file=$2 mode=$3 pat=$4 hit=ok
    if grep -qF -- "$pat" "$file"; then
        [ "$mode" = want ] || hit=FAIL
    else
        [ "$mode" = want-not ] || hit=FAIL
    fi
    [ "$hit" = ok ] || failed=$((failed + 1))
    printf '%-4s %-46s %s "%s"\n' "$hit" "$name" "$mode" "$pat"
}

echo '--- 1: requested OPENGL, the run came up on Vulkan (N2'"'"'s scenario)'
rc=$(run_case mismatch "$T/xemu-reports-vulkan" OPENGL)
check mismatch-stub-ran          "$T/out/run_mismatch.log" want 'nv2a: init'
check mismatch-refuses           "$T/mismatch.err" want     'renderer mismatch'
check mismatch-names-both        "$T/mismatch.err" want     'asked for OPENGL, ran Vulkan'
check mismatch-says-discarded    "$T/mismatch.err" want     'discarded rather than scored'
check mismatch-never-extracts    "$T/mismatch.out" want-not 'captures in'
[ "$rc" != 0 ] || { echo "FAIL mismatch-exit-nonzero (got $rc)"; failed=$((failed + 1)); }

echo '--- 2: requested OPENGL and got OpenGL -- the gate must NOT fire'
rc=$(run_case match "$T/xemu-reports-opengl" OPENGL)
check match-stub-ran             "$T/out/run_match.log" want 'nv2a: init'
check match-no-mismatch          "$T/match.err" want-not 'renderer mismatch'
check match-reached-the-extract  "$T/match.err" want     'nothing on E:'
check match-logged-the-pair      "$T/match.out" want     'requested=OPENGL got=OpenGL'

echo '--- 3: no renderer line at all -- the pre-existing refusal still fires'
rc=$(run_case silent "$T/xemu-reports-nothing" VULKAN)
check silent-stub-ran            "$T/out/run_silent.log" want 'nv2a: init'
check silent-refuses             "$T/silent.err" want     'never reported a renderer'
check silent-not-a-mismatch      "$T/silent.err" want-not 'renderer mismatch'

if [ "$failed" -eq 0 ]; then
    echo 'all fixtures pass'
else
    echo "$failed assertion(s) FAILED"
fi
exit $(( failed ? 1 : 0 ))
