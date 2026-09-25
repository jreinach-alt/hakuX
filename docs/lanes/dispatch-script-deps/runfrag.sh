#!/usr/bin/env bash
# runfrag.sh <worktree> <fragment>...
#
# Source selected selftest.d fragments with the helpers selftest.sh defines
# (ok/bad/check, $T, $TESTING, gh and systemctl shims), without the rest of
# the suite. For iterating on one fragment; selftest.sh is still the gate.
set -u
WT=$1; shift
export HERE="$WT/docs/testing/jobs"; TESTING="$WT/docs/testing"; REPO="$WT"
T=$(mktemp -d "${TMPDIR:-/tmp}/frag.XXXXXX")
export HAKUX_WORK="$T/work" DISPATCH_DIR="$T/work/dispatch" GH_REPO="example/hakux"
mkdir -p "$T/bin" "$DISPATCH_DIR"/{queue,running,results}
cat > "$T/bin/gh" <<'G'
#!/usr/bin/env bash
exit 0
G
cat > "$T/bin/systemctl" <<'G'
#!/usr/bin/env bash
case "$*" in *is-active*) echo active ;; *show*ActiveEnterTimestamp*) date ;; *) exit 0 ;; esac
G
chmod +x "$T/bin/"*; export PATH="$T/bin:$PATH" SELFTEST_GH_LOG="$T/gh.log"; : > "$SELFTEST_GH_LOG"
pass=0; fail=0
ok()   { echo "  ok   $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
check() { local msg=$1; shift; if "$@" >/dev/null 2>&1; then ok "$msg"; else bad "$msg"; fi; }
for f in "$@"; do . "$HERE/selftest.d/$f"; done
echo "passed=$pass failed=$fail"
rm -rf "$T"
[ "$fail" -eq 0 ]
