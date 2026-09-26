#!/usr/bin/env bash
#
# Walk a list of commits and report a suite's bit-identical count at each.
#
#   bisect_suite.sh "Texture render target" trt <sha> <sha> <sha> ...
#
# Answers "which commit changed this suite" without a human watching. Each step
# is a ~20s incremental build and a ~40s run, so a dozen commits is a quarter of
# an hour -- cheap enough to prefer over reasoning about which change was
# probably responsible.
#
# Only hw/ and ui/ are moved to the commit under test; docs and tooling stay at
# HEAD so the harness scoring the result is the same one throughout. That is an
# approximation -- a commit whose rendering change depends on a tooling change
# will not reproduce exactly -- but it keeps the build incremental, which is the
# difference between fifteen minutes and four hours.
#
# The tree is restored on exit, including after an interrupt.
set -u

SUITE="${1:?usage: bisect_suite.sh <suite name> <guest-dir> <sha>...}"
GUEST="${2:?}"
shift 2
SHAS=("$@")
[ "${#SHAS[@]}" -gt 0 ] || { echo "give at least one commit"; exit 2; }

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${HAKUX_WORK:-$HOME/hakux-work}"
GOLDENS="${GOLDENS:-$HOME/goldens/results}"
ISO="$WORK/iso-bisect.iso"
RESULTS_NAME="${SUITE// /_}"

cd "$REPO"
restore() {
    git checkout -q HEAD -- hw/ ui/ 2>/dev/null
    echo "tree restored to HEAD"
}
trap restore EXIT INT TERM

git diff --quiet -- hw/ ui/ || { echo "hw/ or ui/ is dirty; commit or stash first"; exit 1; }

mkdir -p "$WORK"
python3 docs/testing/make_test_iso.py "${BASE_ISO:-$HOME/nxdk_pgraph_tests_xiso.iso}" \
    -o "$ISO" --progress-log --shutdown-on-completion \
    --output-dir "e:/$GUEST" --suite "$SUITE" >/dev/null || exit 1

printf '%-14s %-6s %s\n' "commit" "exact" "subject"
printf '%s\n' "--------------------------------------------------------------"

for sha in "${SHAS[@]}"; do
    git checkout -q "$sha" -- hw/ ui/ || { echo "$sha: checkout failed"; continue; }
    ( cd android && ./gradlew --no-daemon assembleDebug ) > "$WORK/bisect-build.log" 2>&1
    if [ $? -ne 0 ]; then
        printf '%-14s %-6s %s\n' "${sha:0:10}" "BUILD" "$(git log -1 --format=%s "$sha")"
        continue
    fi
    adb ${SERIAL:+-s "$SERIAL"} install -r -d \
        android/app/build/outputs/apk/debug/app-debug.apk >/dev/null 2>&1
    rm -rf "$WORK/res-bisect"
    bash docs/testing/run_disc.sh "$ISO" "$GUEST" "$WORK/res-bisect" 600 >/dev/null 2>&1
    exact=$(python3 - "$WORK/res-bisect" "$GOLDENS" "$RESULTS_NAME" <<'PY'
import os, sys, numpy as np
from PIL import Image
r, g, suite = sys.argv[1], sys.argv[2], sys.argv[3]
n = 0
try:
    for f in sorted(os.listdir(r)):
        if not f.startswith(suite + "::") or not f.endswith(".png"):
            continue
        gp = os.path.join(g, suite, f[len(suite) + 2:])
        if not os.path.exists(gp):
            continue
        a = np.asarray(Image.open(gp).convert("RGBA"), dtype=np.int16)
        b = np.asarray(Image.open(os.path.join(r, f)).convert("RGBA"), dtype=np.int16)
        if a.shape == b.shape and not np.any(a - b):
            n += 1
except OSError:
    print("ERR"); raise SystemExit
print(n)
PY
)
    printf '%-14s %-6s %s\n' "${sha:0:10}" "$exact" "$(git log -1 --format=%s "$sha" | cut -c1-46)"
done
