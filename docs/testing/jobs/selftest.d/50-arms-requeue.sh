# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# arms.sh: an errored arm can be queued again, which is what the ARM ERROR
# comment promises.
#
# Clears the markers 20/30 left and drives the whole queue itself, so it must
# run after them. LAST of the arms fragments.

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
