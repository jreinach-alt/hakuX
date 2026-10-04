# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh + status_html.py: the dashboard answers the owner's four questions
# from its first screen (#432).
#
# WHY THIS EXISTS. The owner read the page at 2026-09-26 16:20 PDT and asked
# seven questions it could not answer: why a device said a bare "held"; why
# the attention box listed four lanes that were fine and missed six open owner
# decisions; why lane.xbox and lane.remote were not lanes; what "never" meant;
# why every summary was cut mid-word; and why the 0.5 section said "0 of 145"
# beside seventeen measured titles. The host kept that tick's output, and the
# lane captured its SOURCES (docs/lanes/dash432/fixtures/1624/src). This
# renders them offline with this tree's status.sh -- replayed gh, systemctl
# and adb, the clock pinned to 16:24:33 PDT -- and asserts on the words a
# reader sees. Every check below fails on the renderer before the change
# (NOTES.md, "Proof", shows both runs).
#
# Independent of every other fragment: its own work tree, PATH and clock.

echo "== status.sh objective (the 16:24 fixture)"
SO_F="$REPO/docs/lanes/dash432/fixtures"
SO_OUT="$T/status-objective"
# release-0.5.toml moved to docs/testing/ (lane.titles05, #433); run_fixture.sh's
# default still names its old home under docs/lanes/dash432/.
STATUS_RELEASE_CONF="$REPO/docs/testing/release-0.5.toml" FIXTURE_REPO="$REPO" bash "$SO_F/run_fixture.sh" "$HERE" "$SO_OUT"; so_rc=$?
check "the fixture renders (status.sh --print exits 0)" [ "$so_rc" -eq 0 ]
check "...and writes the page" [ -s "$SO_OUT/index.html" ]
sf_no65() { ! grep -q "$@"; }
so_check() { python3 "$SO_F/assert_objective.py" "$SO_OUT" "$1" > "$T/status-objective-$1.txt" 2>&1; }
check "no bare 'held': each device is running, in use by a named holder with purpose and end, or idle" so_check held
check "'what needs a person' is exactly the six owner decisions and the stranded perfregimen" so_check person
check "lane.xbox and lane.remote are rows of the lanes table" so_check sessions
check "'never' is not a value on the page, nor on its first screen" so_check never
check "every latest-result cell is a whole sentence" so_check results
# The 0.5 table's own checks (pass 1's titles, counts from rows, no "of 145")
# were #448's, against a target the owner replaced at 17:15 PDT with "145
# benchmarked, 50 Playable" (#433). 66-status-titles.sh asserts the table
# against the new goals; here only pass 1's titles are held to the page.
so_pass1() { python3 - "$SO_OUT/status.json" "$REPO/docs/lanes/dash432/pass1-backfill.json" <<'PY'
import json, sys
rows = {r["title"] for r in json.load(open(sys.argv[1]))["first"]["titles"]["rows"]}
sys.exit(0 if all(r["title"] in rows for r in json.load(open(sys.argv[2]))["rows"]) else 1)
PY
}
check "the 0.5 table carries pass 1's 17 titles" so_pass1
for so_f in "$T"/status-objective-*.txt; do grep -q '^FAIL' "$so_f" && sed 's/^/    /' "$so_f"; done

# The machine-readable outputs are kept and extended, not replaced.
check "lanes.json keeps its old keys and gains the first screen" python3 -c '
import json, sys
j = json.load(open(sys.argv[1]))
sys.exit(0 if all(k in j for k in ("idle", "blocked", "fold_stuck", "queued_old", "devices", "prs_ok", "terr_ok", "first")) else 1)' "$SO_OUT/lanes.json"
check "status.json carries the four answers" python3 -c '
import json, sys
j = json.load(open(sys.argv[1]))
f = j["first"]
sys.exit(0 if f["titles"]["counts"]["listed"] == len(f["titles"]["rows"]) >= 17 and f["queue"]["queued"] == 23 and f["queue"]["queued_05"] == 23
         and [d["state"] for d in f["devices"]] == ["in use", "in use"] and f["stranded"] == ["perfregimen"] else 1)' "$SO_OUT/status.json"
check "the #107 body header's idle list names the stranded lane" grep -qx 'perfregimen' "$SO_OUT/work/status/idle-lanes"
check "STATUS.md keeps the running-units table for #107" grep -q '^### Lanes running' "$SO_OUT/STATUS.md"
check "a file wait reads as one, with the path and its holder" \
    grep -qF '| forza414 | local lane | #414 Forza Motorsport' "$SO_OUT/STATUS.md"
check "...waiting on hw/xbox/nv2a/pgraph/vk/surface.c, held by lane.doa413b" \
    grep -qF 'waiting on a file | hw/xbox/nv2a/pgraph/vk/surface.c, held by lane.doa413b' "$SO_OUT/STATUS.md"
check "parked work is one line with its gate" grep -qF '**Parked until 0.5 ships** (gate: #433 closes' "$SO_OUT/STATUS.md"
check "a merged lane is finished, not blocked" grep -qE '^\| blinx372d \| #372 .* \| #396 \|' "$SO_OUT/STATUS.md"
# The board's status_note is history: #13's names vk/draw.c, held today by
# lane.remote for other work. A note is not a wait; only the current blocker,
# naming the path and its holder together, is.
check "a path in an issue's history is not a file wait" sf_no65 -E '^\| flatlm13 \| local lane .*waiting on a file' "$SO_OUT/STATUS.md"

# jobs/hold.sh (#453) writes .why as "<UTC stamp> <tag>: <reason>". The stamp
# is the hold's start, not its holder: before this, "2026-09-27T01" read as
# the via and the purpose began "02:03Z".
SO_H="$T/status-objective-hold"; mkdir -p "$SO_H/hold"
echo "lane.titlestate" > "$SO_H/hold/thor"
echo "2026-09-27T01:02:03Z lane.titlestate: nav.py pilot on Burnout 3, until 18:41 PDT" > "$SO_H/hold/thor.why"
check "a hold.sh .why names its holder, purpose, start and end" python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
class F:
    D = sys.argv[2]
    def read(self, p):
        return open(p).read() if os.path.exists(p) else None
    def mtime(self, p):
        return 0
h = S._hold_of(F(), "thor")
ok = (h["holder"] == "lane.titlestate" and h["via"] == "lane.titlestate" and h["purpose"].startswith("nav.py pilot")
      and h["start"] == 1790470923 and h["end"] == 1790473260)
print(h); sys.exit(0 if ok else 1)' "$REPO/docs/testing/jobs" "$SO_H"
