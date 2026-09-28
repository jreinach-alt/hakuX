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
check "every measured row shows its median and share at its bar with no tap, one row per title, no fps in a status cell" sm_check fpscol
for sm_f in "$T"/status-measured-*.txt; do grep -q '^FAIL' "$sm_f" && sed 's/^/    /' "$sm_f"; done

# One handheld's measurement is enough (the owner, 18:10 PDT, #433 comment 5851512534).
check "release-0.5.toml asks for one handheld, not both" python3 -c '
import os, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
os.environ.pop("STATUS_RELEASE_CONF", None)
c, p = S._conf({})
sys.exit(0 if c.get("benchmark_copies") == 1 and "copied to both" not in open(p).read() else 1)' "$HERE"

# A 30 fps title reads as one (lane.local, 2026-09-27 19:56 PDT: Galleon, Tork,
# CoD3, MC3, Azurik and BF2MC read "29.0 ... 0% at 30+"). profile.c logs gfps
# as an integer quarter-second sample, so every line of a 30 fps title says
# gfps=29, and the soak read counted them at a strict 30. title_verdict.py
# judges 60 / dt between pacing lines at playable_fps x fps_tolerance
# (targets.toml); the table now reads a soak the same way and names the bar.
# Fixtures: a verdict at 29.97 / 0.85; a soak of pacing lines 2.002 s apart
# (gfps=29, 29.97 per window); a soak in the old line format, gfps 29.4/29.8.
# The second targets.toml sets fps_tolerance 0.9: the bar is read, not 28.5.
# Fails on master at f82e7e87fe (docs/lanes/fpsshare/NOTES.md).
sm_share() {
python3 -c '
import datetime, json, os, re, sys
sys.path.insert(0, sys.argv[1]); import status_html as S
root, tol = sys.argv[2], sys.argv[3]
R = os.path.join(root, "results"); os.makedirs(os.path.join(root, "S"), exist_ok=True)
tg = os.path.join(root, "targets.toml")
open(tg, "w").write("[defaults]\nplayable_fps = 30\nfps_tolerance = %s\n" % tol)
os.environ["TITLE_TARGETS"] = tg; os.environ["TITLESTATE_DIR"] = os.path.join(root, "ts")
def run(rid):
    d = os.path.join(R, rid); os.makedirs(d, exist_ok=True); return d
d = run("1790460000-fpsshare-verdict")
json.dump({"name": "Zz Verdict", "title": "Zz Verdict (USA).xiso.iso", "device": "nova", "fps_window_median": 29.97,
           "fps_ok_share": 0.85, "fps_bar": 30.0, "reached_gameplay": True, "pass": False, "failing": "fps"},
          open(os.path.join(d, "verdict.json"), "w"))
t0 = datetime.datetime(2026, 9, 26, 22, 0, 0)
for rid, iso, line, step in (("1790460100-fpsshare-pace", "Zz Pace (USA).xiso.iso", "gfps=29 G:33.4(30.1-40.2) D:16.7(16.7-16.7)", 2.002),
                             ("1790460200-fpsshare-old", "Zz Old (USA).xiso.iso", None, 2.0)):
    d = run(rid)
    json.dump({"id": rid, "title": iso, "device": "thor", "ref": "abcdef1234"}, open(os.path.join(d, "request.json"), "w"))
    with open(os.path.join(d, "logcat.txt"), "w") as fh:
        for i in range(130):
            ts = (t0 + datetime.timedelta(seconds=i * step)).strftime("%m-%d %H:%M:%S.%f")[:-3]
            fh.write("%s  1234  5678 I hakuX-perf: %s\n" % (ts, line or "fps=30 gfps=%s" % ("29.4" if i % 2 else "29.8")))
    open(os.path.join(d, "DONE"), "w").close()
E = {"WORK": root, "D": root, "S": os.path.join(root, "S"), "STATUS_RELEASE_CONF": os.path.join(root, "none.toml"),
     "STATUS_XISO_DIR": root, "STATUS_TITLES_DIR": root}
F = S.Facts(E); F.now += 60
t = S.titles05(F, {}, os.path.join(root, "none.toml"), F.now)
cell = {}
for x in t["rows"]:
    f = re.sub(r"<[^>]+>", " ", S._fps_cell(x))
    cell[x["title"]] = re.sub(r"\s+", " ", f).strip()
bar = "%g" % (30 * float(tol))
want = {"Zz Verdict": ("30.0", "85% at " + bar + "+"), "Zz Pace": ("30.0", "100% at " + bar + "+"),
        "Zz Old": ("29.6", "100% at " + bar + "+")}
bad = ["%s: %r" % (n, cell.get(n)) for n, (m, s) in want.items()
       if not cell.get(n) or not cell[n].startswith(m + " " + s) or re.search(r"(^| )0% ", cell[n])]
print("\n".join("%s: %s" % kv for kv in sorted(cell.items())))
sys.exit(1 if bad else 0)' "$HERE" "$1" "$2" > "$1.txt" 2>&1 || { sed "s/^/    /" "$1.txt"; return 1; }
}
check "a 30 fps verdict reads 30.0 and 85% at 28.5+, and a soak of gfps=29 lines reads 30.0 and 100%, not 0%" sm_share "$T/status-share" 0.95
check "...and the bar is targets.toml's playable_fps x fps_tolerance, not a constant (tolerance 0.9: at 27+)" sm_share "$T/status-share-tol" 0.9

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
