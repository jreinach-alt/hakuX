#!/bin/sh
# hakux-device.sh - the one entry point for talking to a connected device.
#
# The device loop was scattered: the app's own rotating logs, a PowerShell
# diagnostic puller, and whatever each session reinvented. One of those was
# written, refined over four commits and then deleted as redundant
# (f26a485..b751c7e), which is what happens to tooling nothing documents.
#
# Nothing here is fork-specific beyond the package, which is detected rather
# than hardcoded - debug-tools/pull-diag.ps1 hardcoded com.rfandango.haku_x,
# the upstream source namespace, while this fork installs as
# com.jreinach.hakux, so it found nothing on a device running this build.
#
# Requires: adb on PATH, USB debugging on, a debuggable build for anything
# using run-as.
#
# Usage:
#   tools/hakux-device.sh status                  what is connected and installed
#   tools/hakux-device.sh logs [-o DIR]           pull the app's rotating logs
#   tools/hakux-device.sh diag [-o DIR]           pull diag_session_* captures
#   tools/hakux-device.sh shot [-o FILE]          screenshot the current frame
#   tools/hakux-device.sh crash                   recent hakuX-crash logcat
#   tools/hakux-device.sh all  [-o DIR]           status + logs + diag + shot
#
#   -s SERIAL   target a specific device (as adb -s)
#   -p PKG      override package detection

set -eu

SERIAL=""
PKG=""
OUT=""
CMD="${1:-status}"
[ $# -gt 0 ] && shift

while [ $# -gt 0 ]; do
    case "$1" in
        -s) SERIAL="$2"; shift 2 ;;
        -p) PKG="$2"; shift 2 ;;
        -o) OUT="$2"; shift 2 ;;
        *) echo "unknown option: $1" >&2; exit 2 ;;
    esac
done

adb_() {
    if [ -n "$SERIAL" ]; then adb -s "$SERIAL" "$@"; else adb "$@"; fi
}

# adb.exe under WSL emits CRLF; unstripped it corrupts every path built from
# its output. This bit an earlier script badly enough to warrant a commit
# of its own (f403f78).
adbs() { adb_ shell "$@" 2>/dev/null | tr -d '\r'; }

need_device() {
    if ! command -v adb >/dev/null 2>&1; then
        echo "adb not on PATH" >&2; exit 1
    fi
    count=$(adb_ devices | tr -d '\r' | awk 'NR>1 && $2=="device"' | wc -l)
    if [ "$count" -eq 0 ]; then
        echo "no device in 'adb devices' state 'device'." >&2
        echo "check the cable, USB debugging, and the authorisation prompt." >&2
        exit 1
    fi
    if [ "$count" -gt 1 ] && [ -z "$SERIAL" ]; then
        echo "several devices connected; pass -s SERIAL:" >&2
        adb_ devices | tr -d '\r' | awk 'NR>1 && $2=="device" {print "  " $1}' >&2
        exit 1
    fi
}

detect_pkg() {
    [ -n "$PKG" ] && return 0
    # This fork first, then anything hakux-shaped, so an official build or a
    # renamed one still resolves instead of silently matching nothing.
    for cand in com.jreinach.hakux com.jreinach.hakux.debug; do
        if adbs pm path "$cand" | grep -q package:; then PKG="$cand"; return 0; fi
    done
    PKG=$(adbs pm list packages | sed 's/^package://' \
          | grep -iE 'haku|xemu' | head -1 || true)
    if [ -z "$PKG" ]; then
        echo "no hakuX-like package installed. Pass -p PKG, or check:" >&2
        echo "  adb shell pm list packages | grep -i haku" >&2
        exit 1
    fi
}

runas_ok() {
    adbs run-as "$PKG" true >/dev/null 2>&1
}

# Pull one run-as-protected file by staging it somewhere adb pull can reach.
pull_protected() {
    remote="$1"; local="$2"
    tmp="/data/local/tmp/hakux_stage_$(basename "$remote")"
    adbs run-as "$PKG" cat "$remote" > /dev/null 2>&1 || return 1
    adbs "run-as $PKG cat '$remote' > '$tmp'" || return 1
    adb_ pull "$tmp" "$local" >/dev/null 2>&1 || { adbs rm -f "$tmp"; return 1; }
    adbs rm -f "$tmp"
    return 0
}

cmd_status() {
    need_device; detect_pkg
    echo "device   $(adbs getprop ro.product.model) ($(adbs getprop ro.product.device))"
    echo "android  $(adbs getprop ro.build.version.release)  sdk $(adbs getprop ro.build.version.sdk)"
    echo "abi      $(adbs getprop ro.product.cpu.abi)"
    echo "package  $PKG"
    ver=$(adbs dumpsys package "$PKG" | grep -m1 versionName | sed 's/.*versionName=//' || true)
    echo "version  ${ver:-unknown}"
    if runas_ok; then
        echo "run-as   available (debuggable build)"
        n=$(adbs run-as "$PKG" find files -maxdepth 1 -name 'diag_session_*' -type d 2>/dev/null | wc -l)
        echo "diag     $n session(s) on device"
    else
        echo "run-as   UNAVAILABLE - release build, so logs and diag cannot be pulled"
    fi
    if adbs pidof "$PKG" >/dev/null 2>&1; then echo "running  yes"; else echo "running  no"; fi
}

cmd_logs() {
    need_device; detect_pkg
    dir="${OUT:-hakux-logs}"; mkdir -p "$dir"
    runas_ok || { echo "run-as unavailable; install a debuggable build" >&2; exit 1; }
    found=0
    for f in $(adbs run-as "$PKG" find files -maxdepth 2 -name '*.log*' 2>/dev/null); do
        base=$(basename "$f")
        if pull_protected "$f" "$dir/$base"; then
            echo "  $dir/$base"; found=$((found+1))
        fi
    done
    [ "$found" -eq 0 ] && echo "no app logs found under files/" >&2
    echo "$found file(s)"
}

cmd_diag() {
    need_device; detect_pkg
    dir="${OUT:-hakux-diag}"; mkdir -p "$dir"
    runas_ok || { echo "run-as unavailable; install a debuggable build" >&2; exit 1; }
    sessions=$(adbs run-as "$PKG" find files -maxdepth 1 -name 'diag_session_*' -type d 2>/dev/null)
    if [ -z "$sessions" ]; then
        echo "no diag sessions. Trigger one in-app: Debug > Diag: Capture N Frames." >&2
        echo "Multi-frame captures are known to hang the emulator - see KNOWN_ISSUES.md." >&2
        exit 0
    fi
    for s in $sessions; do
        name=$(basename "$s"); mkdir -p "$dir/$name"
        echo "$name"
        for f in $(adbs run-as "$PKG" ls "$s" 2>/dev/null); do
            pull_protected "$s/$f" "$dir/$name/$f" && echo "  $f"
        done
    done
    echo "-> $dir  (view with debug-tools/diag-viewer.html)"
}

cmd_shot() {
    need_device
    out="${OUT:-hakux-$(date +%Y%m%d-%H%M%S).png}"
    adb_ exec-out screencap -p > "$out"
    if [ ! -s "$out" ]; then echo "screencap produced nothing" >&2; rm -f "$out"; exit 1; fi
    echo "$out"
}

cmd_crash() {
    need_device
    # The app tags kernel-crash dumps hakuX-crash; see KNOWN_ISSUES.md.
    adb_ logcat -d -v threadtime 2>/dev/null | tr -d '\r' | grep -i 'hakuX-crash' || {
        echo "no hakuX-crash entries in the current logcat buffer"; }
}

case "$CMD" in
    status) cmd_status ;;
    logs)   cmd_logs ;;
    diag)   cmd_diag ;;
    shot)   cmd_shot ;;
    crash)  cmd_crash ;;
    all)    cmd_status; echo; cmd_logs; echo; cmd_diag; echo; cmd_shot ;;
    *) sed -n '2,32p' "$0"; exit 2 ;;
esac
