#!/usr/bin/env bash
#
# Desktop build gate. Builds a ref and reports a verdict I can stand behind.
#
# Exists because the ad-hoc version of this filtered ninja's output through a
# grep and took $? from the end of the pipeline. That log then showed warnings
# and "[65/65] Linking target" and nothing else -- and ninja prints the status
# line when it STARTS an edge, so a filtered log like that is consistent with a
# link that failed. Never pipe ninja. Take its status directly.
#
# Usage: docs/testing/gate.sh <ref> [base-ref-for-changed-files]
#   Logs land in $GATE_OUT, else a fresh mktemp dir (path printed at the end).
set -uo pipefail

# Audit L5: this was hard-coded to /home/user/hakuX, which does not exist on
# other hosts, so the script could only ever run here. gate.sh lives at
# <repo>/docs/testing/gate.sh, so derive the root from the script's own
# location; GATE_REPO overrides for anyone who needs it elsewhere.
REPO="${GATE_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
REF="${1:?usage: gate.sh <ref> [base]}"
BASE="${2:-}"
# Logs go to a scratch dir, never beside the script: this lives in the repo
# and the tree has to stay clean.
OUT="${GATE_OUT:-$(mktemp -d -t nv2a-gate-XXXXXX)}"
# mktemp -d creates it; a caller-supplied GATE_OUT may not exist, and a
# failed log redirect takes every downstream check with it.
mkdir -p "$OUT" || { echo "cannot create $OUT" >&2; exit 2; }
LOG="$OUT/gate_$(echo "$REF" | tr -c 'A-Za-z0-9._-' '_').log"

# Audit L5: this cd was unchecked, so on a host without $REPO the script
# carried on in whatever directory it was invoked from and gated that.
cd "$REPO" || { echo "REFUSING: cannot cd to REPO=$REPO" >&2; exit 2; }

# grep -c prints 0 and exits 1 on no match; "|| true" keeps the 0 and drops the
# status. Do NOT add "|| echo 0" -- that prints a second 0.
count() { [ -f "$2" ] || { echo 0; return; }; grep -cE "$1" "$2" || true; }

# One emulator at a time: never rebuild under a live run.
#
# This was "pgrep -x qemu-system-i386" and was INERT -- it never fired once.
# "qemu-system-i386" is 16 characters, the kernel caps /proc/N/comm at 15, and
# pgrep -x compares against comm. Measured against a live 16-character process:
# "pgrep -x qemu-system-i386" -> rc=1 (no match), "pgrep -x qemu-system-i38"
# -> rc=0. pgrep says so on stderr; the old line discarded it with 2>&1.
#
# "pgrep -f qemu-system-i386" is the other trap: the pattern would then sit in
# this script's own argv on some invocations and match the caller.
#
# Compare the exec'd binary's real basename instead -- untruncated, and our own
# shell's exe is bash, so it cannot match the caller. A binary replaced by a
# rebuild reads back as "<path> (deleted)", so strip that suffix.
emulator_pids() {
    local p exe
    for p in /proc/[0-9]*; do
        exe=$(readlink "$p/exe" 2>/dev/null) || continue
        exe="${exe% (deleted)}"
        [ "${exe##*/}" = "qemu-system-i386" ] && printf '%s ' "${p#/proc/}"
    done
    # Audit L4: without this the function's status is whatever that test
    # returned for the LAST /proc entry -- almost always 1, i.e. "failed" --
    # which is wrong for a function whose result is its stdout. Harmless today
    # only because the caller reads the output and the script is not set -e.
    return 0
}
RUNNING="$(emulator_pids)"
if [ -n "$RUNNING" ]; then
    echo "REFUSING: qemu-system-i386 is running (pid(s): $RUNNING);" >&2
    echo "          a rebuild would pull it apart." >&2
    exit 2
fi

if [ -n "$(git status --porcelain)" ]; then
    echo "REFUSING: working tree is dirty. Gate only clean trees." >&2
    git status --porcelain >&2
    exit 2
fi

WAS="$(git symbolic-ref --quiet --short HEAD || git rev-parse HEAD)"
restore() {
    echo "--- restoring $WAS and rebuilding my own head ---"
    git checkout --quiet "$WAS" || { echo "COULD NOT RESTORE $WAS" >&2; return; }
    ninja -C build qemu-system-i386 >"$OUT/restore.log" 2>&1
    echo "restore NINJA_EXIT=$?  (log: $OUT/restore.log)"
}
trap restore EXIT

git checkout --quiet --detach "$REF" || exit 2
SHA="$(git rev-parse --short=8 HEAD)"

: >"$LOG"
ninja -C build qemu-system-i386 >"$LOG" 2>&1
RC=$?
echo "NINJA_EXIT=$RC" >>"$LOG"

COMPILES=$(count '^\[[0-9]+/[0-9]+\] Compiling' "$LOG")
NOWORK=$(count '^ninja: no work to do\.' "$LOG")
FAILS=$(count 'FAILED:|error:' "$LOG")
LINK=$(grep -E '^\[[0-9]+/[0-9]+\] Linking' "$LOG" | tail -1)

echo "================ GATE $SHA ================"
echo "NINJA_EXIT   = $RC          <-- the line that decides it"
echo "compile steps= $COMPILES"
echo "no-work      = $NOWORK        <-- 1 = already up to date, a legitimate 0-compile run"
echo "FAILED/error = $FAILS"
echo "link line    : ${LINK:-<none>}"
if [ -f build/qemu-system-i386 ]; then
    echo "binary       : $(stat -c '%s bytes, mtime %y' build/qemu-system-i386)"
fi

echo "--- warning families ---"
grep -oE '\[-W[a-z=-]+\]' "$LOG" | sort | uniq -c | sort -rn || true
# Count every warning site, and write the count INTO the log as well as to
# stdout. Both halves of that were wrong and the two mistakes compounded.
#
# The old pattern was '\.\./[a-z0-9_/-]+\.c', which required the ../ prefix,
# matched only .c, and allowed only lowercase path characters -- so it missed
# every warning in a header. On 2026-09-13 that was four sites
# (accel/tcg/tb-cache-hints.h x2, vk/stb_image_write.h x2) and the count read
# 70 against a true 74.
#
# And because the number went to stdout only, a later comparison had to be
# made against a differently-counted figure or recomputed by hand off the log,
# which is exactly what happened: two counters were quoted as one series and a
# fold that was flat was reported as four warnings better. A number is only a
# series if it was produced the same way every time, so the log now carries it.
SITES=$(grep -oE '^(\.\./)?[^ ]+\.[ch]:[0-9]+:[0-9]+: warning' "$LOG" \
        | sed 's|^\.\./||' | sort -u | wc -l)
echo "distinct warning sites: $SITES" | tee -a "$LOG"

# SCOPE, and it is the whole reason a warning count can mislead: ninja only
# recompiles what is out of date, so these warnings cover ONLY the files this
# run compiled -- not the tree. A fold gate typically compiles 79 of 1377
# objects, 5.7%. "The tree carries 57 warning sites" was recorded from a run
# that compiled 62. Print the denominator so the number cannot travel without
# it; for the real inventory do a clean build (ninja -t clean first).
# Audit L7: this counted *.c.o files that ALREADY EXIST under build/, so the
# denominator was neither the tree's object count nor a constant -- smaller on
# a fresh tree, excluding every C++ object, and growing as builds accumulate.
# COMPILES counts "Compiling C object" AND "Compiling C++ object", so take the
# matching denominator from the BUILD DESCRIPTION, which does not depend on
# what happens to be on disk.
OBJS=$(ninja -C build -t commands qemu-system-i386 2>/dev/null | grep -c ' -c ')
if [ "${OBJS:-0}" -gt 0 ]; then
    echo "warning scope : $COMPILES of $OBJS compile steps in this target -- warnings cover ONLY these" | tee -a "$LOG"
else
    echo "warning scope : $COMPILES compile steps this run -- warnings cover ONLY these (denominator unavailable)" | tee -a "$LOG"
fi

# Compare with a previous gate's log by file+MESSAGE, never file:line -- a
# function inserted upstream shifts every later line, so the same warning reads
# as one removal plus one addition. ac829cd8 -> 08b4219a scored 30 gone / 27 new
# by line; by file+message over the files BOTH runs compiled it is 1 removal and
# 0 additions. Keying alone is not enough -- see the intersection below.
if [ -n "${PREV_LOG:-}" ] && [ -f "$PREV_LOG" ]; then
    keyed() { grep -oE '^(\.\./)?[^ ]+\.[ch]:[0-9]+:[0-9]+: warning: .*' "$1" \
        | sed 's|^\.\./||; s|:[0-9]*:[0-9]*: warning: |  ::  |' | sort -u; }
    objs()  { grep -oE 'Compiling C object [^ ]+' "$1" | sed 's/.*object //' | sort -u; }

    # Only files COMPILED IN BOTH runs can be compared. Otherwise a warning
    # missing from one side may just not have been rebuilt: gating HEAD after a
    # 4-object incremental against a 79-object log reports 63 "removed", none of
    # which was fixed. meson names an object by replacing '/' with '_', so a
    # source path maps to its object that way -- preceded by '/' after the '.p/'
    # directory, or by '_' inside the name, hence the [/_] anchor.
    objs "$PREV_LOG" > "$OUT/.objs_prev"; objs "$LOG" > "$OUT/.objs_this"

    # Audit M3: this mapped a source path to a meson object name, and objects
    # are named after .c files -- so a HEADER could never enter the
    # intersection and its warnings were silently dropped from the delta. That
    # is two commits after the census regex was widened to .[ch] *because*
    # headers were being missed, and the shared-header case is exactly the one
    # a delta is most useful for. ninja records the real dependency graph, so
    # ask it: a header is comparable when ANY object depending on it was
    # compiled in both runs.
    #
    # Audit L6: ${m} carries the source's own dots (translate-all.c ->
    # ..._translate-all.c), and an unescaped '.' in an ERE matches any
    # character. Escape them.
    ninja -C build -t deps 2>/dev/null \
        | awk '/^[^ ]/ { obj = substr($1, 1, length($1) - 1) } /^ / { print obj "\t" $1 }' \
        > "$OUT/.deps" || : > "$OUT/.deps"

    cat <(keyed "$PREV_LOG") <(keyed "$LOG") | sed 's/  ::.*//' | sort -u \
    | while read -r src; do
        case "$src" in
        *.h)
            # Objects whose recorded deps mention this header, in both runs.
            hit=0
            while read -r obj; do
                grep -qxF "$obj" "$OUT/.objs_prev" \
                    && grep -qxF "$obj" "$OUT/.objs_this" \
                    && { hit=1; break; }
            done < <(grep -F "	" "$OUT/.deps" | grep -F "/$src" | cut -f1 | sort -u)
            [ "$hit" -eq 1 ] && printf '%s\n' "$src"
            ;;
        *)
            m=$(printf '%s' "$src" | tr '/' '_' | sed 's/\./\\./g')
            grep -qE "[/_]${m}\.o$" "$OUT/.objs_prev" \
                && grep -qE "[/_]${m}\.o$" "$OUT/.objs_this" \
                && printf '%s\n' "$src"
            ;;
        esac
      done > "$OUT/.common_src"

    # Audit L6: this was `grep -Ff .common_src`, matching each source path as an
    # unanchored SUBSTRING of the keyed line -- so a path that is a prefix of
    # another (gl/texture.c against vk/texture.c, say) pulled in the wrong
    # file's warnings. The keyed form is "path  ::  message", so match the
    # first field exactly instead.
    incommon() {
        keyed "$1" | awk -F'  ::  ' \
            'NR == FNR { ok[$0] = 1; next } ok[$1]' "$OUT/.common_src" - | sort -u
    }
    echo "--- real warning delta vs $(basename "$PREV_LOG") ---"
    echo "keyed on file+message (line drift removed), restricted to the" \
         "$(wc -l < "$OUT/.common_src") warning-carrying files compiled in BOTH runs"
    echo "removed:"; comm -23 <(incommon "$PREV_LOG") <(incommon "$LOG") | sed 's/^/  /'
    echo "added:";   comm -13 <(incommon "$PREV_LOG") <(incommon "$LOG") | sed 's/^/  /'
    echo "(end)"
fi

if [ -n "$BASE" ]; then
    echo "--- warning sites in files changed by $BASE..$SHA ---"
    # Same widened pattern as SITES above: the old one excluded .h and any
    # path containing a dot, and read 67 against 71 actual on one run.
    grep -oE '^(\.\./)?[^ ]+\.[ch]:[0-9]+:[0-9]+: warning: .*' "$LOG" \
        | sed 's|^\.\./||' | sort -u >"$OUT/.sites"
    git diff --name-only "$BASE".."$SHA" -- '*.c' '*.h' | while read -r f; do
        grep -F "$f:" "$OUT/.sites" || true
    done
    echo "(end)"
fi

if [ "$COMPILES" -eq 0 ] && [ "$NOWORK" -eq 0 ]; then
    echo "VERDICT: UNSOUND -- log shows neither compiles nor 'no work to do';"
    echo "         it was filtered, so NINJA_EXIT cannot be attributed. Re-run."
elif [ "$RC" -eq 0 ] && [ "$FAILS" -eq 0 ] && { [ -n "$LINK" ] || [ "$NOWORK" -eq 1 ]; }; then
    echo "VERDICT: PASS"
else
    echo "VERDICT: FAIL -- do not report PASS from this run"
fi
echo "log: $LOG"
