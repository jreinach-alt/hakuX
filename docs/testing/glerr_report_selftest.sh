#!/usr/bin/env bash
#
# Check gl/shaders.c's Android GL-error report (#86) without an NDK.
#
#   docs/testing/glerr_report_selftest.sh
#
# Why this exists in this shape. The block under test is inside #ifdef
# __ANDROID__, and an agent worktree has no NDK, no device and no arm64 build
# -- #86 was filed rather than fixed for exactly that reason. The same trick
# audio_starve_selftest.sh uses works here: lift the block out by anchor and
# compile it with the host compiler against stubs. Lifting by anchor rather
# than pasting a copy means the test exercises what shaders.c says today, or
# fails to find it and says so.
#
# Three builds, because two different things can go wrong:
#
#   desktop  the host header set, where GL_STACK_OVERFLOW and friends exist
#   gles     -DGLES_LIKE, where they do not -- the Android header set, and the
#            reason gl_error_name guards those cases with #ifdef
#   silent   the same slice with the body of android_report_pending_gl_errors
#            put back to the pre-#86 `while (glGetError() != GL_NO_ERROR) {}`
#
# The third build is the falsifier, and it is asserted on its OUTPUT, not its
# exit code: the helpers are kept so that it still compiles and still runs, and
# a build that merely failed to compile would "fail" for free while testing
# nothing. It has to fail by naming the legs about reporting.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../../hw/xbox/nv2a/pgraph/gl/shaders.c"
HARNESS="$HERE/glerr_report_selftest.c"
[ -f "$SRC" ] || { echo "cannot find $SRC" >&2; exit 2; }
[ -f "$HARNESS" ] || { echo "cannot find $HARNESS" >&2; exit 2; }

CC="${CC:-cc}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The slice runs from gl_error_name to the closing brace of
# android_report_pending_gl_errors. Both anchors are checked rather than
# assumed: a silent mis-slice would compile to nothing and "pass".
python3 - "$SRC" "$TMP/block.inc" <<'PY' || exit 2
import sys

src, out = sys.argv[1], sys.argv[2]
lines = open(src).read().splitlines(True)

def find(pred, after=-1):
    for i, line in enumerate(lines):
        if i > after and pred(line):
            return i
    return None

start = find(lambda l: l.startswith("static const char *gl_error_name("))
report = find(lambda l: l.startswith(
    "static void android_report_pending_gl_errors("))
if start is None or report is None or report < start:
    sys.exit("anchors not found in %s -- the #86 block moved or was renamed."
             % src)
end = find(lambda l: l == "}\n", after=report)
if end is None:
    sys.exit("no closing brace after android_report_pending_gl_errors")

block = "".join(lines[start:end + 1])
for want in ("glGetError", "__android_log_print", "[glerr]"):
    if want not in block:
        sys.exit("sliced block has no %r in it -- wrong anchors?" % want)
open(out, "w").write(block)
print("sliced lines %d..%d of shaders.c" % (start + 1, end + 1))
PY

# The pre-#86 block: same slice, report body restored to silence. The helpers
# stay so the falsification build still compiles and still runs every leg.
python3 - "$TMP/block.inc" "$TMP/silent.inc" <<'PY' || exit 2
import sys

src, out = sys.argv[1], sys.argv[2]
head, sep, _ = open(src).read().partition(
    "static void android_report_pending_gl_errors(const ShaderBinding *binding)")
if not sep:
    sys.exit("cannot find the report function to silence")
open(out, "w").write(head + sep + """
{
    (void)binding;
    while (glGetError() != GL_NO_ERROR) {
        /* Clear any prior GL error to avoid aborting on Android. */
    }
}
""")
PY

build() {  # build <name> <block.inc> [extra cflags...]
    local name="$1" block="$2"; shift 2
    "$CC" -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function \
          -DBLOCK_INC="\"$block\"" "$@" -o "$TMP/$name" "$HARNESS" || {
        echo "$name: build failed" >&2
        return 1
    }
}

rc=0

build desktop "$TMP/block.inc"              || exit 1
build gles    "$TMP/block.inc" -DGLES_LIKE  || exit 1
build silent  "$TMP/silent.inc"             || exit 1

for arm in desktop gles; do
    echo "== $arm"
    out="$("$TMP/$arm")"
    echo "$out"
    case "$out" in
        *"all checks passed"*) ;;
        *) echo "$arm: did not pass" >&2; rc=1 ;;
    esac
done

echo "== silent (pre-#86 falsification: this build MUST fail, and by name)"
out="$("$TMP/silent" || true)"
echo "$out"
for leg in \
    "FAIL first pending error" \
    "FAIL the line carries the [glerr] tag" \
    "FAIL names the enum" \
    "FAIL names the shader" \
    "FAIL a distinct enum is reported" \
    "FAIL every occurrence of a repeat prints" \
    "FAIL ten distinct enums" \
    "FAIL the report index counts up" \
    "FAIL past the budget the line count"
do
    case "$out" in
        *"$leg"*) ;;
        *) echo "silent build did not fail on: $leg" >&2; rc=1 ;;
    esac
done
# ... and it must still pass the legs that are not about reporting, or it is
# failing because the harness broke rather than because the drain is silent.
for leg in \
    "ok   no pending error" \
    "ok   the backlog is fully drained" \
    "ok   past the budget the backlog is still drained"
do
    case "$out" in
        *"$leg"*) ;;
        *) echo "silent build broke a leg that is not about reporting: $leg" >&2
           rc=1 ;;
    esac
done

[ "$rc" -eq 0 ] && echo "glerr_report_selftest: PASS"
exit "$rc"
