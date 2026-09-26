# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $A/$B (the live refs), $GOLDENS, the shims on PATH, ok/bad/check. Not
# executable, no shebang, no exit.
#
# arms.sh backpressure counts only what an arm would wait behind
# (dispatch-hardening defect 12).
#
# The workers serve queue/ in glob order and `z-*` is the idle tier: the
# full-corpus sweep queues one request per suite, ~100 of them, and every arm
# sorts ahead of all of them. arms.sh counted every .req, so a queued sweep held
# `waiting` over ARMS_QUEUE_MAX for hours and no lane's arm was queued at all.
# The host's stopgap was ARMS_QUEUE_MAX=1000, which is no backpressure.
#
# Its own work dir and dispatch dir, so the shared queue 10..50 drive is
# neither read nor left changed. The mutant runs from a copy; the real file is
# never edited.

echo "== arms.sh: a queued z-* sweep does not starve the arms"

IT="$T/idletier"
it_setup() {   # <normal requests to pre-queue>  -> a fresh work + dispatch dir
    rm -rf "$IT"; mkdir -p "$IT/work/arms" "$IT/work/logs/arms" "$IT/d"/{queue,running,results,expect}
    date -u -d '1 minute ago' '+%FT%TZ' > "$IT/work/arms/since"
    python3 - "$IT/d/expect/idletier.json" "$A" "$B" <<'PY'
import json, sys, datetime
p, a, b = sys.argv[1:]
json.dump({"registered_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "who": "lane.idletier", "issue": "1", "prediction": "idle-tier: an arm queues past a sweep",
           "a_ref": a, "b_ref": b,
           "expect": {"Blend_surface/TestA": 0}, "must_not_move": ["Color_mask_blend/*"],
           "must_not_regress": [], "expect_counts": {}}, open(p, "w"), indent=2)
PY
    local i
    for i in $(seq -w 1 100); do echo '{}' > "$IT/d/queue/z-v0.4.0-j1-$i-Suite_$i.req"; done
    for i in $(seq 1 "$1"); do echo '{}' > "$IT/d/queue/179036000$i-lane-other.req"; done
}
it_tick() {   # <arms.sh>  -> the tick log
    ( export HAKUX_WORK="$IT/work" DISPATCH_DIR="$IT/d" ARMS_QUEUE_MAX=4
      bash "$1" ) >/dev/null 2>&1
    cat "$IT/work/logs/arms/tick.log" 2>/dev/null
}
it_new() { ls "$IT/d/queue/"*.req 2>/dev/null | grep -c 'arms-idletier-'; }

# 100 idle-tier + 1 normal: one ahead of an arm, under the cap of 4.
it_setup 1; log=$(it_tick "$HERE/arms.sh")
check "100 z-* + 1 normal: the arms job queues the pair" [ "$(it_new)" -eq 2 ]
check "  and records it" [ "$(ls "$IT/work/arms/pairs/"*.json 2>/dev/null | wc -l)" -eq 1 ]
check "  and does not report the sweep as backpressure" bash -c '! grep -q "queue has" <<< "$1"' -- "$log"

# The cap still bites on real work: a fix that dropped backpressure entirely
# (the host's ARMS_QUEUE_MAX=1000 stopgap) must fail here.
it_setup 4; log=$(it_tick "$HERE/arms.sh")
check "100 z-* + 4 normal: the cap of 4 still refuses" [ "$(it_new)" -eq 0 ]
check "  and the line names both counts" \
    grep -q 'queue has 4 waiting ahead of the idle tier, 100 idle-tier z-\* behind it' <<< "$log"

# The mutant: count everything, which is the old line.
md="$IT-mut"; rm -rf "$md"; mkdir -p "$md"
cp "$HERE/gh-label.sh" "$HERE/localtime.sh" "$md/"
python3 - "$HERE/arms.sh" "$md/arms.sh" <<'PY'
import sys
src, dst = sys.argv[1:]
s = open(src).read()
old = """waiting=$(ls "$D"/queue/*.req 2>/dev/null | grep -vc '/z-[^/]*$')"""
assert s.count(old) == 1, "mutant anchor matches %d times" % s.count(old)
open(dst, "w").write(s.replace(old, """waiting=$(ls "$D"/queue/*.req 2>/dev/null | wc -l)"""))
PY
if [ -f "$md/arms.sh" ]; then
    it_setup 1; log=$(it_tick "$md/arms.sh")
    if [ "$(it_new)" -eq 0 ] && grep -q 'queue has 101 waiting' <<< "$log"; then
        ok "mutant 'count every .req' refuses the pair behind the sweep (red, as it must be)"
    else
        bad "mutant 'count every .req' still queued the pair: the fragment cannot see it"
    fi
else
    bad "mutant anchor no longer matches arms.sh"
fi
rm -rf "$IT" "$md"
