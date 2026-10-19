# Sourced by ../selftest.sh with the harness already built: $T, $REPO, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit -- fail is
# the run's shared counter.
#
# fpsdiag.py (#433, fpsdiag1018) never touches a device from this fragment --
# only `analyze`/`gaps` run, against logcat fixtures this fragment builds
# itself under $T/fpsdiag. No shared state with any other fragment.
#
# This is a greenfield tool (no prior version to run a legacy function
# against), so "mutant-based" here means the brief's own four requirements,
# checked against synthetic fixtures built to the tool's own documented
# formats -- not 86-nightly-notes.sh's "run the old logic and watch it get
# the wrong answer" shape, which has no analog without a predecessor:
#   1. a planted cause reads "supported" while a measured-but-small cause
#      reads "refuted" and a data-less candidate reads "not measured" --
#      together, in one run.
#   2. swapping which class carries the plant flips supported -> refuted
#      (the check reads the data; it is not a constant).
#   3. a fixture with the plant's own tag entirely absent reads "not
#      measured", never "refuted".
#   4. a window holding a boot/pipeline-warmup marker, a save-state load, or
#      zero flip advance is excluded from both classes, counted separately.

echo "== fpsdiag.py: analyze/gaps against synthetic logcat fixtures"

FD="$T/fpsdiag"
mkdir -p "$FD"
FPSDIAG="$REPO/docs/testing/perf/fpsdiag/fpsdiag.py"

# gen.py emits one synthetic hakuX logcat to stdout: --dip/--good windows of
# hakuX-pace + hakuX-phase + [rdc] lines, at the exact field formats
# fpsdiag.py's own parsers expect (Fin:(Sub: Fen:) Tot: GPU:(R: X:) Draw:
# Idle:(Fr: St:); [rdc] tcpu=/vtx=a/b/c/d/tex=a/b/c/d; f=/max=/ms=). dip
# windows get ms=3750 (16 fps); good windows get ms=1875 (32 fps); the
# default bar for an unlisted title is 28.5 fps (30 x 0.95), so dip windows
# always fall under it and good windows always clear it.
cat > "$FD/gen.py" <<'PY'
import argparse

def logline(t, tag, msg, pid=5000):
    hh = int(t // 3600) % 24
    mm = int((t % 3600) // 60)
    ss = t % 60
    return "10-18 %02d:%02d:%06.3f %5d %5d I %s: %s" % (hh, mm, ss, pid, pid + 1, tag, msg)

ap = argparse.ArgumentParser()
ap.add_argument('--dip', type=int, default=6)
ap.add_argument('--good', type=int, default=6)
ap.add_argument('--dip-busy', type=float, default=34.0)
ap.add_argument('--good-busy', type=float, default=30.0)
ap.add_argument('--dip-fen', type=float, default=13.6)
ap.add_argument('--good-fen', type=float, default=2.5)
ap.add_argument('--omit-phase', action='store_true')
ap.add_argument('--boot-at', type=int, default=-1)       # 1-based window index
ap.add_argument('--savestate-at', type=int, default=-1)
ap.add_argument('--zero-flip-at', type=int, default=-1)
args = ap.parse_args()

out = []
t = 43210.0
n = args.dip + args.good
for i in range(1, n + 1):
    is_dip = i <= args.dip
    busy = args.dip_busy if is_dip else args.good_busy
    fen = args.dip_fen if is_dip else args.good_fen
    ms = 3750.0 if is_dip else 1875.0
    tot = 35.0
    gpu = busy / 100.0 * tot

    # Windows are 10 s apart here (vs. real pace ticks' tens of ms) so that
    # mark_refused's own +/-2 s boot-marker tolerance -- generous on
    # purpose, to catch the several real frames around a warm-up blip --
    # does not also reach into a neighbour window at this fixture's much
    # coarser spacing. A marker placed at the window's own midpoint (5 s
    # before its defining pace row) stays inside only that one window's
    # +/-2 s margin.
    if i == args.boot_at:
        out.append(logline(t - 5.0, 'hakuX-build', 'Shader module warm-up complete'))
    if i == args.savestate_at:
        out.append(logline(t - 5.0, 'hakuX', '[savestate] op=load slot=5'))

    if not args.omit_phase:
        out.append(logline(t - 0.02, 'hakuX-phase',
            'Fin:%.1f(Sub:18.0 Fen:%.1f) Tot:%.1f GPU:%.1f(R:%.1f X:1.0) Draw:2.0 Idle:5.0(Fr:3.0 St:2.0)'
            % (fen + 18.0, fen, tot, gpu, gpu - 1.0)))
    out.append(logline(t - 0.01, 'hakuX-stall',
        '[rdc] f=60 dt=1000 tcpu=1150.0 rdous=2 vtx=1/2/3/4 tex=1/2/3/4'))

    if i == args.zero_flip_at:
        out.append(logline(t, 'hakuX-pace', 'f=0 max=0 ms=0'))
    else:
        out.append(logline(t, 'hakuX-pace', 'f=60 max=16.8 ms=%.1f' % ms))
    t += 10.0

print('\n'.join(out))
PY

# -- 1. planted cause reads supported; a small measured effect reads
#    refuted; a data-less candidate reads not measured -- together --------
python3 "$FD/gen.py" --dip 6 --good 6 > "$FD/planted.txt"
python3 "$FPSDIAG" analyze "$FD/planted.txt" --title "Grand Theft Auto III" > "$FD/planted.out" 2>&1
planted_rc=$?
check "fpsdiag analyze: planted fixture exits 0" test "$planted_rc" = "0"
check "fpsdiag analyze: planted fixture scores all 12 windows, refuses none" \
    grep -q "windows: 12 total, 12 scored, 0 refused" "$FD/planted.out"
check "fpsdiag analyze: planted fixture splits 6 dip / 6 good" \
    grep -q "dip (< bar): 6 windows, good (>= bar): 6 windows" "$FD/planted.out"
check "fpsdiag analyze: planted Fen swing (the planted cause) reads supported" \
    grep -q "c2_fin_fen_queue_depth.*supported.*Fen (fence-wait) 13.6ms dip vs 2.5ms good" "$FD/planted.out"
check "fpsdiag analyze: planted GPU busy (flat, not the cause) reads refuted" \
    grep -q "gpu_saturation .*refuted.*GPU busy 34% in dip windows vs 30% in good.*not saturated" "$FD/planted.out"
check "fpsdiag analyze: planted TLB walk share (tiny) reads refuted" \
    grep -q "tlb_walk_cost .*refuted" "$FD/planted.out"
check "fpsdiag analyze: planted zero ART GC lines reads refuted, not not-measured" \
    grep -q "c7_art_gc_pause .*refuted.*zero ART GC log lines" "$FD/planted.out"
check "fpsdiag analyze: a candidate with no capture-sample support reads not measured" \
    grep -q "c4_competing_process_cpu .*not measured" "$FD/planted.out"

# -- 2. swap which class carries the plant: supported -> refuted -----------
python3 "$FD/gen.py" --dip 6 --good 6 --dip-fen 2.5 --good-fen 13.6 > "$FD/swapped.txt"
python3 "$FPSDIAG" analyze "$FD/swapped.txt" --title "Grand Theft Auto III" > "$FD/swapped.out" 2>&1
check "fpsdiag analyze: swapping which class carries the Fen plant flips the verdict to refuted" \
    grep -q "c2_fin_fen_queue_depth.*refuted.*no swing" "$FD/swapped.out"

# -- 3. the plant's own tag entirely absent: not measured, never refuted ---
python3 "$FD/gen.py" --dip 6 --good 6 --omit-phase > "$FD/nophase.txt"
python3 "$FPSDIAG" analyze "$FD/nophase.txt" --title "Grand Theft Auto III" > "$FD/nophase.out" 2>&1
check "fpsdiag analyze: hakuX-phase absent -> Fen swing reads not measured" \
    grep -q "c2_fin_fen_queue_depth.*not measured.*hakuX-phase absent" "$FD/nophase.out"
check "fpsdiag analyze: hakuX-phase absent -> GPU saturation reads not measured" \
    grep -q "gpu_saturation .*not measured.*hakuX-phase absent" "$FD/nophase.out"
check "fpsdiag analyze: hakuX-phase absent never reads refuted for either phase-dependent candidate" \
    bash -c '! grep -qE "(c2_fin_fen_queue_depth|gpu_saturation) +refuted" "$1"' _ "$FD/nophase.out"
check "fpsdiag analyze: a candidate independent of hakuX-phase ([rdc]) is unaffected" \
    grep -q "tlb_walk_cost .*refuted" "$FD/nophase.out"

# -- 4. boot-marker / save-state-load / zero-flip windows are refused, not
#    scored into either class ----------------------------------------------
python3 "$FD/gen.py" --dip 4 --good 4 --boot-at 2 --savestate-at 6 --zero-flip-at 8 > "$FD/refused.txt"
python3 "$FPSDIAG" analyze "$FD/refused.txt" --title "Grand Theft Auto III" > "$FD/refused.out" 2>&1
check "fpsdiag analyze: 3 of 8 windows refused, 5 scored" \
    grep -q "windows: 8 total, 5 scored, 3 refused" "$FD/refused.out"
check "fpsdiag analyze: boot/pipeline-warmup marker window is named as refused" \
    grep -q "boot/pipeline-warmup marker in window" "$FD/refused.out"
check "fpsdiag analyze: save-state load window is named as refused" \
    grep -q "save-state load in window" "$FD/refused.out"
check "fpsdiag analyze: zero flip advance (frozen) window is named as refused" \
    grep -q "zero flip advance (frozen/black)" "$FD/refused.out"
check "fpsdiag analyze: the refused boot-marker dip window is excluded from the dip count (3, not 4)" \
    grep -q "dip (< bar): 3 windows, good (>= bar): 2 windows" "$FD/refused.out"

# -- gaps: no-path lists every candidate; a real path lists only the ones
#    this fixture actually could not measure -------------------------------
python3 "$FPSDIAG" gaps > "$FD/gaps-nopath.out" 2>&1
check "fpsdiag gaps (no path): lists all 12 candidates by name, unconditionally" \
    test "$(grep -c 'needs: see FINDINGS.md' "$FD/gaps-nopath.out")" = "12"
python3 "$FPSDIAG" gaps "$FD/nophase.txt" --title "Grand Theft Auto III" > "$FD/gaps-nophase.out" 2>&1
check "fpsdiag gaps (nophase fixture): GAP-flags the phase-dependent candidates" \
    grep -q "gpu_saturation .*GAP: hakuX-phase absent" "$FD/gaps-nophase.out"
check "fpsdiag gaps (nophase fixture): does not GAP-flag the rdc-backed candidate still in reach" \
    bash -c '! grep -q "tlb_walk_cost .*GAP" "$1"' _ "$FD/gaps-nophase.out"

# -- 5. capture --attach (G5, fpsdata1018): every adb call it makes is a read,
#    never a launch/input/write, and it still produces a scoreable capture --
#    a fake `adb` on PATH stands in for the perflog build; no real device
#    touched by this fragment ------------------------------------------------
FAKEADB="$FD/fakeadb"
mkdir -p "$FAKEADB"
export FAKEADB_LOG="$FD/fakeadb-calls.log"
: > "$FAKEADB_LOG"
cat > "$FAKEADB/adb" <<'SH'
#!/bin/bash
echo "$*" >> "$FAKEADB_LOG"
case "$*" in
  *"logcat -d -v threadtime"*)
    printf '%s\n' \
      '10-18 21:24:09.001  5000  5001 I hakuX   : GPU: Adreno (TM) 740 Driver: PurpleVK' \
      '10-18 21:24:09.050  5000  5001 I hakuX-pace: f=60 max=16.8 ms=16.8'
    ;;
  *"logcat -v threadtime"*)
    echo '10-18 21:24:10.001  5000  5001 I hakuX-pace: f=60 max=16.8 ms=16.8'
    sleep 100
    ;;
  *"shell for z in /sys/class/thermal"*) echo 41000 ;;
  *"shell cat /sys/class/power_supply/battery/temp"*) echo 380 ;;
  *"shell cat /proc/meminfo"*) echo "MemTotal:        8000000 kB" ;;
  *"shell dumpsys power"*) echo "mWakefulness=Awake" ;;
  *"shell cat /sys/devices/system/cpu/online"*) echo "0-7" ;;
  *"shell top -b -n 1"*) echo "PID USER  PR  NI CMD" ;;
  *"shell cat /proc/"*"task"*"stat"*) echo "1234 (haku_x) S 1 1234 1234" ;;
  *) echo "UNEXPECTED: $*" >> "$FAKEADB_LOG.unexpected" ;;
esac
SH
chmod +x "$FAKEADB/adb"

CAPOUT="$FD/capture-out"
rm -rf "$CAPOUT" 2>/dev/null
PATH="$FAKEADB:$PATH" timeout 8 python3 "$FPSDIAG" capture --serial FAKESERIAL --title "Grand Theft Auto III" \
    --seconds 2 --out "$CAPOUT" --pid 1234 > "$FD/capture.out" 2>&1
capture_rc=$?
check "fpsdiag capture --attach: exits 0 against a fake perflog-build adb" test "$capture_rc" = "0"
check "fpsdiag capture --attach: manifest.json names the PurpleVK driver line" \
    grep -q "Driver: PurpleVK" "$CAPOUT/manifest.json"
check "fpsdiag capture --attach: periodic.ndjson gets at least 2 samples in a 2s capture" \
    test "$(wc -l < "$CAPOUT/samples/periodic.ndjson" 2>/dev/null)" -ge 2
check "fpsdiag capture --attach: logcat.txt is written (ring + follow)" \
    test -s "$CAPOUT/logcat.txt"
check "fpsdiag capture --attach: no adb call outside the read-only set (no launch/input/write)" \
    bash -c '! grep -qE "(^| )(input|monkey|am (start|force-stop)|pm |uninstall|install|push|reboot|settings put)( |$)" "$1"' _ "$FAKEADB_LOG"
check "fpsdiag capture --attach: the fake adb never saw an unrecognised call (every call matched the read-only case)" \
    test ! -s "$FAKEADB_LOG.unexpected"
