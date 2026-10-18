# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# jobs/hold.sh (#433, 10-18): an owner-play hold starts a host logcat capture.
#
# THE INCIDENT, 2026-10-18. An owner playthrough's telemetry lives only in a
# host `adb logcat` capture started before the title launches -- the device's
# own ring buffer turns over in ~2-3 minutes and the release app writes no
# readable telemetry file. On 10-17 a Halo run survived by luck (a capture a
# lane run had left running). On 10-18 the owner's first Fable launch did
# not: the hold was taken at 07:09 and nothing was capturing.
#
# THE GLOBAL SHIMS ARE INERT FOR THIS. selftest.sh's own $T/bin/systemd-run
# only logs its argv and never runs anything; $T/bin/systemctl answers
# "active" to `is-active` for ANY unit name, started or not; $T/bin/adb
# ignores every argument. None of that can exercise hold.sh's own capture
# start, so this fragment installs its own LOCAL adb and systemd-run on a
# PATH prepended ahead of $T/bin -- the same local-shim-ahead-of-the-global
# shape 79-stop-hook-hold.sh already uses for its own adb. The local
# systemd-run actually execs the given `bash -c <script>`, detached, so the
# capture's restart loop is a real (if fake-logcat) running process the rest
# of this fragment can kill -0 / /proc check, same as production.
#
# OC_HOLD_SH points the legs at another hold.sh (its own variable, not
# SELFTEST_HOLD_SH, so a run pointing this fragment and 99-hold-take.sh at
# two different mutants cannot collide).
#
# Each leg names the world in which it fails:
#   (a) take for an owner-play tag does not start a capture, or starts one
#       without saying so (no "capture: " line, on either stream).
#   (b) a second take (refused -- the label is already held) starts a
#       second capture, or loses the first.
#   (c) systemd-run refuses the unit: take still leaves the hold.
#   (d) release by the wrong tag stops the capture anyway.
#   (e) release by the right tag leaves the capture running, or does not
#       report its file and size.
#   (f) who does not say NO CAPTURE RUNNING once the capture process is gone.
#   (g) wait-idle does not report the capture on an idle hold, or does not
#       notice when it died.
#
# A non-owner-play tag is unaffected by any of this: 99-hold-take.sh's own
# legs (none of its tags start `owner-play`) are the regression check for
# that, unedited.

echo "== hold.sh: an owner-play hold starts a host logcat capture (#433)"

OC_SH="${OC_HOLD_SH:-$HERE/hold.sh}"
OC="$T/ownerplay"; rm -rf "$OC"; mkdir -p "$OC/dispatch/hold" "$OC/bin"
OC_D="$OC/dispatch"

cat > "$OC/bin/adb" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    devices) printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n'; exit 0 ;;
    *logcat*) printf '=== fake logcat: %s ===\n' "$*"; exec sleep 100000 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$OC/bin/adb"

# A real systemd-run: it detaches the given command (setsid, disowned) so the
# capture loop outlives this shim's own process, same as production outlives
# the shell that ran `take`. OC_SYSTEMD_RUN_FAIL=1 (exported by the caller)
# simulates "systemd refused the unit" (leg c) without touching anything else.
cat > "$OC/bin/systemd-run" <<'EOF'
#!/usr/bin/env bash
if [ "${OC_SYSTEMD_RUN_FAIL:-0}" = 1 ]; then
    echo "systemd-run: refused (test)" >&2
    exit 1
fi
envs=(); unit=""
while [ $# -gt 0 ]; do
    case "$1" in
        --setenv=*) envs+=("${1#--setenv=}"); shift ;;
        --unit) unit="$2"; shift 2 ;;
        bash) shift; break ;;
        *) shift ;;
    esac
done
script="$2"
setsid env "${envs[@]}" bash -c "$script" </dev/null >>"${OC_SYSTEMD_RUN_LOG:-/dev/null}" 2>&1 &
disown
echo "Running as unit: $unit"
exit 0
EOF
chmod +x "$OC/bin/systemd-run"

oc() { PATH="$OC/bin:$PATH" OC_SYSTEMD_RUN_LOG="$OC/systemd-run.log" DISPATCH_DIR="$OC_D" \
       HOLD_WAIT_INTERVAL=1 HOLD_IDLE_INTERVAL=1 bash "$OC_SH" "$@"; }
oc_rc() { local want=$1; shift; oc "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }
oc_out() { local want=$1 pat=$2; shift 2; oc "$@" >"$OC/out" 2>"$OC/err"; [ $? -eq "$want" ] && grep -q -- "$pat" "$OC/out"; }
oc_pid() { cat "$OC_D/hold/$1.capture.pid" 2>/dev/null; }
oc_alive() { local pid; pid=$(oc_pid "$1"); [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }
oc_dead()  { ! oc_alive "$1"; }
oc_wait_pidfile() {   # <label> <timeout_s>: block until the pidfile shows up
    local label=$1 n=$(( ${2:-5} * 10 )) i=0
    while [ ! -s "$OC_D/hold/$label.capture.pid" ] && [ "$i" -lt "$n" ]; do sleep 0.1; i=$((i + 1)); done
}

check "hold.sh parses (bash -n)" bash -n "$HERE/hold.sh"

# (a) take for an owner-play tag starts the capture and says so on its own stdout
check "(a) take for an owner-play tag exits 0 and names the capture on stdout" \
    oc_out 0 '^capture: ' take nova owner-play-1 owner 10-18 playthrough
oc_wait_pidfile nova
check "(a) a capture pidfile exists and names a live process" oc_alive nova
check "(a) the capture's log path was recorded" [ -s "$OC_D/hold/nova.capture" ]
check "(a) who also reports the capture while it is held" oc_out 0 '^capture: ' who nova
OC_LOG1=$(cat "$OC_D/hold/nova.capture")
check "(a) the capture used the dispatcher's own LOGCAT_SPEC (not empty, not a copy)" \
    grep -q 'hakuX-crash:V' "$OC_LOG1"

# (b) a second take (refused -- the label is already held) leaves one capture
OC_PID_B=$(oc_pid nova)
check "(b) a second take by a different tag is refused" oc_rc 3 take nova owner-play-2 someone else
check "(b) the first capture's pid is unchanged (no second one started)" [ "$(oc_pid nova)" = "$OC_PID_B" ]
check "(b) the first capture is still alive" oc_alive nova
oc release nova owner-play-1 >/dev/null 2>&1

# (c) systemd-run refuses the unit: take leaves no hold
export OC_SYSTEMD_RUN_FAIL=1
check "(c) take for an owner-play tag exits 6 when the capture cannot start" \
    oc_rc 6 take nova owner-play-3 capture should fail
unset OC_SYSTEMD_RUN_FAIL
check "(c) the hold is not left behind after a failed capture start" [ ! -e "$OC_D/hold/nova" ]
check "(c) no .why is left behind either" [ ! -e "$OC_D/hold/nova.why" ]

# (d) release by the wrong tag leaves the capture running
check "(d) take for an owner-play tag exits 0 (setup)" oc_rc 0 take nova owner-play-4 setup
oc_wait_pidfile nova
OC_PID_D=$(oc_pid nova)
check "(d) release by a non-taker is refused" oc_rc 3 release nova owner-play-not-the-taker
check "(d) the capture is unaffected by the refused release" oc_alive nova
check "(d) the capture pid is unchanged" [ "$(oc_pid nova)" = "$OC_PID_D" ]

# (e) release by the right tag stops the capture and reports it
check "(e) release by the taker exits 0" oc_out 0 '^capture: ' release nova owner-play-4
check "(e) release's own stdout names the capture file and a byte count" grep -qE 'capture: .*\([0-9]+ bytes\)' "$OC/out"
check "(e) the capture process is gone after release" oc_dead nova
check "(e) the sidecar files are cleaned up" bash -c "[ ! -e '$OC_D/hold/nova.capture' ] && [ ! -e '$OC_D/hold/nova.capture.pid' ]"

# (f) who says NO CAPTURE RUNNING once the process is gone (not released -- killed)
check "(f) take for an owner-play tag exits 0 (setup)" oc_rc 0 take nova owner-play-6 setup
oc_wait_pidfile nova
OC_PID_F=$(oc_pid nova)
check "(f) who reports the capture while it is alive" oc_out 0 '^capture: ' who nova
kill -9 "$OC_PID_F" 2>/dev/null; sleep 0.2
check "(f) who says NO CAPTURE RUNNING once the process is dead" oc_out 0 '^NO CAPTURE RUNNING$' who nova
oc release nova owner-play-6 >/dev/null 2>&1

# (g) wait-idle reports the capture, and fails when it died
check "(g) take for an owner-play tag exits 0 (setup)" oc_rc 0 take nova owner-play-7 setup
oc_wait_pidfile nova
OC_PID_G=$(oc_pid nova)
check "(g) wait-idle on an idle owner-play hold exits 0 and names the capture" \
    oc_out 0 '^capture: ' wait-idle nova 0
kill -9 "$OC_PID_G" 2>/dev/null; sleep 0.2
check "(g) wait-idle exits 5 once the capture has died" oc_rc 5 wait-idle nova 0
oc release nova owner-play-7 >/dev/null 2>&1
rm -f "$OC_D/hold/nova" "$OC_D/hold/nova.why" "$OC_D/hold/nova.capture" "$OC_D/hold/nova.capture.pid"

# MUTANT: the fix removed must go red (leg (a) is not vacuous). A hold.sh
# whose take never calls capture_ensure still takes the hold (unchanged
# behaviour for every other tag), so (a)'s own assertion -- a "capture: "
# line on take's output -- is the only thing that can tell the difference.
OC_MUT="$OC/mut"; mkdir -p "$OC_MUT"
sed 's/if ! cap_line=\$(capture_ensure "\$label"); then/if false; then/' "$HERE/hold.sh" > "$OC_MUT/hold.sh"
cp "$HERE/device_build.py" "$OC_MUT/device_build.py"
check "mutant built: hold.sh with the capture start skipped" \
    [ "$(grep -c 'if ! cap_line=\$(capture_ensure "\$label"); then' "$OC_MUT/hold.sh")" -eq 0 ]
rm -f "$OC_D/hold/nova" "$OC_D/hold/nova.why"
OC_MUT_OUT=$(PATH="$OC/bin:$PATH" DISPATCH_DIR="$OC_D" bash "$OC_MUT/hold.sh" take nova owner-play-8 mutant 2>&1)
check "mutant: take still exits 0 with the hold taken (the mutant is not caught some other way)" \
    [ -f "$OC_D/hold/nova" ]
check "mutant: without the capture start, take's output never says capture (leg (a) is not vacuous)" \
    bash -c '! printf "%s" "$1" | grep -q "capture: "' _ "$OC_MUT_OUT"
PATH="$OC/bin:$PATH" DISPATCH_DIR="$OC_D" bash "$OC_MUT/hold.sh" release nova owner-play-8 >/dev/null 2>&1
rm -f "$OC_D/hold/nova" "$OC_D/hold/nova.why"
