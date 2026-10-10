# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit --
# `fail` is shared and is the run's verdict.
#
# usage/meter.py and usage/mode.sh (#433, owner 2026-10-02 10:10 PDT: 80% of
# the week used drops the harness into Low; back to Normal at the reset).
# NO LIVE TRANSCRIPTS: every ~/.claude/projects file this fragment reads is
# one it wrote itself, under its own $UM/projects (HAKUX_CLAUDE_PROJECTS),
# with its own $UM/work (HAKUX_WORK) so nothing here can read, or leave
# behind, anything in the shared $HAKUX_WORK the later fragments (97, 98, 99)
# share -- the same isolation 88-window-budget.sh and 99-lane-model-file.sh
# use for the same reason.
#
# Depends on no other fragment.

echo "== meter.py: actor classification, the week window, and incremental reads"
UM="$T/usagemode"; rm -rf "$UM"
mkdir -p "$UM/work/briefs" "$UM/work/logs/pricefit" "$UM/projects" "$UM/systemd"
# Save the harness's own values (if any) before this fragment's isolation
# overrides them, so they can be put back exactly -- not just unset. A bare
# `unset` here (the earlier version of this fix) left 97-board-priority.sh
# with no $HAKUX_WORK at all, since selftest.sh only ever sets it once, at
# the top of the whole run, and fragments are sourced into that one shell.
UM_SAVED_WORK_SET=${HAKUX_WORK+1}; UM_SAVED_WORK=${HAKUX_WORK-}
UM_SAVED_PROJECTS_SET=${HAKUX_CLAUDE_PROJECTS+1}; UM_SAVED_PROJECTS=${HAKUX_CLAUDE_PROJECTS-}
UM_SAVED_SYSTEMD_SET=${HAKUX_SYSTEMD_USER_DIR+1}; UM_SAVED_SYSTEMD=${HAKUX_SYSTEMD_USER_DIR-}
export HAKUX_WORK="$UM/work" HAKUX_CLAUDE_PROJECTS="$UM/projects" HAKUX_SYSTEMD_USER_DIR="$UM/systemd"
UM_NOW_ISO='2026-10-02T17:10:00Z'
UM_NOW=$(date -u -d "$UM_NOW_ISO" +%s)
# Exported, not just a shell variable: meter.py's main() reads HAKUX_NOW from
# the environment, and the fixture timestamps below are all offsets from
# this exact instant. Without this, "now" is the real wall clock, which
# merely happens to be close to 2026-10-02 on this host and would make every
# check below flaky by however many seconds the run actually took.
# Unset at the end of this fragment -- every later fragment that does not
# set its own HAKUX_NOW expects the real clock.
export HAKUX_NOW="$UM_NOW"

# One headless-run JSON so fit_prices has ground truth: 1000 input-equivalent
# tokens costing $1.00 -> $0.001 per eq-token for claude-opus-5-5. Every
# fixture assistant message below spends exactly 1000 input_tokens, so every
# one of them costs exactly $1.00 -- chosen so the checks below compare
# against round numbers instead of fighting float formatting.
cat > "$UM/work/logs/pricefit/one.json" <<'EOF'
{"modelUsage": {"claude-opus-5-5": {"inputTokens": 1000, "cacheCreationInputTokens": 0, "cacheReadInputTokens": 0, "outputTokens": 0, "costUSD": 1.0}}}
EOF

python3 - "$UM/projects" "$UM_NOW" <<'PY'
import datetime, json, os, sys
root, now = sys.argv[1], int(sys.argv[2])

def write(dirname, filename, ages, first_user=None):
    d = os.path.join(root, dirname)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, filename), "w") as fh:
        if first_user is not None:
            fh.write(json.dumps({"type": "user",
                                  "message": {"role": "user", "content": first_user}}) + "\n")
        for i, age in enumerate(ages):
            ts = datetime.datetime.fromtimestamp(now - age, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            fh.write(json.dumps({
                "type": "assistant", "timestamp": ts,
                "message": {"id": "%s-%s-%d" % (dirname, filename, i), "model": "claude-opus-5-5",
                            "usage": {"input_tokens": 1000, "cache_creation_input_tokens": 0,
                                      "cache_read_input_tokens": 0, "output_tokens": 0}}}) + "\n")

# lane:fixlane -- one event in each of 1h / 6h / week-but-not-6h / before-the-
# week-start, so the three report windows (1h, 6h, week) are each provable
# against a DIFFERENT subset rather than all moving together.
write("-home-justin-hakux-work-wt-fixlane", "s.jsonl", [600, 10800, 36000, 72000])
write("-home-justin-hakux-work-board-wt", "s.jsonl", [600])
write("-home-justin-hakux-work-wt-cloud-audit1-42", "s.jsonl", [600])
# Same directory, two files: only the FIRST USER MESSAGE tells a hostops
# tick apart from lane.local typing by hand (classify_dir returns
# NEEDS_MESSAGE for the whole directory; resolve_message_actor decides per
# file).
write("-home-justin-hakuX", "hostops.jsonl", [600], first_user="FOCUS -- a hostops tick")
write("-home-justin-hakuX", "interactive.jsonl", [600], first_user="hey can you look at this")
# A project this fleet has nothing to do with: must not appear ANYWHERE below.
write("-home-justin-SuperForge", "s.jsonl", [600])
PY

python3 "$HERE/usage/meter.py" >/dev/null

um_dump() {   # -> $UM/report.txt, one "key=value" per line, from state.json's last_report
    python3 - "$UM/work/usage/state.json" > "$UM/report.txt" <<'PY'
import json, sys
r = json.load(open(sys.argv[1]))["last_report"]
for a, v in sorted(r["spend_by_actor"].items()):
    print("actor_%s=%.2f" % (a.replace(":", "_"), v))
print("n_actors=%d" % len(r["spend_by_actor"]))
print("spend_since_reset=%.2f" % r["spend_since_reset"])
print("rate_1h=%.2f" % r["rate_1h"])
print("rate_6h=%.2f" % r["rate_6h"])
print("estimated_percent=%s" % r["estimated_percent"])
print("capacity=%s" % r["capacity_dollars_per_week"])
print("week_start_epoch=%s" % r["week_start_epoch"])
print("week_end_epoch=%s" % r["week_end_epoch"])
print("n_calibration=%d" % len(r["calibration"]))
PY
}
um_dump
check "lane:fixlane's week total is e1+e2+e3, not e4 (before the week start)" \
    grep -q '^actor_lane_fixlane=3.00$' "$UM/report.txt"
check "board is its own actor, not folded into a lane" grep -q '^actor_board=1.00$' "$UM/report.txt"
check "a cloud-audit worktree is bucketed as cloud, not as a lane named cloud-audit1-42" \
    grep -q '^actor_cloud=1.00$' "$UM/report.txt"
check "a hostops tick (first message 'FOCUS --') is classified as hostops" \
    grep -q '^actor_hostops=1.00$' "$UM/report.txt"
check "a plain first message in the same directory is classified as interactive" \
    grep -q '^actor_interactive=1.00$' "$UM/report.txt"
check "exactly 5 actors: the unrelated SuperForge project contributed none" \
    grep -q '^n_actors=5$' "$UM/report.txt"
check "spend_since_reset is the sum of all 5 actors' week totals (3+1+1+1+1)" \
    grep -q '^spend_since_reset=7.00$' "$UM/report.txt"
check "rate_1h counts only the five events inside the last hour (one dollar each)" \
    grep -q '^rate_1h=5.00$' "$UM/report.txt"
check "rate_6h is a PER-HOUR figure (6 dollars over 6h), not the window's raw total" \
    grep -q '^rate_6h=1.00$' "$UM/report.txt"
check "the two seeded calibration points are there" grep -q '^n_calibration=2$' "$UM/report.txt"
# The 16% seed's own reading instant is UM_NOW itself (2026-10-02T10:10 PDT =
# 17:10Z), so its spend-at-reading equals this run's whole-week total, and
# its capacity (7 / 0.16) is what estimated_percent comes back as: 16.0 again
# -- a seed that round-trips to its own percent is the base case; see the
# calibrate() check below for a value that must NOT be 16.
check "estimated_percent reads back the most recent calibration point (16%)" \
    grep -q '^estimated_percent=16.0$' "$UM/report.txt"

echo "== meter.py: idempotent re-run, then an appended tail is picked up ONCE"
cp "$UM/report.txt" "$UM/report-1.txt"
python3 "$HERE/usage/meter.py" >/dev/null
um_dump
check "a second tick with no new bytes anywhere does not double-count" \
    cmp -s "$UM/report-1.txt" "$UM/report.txt"
python3 - "$UM/projects/-home-justin-hakux-work-wt-fixlane/s.jsonl" "$UM_NOW" <<'PY'
import datetime, json, sys
path, now = sys.argv[1], int(sys.argv[2])
ts = datetime.datetime.fromtimestamp(now - 300, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
with open(path, "a") as fh:
    fh.write(json.dumps({"type": "assistant", "timestamp": ts,
                          "message": {"id": "fixlane-appended", "model": "claude-opus-5-5",
                                      "usage": {"input_tokens": 1000, "cache_creation_input_tokens": 0,
                                                "cache_read_input_tokens": 0, "output_tokens": 0}}}) + "\n")
PY
python3 "$HERE/usage/meter.py" >/dev/null
um_dump
check "an appended event is picked up exactly once, from its own byte offset" \
    grep -q '^actor_lane_fixlane=4.00$' "$UM/report.txt"

echo "== meter.py: calibrate PCT appends a point and it becomes the live one"
python3 "$HERE/usage/meter.py" calibrate 50 >/dev/null
um_dump
check "calibrate adds a third point" grep -q '^n_calibration=3$' "$UM/report.txt"
check "...and it is the one now driving estimated_percent (50, not 16)" \
    grep -q '^estimated_percent=50.0$' "$UM/report.txt"

echo "== meter.py: the projection formula, recomputed independently from the report"
check "projected_percent_at_reset matches estimated% + rate_6h*hours_left/capacity*100" \
    python3 -c "
import json
r = json.load(open('$UM/work/usage/state.json'))['last_report']
hours_left = max(0.0, (r['week_end_epoch'] - $UM_NOW) / 3600.0)
want = r['estimated_percent'] + r['rate_6h'] * hours_left / r['capacity_dollars_per_week'] * 100.0
got = r['projected_percent_at_reset']
# r['rate_6h'] is already rounded to 2dp for display, and hours_left/capacity*100
# here is a ~960x multiplier on it -- a formula bug (wrong rate, missing
# hours_left, inverted capacity) misses by far more than the rounding noise
# that amplification alone can produce, so a loose-looking tolerance still
# catches it.
assert abs(want - got) < 6.0, (want, got)
"

echo "== meter.py: its week anchor agrees with window.sh's, several instants, across a DST change"
. "$HERE/window.sh"
um_agrees() {   # <ISO instant>
    local iso=$1 epoch wsh wpy
    epoch=$(date -u -d "$iso" +%s)
    HAKUX_WORK="$UM/work" HAKUX_NOW="$epoch" window_check
    wsh=$(sed -n 's/^week from \([^ ]*\).*/\1/p' <<< "$WINDOW_FACTS")
    wpy=$(HAKUX_NOW="$epoch" python3 -c "
import os, sys
sys.path.insert(0, '$HERE/usage')
import meter
s, _ = meter.week_bounds(float(os.environ['HAKUX_NOW']))
import datetime
print(datetime.datetime.fromtimestamp(s, datetime.timezone.utc).strftime('%Y-%m-%dT%H:%MZ'))
")
    [ "$wsh" = "$wpy" ]
}
for um_instant in 2026-10-02T17:10:00Z 2026-09-18T03:59:59Z 2026-09-18T04:00:01Z 2026-11-06T05:00:00Z; do
    check "meter.py and window.sh agree on the week start for $um_instant" um_agrees "$um_instant"
done
unset -f um_agrees

echo "== mode.sh: low is one file; it rewrites no dial and no .model, so normal restores nothing"
MM="$T/usagemode-mode"; rm -rf "$MM"; mkdir -p "$MM/work/briefs" "$MM/systemd"
export HAKUX_WORK="$MM/work" HAKUX_SYSTEMD_USER_DIR="$MM/systemd"
printf 'LANE_MAX=10\nMODEL_LANE_ESCALATED=claude-fable-5-1\n' > "$MM/work/limits.env"
echo claude-opus-5-5 > "$MM/work/briefs/alpha.model"
cp "$MM/work/limits.env" "$MM/limits.before"; cp "$MM/work/briefs/alpha.model" "$MM/alpha.before"

bash "$HERE/usage/mode.sh" low > "$MM/low.out" 2>&1
check "low writes the low-active file lane.sh reads" test -s "$MM/work/usage/low-active"
check "low writes no pathfind call cap (dead dial, deleted #433)" \
    bash -c '! grep -q PATHFIND_MODEL_CALLS_MAX "$1"' _ "$MM/work/limits.env"
check "low leaves LANE_MAX alone (lane.sh caps it at read time)" grep -q '^LANE_MAX=10$' "$MM/work/limits.env"
check "low leaves the escalation model alone" \
    grep -q '^MODEL_LANE_ESCALATED=claude-fable-5-1$' "$MM/work/limits.env"
check "low leaves a lane's .model file byte-identical" cmp -s "$MM/alpha.before" "$MM/work/briefs/alpha.model"
check "low writes no snapshot directory" bash -c '! test -e "$1"' _ "$MM/work/usage/saved"
check "low writes a hostops heartbeat drop-in" grep -q 'OnCalendar' "$MM/systemd/hakux-hostops.timer.d/usage-low.conf"
check "the mode file says low, and manual" grep -q '^mode=low$' "$MM/work/usage/mode"
check "...and manual" grep -q '^source=manual$' "$MM/work/usage/mode"
check "every switch is logged" grep -q -- '-> low (manual)' "$MM/work/usage/switches.log"

bash "$HERE/usage/mode.sh" normal > "$MM/normal.out" 2>&1
check "normal leaves limits.env exactly as it was before low" cmp -s "$MM/limits.before" "$MM/work/limits.env"
check "normal leaves alpha's .model exactly as it was" cmp -s "$MM/alpha.before" "$MM/work/briefs/alpha.model"
check "normal removes the hostops drop-in" \
    bash -c '! test -e "$1"' _ "$MM/systemd/hakux-hostops.timer.d/usage-low.conf"
check "normal removes the low-active file" bash -c '! test -e "$1"' _ "$MM/work/usage/low-active"
check "the mode file says normal" grep -q '^mode=normal$' "$MM/work/usage/mode"

echo "== mode.sh: every tick re-evaluates against the meter; no latch, hysteresis, manual lock"
mkdir -p "$MM/work/usage"
um_state() {   # <estimated pct> <projected pct or "">
    python3 - "$MM/work/usage/state.json" "$1" "${2:-}" <<'PY'
import json, sys
path, pct, proj = sys.argv[1], float(sys.argv[2]), sys.argv[3]
json.dump({"calibration": [], "events": [], "offsets": {},
           "last_report": {"week_end_epoch": 1, "estimated_percent": pct,
                            "projected_percent_at_reset": float(proj) if proj else None}},
          open(path, "w"))
PY
}
um_tick() { HAKUX_NOW="$UM_NOW" bash "$HERE/usage/mode.sh" tick > "$MM/$1.out" 2>&1; }
um_mode() { sed -n 's/^mode=//p' "$MM/work/usage/mode"; }
um_lines() { wc -l < "$MM/work/usage/switches.log"; }

bash "$HERE/usage/mode.sh" normal > /dev/null 2>&1    # known starting state, source=manual
um_state 85 90
um_tick t1
check "tick is a no-op while a manual lock is held" grep -qi 'manual override' "$MM/t1.out"
check "...and does not flip the mode" [ "$(um_mode)" = normal ]

bash "$HERE/usage/mode.sh" auto > /dev/null 2>&1
check "auto clears the manual lock and evaluates: 85% used is low" [ "$(um_mode)" = low ]
check "...and source=auto" grep -q '^source=auto$' "$MM/work/usage/mode"
check "...and the switch names the reading that caused it" grep -q -- '-> low (auto): estimated 85' "$MM/work/usage/switches.log"

n=$(um_lines); um_tick t2
check "a tick that changes nothing logs nothing" [ "$(um_lines)" = "$n" ]

um_state 10 80; um_tick t3
check "hysteresis: under 80% used but still 80% projected (>= 75) stays low" [ "$(um_mode)" = low ]

um_state 10 50; um_tick t4
check "no latch: 10% used and 50% projected brings it back to normal mid-week" [ "$(um_mode)" = normal ]
check "...and removes low-active" bash -c '! test -e "$1"' _ "$MM/work/usage/low-active"

um_state 40 80; um_tick t5
check "hysteresis the other way: 80% projected from normal (< 90) stays normal" [ "$(um_mode)" = normal ]

um_state 40 95; um_tick t6
check "projected over: 40% used but 95% projected (>= 90) goes low" [ "$(um_mode)" = low ]

um_state 2 ""; um_tick t7
check "the week rolling over (2% used, no projection yet) is just a low reading: normal" [ "$(um_mode)" = normal ]

# No limits.env override remains for this dial (#433) -- the only way to
# move the entry line now is models.toml itself, via $HAKUX_MODELS_TOML.
cp "$HERE/models.toml" "$MM/models-lowproj60.toml"
sed -i 's/^low_proj = 90.*/low_proj = 60/' "$MM/models-lowproj60.toml"
grep -q '^low_proj = 60$' "$MM/models-lowproj60.toml" || bad "fixture: low_proj edit did not take"
um_state 10 65
export HAKUX_MODELS_TOML="$MM/models-lowproj60.toml"
um_tick t8
unset HAKUX_MODELS_TOML
check "the entry line is a models.toml dial: low_proj=60 makes 65% projected low" [ "$(um_mode)" = low ]

rm -f "$MM/work/usage/low-active"; um_state 10 80; um_tick t9
check "a mode file saying low with low-active missing heals: the file comes back" test -s "$MM/work/usage/low-active"

unset -f um_dump um_state um_tick um_mode um_lines
unset UM MM UM_NOW UM_NOW_ISO far_future um_instant
unset HAKUX_NOW

# Restore exactly what was there before (addendum 2, fold selftest
# 2026-10-10 15:49): re-export the harness's own value if it had one,
# unset only if it did not, so a later fragment sourced into this same
# shell (97, 98, 99) sees the real $HAKUX_WORK, not this one's, and sees it
# as a value, not a missing variable under `set -u`.
if [ -n "$UM_SAVED_WORK_SET" ]; then export HAKUX_WORK="$UM_SAVED_WORK"; else unset HAKUX_WORK; fi
if [ -n "$UM_SAVED_PROJECTS_SET" ]; then export HAKUX_CLAUDE_PROJECTS="$UM_SAVED_PROJECTS"; else unset HAKUX_CLAUDE_PROJECTS; fi
if [ -n "$UM_SAVED_SYSTEMD_SET" ]; then export HAKUX_SYSTEMD_USER_DIR="$UM_SAVED_SYSTEMD"; else unset HAKUX_SYSTEMD_USER_DIR; fi
unset UM_SAVED_WORK_SET UM_SAVED_WORK UM_SAVED_PROJECTS_SET UM_SAVED_PROJECTS UM_SAVED_SYSTEMD_SET UM_SAVED_SYSTEMD
check "HAKUX_WORK is restored to the harness's own value after this fragment" \
    [ "${HAKUX_WORK-}" = "$T/work" ]
