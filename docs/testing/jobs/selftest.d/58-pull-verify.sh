# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# run_disc.sh: a pulled image is checked against the device's, and a file the
# image cannot give in full is named SHORT.
#
# On 09-25 two arms scored 56 and 51 W_param PNGs that were each exactly
# 16384 bytes, one FATX cluster, from guests that had exited cleanly. The
# image is qcow2, so a truncated pull cannot do that (the extractor raises
# "short read"). A hole can: one 4 KB write missing from the host's copy
# zeroes a page of the FAT, and every chain through that page ends after its
# first cluster. That is the damage these fixtures carry. They carry it in a
# real qcow2 holding a real FATX volume, so the extractor under test reads
# real bytes.
#
# THE FALSIFIER is case (a). A damaged pull, then a good one, then a damaged
# one again: the good pull sits in the middle. Before this change run_disc.sh
# pulls once, extracts the damaged image, exits 0, and scores a 16384-byte
# t.png. Case (a) goes red there on pulls=1 and png=16384, not on a message.
#
# Cases, each a device image, the images its pulls return in order, and
# whether the device answers md5sum:
#   (a) good; hole, good, hole; md5  -> 2 pulls, the good one extracted
#   (b) good; hole x3;          md5  -> 3 pulls, exit 1, nothing extracted
#   (c) good; hole, good;       none -> the SHORT count forces a second pull
#   (d) hole; hole;             md5  -> the device's own image: 1 pull, SHORT
#   (e) good; good;             md5  -> 1 pull, clean
# The mutants run here too, against copies in a scratch dir; the real files
# are never edited.

echo "== run_disc: the pull is checked against the device; SHORT files are named"

PV="$T/pullverify"; mkdir -p "$PV/bin"

python3 - "$PV" <<'PY'
import struct, sys
out = sys.argv[1]
CB = 16                                   # qcow2 cluster bits: 64 KiB
E_OFF, E_SIZE = 0xABE80000, 0x1312D6000   # extract_results.PARTITIONS["E"], literal
SPC, BPC = 32, 32 * 512                   # FATX: 16 KiB clusters
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

png = b"\x89PNG\r\n\x1a\n" + bytes((i * 7) & 0xFF for i in range(40000 - 16)) + b"IEND\xaeB`\x82"
assert len(png) == 40000
writes = {E_OFF: struct.pack("<IIII", 0x58544146, 1, SPC, 1)}
fat = {1: 0xFFFFFFFF, 2: 0xFFFFFFFF, 3: 4, 4: 5, 5: 0xFFFFFFFF, 6: 0xFFFFFFFF}
for i, v in fat.items():
    writes[FAT + 4 * i] = struct.pack("<I", v)
writes[cl(1)] = dirent("nxdk_pgraph_tests", 0x10, 2, 0)
writes[cl(2)] = dirent("t.png", 0, 3, len(png)) + dirent("one.txt", 0, 6, 10)
writes[cl(3)] = png
writes[cl(6)] = b"0123456789"

def qcow2(path, writes):
    guest = {}
    for off, data in writes.items():
        for i, b in enumerate(data):
            c = (off + i) >> CB
            guest.setdefault(c, bytearray(1 << CB))[(off + i) & ((1 << CB) - 1)] = b
    l2_bits = CB - 3
    l1_size = -(-(E_OFF + E_SIZE) // (1 << (CB + l2_bits)))
    host = [bytearray(1 << CB), bytearray(1 << CB)]     # header, L1
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

qcow2(out + "/good.img", writes)
# The hole: the 4 KB page of the FAT holding entries 0..1023 never landed.
hole = dict(writes)
for i in fat:
    hole[FAT + 4 * i] = b"\0\0\0\0"
qcow2(out + "/hole.img", hole)
PY
check "the fixture images were written" eval '[ -s "$PV/good.img" ] && [ -s "$PV/hole.img" ]'

# The extractor on its own, the real one.
pv_extract() { python3 "$TESTING/extract_results.py" "$PV/$1.img" -o "$PV/x-$1" 2>&1 | tail -1; }
PVX_GOOD=$(pv_extract good); PVX_HOLE=$(pv_extract hole)
check "extract: the good image gives t.png whole, 40000 bytes" \
      eval '[ "$(stat -c %s "$PV/x-good/t.png" 2>/dev/null)" = 40000 ]'
check "  ... and its summary names no SHORT file" eval 'case "$PVX_GOOD" in *SHORT*) false ;; "extracted 2 files"*) ;; *) false ;; esac'
check "extract: the holed image gives t.png as one cluster, 16384 bytes" \
      eval '[ "$(stat -c %s "$PV/x-hole/t.png" 2>/dev/null)" = 16384 ]'
check "  ... and its summary says 1 SHORT, first t.png" \
      grep -q "; 1 SHORT: the cluster chain ended before the size the directory records (first: t.png)$" <<<"$PVX_HOLE"
check "  ... while one.txt, a one-cluster file, is whole" \
      eval '[ "$(cat "$PV/x-hole/one.txt")" = 0123456789 ]'

# The fake adb: the guest shows for one poll; md5sum answers for the device's
# image unless $PV/c/nomd5 exists; each pull returns the next image in
# $PV/c/seq and logs it.
cat > "$PV/bin/adb" <<'EOF'
#!/usr/bin/env bash
C="$PV/c"
case "$*" in
    *"ps -A"*) [ -e "$C/seen" ] || { : > "$C/seen"; echo "com.jreinach.hakux.debug:xemu"; } ;;
    *md5sum*) [ -e "$C/nomd5" ] || echo "$(md5sum < "$PV/$(cat "$C/device").img" | cut -d' ' -f1)  /storage/emulated/0/x/hdd.img" ;;
    *" pull "*) n=$(( $(wc -l < "$C/pulls") + 1 ))
                img=$(sed -n "${n}p" "$C/seq"); [ -n "$img" ] || img=$(tail -1 "$C/seq")
                cp "$PV/$img.img" "${@: -1}"; echo "$img" >> "$C/pulls" ;;
esac
exit 0
EOF
chmod +x "$PV/bin/adb"; : > "$PV/disc.iso"

pv_case() {   # <scripts dir> <case> <device image> <md5|none> <pull images...> -> one line
    local dir=$1 name=$2 dev=$3 md5=$4; shift 4
    rm -rf "$PV/c"; mkdir -p "$PV/c"; : > "$PV/c/pulls"
    echo "$dev" > "$PV/c/device"; printf '%s\n' "$@" > "$PV/c/seq"
    [ "$md5" = none ] && : > "$PV/c/nomd5"
    ( PV="$PV" PATH="$PV/bin:$PATH" SERIAL=fake DEVICE_LABEL=fake \
      HAKUX_HDD_SCRATCH="$PV/c/hdd.img" HAKUX_DEVICE_LEASE="$PV/c/lease" \
      DEVISO=/x/fast.iso MISSES_TO_EXIT=1 ADB_RETRY_SLEEP=0 \
      timeout 60 bash "$dir/run_disc.sh" "$PV/disc.iso" nxdk_pgraph_tests "$PV/c/res" 30 \
      > "$PV/c/log" 2>&1; echo $? > "$PV/c/rc" )
    local w="" png
    png=$(stat -c %s "$PV/c/res/t.png" 2>/dev/null || echo -)
    grep -q "md5 matches the device's image" "$PV/c/log" && w="$w MATCH"
    grep -q "is not the device's" "$PV/c/log" && w="$w NOTDEV"
    grep -q "none matched the device's image" "$PV/c/log" && w="$w NONE"
    grep -q " SHORT: " "$PV/c/log" && w="$w SHORT"
    grep -q "NOT VERIFIED" "$PV/c/log" && w="$w UNVER"
    grep -q "image on the device is itself" "$PV/c/log" && w="$w ONDEV"
    echo "$name rc=$(cat "$PV/c/rc") pulls=$(wc -l < "$PV/c/pulls") png=$png$w"
}
pv_all() {    # <scripts dir> -> every case, one line each
    pv_case "$1" a good md5  hole good hole
    pv_case "$1" b good md5  hole hole hole
    pv_case "$1" c good none hole good
    pv_case "$1" d hole md5  hole
    pv_case "$1" e good md5  good
}
WANT="a rc=0 pulls=2 png=40000 MATCH NOTDEV
b rc=1 pulls=3 png=- NOTDEV NONE
c rc=0 pulls=2 png=40000 SHORT UNVER
d rc=0 pulls=1 png=16384 MATCH SHORT ONDEV
e rc=0 pulls=1 png=40000 MATCH"
GOT=$(pv_all "$TESTING")
pv_is() { [ "$(grep "^$1 " <<<"$GOT")" = "$(grep "^$1 " <<<"$WANT")" ]; }
pv_leg() { if pv_is "$1"; then ok "$2"; else bad "$2 -- got: $(grep "^$1 " <<<"$GOT")"; fi; }
pv_leg a "(a) a holed pull is refused by md5; the good pull in the middle is extracted whole"
pv_leg b "(b) three pulls that never match: exit 1, nothing extracted, and it says so"
pv_leg c "(c) no device md5: the SHORT count forces a second pull, which is whole"
pv_leg d "(d) a pull matching a holed device image: 1 pull, SHORT named, blamed on the device"
pv_leg e "(e) a clean pull: 1 pull, verified"

# ------------------------------------------------------------------ mutants
pv_mutant() {   # <label> <file> <exact line> <replacement> <case that must go wrong>
    local md="$PV/mut"; rm -rf "$md"; mkdir -p "$md"
    cp "$TESTING/run_disc.sh" "$TESTING/devices.sh" "$TESTING/extract_results.py" "$md/"
    python3 - "$md/$2" "$3" "$4" <<'PY' || { bad "mutant: its anchor no longer matches $2"; return; }
import sys
p, old, new = sys.argv[1:]
s = open(p).read()
if s.count(old) != 1:
    sys.exit(1)
open(p, "w").write(s.replace(old, new))
PY
    local mg; mg=$(pv_all "$md")
    if [ "$mg" = "$WANT" ]; then bad "mutant '$1' passes every case (the fragment cannot see it)"
    elif [ "$(grep "^$5 " <<<"$mg")" != "$(grep "^$5 " <<<"$WANT")" ]; then ok "mutant '$1' is red on ($5)"
    else bad "mutant '$1' is red, but not on ($5): $(tr '\n' ';' <<<"$mg")"; fi
}
pv_mutant "the md5 is never compared" run_disc.sh \
    '    if [ -n "$DEV_MD5" ]; then' '    if false; then' b
pv_mutant "SHORT never forces a second pull" run_disc.sh \
    '    [ "$pull_try" -lt "$PULL_TRIES" ] || break' '    break' c
pv_mutant "the extractor does not measure the chain" extract_results.py \
    '        if len(data) < size and short is not None:' '        if False:' d
