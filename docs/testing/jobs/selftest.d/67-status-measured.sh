# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# status.sh + status_html.py: "Measured N / 145" leads the 0.5 line, has the
# first bar in "How close is 0.5?", and a chart of titles over time (#433).
#
# WHY THIS EXISTS. The owner, 2026-09-26 ~21:55 PDT: "track at the top and
# chart in the How close section Measured x / 145 so we at least show progress
# on the titles we have an FPS reading for? Otherwise it looks like no progress
# has been made towards 0.5." Benchmarked needs a route, a save and a MAX run;
# Measured is any gameplay-window fps reading, on either handheld, any build or
# mode: pass 1's hand-reviewed rows, verdicts, and soaks read as the Ghoulies
# gate reads them. This renders lane.titles05's fixture plus three soaks
# (docs/lanes/measured05/fixture) and asserts on the words a reader sees. Each
# check fails on master's renderer at f805f978ad (docs/lanes/measured05/NOTES.md).
#
# Independent of every other fragment: its own copy of the fixture, PATH and clock.

echo "== status.sh Measured N / 145 and the progress chart (#433)"
SM_F="$REPO/docs/lanes/measured05/fixture"
SM_OUT="$T/status-measured"
bash "$SM_F/render.sh" "$HERE" "$SM_OUT" "$REPO" > /dev/null 2>&1; sm_rc=$?
check "the fixture renders (status.sh --print exits 0)" [ "$sm_rc" -eq 0 ]
sm_check() { python3 "$SM_F/assert_measured.py" "$SM_OUT" "$1" > "$T/status-measured-$1.txt" 2>&1; }
check "the 0.5 line leads with 'Measured N / 145', N the fixture's titles with any fps reading" sm_check glance
check "Measured >= Benchmarked >= Playable, and a soak alone makes a title Measured" sm_check order
check "How close shows a Measured bar first, above Benchmarked and Playable" sm_check bar
check "the chart is inline SVG under the bars; its Measured line ends at N; three dashes" sm_check chart
check "status.json carries the three series" sm_check json
check "Copied is a tick on one handheld, never a half, and nothing says 'copied to both handhelds'" sm_check copied
check "every measured row shows its median and share at 30+ with no tap, one row per title, no fps in a status cell" sm_check fpscol
for sm_f in "$T"/status-measured-*.txt; do grep -q '^FAIL' "$sm_f" && sed 's/^/    /' "$sm_f"; done

# One handheld's measurement is enough (the owner, 18:10 PDT, #433 comment 5851512534).
check "release-0.5.toml asks for one handheld, not both" python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
os.environ.pop("STATUS_RELEASE_CONF", None)
c, p = S._conf({})
sys.exit(0 if c.get("benchmark_copies") == 1 and "copied to both" not in open(p).read() else 1)' "$HERE"

# A build on inputs cut off mid-write finishes (hostops, 2026-09-26 22:39 PDT: the
# 21:55 board tick hung 41 min at 5.2 GB in status_html.py build). The cause:
# md_to_html never advanced past a "|" line with no separator after it, so a
# STATUS.md cut just before its last table's separator (a table below the fold)
# looped forever; master's renderer is killed at the bound on that input. The
# truncated facts.tsv and lanes.json finish on master too; they stay as guards.
SM_R="$SM_OUT/render"; SM_C="$T/status-measured-cut"; mkdir -p "$SM_C"
head -c "$(( $(wc -c < "$SM_R/facts.tsv") / 2 ))" "$SM_R/facts.tsv" > "$SM_C/facts.tsv"
head -c "$(( $(wc -c < "$SM_R/lanes.json") / 2 ))" "$SM_R/lanes.json" > "$SM_C/lanes.json"
python3 -c '
import re, sys
ls = open(sys.argv[1]).read().splitlines()
k = max(i for i, l in enumerate(ls) if re.match(r"^\|[\s:|-]+\|?\s*$", l))
open(sys.argv[2], "w").write("\n".join(ls[:k]) + "\n")' "$SM_R/STATUS.md" "$SM_C/STATUS.md"
sm_cut() {
    timeout 30 python3 "$HERE/status_html.py" build --facts "$1" --lanes "$2" --md "$3" \
        --json "$SM_C/status.json" --html "$SM_C/index.html" > /dev/null 2>&1
}
check "a build on a truncated facts.tsv finishes" sm_cut "$SM_C/facts.tsv" "$SM_R/lanes.json" "$SM_R/STATUS.md"
check "a build on a truncated lanes.json finishes" sm_cut "$SM_R/facts.tsv" "$SM_C/lanes.json" "$SM_R/STATUS.md"
check "a build on a STATUS.md cut before its last table's separator finishes" \
    sm_cut "$SM_R/facts.tsv" "$SM_R/lanes.json" "$SM_C/STATUS.md"
check "md_to_html finishes on a table header with nothing after it" timeout 10 python3 -c '
import sys; sys.path.insert(0, sys.argv[1]); import status_html as S
sys.exit(0 if "<p>| a | b |</p>" in S.md_to_html("## x\n| a | b |") else 1)' "$HERE"
check "status.sh bounds the build with a timeout that it logs" grep -q 'timeout "${STATUS_BUILD_TIMEOUT:-120}" python3 "$J/status_html.py" build' "$HERE/status.sh"
