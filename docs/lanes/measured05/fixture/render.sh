#!/usr/bin/env bash
# Render lane.titles05's fixture (the 16:24 fixture, the pass-1 backfill and a
# synthetic registry) plus three soaks with logcats, offline.
#
#   render.sh <jobs dir holding status.sh> <out dir> [repo holding the fixtures]
#
# The soaks (soaks.py) are what a title with no verdict is measured by:
#   Zz Soak Only (USA).xiso.iso       no registry entry; gfps 90-240 s -> measured
#   5A5A0005-Zz_Purple.xiso.iso x2    a registry title, both handhelds -> one title
#   Zz Soak Menu (USA).xiso.iso       gfps only in its first 60 s -> NOT measured
set -u
JOBS=$(cd "$1" && pwd); mkdir -p "$2"; OUT=$(cd "$2" && pwd)
HERE_M=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO=${3:-$(cd "$HERE_M/../../../.." && pwd)}
T5="$REPO/docs/lanes/titles05/fixture"
rm -rf "$OUT/fx" "$OUT/synth"; mkdir -p "$OUT/fx" "$OUT/synth"
cp -a "$REPO/docs/lanes/dash432/fixtures/1624" "$REPO/docs/lanes/dash432/fixtures/run_fixture.sh" \
      "$REPO/docs/lanes/dash432/fixtures/replay.py" "$OUT/fx/"
python3 "$T5/synth.py" "$OUT/fx/1624/src/work" "$OUT/synth" "$REPO" || exit 1
python3 "$HERE_M/soaks.py" "$OUT/fx/1624/src/work" "$OUT/synth" || exit 1
TITLE_TARGETS="$OUT/synth/targets.toml" STATUS_RELEASE_CONF="$OUT/synth/release-0.5.toml" \
STATUS_XISO_DIR="$OUT/synth/xiso" STATUS_DEVWATCH="$OUT/synth/devwatch.json" FIXTURE_REPO="$REPO" \
    bash "$OUT/fx/run_fixture.sh" "$JOBS" "$OUT/render"
