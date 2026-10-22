# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, $REPO,
# ok/bad/check. Not executable, no shebang, no exit.
#
# playprobe_report.py (#433, playprobe1021, owner 2026-10-21: "the game needs to hold 30 FPS
# regardless of the path chosen when in gameplay. If falling into water craters the framerate,
# we need to know that."). A read-only tool: it lays the `hakuX-perf gfps=` lines of a run
# against the `input` / `play-probe` markers drive.py writes to logcat. Nothing here touches
# a device; the logcat is a fixture built below, to the formats the tool's parsers expect.
#
# THE FIXTURE (device clock 18:00:00 + n s; gfps 30 unless named):
#   30        state=play; hold LY min RT max
#   60        hold LY max RT max               (62: tap A)
#   64-66     gfps 18 19 17                    -> ONE dip (3 s), under hold LY max, tap A 2 s before
#   77, 78.5  play-probe round 2 start; tap A  -> before the dip at 80
#   80        gfps 22                          -> a dip, with the probe line and the tap in view
#   90, 91    gfps 29, 28                      -> 29 is AT the bar (30 x 0.95 = 28.5); 28 is a dip
#   95        state=ingame_menu; 96-99 gfps 10 -> below the bar, NOT in play: counted apart
#   100       state=play; hold LY min RT max
#   so: 74 play seconds, 69 at the bar, 5 below, 3 dips, 4 below-bar seconds outside play.
#
# THE MUTANTS (the source is patched in memory; each anchor must match once):
#   state     the `play`-only filter dropped: menu seconds are scored as dips
#   merge     consecutive dip seconds not merged: the 3 s dip is 3
#   hold      the held input never found: "holding: nothing logged"
#   lookback  no window before a dip: the tap and the probe line are not shown

echo "== playprobe_report.py: dips laid against the inputs before them (playprobe1021)"

PR="$T/playprobe"; rm -rf "$PR"; mkdir -p "$PR"
PRTOOL="$TESTING/titles/playprobe_report.py"

cat > "$PR/gen.py" <<'PY'
import sys

def line(n, tag, msg, pid=5000):
    s = 18 * 3600 + n
    return "10-21 %02d:%02d:%06.3f I/%s(%5d): %s" % (s // 3600, s % 3600 // 60, s % 60, tag, pid, msg)

no_inputs = "--no-inputs" in sys.argv
no_perf = "--no-perf" in sys.argv
out = []
def route(n, msg):
    out.append(line(n, "hakuX-route", msg, 6000))

for n, st in ((0, "boot"), (10, "title"), (20, "unknown"), (30, "play"), (95, "ingame_menu"), (100, "play")):
    route(n, "state=%s t=%d" % (st, n))
if not no_inputs:
    route(30.2, "input t=30.2 hold LY min RT max why=play")
    route(60.0, "input t=60.0 hold LY max RT max why=play")
    route(62.0, "input t=62.0 tap A why=play")
    route(77.0, "play-probe round 2 start idle=8.0s queue=A,X,Y t=77.0")
    route(78.5, "input t=78.5 tap A why=play")
    route(100.0, "input t=100.0 hold LY min RT max why=play")

dips = {64: 18, 65: 19, 66: 17, 80: 22, 90: 29, 91: 28, 96: 10, 97: 10, 98: 10, 99: 10}
if not no_perf:
    for n in range(30, 110):
        out.append(line(n, "hakuX-perf", "gfps=%d G:16.6(15.2-18.1) D:16.7(16.6-16.7) S:0.7 J:0.0 Df:0" % dips.get(n, 30)))
out.sort()
print("\n".join(out))
PY

# runs the tool's main() with its source patched in memory: <old> <new> <args...>; "-" = unpatched
cat > "$PR/mut.py" <<'PY'
import sys
path, old, new = sys.argv[1:4]
src = open(path).read()
if old != "-":
    assert src.count(old) == 1, "mutant anchor %r matches %d times" % (old, src.count(old))
    src = src.replace(old, new)
ns = {"__file__": path, "__name__": "playprobe_report_mutant"}
exec(compile(src, path, "exec"), ns)
sys.exit(ns["main"](sys.argv[4:]))
PY

python3 "$PR/gen.py" > "$PR/logcat.txt"
python3 "$PR/gen.py" --no-inputs > "$PR/noinputs.txt"
python3 "$PR/gen.py" --no-perf > "$PR/noperf.txt"
rc=0; python3 "$PRTOOL" "$PR/logcat.txt" > "$PR/real.out" 2>&1 || rc=$?
check "playprobe_report: runs on the fixture and exits 0" test "$rc" = "0"
check "playprobe_report: the bar is the verdict's (30 x 0.95 = 28.5)" grep -q "gfps >= 28.5" "$PR/real.out"
check "playprobe_report: 74 play seconds, 69 at the bar, 5 below" \
    grep -q "play: 74 perf seconds, 69 at the bar (93.2%.*), 5 below" "$PR/real.out"
check "playprobe_report: three dips; the 3 s one is one dip, 29 gfps is not a dip, 28 is" \
    grep -q "playprobe_report: 3 dip(s) in 74 play s" "$PR/real.out"
check "playprobe_report: the 3 s dip is named with its length and its worst second" \
    grep -qE "^dip 18:01:03\.[0-9]+ - 18:01:06\.[0-9]+  3 s  min 17  mean 18\.0" "$PR/real.out"
check "playprobe_report: it names what was held (hold LY max RT max) and the tap 2 s before" \
    bash -c 'sed -n "/^dip 18:01:03/,/^dip 18:01:19/p" "$1" | grep -q "holding: hold LY max RT max" && sed -n "/^dip 18:01:03/,/^dip 18:01:19/p" "$1" | grep -q "input tap A"' _ "$PR/real.out"
check "playprobe_report: the dip at 80 s shows the probe line and the tap that came before it" \
    bash -c 'sed -n "/^dip 18:01:19/,/^dip 18:01:30/p" "$1" > "$2"; grep -q "play-probe round 2 start" "$2" && grep -q "input tap A" "$2"' _ "$PR/real.out" "$PR/b.out"
check "playprobe_report: a dip with nothing before it says so, rather than guessing" \
    grep -q "no input or probe in the 4 s before it" "$PR/real.out"
check "playprobe_report: 4 below-bar seconds in a menu are counted apart, not as dips" \
    grep -q "outside play: 4 below-bar seconds" "$PR/real.out"
check "playprobe_report: by input -- 35 s under hold LY max RT max, mean 28.7, 5 below the bar" \
    grep -qE "hold LY max RT max +35 s +mean +28\.7 +below bar 5 s" "$PR/real.out"
python3 "$PRTOOL" "$PR/logcat.txt" --bar 29.5 > "$PR/bar.out" 2>&1
check "playprobe_report: --bar moves the line (29 gfps is below 29.5: 6 below, joined to the 28 as one dip)" \
    grep -q "), 6 below" "$PR/bar.out" && grep -q "playprobe_report: 3 dip(s)" "$PR/bar.out"

python3 "$PRTOOL" "$PR/noinputs.txt" > "$PR/noin.out" 2>&1
check "playprobe_report: a run with no input markers says the dips are not attributable" \
    grep -q "NOT attributable" "$PR/noin.out"
check "playprobe_report: ... and does not claim a cause (no holding line)" \
    bash -c '! grep -q "holding:" "$1"' _ "$PR/noin.out"
python3 "$PRTOOL" "$PR/noperf.txt" > "$PR/noperf.out" 2>&1
check "playprobe_report: no gfps lines reads not measured, never 0 dips" \
    grep -q "not measured: no hakuX-perf gfps= line" "$PR/noperf.out"
python3 "$PRTOOL" "$PR/nonexistent.txt" > "$PR/none.out" 2>&1
check "playprobe_report: a missing logcat exits 2" test "$?" = "2"

python3 "$PR/mut.py" "$PRTOOL" '        if state_at(mid) != "play":' '        if False:' "$PR/logcat.txt" > "$PR/m-state.out" 2>&1
check "mutant (menu seconds scored as play): the outside-play count and the 5-below count are wrong" \
    bash -c '! grep -q "outside play: 4 below-bar seconds" "$1"' _ "$PR/m-state.out"
python3 "$PR/mut.py" "$PRTOOL" 'MERGE_GAP_S = 2.5' 'MERGE_GAP_S = 0.5' "$PR/logcat.txt" > "$PR/m-merge.out" 2>&1
check "mutant (consecutive dip seconds not merged): the 3 s dip is three" \
    bash -c '! grep -q "playprobe_report: 3 dip(s)" "$1"' _ "$PR/m-merge.out"
python3 "$PR/mut.py" "$PRTOOL" '            if is_hold(inputs[i][1]):' '            if False:' "$PR/logcat.txt" > "$PR/m-hold.out" 2>&1
check "mutant (held input never found): the dip says nothing logged" \
    bash -c 'grep -q "holding: nothing logged" "$1" && ! grep -q "holding: hold LY max RT max" "$1"' _ "$PR/m-hold.out"
python3 "$PR/mut.py" "$PRTOOL" '        lo, hi = start - lookback, end' '        lo, hi = end, end' "$PR/logcat.txt" > "$PR/m-look.out" 2>&1
check "mutant (no window before a dip): the tap and the probe line are not shown" \
    bash -c '! grep -q "play-probe round 2 start" "$1"' _ "$PR/m-look.out"
