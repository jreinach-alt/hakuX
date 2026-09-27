# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh + status_html.py: the 0.5 section is a title table against the
# owner's goals, 145 benchmarked and 50 Playable (#433).
#
# WHY THIS EXISTS. The owner, 2026-09-26 ~17:50 PDT: "On the status page, the
# 0.5 goals is a wall of text ... It should have a list of the titles and
# everything we need to track their status like FPS measurement and a color,
# and if there's a related issue open, is it in flight." #448 rendered each
# title as a paragraph (several screens at 400 px) under a target that still
# said "~2026-09-28". This renders lane.dash432's 16:24 fixture plus the pass-1
# backfill plus a synthetic registry with one title at each stage of the scale
# (docs/lanes/titles05/fixture/synth.py, added to the fixture's own
# targets.toml, never the live one) and asserts on the words a reader
# sees. Every check fails on #448's renderer (docs/lanes/titles05/NOTES.md,
# "Proof", shows both runs).
#
# Independent of every other fragment: its own copy of the fixture, PATH and clock.

echo "== status.sh 0.5 title table (#433)"
ST_F="$REPO/docs/lanes/titles05/fixture"
ST_OUT="$T/status-titles"
bash "$ST_F/render.sh" "$HERE" "$ST_OUT" "$REPO" > /dev/null 2>&1; st_rc=$?
check "the fixture renders (status.sh --print exits 0)" [ "$st_rc" -eq 0 ]
check "...and writes the page" [ -s "$ST_OUT/render/index.html" ]
st_check() { python3 "$ST_F/assert_titles.py" "$ST_OUT" "$1" > "$T/status-titles-$1.txt" 2>&1; }
check "every row carries exactly one status word from the scale, and each stage renders as itself" st_check word
check "Benchmarked N / 145 and Playable M / 50 are the rows' counts" st_check counts
check "fixed columns: no title or next step past two lines at 360 or 400 px; short tokens never wrap" st_check lines
check "nothing in the 0.5 section is shortened (no ellipsis; every title and next step in full)" st_check nocut
check "the pipeline is four labelled columns (Copied, Inputs, Save, Bench) with a legend; one-route titles count" st_check pipe
check "the target line says 145 and 50 and carries no date" st_check target
check "'~2026-09-28' is not on the page" st_check nodate
check "the 'not copied' tail folds after 10 rows, with its count" st_check fold
check "red first, then from the most advanced stage down" st_check order
check "the header forecasts from the last 48 h rate" st_check forecast
check "each issue shows its state and what is in flight; an unowned open one is an alarm" st_check flight
check "Q4 shows the device watchdog's word and last hour; a stale watchdog is lane.local's alarm" st_check watch
for st_f in "$T"/status-titles-*.txt; do grep -q '^FAIL' "$st_f" && sed 's/^/    /' "$st_f"; done

# titlestate.py no-save: a two-route title (Black) whose disk was read and holds
# no save stops reading "none extracted", and says why; the same registry
# without the record still asks for a save. Black's entry is read from the
# fixture's registry, like every row above: the live targets.toml changes
# under this check without running it.
check "a no-save record stands in for a save, with its reason; without it the save is still asked for" python3 -c '
import json, os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
d = os.path.join(sys.argv[2], "status-nosave", "devices"); os.makedirs(d, exist_ok=True)
os.environ["TITLESTATE_DIR"] = os.path.dirname(d)
os.environ["TITLE_TARGETS"] = sys.argv[3]
class F: D = ""
def reg(row):
    json.dump({"device": "thor", "image": None, "rejected": {}, "titles": {"45410083": row}}, open(os.path.join(d, "thor.json"), "w"))
    return S._registry(F)[0]["45410083"]
g = reg({"profile": True, "save_na": {"reason": "UDATA holds no save", "by_run": "r", "utc": "t"}})
det = S._title_detail(dict(g, inputs=True, devices=["thor"], next="-"), 0)
g0 = reg({"profile": True})
sys.exit(0 if not g["needs_save"] and "save: not needed: UDATA holds no save" in det and g0["needs_save"] and not g0["save_na"] else 1)' "$HERE" "$T" "$ST_F/targets.toml"

# The config's new home is the default, and it is the owner's two numbers.
check "release-0.5.toml at docs/testing is the default and states 145 and 50" python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
os.environ.pop("STATUS_RELEASE_CONF", None)
c, p = S._conf({})
sys.exit(0 if p.endswith("docs/testing/release-0.5.toml") and c.get("benchmarked_target") == 145 and c.get("playable_target") == 50 else 1)' "$HERE"
