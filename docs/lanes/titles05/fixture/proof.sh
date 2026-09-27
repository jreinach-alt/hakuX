#!/usr/bin/env bash
# Render the fixture with older renderers and their own configs (before) and
# with this tree's (after), assert the 0.5 table on each, and, when CHROME
# names a headless browser, shoot each at 400 and 360 px.
#
#   proof.sh <scratch dir> [base sha ...]
#
# Default bases: deb0903b51 (PR #448's fold) and cd78454e6a (PR #458 before
# the owner's layout review, 2026-09-26 20:45 PDT).
set -u
F=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOP=$(git -C "$F" rev-parse --show-toplevel)
mkdir -p "$1"; S=$(cd "$1" && pwd); shift
BASES=("$@"); [ ${#BASES[@]} -gt 0 ] || BASES=(deb0903b51 cd78454e6a)
RUNS=()
for B in "${BASES[@]}"; do
    bash "$TOP/docs/lanes/dash432/fixtures/old_renderer.sh" "$S/old-$B" "$B"
    # the registry the renderer imports (titlestate.py, routes/, and what saves.py loads) as of that base
    git -C "$TOP" archive "$B" docs/testing/titles docs/testing/extract_results.py tools/make_xbox_hdd.py | tar -x -C "$S/old-$B"
    git -C "$TOP" show "$B:docs/lanes/dash432/release-0.5.toml" > "$S/conf-$B.toml" 2>/dev/null ||
        git -C "$TOP" show "$B:docs/testing/release-0.5.toml" > "$S/conf-$B.toml"
    SYNTH_CONF="$S/conf-$B.toml" bash "$F/render.sh" "$S/old-$B/docs/testing/jobs" "$S/before-$B" "$TOP"; echo "before-$B rc=$?"
    RUNS+=("before-$B")
done
bash "$F/render.sh" "$TOP/docs/testing/jobs" "$S/after" "$TOP"; echo "after rc=$?"
RUNS+=(after)
for o in "${RUNS[@]}"; do
    echo "== $o"
    python3 "$F/assert_titles.py" "$S/$o"
    if [ -n "${CHROME:-}" ]; then
        for w in 400 360; do
            bash "$TOP/docs/lanes/dash432/fixtures/shoot.sh" "$S/$o/render/index.html" "$S/shots/$o-phone-$w.png" "$w" "${SHOT_H:-2400}" > /dev/null
        done
    fi
done
exit 0
