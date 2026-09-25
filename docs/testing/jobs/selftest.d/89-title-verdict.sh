# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# The title ruler: title_verdict.py over fixture result dirs, soak_title.sh's
# liveness check against a fake adb, and a mutant per check that must turn
# this fragment red.
#
# WHY FIXTURES AND MUTANTS BOTH. A verdict that says PASS on the passing
# fixture proves nothing about the four ways it can be wrong; each mutant
# below is one of them, written into a copy, and the fragment asserts that
# the fixtures catch it. A mutant that survives means a check that is green
# because it is looking at nothing.

echo "== title verdict: fixtures"
TV="$T/titlev"; rm -rf "$TV"; mkdir -p "$TV"

# Six result dirs, all in logcat -v time. Perf lines every 2 s is 30 fps
# (one line per 60 guest flips). Every fixture boots through 100 s of
# 10 fps loading BEFORE the mark, so a verdict that counts pre-mark windows
# sees 100 of 760 s below the bar (87% < 90%) and fails the passing run.
python3 - "$TV" <<'PY'
import json, os, sys
root = sys.argv[1]
T0 = 13 * 3600

def stamp(t):
    t = T0 + t
    return "09-25 %02d:%02d:%06.3f" % (t // 3600, (t % 3600) // 60, t % 60)

def make(name, *, mark=True, gap_at=None, crash_at=None, fps=30.0, g_ms=33.3,
         runlog_extra="", exited=None, end=760.0):
    d = os.path.join(root, name); os.makedirs(d)
    L = [(1.0, "I", "hakuX", "surface_scale=1 (override=)"),
         (2.0, "I", "hakuX-route", "soak start")]
    t = 10.0
    while t < 100.0:                      # loading at 10 fps, before the mark
        L.append((t, "I", "hakuX-perf", "gfps=10 G:100.0(90.0-110.0) D:16.7"))
        t += 6.0
    if mark:
        L.append((100.0, "I", "hakuX-route", "mark gameplay"))
    t = 100.5
    stop = crash_at if crash_at else end - 0.5
    while t < stop:
        if gap_at and gap_at <= t < gap_at + 30:   # 30 s with no flips
            t = gap_at + 30
            continue
        L.append((t, "I", "hakuX-perf",
                  "gfps=%d G:%.1f(%.1f-%.1f) D:16.7" % (fps, g_ms, g_ms - 1, g_ms + 1)))
        t += 60.0 / fps
    a = 0.0
    while a < stop:
        L.append((a, "I", "hakuX-audiocap",
                  "starve: 0/9375 callbacks short (0 empty), 0/1 bytes zero-filled"))
        a += 30.0
    if crash_at:
        L.append((crash_at, "E", "hakuX-crash", "=== XBOX KERNEL CRASH (BugCheck) ==="))
    else:
        L.append((end, "I", "hakuX-route", "soak end"))
    L.sort(key=lambda x: x[0])
    with open(os.path.join(d, "logcat.txt"), "w") as f:
        for t, lv, tag, msg in L:
            f.write("%s %s/%s( 4242): %s\n" % (stamp(t), lv, tag, msg))
    with open(os.path.join(d, "run.log"), "w") as f:
        f.write("ROUTE 13:00:00.000 start r.route serial=x\n")
        f.write(runlog_extra)
        if exited:
            f.write("guest exited after %ds of 900s\n" % exited)
        f.write("adb_failures=%d\n" % runlog_extra.count("ADB:"))
    json.dump({"id": "fx-" + name, "title": "Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso",
               "route_name": "crimson-skies", "route": "wait 1\n", "ref": "abc"},
              open(os.path.join(d, "request.json"), "w"))
    json.dump({"kind": "soak", "device_label": "nova", "apk_sha": "0" * 12, "ref": "abc"},
              open(os.path.join(d, "result.json"), "w"))

make("pass")
make("crash", crash_at=400.0, exited=400)
make("hang", gap_at=300.0)
make("nomark", mark=False)
# 20 fps by the clock, while G -- a smoothed average -- still claims 30.
make("below", fps=20.0, g_ms=33.3)
# Three failed probes, and the guest never exited: not a crash, not a hang.
make("adbfail", runlog_extra="".join(
    "ADB: liveness probe failed (try %d/3): UtilAcceptVsock:271: accept4 failed 110\n" % k
    for k in (1, 2, 3)))
PY

# verdict_expect <title_verdict.py> -> prints one "FAIL <why>" line per unmet
# expectation, nothing when all hold. Used for the real script (each line is a
# bad) and for every mutant (at least one line is the mutant being caught).
verdict_expect() {
    local vpy="$1" f
    for f in pass crash hang nomark below adbfail; do
        rm -f "$TV/$f/verdict.json"
        python3 "$vpy" "$TV/$f" --targets "$TESTING/titles/targets.toml" >/dev/null 2>&1 \
            || { echo "FAIL $f: title_verdict exited non-zero"; continue; }
    done
    python3 - "$TV" <<'PY'
import json, os, sys
root = sys.argv[1]
def v(n):
    try:
        return json.load(open(os.path.join(root, n, "verdict.json")))
    except Exception:
        return {}
exp = {
    "pass":    lambda x: x.get("pass") is True and x.get("rating_candidate") == "Playable"
                         and x.get("fps_windows", 0) > 300 and x.get("audio_measured") is True,
    "crash":   lambda x: x.get("pass") is False and x.get("crash") is True
                         and (x.get("failing") or "").startswith("crash"),
    "hang":    lambda x: x.get("pass") is False and x.get("hang") is True and x.get("crash") is False,
    "nomark":  lambda x: x.get("pass") is False and x.get("reached_gameplay") is False
                         and (x.get("failing") or "").startswith("reached_gameplay"),
    "below":   lambda x: x.get("pass") is False and (x.get("failing") or "").startswith("fps")
                         and x.get("fps_ok_share") is not None and x["fps_ok_share"] < 0.9,
    "adbfail": lambda x: x.get("pass") is True and x.get("crash") is False
                         and x.get("adb_failures") == 3,
}
for n, ok in exp.items():
    x = v(n)
    if not ok(x):
        print("FAIL %s: pass=%s failing=%s crash=%s hang=%s fps_ok=%s" % (
            n, x.get("pass"), x.get("failing"), x.get("crash"), x.get("hang"), x.get("fps_ok_share")))
PY
}

out=$(verdict_expect "$TESTING/title_verdict.py")
for f in pass crash hang nomark below adbfail; do
    case "$out" in
        *"FAIL $f:"*) bad "verdict on the '$f' fixture: $(printf '%s\n' "$out" | grep "FAIL $f:")" ;;
        *) ok "verdict on the '$f' fixture is what it should be" ;;
    esac
done
check "verdict.json is valid JSON and names the Crimson Skies title id" \
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1])); assert v["title_id"]=="4D530021" and v["human_review"]==""' "$TV/pass/verdict.json"

echo "== title verdict: mutants of title_verdict.py"
# Each is one line changed in a copy; `grep -q` first, so a mutant whose
# anchor no longer exists fails loudly instead of testing the original.
# A mutant counts as caught only by THE fixture aimed at it: "some line went
# red" would also be satisfied by an unrelated broken expectation, which is
# exactly how a mutant survives unnoticed.
tv_mutant() {   # <name> <fixture that must catch it> <python: old> <python: new>
    local name="$1" want="$2" m="$T/tv-mutant.py"
    shift
    python3 - "$TESTING/title_verdict.py" "$m" "$2" "$3" <<'PY'
import sys
src, dst, old, new = sys.argv[1:5]
s = open(src).read()
if s.count(old) != 1:
    sys.exit("anchor not found once: %r" % old)
open(dst, "w").write(s.replace(old, new))
PY
    [ $? = 0 ] || { bad "mutant '$name': its anchor is gone from title_verdict.py -- update the mutant"; return; }
    # The copy imports nothing from its own directory, but it reads the
    # targets file by path, which verdict_expect passes explicitly.
    case "$(verdict_expect "$m")" in
        *"FAIL $want:"*) ok "mutant caught by the '$want' fixture: $name" ;;
        *) bad "mutant SURVIVED the '$want' fixture: $name" ;;
    esac
    rm -f "$m"
}
tv_mutant "judge by G" below \
    'FRAMES_PER_LINE / dt_s, float(p1.group(2))' \
    '1000.0 / float(p1.group(2)), float(p1.group(2))'
tv_mutant "count pre-mark windows" pass \
    'zip(after, after[1:])' \
    'zip(perf, perf[1:])'
tv_mutant "drop the hang check" hang \
    'v["hang"] = bool(hang_gaps)' \
    'v["hang"] = False'

echo "== soak_title.sh: one failed adb probe is not a guest exit"
# A fake adb that answers the soak's calls. `ps` answers in the order the
# scenario file lists: up (running), fail (a WSL vsock error, exit 1), down
# (running, no xemu). Past the end, the last answer repeats.
SK="$T/soak"; rm -rf "$SK"; mkdir -p "$SK/bin"
cat > "$SK/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$SOAK_FAKE/calls"
case "$*" in
    *"ps -A -o NAME"*)
        n=$(cat "$SOAK_FAKE/n" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$SOAK_FAKE/n"
        a=$(sed -n "${n}p" "$SOAK_FAKE/scenario"); [ -n "$a" ] || a=$(tail -1 "$SOAK_FAKE/scenario")
        case "$a" in
            up)   printf 'NAME\r\ninit\r\ncom.jreinach.hakux.debug:xemu\r\n' ;;
            down) printf 'NAME\r\ninit\r\n' ;;
            fail) echo "UtilAcceptVsock:271: accept4 failed 110" >&2; exit 1 ;;
        esac ;;
    *) exit 0 ;;
esac
EOF
chmod +x "$SK/bin/adb"
printf 'wait 600\n' > "$SK/r.route"

soak_run() {   # <soak_title.sh> <scenario words...> -> run.log on stdout
    local s="$1"; shift
    rm -f "$SK/n" "$SK/calls"; printf '%s\n' "$@" > "$SK/scenario"
    # The lease is a scratch file: release() removes it, and the real shared
    # lease on a host must never be touched by a selftest.
    PATH="$SK/bin:$PATH" SOAK_FAKE="$SK" SERIAL=ee317437 ROUTE_DRY=1 \
        HAKUX_DEVICE_LEASE="$SK/lease" SOAK_POLL_S=0.2 SOAK_RETRY_S=0.1 \
        ROUTE_FILE="$SK/r.route" timeout 60 bash "$s" /fake/iso.iso 2 2>&1
}
log1=$(soak_run "$TESTING/soak_title.sh" up fail up)
case "$log1" in *"guest exited"*) bad "one failed probe ended the soak as a guest exit";;
                *) ok "one failed probe did not end the soak";; esac
case "$log1" in *"adb_failures=1"*) ok "adb_failures=1 is written to run.log";;
                *) bad "adb_failures=1 missing from run.log: $(printf '%s' "$log1" | grep adb_failures)";; esac
case "$log1" in *"held iso.iso"*) ok "the soak held to its deadline";;
                *) bad "the soak did not hold to its deadline";; esac
case "$log1" in *"ROUTE started"*"ROUTE "*" end"*) ok "the route was started and stopped with the hold";;
                *) bad "the route was not started and stopped: $(printf '%s' "$log1" | grep ROUTE | head -3)";; esac
log2=$(soak_run "$TESTING/soak_title.sh" up up down)
case "$log2" in *"guest exited"*) ok "a real exit (ps works, no xemu) still ends the soak";;
                *) bad "a real exit was not seen";; esac
log3=$(soak_run "$TESTING/soak_title.sh" up fail fail fail up)
case "$log3" in *"guest exited"*) bad "three failed probes read as an exit (should be unknown)";;
                *"adb_failures=3"*) ok "three failed probes are unknown, counted, and keep holding";;
                *) bad "three failed probes: $(printf '%s' "$log3" | grep -E 'adb_failures|ADB' | head -3)";; esac

echo "== soak_title.sh mutant: treat one adb failure as an exit"
SM="$T/soak-mutant"; rm -rf "$SM"; mkdir -p "$SM"
cp "$TESTING/devices.sh" "$SM/"; mkdir -p "$SM/titles" "$SM/perf"
cp "$TESTING/titles/route.sh" "$SM/titles/"; cp "$TESTING/perf/pad.sh" "$SM/perf/"
if python3 - "$TESTING/soak_title.sh" "$SM/soak_title.sh" <<'PY'
import sys
s = open(sys.argv[1]).read()
old = '[ "$r" = 2 ] || return "$r"'
if s.count(old) != 1:
    sys.exit(1)
open(sys.argv[2], "w").write(s.replace(old, '[ "$r" = 2 ] && return 1; return "$r"'))
PY
then
    case "$(soak_run "$SM/soak_title.sh" up fail up)" in
        *"guest exited"*) ok "mutant caught: treat one adb failure as an exit" ;;
        *) bad "mutant SURVIVED: treat one adb failure as an exit" ;;
    esac
else
    bad "soak mutant: its anchor is gone from soak_title.sh -- update the mutant"
fi
rm -rf "$SM"

echo "== route.sh: a route is refused before anything is played"
printf 'wait 1\npress Q\n' > "$SK/bad.route"
check "route.sh --check refuses an unknown button" \
    bash -c '! bash "$1" --check "$2"' _ "$TESTING/titles/route.sh" "$SK/bad.route"
for r in "$TESTING"/titles/routes/*.route; do
    check "route parses: $(basename "$r")" bash "$TESTING/titles/route.sh" --check "$r"
done
echo "== request.sh --route: the route's text travels in the request"
# A private dispatch dir, so the queued record cannot change what a later
# fragment counts in the harness's queue.
RQ="$T/route-queue"; rm -rf "$RQ"; mkdir -p "$RQ"/{queue,running,results,expect}
rq() { DISPATCH_DIR="$RQ" bash "$TESTING/request.sh" --who rt --purpose "route selftest" --no-expect "selftest" "$@"; }
if rq --title "Crimson Skies.iso" --seconds 900 --route crimson-skies >/dev/null 2>&1; then
    check "the queued request carries the route's name and full text" \
        python3 -c 'import json,glob,sys; r=json.load(open(glob.glob(sys.argv[1]+"/queue/*.req")[0])); src=open(sys.argv[2]).read(); assert r["route_name"]=="crimson-skies" and r["route"].strip()==src.strip()' \
        "$RQ" "$TESTING/titles/routes/crimson-skies.route"
else
    bad "request.sh refused a valid --title --route request"
fi
# On the WORDS, not the exit code: request.sh exits 2 for a dozen reasons.
case "$(rq --suites "Blend tests" --route crimson-skies 2>&1)" in
    *"--route only means anything on a soak"*) ok "request.sh refuses --route without --title" ;;
    *) bad "request.sh did not refuse --route without --title" ;; esac
case "$(rq --title a.iso --route no-such-route 2>&1)" in
    *"no route 'no-such-route'"*) ok "request.sh refuses a route that does not exist" ;;
    *) bad "request.sh did not refuse a missing route" ;; esac
unset TV SK SM RQ log1 log2 log3 out
