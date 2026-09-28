# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit -- `fail`
# is shared and is the run's verdict.
#
# dispatcher serve: a handheld that attaches AFTER serve started gets a worker.
#
# WHY. serve listed `adb devices` once and supervised only the serials it saw
# then. 2026-09-26: the update window restarted it at 20:12 PDT with the Thor
# off adb (charging); the owner plugged it back at 20:35 and it was never
# served -- one worker (ee317437), no dispatch/lanes/thor, devwatch "thor
# no-worker" -- until a drain-restart that held both devices. With NOTHING
# attached, serve exited 2 instead.
#
# Real dispatcher.sh serve, in its own DISPATCH_DIR, with a scripted adb and
# a stub worker: DISPATCH_SRC points at a directory whose only file is a
# dispatcher.sh that records "<serial> <pid>" and sleeps, so the snapshot the
# supervisor execs is the stub and no device is ever touched.

echo "== dispatch late device: serve starts a worker for a handheld that attaches later"
LD="$T/late-device"; rm -rf "$LD"; mkdir -p "$LD/bin" "$LD/src"
cat > "$LD/bin/adb" <<'EOF'
#!/usr/bin/env bash
# Answers `adb devices` from $LATE_ADB. A first line of FAIL prints the rest
# and exits 1: the interop transient, whose output must not be believed.
[ "$1" = devices ] || exit 0
if [ "$(head -1 "$LATE_ADB")" = FAIL ]; then
    printf 'List of devices attached\n'; tail -n +2 "$LATE_ADB"; exit 1
fi
printf 'List of devices attached\n'; cat "$LATE_ADB"
EOF
cat > "$LD/src/dispatcher.sh" <<'EOF'
#!/usr/bin/env bash
echo "$2 $$" >> "$LATE_WORKERS"
exec sleep 300
EOF
chmod +x "$LD/bin/adb" "$LD/src/dispatcher.sh"

late_serve() {   # <dir> -> starts serve in the background, echoes its pid
    local d="$1"; mkdir -p "$d"; : > "$d/workers"
    ( export DISPATCH_DIR="$d/dispatch" DISPATCH_SRC="$LD/src" LATE_ADB="$d/adb" \
             LATE_WORKERS="$d/workers" PATH="$LD/bin:$PATH" \
             DISPATCH_SUPERVISE_SLEEP=1 DISPATCH_RESCAN_SECS=0
      unset SERIAL
      exec bash "$TESTING/dispatcher.sh" serve ) > "$d/serve.out" 2>&1 &
    echo $!
}
late_wait() {    # <file> <fixed string> [seconds] -- true once it appears
    local n=0
    while [ "$n" -lt "${3:-15}" ]; do
        grep -qF -- "$2" "$1" 2>/dev/null && return 0
        sleep 1; n=$((n+1))
    done
    return 1
}
late_stop() {    # <pid> <dir>
    kill "$1" 2>/dev/null; wait "$1" 2>/dev/null
    local w; for w in $(awk '{print $2}' "$2/workers" 2>/dev/null); do kill "$w" 2>/dev/null; done
}
late_count() { grep -cF -- "$2" "$1" 2>/dev/null || true; }

# ---- A: one handheld at start, the second attaches later
A="$LD/a"; mkdir -p "$A"
printf 'ee317437\tdevice\n' > "$A/adb"
pid=$(late_serve "$A")
if late_wait "$A/workers" "ee317437 "; then ok "serve starts a worker for the handheld attached at start"
else bad "serve starts a worker for the handheld attached at start -- $(tail -3 "$A/serve.out")"; fi

# The interop transient: a listing that FAILS is not believed, even if it
# names a device.
printf 'FAIL\nee317437\tdevice\nbdc158a5\tdevice\n' > "$A/adb"
sleep 3
check "a failed adb listing starts nothing" test "$(late_count "$A/workers" "bdc158a5 ")" -eq 0

# The Thor comes back from charging, and an unknown serial is plugged in too.
printf 'ee317437\tdevice\nbdc158a5\tdevice\n0000dead\tdevice\nffffbeef\tunauthorized\n' > "$A/adb"
if late_wait "$A/serve.out" "starting worker for bdc158a5 (attached late)"; then
    ok "a handheld attached after serve started gets a worker (attached late)"
else
    bad "a handheld attached after serve started gets a worker -- serve.out:"; sed 's/^/       /' "$A/serve.out" | tail -5
fi
check "the late handheld's worker actually ran" late_wait "$A/workers" "bdc158a5 " 5
sleep 3   # several more rescans with both attached
check "the handheld served from the start is never started twice" \
      test "$(late_count "$A/workers" "ee317437 ")" -eq 1
check "the late handheld is started once, not once per rescan" \
      test "$(late_count "$A/workers" "bdc158a5 ")" -eq 1
check "an unknown serial is logged once, not once per rescan" \
      test "$(late_count "$A/serve.out" "skipping unknown device 0000dead")" -eq 1
check "an unknown serial gets no worker" test "$(late_count "$A/workers" "0000dead")" -eq 0
check "an unauthorized device gets no worker" test "$(late_count "$A/workers" "ffffbeef")" -eq 0
late_stop "$pid" "$A"

# ---- B: nothing attached at start -- no exit 2, and the first to attach is served
B="$LD/b"; mkdir -p "$B"
: > "$B/adb"
pid=$(late_serve "$B")
sleep 3
if kill -0 "$pid" 2>/dev/null; then ok "serve keeps supervising with no device attached"
else bad "serve keeps supervising with no device attached -- it exited: $(tail -2 "$B/serve.out")"; fi
check "serve logs that it is supervising none" late_wait "$B/serve.out" "no known device attached; supervising none" 2
printf 'bdc158a5\tdevice\n' > "$B/adb"
if late_wait "$B/serve.out" "starting worker for bdc158a5 (attached late)"; then
    ok "the first handheld to attach to an empty serve gets a worker"
else
    bad "the first handheld to attach to an empty serve gets a worker -- $(tail -2 "$B/serve.out")"
fi
late_stop "$pid" "$B"
