#!/usr/bin/env bash
#
# Run a long queue of single-test pgraph discs that yields the device on demand.
#
#   sweep_queue.sh start <queue.txt>   begin (or continue) working the queue
#   sweep_queue.sh pause               stop after the current test, free the Nova
#   sweep_queue.sh resume              carry on
#   sweep_queue.sh status              progress, and whether the device is free
#   sweep_queue.sh collect             pull the image and extract results so far
#
# There is one device, and a full re-baseline is hours of it. Without a way to
# preempt, any fix that needs the Nova waits for the whole sweep; with a naive
# preempt, an experimental APK installed mid-sweep silently produces results
# from a different binary than the ones before it.
#
# So: `pause` blocks until the runner has genuinely parked, and every `resume`
# reinstalls the baseline APK before continuing. Which build produced each
# result is recorded per row, so a mix-up is visible after the fact rather than
# inferred.
#
# Discs are built just-in-time — 1,591 tests would otherwise be ~9GB of ISOs.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERIAL="${SERIAL:-$(adb devices | tr -d '\r' | awk 'NR>1 && $2=="device"{print $1; exit}')}"
PKG="${PKG:-com.jreinach.hakux.debug}"
ACT="$PKG/com.rfandango.haku_x.LauncherActivity"
HDD="/sdcard/Android/data/$PKG/files/x1box/hdd.img"
DEVISO="/storage/E6C6-D7AA/Games/XBox/sweep.iso"
LEASE="${HAKUX_DEVICE_LEASE:-/tmp/hakux-device-lease}"

STATE="${SWEEP_STATE:?set SWEEP_STATE to a working directory}"
BASE_ISO="${BASE_ISO:?set BASE_ISO to the stock nxdk_pgraph_tests xiso}"
GOLDENS="${GOLDENS:?set GOLDENS to goldens/results}"
RESULTS="${RESULTS:?set RESULTS to the sweep results dir}"
BASELINE_APK="${BASELINE_APK:?set BASELINE_APK to the APK the sweep measures}"

mkdir -p "$STATE"
QUEUE="$STATE/queue.txt"; DONE="$STATE/done.tsv"; LOG="$STATE/run.log"
PAUSE="$STATE/PAUSE"; IDLE="$STATE/IDLE"; PID="$STATE/pid"

a() { adb -s "$SERIAL" "$@"; }
now() { date +%H:%M:%S; }

apk_sha() { sha256sum "$BASELINE_APK" 2>/dev/null | cut -c1-12; }

install_baseline() {
    a install -r "$BASELINE_APK" >/dev/null 2>&1
    echo "$(now) installed baseline $(apk_sha)" >> "$LOG"
}

run_one() {  # $1 = Suite::Test ; echoes guest_dir on success
    local spec="$1" plan
    plan=$(python3 "$HERE/make_isolation_discs.py" x --results "$RESULTS" \
             --goldens "$GOLDENS" --base "$BASE_ISO" --out-dir "$STATE/disc" \
             --build-one "$spec" 2>>"$LOG") || return 1
    local gdir iso
    gdir=$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['guest_dir'])" "$plan")
    iso=$(python3  -c "import json,sys;print(json.loads(sys.argv[1])['iso'])"  "$plan")

    a push "$iso" "$DEVISO" >/dev/null 2>&1 || return 1
    a shell am force-stop "$PKG" >/dev/null 2>&1
    a shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1
    a shell "am start -a android.intent.action.VIEW -n $ACT --es rom_path '$DEVISO'" \
        >/dev/null 2>&1
    local s
    for s in $(seq 1 25); do
        sleep 1
        touch "$LEASE"          # hold the device so the Stop hook defers
        a shell 'ps -A -o NAME' | tr -d '\r' | grep -qx "$PKG:xemu" || break
    done
    a shell am force-stop "$PKG" >/dev/null 2>&1
    echo "$gdir"
}

# ES-DE (org.es_de.frontend) is this device's home app and its window carries
# FLAG_KEEP_SCREEN_ON, so the moment the emulator leaves the foreground the
# display is pinned on and the screen-off timeout never fires. Measured on the
# Nova: asleep and idle draws +122uA, the same device parked on ES-DE with the
# screen lit draws -107mA. Anywhere this script hands the device back, put the
# panel out. KEYCODE_SLEEP overrides the flag; the timeout cannot.
sleep_panel() { a shell input keyevent KEYCODE_SLEEP >/dev/null 2>&1; }

collect() {
    local img="$STATE/hdd.img"
    a pull "$HDD" "$img" >/dev/null 2>&1 || return 1
    local n=0
    while IFS=$'\t' read -r spec gdir _sha _ts; do
        [ -n "${gdir:-}" ] || continue
        [ -d "$STATE/out/$gdir" ] && continue
        python3 "$HERE/extract_results.py" "$img" -o "$STATE/out/$gdir" -d "$gdir" \
            >/dev/null 2>&1 && n=$((n+1))
    done < "$DONE"
    echo "collected $n new result dir(s) into $STATE/out"
}

worker() {
    echo "$(now) worker start, $(wc -l < "$QUEUE") queued" >> "$LOG"
    install_baseline
    local paused=0 count=0
    while [ -s "$QUEUE" ]; do
        if [ -f "$PAUSE" ]; then
            if [ "$paused" = 0 ]; then
                a shell am force-stop "$PKG" >/dev/null 2>&1
                rm -f "$LEASE"          # let the Stop hook protect the device again
                collect >> "$LOG" 2>&1
                sleep_panel
                touch "$IDLE"
                echo "$(now) paused, device free" >> "$LOG"
                paused=1
            fi
            sleep 3
            continue
        fi
        if [ "$paused" = 1 ]; then
            rm -f "$IDLE"
            echo "$(now) resuming" >> "$LOG"
            install_baseline            # whatever was installed meanwhile is gone
            paused=0
        fi

        local spec gdir
        spec=$(head -1 "$QUEUE")
        if gdir=$(run_one "$spec"); then
            printf '%s\t%s\t%s\t%s\n' "$spec" "$gdir" "$(apk_sha)" "$(date -Is)" >> "$DONE"
            sed -i '1d' "$QUEUE"
        else
            printf '%s\t\tFAILED\t%s\n' "$spec" "$(date -Is)" >> "$DONE"
            sed -i '1d' "$QUEUE"
            echo "$(now) FAILED $spec" >> "$LOG"
        fi
        count=$((count+1))
        [ $((count % 100)) = 0 ] && collect >> "$LOG" 2>&1
    done
    collect >> "$LOG" 2>&1
    rm -f "$LEASE"
    sleep_panel
    echo "$(now) QUEUE EMPTY" >> "$LOG"
}

case "${1:-status}" in
  start)
    [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null && { echo "already running (pid $(cat "$PID"))"; exit 0; }
    [ -n "${2:-}" ] && cp "$2" "$QUEUE"
    [ -f "$QUEUE" ] || { echo "no queue; pass one: sweep_queue.sh start queue.txt"; exit 1; }
    touch "$DONE"; rm -f "$PAUSE" "$IDLE"
    worker & echo $! > "$PID"
    echo "started (pid $(cat "$PID")), $(wc -l < "$QUEUE") queued"
    ;;
  pause)
    touch "$PAUSE"
    for _ in $(seq 1 40); do [ -f "$IDLE" ] && break; sleep 2; done
    if [ -f "$IDLE" ]; then
        a shell am force-stop "$PKG" >/dev/null 2>&1
        sleep_panel
        echo "paused — the Nova is yours. $(wc -l < "$QUEUE") test(s) still queued."
    else
        echo "WARNING: runner did not confirm idle; check $LOG before using the device."
        exit 1
    fi
    ;;
  resume)  rm -f "$PAUSE"; echo "resumed; baseline APK will be reinstalled first" ;;
  status)
    d=$( [ -f "$DONE" ] && wc -l < "$DONE" || echo 0 )
    q=$( [ -f "$QUEUE" ] && wc -l < "$QUEUE" || echo 0 )
    running=no; [ -f "$PID" ] && kill -0 "$(cat "$PID")" 2>/dev/null && running=yes
    state=running; [ -f "$PAUSE" ] && state=paused
    [ -f "$IDLE" ] && state="paused (device free)"
    echo "worker=$running  state=$state  done=$d  remaining=$q"
    [ "$q" -gt 0 ] && echo "eta ~$(( q * 13 / 60 )) min at 13s/test"
    ;;
  collect) collect ;;
  *) sed -n '3,12p' "$0" ;;
esac
