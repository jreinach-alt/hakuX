# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# THE STOP HOOK AND A HELD HANDHELD.
#
# stop-emulator.sh is every session's Stop hook. It force-stops the app and
# sleeps the panel on every attached handheld unless a lease is fresh, and it
# never read $DISPATCH_DIR/hold/<label>. A hold stops the dispatcher claiming,
# so nothing refreshes the per-device lease while a device is held, and every
# held session (a pilot, profile_ab.sh, a title push) was killed by the next
# turn end of any other session: the Nova, 2026-09-26 16:24 PDT, mid-Crimson.
#
# The hook runs from a scratch copy of docs/testing with devices.sh's lease
# path moved under $SH: the real one is /tmp/hakux-device-lease.<label>, which
# a live host touches for a held device and which this test must neither read
# nor write. adb is a shim that logs every call; the verdict is read from that
# log, per serial, never from the hook's exit code (always 0) or its stdout.
#
# SH_HOOK names the hook under test (default: this tree's). Pointing it at
# origin/master's copy is how leg (a) is shown to fail on the pre-change hook.
#
# Each leg names the world in which it fails:
#   (a) the hook ignores the hold      -> the Nova is force-stopped and slept.
#       Its pair, the unheld Thor IS stopped, fails a hook that skips everyone.
#   (b) the hook honours a battery hold -> the Nova is left lit and running.
#   (c) the hold check broke the per-device lease -> the Thor is stopped.
#   (d) the hold check skips an unheld, unleased device -> nothing is stopped.

echo "== the Stop hook leaves a held handheld alone"
SH="$T/stop-hook"; rm -rf "$SH"; mkdir -p "$SH/testing" "$SH/bin"
cp "${SH_HOOK:-$TESTING/stop-emulator.sh}" "$SH/testing/stop-emulator.sh"
sed "s|/tmp/hakux-device-lease\.|$SH/lease.|" "$TESTING/devices.sh" > "$SH/testing/devices.sh"
cat > "$SH/bin/adb" <<'EOF'
#!/usr/bin/env bash
echo "$*" >> "${SH_ADB_LOG:?}"
case "$*" in
    devices) printf 'List of devices attached\r\nbdc158a5\tdevice\r\nee317437\tdevice\r\n' ;;
    *"ps -A -o NAME"*) printf 'NAME\r\nsystem_server\r\ncom.jreinach.hakux.debug\r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
esac
exit 0
EOF
chmod +x "$SH/bin/adb"

sh_run() {   # <leg>: run the hook against $SH/<leg>/dispatch; the adb log is $SH/<leg>.log
    local leg=$1
    mkdir -p "$SH/$leg/dispatch/hold"; : > "$SH/$leg.log"
    ( export PATH="$SH/bin:$PATH" SH_ADB_LOG="$SH/$leg.log" DISPATCH_DIR="$SH/$leg/dispatch" \
             HAKUX_DEVICE_LEASE="$SH/shared-lease-absent"
      bash "$SH/testing/stop-emulator.sh" ) > "$SH/$leg.out" 2>&1
    echo $? > "$SH/$leg.rc"
}
sh_stopped() { grep -qx -- "-s $2 shell am force-stop com.jreinach.hakux.debug" "$SH/$1.log"; }
sh_slept()   { grep -qx -- "-s $2 shell input keyevent KEYCODE_SLEEP" "$SH/$1.log"; }
sh_touched() { grep -q -- "^-s $2 " "$SH/$1.log"; }
sh_leases() { rm -f "$SH"/lease.*; touch -d '10 minutes ago' "$SH/lease.nova" "$SH/lease.thor"; }

# (a) the Nova held for a title push, its lease long stale; the Thor unheld.
sh_leases
mkdir -p "$SH/a/dispatch/hold"
touch "$SH/a/dispatch/hold/nova"
echo "title push by lane.xbox: Crash Bandicoot" > "$SH/a/dispatch/hold/nova.why"
sh_run a
check "(a) the hook exits 0"                                grep -qx 0 "$SH/a.rc"
if ! sh_stopped a ee317437 && ! sh_slept a ee317437; then
    ok "(a) held Nova: no force-stop and no sleep"
else bad "(a) held Nova was stopped or slept: $(grep -- '-s ee317437' "$SH/a.log" | tr '\n' ';')"; fi
if ! sh_touched a ee317437; then ok "(a) held Nova: no adb call spent on it at all"
else bad "(a) adb calls on the held Nova: $(grep -- '-s ee317437' "$SH/a.log" | tr '\n' ';')"; fi
check "(a) unheld Thor IS force-stopped"                    sh_stopped a bdc158a5
check "(a) unheld Thor IS slept"                            sh_slept a bdc158a5

# (b) the Nova held to charge: stopped and slept like any unleased device.
sh_leases
mkdir -p "$SH/b/dispatch/hold"
touch "$SH/b/dispatch/hold/nova"
echo "Battery: 12%, charging to 60% before the next batch" > "$SH/b/dispatch/hold/nova.why"
sh_run b
check "(b) the hook exits 0"                                grep -qx 0 "$SH/b.rc"
check "(b) battery-held Nova IS force-stopped"              sh_stopped b ee317437
check "(b) battery-held Nova IS slept"                      sh_slept b ee317437

# (c) no hold; the Thor's own lease fresh, the Nova's stale.
sh_leases; touch "$SH/lease.thor"
sh_run c
check "(c) the hook exits 0"                                grep -qx 0 "$SH/c.rc"
if ! sh_touched c bdc158a5; then ok "(c) leased Thor: left alone, no adb call"
else bad "(c) adb calls on the leased Thor: $(grep -- '-s bdc158a5' "$SH/c.log" | tr '\n' ';')"; fi
check "(c) unleased Nova IS force-stopped"                  sh_stopped c ee317437

# (d) no hold, no fresh lease anywhere: both stopped and slept.
sh_leases
sh_run d
check "(d) the hook exits 0"                                grep -qx 0 "$SH/d.rc"
for s in bdc158a5 ee317437; do
    check "(d) $s force-stopped"                            sh_stopped d $s
    check "(d) $s slept"                                    sh_slept d $s
done
