# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# jobs/hold.sh (#433, 10-18; 10-22): an owner-play hold starts a host logcat
# capture, and the capture confirms itself.
#
# THE INCIDENTS.
#   2026-10-18. An owner playthrough's telemetry lives only in a host `adb
#   logcat` capture started before the title launches -- the device's own ring
#   buffer turns over in ~2-3 minutes and the release app writes no readable
#   telemetry file. The owner's first Fable launch was lost because nothing was
#   capturing; hold.sh now starts the capture itself (this fragment's legs a-g).
#   2026-10-22. Every `take` of an owner-play hold exited 6, "never confirmed
#   running": the capture's pidfile held a literal `$`. The service manager
#   rewrites a unit's command line before it execs it (systemd.service(5),
#   "Command lines"): `$$` becomes `$`, `${VAR}` is replaced, a whole argument
#   `$VAR` is replaced and word-split. hold.sh handed the whole script over as
#   `bash -c "$script"`, so `echo "$$" > "$PIDFILE"` became `echo "$" >
#   "$PIDFILE"`. This fragment passed throughout, because it ran its own
#   systemd-run, which handed the script to bash untouched. Same pass on a
#   second defect nobody saw: the script's `trap "kill $cur ..." TERM` was
#   double-quoted, so $cur was expanded (empty) when the trap was set and TERM
#   never reached the adb child.
#
# THE FAKE IS HONEST NOW. $OC/bin/systemd-run applies systemd's command-line
# expansion to its argv (python, below) before it execs anything, runs the
# command with a clean environment plus --setenv (a unit does not inherit the
# caller's), refuses a unit name that is still running, and records the unit's
# pid so $OC/bin/systemctl can stop it. Its expansion is checked against a
# table of what the REAL systemd-run did to the same words (collected on
# systemd 255, 2026-10-22), and against the real systemd-run itself whenever a
# user manager answers. Where it does, one leg also runs the capture script
# itself as a real transient unit (fake adb first on PATH, a serial no device
# has) -- the real expansion, no device.
#
# OC_HOLD_SH points the legs at another hold.sh (its own variable, not
# SELFTEST_HOLD_SH, so a run pointing this fragment and 99-hold-take.sh at
# two different mutants cannot collide). A copy outside jobs/ needs two things
# to run: `HERE=` pinned to the real jobs/ (it resolves devices.sh and
# dispatcher.sh from there) and device_build.py beside it (take runs
# "$(dirname "$0")/device_build.py"). oc_mutate below does both for the
# mutants; a hand-made copy of an old hold.sh must too.
#
# Each leg names the world in which it fails:
#   (a) take for an owner-play tag does not start a capture, starts one
#       without saying so, or starts one whose pidfile is not the capture's pid
#       (the launch lets systemd rewrite the script); SPEC's `*:S` is globbed.
#   (b) a second take (refused -- the label is already held) starts a
#       second capture, or loses the first.
#   (c) systemd-run refuses the unit: take still leaves the hold.
#   (d) release by the wrong tag stops the capture anyway.
#   (e) release by the right tag leaves the capture (or its adb child)
#       running, or does not report its file and size.
#   (f) who does not say NO CAPTURE RUNNING once the capture process is gone.
#   (g) wait-idle does not report the capture on an idle hold, or does not
#       notice when it died.
#   (h) SIGTERM to the capture's bash alone leaves its adb child running.
#   (i) the restart loop does not append with a gap marker when adb dies.
#   (j) a live process that merely mentions logcat passes for the capture, or
#       release kills it.
#   (k) a capture that systemd accepted but that never showed itself is left
#       running, and holds the unit name against the next take.
#   (l) the fake systemd-run's expansion differs from the table, or from the
#       real systemd-run's.
#   (m) real systemd: the pidfile is not the capture's pid, or TERM leaves the
#       adb child.
#
# Each mutant reinstates ONE weaker rule in a copy of hold.sh (oc_mutate, which
# fails unless the text it replaces occurs exactly once) and must turn its leg
# red: the capture start skipped (a), the 10-18 `bash -c "$script"` launch (a),
# the 10-18 double-quoted trap (h), the 10-18 cmdline-mentions-logcat identity
# (j), the unconfirmed unit left running (k), `set -f` removed (a).
#
# A non-owner-play tag is unaffected by any of this: 99-hold-take.sh's own
# legs (none of its tags start `owner-play`) are the regression check for
# that, unedited.

echo "== hold.sh: an owner-play hold starts a host logcat capture (#433)"

OC_SH="${OC_HOLD_SH:-$HERE/hold.sh}"
OC="$T/ownerplay"; rm -rf "$OC"; mkdir -p "$OC/dispatch/hold" "$OC/bin" "$OC/units" "$OC/mut" "$OC/cwd"
OC_D="$OC/dispatch"
: > "$OC/adb.pids"
: > "$OC/cwd/decoy:S"        # the unit's working directory holds a file `*:S` would glob to
cp "$HERE/device_build.py" "$OC/mut/device_build.py"   # hold.sh take runs "$(dirname "$0")/device_build.py": a copy needs it beside it

# Every fake finds its state beside itself ($OC), not in the caller's
# environment: a real unit does not inherit the caller's environment either.
cat > "$OC/bin/adb" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    devices) printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n'; exit 0 ;;
    *logcat*) echo $$ >> "$(dirname "$0")/../adb.pids"
              printf '=== fake logcat: %s ===\n' "$*"; exec sleep 100000 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$OC/bin/adb"

# A systemd-run that does to the command line what the service manager does.
# Rules, as observed on systemd 255 (see the table in this fragment):
#   - an argument that is exactly `$NAME` (the character after `$` is neither
#     `{` nor `$`): replaced by the variable's value split on whitespace; an
#     unset name drops the argument. `$` alone, `$1`, `$?`, `$(...)` are such
#     arguments and are dropped.
#   - anywhere else: `$$` -> `$`; `${NAME}` -> the value, or nothing if unset
#     (`${NAME:...}` and an unclosed `${` are left alone); any other `$` stays.
#   - `%` is not touched in a transient unit's command.
# Variables are the unit's environment: --setenv plus PATH/HOME/LANG.
# --expand-environment=no turns all of it off. --wait/--pipe run the command in
# the foreground (the table legs); otherwise it is detached in its own session
# and recorded as unit <name> for $OC/bin/systemctl.
cat > "$OC/bin/systemd-run" <<'EOF'
#!/usr/bin/env python3
import os, subprocess, sys


def expand_word(w, env):
    if w.startswith("$") and not w.startswith("${") and not w.startswith("$$"):
        v = env.get(w[1:])
        return v.split() if v is not None else []
    out, i = [], 0
    while i < len(w):
        if w.startswith("$$", i):
            out.append("$")
            i += 2
        elif w.startswith("${", i) and "}" in w[i:]:
            j = w.index("}", i)
            name = w[i + 2:j]
            out.append(w[i:j + 1] if ":" in name else env.get(name, ""))
            i = j + 1
        else:
            out.append(w[i])
            i += 1
    return ["".join(out)]


def main(argv):
    if os.environ.get("OC_SYSTEMD_RUN_FAIL") == "1":
        sys.stderr.write("systemd-run: refused (test)\n")
        return 1
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    unit, setenv, expand, sync = None, {}, True, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--":
            i += 1
            break
        if not a.startswith("-"):
            break
        if a in ("--unit", "-u"):
            unit = argv[i + 1]
            i += 2
            continue
        if a.startswith("--unit="):
            unit = a[7:]
        elif a.startswith("--setenv="):
            k, _, v = a[9:].partition("=")
            setenv[k] = v
        elif a.startswith("--expand-environment="):
            expand = a.split("=", 1)[1].lower() not in ("no", "false", "0", "off")
        elif a in ("--wait", "--pipe", "-P"):
            sync = True
        elif a in ("-p", "--property"):
            i += 1
        i += 1
    cmd = argv[i:]
    if not cmd:
        sys.stderr.write("Command line required\n")
        return 1
    env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": os.environ.get("HOME", "/"), "LANG": "C"}
    env.update(setenv)
    if expand:
        cmd = [w for a in cmd for w in expand_word(a, env)]
    if os.environ.get("OC_UNIT_SILENT") == "1":
        cmd = ["sleep", "100000"]      # a unit that starts and never says so
    cwd = os.path.join(root, "cwd")
    if unit:                           # what the unit's process is actually exec'd with, NUL-separated
        with open(os.path.join(root, "units", unit + ".argv"), "w") as f:
            f.write("\0".join(cmd))
    try:
        if sync:
            return subprocess.run(cmd, env=env, cwd=cwd).returncode
        if unit:
            try:
                os.kill(int(open(os.path.join(root, "units", unit + ".pid")).read()), 0)
                sys.stderr.write("Failed to start transient service unit: Unit %s.service was already loaded or has a fragment file.\n" % unit)
                return 1
            except (OSError, ValueError):
                pass
        log = open(os.path.join(root, "systemd-run.log"), "ab")
        p = subprocess.Popen(cmd, env=env, cwd=cwd, stdin=subprocess.DEVNULL, stdout=log,
                             stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as e:
        sys.stderr.write("Failed to start transient service unit: %s\n" % e)
        return 1
    if unit:
        for suffix in (".pid", ".last"):
            with open(os.path.join(root, "units", unit + suffix), "w") as f:
                f.write(str(p.pid))
    sys.stderr.write("Running as unit: %s.service\n" % unit)
    return 0


sys.exit(main(sys.argv[1:]))
EOF
chmod +x "$OC/bin/systemd-run"

# `systemctl --user stop <unit>` and `is-active <unit>` on the units the fake
# systemd-run started: a stop takes the unit's whole process group, as the real
# one takes its cgroup. Nothing else. (selftest.sh's global one answers
# `active` to everything.)
cat > "$OC/bin/systemctl" <<'EOF'
#!/usr/bin/env bash
root="$(cd "$(dirname "$0")/.." && pwd)"
op=""; unit=""
for a in "$@"; do
    case "$a" in -*) ;; *) if [ -z "$op" ]; then op=$a; elif [ -z "$unit" ]; then unit=${a%.service}; fi ;; esac
done
rec="$root/units/$unit.pid"
case "$op" in
    stop)
        if [ -f "$rec" ]; then
            pid=$(cat "$rec")
            kill -TERM -- "-$pid" 2>/dev/null
            for _ in $(seq 30); do kill -0 -- "-$pid" 2>/dev/null || break; sleep 0.1; done
            rm -f "$rec"
        fi
        exit 0 ;;
    is-active)
        if [ -f "$rec" ] && kill -0 "$(cat "$rec")" 2>/dev/null; then echo active; exit 0; fi
        echo inactive; exit 3 ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$OC/bin/systemctl"

ocx() { local sh=$1; shift
        PATH="$OC/bin:$PATH" DISPATCH_DIR="$OC_D" HOLD_WAIT_INTERVAL=1 HOLD_IDLE_INTERVAL=1 \
        HOLD_CAPTURE_CONFIRM_TRIES="${OC_TRIES:-25}" bash "$sh" "$@"; }
oc() { ocx "$OC_SH" "$@"; }
oc_rc() { local want=$1; shift; oc "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }
oc_out() { local want=$1 pat=$2; shift 2; oc "$@" >"$OC/out" 2>"$OC/err"; [ $? -eq "$want" ] && grep -q -- "$pat" "$OC/out"; }
oc_pid() { cat "$OC_D/hold/$1.capture.pid" 2>/dev/null; }
oc_alive() { local pid; pid=$(oc_pid "$1"); [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; }
oc_dead()  { ! oc_alive "$1"; }
oc_num() { [[ "${1:-}" =~ ^[0-9]+$ ]]; }
oc_gone() { ! kill -0 "$1" 2>/dev/null; }                 # <pid> is not alive
oc_wait() { local n=$(( $1 * 10 )) i=0; shift             # <timeout_s> <cmd...>: poll every 0.1 s until it succeeds
            while ! "$@" >/dev/null 2>&1; do i=$((i + 1)); [ "$i" -ge "$n" ] && return 1; sleep 0.1; done; }
oc_wait_pidfile() {   # <label> <timeout_s>: block until the pidfile shows up
    local label=$1 n=$(( ${2:-5} * 10 )) i=0
    while [ ! -s "$OC_D/hold/$label.capture.pid" ] && [ "$i" -lt "$n" ]; do sleep 0.1; i=$((i + 1)); done
}
oc_nadb()      { wc -l < "$OC/adb.pids"; }                 # fake-logcat starts so far
oc_adb_after() { [ "$(oc_nadb)" -gt "$1" ]; }              # ... more than <n>
oc_adb_last()  { tail -n1 "$OC/adb.pids"; }
oc_not() { ! "$@"; }
# Leave nothing of the label behind: the unit and its group, any fake-logcat
# child a kill -9 orphaned, the hold and capture files.
oc_reset() {
    "$OC/bin/systemctl" --user stop hakux-ownerplay-capture-nova >/dev/null 2>&1
    local p
    for p in $(cat "$OC/adb.pids" 2>/dev/null); do
        [ -e "/proc/$p" ] || continue
        [ "$(tr '\0' ' ' 2>/dev/null < "/proc/$p/cmdline")" = "sleep 100000 " ] && kill "$p" 2>/dev/null
    done
    rm -f "$OC_D/hold/nova" "$OC_D/hold/nova.why" "$OC_D/hold/nova.tier" "$OC_D/hold/nova.capture" \
          "$OC_D/hold/nova.capture.pid" "$OC_D/hold/nova.capture.sh"
}
# oc_mutate <out> <old> <new>: hold.sh with <old> (exactly once) replaced by
# <new>, HERE pinned to the real jobs/ so devices.sh and dispatcher.sh resolve.
oc_mutate() {
    python3 -I - "$OC_SH" "$1" "$2" "$3" "$HERE" <<'PY'
import sys
src, out, old, new, here = sys.argv[1:]
s = open(src).read()
if s.count(old) != 1:
    sys.exit(1)
lines = s.replace(old, new).split("\n")
for i, l in enumerate(lines):
    if l.startswith("HERE="):
        lines[i] = 'HERE="%s"' % here
        break
open(out, "w").write("\n".join(lines))
PY
}

# ---- probes: one hold.sh in, a verdict in globals out, so the same probe runs
# against hold.sh and against each mutant of it.

# take, then who: 0 when take started a capture that who then reports.
oc_core_probe() {
    local sh=$1 rc
    oc_reset
    ocx "$sh" take nova owner-play-core probe >"$OC/core.out" 2>&1; OC_CP_RC=$?
    [ "$OC_CP_RC" -eq 0 ] && grep -q '^capture: ' "$OC/core.out" && ocx "$sh" who nova 2>/dev/null | grep -q '^capture: '
    rc=$?
    ocx "$sh" release nova owner-play-core >/dev/null 2>&1
    oc_reset
    return $rc
}
# TERM to the capture's bash alone (all `kill <pidfile pid>` sends): did it and
# its adb child go? Sets OC_TP_BASH / OC_TP_CHILD to 0 when gone within 3 s.
oc_trap_probe() {
    local sh=$1 n0 pid child
    OC_TP_BASH=1; OC_TP_CHILD=1
    oc_reset
    n0=$(oc_nadb)
    ocx "$sh" take nova owner-play-trap probe >/dev/null 2>&1 || return 1
    oc_wait 3 oc_adb_after "$n0" || return 1
    pid=$(oc_pid nova); child=$(oc_adb_last)
    kill -TERM "$pid" 2>/dev/null
    oc_wait 3 oc_gone "$pid"; OC_TP_BASH=$?
    oc_wait 3 oc_gone "$child"; OC_TP_CHILD=$?
    ocx "$sh" release nova owner-play-trap >/dev/null 2>&1
    oc_reset
}
# A dead capture whose pidfile now names a live process that mentions logcat.
# Sets OC_ID_OLDCHECK (0: the old `grep logcat cmdline` check would accept the
# decoy), OC_ID_SAYS (0: who reports a capture), OC_ID_KILLED (0: release killed it).
oc_ident_probe() {
    local sh=$1 pid decoy
    OC_ID_OLDCHECK=1; OC_ID_SAYS=1; OC_ID_KILLED=1      # unknown counts as the bad answer
    oc_reset
    ocx "$sh" take nova owner-play-id probe >/dev/null 2>&1 || return 1
    pid=$(oc_pid nova)
    kill -9 "$pid" 2>/dev/null; oc_wait 3 oc_gone "$pid"
    # One process, no children (a bash -c decoy would orphan its sleep when a
    # mutant's release kills it), with "logcat" on its command line.
    python3 -I -c 'import time; time.sleep(100000)' adb-logcat-decoy </dev/null >/dev/null 2>&1 &
    decoy=$!
    sleep 0.3
    printf '%s\n' "$decoy" > "$OC_D/hold/nova.capture.pid"
    grep -q logcat "/proc/$decoy/cmdline" 2>/dev/null; OC_ID_OLDCHECK=$?
    ocx "$sh" who nova 2>/dev/null | grep -q '^capture: '; OC_ID_SAYS=$?
    ocx "$sh" release nova owner-play-id >/dev/null 2>&1
    sleep 0.3
    kill -0 "$decoy" 2>/dev/null; OC_ID_KILLED=$(( $? == 0 ? 0 : 1 ))     # 0: the decoy survived release
    kill "$decoy" 2>/dev/null
    oc_reset
}
# systemd accepts the unit, the unit never writes its pidfile: take must exit 6,
# stop the unit, and leave the name free for the next take.
# Sets OC_OR_RC (take's exit), OC_OR_GONE (0: the unit's process was gone within
# 3 s of the failed take) and OC_OR_RETAKE (the exit of the very next take, made
# while the first unit's process is left exactly as the failed take left it).
# Unknown answers are the bad ones.
oc_orphan_probe() {
    local sh=$1 last
    OC_OR_RC=; OC_OR_GONE=1; OC_OR_RETAKE=
    oc_reset; rm -f "$OC/units/"*
    OC_TRIES=5 OC_UNIT_SILENT=1 ocx "$sh" take nova owner-play-orphan silent >/dev/null 2>&1; OC_OR_RC=$?
    last=$(cat "$OC/units/hakux-ownerplay-capture-nova.last" 2>/dev/null)
    oc_num "$last" || { OC_OR_RC="no-unit:$OC_OR_RC"; return 1; }       # never `kill 0`: that is the whole process group
    oc_wait 3 oc_gone "$last"; OC_OR_GONE=$?
    ocx "$sh" take nova owner-play-orphan2 retake >/dev/null 2>&1; OC_OR_RETAKE=$?
    ocx "$sh" release nova owner-play-orphan2 >/dev/null 2>&1
    kill "$last" 2>/dev/null
    oc_reset
}
# Is SPEC's `*:S` handed to adb as written, with a file `decoy:S` in the unit's cwd?
oc_glob_probe() {
    local sh=$1 log
    OC_GP_LITERAL=1; OC_GP_GLOBBED=1
    oc_reset
    ocx "$sh" take nova owner-play-glob probe >/dev/null 2>&1 || return 1
    log=$(cat "$OC_D/hold/nova.capture" 2>/dev/null)
    oc_wait 3 grep -q 'fake logcat' "$log"
    grep -qF ' *:S ===' "$log"; OC_GP_LITERAL=$?
    grep -q 'decoy:S' "$log"; OC_GP_GLOBBED=$?
    ocx "$sh" release nova owner-play-glob >/dev/null 2>&1
    oc_reset
}

check "hold.sh parses (bash -n)" bash -n "$HERE/hold.sh"

# ---- (l) the fake's expansion: the table is what the REAL systemd-run (255)
# gave for `printf '<%s>' <word> END` with --setenv=A='x y' --setenv=_X=u.
OC_VECTORS=$(cat <<'VEC'
$A	<x><y><END>
${A}	<x y><END>
pre$A	<pre$A><END>
pre${A}post	<prex ypost><END>
$$	<$><END>
$$A	<$A><END>
$NOPE	<END>
${NOPE}	<><END>
$	<END>
a$	<a$><END>
${A	<${A><END>
${A:+b}	<${A:+b}><END>
$${A}	<${A}><END>
$$$$	<$$><END>
x${A}${NOPE}y	<xx yy><END>
$A$A	<END>
$(echo)	<END>
%H	<%H><END>
${A}}	<x y}><END>
echo "$$" > f	<echo "$" > f><END>
trap "kill $cur" TERM; echo ${A}	<trap "kill $cur" TERM; echo x y><END>
$_X	<u><END>
${_X}	<u><END>
VEC
)
oc_vec() { "$1" --user --wait --collect --pipe -q --setenv=A='x y' --setenv=_X=u printf '<%s>' "$2" END 2>/dev/null; }
oc_vec_bad() {   # <systemd-run>: the table words it does not reproduce, one per line
    local w want
    while IFS=$'\t' read -r w want; do
        [ "$(oc_vec "$1" "$w")" = "$want" ] || printf '%s\n' "$w"
    done <<< "$OC_VECTORS"
}
OC_BAD=$(oc_vec_bad "$OC/bin/systemd-run")
[ -z "$OC_BAD" ] || printf '    fake differs from the table on: %s\n' "$(printf '%s' "$OC_BAD" | tr '\n' ' ')"
check "(l) the fake systemd-run reproduces the table: \$\$ -> \$, \${VAR} replaced, a whole \$VAR split or dropped, the rest left to bash" \
    [ -z "$OC_BAD" ]
OC_E="$OC/expand.out"
"$OC/bin/systemd-run" --user --wait --collect --pipe -q bash -c 'printf %s "$$" > "$1"' _ "$OC_E" >/dev/null 2>&1
check "(l) through the fake, an unescaped \$\$ is a literal \$ in the script (the 10-22 defect)" \
    bash -c '[ "$(cat "$1")" = "\$" ]' _ "$OC_E"
"$OC/bin/systemd-run" --user --wait --collect --pipe -q --expand-environment=no bash -c 'printf %s "$$" > "$1"' _ "$OC_E" >/dev/null 2>&1
check "(l) with --expand-environment=no the same script gets its pid" oc_num "$(cat "$OC_E")"

OC_REAL_SD=/usr/bin/systemd-run; OC_REAL_SC=/usr/bin/systemctl
oc_real_ok() { [ -x "$OC_REAL_SD" ] && [ -x "$OC_REAL_SC" ] && [ "$(timeout 20 "$OC_REAL_SD" --user --wait --collect --pipe -q printf ok 2>/dev/null)" = ok ]; }
if oc_real_ok; then
    OC_BAD_REAL=$(oc_vec_bad "$OC_REAL_SD")
    [ -z "$OC_BAD_REAL" ] || printf '    the real systemd-run differs from the table on: %s\n' "$(printf '%s' "$OC_BAD_REAL" | tr '\n' ' ')"
    check "(l) the real systemd-run still gives the table (the fake is checked against it, not against a memory of it)" \
        [ -z "$OC_BAD_REAL" ]
else
    echo "  skip (l)/(m) real-systemd legs: no answering user manager (systemd-run --user printf ok)"
fi

# (a) take for an owner-play tag starts the capture and says so on its own stdout
n0=$(oc_nadb)
check "(a) take for an owner-play tag exits 0 and names the capture on stdout" \
    oc_out 0 '^capture: ' take nova owner-play-1 owner 10-18 playthrough
oc_wait_pidfile nova
check "(a) the pidfile holds the capture's pid (digits, not a literal \$)" oc_num "$(oc_pid nova)"
check "(a) a capture pidfile exists and names a live process" oc_alive nova
check "(a) the capture's log path was recorded" [ -s "$OC_D/hold/nova.capture" ]
check "(a) the capture script is a file beside the pidfile, and the unit is exec'd as 'bash <that file>' (no script text for systemd to rewrite)" \
    bash -c '[ -s "$1" ] && [ "$(tr "\0" " " < "$2")" = "bash $1" ]' _ "$OC_D/hold/nova.capture.sh" "$OC/units/hakux-ownerplay-capture-nova.argv"
check "(a) who also reports the capture while it is held" oc_out 0 '^capture: ' who nova
OC_LOG1=$(cat "$OC_D/hold/nova.capture")
oc_wait 3 oc_adb_after "$n0"
check "(a) the capture used the dispatcher's own LOGCAT_SPEC (not empty, not a copy)" \
    grep -q 'hakuX-crash:V' "$OC_LOG1"
check "(a) the unit's own environment reached adb: -s <serial> and the spec" \
    grep -q 'fake logcat: -s ee317437 logcat -v threadtime -T 1 hakuX-crash:V' "$OC_LOG1"
oc_glob_probe "$OC_SH"
check "(a) SPEC's *:S reaches adb as written" [ "$OC_GP_LITERAL" -eq 0 ]
check "(a) ... and is not globbed against the unit's working directory" [ "$OC_GP_GLOBBED" -ne 0 ]
oc_reset
oc_rc 0 take nova owner-play-1 owner 10-18 playthrough
oc_wait_pidfile nova

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
check "(c) no capture script is left behind" [ ! -e "$OC_D/hold/nova.capture.sh" ]

# (d) release by the wrong tag leaves the capture running
check "(d) take for an owner-play tag exits 0 (setup)" oc_rc 0 take nova owner-play-4 setup
oc_wait_pidfile nova
OC_PID_D=$(oc_pid nova)
check "(d) release by a non-taker is refused" oc_rc 3 release nova owner-play-not-the-taker
check "(d) the capture is unaffected by the refused release" oc_alive nova
check "(d) the capture pid is unchanged" [ "$(oc_pid nova)" = "$OC_PID_D" ]

# (e) release by the right tag stops the capture and reports it
oc_wait 3 oc_adb_after "$(( $(oc_nadb) - 1 ))"
OC_ADB_E=$(oc_adb_last)
check "(e) release by the taker exits 0" oc_out 0 '^capture: ' release nova owner-play-4
check "(e) release's own stdout names the capture file and a byte count" grep -qE 'capture: .*\([0-9]+ bytes\)' "$OC/out"
check "(e) the capture process is gone after release (the pid read BEFORE release)" oc_wait 3 oc_gone "$OC_PID_D"
check "(e) ... and so is its adb child" oc_wait 3 oc_gone "$OC_ADB_E"
check "(e) the sidecar files are cleaned up" \
    bash -c "[ ! -e '$OC_D/hold/nova.capture' ] && [ ! -e '$OC_D/hold/nova.capture.pid' ] && [ ! -e '$OC_D/hold/nova.capture.sh' ]"

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
oc_reset

# (h) TERM to the capture's own bash -- which is all `kill <pidfile pid>` sends --
# takes its adb child with it. The 10-18 script's double-quoted trap did not:
# every run of this fragment left four `sleep 100000` behind.
oc_trap_probe "$OC_SH"
check "(h) the capture's bash exits on TERM" [ "$OC_TP_BASH" -eq 0 ]
check "(h) its adb child is gone with it (the trap's \$cur is read when TERM comes, not when trap is set)" \
    [ "$OC_TP_CHILD" -eq 0 ]

# (i) the restart loop: adb dies, the capture appends a gap marker and a fresh
# start marker to the SAME file, with the same bash, and starts adb again.
oc_reset
n0=$(oc_nadb)
oc_rc 0 take nova owner-play-9 restart
oc_wait 3 oc_adb_after "$n0"
OC_PID_I=$(oc_pid nova); OC_LOG_I=$(cat "$OC_D/hold/nova.capture"); OC_ADB_I=$(oc_adb_last)
kill -TERM "$OC_ADB_I" 2>/dev/null
check "(i) adb is started again after the gap (within 8 s)" oc_wait 8 oc_adb_after "$(( n0 + 1 ))"
check "(i) the log says the first adb exited, with its rc, and that the capture restarts after a gap" \
    grep -qE '^=== capture process exited rc=143 at [0-9TZ:-]+; restarting after a gap ===$' "$OC_LOG_I"
check "(i) the log has two start markers" bash -c '[ "$(grep -c "^=== capture (re)start " "$1")" -ge 2 ]' _ "$OC_LOG_I"
check "(i) the first start marker is still the first line (appended, not truncated)" \
    bash -c 'head -n1 "$1" | grep -q "^=== capture (re)start "' _ "$OC_LOG_I"
check "(i) both adb runs wrote into the one file" bash -c '[ "$(grep -c "^=== fake logcat" "$1")" -ge 2 ]' _ "$OC_LOG_I"
check "(i) the same bash is still the capture, and the pidfile still names it" \
    bash -c '[ "$(cat "$1")" = "$2" ] && kill -0 "$2"' _ "$OC_D/hold/nova.capture.pid" "$OC_PID_I"
oc release nova owner-play-9 >/dev/null 2>&1
oc_reset

# (j) a pid that answers to kill -0 and mentions logcat is not the capture
oc_ident_probe "$OC_SH"
check "(j) the decoy would pass the old check (it mentions logcat on its command line)" [ "$OC_ID_OLDCHECK" -eq 0 ]
check "(j) who does not report a capture for it" [ "$OC_ID_SAYS" -ne 0 ]
check "(j) release does not kill it" [ "$OC_ID_KILLED" -eq 0 ]

# (k) a unit systemd accepted that never wrote its pidfile
oc_orphan_probe "$OC_SH"
check "(k) take exits 6" [ "$OC_OR_RC" -eq 6 ]
check "(k) the unit's process is stopped, not left running" [ "$OC_OR_GONE" -eq 0 ]
check "(k) the next take gets the unit name and a capture" [ "$OC_OR_RETAKE" -eq 0 ]

# (m) the real systemd: the capture script itself, as a real transient unit.
if oc_real_ok; then
    awk '/cat <<.CAPTURE_SCRIPT.$/{f=1;next} /^CAPTURE_SCRIPT$/{f=0} f' "$OC_SH" > "$OC/real-capture.sh"
    oc_real_unit() {   # <name> <file|dashc>: start it, wait for its pidfile
        local pf="$OC/real-$1.pid"; rm -f "$pf"
        if [ "$2" = file ]; then set -- "$1" bash "$OC/real-capture.sh"; else set -- "$1" bash -c "$(cat "$OC/real-capture.sh")"; fi
        local name=$1; shift
        "$OC_REAL_SD" --user --collect -q --unit "hakux-selftest-ownerplay-$name-$$" -p RuntimeMaxSec=60 \
            --setenv=PATH="$OC/bin:/usr/bin:/bin" --setenv=SERIAL=selftest-no-such-device --setenv=LOG="$OC/real-$name.log" \
            --setenv=SPEC='a:V *:S' --setenv=PIDFILE="$pf" "$@" >/dev/null 2>&1 || return 1
        oc_wait 5 test -s "$pf"
    }
    oc_real_stop() { "$OC_REAL_SC" --user stop "hakux-selftest-ownerplay-$1-$$" >/dev/null 2>&1; }
    n0=$(oc_nadb)
    oc_real_unit file file
    OC_RPID=$(cat "$OC/real-file.pid" 2>/dev/null)
    check "(m) real systemd, bash <file>: the pidfile holds the capture's pid" oc_num "$OC_RPID"
    check "(m) ... and that pid carries the PIDFILE the unit was given" \
        bash -c 'tr "\0" "\n" < /proc/$1/environ | grep -qxF "PIDFILE=$2"' _ "$OC_RPID" "$OC/real-file.pid"
    oc_wait 3 oc_adb_after "$n0"; OC_RCHILD=$(oc_adb_last)
    kill -TERM "$OC_RPID" 2>/dev/null
    check "(m) real systemd: TERM to the capture's bash ends it" oc_wait 3 oc_gone "$OC_RPID"
    check "(m) real systemd: ... and its adb child" oc_wait 3 oc_gone "$OC_RCHILD"
    oc_real_stop file
    oc_real_unit dashc dashc
    check "(m) real systemd, bash -c <script> (the 10-18 launch): the pidfile holds a literal \$" \
        bash -c '[ "$(cat "$1")" = "\$" ]' _ "$OC/real-dashc.pid"
    oc_real_stop dashc
    oc_reset
fi

# MUTANTS: each reinstates one weaker rule and must make its leg go red.
check "mutant built: hold.sh with the capture start skipped" \
    oc_mutate "$OC/mut/nocapture.sh" 'if ! cap_line=$(capture_ensure "$label"); then' 'if false; then'
rm -f "$OC_D/hold/nova" "$OC_D/hold/nova.why"
OC_MUT_OUT=$(ocx "$OC/mut/nocapture.sh" take nova owner-play-8 mutant 2>&1)
check "mutant: take still exits 0 with the hold taken (the mutant is not caught some other way)" \
    [ -f "$OC_D/hold/nova" ]
check "mutant: without the capture start, take's output never says capture (leg (a) is not vacuous)" \
    bash -c '! printf "%s" "$1" | grep -q "capture: "' _ "$OC_MUT_OUT"
ocx "$OC/mut/nocapture.sh" release nova owner-play-8 >/dev/null 2>&1
oc_reset

# the 10-22 launch: the script on bash's command line, for systemd to rewrite
# ($0 is given the script path so only the expansion differs from the fix).
check "mutant built: hold.sh with the plain bash -c \"\$script\" launch" \
    oc_mutate "$OC/mut/launch.sh" 'bash "$cs" >/dev/null 2>&1' 'bash -c "$(cat "$cs")" "$cs" >/dev/null 2>&1'
check "the fix passes the core probe (take, then who)" oc_core_probe "$OC_SH"
oc_core_probe "$OC/mut/launch.sh"; OC_M_RC=$?
check "mutant launch: take exits 6 and who has no capture (leg (a) is not vacuous)" [ "$OC_M_RC" -ne 0 ]
check "mutant launch: the script bash was exec'd with has its pid line rewritten to echo \"\$\" (the 10-22 symptom, as the unit received it)" \
    bash -c 'tr "\0" "\n" < "$1" | grep -qxF -- "echo \"\$\" > \"\$PIDFILE\""' _ "$OC/units/hakux-ownerplay-capture-nova.argv"
check "mutant launch: take says the unit never confirmed running" [ "$OC_CP_RC" -eq 6 ]

# the 10-18 trap: double-quoted, $cur read when the trap is set
check "mutant built: hold.sh with the double-quoted trap" \
    oc_mutate "$OC/mut/trap.sh" $'trap \'kill "$cur" 2>/dev/null; exit 0\' TERM' 'trap "kill $cur 2>/dev/null; exit 0" TERM'
oc_trap_probe "$OC/mut/trap.sh"
check "mutant trap: the capture's bash still exits on TERM (so only the child distinguishes it)" [ "$OC_TP_BASH" -eq 0 ]
check "mutant trap: the adb child survives TERM (leg (h) is not vacuous)" [ "$OC_TP_CHILD" -ne 0 ]

# the 10-18 identity: "/proc/<pid>/cmdline mentions logcat" (and, now that the script is a file, its name)
check "mutant built: hold.sh with the cmdline-mentions-logcat identity" \
    oc_mutate "$OC/mut/ident.sh" 'tr '\''\0'\'' '\''\n'\'' < "/proc/$2/environ" 2>/dev/null | grep -qxF -- "PIDFILE=$(cap_pidfile "$1")"' 'grep -q -E '\''logcat|capture\.sh'\'' "/proc/$2/cmdline" 2>/dev/null'
oc_ident_probe "$OC/mut/ident.sh"
check "mutant ident: who reports a capture for the decoy (leg (j) is not vacuous)" [ "$OC_ID_SAYS" -eq 0 ]
check "mutant ident: release kills the decoy" [ "$OC_ID_KILLED" -ne 0 ]

# the orphan: take gives up on a unit it started and leaves it running
check "mutant built: hold.sh that leaves an unconfirmed unit running" \
    oc_mutate "$OC/mut/orphan.sh" $'capture_stop "$label"\n    rm -f "$pf" "$(cap_pathfile "$label")" "$cs"\n' ''
oc_orphan_probe "$OC/mut/orphan.sh"
check "mutant orphan: take still exits 6" [ "$OC_OR_RC" -eq 6 ]
check "mutant orphan: the unit's process is still running" [ "$OC_OR_GONE" -ne 0 ]
check "mutant orphan: the next take is refused for the unit name (leg (k) is not vacuous)" [ "$OC_OR_RETAKE" -ne 0 ]

# the glob: set -f removed
check "mutant built: hold.sh without set -f" \
    oc_mutate "$OC/mut/glob.sh" $'set -f\n' ''
oc_glob_probe "$OC/mut/glob.sh"
check "mutant glob: *:S is globbed against the working directory (leg (a) is not vacuous)" [ "$OC_GP_GLOBBED" -eq 0 ]

oc_reset
