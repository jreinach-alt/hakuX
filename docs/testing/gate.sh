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

REPO=/home/user/hakuX
REF="${1:?usage: gate.sh <ref> [base]}"
BASE="${2:-}"
# Logs go to a scratch dir, never beside the script: this lives in the repo
# and the tree has to stay clean.
OUT="${GATE_OUT:-$(mktemp -d -t nv2a-gate-XXXXXX)}"
# mktemp -d creates it; a caller-supplied GATE_OUT may not exist, and a
# failed log redirect takes every downstream check with it.
mkdir -p "$OUT" || { echo "cannot create $OUT" >&2; exit 2; }
LOG="$OUT/gate_$(echo "$REF" | tr -c 'A-Za-z0-9._-' '_').log"

cd "$REPO"

# grep -c prints 0 and exits 1 on no match; "|| true" keeps the 0 and drops the
# status. Do NOT add "|| echo 0" -- that prints a second 0.
count() { [ -f "$2" ] || { echo 0; return; }; grep -cE "$1" "$2" || true; }

# One emulator at a time: never rebuild under a live run. -x matches the process
# name only, so this cannot match our own shell the way "pgrep -f" would.
if pgrep -x qemu-system-i386 >/dev/null 2>&1; then
    echo "REFUSING: qemu-system-i386 is running; a rebuild would pull it apart." >&2
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

if [ -n "$BASE" ]; then
    echo "--- warning sites in files changed by $BASE..$SHA ---"
    grep -oE '\.\./[a-z0-9_/-]+\.c:[0-9]+:[0-9]+: warning: .*' "$LOG" \
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
