# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# Per-run battery admission (#507, owner 2026-09-28): the dispatcher claims a
# request on a handheld only when the battery level covers 15 % + 5 % + the
# learned drain over the run (battery_admit.py). dispatcher.sh's own
# serve_queue and serve_one, sourced, with an adb whose `dumpsys battery`
# answers a level from a file and a build_ref that fails at once -- so a claim
# is visible as results/<id>/request.json and nothing runs.
#
# The fixture history teaches rate 27 %/h and overhead 340 s exactly:
#   four nova soaks from 40 % over 600 s, falling 2/3/4/6 % = 12/18/24/36 %/h,
#   p75 = 24 + 0.25 x 12 = 27; DONE 0/20/40/60 s after the last sample with
#   `seconds` 300, so overhead 300/320/340/360;
#   a nova soak from 90 % that counts for overhead (340 s) and not for rate
#   (above LEARN_BELOW, 0 %/h), so overhead p75 over five = 340;
#   and two that count for neither: a thor soak and a nova test-disc run
#   (each 120 %/h, overhead 1000 s).
# So a 2100 s soak needs 15 + 5 + 27 x 2440 / 3600 = 38.3 and a 300 s soak
# 24.8 (each 0.049 up, then to one decimal). Those cases run the nova at the
# default floor 15 (BATTERY_FLOOR_nova=15); the nova's own floor, 30, has its
# own case: 53.3 and 39.8.

echo "== battery admission: claim only what the level covers; the head is not starved"
BA="$T/battadmit"; rm -rf "$BA"; mkdir -p "$BA/bin"
cat > "$BA/bin/adb" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$BA_ADB_LOG"
case "$*" in
    *"dumpsys battery"*) [ "$(cat "$BA_LEVEL")" != FAIL ] || { echo "error: device offline" >&2; exit 1; }
        printf 'Current Battery Service state:\n  AC powered: false\n  USB powered: true\n  level: %s\n  scale: 100\n' "$(cat "$BA_LEVEL")" ;;
    devices*) printf 'List of devices attached\nee317437\tdevice\n' ;;
esac
exit 0
EOF
chmod +x "$BA/bin/adb"
cat > "$BA/drive.sh" <<'EOF'
# drive.sh <testing-dir> <dispatch-dir>: one queue walk, as the worker loop does
export DISPATCH_DIR="$2" SERIAL=ee317437
. "$1/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
build_ref() { return 4; }
shopt -s nullglob
for _w in $(seq "${BA_WALKS:-1}"); do   # several walks in one worker, as its loop does
    reqs=("$2"/queue/*.req)
    serve_queue "${reqs[@]}"
    echo "walk=$?"
    # BA_LEVEL_AT=k:L -- the level becomes L after walk k, in the same worker
    BA_LEVEL_AT="${BA_LEVEL_AT:-}"
    [ "${BA_LEVEL_AT%%:*}" != "$_w" ] || echo "${BA_LEVEL_AT#*:}" > "$BA_LEVEL"
    [ "$_w" = "${BA_WALKS:-1}" ] || sleep 1.1   # so a running clock in a line moves
done
EOF

ba_hist() {   # <dispatch dir>: the fixture history above
    python3 - "$1" <<'PY'
import json, os, sys
d = sys.argv[1]
T0 = 1790000000.0
def result(rid, label, title, seconds, cap0, fall, span, done_after, i):
    r = os.path.join(d, "results", rid); os.makedirs(r)
    t0 = T0 + 10000 * i
    json.dump(dict(id=rid, title=title, seconds=seconds, runs=1), open(os.path.join(r, "request.json"), "w"))
    json.dump(dict(device_label=label, kind="soak" if title else None), open(os.path.join(r, "result.json"), "w"))
    if cap0 is not None:
        with open(os.path.join(r, "thermal.jsonl"), "w") as fh:
            for k, (dt, c) in enumerate([(0, cap0), (span / 2, cap0 - fall / 2.0), (span, cap0 - fall)]):
                fh.write(json.dumps(dict(t=t0 + dt, label=["cool", "hold", "end"][k],
                                         pw=dict(battery=dict(capacity=int(round(c)), status="Charging")))) + "\n")
    open(os.path.join(r, "DONE"), "w").close()
    for f in os.listdir(r):
        os.utime(os.path.join(r, f), (t0 + span + done_after, t0 + span + done_after))
for i, (fall, after) in enumerate([(2, 0), (3, 20), (4, 40), (6, 60)]):
    result("h-nova-%d" % i, "nova", "Fixture.iso", 300, 40, fall, 600, after, i)
result("h-nova-full", "nova", "Fixture.iso", 300, 90, 0, 600, 40, 4)       # above LEARN_BELOW
result("h-thor", "thor", "Fixture.iso", 300, 40, 20, 600, 1000, 5)        # another device
result("h-nova-disc", "nova", "", 60, 40, 20, 600, 1000, 6)               # another kind
PY
}
ba_setup() {  # <dir> <level> <req-id:seconds>... -> a fresh dispatch dir, nothing walked
    local dir="$1" level="$2" q; shift 2
    rm -rf "$dir"; mkdir -p "$dir"/{queue,running,results,logs,lanes}
    ba_hist "$dir"
    for q in "$@"; do
        printf '{"id":"%s","requester":"selftest","purpose":"battery","ref":"HEAD","title":"Fixture.iso","seconds":%s,"runs":1}\n' \
            "${q%%:*}" "${q##*:}" > "$dir/queue/${q%%:*}.req"
    done
    echo "$level" > "$dir/level"
}
ba_case() {   # <tree> <dir> <level> <req-id:seconds>... -> set up, walk once
    local tree="$1"; shift
    ba_setup "$@"
    ba_walk "$tree" "$1"
}
ba_walk() {   # <tree> <dir> [walks]: one more worker over what is queued now
    BATTERY_FLOOR_nova="${BA_FLOOR_NOVA-15}" BA_WALKS="${3:-1}" PATH="$BA/bin:$PATH" BA_ADB_LOG="$2/adb.log" BA_LEVEL="$2/level" ADB_QUICK_TIMEOUT=5 ADB_RETRY_SLEEP=0 \
        timeout -k 2 60 bash "$BA/drive.sh" "$1" "$2" >>"$2/drive.out" 2>&1
}
ba_claimed() { [ -f "$1/results/$2/request.json" ] && [ ! -e "$1/queue/$2.req" ]; }
ba_queued()  { [ -e "$1/queue/$2.req" ] && [ ! -e "$1/results/$2/request.json" ]; }
ba_logged()  { grep -qF -- "$2" "$1/logs/dispatcher.log"; }
ba_bjson()   { python3 -c 'import json,sys; b=json.load(open(sys.argv[1])); sys.exit(0 if (b["battery_start"], b["need"], b["rate"]) == (int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])) else 1)' "$@"; }
ba_mut() {   # <file under docs/testing> <sed-expression> <name> -> echoes the tree, "" if the sed matched nothing
    local rel="$1" dir="$BA/$3" x
    rm -rf "$dir"; mkdir -p "$dir"
    for x in "$TESTING"/*; do ln -s "$x" "$dir/$(basename "$x")"; done
    rm -f "$dir/$rel"
    sed "$2" "$TESTING/$rel" > "$dir/$rel" || return 0
    cmp -s "$dir/$rel" "$TESTING/$rel" || printf '%s\n' "$dir"
}

# -------------------------------------------------------------- the learning
ba_setup "$BA/l" 0
BAL=$(python3 "$TESTING/battery_admit.py" learn "$BA/l" nova soak)
ba_learned() {   # <learn json> -> 0 when it is the fixture's 27 %/h n=4 and 340 s n=5
    python3 -c 'import json,sys; v=json.loads(sys.argv[1]); sys.exit(0 if (v["rate"], v["rate_src"], v["rate_n"], v["overhead_s"], v["overhead_n"]) == (27.0, "learned", 4, 340.0, 5) else 1)' "$1"
}
if ba_learned "$BAL"; then ok "learn: nova soak rate is p75 27 %/h of the four low-charge nova soaks, overhead p75 340 s"
else bad "learn: want rate 27 learned n=4, overhead 340 n=5 -- got $(printf '%s' "$BAL" | tr -d '\n' | cut -c1-300)"; fi
check "learn: the thor with no history of its own answers from the fallback table (10 %/h)" \
    python3 -c 'import json,sys; v=json.loads(sys.argv[1]); sys.exit(0 if (v["rate"], v["rate_src"]) == (10.0, "fallback") else 1)' \
    "$(python3 "$TESTING/battery_admit.py" learn "$BA/l" thor soak)"

# ------------------------------------------------------------------ fits
ba_case "$TESTING" "$BA/a" 50 0-long:2100
check "fits: level 50 >= need 38.3 -> the 2100 s soak is claimed" ba_claimed "$BA/a" 0-long
check "fits: battery.json records battery_start 50, need 38.3, rate 27" ba_bjson "$BA/a/results/0-long/battery.json" 50 38.3 27
check "fits: the admit line names level, need and the learned inputs" \
    ba_logged "$BA/a" "BATTERY: admit 0-long: level 50 >= need 38.3 (floor 15 + margin 5 + rate 27.0 %/h learned n=4, 1 x (2100s + overhead 340s learned n=5))"
check "fits: the level came from dumpsys battery" grep -q "shell dumpsys battery" "$BA/a/adb.log"

# ------------------------------------------ does not fit -> the shorter one
ba_case "$TESTING" "$BA/b" 30 0-long:2100 1-short:300
check "skip: level 30 < need 38.3 -> the long head stays queued" ba_queued "$BA/b" 0-long
check "skip: the 300 s soak behind it (need 24.8) is claimed instead" ba_claimed "$BA/b" 1-short
check "skip: logged as BATTERY: skip <id>: level L < need N" ba_logged "$BA/b" "BATTERY: skip 0-long: level 30 < need 38.3"
check "skip: the backfill records battery_start 30, need 24.8, rate 27" ba_bjson "$BA/b/results/1-short/battery.json" 30 24.8 27

# ---------------------------------------------------------- nothing fits
ba_case "$TESTING" "$BA/c" 22 0-long:2100 1-short:300
check "none: level 22 -> the long soak is not claimed" ba_queued "$BA/c" 0-long
check "none: level 22 < need 24.8 -> nor the short one" ba_queued "$BA/c" 1-short
check "none: the walk reports nothing served" grep -q "walk=1" "$BA/c/drive.out"
check "none: running/ is empty" bash -c '! ls "$1"/running/*.req >/dev/null 2>&1' _ "$BA/c"

# --------------------------------------------- the head is not starved
# Refused for 2000 s (> BATTERY_HEAD_WAIT_S 1800): the head now holds the
# device. The short one fits and is NOT claimed; when the level reaches the
# head's need the head is claimed on that walk.
ba_starve() {   # <tree> <dir>
    ba_setup "$2" 30 0-long:2100 1-short:300
    python3 -c 'import json,sys,time; json.dump(dict(id="0-long", since=time.time()-2000), open(sys.argv[1],"w"))' "$2/.battery_head.nova"
    ba_walk "$1" "$2"
}
ba_starve "$TESTING" "$BA/e"
check "starve: head refused 2000 s -> the short soak that fits is held back" ba_queued "$BA/e" 1-short
check "starve: logged as a hold for the head" ba_logged "$BA/e" "BATTERY: hold for head 0-long"
echo 39 > "$BA/e/level"; rm -f "$BA/e/.battery_level.nova"
ba_walk "$TESTING" "$BA/e"
check "starve: at level 39 >= 38.3 the head is claimed first" ba_claimed "$BA/e" 0-long
check "starve: and the reservation is cleared" test ! -e "$BA/e/.battery_head.nova"

# ------------------------------------------- a head that can never fit
# Uncapped, 20000 s needs 15 + 5 + 27 x 20340 / 3600 = 172.6: more than any
# level. Capped at BATTERY_CEILING 75, it is claimed at 80 even after holding
# the device past HEAD_WAIT_S (pass 1 on #587, M2).
ba_ceiling() {   # <tree> <dir>
    ba_setup "$2" 80 0-huge:20000 1-short:300
    python3 -c 'import json,sys,time; json.dump(dict(id="0-huge", since=time.time()-2000), open(sys.argv[1],"w"))' "$2/.battery_head.nova"
    ba_walk "$1" "$2"
}
ba_ceiling "$TESTING" "$BA/g"
check "ceiling: a head needing 172.6 is claimed at level 80 >= the ceiling 75" ba_claimed "$BA/g" 0-huge
check "ceiling: the admit line says the need was capped" \
    ba_logged "$BA/g" "; need 172.6 capped at ceiling 75)"
check "ceiling: battery.json records need 75 and need_uncapped 172.6" \
    python3 -c 'import json,sys; b=json.load(open(sys.argv[1])); sys.exit(0 if (b["need"], b["need_uncapped"]) == (75.0, 172.6) else 1)' "$BA/g/results/0-huge/battery.json"

# ------------------------------------------------ the helper itself fails
# A request the helper cannot read ("seconds": "90s") exits 2 with the reason
# and is admitted unchecked, not refused on every tick as "does not fit"
# (pass 1 on #587, M1).
ba_bad() {   # <tree> <dir>
    ba_setup "$2" 50
    printf '{"id":"0-bad","requester":"selftest","purpose":"battery","ref":"HEAD","title":"Fixture.iso","seconds":"90s","runs":1}\n' > "$2/queue/0-bad.req"
    ba_walk "$1" "$2"
}
ba_bad "$TESTING" "$BA/h"
check "helper fails: the malformed request is claimed" ba_claimed "$BA/h" 0-bad
check "helper fails: logged as exited 2, admitting unchecked, with the reason" \
    ba_logged "$BA/h" "BATTERY: battery_admit.py exited 2 on 0-bad; admitting unchecked: battery_admit.py failed: ValueError"
# One history result that raises is one result not learned from.
ba_setup "$BA/i" 0
mkdir -p "$BA/i/results/h-bad"
printf '{"id":"h-bad","title":"Fixture.iso","seconds":300,"runs":"x"}\n' > "$BA/i/results/h-bad/request.json"
printf '{"device_label":"nova","kind":"soak"}\n' > "$BA/i/results/h-bad/result.json"
: > "$BA/i/results/h-bad/DONE"
if ba_learned "$(python3 "$TESTING/battery_admit.py" learn "$BA/i" nova soak)"; then
    ok "helper fails: a history result that raises is skipped; nova soak still learns 27 %/h, 340 s"
else bad "helper fails: a history result that raises broke the learning"; fi

# ------------------------------------------------ each line logged once
ba_hold3() {   # <tree> <dir>: three walks in one worker, holding for the head
    ba_setup "$2" 30 0-long:2100 1-short:300
    python3 -c 'import json,sys,time; json.dump(dict(id="0-long", since=time.time()-2000), open(sys.argv[1],"w"))' "$2/.battery_head.nova"
    ba_walk "$1" "$2" 3
}
ba_holds() { grep -c 'BATTERY: hold for head 0-long' "$1/logs/dispatcher.log"; }
ba_hold3 "$TESTING" "$BA/j"
check "log once: three walks holding for the head log the hold line once" \
    test "$(ba_holds "$BA/j")" -eq 1

# ------------------------------------------- an unreadable level: fail closed
# dumpsys fails (the Nova's link, 16:41 on 09-28): nothing is claimed, one read
# per walk, one line per episode; the walk after it reads again and claims.
ba_unread() {   # <tree> <dir>: one worker, two walks unreadable, then one at 50
    ba_setup "$2" FAIL 0-long:2100 1-short:300
    BA_LEVEL_AT=2:50 ba_walk "$1" "$2" 3
}
ba_unread "$TESTING" "$BA/u"
check "unreadable: nothing claimed on either unreadable walk (walk=1 twice)" test "$(grep -c "walk=1" "$BA/u/drive.out")" -eq 2
check "unreadable: logged as not claiming" ba_logged "$BA/u" "BATTERY: level unreadable on nova; not claiming 0-long, reading again at the next walk"
check "unreadable: once per episode, not once per walk" test "$(grep -c 'level unreadable on nova' "$BA/u/logs/dispatcher.log")" -eq 1
check "unreadable: one dumpsys per walk, not per request (3 walks, 2 requests)" \
    test "$(grep -c 'dumpsys battery' "$BA/u/adb.log")" -eq 3
check "unreadable: at 50 the next walk claims the head" ba_claimed "$BA/u" 0-long
check "unreadable: and says the level is readable again" ba_logged "$BA/u" "BATTERY: level readable again on nova (50) after "

# --------------------------------------------- the nova's own floor, 30
# No BATTERY_FLOOR_nova: FLOOR_BY_LABEL's 30. At 50 the 2100 s soak needs
# 30 + 5 + 18.3 = 53.3 and waits; the 300 s soak needs 39.8 and is claimed.
ba_novafloor() {   # <tree> <dir>
    BA_FLOOR_NOVA="" ba_case "$1" "$2" 50 0-long:2100 1-short:300
}
ba_novafloor "$TESTING" "$BA/n"
check "nova floor: level 50 < need 53.3 -> the 2100 s soak stays queued" ba_queued "$BA/n" 0-long
check "nova floor: the line names floor 30" ba_logged "$BA/n" "BATTERY: skip 0-long: level 50 < need 53.3 (floor 30 + margin 5 + rate 27.0"
check "nova floor: the 300 s soak (need 39.8) is claimed" ba_claimed "$BA/n" 1-short
check "nova floor: battery.json records need 39.8 and floor 30" \
    python3 -c 'import json,sys; b=json.load(open(sys.argv[1])); sys.exit(0 if (b["need"], b["floor"]) == (39.8, 30.0) else 1)' "$BA/n/results/1-short/battery.json"
printf '{"id":"t-long","title":"Fixture.iso","seconds":2100,"runs":1}\n' > "$BA/l/t-long.req"
ba_thorfloor() {   # <tree>: the thor keeps 15 (its fallback rate 10 %/h, overhead 120 s)
    env -u BATTERY_FLOOR_thor python3 "$1/battery_admit.py" check "$BA/l" thor "$BA/l/t-long.req" 50 \
        | sed -n 2p | python3 -c 'import json,sys; b=json.load(sys.stdin); sys.exit(0 if b["floor"] == 15.0 else 1)'
}
check "thor floor: the thor keeps floor 15" ba_thorfloor "$TESTING"

# ------------------------------------------------------------ the cache
ba_case "$TESTING" "$BA/f" 22 0-long:2100 1-short:300
echo 90 > "$BA/f/level"; ba_walk "$TESTING" "$BA/f"
check "cache: two walks inside a minute read dumpsys once" \
    test "$(grep -c 'dumpsys battery' "$BA/f/adb.log")" -eq 1
check "cache: so the second walk still saw 22 and claimed nothing" ba_queued "$BA/f" 0-long

# ----------------------------------------------- result.json carries it
BAR="$BA/r"; mkdir -p "$BAR"
printf '{"battery_start": 30, "need": 24.9, "rate": 27}\n' > "$BAR/battery.json"
sed -n '/^def _battery(rdir):/,/^        return None$/p' "$TESTING/dispatcher.sh" > "$BAR/soak.py"
check "result.json: the soak writer's _battery reads battery.json back" \
    python3 -c 'import json,os,sys; exec(open(sys.argv[1]).read()); b=_battery(sys.argv[2]); sys.exit(0 if b["need"] == 24.9 else 1)' "$BAR/soak.py" "$BAR"
check "result.json: the soak writer records it as battery=_battery(rdir)" grep -q '^               battery=_battery(rdir)),$' "$TESTING/dispatcher.sh"
sed -n '/^# What admitted it (battery_admit.py): battery_start, need, rate.$/,/^    meta\["battery"\] = None$/p' "$TESTING/dispatcher.sh" > "$BAR/disc.py"
check "result.json: the disc writer sets meta[battery] from battery.json" \
    python3 -c 'import json,os,sys; meta={}; rdir=sys.argv[2]; exec(open(sys.argv[1]).read()); sys.exit(0 if meta["battery"]["rate"] == 27 else 1)' "$BAR/disc.py" "$BAR"

# ----------------------------------------------------------------- mutants
# Each runs a case above against a broken copy and asserts it GOES RED.
M=$(ba_mut battery_admit.py 's/^PCTL = 0.75$/PCTL = 0.5/' m-pctl)
if [ -z "$M" ]; then bad "MUTANT learn: sed matched nothing"
elif ba_learned "$(python3 "$M/battery_admit.py" learn "$BA/l" nova soak)"; then bad "MUTANT learn (median, not p75): still reads 27"
else ok "MUTANT learn (median, not p75): red"; fi
M=$(ba_mut battery_admit.py 's/            and caps\[0\]\[1\] <= LEARN_BELOW):/            ):/' m-below)
if [ -z "$M" ]; then bad "MUTANT learn-below: sed matched nothing"
elif ba_learned "$(python3 "$M/battery_admit.py" learn "$BA/l" nova soak)"; then bad "MUTANT learn-below (a full-battery run counts): still reads 27"
else ok "MUTANT learn-below (a full-battery run counts): red"; fi
M=$(ba_mut battery_admit.py 's/rec\["label"\] != label or //' m-label)
if [ -z "$M" ]; then bad "MUTANT learn-label: sed matched nothing"
elif ba_learned "$(python3 "$M/battery_admit.py" learn "$BA/l" nova soak)"; then bad "MUTANT learn-label (the thor's runs count for the nova): still reads 27"
else ok "MUTANT learn-label (the thor's runs count for the nova): red"; fi

# fits: admission reads the margin as 50 -> the 2100 s soak no longer fits at 50
M=$(ba_mut battery_admit.py 's/^MARGIN = float(os.environ.get("BATTERY_MARGIN", "5"))$/MARGIN = 50.0/' m-floor)
if [ -z "$M" ]; then bad "MUTANT fits: sed matched nothing"
else ba_case "$M" "$BA/ma" 50 0-long:2100
     if ba_claimed "$BA/ma" 0-long; then bad "MUTANT fits (margin 50): still claimed"; else ok "MUTANT fits (margin 50): red"; fi; fi
# skip: serve_one stops at the first refusal -> the short one is never reached
M=$(ba_mut dispatcher.sh 's/^    battery_admit "\$req" "\$id" || return 1$/    battery_admit "$req" "$id" || return 0/' m-skip)
if [ -z "$M" ]; then bad "MUTANT skip: sed matched nothing"
else ba_case "$M" "$BA/mb" 30 0-long:2100 1-short:300
     if ba_claimed "$BA/mb" 1-short; then bad "MUTANT skip (refusal ends the walk): short still claimed"; else ok "MUTANT skip (refusal ends the walk): red"; fi; fi
# none: the admission call removed -> everything is claimed at 22
M=$(ba_mut dispatcher.sh 's/^    battery_admit "\$req" "\$id" || return 1$/    :/' m-none)
if [ -z "$M" ]; then bad "MUTANT none: sed matched nothing"
else ba_case "$M" "$BA/mc" 22 0-long:2100 1-short:300
     if ba_queued "$BA/mc" 0-long && ba_queued "$BA/mc" 1-short; then bad "MUTANT none (no admission): nothing claimed"; else ok "MUTANT none (no admission): red"; fi; fi
# starve: no reservation -> the short one backfills forever
M=$(ba_mut battery_admit.py 's/^        if waited >= HEAD_WAIT_S:$/        if False:/' m-starve)
if [ -z "$M" ]; then bad "MUTANT starve: sed matched nothing"
else ba_starve "$M" "$BA/me"
     if ba_queued "$BA/me" 1-short; then bad "MUTANT starve (no head reservation): short still held"; else ok "MUTANT starve (no head reservation): red"; fi; fi
# cache: never trusted -> two reads
M=$(ba_mut dispatcher.sh 's/-lt "\${BATTERY_CACHE_S:-60}"/-lt 0/' m-cache)
if [ -z "$M" ]; then bad "MUTANT cache: sed matched nothing"
else ba_case "$M" "$BA/mf" 22 0-long:2100 1-short:300; ba_walk "$M" "$BA/mf"
     if [ "$(grep -c 'dumpsys battery' "$BA/mf/adb.log")" -eq 1 ]; then bad "MUTANT cache (never cached): still one read"; else ok "MUTANT cache (never cached): red"; fi; fi
# ceiling: no cap -> the head that can never fit holds the device; nothing is claimed
M=$(ba_mut battery_admit.py 's/^    need = min(need, CEILING)$/    pass/' m-ceiling)
if [ -z "$M" ]; then bad "MUTANT ceiling: sed matched nothing"
else ba_ceiling "$M" "$BA/mg"
     if ba_claimed "$BA/mg" 0-huge || ba_claimed "$BA/mg" 1-short; then bad "MUTANT ceiling (no cap): still claimed"; else ok "MUTANT ceiling (no cap): red"; fi; fi
# helper fails: the exception reaches the interpreter -> exit 1, refused
M=$(ba_mut battery_admit.py 's/^    except Exception as e: .*$/    except KeyboardInterrupt as e:/' m-exc)
if [ -z "$M" ]; then bad "MUTANT helper-fails: sed matched nothing"
else ba_bad "$M" "$BA/mh"
     if ba_claimed "$BA/mh" 0-bad; then bad "MUTANT helper-fails (no handler): still claimed"; else ok "MUTANT helper-fails (no handler): red"; fi; fi
# log once: the key is the raw line -> the hold line's clock logs it every walk
M=$(ba_mut dispatcher.sh 's/^    key=\$(printf .*$/    key="$line"/' m-once)
if [ -z "$M" ]; then bad "MUTANT log-once: sed matched nothing"
else ba_hold3 "$M" "$BA/mj"
     if [ "$(ba_holds "$BA/mj")" -eq 1 ]; then bad "MUTANT log-once (clock in the key): still once"; else ok "MUTANT log-once (clock in the key): red"; fi; fi
# unreadable: admit on an unreadable level -> the head is claimed on a failing link
M=$(ba_mut dispatcher.sh 's/^    \[ -n "\$level" \] || { battery_unreadable "\$id"; return 1; }$/    [ -n "$level" ] || { battery_unreadable "$id"; return 0; }/' m-unread)
if [ -z "$M" ]; then bad "MUTANT unreadable: sed matched nothing"
else ba_setup "$BA/mu" FAIL 0-long:2100; ba_walk "$M" "$BA/mu"
     if ba_queued "$BA/mu" 0-long; then bad "MUTANT unreadable (admits): still queued"; else ok "MUTANT unreadable (admits): red"; fi; fi
# unreadable, one read per walk: the walk's flag ignored -> a dumpsys per request
M=$(ba_mut dispatcher.sh 's/^    \[ -z "\${BATT_WALK_UNREAD:-}" \] || return 1$/    :/' m-unreadwalk)
if [ -z "$M" ]; then bad "MUTANT unreadable-walk: sed matched nothing"
else ba_unread "$M" "$BA/mv"
     if [ "$(grep -c 'dumpsys battery' "$BA/mv/adb.log")" -eq 3 ]; then bad "MUTANT unreadable-walk (read per request): still 3 reads"; else ok "MUTANT unreadable-walk (read per request): red"; fi; fi
# unreadable, once per episode: every walk logs
M=$(ba_mut dispatcher.sh 's/^    if \[ -z "\$BATT_UNREAD_SINCE" \]; then$/    if true; then/' m-unreadonce)
if [ -z "$M" ]; then bad "MUTANT unreadable-once: sed matched nothing"
else ba_unread "$M" "$BA/mw"
     if [ "$(grep -c 'level unreadable on nova' "$BA/mw/logs/dispatcher.log")" -eq 1 ]; then bad "MUTANT unreadable-once (every walk): still once"; else ok "MUTANT unreadable-once (every walk): red"; fi; fi
# nova floor: the table emptied -> the nova is back at 15 and the 2100 s soak is claimed at 50
M=$(ba_mut battery_admit.py 's/^FLOOR_BY_LABEL = {"nova": 30.0}$/FLOOR_BY_LABEL = {}/' m-novafloor)
if [ -z "$M" ]; then bad "MUTANT nova-floor: sed matched nothing"
else ba_novafloor "$M" "$BA/mn"
     if ba_queued "$BA/mn" 0-long; then bad "MUTANT nova-floor (no table): still queued"; else ok "MUTANT nova-floor (no table): red"; fi; fi
# thor floor: every device at 30 -> the thor's floor is not 15
M=$(ba_mut battery_admit.py 's/FLOOR_BY_LABEL.get(label, FLOOR)$/30.0/' m-thorfloor)
if [ -z "$M" ]; then bad "MUTANT thor-floor: sed matched nothing"
elif ba_thorfloor "$M"; then bad "MUTANT thor-floor (all at 30): still 15"
else ok "MUTANT thor-floor (all at 30): red"; fi
