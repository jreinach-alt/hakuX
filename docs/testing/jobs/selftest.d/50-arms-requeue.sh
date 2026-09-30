# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh: an errored arm can be queued again, which is what the ARM ERROR
# comment promises.
#
# Clears the markers 20/30 left and drives the whole queue itself, so it must
# run after them. LAST of the arms fragments.

# SCRATCH GUARD (lane.dispatchguard). This fragment empties $DISPATCH_DIR's
# queue and results and $HAKUX_WORK's arms markers. selftest.sh points both at
# a fresh mktemp tree; a script that sources the fragment any other way points
# them at whatever the caller exported -- on a lane host, the live dispatch
# dir. On 2026-09-29 the live queue and results were emptied twice in five
# minutes that way. So refuse, before any rm, unless all three hold:
#   1. DISPATCH_DIR and HAKUX_WORK are exactly $T/work/dispatch and $T/work;
#   2. $T sits strictly below a tmp root (${TMPDIR:-/tmp} or /tmp);
#   3. none of T, HAKUX_WORK, DISPATCH_DIR is inside, or contains,
#      $HOME/hakux-work.
# Paths are compared as realpaths. Run a fragment alone with
# `SELFTEST_ONLY=NN-name bash docs/testing/jobs/selftest.sh`. The same block is
# in 50-arms-requeue.sh and 51-dispatch-hardening.sh; keep them identical.
_dg_real() { realpath -m -- "$1" 2>/dev/null; }
_dg_scratch() {   # -> 0, or 1 with the reason on stdout
    local t d w p l tmp=no
    [ -n "${T:-}" ] && [ -n "${DISPATCH_DIR:-}" ] && [ -n "${HAKUX_WORK:-}" ] \
        || { echo "T, DISPATCH_DIR and HAKUX_WORK must all be set"; return 1; }
    t=$(_dg_real "$T"); d=$(_dg_real "$DISPATCH_DIR"); w=$(_dg_real "$HAKUX_WORK")
    [ -n "$t" ] && [ "$d" = "$t/work/dispatch" ] && [ "$w" = "$t/work" ] \
        || { echo "DISPATCH_DIR and HAKUX_WORK are not \$T/work/dispatch and \$T/work"; return 1; }
    for p in "$(_dg_real "${TMPDIR:-/tmp}")" /tmp; do
        case "$t/" in "$p"/?*/) tmp=yes ;; esac
    done
    [ "$tmp" = yes ] || { echo "T=$t is not below \${TMPDIR:-/tmp} or /tmp"; return 1; }
    [ -n "${HOME:-}" ] || return 0
    l=$(_dg_real "$HOME/hakux-work")
    for p in "$t" "$w" "$d"; do
        case "$p/" in "$l"/*) echo "$p is inside the live $l"; return 1 ;; esac
        case "$l/" in "$p"/*) echo "$p contains the live $l"; return 1 ;; esac
    done
}
if ! _dg_why=$(_dg_scratch); then
    echo "SELFTEST GUARD: ${BASH_SOURCE[0]##*/} refuses to run, nothing removed: $_dg_why" \
         "(T=${T:-} DISPATCH_DIR=${DISPATCH_DIR:-} HAKUX_WORK=${HAKUX_WORK:-})." \
         "Run it through selftest.sh: SELFTEST_ONLY=${BASH_SOURCE[0]##*/} bash docs/testing/jobs/selftest.sh" >&2
    fail=$((${fail:-0} + 1))
    return 1 2>/dev/null || exit 1
fi

echo "== arms.sh: an errored arm can be queued again, which is what the ARM ERROR comment promises"
# The ARM ERROR comment tells the lane to delete the pair and judged markers to
# have the job queue the arm again. It could not work: the errored result's
# request.json still carried the expect_sha, so already_ran matched it forever.
# Measured 2026-09-19, when #89's arm failed to build on both sides because
# meson was not on the daemon's PATH -- a host fault the lane could do nothing
# about and could not retry past either.
clear_markers() { rm -f "$HAKUX_WORK"/arms/judged/* "$HAKUX_WORK"/arms/pairs/*.json; }
finish_queue() {   # <marker-file-or-"">: turn the queue into results, erroring them or not
    local q id d
    for q in "$DISPATCH_DIR"/queue/*.req; do
        [ -f "$q" ] || continue
        id=$(basename "$q" .req); d="$DISPATCH_DIR/results/$id"
        mkdir -p "$d"; mv "$q" "$d/request.json"
        [ -n "$1" ] && echo simulated > "$d/$1"
    done
}
clear_markers; rm -f "$DISPATCH_DIR"/queue/*.req
bash "$HERE/arms.sh" >/dev/null 2>&1          # queue the pair afresh
finish_queue ERROR                            # both arms ran and ERRORed
clear_markers
bash "$HERE/arms.sh" >/dev/null 2>&1
check "an ERROR result is not a run, so the pair can be queued again" \
    [ "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)" -ge 2 ]
finish_queue ""                               # this time both arms completed
clear_markers
bash "$HERE/arms.sh" >/dev/null 2>&1
check "a completed result IS a run, so the pair is not queued again" \
    [ "$(ls "$DISPATCH_DIR"/queue/*.req 2>/dev/null | wc -l)" -eq 0 ]
