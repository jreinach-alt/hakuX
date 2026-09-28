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
# 24.8 (each 0.049 up, then to one decimal).

echo "== battery admission: claim only what the level covers; the head is not starved"
BA="$T/battadmit"; rm -rf "$BA"; mkdir -p "$BA/bin"
cat > "$BA/bin/adb" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "$BA_ADB_LOG"
case "$*" in
    *"dumpsys battery"*) printf 'Current Battery Service state:\n  AC powered: false\n  USB powered: true\n  level: %s\n  scale: 100\n' "$(cat "$BA_LEVEL")" ;;
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
reqs=("$2"/queue/*.req)
serve_queue "${reqs[@]}"
echo "walk=$?"
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
ba_walk() {   # <tree> <dir>: one more walk over what is queued now
    PATH="$BA/bin:$PATH" BA_ADB_LOG="$2/adb.log" BA_LEVEL="$2/level" ADB_QUICK_TIMEOUT=5 ADB_RETRY_SLEEP=0 \
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
    ba_logged "$BA/a" "BATTERY: admit 0-long: level 50 >= need 38.3 (rate 27.0 %/h learned n=4, 1 x (2100s + overhead 340s learned n=5))"
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

# fits: admission reads the floor as 50 -> the 2100 s soak no longer fits at 50
M=$(ba_mut battery_admit.py 's/^FLOOR = float(os.environ.get("BATTERY_FLOOR", "15"))$/FLOOR = 50.0/' m-floor)
if [ -z "$M" ]; then bad "MUTANT fits: sed matched nothing"
else ba_case "$M" "$BA/ma" 50 0-long:2100
     if ba_claimed "$BA/ma" 0-long; then bad "MUTANT fits (floor 50): still claimed"; else ok "MUTANT fits (floor 50): red"; fi; fi
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
