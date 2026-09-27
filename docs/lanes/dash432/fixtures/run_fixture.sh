#!/usr/bin/env bash
# Render the 16:24 PDT fixture with a given status.sh, offline.
#
#   run_fixture.sh <jobs dir holding status.sh> <out dir>
#
# Copies the fixture's work tree (mtimes kept: the holds' start times are their
# mtimes), puts gh/systemctl/adb replays first on PATH, pins the clock at the
# fixture's NOW, and runs `status.sh --print`, which renders and never
# publishes. Leaves STATUS.md, index.html, status.json and lanes.json in <out>.
set -u
JOBS=$(cd "$1" && pwd); OUT=$2
HERE_F=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SRC="$HERE_F/1624/src"
rm -rf "$OUT"; mkdir -p "$OUT/bin"
cp -a "$SRC/work" "$OUT/work"
for t in gh systemctl adb; do
    printf '#!/usr/bin/env bash\nexec python3 "%s" %s "$@"\n' "$HERE_F/replay.py" "$t" > "$OUT/bin/$t"; chmod +x "$OUT/bin/$t"
done
printf '#!/usr/bin/env bash\necho 0\n' > "$OUT/bin/pgrep"; chmod +x "$OUT/bin/pgrep"
mkdir -p "$OUT/work/host-tools"
printf '#!/usr/bin/env python3\nprint("plug KP115 (Xbox) at [lan]: ON, 66.2 W")\n' > "$OUT/work/host-tools/kasa_console.py"
chmod +x "$OUT/work/host-tools/kasa_console.py"
echo 'LANE_MAX=24' > "$OUT/work/limits.env"
NOW=1790465073
BOOT=$(date -d 'Sat 2026-09-26 14:44:00 PDT' +%s)
PATH="$OUT/bin:$PATH" FIXTURE_SRC="$SRC" \
HAKUX_WORK="$OUT/work" DISPATCH_DIR="$OUT/work/dispatch" HAKUX_REPO_DIR="${FIXTURE_REPO:-$(git -C "$JOBS" rev-parse --show-toplevel)}" \
GH_REPO=jreinach-alt/hakuX STATUS_BOARD_DIR="$SRC/board" STATUS_NOW=$NOW STATUS_BOOT_EPOCH=$BOOT \
STATUS_TITLES_DIR="$OUT/work/titles" HAKUX_XISO_DIR="$OUT/no-xiso" \
STATUS_RELEASE_CONF="${STATUS_RELEASE_CONF:-$HERE_F/../release-0.5.toml}" \
    bash "$JOBS/status.sh" --print > "$OUT/stdout.txt" 2> "$OUT/stderr.txt"
rc=$?
for f in STATUS.md index.html status.json lanes.json facts.tsv; do cp "$OUT/work/status/$f" "$OUT/$f" 2>/dev/null; done
exit $rc
