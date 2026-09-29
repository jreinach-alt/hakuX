# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# status.sh: the dashboard never publishes a degraded render over a good one (#507).
#
# WHY THIS EXISTS. At 17:42 PDT on 2026-09-28, just after both handhelds left
# USB, the board tick published a page reading "Measured 0 / 145, Benchmarked
# 0 / 145, Playable 0 / 50; 0 lanes; no devices; queue not read" over one
# reading 47 / 11 / 1 with 11 lanes, and PAGES_MIN_GAP held the next good
# render back six minutes. That page is what status_html.py build makes when
# the lane block's lanes.json is missing; the board sends status.sh's output to
# /dev/null, so nothing said why. Here the lane block is made to hang the way it
# did (a gh read that does not return, killed at STATUS_LANES_TIMEOUT), against
# a local bare repository standing in for gh-pages, in a work dir of its own.
#
# Each case runs once on the real scripts and once per mutant that removes the
# behaviour it checks; a case that stays green under its mutant checks nothing.
#   refuse   a degraded render past the gap is not published    (mutant: no guard)
#   atonce   the next complete render publishes inside the gap  (mutant: no bypass)
#   decrease a real one-title decrease still publishes          (mutant: any decrease refused)
#   why      the failing step and its stderr are in render-degraded.log with the
#            output sent to /dev/null                           (mutant: no render record)
#
# Independent of every other fragment: its own work dir, dispatch dir, PATH and remote.

echo "== status.sh refuses a degraded render (#507)"
SG="$T/statusguard"; rm -rf "$SG"; mkdir -p "$SG/bin"
cat > "$SG/bin/gh" <<'GHEOF'
#!/usr/bin/env bash
# The lane block's first GitHub read is gather()'s `pr list --limit 300`; with
# SG_HANG=1 it does not return, as the reads after the devices vanished did not.
case "$1 $2" in "auth status") exit 0 ;; esac
[ "${SG_HANG:-0}" = 1 ] && [[ "$*" == *"--limit 300"* ]] && { sleep 20; exit 1; }
case "$1 $2" in "pr list"|"issue list") [[ "$*" == *"--jq"* ]] || echo "[]" ;; esac
exit 0
GHEOF
printf '#!/usr/bin/env bash\necho 0\n' > "$SG/bin/pgrep"; chmod +x "$SG/bin/gh" "$SG/bin/pgrep"

# Two measured titles, from verdicts (status_html.py titles05 reads dispatch/results).
sg_verdict() {   # <run id> <title>
    mkdir -p "$SG/work/dispatch/results/$1"
    printf '{"name": "%s", "title": "%s (USA).xiso.iso", "device": "nova", "fps_window_median": 31.0, "fps_ok_share": 0.9, "fps_bar": 28.5, "reached_gameplay": true, "pass": false, "failing": "soak"}\n' \
        "$2" "$2" > "$SG/work/dispatch/results/$1/verdict.json"
}
sg_tick() {   # <jobs dir> [env...]: one --pages tick; its output is the tick's words
    env PATH="$SG/bin:$PATH" HAKUX_WORK="$SG/work" DISPATCH_DIR="$SG/work/dispatch" GH_REPO=example/hakux \
        STATUS_BOARD_DIR="$SG/noboard" HAKUX_XISO_DIR="$SG/noxiso" STATUS_TITLES_DIR="$SG/notitles" \
        STATUS_RELEASE_CONF="$SG/none.toml" TITLE_TARGETS="$SG/none-targets.toml" TITLESTATE_DIR="$SG/ts" \
        STATUS_PAGES_REMOTE="$SG/pages.git" STATUS_LANES_TIMEOUT=3 "${@:2}" bash "$1/status.sh" --pages 2>&1
}
sg_head() { git --git-dir="$SG/pages.git" rev-parse gh-pages 2>/dev/null; }
sg_page() { git --git-dir="$SG/pages.git" show gh-pages:index.html 2>/dev/null; }
sg_age() {    # pretend the last publish was $1 s ago
    local t k; read -r t k < "$SG/work/status/pages-state"; echo "$(( t - $1 )) $k" > "$SG/work/status/pages-state"
}

# The scenario, against the scripts in <jobs dir>; one "<case> ok|FAIL <why>" line each.
sg_scenario() {
    local J=$1 o c1 c2
    rm -rf "$SG/work" "$SG/pages.git"; mkdir -p "$SG/work/dispatch/queue" "$SG/work/dispatch/running" "$SG/noboard"
    git init -q --bare "$SG/pages.git"
    sg_verdict 1790460000-sg-a "Zz Alpha"; sg_verdict 1790460100-sg-b "Zz Bravo"
    # 1. a good page goes up, and it read everything
    o=$(sg_tick "$J"); c1=$(sg_head)
    if grep -q '^pages: published' <<< "$o" && sg_page | grep -q 'Measured 2 /'; then echo "setup ok"
    else echo "setup FAIL the first good tick did not publish Measured 2: $(tr '\n' ' ' <<< "$o" | cut -c1-300)"; fi
    # 2. inside the gap, the lane block hangs: refused, as the guard runs first
    printf '{"id": "1-sg-q", "requester": "sgx", "queued_utc": "%s"}\n' "$(date -u -d '1 hour ago' +%FT%TZ)" > "$SG/work/dispatch/queue/1-sg-q.req"
    o=$(sg_tick "$J" SG_HANG=1)
    grep -q '^pages: degraded render (' <<< "$o" || echo "atonce FAIL the hung tick inside the gap was not judged degraded: $(tr '\n' ' ' <<< "$o" | cut -c1-300)"
    # 3. the next complete render, still inside the gap, publishes at once
    o=$(sg_tick "$J"); c2=$(sg_head)
    if [ "$c2" != "$c1" ] && grep -q 'publishes at once' <<< "$o" && sg_page | grep -q '1 run queued while'; then echo "atonce ok"
    else echo "atonce FAIL a complete render after a refusal waited: $(tr '\n' ' ' <<< "$o" | cut -c1-300)"; fi
    # 4. past the gap (the incident), the lane block hangs, and the caller discards the output
    rm -f "$SG/work/dispatch/queue/1-sg-q.req"; sg_age 700; : > "$SG/work/status/render-degraded.log"
    sg_tick "$J" SG_HANG=1 > /dev/null
    if [ "$(sg_head)" = "$c2" ] && sg_page | grep -q 'Measured 2 /' && ! sg_page | grep -q 'queue not read'; then echo "refuse ok"
    else echo "refuse FAIL a degraded render replaced the good page (it reads: $(sg_page | grep -o 'Measured [0-9]* /[^<]*' | head -1))"; fi
    if grep -q 'render: status_html.py lanes exited 124 after' "$SG/work/status/render-degraded.log" \
       && grep -q '^    status_html.py lanes timed out after 3 s' "$SG/work/status/render-degraded.log" \
       && grep -q 'pages: degraded render (the lane block was not read.*); not published' "$SG/work/status/render-degraded.log"; then echo "why ok"
    else echo "why FAIL render-degraded.log does not name the step, its stderr and the refusal: $(tr '\n' '|' < "$SG/work/status/render-degraded.log" | cut -c1-400)"; fi
    # 5. a title's reading is withdrawn: a real decrease, published
    rm -rf "$SG/work/dispatch/results/1790460100-sg-b"; sg_age 700
    o=$(sg_tick "$J")
    if grep -q '^pages: published' <<< "$o" && sg_page | grep -q 'Measured 1 /'; then echo "decrease ok"
    else echo "decrease FAIL a real one-title decrease was not published: $(tr '\n' ' ' <<< "$o" | cut -c1-300)"; fi
}

sg_scenario "$HERE" > "$SG/real.txt"
for sg_c in setup refuse atonce decrease why; do
    check "real scripts: $sg_c" grep -q "^$sg_c ok" "$SG/real.txt"
done
grep 'FAIL' "$SG/real.txt" | sed 's/^/    /'

# The mutants: each removes one behaviour, and the case that checks it must go red.
sg_mutant() {   # <name> <file> <python re.sub pattern> <replacement>
    local M="$SG/mut-$1"; rm -rf "$M"; mkdir -p "$M"
    cp "$HERE"/*.sh "$HERE"/*.py "$HERE"/*.env "$M/" 2>/dev/null
    python3 -c '
import re, sys
p, pat, rep = sys.argv[1:4]
s = open(p).read(); t, n = re.subn(pat, rep, s)
if n != 1: sys.exit("mutant pattern matched %d times in %s" % (n, p))
open(p, "w").write(t)' "$M/$2" "$3" "$4" || return 2
    sg_scenario "$M" > "$SG/mut-$1.txt"
}
sg_red() {      # <mutant> <case>: the mutant applied, and turned that case red
    sg_mutant "$1" "$3" "$4" "$5" && grep -q "^$2 FAIL" "$SG/mut-$1.txt"
}
check "mutant: no guard -> refuse goes red" \
    sg_red noguard refuse status.sh 'if \[ "\$grc" -eq 1 \]; then' 'if false; then'
check "mutant: no bypass of the gap after a refusal -> atonce goes red" \
    sg_red nobypass atonce status.sh 'if \[ -s "\$PREFUSED" \]; then' 'if false; then'
check "mutant: any decrease refused -> decrease goes red" \
    sg_red anydecrease decrease status_html.py 'if any\(old.get\(k\) for k in c\) and not any\(new.get\(k\) for k in c\):' 'if any(new.get(k, 0) < old.get(k, 0) for k in c):'
check "mutant: no render record -> why goes red" \
    sg_red norecord why status.sh '\[ -n "\$steps_failed" \] && deglog' 'false \&\& deglog'
