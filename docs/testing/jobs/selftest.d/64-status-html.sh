# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# status.sh + status_html.py: the dashboard on GitHub Pages.
#
# WHY THIS EXISTS. The roll-up was a comment on #107: it rendered below the
# issue's timeline, and the per-tick title rename put 304 permanent `renamed`
# rows above it in a week (2026-09-26). The page that replaces it is one file on
# an orphan gh-pages branch of ONE commit, republished only when its content
# moves, and #107 is switched to a pointer exactly once. Each of those is a
# check below, against a local bare repository standing in for GitHub.
#
# Runs after 63-status-lanes.sh and restores selftest.sh's gh shim at the end.
#
# UPDATED FOR #432 (lane.dash432, 2026-09-26): the first screen is no longer a
# strip of tiles and a NEEDS ATTENTION box but four questions in order (how
# close is 0.5, what is happening, what needs a person, are the machines
# healthy), rendered from status.json's `first`. The fixture JSON carries a
# `first` block; the order check, the attention wording, the key's moving part
# (the queue now lives in `first.queue`), the republished change (a queued run
# shows in the Queue line; "queued over 60 min" is no longer an alarm: a long
# queue behind two busy devices is not a fault) and the panel's lines (no
# "N of 145": the counts are computed from the 0.5 title table) follow it.

echo "== status.sh dashboard"
SH_PY="$HERE/status_html.py"
sh_no() { ! grep -q "$@"; }

# ---- 1. the renderer, from a fixture JSON: first screen, self-contained, public-safe
SH_J="$T/status-dash.json"
cat > "$SH_J" <<'EOF'
{"now": 1790400000, "generated": "2026-09-25 22:00 PDT", "tz": "PDT", "floor_secs": 1800, "heartbeat_secs": 1800,
 "next_due": "2026-09-25 22:30 PDT",
 "first": {"release_name": "0.5", "conf": {"target": "0.5 ships as the first tested-titles list.", "decided": "owner"},
           "devices": [{"name": "thor", "state": "running", "who": "arms-x", "purpose": "1-arms-x-fix", "since": 1790399000, "src": "dispatch/running"},
                       {"name": "nova", "state": "in use", "who": "owner", "purpose": "owner hold, see /home/someone/.ssh/id_ed25519", "since": 1790399500, "until": 1790401000, "src": "dispatch/hold/nova.why"}],
           "queue": {"queued": 3, "queued_05": 2, "idle_tier": 90, "constraint": "device-bound: 3 runs queued, both devices busy"},
           "lanes": [{"lane": "x", "kind": "local lane", "issue": "#1 t", "state": "running", "since": 1790399000, "result": "It works."}],
           "titles": {"rows": [], "counts": {"on_handhelds": 0, "tested": 0, "reached": 0, "playable": 0}}},
 "strip": {"devices": [{"name": "thor", "state": "running", "detail": "arms-x: 1-arms-x-fix"},
                       {"name": "nova", "state": "held", "detail": "owner hold, see /home/someone/.ssh/id_ed25519"}],
           "queue": 3, "queue_idle": 90, "arms_running": 1, "lanes_running": 2, "lane_cap": 24,
           "last_fold": 1790399000, "last_fold_subject": "PR #1 lane/x"},
 "attention": [{"kind": "fold", "who": "host", "action": "PR #9 fold-ready for 2h and not folded: CONFLICTING, mail me at someone@example.com, token ghp_abcdefghijklmnopqrstuvwxyz0123"}],
 "release": {"gate": "the gate", "candidate": "none cut yet", "blockers": [{"number": "311", "title": "Ghoulies"}], "blockers_known": true},
 "details_md": "## title\n\n### Board job\n\n| lane | state |\n|---|---|\n| a | b \\| c |\n\n- `code` and **bold**\n\n```\nraw /home/someone/x\n```\n"}
EOF
SH_H="$T/status-dash.html"
python3 "$SH_PY" render "$SH_J" -o "$SH_H"; check "status_html.py renders a fixture" [ -s "$SH_H" ]
check "the page refreshes itself every 60 s" grep -q '<meta http-equiv="refresh" content="60">' "$SH_H"
check "the page has a dark variant" grep -q 'prefers-color-scheme:dark' "$SH_H"
check "the page is phone-width aware" grep -q 'name="viewport" content="width=device-width' "$SH_H"
check "the page loads no external script or stylesheet" sh_no -E '<script[^>]+src=|<link[^>]+stylesheet' "$SH_H"
check "the page says how long ago it was updated" grep -q 'id="age" data-t="1790400000"' "$SH_H"
check "the machines answer names the Thor's run" grep -q 'running</span> 1-arms-x-fix, for arms-x' "$SH_H"
check "a hold names its holder and its end" grep -q 'in use by owner</span>' "$SH_H"
check "what needs a person is on the page" grep -q '3. What needs a person?' "$SH_H"
check "...with who acts" grep -q '<span class="who">host</span>PR #9' "$SH_H"
check "the release blockers are on the page" grep -q '#311 Ghoulies' "$SH_H"
sh_order() { python3 - "$1" <<'PY'
import sys; s = open(sys.argv[1]).read()
a, b, c, d, e, f = (s.find(x) for x in ('class="glance"', 'id="q1"', 'id="q2"', 'id="q3"', 'id="q4"', ">Board job</h"))
sys.exit(0 if -1 < a < b < c < d < e < f else 1)
PY
}
check "at a glance, then the four questions in order, then the details" sh_order "$SH_H"
check "a Markdown table becomes an HTML table" grep -q '<td>b | c</td>' "$SH_H"
check "the page's own title block is not repeated below the fold" sh_no '<h3>title</h3>' "$SH_H"
check "no email address reaches the public page" sh_no 'someone@example.com' "$SH_H"
check "no token reaches the public page" sh_no 'ghp_abcdef' "$SH_H"
check "no credential path reaches the public page" sh_no 'id_ed25519' "$SH_H"
check "no home directory reaches the public page (fenced blocks too)" sh_no '/home/someone' "$SH_H"

# ---- 2. the content key ignores the clock and nothing else
k1=$(python3 "$SH_PY" key "$SH_H")
sed 's/"now": 1790400000/"now": 1790403333/; s/22:00 PDT/22:55 PDT/; s/22:30 PDT/23:25 PDT/' "$SH_J" > "$T/status-dash2.json"
python3 "$SH_PY" render "$T/status-dash2.json" -o "$T/status-dash2.html"
k2=$(python3 "$SH_PY" key "$T/status-dash2.html")
check "a page that differs only in its clock has the same key" [ -n "$k1" ] && [ "$k1" = "$k2" ]
sed 's/"queued": 3/"queued": 4/' "$SH_J" > "$T/status-dash3.json"
python3 "$SH_PY" render "$T/status-dash3.json" -o "$T/status-dash3.html"
check "a page whose queue moved has a new key" [ "$k1" != "$(python3 "$SH_PY" key "$T/status-dash3.html")" ]

# ---- 3. publishing: one commit, force-pushed, only on change
SH_BARE="$T/status-pages.git"; rm -rf "$SH_BARE" "$HAKUX_WORK/status/pages" "$HAKUX_WORK/status/pages-state" "$HAKUX_WORK/status/issue-pointer"
git init -q --bare "$SH_BARE"
SH_LOG="$T/gh-dash.log"
cat > "$T/bin/gh" <<'GHEOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo "107 harness: live status -- 21:00 PDT+, 0 lanes running"; exit 0 ;;
    "pr list")
        [[ "$args" == *"--jq"* ]] && exit 0
        if [ -n "${SELFTEST_FOLDREADY:-}" ]; then
            echo '[{"number": 900, "state": "OPEN", "isDraft": false, "headRefName": "lane/stuckx", "labels": [{"name": "fold-ready"}]}]'
        else echo "[]"; fi
        exit 0 ;;
    "pr view") [[ "$args" == *"mergeable"* ]] && echo "{\"mergeable\": \"${SELFTEST_FOLDREADY:-UNKNOWN}\", \"statusCheckRollup\": []}"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"/events"* ]] && { date -u -d '3 hours ago' +%FT%TZ; exit 0; }
        [[ "$args" == *"/pages"* ]] && { [ -n "${SELFTEST_PAGES_URL:-}" ] && echo "$SELFTEST_PAGES_URL"; exit 0; }
        [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
GHEOF
chmod +x "$T/bin/gh"
echo 5738613782 > "$HAKUX_WORK/status/comment-id"
# The page counts the HOST's dispatcher workers (`pgrep -fc`), which come and
# go under this fake host when it runs on the real one -- a real change, and
# so a republish, which is right on the host and noise here. Pin it.
printf '#!/usr/bin/env bash\necho 0\n' > "$T/bin/pgrep"; chmod +x "$T/bin/pgrep"
# The board and the title staging dir are pinned for the same reason. Unpinned,
# the lane block reads origin/board of the checkout, which CI fetches too, so the
# live board's blocked lanes became attention rows. On 2026-09-26 eleven of them
# pushed this fixture's queue line past the ten the page shows, and "the
# republished page carries the change" went red on master's own code.
SH_NOBOARD="$T/status-dash-noboard"; mkdir -p "$SH_NOBOARD"
sh_tick() { STATUS_BOARD_DIR="$SH_NOBOARD" HAKUX_XISO_DIR="$T/status-dash-noxiso" \
    STATUS_PAGES_REMOTE="$SH_BARE" SELFTEST_GH_LOG="$SH_LOG" bash "$HERE/status.sh" "$@" 2>&1; }
: > "$SH_LOG"; sout=$(sh_tick)
check "the first tick publishes gh-pages" grep -q '^pages: published' <<< "$sout"
check "gh-pages holds index.html" bash -c 'git --git-dir="$1" cat-file -e gh-pages:index.html' _ "$SH_BARE"
check "gh-pages holds .nojekyll" bash -c 'git --git-dir="$1" cat-file -e gh-pages:.nojekyll' _ "$SH_BARE"
sh_c1=$(git --git-dir="$SH_BARE" rev-parse gh-pages 2>/dev/null)
sout=$(sh_tick)
check "a second tick with nothing changed does not republish" grep -q '^pages: unchanged' <<< "$sout"
check "...so two ticks make one commit" [ "$(git --git-dir="$SH_BARE" rev-parse gh-pages 2>/dev/null)" = "$sh_c1" ]
# Content moved, but inside the ten-minute gap: held back.
printf '{"id": "1-selftest-dash", "requester": "dashx", "queued_utc": "%s"}\n' "$(date -u -d '2 hours ago' +%FT%TZ)" > "$DISPATCH_DIR/queue/1-selftest-dash.req"
sout=$(sh_tick)
check "a change inside the ten-minute gap waits" grep -q '^pages: changed, but published' <<< "$sout"
# Past the gap: published, and still one commit with no parent.
read -r sh_t sh_k < "$HAKUX_WORK/status/pages-state"; echo "$(( sh_t - 700 )) $sh_k" > "$HAKUX_WORK/status/pages-state"
sout=$(sh_tick)
check "the change is published once the gap has passed" grep -q '^pages: published' <<< "$sout"
check "gh-pages is still exactly one commit" [ "$(git --git-dir="$SH_BARE" rev-list --count gh-pages 2>/dev/null)" = 1 ]
check "the republished page carries the change" \
    bash -c 'git --git-dir="$1" show gh-pages:index.html | grep -q "1 run queued while"' _ "$SH_BARE"
rm -f "$DISPATCH_DIR/queue/1-selftest-dash.req"
read -r sh_t sh_k < "$HAKUX_WORK/status/pages-state"; echo "$(( sh_t - 700 )) $sh_k" > "$HAKUX_WORK/status/pages-state"
sh_tick >/dev/null
# Unchanged but past the heartbeat: republished, so its age means something.
sout=$(sh_tick)
check "(the heartbeat case starts from an unchanged page)" grep -q '^pages: unchanged' <<< "$sout"
read -r sh_t sh_k < "$HAKUX_WORK/status/pages-state"; echo "$(( sh_t - 1900 )) $sh_k" > "$HAKUX_WORK/status/pages-state"
sout=$(sh_tick)
check "an unchanged page is republished at the heartbeat" grep -q '^pages: published' <<< "$sout"
check "without a named remote, a test repository is never pushed" \
    bash -c 'out=$(SELFTEST_GH_LOG=/dev/null bash "$1/status.sh" --pages 2>&1); grep -q "no remote for example/hakux" <<< "$out"' _ "$HERE"
check "the dashboard JSON is written for other readers" python3 -c 'import json,sys; json.load(open(sys.argv[1]))["strip"]' "$HAKUX_WORK/status/status.json"

# ---- 4. #107: legacy until Pages serves the page, then a pointer ONCE
check "before Pages is enabled, #107's legacy roll-up continues" grep -q 'issues/comments/5738613782' "$SH_LOG"
: > "$SH_LOG"; sout=$(SELFTEST_PAGES_URL="https://example.github.io/hakux/" sh_tick)
check "once Pages serves it, #107's body becomes the pointer" grep -q 'api -X PATCH repos/example/hakux/issues/107 -F body=' "$SH_LOG"
check "...naming the URL" grep -q 'https://example.github.io/hakux/' "$HAKUX_WORK/status/POINTER.md"
check "...one last rename, to a title without a clock" grep -q -- '-f title=harness: live status -- moved to https://example.github.io/hakux/' "$SH_LOG"
check "...the old roll-up comment says where it went" grep -q 'issues/comments/5738613782 -f body=The roll-up moved' "$SH_LOG"
check "...the issue is kept pinned" grep -q '^issue pin 107' "$SH_LOG"
check "...and locked" grep -q '^issue lock 107' "$SH_LOG"
: > "$SH_LOG"; sout=$(SELFTEST_PAGES_URL="https://example.github.io/hakux/" sh_tick)
check "after the switch a tick never writes to #107" sh_no -E 'api -X PATCH repos/example/hakux/issues/(107|comments)' "$SH_LOG"
check "...so it can never rename it again" sh_no -- '-f title=' "$SH_LOG"
check "...and says so" grep -q 'points at the dashboard; not touched' <<< "$sout"

# ---- 5. a fold-ready PR left unfolded for an hour, with the reason
sout=$(SELFTEST_FOLDREADY=CONFLICTING SELFTEST_GH_LOG="$SH_LOG" bash "$HERE/status.sh" --print 2>&1)
check "a CONFLICTING fold-ready PR is named in NEEDS ATTENTION" \
    python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["attention"]; sys.exit(0 if any("PR #900" in x["action"] and "CONFLICTING" in x["action"] for x in a) else 1)' "$HAKUX_WORK/status/status.json"
sout=$(SELFTEST_FOLDREADY=MERGEABLE SELFTEST_GH_LOG="$SH_LOG" bash "$HERE/status.sh" --print 2>&1)
check "a mergeable one with no CI run says CI never ran" \
    python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["attention"]; sys.exit(0 if any("PR #900" in x["action"] and "CI never ran" in x["action"] for x in a) else 1)' "$HAKUX_WORK/status/status.json"

# ---- 6. the 0.5 panel (#432): counts from their files, the Ghoulies gate
#   thor g-old  Ghoulies, perf lines: 100 outside 90-240 s, t/10 inside
#               (9..24, sixteen lines) -> median 16.5; a window read wrong
#               or a mean would not give it
#   thor g-new  Ghoulies, NEWER, no perf lines -> passed over, counted
#   thor x      not Ghoulies, newest of all, perf 50 -> never read
#   nova        no soak -> named as missing, and the gate is NOT MET
#   verdicts    A passes Playable on both, B on thor only -> tested 2,
#               Playable 1; titles json lists 3; no xiso manifest
SP="$T/status-panel"; rm -rf "$SP"; mkdir -p "$SP/res" "$SP/titles"
echo '["a", "b", "c"]' > "$SP/titles/already-on-handhelds.json"
sp_soak() {   # <id> <device> <title> <perf: yes|no|flat> <mtime>
    mkdir -p "$SP/res/$1"
    printf '{"title": "%s", "device": "%s", "ref": "abcdef0123456"}\n' "$3" "$2" > "$SP/res/$1/request.json"
    python3 - "$SP/res/$1/logcat.txt" "$4" <<'PY'
import sys
out = ["--------- beginning of main"]
for t in range(0, 300, 10):
    g = 50 if sys.argv[2] == "flat" else (t // 10 if 90 <= t <= 240 else 100)
    line = "09-26 10:%02d:%02d.000 I/hakuX-perf( 1): gfps=%d G:33" % (t // 60, t % 60, g)
    out.append(line if sys.argv[2] != "no" else "09-26 10:00:00.000 I/hakuX   ( 1): frame")
open(sys.argv[1], "w").write("\n".join(out) + "\n")
PY
    touch -d "$5" "$SP/res/$1/DONE"
}
sp_soak g-old thor "Grabbed by the Ghoulies (USA).xiso.iso" yes "2 hours ago"
sp_soak g-new thor "Grabbed by the Ghoulies (USA).xiso.iso" no "1 hour ago"
sp_soak x     thor "Blinx (USA).xiso.iso" flat "10 minutes ago"
sp_verdict() { mkdir -p "$SP/res/$1"; printf '{"name": "%s", "device": "%s", "pass": %s, "rating_candidate": "Playable", "judged_utc": "2026-09-26T10:00:00Z"}\n' "$2" "$3" "$4" > "$SP/res/$1/verdict.json"; }
sp_verdict v1 A thor true; sp_verdict v2 A nova true; sp_verdict v3 B thor true; sp_verdict v4 B nova false
python3 "$SH_PY" release05 --titles "$SP/titles" --results "$SP/res" --xiso "$SP/no-xiso" > "$SP/facts.tsv"
sp_has() { grep -qxF -- "$(printf "$1")" "$SP/facts.tsv"; }
check "panel: titles on the handhelds are counted from the json" sp_has 'r05\tcopied\t3'
check "panel: a missing staging manifest is 'no source', naming the file" sp_has 'r05\tstaged\tno source: <xiso dir>/manifest.csv'
check "panel: a title with a verdict on either handheld is tested" sp_has 'r05\ttested\t2'
check "panel: Playable needs a pass on every handheld tested" sp_has 'r05\tplayable\t1'
check "panel: the gate reads the newest Ghoulies soak WITH gfps, median over 90-240 s, and counts the newer one passed over" \
    bash -c 'grep -qP "^r05gate\tthor\t16.5\t16\tg-old\tabcdef0123\t[0-9]+\t1$" "$1"' _ "$SP/facts.tsv"
check "panel: a handheld with no soak has an empty row" sp_has 'r05gate\tnova\t\t0\t\t\t\t0'
printf 'release_name\t0.5\nrelease_titles_target\t145\nr05issues_known\nr05issue\t424\tlane.x\tPerformance\n' >> "$SP/facts.tsv"
echo '{}' > "$SP/lanes.json"; : > "$SP/md"
python3 "$SH_PY" build --facts "$SP/facts.tsv" --lanes "$SP/lanes.json" --md "$SP/md" --json "$SP/s.json" --html "$SP/i.html"
sp_text=$(python3 "$SH_PY" panel "$SP/s.json")
check "panel: no count against a quota (the counts are the title table's)" sh_no -F 'of 145' <<< "$sp_text"
check "panel: one handheld with no readable soak is NOT MET, and says which" \
    grep -qF 'NOT MET -- thor 16.5 (n=16; g-old' <<< "$sp_text"
check "panel: ...and names the soak it passed over" grep -qF '1 newer soak logged no gfps in 90-240 s' <<< "$sp_text"
check "panel: the lane on each 0.5 issue" grep -qF '#424 lane.x -- Performance' <<< "$sp_text"
check "panel: the page carries the gate's readings" grep -qF 'thor: <b>16.5</b> gfps median (n=16)' "$SP/i.html"

# ---- restore selftest.sh's own shim and state for any later fragment.
rm -f "$T/bin/pgrep" "$HAKUX_WORK/status/comment-id" "$HAKUX_WORK/status/issue-pointer" "$HAKUX_WORK/status/pages-state"
rm -rf "$HAKUX_WORK/status/pages"
cat > "$T/bin/gh" <<'GHEOF'
#!/usr/bin/env bash
echo "$*" >> "${SELFTEST_GH_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list")
        if [[ "$args" == *"--head lane/selftest"* ]]; then
            [[ "$args" == *".[0].number"* ]] && { echo 102; exit 0; }
            echo "#102 draft"; exit 0
        fi
        [[ "$args" == *"--jq"* ]] && exit 0
        echo "[]"; exit 0 ;;
    "pr view") echo GREEN; exit 0 ;;
    "issue list") [[ "$args" == *"harness-status"* ]] && echo 107; exit 0 ;;
    "issue create") echo "https://github.com/example/hakux/issues/107"; exit 0 ;;
    "api "*|"api -X"*)
        [[ "$args" == *"--jq .id"* ]] && { echo 5; exit 0; }
        [[ "$args" == *"/labels"* && "$args" != *"-X"* ]] && { printf '%s\n' ${SELFTEST_LABELS:-}; exit 0; }
        exit 0 ;;
    *) exit 0 ;;
esac
GHEOF
chmod +x "$T/bin/gh"
