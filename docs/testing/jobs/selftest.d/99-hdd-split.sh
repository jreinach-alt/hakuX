# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# The titles disk / nxdk disk split (lane.hddsplit, #397). A title run must
# boot files/x1box/titles.qcow2, built on the host from the save store, and
# every other run hdd.img; and neither disk may grow without bound.
#
# A fake adb serves one fake device: its files/x1box is a directory, its
# x1box_prefs.xml a file, and shell commands on paths run on the host with the
# device path mapped into that directory. The dispatcher's own functions are
# called, sourced from dispatcher.sh; nothing here re-implements them.
#
# THE FALSIFIERS: against master (no split) titles_disk_prepare does not
# exist, the prefs keep hddPath on hdd.img, and the first legs go red on the
# written pref and the pushed disk's sha, not on a missing file. The
# harvest-error leg is the impossible row for plan(): a disk whose saves did
# not all come off must be kept, however stale the store says it is.

echo "== hdd split: a title run boots the titles disk; hdd.img stays the discs'"
HS="$T/hddsplit"; rm -rf "$HS"; mkdir -p "$HS/bin" "$HS/dev/fs" "$HS/dispatch" "$HS/fix"
X=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box
cat > "$HS/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
echo "$*" >> "$HS_DEV/calls"
X=/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box
map() { printf '%s' "${1//$X/$HS_DEV/fs}"; }
case "$1" in
    push) cp "$2" "$(map "$3")" && chmod 644 "$(map "$3")" ;;   # adb push: the shell's umask
    pull) cp "$(map "$2")" "$3" ;;
    shell) shift; c="$*"
        case "$c" in
            "am force-stop"*) ;;
            "chmod "*)   # nochmod: the device refuses the mode change
                [ -f "$HS_DEV/nochmod" ] && exit 1
                sh -c "$(map "$c")" ;;
            *"cat > shared_prefs/x1box_prefs.xml"*) cat > "$HS_DEV/prefs.xml"
                [ -f "$HS_DEV/drop_readback" ] && touch "$HS_DEV/drop_next" ;;
            *"cat shared_prefs/x1box_prefs.xml"*)   # drop_readback: the write lands, its read-back is lost
                if [ -f "$HS_DEV/drop_next" ]; then rm -f "$HS_DEV/drop_next"; else cat "$HS_DEV/prefs.xml"; fi ;;
            "cp -f "*)   # nospace: the on-device backup runs out of room part way
                if [ -f "$HS_DEV/nospace" ]; then
                    set -- $(map "$c" | tr -d "'"); head -c 100 "$3" > "$4"; exit 1
                fi
                sh -c "$(map "$c")" ;;
            *) sh -c "$(map "$c")" ;;
        esac ;;
esac
EOF
chmod +x "$HS/bin/adb"
cat > "$HS/dev/prefs.xml" <<EOF
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <boolean name="setup_complete" value="true" />
    <string name="hddPath">$X/hdd.img</string>
    <string name="mcpxPath">$X/mcpx.bin</string>
</map>
EOF
cp "$HS/dev/prefs.xml" "$HS/prefs.orig.xml"

# Fixture saves, and a device hdd.img carrying two of them (what pass 1 left).
python3 - "$TESTING/titles" "$HS/fix" <<'PY'
import hashlib, json, os, sys
sys.path.insert(0, sys.argv[1]); import saves
out = sys.argv[2]
def mk(tid, payload):
    d = os.path.join(out, tid); t = saves.fatx_now()
    ents = [{"path": f"UDATA/{tid}", "dir": True, "times": t},
            {"path": f"UDATA/{tid}/ABCDEF012345", "dir": True, "times": t}]
    for name, data in (("TitleMeta.xbx", tid.encode() * 8), ("ABCDEF012345/SaveMeta.xbx", payload)):
        p = os.path.join(d, "UDATA", tid, *name.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True); open(p, "wb").write(data)
        ents.append({"path": f"UDATA/{tid}/{name}", "dir": False, "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest(), "times": t})
    m = {"title_id": tid, "entries": ents}; m["save_id"] = saves.save_id(m)
    json.dump(m, open(os.path.join(d, "save.json"), "w"))
for tid, p in (("4D530021", b"crimson" * 300), ("4541005B", b"burnout" * 900), ("4D530053", b"ghoulies" * 50)):
    mk(tid, p)
saves.build(os.path.join(out, "hdd.img"), [os.path.join(out, t) for t in ("4D530021", "4541005B")])
saves.build(os.path.join(out, "played.qcow2"), [os.path.join(out, t) for t in ("4D530021", "4541005B", "4D530053")])
PY
cp "$HS/fix/hdd.img" "$HS/dev/fs/hdd.img"; chmod 660 "$HS/dev/fs/hdd.img"   # as the app made it
check "fixtures: a device hdd.img with two titles' saves" test -s "$HS/dev/fs/hdd.img"

# Run a shell snippet inside a sourced dispatcher.sh against the fake device.
hs_env() {
    ( export DISPATCH_DIR="$HS/dispatch" TITLESTATE_DIR="$HS/dispatch/titlestate" \
             SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO" \
             MAKE_XBOX_HDD="$REPO/tools/make_xbox_hdd.py" HS_DEV="$HS/dev" \
             ADB_RETRY_SLEEP=0 PATH="$HS/bin:$PATH"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}
pref() { sed -n 's:.*<string name="hddPath">\(.*\)</string>.*:\1:p' "$HS/dev/prefs.xml"; }
reg() {   # <python expr over st> -> value from the nova registry
    python3 -c 'import json,sys; st=json.load(open(sys.argv[1])); print(eval(sys.argv[2]))' \
        "$HS/dispatch/titlestate/devices/nova.json" "$1"
}
verify_on() {   # <image> <tid...>: every named save verifies on the image
    local img="$1"; shift
    for t in "$@"; do
        python3 "$TESTING/titles/saves.py" verify "$img" \
            "$HS/dispatch/titlestate/saves/$t/$(reg "st['titles']['$t']['save']")" >/dev/null 2>&1 || return 1
    done
}

# ------------------------------------------------------------ first title run
mkdir -p "$HS/r1"
hs_env 'titles_disk_prepare req1 "$HS/r1"' > "$HS/r1.log" 2>&1; rc=$?
check "the first title run's disk is prepared (rc=$rc)" [ "$rc" = 0 ]
plans=$(python3 -c 'import json,sys; print(" ".join(p["action"] for p in json.load(open(sys.argv[1]))["plans"]))' "$HS/r1/hdd.json" 2>/dev/null)
check "  ... by seed, build, keep (got: $plans)" [ "$plans" = "seed build keep" ]
check "  ... hddPath now names titles.qcow2 (got: $(pref))" [ "$(pref)" = "$X/titles.qcow2" ]
dsha=$(sha256sum "$HS/dev/fs/titles.qcow2" 2>/dev/null | cut -d' ' -f1)
check "  ... the device's titles.qcow2 is the pushed image (registry sha256)" \
      [ -n "$dsha" ] && [ "$dsha" = "$(reg "st['image']['sha256']")" ]
check "  ... result's sha256_at_start is the device file's" \
      grep -q "\"sha256_at_start\": \"$dsha\"" "$HS/r1/hdd.json"
check "  ... the seed carried both of hdd.img's saves onto it" verify_on "$HS/dev/fs/titles.qcow2" 4D530021 4541005B
check "  ... hdd.img itself was not changed" cmp -s "$HS/fix/hdd.img" "$HS/dev/fs/hdd.img"
# (lane.hddperm.) adb push leaves 644; the app writes through its group, so
# a 644 titles.qcow2 aborts xemu with Permission denied before focus.
mode_of() { stat -c %a "$1" 2>/dev/null; }
check "  ... the pushed titles.qcow2 is 660, as hdd.img is (got: $(mode_of "$HS/dev/fs/titles.qcow2"))" \
      eval '[ "$(mode_of "$HS/dev/fs/titles.qcow2")" = 660 ] && [ "$(mode_of "$HS/dev/fs/hdd.img")" = 660 ]'
check "  ... the marker holds the hddPath it replaced" \
      [ "$(cat "$HS/dispatch/.hdd_pref.nova" 2>/dev/null)" = "$X/hdd.img" ]

# ------------------------------------------------- the run writes a new save
cp "$HS/fix/played.qcow2" "$HS/dev/fs/titles.qcow2"     # the guest saved Ghoulies
psha=$(sha256sum "$HS/dev/fs/titles.qcow2" | cut -d' ' -f1)
hs_env 'titles_disk_after req1 "$HS/r1"' > "$HS/r1.after.log" 2>&1
check "after the run: the new title's save is harvested into the store" \
      grep -q '"4D530053"' "$HS/r1/hdd.after.json"
check "  ... the registry knows the device file's new sha256" [ "$(reg "st['image']['device_sha256']")" = "$psha" ]
check "  ... hddPath is back on hdd.img (got: $(pref))" [ "$(pref)" = "$X/hdd.img" ]
check "  ... the prefs file is byte-identical to before the run" cmp -s "$HS/prefs.orig.xml" "$HS/dev/prefs.xml"
check "  ... the marker is gone" test ! -e "$HS/dispatch/.hdd_pref.nova"

# A disc run: no marker, so not one adb call for the pref.
: > "$HS/dev/calls"
hs_env 'restore_hdd_pref' >/dev/null 2>&1
check "a request with no marker makes no adb call for hddPath" test ! -s "$HS/dev/calls"

# ------------------------------------------ the next title run rebuilds with it
mkdir -p "$HS/r2"
hs_env 'titles_disk_prepare req2 "$HS/r2"' > "$HS/r2.log" 2>&1
plans=$(python3 -c 'import json,sys; print(" ".join(p["action"] for p in json.load(open(sys.argv[1]))["plans"]))' "$HS/r2/hdd.json" 2>/dev/null)
check "the second run rebuilds from the store: build, keep (got: $plans)" [ "$plans" = "build keep" ]
check "  ... its disk carries all three saves" verify_on "$HS/dev/fs/titles.qcow2" 4D530021 4541005B 4D530053
check "  ... and is the image the registry says was pushed" \
      [ "$(sha256sum "$HS/dev/fs/titles.qcow2" | cut -d' ' -f1)" = "$(reg "st['image']['sha256']")" ]
check "  ... and is 660 (got: $(mode_of "$HS/dev/fs/titles.qcow2"))" [ "$(mode_of "$HS/dev/fs/titles.qcow2")" = 660 ]
hs_env 'titles_disk_after req2 "$HS/r2"' >/dev/null 2>&1
check "  ... an untouched disk is not pulled after the run" grep -q unchanged_or_blocked "$HS/r2/hdd.after.json"

# ------------------------------- the pref write lands, its read-back is lost
# (pass-1 M1.) The marker must already hold hdd.img, or the next disc run
# boots the titles disk and the next title run makes that permanent.
echo "== hdd split: a failed hddPath read-back still leaves the way back"
mkdir -p "$HS/r5"; touch "$HS/dev/drop_readback"
hs_env 'titles_disk_prepare req5 "$HS/r5"' > "$HS/r5.log" 2>&1; rc=$?
rm -f "$HS/dev/drop_readback" "$HS/dev/drop_next"
check "a lost read-back fails the prepare (rc=$rc)" [ "$rc" != 0 ]
check "  ... the write did land: hddPath names titles.qcow2 (got: $(pref))" [ "$(pref)" = "$X/titles.qcow2" ]
check "  ... and the marker already holds hdd.img" \
      [ "$(cat "$HS/dispatch/.hdd_pref.nova" 2>/dev/null)" = "$X/hdd.img" ]
hs_env 'restore_hdd_pref' >/dev/null 2>&1
check "  ... so the next request's restore puts hdd.img back (got: $(pref))" [ "$(pref)" = "$X/hdd.img" ]
check "  ... byte for byte" cmp -s "$HS/prefs.orig.xml" "$HS/dev/prefs.xml"
# A device already left on the titles disk with no marker (the pre-fix fault).
sed -i "s:$X/hdd.img</string>:$X/titles.qcow2</string>:" "$HS/dev/prefs.xml"
mkdir -p "$HS/r6"
hs_env 'titles_disk_prepare req6 "$HS/r6"' > "$HS/r6.log" 2>&1
check "hddPath found on titles.qcow2 is never recorded as the one to put back" \
      [ "$(cat "$HS/dispatch/.hdd_pref.nova" 2>/dev/null)" = "$X/hdd.img" ]
hs_env 'titles_disk_after req6 "$HS/r6"' >/dev/null 2>&1
check "  ... the run after it ends on hdd.img (got: $(pref))" [ "$(pref)" = "$X/hdd.img" ]
printf '%s' "$X/titles.qcow2" > "$HS/dispatch/.hdd_pref.nova"
sed -i "s:$X/hdd.img</string>:$X/titles.qcow2</string>:" "$HS/dev/prefs.xml"
hs_env 'restore_hdd_pref' >/dev/null 2>&1
check "a marker naming titles.qcow2 restores hdd.img (got: $(pref))" [ "$(pref)" = "$X/hdd.img" ]

# ------------------------------------------------------ plan(): the guards
echo "== hdd split: plan() never rebuilds over an unharvested disk"
PT="$HS/plan"; mkdir -p "$PT/devices"
plan_on() {   # <registry json> <bytes> <sha> -> action
    printf '%s\n' "$1" > "$PT/devices/thor.json"
    TITLESTATE_DIR="$PT" python3 "$TESTING/titles/titlestate.py" plan --device thor \
        --device-bytes "$2" --device-sha "$3" --cap 1000 --ceiling 5000 \
        | python3 -c 'import json,sys; print(json.load(sys.stdin)["action"])'
}
IMG='"image": {"sha256": "aa", "device_sha256": "aa", "built_from": {}'
check "a changed disk is harvested before anything else" \
      [ "$(plan_on "{\"titles\": {}, $IMG}}" 10 bb)" = harvest ]
check "a disk whose last harvest failed is kept, stale or not" \
      [ "$(plan_on "{\"titles\": {\"4D530021\": {\"profile\": true, \"save\": \"x\"}}, $IMG, \"last_pull\": {\"sha256\": \"bb\", \"errors\": {\"4D530021\": \"short\"}}}}" 4000 bb)" = keep ]
check "  ... unless it is past the ceiling" \
      [ "$(plan_on "{\"titles\": {}, $IMG, \"last_pull\": {\"sha256\": \"bb\", \"errors\": {\"4D530021\": \"short\"}}}}" 6000 bb)" = build ]
check "a clean disk past the cap is rebuilt" [ "$(plan_on "{\"titles\": {}, $IMG}}" 2000 aa)" = build ]
check "a clean disk under the cap is kept" [ "$(plan_on "{\"titles\": {}, $IMG}}" 900 aa)" = keep ]
check "a disk missing from the device is rebuilt" [ "$(plan_on "{\"titles\": {}, $IMG}}" -1 "")" = build ]

# ------------------------------------------------------------- the switch
mkdir -p "$HS/r3"; : > "$HS/dev/calls"
hs_env 'HAKUX_TITLES_DISK=0 titles_disk_prepare req3 "$HS/r3"' >/dev/null 2>&1
check "HAKUX_TITLES_DISK=0: the split is off, recorded, and no adb call is made" \
      eval 'grep -q "HAKUX_TITLES_DISK=0" "$HS/r3/hdd.json" && [ ! -s "$HS/dev/calls" ] && [ "$(pref)" = "$X/hdd.img" ]'

# ------------------------------------------------------- the hdd.img guard
echo "== hdd split: hdd.img past its limit is reset through saves.py reset"
osha=$(sha256sum "$HS/dev/fs/hdd.img" | cut -d' ' -f1)
mkdir -p "$HS/r4"
hs_env 'hdd_img_guard "$HS/r4"' >/dev/null 2>&1
check "under the limit the guard does nothing" test ! -e "$HS/r4/hdd_guard.json"
hs_env 'HAKUX_HDD_RESET_BYTES=1000 hdd_img_guard "$HS/r4"' > "$HS/r4.log" 2>&1
check "over the limit hdd.img is reset" grep -q '"action": "reset"' "$HS/r4/hdd_guard.json"
check "  ... the original is kept on the device as hdd.img.bak-auto" \
      [ "$(sha256sum "$HS/dev/fs/hdd.img.bak-auto" 2>/dev/null | cut -d' ' -f1)" = "$osha" ]
check "  ... the new hdd.img is not the old one" \
      [ "$(sha256sum "$HS/dev/fs/hdd.img" | cut -d' ' -f1)" != "$osha" ]
check "  ... and is 660, not adb push's 644 (got: $(mode_of "$HS/dev/fs/hdd.img"))" [ "$(mode_of "$HS/dev/fs/hdd.img")" = 660 ]
check "  ... and every save on it survived" \
      eval 'for t in 4D530021 4541005B; do python3 "$TESTING/titles/saves.py" verify "$HS/dev/fs/hdd.img" "$HS/fix/$t" >/dev/null || exit 1; done'

# A device that refuses the chmod: the push fails, and the disk it would have
# replaced is still the one it was.
echo "== hdd split: a push whose mode cannot be set fails and replaces nothing"
cp "$HS/dev/fs/hdd.img" "$HS/hdd.before"; head -c 4096 /dev/urandom > "$HS/other.img"
touch "$HS/dev/nochmod"
hs_env 'dev_push "$HS/other.img" "$X/hdd.img"' > "$HS/nochmod.log" 2>&1; rc=$?
rm -f "$HS/dev/nochmod" "$HS/dev/fs/hdd.img.new"
check "a refused chmod fails dev_push (rc=$rc)" [ "$rc" != 0 ]
check "  ... and hdd.img is the disk it was" cmp -s "$HS/hdd.before" "$HS/dev/fs/hdd.img"
cp -p "$HS/hdd.before" "$HS/dev/fs/hdd.img"   # so a red leg here does not redden the guard's

# (pass-1 M2.) A reset that cannot succeed on this disk is paid for once.
echo "== hdd split: a failed reset is not retried on the same disk"
FAILED="$HS/dispatch/.hdd_guard_failed.nova"
guard() { : > "$HS/dev/calls"; rm -f "$HS/r4/hdd_guard.json"; hs_env 'HAKUX_HDD_RESET_BYTES=1000 hdd_img_guard "$HS/r4"' >> "$HS/r4.log" 2>&1; }
touch "$HS/dev/nospace"; guard; rm -f "$HS/dev/nospace"
check "no room for the backup: an alert" grep -q 'could not back up' "$HS/r4/hdd_guard.json"
check "  ... and the partial hdd.img.bak-auto is removed" test ! -e "$HS/dev/fs/hdd.img.bak-auto"
check "  ... the failure is recorded against the disk" test -s "$FAILED"
guard
check "  ... the next request writes the alert again, marked repeat" grep -q '"repeat": true' "$HS/r4/hdd_guard.json"
check "  ... without pulling or hashing the disk" eval '! grep -q "pull\|sha256sum" "$HS/dev/calls"'
head -c 3000000 /dev/urandom > "$HS/dev/fs/hdd.img"
guard
check "a disk saves.py refuses: an alert" grep -q 'saves.py reset refused' "$HS/r4/hdd_guard.json"
guard
check "  ... not retried while the disk is unchanged" \
      eval 'grep -q "\"repeat\": true" "$HS/r4/hdd_guard.json" && ! grep -q "^pull" "$HS/dev/calls"'
printf x >> "$HS/dev/fs/hdd.img"
guard
check "  ... a write to hdd.img re-arms the guard" \
      eval '! grep -q "\"repeat\"" "$HS/r4/hdd_guard.json" && grep -q "^pull" "$HS/dev/calls"'

# --------------------------------------------------------- the wiring
echo "== hdd split: serve_one calls it where the runs are"
body=$(hs_env 'declare -f serve_one')
# Comment lines out: the result writers' heredocs name these functions in prose.
order=$(printf '%s\n' "$body" | grep -v '^[[:space:]]*#' | grep -n -o 'restore_hdd_pref\|titles_disk_prepare\|soak_title.sh\|titles_disk_after\|hdd_img_guard\|run_disc.sh' \
        | cut -d: -f2 | uniq | tr '\n' ' ')
check "restore, prepare, soak, after, then guard before the disc runs (got: $order)" \
      [ "$order" = "restore_hdd_pref titles_disk_prepare restore_hdd_pref soak_title.sh titles_disk_after hdd_img_guard run_disc.sh " ]
