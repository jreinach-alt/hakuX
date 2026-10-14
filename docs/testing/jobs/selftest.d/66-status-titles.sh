# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh + status_html.py: the 0.5 section is a title table against the
# owner's goals, 145 measured and 50 Playable (#433).
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
# counts/lines/pipe delegate to assert_titles.py's c_counts/c_lines/c_pipe,
# which assert the now-removed Benchmarked header and the C I S B column
# (#433); replaced below with inline checks of the same shape, against the
# new rendering. target/nocut/fold/nameless/order/forecast/flight/watch are
# unaffected (none mention Benchmarked or the pipeline) and still delegate.
check "nothing in the 0.5 section is shortened (no ellipsis; every title and next step in full)" st_check nocut
check "the target line says 145 and 50 and carries no date" st_check target
check "'~2026-09-28' is not on the page" st_check nodate
check "the 'not copied' tail folds after 10 rows, with its count" st_check fold
check "a verdict with no name or title_id lands in its title's row, by the ISO's title-ID prefix" st_check nameless
check "red first, then from the most advanced stage down" st_check order
check "the header forecasts from the last 48 h rate" st_check forecast
check "each issue shows its state and what is in flight; an unowned open one is an alarm" st_check flight
check "Q4 shows the device watchdog's word and last hour; a stale watchdog is lane.local's alarm" st_check watch
for st_f in "$T"/status-titles-*.txt; do grep -q '^FAIL' "$st_f" && sed 's/^/    /' "$st_f"; done

# The SpongeBob falsifier (title_id as the join key, #433 Part 1): the owner
# found SpongeBob listed as "copied" while it sat on the Playable wall,
# because an ISO-stem spelling and the ledger's own spelling of one
# title_id landed on two rows. Its own fixture (not the 16:24 one above --
# this defect needs one disagreeing pair, not a title at every stage) must
# still split on the pre-#433 code, so this stays a falsifier: a change that
# disabled the catalog lookup rather than fixing it would still fail here.
python3 "$REPO/docs/lanes/titledb1014/fixture/spongebob_falsifier.py" "$REPO" > "$T/spongebob-falsifier.txt" 2>&1
check "two differently-spelled sources of one title_id fold to one Playable row (the SpongeBob defect, #433)" \
    grep -q '^PASS' "$T/spongebob-falsifier.txt"
grep -q '^FAIL' "$T/spongebob-falsifier.txt" && sed 's/^/    /' "$T/spongebob-falsifier.txt"

# No Benchmarked header, no C I S B column or its legend, anywhere on the page (#433).
check "no 'Benchmarked' count and no C I S B pipeline column or legend" python3 -c '
import re, sys
html = open(sys.argv[1] + "/render/index.html", encoding="utf-8").read()
bad = []
if "Benchmarked" in html:
    bad.append("Benchmarked still appears")
if re.search(r"<th class=\"v\"", html) or "Pipeline: Copied, Inputs, Save, Bench" in html:
    bad.append("the C I S B column or its legend still appears")
if bad:
    print("; ".join(bad)); sys.exit(1)' "$ST_OUT"

# The title table is still a fixed three-column layout (title/next step, status,
# fps) now that the four pipe columns are gone -- no col.w-p, no c-m marks.
check "fixed three-column layout: no pipe column width or tick marks remain" python3 -c '
import re, sys
html = open(sys.argv[1] + "/render/index.html", encoding="utf-8").read()
m = re.search(r"(?s)<section class=\"q\" id=\"q1\">.*?</section>", html)
q1 = m.group(0) if m else ""
bad = []
if "table.tt col.w-p" in html or "col.w-p" in html:
    bad.append("col.w-p still defined")
if "c-m" in q1:
    bad.append("c-m tick marks still rendered")
if "table-layout:fixed" not in html or "table.tt" not in html:
    bad.append("table.tt no longer fixed-layout")
if "<col class=\"w-f\">" not in q1:
    bad.append("the fps column lost its own width")
if bad:
    print("; ".join(bad)); sys.exit(1)' "$ST_OUT"

# The next step is always exactly one of the owner'"'"'s four phrases, "review
# frames for Playable" (a passing soak not yet in the Playable ledger), or "done"
# for Playable rows -- never "benchmark at MAX" / "re-benchmark at MAX" (#433).
check "next step uses only reach gameplay / soak for Playable / review frames for Playable / below the bar / blocked: <reason> / done" python3 -c '
import re, sys
html = open(sys.argv[1] + "/render/index.html", encoding="utf-8").read()
m = re.search(r"(?s)<section class=\"q\" id=\"q1\">.*?</section>", html)
q1 = m.group(0) if m else ""
steps = [re.sub("<[^>]+>", "", s) for s in re.findall(r"<span class=\"nx[^\"]*\">(.*?)</span>", q1)]
bad = [s for s in steps if not (s in ("reach gameplay", "soak for Playable", "review frames for Playable", "below the bar", "done") or s.startswith("blocked: "))]
if "benchmark at MAX" in q1.lower() or "re-benchmark" in q1.lower():
    bad.append("benchmark-at-MAX wording still present")
if not steps:
    bad.append("no next-step rows found")
if bad:
    print("; ".join(bad)); sys.exit(1)' "$ST_OUT"

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

# title_verdict.py names the title the same way at scoring time: an ISO the
# registry's map does not list, whose file name leads with a registered title
# ID, is that title (so its verdict carries title_id and name); an unregistered
# prefix is still no title.
check "title_verdict.py finds a title by its ISO's title-ID prefix, and only a registered one" python3 -c '
import sys
sys.path.insert(0, sys.argv[1]); import title_verdict as V
tg = {"titles": {"5A5A0009": {"name": "Zz Nameless", "iso": {"thor": "5A5A0009-Zz_Nameless.xiso.iso"}}}}
a = V.find_title(tg, "/x/5A5A0009-Zz_Nameless_(USA).xiso.iso")
b = V.find_title(tg, "5a5a0009-Zz_Nameless.xiso.iso")
c = V.find_title(tg, "5A5A0010-Zz_Other.xiso.iso")
sys.exit(0 if a[0] == b[0] == "5A5A0009" and a[1]["name"] == "Zz Nameless" and c == (None, {}) else 1)' "$HERE/.."

# 0.6 is the new default (#433), with the owner's curve numbers; 0.5 stays
# readable as history, by explicit override only.
check "release-0.6.toml at docs/testing is the default and states 300 measured and 110 Playable" python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
os.environ.pop("STATUS_RELEASE_CONF", None)
c, p = S._conf({})
sys.exit(0 if p.endswith("docs/testing/release-0.6.toml") and S._measured_target(c) == 300 and c.get("playable_target") == 110
         and "benchmarked_target" not in c and c.get("curve") else 1)' "$HERE"
check "release-0.5.toml is still readable by explicit STATUS_RELEASE_CONF override, states 145 and 50" python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
p5 = os.path.join(sys.argv[2], "docs/testing/release-0.5.toml")
c, p = S._conf({"STATUS_RELEASE_CONF": p5})
sys.exit(0 if os.path.normpath(p) == os.path.normpath(p5) and S._measured_target(c) == 145 and c.get("playable_target") == 50 else 1)' "$HERE" "$REPO"
# The release counts measured titles (the owner, 2026-10-12): the Measured bar and
# the forecast read measured_target, and a file without it falls back to the old field.
check "the Measured target is measured_target, else benchmarked_target" python3 -c '
import sys
sys.path.insert(0, sys.argv[1]); import status_html as S
sys.exit(0 if S._measured_target({"measured_target": 120, "benchmarked_target": 145}) == 120
         and S._measured_target({"benchmarked_target": 140}) == 140 else 1)' "$HERE"
