#!/usr/bin/env bash
#
# Measure issue #19 end to end, unattended.
#
#   overnight_19.sh start        run the whole chain
#   overnight_19.sh status       where it is
#   overnight_19.sh pause        park after the current step, free the Nova
#   overnight_19.sh resume
#   overnight_19.sh report       write/refresh the morning summary
#
# #19 says 328 of 864 failing tests render *another test's* image. That one
# signature has two causes needing opposite fixes -- state leaking forward from
# an earlier test (the test is right when run alone) versus a state bit we never
# implement (the test is wrong alone too) -- and nothing in the score sheet
# tells them apart. Running each accused test by itself does.
#
# Three rules this script exists to enforce, because doing it by hand kept
# breaking all three:
#
#   1. ONE BINARY. The "in company" arm and the "alone" arm must come from the
#      same APK or an improvement has two explanations. So the company arm is
#      re-measured with tonight's APK instead of reusing yesterday's numbers,
#      and every row records the APK sha that produced it.
#
#   2. NO JUDGEMENT IN THE LOOP. Every suite is measured, crossmatched and
#      classified by script. A suite that crashes, times out or scores zero is
#      logged and the next one starts. Nothing here decides a suite is
#      uninteresting and moves on to something more interesting.
#
#   3. COMPLETE ANSWERS EARLY. The work runs in groups, and each group is taken
#      all the way to a verdict before the next one starts. A night that ends
#      early therefore loses the tail rather than leaving one giant half-
#      measured arm and no verdicts at all.
#
# It parks itself rather than running into someone's morning: past DEADLINE_H
# hours, or below BATTERY_FLOOR percent, no new step starts. The Nova draws more
# than the cable supplies while emulating, so the floor is not optional.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERIAL="${SERIAL:-ee317437}"
PKG="${PKG:-com.jreinach.hakux.debug}"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"

STATE="${STATE:-$HOME/hakux-work/night19}"
# Named by role, not by build: the baseline is "whichever build this sweep is
# measuring", and pointing a default at a dated scratch APK is how a later run
# silently measures last night's binary.
#
# It must be a real file, not a symlink. adb here is Windows adb.exe reached
# through WSL interop and it cannot stat a Linux symlink: `install` failed with
# "No such file or directory", the run carried on against whatever was already
# installed, and every row recorded the sha of the file the symlink pointed at.
# A wrong number is recoverable; a wrong number wearing the right label is not.
APK="${APK:-$HOME/hakux-work/apk-sweep-baseline.apk}"
BASE_ISO="${BASE_ISO:-$HOME/nxdk_pgraph_tests_xiso.iso}"
GOLDENS="${GOLDENS:-$HOME/goldens/results}"
DEADLINE_H="${DEADLINE_H:-9}"
BATTERY_FLOOR="${BATTERY_FLOOR:-15}"

LOG="$STATE/run.log"
PAUSE="$STATE/PAUSE"
PID="$STATE/pid"
ROWS="$STATE/rows.tsv"
STARTED="$STATE/started_at"

# Every name here was checked against the literals in the XBE before the night
# started, because a name the suite does not recognise runs nothing and the
# result is an empty arm rather than an error. Twenty-three matched exactly;
# `Specular` appears in the disc only as " Specular", with a leading space,
# while the directory it writes is `Specular`. Which one the config key wants is
# not knowable from outside, so both forms are listed -- an unmatched key runs
# nothing, so the wrong one costs nothing. `_Specular` is the leading-space
# form: the underscore-to-space rule below turns it into " Specular".
#
# Groups, cheapest first. Each is one disc, one boot, one image pull: pulling a
# 1.5GB image per *test* was what made the obvious version of this take a day
# and a half. The two giants are alone at the end because Blend_tests is 1,673
# tests by itself, and a group that big going first would bank one answer and
# no others.
GROUP_NAMES=(g0 g1 g2)
GROUP_TIMEOUT=(3900 2400 5400)
GROUP_SUITES=(
    "Stipple_tests Texture_perspective Surface_format Texture_DXT Texture_signed_component_tests Specular _Specular Lighting_spotlight Blend_surface ZMinMaxControl Bump_map Texture_render_target Image_blit Fog_param Fog_gen Line_width Texture_cubemap ZPass_pixel_count Window_clip Attrib_carryover Fog_exceptional_value W_param Texture_shadow_comparator"
    "Depth_buffer"
    "Blend_tests"
)

mkdir -p "$STATE"
a() { timeout "${ADB_TIMEOUT:-120}" adb -s "$SERIAL" "$@"; }
say() { echo "$(date '+%m-%d %H:%M:%S') $*" | tee -a "$LOG" >/dev/null; }
apk_sha() { sha256sum "$APK" 2>/dev/null | cut -c1-12; }
battery() { a shell 'cat /sys/class/power_supply/battery/capacity' 2>/dev/null | tr -d '\r'; }

# The device can leave the USB bus -- it did once while this harness was being
# built. Every step needs it, so wait rather than measure nothing: an absent
# device produces an empty arm that looks exactly like a suite that renders
# nothing, and that is the most expensive kind of wrong result here.
wait_device() {
    local waited=0
    while ! adb devices | tr -d '\r' | grep -q "^$SERIAL[[:space:]]*device$"; do
        if [ "$waited" = 0 ]; then
            say "device $SERIAL is not on the bus; waiting for it"
        fi
        sleep 30; waited=$((waited+30))
        if [ "$waited" -ge "${DEVICE_WAIT:-3600}" ]; then
            say "STOP: device absent for ${waited}s"
            return 1
        fi
    done
    [ "$waited" -gt 0 ] && say "device back after ${waited}s"
    return 0
}

# Checked between steps only: a step already running always finishes, so no row
# is ever half-measured.
may_continue() {
    local now lvl started
    started=$(cat "$STARTED" 2>/dev/null || date +%s)
    now=$(date +%s)
    if [ $(( (now - started) / 3600 )) -ge "$DEADLINE_H" ]; then
        say "STOP: ${DEADLINE_H}h deadline reached"; return 1
    fi
    lvl=$(battery)
    if [ -n "$lvl" ] && [ "$lvl" -le "$BATTERY_FLOOR" ] 2>/dev/null; then
        say "STOP: battery ${lvl}% at or below floor ${BATTERY_FLOOR}%"; return 1
    fi
    while [ -f "$PAUSE" ]; do
        a shell am force-stop "$PKG" >/dev/null 2>&1
        rm -f "$LEASE"; a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
        sleep 5
    done
    wait_device || return 1
    return 0
}

# Every row this sweep writes carries the sha of $APK, so the run is only
# honest if $APK is genuinely what is on the device. An install that fails
# leaves the previous build running and the rows claiming otherwise, which is
# worse than no measurement at all -- so this is checked, not assumed.
install_baseline() {
    local out
    out=$(a install -r "$APK" 2>&1)
    echo "$out" >> "$LOG"
    case "$out" in
        *Success*) say "installed $(apk_sha)"; return 0 ;;
        *) say "INSTALL FAILED: $(echo "$out" | tail -1)"; return 1 ;;
    esac
}

park() {
    a shell am force-stop "$PKG" >/dev/null 2>&1
    a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1
    rm -f "$LEASE"
    say "device parked, panel out"
}

# ---- the company arm for one group: every suite in it, one disc ----------
run_company() {
    local g="$1" suites="$2" tmo="$3"
    local res="$STATE/company/$g" iso="$STATE/iso/$g.iso" args=() s
    [ -f "$res/.done" ] && return 0
    mkdir -p "$STATE/iso" "$res"
    for s in $suites; do args+=(--suite "${s//_/ }"); done
    # The guest's E: drive keeps whatever a previous run left in this
    # directory, and the extractor pulls the directory, not the run. A retry
    # therefore comes back with the old captures mixed in -- the probe asked
    # for one 15-test suite and got 29 files, 14 of them from an earlier
    # probe of two different suites. So every attempt gets its own directory.
    local gdir="$g$(date +%s | tail -c 6)"
    # --shutdown-on-completion is not optional here. Without it the suite
    # *reboots* when it finishes, so the emulator process never exits, the
    # wait loop runs to its full timeout, and the whole group is re-run from
    # the top however many times fit inside it. The probe found this in ten
    # minutes; a group would have lost an hour to it.
    if ! python3 "$HERE/make_test_iso.py" "$BASE_ISO" -o "$iso" "${args[@]}" \
            --progress-log --shutdown-on-completion --output-dir "e:/$gdir" \
            >>"$LOG" 2>&1; then
        say "A $g: disc build FAILED"; return 1
    fi
    say "A $g: $(echo "$suites" | wc -w) suite(s) into e:/$gdir, timeout ${tmo}s, batt $(battery)%"
    SERIAL="$SERIAL" bash "$HERE/run_disc.sh" "$iso" "$gdir" "$res" "$tmo" >>"$LOG" 2>&1
    local n; n=$(ls "$res"/*.png 2>/dev/null | wc -l)
    printf 'company\t%s\t%s\t%s\t%s\n' "$g" "$n" "$(apk_sha)" "$(date -Is)" >> "$ROWS"
    if [ "$n" = 0 ]; then
        say "A $g: NO IMAGES -- suite names or disc wrong, see the progress log"
        return 1
    fi
    say "A $g: $n captures"
    python3 "$HERE/score_sweep.py" --out "$res" --goldens "$GOLDENS" --flat \
        --tsv "$STATE/company/$g.tsv" >>"$LOG" 2>&1
    tail -12 "$STATE/company/$g.tsv" >>"$LOG" 2>&1
    touch "$res/.done"
    rm -f "$iso"
}

# ---- accuse: which of this group's captures render another test's image ---
run_crossmatch() {
    local g="$1" res="$STATE/company/$g"
    local xm="$STATE/crossmatch_$g.txt" q="$STATE/solo_$g.txt"
    [ -d "$res" ] || return 1
    say "B $g: crossmatching $(ls "$res"/*.png 2>/dev/null | wc -l) captures"
    python3 "$HERE/crossmatch.py" "$res" --goldens "$GOLDENS" > "$xm" 2>>"$LOG"
    # crossmatch.py prints padded columns, not tabs; every field is a name with
    # no spaces in it, so whitespace splitting is the right reader. The numeric
    # test on the error column is what rejects the header and the rule line.
    awk 'NF==5 && $4+0==$4 {print $1"::"$2}' "$xm" | sort -u > "$q"
    say "B $g: $(wc -l < "$q") test(s) accused of rendering another test's image"
}

# ---- run each accused test alone, via the hardened solo runner -----------
# sweep_queue.sh already does the parts that are easy to get wrong: unique
# guest dir per test, one image pull per hundred tests, the lease touched every
# second so the Stop hook defers, baseline reinstalled on every resume, and the
# APK sha recorded per row. Driving it is better than writing it again.
run_solo() {
    local g="$1" q="$STATE/solo_$g.txt"
    [ -s "$q" ] || { say "C $g: nothing accused, skipping"; return 0; }
    local sq="$STATE/sq_$g"
    export SWEEP_STATE="$sq" BASE_ISO GOLDENS \
           RESULTS="$STATE/company/$g" BASELINE_APK="$APK" SERIAL PKG
    mkdir -p "$sq"
    bash "$HERE/sweep_queue.sh" start "$q" >>"$LOG" 2>&1
    local left
    while :; do
        sleep 60
        left=$(wc -l < "$sq/queue.txt" 2>/dev/null || echo 0)
        if ! [ -f "$sq/pid" ] || ! kill -0 "$(cat "$sq/pid")" 2>/dev/null; then
            say "C $g: solo runner finished, $left left in queue"; break
        fi
        if ! may_continue; then
            say "C $g: parking the solo runner with $left left"
            bash "$HERE/sweep_queue.sh" pause >>"$LOG" 2>&1
            kill "$(cat "$sq/pid")" 2>/dev/null
            return 1
        fi
    done
    bash "$HERE/sweep_queue.sh" collect >>"$LOG" 2>&1
}

worker() {
    # Wait for the device *before* starting the clock, so a run armed while the
    # Nova is unplugged spends the night measuring rather than counting down.
    say "=== overnight #19 armed, APK $(apk_sha) ==="
    DEVICE_WAIT="${DEVICE_WAIT:-43200}" wait_device || { say "never appeared"; return 1; }
    date +%s > "$STARTED"
    say "=== start, batt $(battery)% ==="
    if ! install_baseline; then
        say "STOP: could not install $APK -- refusing to measure an unknown binary"
        park
        return 1
    fi
    local i g
    for i in "${!GROUP_NAMES[@]}"; do
        g="${GROUP_NAMES[$i]}"
        may_continue || break
        run_company "$g" "${GROUP_SUITES[$i]}" "${GROUP_TIMEOUT[$i]}" || continue
        run_crossmatch "$g" || continue
        may_continue || break
        run_solo "$g" || break
        say "--- $g complete ---"
        python3 "$HERE/night19_report.py" "$STATE" --goldens "$GOLDENS" \
            > "$STATE/report.md" 2>>"$LOG"
    done
    park
    python3 "$HERE/night19_report.py" "$STATE" --goldens "$GOLDENS" \
        > "$STATE/report.md" 2>>"$LOG"
    say "=== finished; report in $STATE/report.md ==="
}

# A dry run of the whole chain on two tiny suites, in its own state directory.
# The chain has five moving parts (disc build, guest output directory, image
# extraction, crossmatch parsing, solo runner) and a mistake in any of them only
# shows up hours in. Fourteen tests is a cheap way to find out first.
if [ "${1:-}" = "probe" ]; then
    shift
    STATE="$STATE-probe"; LOG="$STATE/run.log"; PAUSE="$STATE/PAUSE"
    PID="$STATE/pid"; ROWS="$STATE/rows.tsv"; STARTED="$STATE/started_at"
    GROUP_NAMES=(p0); GROUP_TIMEOUT=(900)
    GROUP_SUITES=("${*:-Stipple_tests Texture_perspective}")
    mkdir -p "$STATE"
    worker
    cat "$STATE/report.md" 2>/dev/null
    exit 0
fi

case "${1:-status}" in
  start)
    [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null && { echo "already running (pid $(cat "$PID"))"; exit 0; }
    rm -f "$PAUSE"
    worker & echo $! > "$PID"
    echo "started (pid $(cat "$PID")); log $LOG"
    ;;
  pause)  touch "$PAUSE"; echo "will park after the current step" ;;
  resume) rm -f "$PAUSE"; echo "resumed" ;;
  status)
    r=no; [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null && r=yes
    echo "worker=$r  groups_measured=$(ls -d "$STATE"/company/*/.done 2>/dev/null | wc -l)/${#GROUP_NAMES[@]}  batt=$(battery)%"
    for f in "$STATE"/solo_*.txt; do
        [ -e "$f" ] || continue
        g=$(basename "$f" .txt); g="${g#solo_}"
        d=$( [ -f "$STATE/sq_$g/done.tsv" ] && wc -l < "$STATE/sq_$g/done.tsv" || echo 0 )
        echo "  $g: accused=$(wc -l < "$f")  solo_run=$d"
    done
    tail -6 "$LOG" 2>/dev/null
    ;;
  report) python3 "$HERE/night19_report.py" "$STATE" --goldens "$GOLDENS" ;;
  *) sed -n '3,9p' "$0" ;;
esac
