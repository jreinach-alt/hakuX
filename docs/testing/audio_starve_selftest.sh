#!/usr/bin/env bash
#
# Check the APU's output-starvation accounting without building the emulator.
#
#   docs/testing/audio_starve_selftest.sh
#
# Why this exists in this shape. An agent worktree cannot build the native side
# (the Android build needs a JDK the fresh trees do not get, and nobody should
# be running ninja to check thirty lines of counter arithmetic), so the logic in
# monitor_sink_cb's accounting would otherwise ship with no check at all beyond
# reading it. The capture harness had the same problem and solved it the same
# way: lift the code out and run it against stubs.
#
# The lift is by ANCHOR, not by line number. An earlier version of this pasted a
# copy of the functions into the test, which is the version that rots: the copy
# and the original drift apart silently and the test then certifies code that is
# no longer in the tree. Extracting on every run means the test either exercises
# what apu.c currently says or fails to find it and says so.
#
# What it does NOT check: that apu.c compiles, that the counters are wired into
# monitor_sink_cb and se_frame, or anything about threading. Those need the real
# build and a real run. This checks the arithmetic and the reporting cadence,
# which is where the mistakes that matter live -- counting free_b instead of
# (free_b - copied) turns a 1% loss into a 100% one, and reporting cumulative
# totals instead of deltas makes one early burst read as permanent starvation.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../../hw/xbox/mcpx/apu/apu.c"
[ -f "$SRC" ] || { echo "cannot find $SRC" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The block runs from the comment that opens it to the line before se_frame,
# which is the first function after it. Both anchors are checked rather than
# assumed: a silent mis-extract would compile to an empty file and "pass".
START=$(grep -n '^ \* Output starvation accounting' "$SRC" | cut -d: -f1)
END=$(grep -n '^static void se_frame' "$SRC" | cut -d: -f1)
if [ -z "$START" ] || [ -z "$END" ]; then
    echo "anchors not found in apu.c -- the starvation block moved or was renamed." >&2
    echo "  '* Output starvation accounting' : ${START:-MISSING}" >&2
    echo "  'static void se_frame'           : ${END:-MISSING}" >&2
    exit 2
fi
# START-1 picks up the opening /* of the comment.
sed -n "$((START - 1)),$((END - 1))p" "$SRC" > "$TMP/apu_starve_extract.c"

for want in apu_starve_account apu_starve_report "struct {"; do
    grep -q "$want" "$TMP/apu_starve_extract.c" || {
        echo "extract is missing $want -- anchors matched but the block is wrong" >&2
        exit 2; }
done

CC="${CC:-gcc}"
"$CC" -std=gnu11 -Wall -Wextra -Wformat=2 -Werror \
      -I"$TMP" -I"$HERE" -o "$TMP/t" "$HERE/audio_starve_selftest.c" || {
    echo "the extracted accounting did not compile cleanly" >&2; exit 1; }
"$TMP/t"
