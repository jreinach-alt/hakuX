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

echo "== status.sh dashboard"
SH_PY="$HERE/status_html.py"
sh_no() { ! grep -q "$@"; }

# ---- 1. the renderer, from a fixture JSON: first screen, self-contained, public-safe
SH_J="$T/status-dash.json"
cat > "$SH_J" <<'EOF'
{"now": 1790400000, "generated": "2026-09-25 22:00 PDT", "tz": "PDT", "floor_secs": 1800, "heartbeat_secs": 1800,
 "next_due": "2026-09-25 22:30 PDT",
 "strip": {"devices": [{"name": "thor", "state": "running", "detail": "arms-x: 1-arms-x-fix"},
                       {"name": "nova", "state": "held", "detail": "owner hold, see /home/someone/.ssh/id_ed25519"}],
           "queue": 3, "queue_idle": 90, "arms_running": 1, "lanes_running": 2, "lane_cap": 24,
           "last_fold": 1790399000, "last_fold_subject": "PR #1 lane/x"},
 "attention": [{"kind": "fold", "text": "PR #9 fold-ready for 2h and not folded: CONFLICTING, mail me at someone@example.com, token ghp_abcdefghijklmnopqrstuvwxyz0123"}],
 "release": {"gate": "the gate", "candidate": "none cut yet", "blockers": [{"number": "311", "title": "Ghoulies"}], "blockers_known": true},
 "details_md": "## title\n\n### Lanes running\n\n| lane | state |\n|---|---|\n| a | b \\| c |\n\n- `code` and **bold**\n\n```\nraw /home/someone/x\n```\n"}
EOF
SH_H="$T/status-dash.html"
python3 "$SH_PY" render "$SH_J" -o "$SH_H"; check "status_html.py renders a fixture" [ -s "$SH_H" ]
check "the page refreshes itself every 60 s" grep -q '<meta http-equiv="refresh" content="60">' "$SH_H"
check "the page has a dark variant" grep -q 'prefers-color-scheme:dark' "$SH_H"
check "the page is phone-width aware" grep -q 'name="viewport" content="width=device-width' "$SH_H"
check "the page loads no external script or stylesheet" sh_no -E '<script[^>]+src=|<link[^>]+stylesheet' "$SH_H"
check "the page says how long ago it was updated" grep -q 'id="age" data-t="1790400000"' "$SH_H"
check "the strip names the Thor's run" grep -q 'arms-x: 1-arms-x-fix' "$SH_H"
check "NEEDS ATTENTION is on the page" grep -q 'NEEDS ATTENTION (1)' "$SH_H"
check "the release blockers are on the page" grep -q '#311 Ghoulies' "$SH_H"
sh_order() { python3 - "$1" <<'PY'
import sys; s = open(sys.argv[1]).read()
a, b, c, d = (s.find(x) for x in ('class="strip"', "NEEDS ATTENTION", "Release", ">Lanes running</h"))
sys.exit(0 if -1 < a < b < c < d else 1)
PY
}
check "strip, then NEEDS ATTENTION, then the gate, then the details" sh_order "$SH_H"
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
sed 's/"queue": 3/"queue": 4/' "$SH_J" > "$T/status-dash3.json"
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
sh_tick() { STATUS_PAGES_REMOTE="$SH_BARE" SELFTEST_GH_LOG="$SH_LOG" bash "$HERE/status.sh" "$@" 2>&1; }
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
    bash -c 'git --git-dir="$1" show gh-pages:index.html | grep -q "queued over 60 min; oldest 1-selftest-dash"' _ "$SH_BARE"
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
    python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["attention"]; sys.exit(0 if any("PR #900" in x["text"] and "CONFLICTING" in x["text"] for x in a) else 1)' "$HAKUX_WORK/status/status.json"
sout=$(SELFTEST_FOLDREADY=MERGEABLE SELFTEST_GH_LOG="$SH_LOG" bash "$HERE/status.sh" --print 2>&1)
check "a mergeable one with no CI run says CI never ran" \
    python3 -c 'import json,sys; a=json.load(open(sys.argv[1]))["attention"]; sys.exit(0 if any("PR #900" in x["text"] and "CI never ran" in x["text"] for x in a) else 1)' "$HAKUX_WORK/status/status.json"

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
