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
FIXTURE_REPO="$REPO" bash "$SO_F/run_fixture.sh" "$HERE" "$SO_OUT"; so_rc=$?
check "the fixture renders (status.sh --print exits 0)" [ "$so_rc" -eq 0 ]
check "...and writes the page" [ -s "$SO_OUT/index.html" ]
sf_no65() { ! grep -q "$@"; }
so_check() { python3 "$SO_F/assert_objective.py" "$SO_OUT" "$1" > "$T/status-objective-$1.txt" 2>&1; }
check "no bare 'held': each device is running, in use by a named holder with purpose and end, or idle" so_check held
check "'what needs a person' is exactly the six owner decisions and the stranded perfregimen" so_check person
check "lane.xbox and lane.remote are rows of the lanes table" so_check sessions
check "'never' is not a value on the page, nor on its first screen" so_check never
check "every latest-result cell is a whole sentence" so_check results
check "the 0.5 table carries pass 1's 17 titles, and its counts are its rows'" so_check titles
check "the 0.5 section does not count against 145" so_check no145
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
sys.exit(0 if f["titles"]["counts"]["tested"] == 16 and f["queue"]["queued"] == 23 and f["queue"]["queued_05"] == 23
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
