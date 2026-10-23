# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# A disc run boots the harness's disk, and a run on any other disk is refused by
# name (suitesha1022, #433).
#
# THE INCIDENT. From 10-19 every pgraph disc run on the Nova ended "ran but
# produced 0 captures" with `error: d98f15f: d98f15f not found` in run1.log. The
# app's `hddPath` pref named the owner's image (hdd-owner-1018.img); the guest
# wrote its PNGs there; run_disc.sh pulled .../x1box/hdd.img, matched its md5
# against the device's (a faithful copy of the wrong file) and the extractor
# looked for a directory that was never on it. The message read as a sha lookup,
# and the doctor blamed the host. The rule "every other run leaves hddPath on
# hdd.img" was a sentence in a comment; nothing made it so or checked it.
#
# THE FALSIFIER is S1. The device's prefs say hddPath=<the owner's image>; the
# fake app boots whatever its pref says, as the real one does, and writes its
# output dir into the disk it booted. Before the change nothing touches the pref:
# the guest boots the owner's image, hdd.img never gets the dir, and the request
# is a 0-capture result. S1 requires hddPath to read hdd.img while the guest is
# running, the owner's path (the prefs file, byte for byte) afterwards, and the
# owner's image unchanged.
#
# Legs:
#   run_disc.sh on its own (D1-D4): a log naming hdd.img passes; a log naming
#       another image is `WRONG HDD: guest wrote <path>, harness pulls <path>`,
#       exit 1, nothing pulled; a log naming no disk is `HDD UNKNOWN`, never a
#       pass; no capture at all is `HDD UNCHECKED` (direct callers only).
#   serve_one, as written, against the fake device (S1-S7):
#       S1 owner pref, app honours it -> hdd.img during, owner's after   (FALSIFIER)
#       S2 pref already hdd.img        -> no write, no marker
#       S3 pref moved, the app boots another image anyway -> WRONG HDD is the
#          request's ERROR, not "0 captures"; pref restored
#       S4 prefs unreadable (no run-as) -> the run goes on, the log check guards
#       S5 pref write refused          -> the run is refused, nothing launched
#       S6 a stale marker (a title run that died) -> restored first, then S1
#       S7 hddPath absent              -> set for the run, the key removed after
#   the extractor's not-found names the dir looked for and what the root holds;
#   the doctor knows the cause (wrong-hdd), with no model session.
#
# MUTANTS reinstate the weaker rule and each must turn a named leg red:
#   M1 a disc run trusts hddPath (disc_hdd_prepare never runs)        -> S1
#   M2 run_disc.sh believes whatever disk the log names               -> D2
#   M3 the dispatcher drops the verdict for the generic 0-capture ERROR -> S3
#   M4 hddPath is not put back after the run                          -> S1
#   M5 the extractor's not-found loses the roots it found             -> extractor
#   M6 the doctor has no wrong-hdd class                              -> doctor
#
# Everything stays under $T: the fake adb is on a PATH prepended here, the
# scratch image, the lease and the vsh ledger are set into $T (their defaults sit
# under the live $HOME/hakux-work and /tmp), and the fake adb ignores any command
# it does not know instead of handing it to a shell.

echo "== disc runs: hddPath is hdd.img for the run and the owner's after it; another disk is refused by name (suitesha1022)"

case "${T:-}" in
    /tmp/?*|"${TMPDIR:-/tmp}"/?*) ;;
    *) echo "99-disc-hdd: T='${T:-}' is not a scratch dir under /tmp; refusing to run, nothing removed" >&2
       fail=$((${fail:-0} + 1)); return 1 2>/dev/null || exit 1 ;;
esac

DX="$T/dischdd"; rm -rf "$DX"; mkdir -p "$DX/bin"
DXXD=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box
DXOWNER=$DXXD/hdd-owner-1018.img
DXWRONG="WRONG HDD: guest wrote $DXOWNER, harness pulls $DXXD/hdd.img"
dhd_gd() { echo "d$(echo "${1}1" | md5sum | cut -c1-6)"; }   # the dispatcher's own, run 1
DHD_NAMES=dgdir
for dhd_n in s1 s2 s3 s4 s5 s6 s7; do DHD_NAMES="$DHD_NAMES $(dhd_gd "1-$dhd_n")"; done

# ------------------------------------------------------------- two disk images
# good.img: a real qcow2 holding a real FATX volume (58-pull-verify.sh's layout)
# with one output dir per name, each holding t.png. other.img: a disk some
# earlier run wrote, with a dir of its own and none of the above.
python3 - "$DX" $DHD_NAMES <<'PY'
import struct, sys
out, names = sys.argv[1], sys.argv[2:]
CB = 16
E_OFF, E_SIZE = 0xABE80000, 0x1312D6000
SPC, BPC = 32, 32 * 512
fat_entries = E_SIZE // BPC + 1
fat_size = -(-fat_entries * 4 // 4096) * 4096
FAT = E_OFF + 4096
DATA = FAT + fat_size

def cl(n):
    return DATA + (n - 1) * BPC

def dirent(name, attr, first, size):
    e = bytearray(64)
    e[0] = len(name); e[1] = attr; e[2:2 + len(name)] = name.encode()
    struct.pack_into("<II", e, 44, first, size)
    return bytes(e)

def qcow2(path, writes):
    guest = {}
    for off, data in writes.items():
        for i, b in enumerate(data):
            c = (off + i) >> CB
            guest.setdefault(c, bytearray(1 << CB))[(off + i) & ((1 << CB) - 1)] = b
    l2_bits = CB - 3
    l1_size = -(-(E_OFF + E_SIZE) // (1 << (CB + l2_bits)))
    host = [bytearray(1 << CB), bytearray(1 << CB)]
    l2 = {}
    for c in sorted(guest):
        l1i = c >> l2_bits
        if l1i not in l2:
            l2[l1i] = len(host); host.append(bytearray(1 << CB))
            struct.pack_into(">Q", host[1], 8 * l1i, l2[l1i] << CB)
        struct.pack_into(">Q", host[l2[l1i]], 8 * (c & ((1 << l2_bits) - 1)), len(host) << CB)
        host.append(guest[c])
    struct.pack_into(">IIQIIQIIQ", host[0], 0, 0x514649FB, 2, 0, 0, CB, E_OFF + E_SIZE,
                     0, l1_size, 1 << CB)
    open(path, "wb").write(b"".join(host))

def image(path, dirs):
    png = b"\x89PNG\r\n\x1a\n" + bytes((i * 7) & 0xFF for i in range(6000 - 16)) + b"IEND\xaeB`\x82"
    writes = {E_OFF: struct.pack("<IIII", 0x58544146, 1, SPC, 1)}
    fat = {1: 0xFFFFFFFF}
    root = b""
    for i, d in enumerate(dirs):
        dc, fc = 2 + 2 * i, 3 + 2 * i
        fat[dc] = fat[fc] = 0xFFFFFFFF
        root += dirent(d, 0x10, dc, 0)
        writes[cl(dc)] = dirent("t.png", 0, fc, len(png))
        writes[cl(fc)] = png
    writes[cl(1)] = root
    for k, v in fat.items():
        writes[FAT + 4 * k] = struct.pack("<I", v)
    qcow2(path, writes)

image(out + "/good.img", names)
image(out + "/other.img", ["dOLDRUN"])
PY
check "the two fixture images were written" eval '[ -s "$DX/good.img" ] && [ -s "$DX/other.img" ]'

# ---------------------------------------------------------------- the fake adb
# The device is a directory, $DD_DEV: fs/ is files/x1box, prefs.xml the app's
# x1box_prefs.xml, flags are empty files. The fake app does what the real one
# does on the point under test: `am start` reads hddPath from prefs.xml NOW
# (that is "during the run"), boots that image unless a `boots` file says the
# app resolves another, writes its output dir into the disk it booted, and
# logs `Prefs hddPath=` and `HDD resolved:` the way xemu_android.cpp does.
#   no_run_as          run-as cat fails (a release package)
#   refuse_pref_write  the write is swallowed
#   nolog              the app logs no HDD line
cat > "$DX/bin/adb" <<'EOF'
#!/usr/bin/env bash
V="${DD_DEV:?}"
XD=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box
[ "${1:-}" = -s ] && shift 2
echo "$*" >> "$V/calls"
pref() { sed -n 's|.*<string name="hddPath">\(.*\)</string>.*|\1|p' "$V/prefs.xml" | head -1; }
file() { case "$1" in "$XD"/*) echo "$V/fs/${1#"$XD"/}" ;; *) echo "$V/nothing" ;; esac; }
case "${1:-}" in
    devices) printf 'List of devices attached\nbdc158a5\tdevice\nee317437\tdevice\n' ;;
    install) echo Success ;;
    pull)    f=$(file "$2"); [ -f "$f" ] || { echo "adb: error: failed to stat remote object '$2'" >&2; exit 1; }
             cp "$f" "$3" ;;
    logcat)  [ "${2:-}" = -c ] && exit 0
             n=0; while [ ! -e "$V/started" ] && [ "$n" -lt 600 ]; do sleep 0.1; n=$((n + 1)); done
             [ -e "$V/started" ] || exit 0
             if [ -e "$V/nolog" ]; then
                 echo '10-22 10:00:01.000 I/hakuX   ( 4242): frame 1'
             else
                 echo "10-22 10:00:01.000 I/hakuX   ( 4242): Prefs hddPath=$(cat "$V/run_pref")"
                 echo "10-22 10:00:01.001 I/hakuX   ( 4242): HDD resolved: $(cat "$V/booted")  size=764346368"
             fi
             exec sleep 120 ;;
    shell)   shift; c="$*"
             case "$c" in
                 *"cat > shared_prefs/x1box_prefs.xml"*)
                     if [ -e "$V/refuse_pref_write" ]; then cat >/dev/null; else cat > "$V/prefs.xml"; fi ;;
                 *"cat shared_prefs/x1box_prefs.xml"*)
                     if [ -e "$V/no_run_as" ]; then echo "run-as: package not debuggable: com.jreinach.hakux.debug" >&2; exit 1; fi
                     cat "$V/prefs.xml" ;;
                 "am start "*)
                     cur=$(pref); printf '%s' "$cur" > "$V/run_pref"; echo "$cur" >> "$V/run_pref.log"
                     if [ -e "$V/boots" ]; then b=$(cat "$V/boots"); elif [ -n "$cur" ]; then b=$cur; else b="$XD/hdd.img"; fi
                     printf '%s' "$b" > "$V/booted"
                     if [ "$b" = "$XD/hdd.img" ]; then cp "$V/good.img" "$V/fs/hdd.img"
                     else f=$(file "$b"); [ -f "$f" ] && echo "the guest wrote e:/d here" >> "$f"; fi
                     : > "$V/started"; echo 2 > "$V/ps_left" ;;
                 "am force-stop "*) rm -f "$V/started"; echo 0 > "$V/ps_left" ;;
                 "ps -A"*) n=$(cat "$V/ps_left" 2>/dev/null || echo 0)
                           if [ "$n" -gt 0 ]; then echo com.jreinach.hakux.debug:xemu; echo $((n - 1)) > "$V/ps_left"; fi ;;
                 "md5sum "*) p=${c#md5sum }; p=${p//\'/}; f=$(file "$p")
                           [ -f "$f" ] && echo "$(md5sum < "$f" | cut -d' ' -f1)  $p" ;;
             esac ;;
esac
exit 0
EOF
chmod +x "$DX/bin/adb"

dhd_prefs() {   # <value | -> -> an x1box_prefs.xml on stdout; "-" leaves hddPath out
    echo "<?xml version='1.0' encoding='utf-8' standalone='yes' ?>"
    echo '<map>'
    echo '    <boolean name="firstRun" value="false" />'
    [ "$1" = - ] || printf '    <string name="hddPath">%s</string>\n' "$1"
    echo '    <int name="fps" value="30" />'
    echo '</map>'
}
dhd_dev() {     # <pref value | -> : a fresh fake device; prefs.orig.xml is what must come back
    local V="$DX/dev"; rm -rf "$V"; mkdir -p "$V/fs"
    cp "$DX/good.img" "$V/good.img"; cp "$DX/other.img" "$V/fs/hdd.img"
    head -c 65536 /dev/urandom > "$V/fs/hdd-owner-1018.img"
    sha256sum "$V/fs/hdd-owner-1018.img" | cut -d' ' -f1 > "$V/owner.sha"
    dhd_prefs "$1" > "$V/prefs.xml"; cp "$V/prefs.xml" "$V/prefs.orig.xml"
}

# ------------------------------------------------- trees, runners and mutants
printf '%s\n' 'import sys' 'open(sys.argv[sys.argv.index("-o") + 1], "w").close()' > "$DX/make_test_iso.py"
cat > "$DX/score_sweep.py" <<'EOF'
import os, sys
a = sys.argv
out, tsv = a[a.index("--out") + 1], a[a.index("--tsv") + 1]
with open(tsv, "w") as fh:
    fh.write("suite\ttest\tsolo\tstatus\tdiffering\tmax_rgb\tmax_a\tpixels\toff_by_one\tapk_sha\tdisc_id\tlabel\n")
    for f in sorted(os.listdir(out)) if os.path.isdir(out) else []:
        if f.endswith(".png"):
            fh.write("S\t%s\tTrue\tok\t0\t0\t0\t100\t0\tsha\tdisc\tl\n" % f)
EOF
dhd_sub() {   # <file> <old> <new>: exactly one occurrence replaced, or exit 1
    python3 - "$@" <<'PY'
import sys
p, old, new = sys.argv[1:]
s = open(p).read()
if s.count(old) != 1:
    sys.exit(1)
open(p, "w").write(s.replace(old, new))
PY
}
dhd_tree() {  # <name> [<file> <old> <new>] -> a symlink tree of docs/testing on stdout; the file mutated
    local dir="$DX/tree-$1" x; rm -rf "$dir"; mkdir -p "$dir/jobs"
    for x in "$TESTING"/*; do [ "$(basename "$x")" = jobs ] || ln -s "$x" "$dir/$(basename "$x")"; done
    for x in "$TESTING"/jobs/*; do ln -s "$x" "$dir/jobs/$(basename "$x")"; done
    rm -f "$dir/make_test_iso.py" "$dir/score_sweep.py"
    cp "$DX/make_test_iso.py" "$DX/score_sweep.py" "$dir/"
    if [ -n "${2:-}" ]; then
        rm -f "$dir/$2"; cp "$TESTING/$2" "$dir/$2"
        dhd_sub "$dir/$2" "$3" "$4" || return 1
        chmod +x "$dir/$2"
    fi
    printf '%s\n' "$dir"
}
cat > "$DX/drive.sh" <<'EOF'
# drive.sh <tree> <dispatch-dir> <request-id>: one serve_one, as written
export DISPATCH_DIR="$2" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO" BATTERY_ADMIT=off
. "$1/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
build_ref() { echo "$DHD_APK"; }
serve_one "$2/queue/$3.req"
EOF
echo one > "$DX/apk"; : > "$DX/base.iso"; : > "$DX/disc.iso"
dhd_env() {   # the environment every fake-device run shares; the scratch paths all sit in $DX
    env PATH="$DX/bin:$PATH" DD_DEV="$DX/dev" HAKUX_HDD_SCRATCH="$DX/hdd-scratch.img" \
    HAKUX_DEVICE_LEASE="$DX/lease" VSH_LOG_LEDGER="$DX/vsh-ledger" ADB_RETRY_SLEEP=0 \
    ADB_INSTALL_TIMEOUT=5 ADB_QUICK_TIMEOUT=5 APPEAR_TIMEOUT=10 HDD_LINE_WAIT=5 MISSES_TO_EXIT=1 \
    DHD_APK="$DX/apk" REPO="$REPO" "$@"
}

dhd_setup_s1() { dhd_dev "$DXOWNER"; }
dhd_setup_s2() { dhd_dev "$DXXD/hdd.img"; }
dhd_setup_s3() { dhd_dev "$DXOWNER"; printf '%s' "$DXOWNER" > "$DD_V/boots"; }
dhd_setup_s4() { dhd_dev "$DXOWNER"; : > "$DD_V/no_run_as"; }
dhd_setup_s5() { dhd_dev "$DXOWNER"; : > "$DD_V/refuse_pref_write"; }
dhd_setup_s6() { dhd_dev "$DXOWNER"; dhd_prefs "$DXXD/titles.qcow2" > "$DD_V/prefs.xml"
                 printf '%s' "$DXOWNER" > "$DD_D/.hdd_pref.nova"; }
dhd_setup_s7() { dhd_dev -; }
dhd_go() {    # <scenario> <tree> [<tag>] -> serve_one on the fake device; DD_V, DD_D, DD_R say where
    local s=$1 tree=$2 id="1-$1"
    DD_V="$DX/dev"; DD_D="$DX/d-$s-${3:-real}"; DD_R="$DD_D/results/$id"
    rm -rf "$DD_D"; mkdir -p "$DD_D"/{queue,running,results,logs,lanes}
    "dhd_setup_$s"
    printf '%s\n' '{"requester":"selftest","purpose":"disc hdd","ref":"HEAD","suites":["S"],"base_iso":"'"$DX/base.iso"'"}' \
        > "$DD_D/queue/$id.req"
    dhd_env timeout -k 2 90 bash "$DX/drive.sh" "$tree" "$DD_D" "$id" > "$DD_D/drive.out" 2>&1
}
dhd_direct() {   # <tree> <yes|no: a CAPTURE_LOG> -> DD_OUT, DD_RC: run_disc.sh alone, on the device in $DX/dev
    local cap=""; [ "$2" = yes ] && cap="$DX/cap.log"
    rm -rf "$DX/res" "$DX/cap.log" "$DX/hdd-scratch.img"
    DD_V="$DX/dev"
    DD_OUT=$(dhd_env SERIAL=ee317437 DEVICE_LABEL=nova DEVISO=/x/fast.iso CAPTURE_LOG="$cap" \
        timeout 60 bash "$1/run_disc.sh" "$DX/disc.iso" dgdir "$DX/res" 30 2>&1); DD_RC=$?
}
dhd_doc() {   # <tree> <dispatch_doctor.sh args...>
    ( export PATH="$DX/bin:$PATH" DD_DEV="$DX/dev" DISPATCH_DIR="$DX/dd" SERIAL=ee317437 \
             DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO" BATTERY_ADMIT=off ADB_RETRY_SLEEP=0 ADB_QUICK_TIMEOUT=5
      bash "$1/dispatch_doctor.sh" "${@:2}" 2>/dev/null )
}

# ---------------------------------------------------------------- predicates
# One property each, read from DD_V (the device), DD_D (the dispatch dir), DD_R
# (the result dir) or DD_OUT, so a leg and the mutant that must break it ask the
# very same question.
dhd_p_on_hdd()    { [ "$(cat "$DD_V/run_pref" 2>/dev/null)" = "$DXXD/hdd.img" ] && [ "$(wc -l < "$DD_V/run_pref.log")" = 1 ]; }
dhd_p_pref_back() { cmp -s "$DD_V/prefs.xml" "$DD_V/prefs.orig.xml"; }
dhd_p_no_marker() { [ ! -e "$DD_D/.hdd_pref.nova" ]; }
dhd_p_owner_img() { [ "$(sha256sum "$DD_V/fs/hdd-owner-1018.img" | cut -d' ' -f1)" = "$(cat "$DD_V/owner.sha")" ]; }
dhd_p_untouched() { dhd_p_owner_img && ! grep -q hdd-owner "$DD_V/calls"; }
dhd_p_verdict()   { [ "$(head -1 "$DD_R/ERROR" 2>/dev/null)" = "$DXWRONG" ]; }
dhd_p_done()      { [ -e "$DD_R/DONE" ] && [ ! -e "$DD_R/ERROR" ] && [ -s "$DD_R/captures1/t.png" ]; }
dhd_p_direct_wrong() { [ "$DD_RC" = 1 ] && grep -qx "$DXWRONG" <<<"$DD_OUT"; }
dhd_j()           { python3 -c 'import json, sys
d = json.load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d = (d or {}).get(k)
print(d)' "$1" "$2" 2>/dev/null; }
dhd_p_disc()      { [ "$(dhd_j "$DD_R/hdd_disc.json" action)" = "$1" ]; }
dhd_p_extract()   { local o; o=$(python3 "$1/extract_results.py" "$DX/other.img" -d dMISSING -o "$DX/xo" 2>&1)
                    grep -q "looked for 'dMISSING'" <<<"$o" && grep -q "dOLDRUN" <<<"$o"; }
dhd_p_classes()   { local e r n=0
                    for e in "$DXWRONG" "HDD UNKNOWN: $DX/cap.log has no 'HDD resolved:' line" \
                             "could not point hddPath at hdd.img for this disc run (it names $DXOWNER); a disc must not run on another image; see dispatcher.log"; do
                        rm -rf "$DX/rd"; mkdir -p "$DX/rd"; printf '%s\n' "$e" > "$DX/rd/ERROR"
                        r=$(dhd_doc "$1" classify "$DX/rd"); [ "$r" = wrong-hdd ] && n=$((n + 1))
                    done
                    [ "$n" = 3 ]; }
dhd_p_wiring()    { python3 - "$TESTING/dispatcher.sh" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
body = s[s.index("\nserve_one() {"):]
def first(pat):
    m = re.search(pat, body, re.M)
    return m.start() if m else -1
g = first(r'^    hdd_img_guard "\$rdir"$')
p = first(r'^    if ! disc_hdd_prepare "\$rdir"; then$')
a = first(r'^    disc_hdd_after "\$rdir"$')
w = first(r'^    REQ_ENV_JSON=')
runs = [m.start() for m in re.finditer(r'bash "\$HERE/run_disc\.sh"', body) if p < m.start() < a]
sys.exit(0 if -1 < g < p < a < w and runs else 1)
PY
}

# ------------------------------------------------- the extractor's not-found
echo "-- the extractor says where it looked"
check "extract: a dir the image lacks is named, with the root dirs the image does hold" dhd_p_extract "$TESTING"

# ------------------------------------------------------ run_disc.sh on its own
echo "-- run_disc.sh: the disk the guest wrote is read from its log, not assumed"
dhd_dev "$DXXD/hdd.img"; dhd_direct "$TESTING" yes
check "D1: a log naming hdd.img passes: exit 0, t.png extracted, and the run says what it checked" \
    eval '[ "$DD_RC" = 0 ] && [ -s "$DX/res/t.png" ] && grep -q "^hdd: the guest.s log says it booted $DXXD/hdd.img" <<<"$DD_OUT"'
dhd_dev "$DXOWNER"; dhd_direct "$TESTING" yes
check "D2: a log naming the owner's image is the WRONG HDD verdict, naming both disks, exit 1" dhd_p_direct_wrong
check "D2: ... and it is not the extractor's message" eval '! grep -q "not found" <<<"$DD_OUT"'
check "D2: ... nothing was pulled and nothing extracted" eval '! grep -q "^pull " "$DD_V/calls" && [ ! -e "$DX/res" ]'
dhd_dev "$DXXD/hdd.img"; : > "$DX/dev/nolog"; dhd_direct "$TESTING" yes
check "D3: a log with no HDD line is HDD UNKNOWN, exit 1, nothing pulled -- never a pass" \
    eval '[ "$DD_RC" = 1 ] && grep -q "^HDD UNKNOWN: " <<<"$DD_OUT" && ! grep -q "^pull " "$DD_V/calls"'
dhd_dev "$DXXD/hdd.img"; dhd_direct "$TESTING" no
check "D4: no CAPTURE_LOG (a direct caller) is HDD UNCHECKED and goes on to pull" \
    eval '[ "$DD_RC" = 0 ] && grep -q "^HDD UNCHECKED: " <<<"$DD_OUT" && [ -s "$DX/res/t.png" ]'

# ---------------------------------------------------- serve_one, as written
echo "-- serve_one: a disc run puts hddPath on hdd.img and puts it back"
DHD_TREE=$(dhd_tree real) || DHD_TREE=""
if [ -z "$DHD_TREE" ]; then
    bad "could not build the serve tree"
else
    dhd_go s1 "$DHD_TREE"
    check "S1 (FALSIFIER): hddPath read hdd.img when the guest started, though it named the owner's image on arrival" dhd_p_on_hdd
    check "S1: and the guest's own log agrees (Prefs hddPath= and HDD resolved: both hdd.img)" \
        eval 'grep -q "Prefs hddPath=$DXXD/hdd.img\$" "$DD_R/logcat1.txt" && grep -q "HDD resolved: $DXXD/hdd.img  " "$DD_R/logcat1.txt"'
    check "S1: afterwards hddPath is the owner's again: the prefs file is byte for byte what it was" dhd_p_pref_back
    check "S1: the marker is gone" dhd_p_no_marker
    check "S1: the owner's image is byte for byte unchanged, and no adb call so much as named it" dhd_p_untouched
    check "S1: the run scored: DONE, no ERROR, t.png extracted" dhd_p_done
    check "S1: hdd_disc.json says set / was the owner's / restored" \
        eval '[ "$(dhd_j "$DD_R/hdd_disc.json" action)" = set ] && [ "$(dhd_j "$DD_R/hdd_disc.json" was)" = "$DXOWNER" ] && [ "$(dhd_j "$DD_R/hdd_disc.json" restored)" = True ]'
    check "S1: result.json carries it (hdd_disc.action)" eval '[ "$(dhd_j "$DD_R/result.json" hdd_disc.action)" = set ]'

    dhd_go s2 "$DHD_TREE"
    check "S2: a pref already on hdd.img is read and not written (no write call, no marker)" \
        eval '! grep -q "cat > shared_prefs" "$DD_V/calls" && [ ! -e "$DD_D/.hdd_pref.nova" ]'
    check "S2: action=kept, prefs untouched, the run scored" eval 'dhd_p_disc kept && dhd_p_pref_back && dhd_p_on_hdd && dhd_p_done'

    dhd_go s3 "$DHD_TREE"
    check "S3: the app resolves another image whatever the pref: ERROR's first line is the WRONG HDD verdict" dhd_p_verdict
    check "S3: ... not the 0-capture result" eval '! grep -q "produced 0 captures" "$DD_R/ERROR"'
    check "S3: ... and run1.log carries the same verdict" eval 'grep -qx "$DXWRONG" "$DD_R/run1.log"'
    check "S3: nothing was pulled (the guest was stopped, not left to write)" eval '! grep -q "^pull " "$DD_V/calls"'
    check "S3: the doctor named the cause with no model session (doctor.md wrong-hdd, ERROR says so, no TSV row)" \
        eval 'head -1 "$DD_R/doctor.md" | grep -q "^wrong-hdd:" && tail -1 "$DD_R/ERROR" | grep -q "^doctor: give-up: the disc ran on a different disk.*(see doctor.md)\$" && [ ! -e "$DD_D/logs/dispatch-doctor.tsv" ]'
    check "S3: hddPath is put back though the run failed" eval 'dhd_p_pref_back && dhd_p_no_marker'

    dhd_go s4 "$DHD_TREE"
    check "S4: prefs unreadable: the pref is not written, action=unread, the run goes on" \
        eval 'dhd_p_disc unread && ! grep -q "cat > shared_prefs" "$DD_V/calls" && grep -q "^shell am start" "$DD_V/calls"'
    check "S4: ... and the log check catches the owner's image: the same WRONG HDD verdict" dhd_p_verdict

    dhd_go s5 "$DHD_TREE"
    check "S5: a pref that cannot be moved refuses the run, naming the image it names" \
        eval 'head -1 "$DD_R/ERROR" | grep -qF "could not point hddPath at hdd.img for this disc run (it names $DXOWNER)"'
    check "S5: no guest was launched" eval '! grep -q "^shell am start" "$DD_V/calls"'
    check "S5: hddPath is still the owner's, byte for byte, and no marker is left" eval 'dhd_p_pref_back && dhd_p_no_marker && dhd_p_untouched'
    check "S5: the doctor knows it (wrong-hdd) without a session" eval 'head -1 "$DD_R/doctor.md" | grep -q "^wrong-hdd:"'

    dhd_go s6 "$DHD_TREE"
    check "S6: a marker left by a died title run is restored first; the disc then runs on hdd.img" dhd_p_on_hdd
    check "S6: ... and the owner's path, not the titles disk, is what comes back; marker gone" \
        eval 'dhd_p_pref_back && dhd_p_no_marker && dhd_p_untouched && dhd_p_done'

    dhd_go s7 "$DHD_TREE"
    check "S7: no hddPath at all: set for the run, then the key is removed again, byte for byte" \
        eval 'dhd_p_on_hdd && dhd_p_pref_back && dhd_p_no_marker && dhd_p_done && dhd_p_disc set'
fi
check "serve_one order: hdd_img_guard, disc_hdd_prepare, run_disc.sh, disc_hdd_after, then the result" dhd_p_wiring

# ---------------------------------------------------------------- the doctor
echo "-- the doctor knows the cause"
dhd_dev "$DXOWNER"
check "doctor: WRONG HDD, HDD UNKNOWN and 'could not point hddPath' each classify as wrong-hdd" dhd_p_classes "$TESTING"
rm -rf "$DX/dd" "$DX/rd"; mkdir -p "$DX/rd"; printf '%s\n' "$DXWRONG" > "$DX/rd/ERROR"
DHD_V=$(dhd_doc "$TESTING" diagnose 1-x "$DX/rd")
check "doctor: diagnose gives a give-up verdict that names the disk, and writes doctor.md" \
    eval 'grep -q "^VERDICT give-up: the disc ran on a different disk .*WRONG HDD" <<<"$DHD_V" && head -1 "$DX/rd/doctor.md" | grep -q "^wrong-hdd:"'
check "doctor: ... with no cap slot used (no TSV row), only a lesson" \
    eval '[ ! -s "$DX/dd/logs/dispatch-doctor.tsv" ] && grep -q "wrong-hdd" "$DX/dd/doctor-lessons.md"'
rm -rf "$DX/rd"; mkdir -p "$DX/rd"; printf '%s\n' "ran but produced 0 captures; see run1.log and captures1/" > "$DX/rd/ERROR"
check "doctor control: the generic 0-capture ERROR is still its own class (zero-captures)" \
    eval '[ "$(dhd_doc "$TESTING" classify "$DX/rd")" = zero-captures ]'

# ------------------------------------------------------------------ mutants
echo "-- mutants: each weaker rule must turn a named leg red"
dhd_mutant() {   # <label> <file> <old> <new> <predicate run on the result: it must FAIL> <how to run: s1|s3|d2|extract|doc>
    local label=$1 file=$2 old=$3 new=$4 pred=$5 how=$6 tree
    tree=$(dhd_tree "m-$how" "$file" "$old" "$new") || { bad "mutant '$label': its anchor no longer matches exactly once in $file"; return; }
    case "$how" in
        s1|s3) dhd_go "$how" "$tree" mut ;;
        d2)    dhd_dev "$DXOWNER"; dhd_direct "$tree" yes ;;
        doc)   dhd_dev "$DXOWNER" ;;
    esac
    # red because the run finished and the property is gone -- not because the run fell over
    case "$how" in
        s1|s3) [ -e "$DD_R/DONE" ] || [ -e "$DD_R/ERROR" ] || { bad "mutant '$label': the request neither finished nor failed (see $DD_D/drive.out)"; return; } ;;
        d2)    [ -n "$DD_OUT" ] || { bad "mutant '$label': run_disc.sh printed nothing"; return; } ;;
    esac
    if "$pred" "$tree"; then bad "mutant '$label' passes the leg that should catch it ($pred)"
    else ok "mutant '$label' is red on $pred"; fi
}
dhd_mutant "M1 a disc run trusts hddPath" dispatcher.sh \
    '    if ! disc_hdd_prepare "$rdir"; then' '    if false; then' dhd_p_on_hdd s1
dhd_mutant "M4 hddPath is not put back after the run" dispatcher.sh \
    '    restore_hdd_pref || { ok=false;' '    true || { ok=false;' dhd_p_pref_back s1
dhd_mutant "M3 the dispatcher reports 0 captures, not the disk" dispatcher.sh \
    '    if [ -n "$hdd_bad" ]; then' '    if false; then' dhd_p_verdict s3
dhd_mutant "M2 run_disc.sh believes any disk the log names" run_disc.sh \
    '        if [ "$b" != "$DEVHDD" ]; then' '        if false; then' dhd_p_direct_wrong d2
dhd_mutant "M5 the extractor does not say what the root holds" extract_results.py \
    ' and it holds {self._holds(cluster)}")' '")' dhd_p_extract extract
dhd_mutant "M6 the doctor has no wrong-hdd class" dispatch_doctor.sh \
    '"WRONG HDD:"*|"HDD UNKNOWN:"*|*"could not point hddPath at hdd.img"*)' '"NO SUCH HDD:"*)' dhd_p_classes doc
