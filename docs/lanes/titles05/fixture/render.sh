#!/usr/bin/env bash
# Render the 16:24 fixture plus the pass-1 backfill plus a synthetic registry
# (one title at each stage of the 0.5 scale) with a given status.sh, offline.
#
#   render.sh <jobs dir holding status.sh> <out dir> [repo holding the fixtures]
#
# Copies lane.dash432's fixture (docs/lanes/dash432/fixtures) so the synthetic
# rows never touch it, adds synth.py's registry, and runs its run_fixture.sh.
# Leaves index.html, status.json and synth/expect.json under <out>.
set -u
JOBS=$(cd "$1" && pwd); mkdir -p "$2"; OUT=$(cd "$2" && pwd)
HERE_R=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=${3:-$(cd "$HERE_R/../../../.." && pwd)}
rm -rf "$OUT/fx" "$OUT/synth"; mkdir -p "$OUT/fx" "$OUT/synth"
cp -a "$REPO/docs/lanes/dash432/fixtures/1624" "$REPO/docs/lanes/dash432/fixtures/run_fixture.sh" \
      "$REPO/docs/lanes/dash432/fixtures/replay.py" "$OUT/fx/"
python3 "$HERE_R/synth.py" "$OUT/fx/1624/src/work" "$OUT/synth" "$REPO" || exit 1
TITLE_TARGETS="$OUT/synth/targets.toml" STATUS_RELEASE_CONF="$OUT/synth/release-0.5.toml" \
STATUS_XISO_DIR="$OUT/synth/xiso" STATUS_DEVWATCH="$OUT/synth/devwatch.json" FIXTURE_REPO="$REPO" \
    bash "$OUT/fx/run_fixture.sh" "$JOBS" "$OUT/render"
