#!/usr/bin/env bash
# Render the fixture with #448's renderer and its own config (before) and with
# this tree's (after), assert the 0.5 table on both, and, when CHROME names a
# headless browser, shoot both at 400 px.
#
#   proof.sh <scratch dir> [base sha, default deb0903b51 = PR #448's fold]
set -u
F=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
TOP=$(git -C "$F" rev-parse --show-toplevel)
mkdir -p "$1"; S=$(cd "$1" && pwd); BASE=${2:-deb0903b51}
bash "$TOP/docs/lanes/dash432/fixtures/old_renderer.sh" "$S/old" "$BASE"
git -C "$TOP" show "$BASE:docs/lanes/dash432/release-0.5.toml" > "$S/conf-448.toml"
SYNTH_CONF="$S/conf-448.toml" bash "$F/render.sh" "$S/old/docs/testing/jobs" "$S/before" "$TOP"; echo "before rc=$?"
bash "$F/render.sh" "$TOP/docs/testing/jobs" "$S/after" "$TOP"; echo "after rc=$?"
for o in before after; do
    echo "== $o"
    python3 "$F/assert_titles.py" "$S/$o"
    [ -n "${CHROME:-}" ] && bash "$TOP/docs/lanes/dash432/fixtures/shoot.sh" "$S/$o/render/index.html" "$S/shots/$o-phone.png" 400 "${SHOT_H:-2400}" > /dev/null
done
exit 0
