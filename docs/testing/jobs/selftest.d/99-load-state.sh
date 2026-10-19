# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# ok/bad/check. Not executable, no shebang, no exit -- `fail` is shared.
#
# Loading a save state without anyone driving the pause menu (#433,
# lane.savestate-req1019): dispatcher.sh's scene_state_dir/set_scene_pref/
# start_scene_watch/scene_verdict/restore_scene_pref, called directly (the
# same functions dispatcher.sh's soak path calls, not a reimplementation),
# against a fake device root and a fake `adb` on PATH, plus a real
# request.sh for case (e) (the queue-time refusal needs the real argv
# parsing, not a stand-in).
#
# THE FAKE DEVICE. $LS_DEV mirrors the two real locations these functions
# touch: $LS_DEV/x1box/states/<ttid>/slotN.hxs (external storage, plain
# `adb shell`, dev_push/dev_sha256's own territory) and
# $LS_DEV/data/shared_prefs/x1box_prefs.xml (internal storage, needs
# run-as). x1box_dir() is redefined, AFTER sourcing dispatcher.sh, to point
# at $LS_DEV/x1box -- the one function every path above goes through to
# reach the device, so nothing else needs to know the fake exists.
#
# THE FAKE ADB answers `shell` by running the command against the real host
# paths above (bash -c, since scene_state_dir's paths are now real paths
# under $LS_DEV), special-casing `run-as <pkg> <rest>` (cd into
# $LS_DEV/data first -- shared_prefs/x1box_prefs.xml is relative there) and
# `am force-stop` (no-op, there is no process to stop). `push` copies
# through wslpath -u, same as dev_push's own wslpath -w. Every call is
# logged to $LS_ADBLOG.
#
# perf/pad.sh is NOT faked: ROUTE_DRY=1 (its own dry mode, already used by
# route.sh --dry) makes it print what it would send and touch no device, so
# start_scene_watch's real RT_DOWN/RT_RELEASED path runs for real, against
# the real pad.sh, with zero adb calls.
#
# THE MUTANT drops the restore step (restore_scene_pref() neutered to a bare
# `return 0`, by sed on a copy -- cmp-verified to differ -- never on
# docs/testing itself) and reruns case (a); the slot3/pref restoration
# checks that passed under the real file must fail under the mutant, or the
# fragment is not exercising restore_scene_pref at all.

_ls_dg_real() { realpath -m -- "$1" 2>/dev/null; }
LS="$T/ls"
case "$(_ls_dg_real "$LS")" in
    "$(_ls_dg_real "${TMPDIR:-/tmp}")"/*|/tmp/*) ;;
    *) echo "SELFTEST GUARD: 99-load-state.sh refuses to run, nothing removed: $LS is not under \${TMPDIR:-/tmp} or /tmp" >&2
       fail=$((${fail:-0} + 1)); return 1 2>/dev/null || exit 1 ;;
esac
rm -rf "$LS"
mkdir -p "$LS/bin" "$LS/src" "$LS/device/x1box/states/5454000e" "$LS/device/data/shared_prefs" "$LS/dispatch/logs" "$LS/mut"
export LS_DEV="$LS/device" LS_ADBLOG="$LS/adb.log"
: > "$LS_ADBLOG"

cat > "$LS/bin/adb" <<'SH'
#!/usr/bin/env bash
echo "ADB $*" >> "$LS_ADBLOG"
[ "$1" = devices ] && { printf 'List of devices attached\nee317437\tdevice\n'; exit 0; }
[ "$1" = -s ] && shift 2
sub="$1"; shift
case "$sub" in
    shell)
        cmd="$1"
        case "$cmd" in
            "am force-stop "*) exit 0 ;;
            run-as*)
                rest="${cmd#run-as }"; rest="${rest#* }"
                ( cd "$LS_DEV/data" && bash -c "$rest" )
                exit $? ;;
            *) bash -c "$cmd"; exit $? ;;
        esac ;;
    push)
        src=$(wslpath -u "$1" 2>/dev/null) || src="$1"
        cp "$src" "$2"; exit $? ;;
    *) exit 0 ;;
esac
SH
chmod +x "$LS/bin/adb"

ls_reset_device() {
    printf 'ORIGINAL-SLOT5' > "$LS_DEV/x1box/states/5454000e/slot5.hxs"
    printf 'ORIGINAL-SLOT3' > "$LS_DEV/x1box/states/5454000e/slot3.hxs"
    rm -f "$LS_DEV/x1box/states/5454000e/"*.hld
    cat > "$LS_DEV/data/shared_prefs/x1box_prefs.xml" <<'XML'
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="hddPath">/sdcard/x1box/hdd.img</string>
    <boolean name="savestate_auto_load" value="false" />
</map>
XML
    rm -f "$LS/dispatch/.scene_pref.ls" "$LS/dispatch/.scene_files.ls"
}

ls_req() {   # <path> <load_slot> <load_state_file> <hold_trigger>
    python3 -c 'import json,sys
json.dump(dict(load_slot=sys.argv[2], load_state_file=sys.argv[3],
               hold_trigger=sys.argv[4], title_id="5454000e"),
          open(sys.argv[1], "w"))' "$1" "$2" "$3" "$4"
}

# ls_src <dispatcher.sh to source>: everything a scene call needs, isolated
# to this fragment's own fake device and dispatch dir. Call only inside a
# `( ... )` subshell -- it exports PATH and redefines x1box_dir() for
# whatever sources dispatcher.sh next, in THIS shell only.
ls_src() {
    export SERIAL=ee317437 DEVICE_LABEL=ls PKG=com.jreinach.hakux.debug
    export ADB_QUICK_TIMEOUT=5 ADB_RETRIES=0 ROUTE_DRY=1
    export DISPATCH_DIR="$LS/dispatch" HAKUX_WORK="$LS/work"
    export PATH="$LS/bin:$PATH"
    . "$1" selftest-not-a-subcommand >/dev/null 2>&1
    x1box_dir() { echo "$LS_DEV/x1box"; }
}

ls_slot3_restored() {
    [ ! -e "$LS_DEV/x1box/states/5454000e/slot3.hxs.hld" ] \
        && [ "$(cat "$LS_DEV/x1box/states/5454000e/slot3.hxs" 2>/dev/null)" = ORIGINAL-SLOT3 ]
}
ls_pref_is() { grep -q "value=\"$1\"" "$LS_DEV/data/shared_prefs/x1box_prefs.xml" 2>/dev/null; }

# ---------------------------------------------------------------- (a) load ok
echo "== load-state (a): load ok -- result carries the load line and RT window"
RDIR="$LS/rdir-a"; rm -rf "$RDIR"; mkdir -p "$RDIR"
REQ="$LS/req-a.json"
ls_reset_device
ls_req "$REQ" 5 "" "rt:1"
SHA5_BEFORE=$(sha256sum "$LS_DEV/x1box/states/5454000e/slot5.hxs" | cut -d' ' -f1)
(
    ls_src "$TESTING/dispatcher.sh"
    set_scene_pref "$REQ" "$RDIR" 5454000e; echo $? > "$RDIR/set.rc"
    # Snapshot the mid-run state HERE, before restore_scene_pref (below, same
    # subshell) puts everything back -- checking it after the subshell exits
    # would only ever see the post-restore state.
    [ -e "$LS_DEV/x1box/states/5454000e/slot3.hxs.hld" ] && echo parked > "$RDIR/slot3.midrun"
    grep -q 'value="true"' "$LS_DEV/data/shared_prefs/x1box_prefs.xml" && echo true > "$RDIR/pref.midrun"
    printf '10-19 12:00:00.000  111  111 I hakuX-lane: [savestate] op=load slot=5 ok=1 build=test\n' > "$RDIR/logcat.txt"
    start_scene_watch "$RDIR" "$REQ"
    wait "$SCENE_WATCH_PID" 2>/dev/null
    scene_verdict "$RDIR" "$REQ" testsha > "$RDIR/verdict.out"
    restore_scene_pref; echo $? > "$RDIR/restore.rc"
)
[ "$(cat "$RDIR/set.rc" 2>/dev/null)" = 0 ] && ok "(a) set_scene_pref isolated slot 5" || bad "(a) set_scene_pref failed"
[ "$(cat "$RDIR/slot3.midrun" 2>/dev/null)" = parked ] && ok "(a) the sibling slot3 was parked, not deleted, for the run" || bad "(a) slot3 was not parked during the run"
[ "$(cat "$RDIR/pref.midrun" 2>/dev/null)" = true ] && ok "(a) savestate_auto_load was set true for the run" || bad "(a) savestate_auto_load was not set true during the run"
grep -q '^LOAD_OK.*op=load slot=5 ok=1' "$RDIR/rt_hold.log" 2>/dev/null && ok "(a) rt_hold.log carries the load line" || bad "(a) rt_hold.log is missing LOAD_OK"
grep -qE '^RT_DOWN [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{1,3}$' "$RDIR/rt_hold.log" 2>/dev/null && ok "(a) RT_DOWN logged as HH:MM:SS.mmm (score2.py's own format)" || bad "(a) RT_DOWN missing or not HH:MM:SS.mmm"
grep -qE '^RT_RELEASED [0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{1,3}$' "$RDIR/rt_hold.log" 2>/dev/null && ok "(a) RT_RELEASED logged" || bad "(a) RT_RELEASED missing"
[ -z "$(cat "$RDIR/verdict.out" 2>/dev/null)" ] && ok "(a) scene_verdict printed no void for a good load" || bad "(a) scene_verdict voided a good load: $(cat "$RDIR/verdict.out" 2>/dev/null)"
check "(a) scene.json has void=null and both RT timestamps" python3 -c '
import json,sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if d.get("void") is None and d.get("rt_down") and d.get("rt_released") else 1)' "$RDIR/scene.json"
[ "$(cat "$RDIR/restore.rc" 2>/dev/null)" = 0 ] && ok "(a,d) restore_scene_pref returned ok" || bad "(a,d) restore_scene_pref returned non-zero"
ls_slot3_restored && ok "(a,d) slot3 unparked with its original bytes" || bad "(a,d) slot3 not restored byte-for-byte"
ls_pref_is false && ok "(a,d) savestate_auto_load restored to false" || bad "(a,d) savestate_auto_load not restored"
SHA5_AFTER=$(sha256sum "$LS_DEV/x1box/states/5454000e/slot5.hxs" | cut -d' ' -f1)
[ "$SHA5_AFTER" = "$SHA5_BEFORE" ] && ok "(a,d) the owner's own slot5 (no push named) was never touched" || bad "(a,d) slot5 bytes changed even though nothing was pushed into it"
[ ! -e "$LS/dispatch/.scene_pref.ls" ] && [ ! -e "$LS/dispatch/.scene_files.ls" ] && ok "(a,d) no stale scene marker left" || bad "(a,d) a scene marker file was left behind"

# ------------------------------------------------------------ (b) no op=load
echo "== load-state (b): no op=load line within the window -- VOID with a stated reason"
RDIR="$LS/rdir-b"; rm -rf "$RDIR"; mkdir -p "$RDIR"
REQ="$LS/req-b.json"
ls_reset_device
ls_req "$REQ" 5 "" ""
(
    ls_src "$TESTING/dispatcher.sh"
    export SCENE_LOAD_TIMEOUT=2   # the real 30s default, shortened for the test; start_scene_watch reads this override
    set_scene_pref "$REQ" "$RDIR" 5454000e
    printf '10-19 12:00:00.000  111  111 I hakuX-pace: f=1 max=1 ms=1\n' > "$RDIR/logcat.txt"
    start_scene_watch "$RDIR" "$REQ"
    wait "$SCENE_WATCH_PID" 2>/dev/null
    scene_verdict "$RDIR" "$REQ" testsha > "$RDIR/verdict.out"
    restore_scene_pref; echo $? > "$RDIR/restore.rc"
)
grep -q '^LOAD_TIMEOUT' "$RDIR/rt_hold.log" 2>/dev/null && ok "(b) rt_hold.log recorded LOAD_TIMEOUT" || bad "(b) no LOAD_TIMEOUT recorded"
case "$(cat "$RDIR/verdict.out" 2>/dev/null)" in
    *"no [savestate] op=load line"*) ok "(b) scene_verdict voided with a stated reason" ;;
    *) bad "(b) expected a 'no op=load line' void reason; got: $(cat "$RDIR/verdict.out" 2>/dev/null)" ;;
esac
check "(b) scene.json void is set (non-null, non-empty)" python3 -c '
import json,sys
sys.exit(0 if json.load(open(sys.argv[1])).get("void") else 1)' "$RDIR/scene.json"
[ "$(cat "$RDIR/restore.rc" 2>/dev/null)" = 0 ] && ok "(b,d) restore_scene_pref returned ok after a VOID" || bad "(b,d) restore_scene_pref returned non-zero after a VOID"
ls_slot3_restored && ok "(b,d) slot3 restored byte-for-byte after a VOID run" || bad "(b,d) slot3 not restored after a VOID run"
ls_pref_is false && ok "(b,d) savestate_auto_load restored after a VOID run" || bad "(b,d) savestate_auto_load not restored after a VOID run"

# --------------------------------------------------------- (c) op=save appears
echo "== load-state (c): an op=save line mid-run -- VOID even though the load was ok"
RDIR="$LS/rdir-c"; rm -rf "$RDIR"; mkdir -p "$RDIR"
REQ="$LS/req-c.json"
ls_reset_device
ls_req "$REQ" 5 "" ""
(
    ls_src "$TESTING/dispatcher.sh"
    set_scene_pref "$REQ" "$RDIR" 5454000e
    printf '10-19 12:00:00.000  111  111 I hakuX-lane: [savestate] op=load slot=5 ok=1\n10-19 12:00:05.000  111  111 I hakuX-lane: [savestate] op=save slot=5 ok=1\n' > "$RDIR/logcat.txt"
    start_scene_watch "$RDIR" "$REQ"
    wait "$SCENE_WATCH_PID" 2>/dev/null
    scene_verdict "$RDIR" "$REQ" testsha > "$RDIR/verdict.out"
    restore_scene_pref; echo $? > "$RDIR/restore.rc"
)
case "$(cat "$RDIR/verdict.out" 2>/dev/null)" in
    *"op=save"*) ok "(c) scene_verdict voided on a mid-run op=save line" ;;
    *) bad "(c) expected a void naming op=save; got: $(cat "$RDIR/verdict.out" 2>/dev/null)" ;;
esac
[ "$(cat "$RDIR/restore.rc" 2>/dev/null)" = 0 ] && ok "(c,d) restore_scene_pref returned ok after a save-triggered VOID" || bad "(c,d) restore_scene_pref returned non-zero after a save-triggered VOID"
ls_slot3_restored && ok "(c,d) slot3 restored byte-for-byte after a save-triggered VOID" || bad "(c,d) slot3 not restored after a save-triggered VOID"
ls_pref_is false && ok "(c,d) savestate_auto_load restored after a save-triggered VOID" || bad "(c,d) savestate_auto_load not restored after a save-triggered VOID"

# --------------------------------------------------- (e) request.sh queue gate
echo "== load-state (e): request.sh refuses --load-state with a missing file, at queue time"
LS_MISSING="$LS/src/does-not-exist.hxs"
rm -f "$LS_MISSING"
LS_QDIR="$LS/dispatch-e"; rm -rf "$LS_QDIR"
mkdir -p "$LS_QDIR"/{queue,running,results,expect}
LS_EOUT="$LS/req-e.out"
DISPATCH_DIR="$LS_QDIR" bash "$TESTING/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --load-state "$LS_MISSING" >"$LS_EOUT" 2>&1
LS_ERC=$?
case "$LS_ERC:$(cat "$LS_EOUT")" in
    2:*"refusing to queue"*"$LS_MISSING"*) ok "(e) request.sh refused the missing --load-state file (exit 2)" ;;
    *) bad "(e) expected exit 2 naming the missing file; got rc=$LS_ERC: $(cat "$LS_EOUT")" ;;
esac
[ -z "$(ls "$LS_QDIR/queue" 2>/dev/null)" ] && ok "(e) nothing was queued for the refused request" || bad "(e) a request landed in queue/ despite the refusal"

# ------------------------------------------- (f) stale-dispatcher queue guard
# Confirmed for real this session (#433): a request carrying scene/load_slot/
# hold_trigger, served by a pre-fold dispatcher that has never heard of those
# fields, is not refused and not void -- it just runs an ordinary soak from
# the title screen and files the result as though it were the scene asked
# for. request.sh's --only-tests/--audio-capture guards already check the
# SNAPSHOT the dispatcher actually runs (not the requester's own tree) for
# exactly this reason; --scene/--load-state needs the same guard.
echo "== load-state (f): request.sh refuses --scene/--load-state when the serving dispatcher (tree or snapshot) predates scene_verdict"
LS_FQ="$LS/dispatch-f"; LS_TREE="$LS/tree-f"
mkdir -p "$LS_FQ/bin" "$LS_TREE/docs/testing"
printf '#!/usr/bin/env bash\n# stub, no scene support\n' > "$LS_TREE/docs/testing/dispatcher.sh"

# (f1) neither the snapshot nor the tree has it -> plain "not supported"
rm -rf "$LS_FQ/queue" "$LS_FQ/running" "$LS_FQ/results" "$LS_FQ/expect"
mkdir -p "$LS_FQ"/{queue,running,results,expect}
cp "$LS_TREE/docs/testing/dispatcher.sh" "$LS_FQ/bin/dispatcher.sh"
LS_FOUT="$LS/req-f1.out"
DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$TESTING/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --load-state 5 >"$LS_FOUT" 2>&1
case "$?:$(cat "$LS_FOUT")" in
    2:*"refusing to queue"*"not supported by the"*) ok "(f1) refused: neither snapshot nor tree supports --load-state" ;;
    *) bad "(f1) expected exit 2 'not supported'; got: $(cat "$LS_FOUT")" ;;
esac
[ -z "$(ls "$LS_FQ/queue" 2>/dev/null)" ] && ok "(f1) nothing queued" || bad "(f1) a request landed in queue/ despite the refusal"

# (f2) the tree has it, the snapshot (what actually serves) does not -> the
# more specific "merged but still running an older snapshot" message
cp "$TESTING/dispatcher.sh" "$LS_TREE/docs/testing/dispatcher.sh"
LS_FOUT="$LS/req-f2.out"
DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$TESTING/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --load-state 5 >"$LS_FOUT" 2>&1
case "$?:$(cat "$LS_FOUT")" in
    2:*"refusing to queue"*"older snapshot"*) ok "(f2) refused: merged in the tree, snapshot still stale" ;;
    *) bad "(f2) expected exit 2 'older snapshot'; got: $(cat "$LS_FOUT")" ;;
esac
[ -z "$(ls "$LS_FQ/queue" 2>/dev/null)" ] && ok "(f2) nothing queued" || bad "(f2) a request landed in queue/ despite the refusal"

# (f3) the snapshot has it too -> the (f1)/(f2) guard itself does not fire.
# (A real title still needs a kept profile/golden to queue at all -- out of
# scope here, so this only asserts the ABSENCE of this fragment's own
# refusal text, not an overall rc=0.)
cp "$TESTING/dispatcher.sh" "$LS_FQ/bin/dispatcher.sh"
LS_FOUT="$LS/req-f3.out"
DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$TESTING/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --load-state 5 --no-expect "selftest (f3)" >"$LS_FOUT" 2>&1
case "$(cat "$LS_FOUT" 2>/dev/null)" in
    *"not supported by the"*|*"older snapshot"*) bad "(f3) the stale-dispatcher guard fired even though the snapshot has scene_verdict: $(cat "$LS_FOUT")" ;;
    *) ok "(f3) an up-to-date snapshot does not trip the stale-dispatcher guard" ;;
esac

# ------------------------------------------------------- MUTANT: drop restore
echo "== load-state MUTANT: restore_scene_pref dropped -- case (a,d)'s restore checks must then fail"
# dispatcher.sh sources ./devices.sh relative to its OWN directory at load
# time (HERE="$(dirname BASH_SOURCE[0])"), so the mutant needs every sibling
# dispatcher.sh depends on next to it, not just the one file that changed --
# a bare copy of dispatcher.sh alone fails at `. "$HERE/devices.sh"` before
# any scene function is even reached, which would make this mutant "pass"
# for the wrong reason (nothing ran, so nothing un-restored anything). Mirror
# $TESTING with symlinks, same as 51-dispatch-hardening.sh's dhmut(); only
# dispatcher.sh itself is a real, mutated file.
rm -rf "$LS/mut"; mkdir -p "$LS/mut"
for _ls_x in "$TESTING"/*; do
    _ls_b="$(basename "$_ls_x")"
    [ "$_ls_b" = dispatcher.sh ] || ln -s "$_ls_x" "$LS/mut/$_ls_b"
done
sed 's|^restore_scene_pref() {$|restore_scene_pref() { return 0 #MUTANT-DROPPED-RESTORE (99-load-state.sh)|' \
    "$TESTING/dispatcher.sh" > "$LS/mut/dispatcher.sh"
if cmp -s "$LS/mut/dispatcher.sh" "$TESTING/dispatcher.sh"; then
    bad "MUTANT: could not build it (the sed matched nothing -- restore_scene_pref() { not found verbatim)"
else
    RDIR="$LS/rdir-mut"; rm -rf "$RDIR"; mkdir -p "$RDIR"
    REQ="$LS/req-mut.json"
    ls_reset_device
    ls_req "$REQ" 5 "" ""
    (
        ls_src "$LS/mut/dispatcher.sh"
        set_scene_pref "$REQ" "$RDIR" 5454000e
        printf '10-19 12:00:00.000  111  111 I hakuX-lane: [savestate] op=load slot=5 ok=1\n' > "$RDIR/logcat.txt"
        start_scene_watch "$RDIR" "$REQ"
        wait "$SCENE_WATCH_PID" 2>/dev/null
        scene_verdict "$RDIR" "$REQ" testsha > "$RDIR/verdict.out"
        restore_scene_pref; echo $? > "$RDIR/restore.rc"
    )
    if ls_slot3_restored && ls_pref_is false; then
        bad "MUTANT: dropping the restore step still left slot3 restored and the pref false -- case (d) does not exercise the restore"
    else
        ok "MUTANT: with the restore step dropped, slot3 stays parked and/or the pref stays true -- case (d) is real"
    fi
fi

[ -s "$LS_ADBLOG" ] && ok "the fake adb was actually exercised (not bypassed)" || bad "the fake adb log is empty -- nothing above drove a real adb call"
