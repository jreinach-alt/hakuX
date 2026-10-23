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
# THE FAKE DEVICE IS APP-ONLY, AS THE REAL ONE IS (lane.scenewrite1023). On
# the Nova a title's states dir is `drwxr-s--- u0_a145 ext_data_rw`: `adb
# shell` (uid shell, group ext_data_rw) reads it and cannot create, rename or
# delete in it, until `run-as <pkg> chmod g+w` opens it. This fragment's fake
# ran every `shell` and `push` as the host user, so nothing it did could ever
# show that split, and the scene path shipped on a comment saying the dir was
# shell-writable. Now the host user stands in for the shell user and the
# kernel does the refusing: a states dir the fake marks app-only is host
# mode 555 (owner-readable, not owner-writable), so a plain-shell or push
# create, `mv`, `cp` into, `rm` or `.new` fails with a real EACCES, while
# `ls`, `stat` and `sha256sum` still work. `run-as <pkg> chmod g+w|g-w <dir>`
# is translated to u+w|u-w (the owner changing its own dir) and `run-as` of
# anything else may write a closed dir (it is the owner). Faults are files,
# so a case switches one on by creating it and ls_reset_device clears them:
#   fault.stuck      run-as chmod does nothing (a dir run-as cannot open)
#   fault.failmv     text; a plain-shell `mv` whose command contains it fails
#   fault.failmv.lie with fault.failmv: the mv does nothing and says it worked
# The kernel only refuses a non-root user, so the (k0) probe says so loudly
# when this runs as root.
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
#
# THE SCENE'S DISK (g)-(j): a load rolls back the disk it boots, so a scene
# boots a copy of the disk its state was saved on, never the owner's image
# and never titles.qcow2 (dispatcher.sh, A SCENE BOOTS A COPY). The fake
# device gains hdd-owner-1018.img and a copy, hddPath on the owner's image as
# on the Nova. (g) scene_hdd_prepare/scene_hdd_after move the pref and put it
# back byte for byte; (h) scene_hdd_check's refusals; (i) request.sh refuses
# the same names in the same words; (j) serve_one itself, in a mirror of
# $TESTING whose soak_title.sh is a stub that records the disk hddPath names
# and writes to it as a load does. Six mutants, each one exact substitution
# on a mirror copy, each reinstating the weaker rule one check above exists
# to refuse; each must turn that check red.
#
# THE STATES DIR (k), lane.scenewrite1023, against the app-only fake: (k0) the
# fake itself behaves as the device does; (k1) a closed dir plus a host-file
# push -- set_scene_pref opens it, backs up, pushes, parks, and restore puts
# every file back byte for byte and the mode back; (k1b) a dir that is already
# open is neither chmodded nor closed; (k2) a dir run-as cannot open fails
# with the named reason and nothing on the device changes; (k3, k3b) a park
# that fails, and one that lies about it, fail the setup with the files it had
# already moved back; (k5) the app's lower-case dir for an upper-case ttid;
# (k6, k7) a missing dir and a request with no title id. Mutants: the open
# step dropped (k1), the restore's close dropped (k1), a failed park ignored as
# `&& parked+=` ignored it, with and without the listing that backs the mv
# status (k3, k3b).

_ls_dg_real() { realpath -m -- "$1" 2>/dev/null; }
LS="$T/ls"
case "$(_ls_dg_real "$LS")" in
    "$(_ls_dg_real "${TMPDIR:-/tmp}")"/*|/tmp/*) ;;
    *) echo "SELFTEST GUARD: 99-load-state.sh refuses to run, nothing removed: $LS is not under \${TMPDIR:-/tmp} or /tmp" >&2
       fail=$((${fail:-0} + 1)); return 1 2>/dev/null || exit 1 ;;
esac
# A closed states dir is host mode 555, which rm -rf cannot empty: open them first.
chmod -R u+w "$LS" 2>/dev/null
rm -rf "$LS"
mkdir -p "$LS/bin" "$LS/src" "$LS/device/x1box/states/5454000e" "$LS/device/data/shared_prefs" "$LS/dispatch/logs" "$LS/mut"
export LS_DEV="$LS/device" LS_ADBLOG="$LS/adb.log" LS_FAKE="$LS/fault"
: > "$LS_ADBLOG"

cat > "$LS/bin/adb" <<'SH'
#!/usr/bin/env bash
echo "ADB $*" >> "$LS_ADBLOG"
[ "$1" = devices ] && { printf 'List of devices attached\nee317437\tdevice\n'; exit 0; }
[ "$1" = -s ] && shift 2
sub="$1"; shift
# The host user is the shell user; a states dir the fake marks app-only is
# host mode 555, so the kernel refuses its writes (header comment).
case "$sub" in
    shell)
        cmd="$1"
        case "$cmd" in
            "am force-stop "*) exit 0 ;;
            run-as*)
                rest="${cmd#run-as }"; rest="${rest#* }"
                case "$rest" in
                    "chmod g+w "*|"chmod g-w "*)
                        # The app (the owner) changing the group bit of its dir:
                        # for the host user that is the owner bit.
                        [ -e "$LS_FAKE.stuck" ] && exit 0
                        read -r _ op path <<<"$rest"
                        path="${path#\'}"; path="${path%\'}"
                        case "$op" in g+w) chmod u+w "$path";; g-w) chmod u-w "$path";; esac
                        exit $? ;;
                    *)
                        # Anything else run-as does may write a closed dir: it owns it.
                        closed=$(find "$LS_DEV/x1box/states" -type d ! -perm -u+w 2>/dev/null)
                        for d in $closed; do chmod u+w "$d"; done
                        ( cd "$LS_DEV/data" && bash -c "$rest" ); rc=$?
                        for d in $closed; do chmod u-w "$d"; done
                        exit $rc ;;
                esac ;;
            *)
                if [ -s "$LS_FAKE.failmv" ]; then
                    pat=$(cat "$LS_FAKE.failmv")
                    case "$cmd" in
                        *"mv "*"$pat"*)
                            [ -e "$LS_FAKE.failmv.lie" ] && exit 0
                            echo "mv: failed to rename: Permission denied" >&2; exit 1 ;;
                    esac
                fi
                bash -c "$cmd"; exit $? ;;
        esac ;;
    push)
        src=$(wslpath -u "$1" 2>/dev/null) || src="$1"
        cp "$src" "$2"; exit $? ;;
    install) echo Success; exit 0 ;;
    *) exit 0 ;;
esac
SH
chmod +x "$LS/bin/adb"

# ls_reset_device [open] [slot1]: the fake device as a fresh Nova title has
# it -- the states dir the app's (555) unless "open" (the Nova's 5454000e after
# lane.local's by-hand chmod) -- and no fault switched on. "slot1" adds a third
# slot file, for a case that needs two files to park.
ls_reset_device() {
    local d="$LS_DEV/x1box/states/5454000e" a
    chmod -R u+w "$LS_DEV/x1box/states" 2>/dev/null
    rm -rf "$LS_DEV/x1box/states"
    mkdir -p "$d"
    printf 'ORIGINAL-SLOT5' > "$d/slot5.hxs"
    printf 'ORIGINAL-SLOT3' > "$d/slot3.hxs"
    for a in "$@"; do [ "$a" = slot1 ] && printf 'ORIGINAL-SLOT1' > "$d/slot1.hxs"; done
    chmod 660 "$d"/*.hxs
    rm -f "$LS_FAKE".*
    cat > "$LS_DEV/data/shared_prefs/x1box_prefs.xml" <<'XML'
<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="hddPath">/sdcard/x1box/hdd.img</string>
    <boolean name="savestate_auto_load" value="false" />
</map>
XML
    # Every label: device_env names ee317437 nova, whatever DEVICE_LABEL was.
    rm -f "$LS/dispatch/.scene_pref."* "$LS/dispatch/.scene_files."*
    # states/ is the app's too (shell cannot make a title dir in it).
    case " $* " in
        *" open "*) chmod 755 "$d";;
        *)          chmod 555 "$d";;
    esac
    chmod 555 "$LS_DEV/x1box/states"
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
[ -z "$(ls -A "$LS/dispatch" | grep -E '^\.scene_(pref|files)\.')" ] && ok "(a,d) no stale scene marker left" || bad "(a,d) a scene marker file was left behind"

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
echo "== load-state (f): request.sh refuses --scene/--load-state when the serving dispatcher (tree or snapshot) predates scene_hdd_check"
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
    *"not supported by the"*|*"older snapshot"*) bad "(f3) the stale-dispatcher guard fired even though the snapshot has scene_hdd_check: $(cat "$LS_FOUT")" ;;
    *) ok "(f3) an up-to-date snapshot does not trip the stale-dispatcher guard" ;;
esac

# ---------------------------------------------- the scene's disk: fixtures
LS_OWNER="$LS_DEV/x1box/hdd-owner-1018.img" LS_COPY="$LS_DEV/x1box/hdd-scene-gta3.img"
LS_PREFS="$LS_DEV/data/shared_prefs/x1box_prefs.xml"
ls_reset_hdd() {   # [hddPath, default the owner's image]
    ls_reset_device
    printf 'OWNER-DISK' > "$LS_OWNER"; chmod 660 "$LS_OWNER"
    printf 'OWNER-DISK' > "$LS_COPY"; chmod 644 "$LS_COPY"
    rm -f "$LS/dispatch/.hdd_pref."*
    sed -i "s|/sdcard/x1box/hdd.img|${1:-$LS_OWNER}|" "$LS_PREFS"
    cp "$LS_PREFS" "$LS/prefs.before"
    LS_OWNER_SHA=$(sha256sum "$LS_OWNER" | cut -d' ' -f1)
}
ls_hreq() {   # <path> <scene_hdd> [load_slot, default 5]
    python3 -c 'import json,sys
json.dump(dict(title="Grand Theft Auto III", title_id="5454000e",
               load_slot=sys.argv[3], scene_hdd=sys.argv[2], hold_trigger=""),
          open(sys.argv[1], "w"))' "$1" "$2" "${3-5}"
}
ls_pref_hdd() { sed -n 's|.*<string name="hddPath">\(.*\)</string>.*|\1|p' "$LS_PREFS"; }
ls_owner_intact() {
    [ "$(sha256sum "$LS_OWNER" | cut -d' ' -f1)" = "$LS_OWNER_SHA" ] && [ "$(stat -c %a "$LS_OWNER")" = 660 ]
}
ls_no_hdd_marker() { [ -z "$(ls -A "$LS/dispatch" | grep '^\.hdd_pref\.')" ]; }
ls_json() {   # <file> <python expression over d>
    python3 -c 'import json,sys
d = json.load(open(sys.argv[1]))
sys.exit(0 if eval(sys.argv[2]) else 1)' "$1" "$2" 2>/dev/null
}

# The soak stand-in: what hddPath names when the title would boot, a write to
# that disk as a load's rollback is (only under the fake device), and a load.
cat > "$LS/soak_stub.sh" <<'SH'
#!/usr/bin/env bash
r=$(dirname "$CAPTURE_LOG")
h=$(sed -n 's|.*<string name="hddPath">\(.*\)</string>.*|\1|p' "$LS_DEV/data/shared_prefs/x1box_prefs.xml")
printf '%s\n' "$h" > "$r/soak.hdd"
case "$h" in "$LS_DEV"/*) [ -f "$h" ] && printf 'ROLLED-BACK' >> "$h";; esac
printf '10-23 12:00:00.000  111  111 I hakuX-lane: [savestate] op=load slot=5 ok=1 build=test\n' >> "$CAPTURE_LOG"
sleep 2
SH
: > "$LS/fake.apk"

# ls_mirror <dir>: $TESTING by symlink, a real copy of dispatcher.sh for a
# mutant to edit, and the stub in soak_title.sh's place (serve_one runs it
# from dispatcher.sh's own directory).
ls_mirror() {
    local d="$1" x b
    rm -rf "$d"; mkdir -p "$d"
    for x in "$TESTING"/*; do
        b="$(basename "$x")"
        case "$b" in dispatcher.sh|soak_title.sh) ;; *) ln -s "$x" "$d/$b";; esac
    done
    cp "$TESTING/dispatcher.sh" "$d/dispatcher.sh"
    cp "$LS/soak_stub.sh" "$d/soak_title.sh"
}
# ls_mutate <file> <old> <new>: exactly one occurrence replaced, or exit 1.
ls_mutate() {
    python3 - "$@" <<'PY'
import sys
p, old, new = sys.argv[1:4]
s = open(p).read()
if s.count(old) != 1:
    sys.exit("%d occurrences" % s.count(old))
open(p, "w").write(s.replace(old, new))
PY
}

# ls_case_g <dispatcher.sh> <rdir> [initial hddPath]: scene_hdd_prepare, the
# state mid-run, scene_hdd_after.
ls_case_g() {
    local disp="$1" rdir="$2"
    rm -rf "$rdir"; mkdir -p "$rdir"
    ls_reset_hdd "${3:-}"
    ls_hreq "$rdir.req" hdd-scene-gta3.img
    (
        ls_src "$disp"
        scene_hdd_prepare "$rdir" "$rdir.req"; echo $? > "$rdir/prepare.rc"
        ls_pref_hdd > "$rdir/pref.midrun"
        stat -c %a "$LS_COPY" > "$rdir/copy.mode"
        ls_no_hdd_marker || echo present > "$rdir/marker.midrun"
        scene_hdd_after "$rdir"; echo $? > "$rdir/after.rc"
    )
}
# ls_check_rc <dispatcher.sh> <rdir> <scene_hdd> [load_slot]: scene_hdd_check's rc.
ls_check_rc() {
    local disp="$1" rdir="$2"
    rm -rf "$rdir"; mkdir -p "$rdir"
    ls_hreq "$rdir.req" "$3" "${4-5}"
    ( ls_src "$disp"; scene_hdd_check "$rdir.req" "$rdir"; echo $? > "$rdir/check.rc" )
    cat "$rdir/check.rc" 2>/dev/null
}
# ls_serve <dir> <request json> <id>: serve_one from <dir>/dispatcher.sh on
# the fake device. The build, the ISO lookup, the route and profile gates and
# the captures are stubbed; the claim, scene_hdd_check, the install, the
# scene's slot and disk and every restore are the real code. The titles disk
# is stubbed to say whether it was asked for.
ls_serve() {
    local dir="$1" req="$2" id="$3"
    rm -rf "$LS/dispatch/results/$id"
    (
        export BATTERY_ADMIT=off HAKUX_DEVICE_LEASE="$LS/lease" SCENE_LOAD_TIMEOUT=5
        ls_src "$dir/dispatcher.sh"
        build_ref() { echo "$LS/fake.apk"; }
        guard_not_release_apk() { return 0; }
        lane_blind_check() { :; }
        clear_shader_caches_on_apk_change() { return 0; }
        apply_env_pref() { return 0; }
        ensure_legacy_folder_pref() { return 0; }
        device_title_path() { echo "/fake/Grand Theft Auto III.iso"; }
        ensure_route_attached() { return 0; }
        profile_gate_check() { return 0; }
        ensure_profile_restored() { :; }
        titles_disk_prepare() { echo called > "$2/titles_disk_prepare.called"; return 0; }
        titles_disk_after() { echo called > "$2/titles_disk_after.called"; }
        verify_profile_on_device() { echo called > "$3/verify_profile.called"; return 0; }
        write_route_refs() { return 0; }
        start_frame_capture() { :; }; stop_frame_capture() { :; }
        start_soak_video() { :; }; stop_soak_video() { :; }
        maybe_run_doctor() { :; }; queue_master_restore() { :; }
        cp "$req" "$D/queue/$id.req"
        serve_one "$D/queue/$id.req"; echo $? > "$LS/serve-$id.rc"
    ) >/dev/null 2>&1
}
ls_installs() { grep -c '^ADB -s ee317437 install' "$LS_ADBLOG"; }

# ------------------------------------------------ (g) the scene boots the copy
echo "== load-state (g): scene_hdd_prepare points hddPath at the copy; scene_hdd_after puts the owner's path back"
RDIR="$LS/rdir-g"
ls_case_g "$TESTING/dispatcher.sh" "$RDIR"
[ "$(cat "$RDIR/prepare.rc" 2>/dev/null)" = 0 ] && ok "(g) scene_hdd_prepare returned ok" || bad "(g) scene_hdd_prepare returned $(cat "$RDIR/prepare.rc" 2>/dev/null)"
[ "$(cat "$RDIR/pref.midrun" 2>/dev/null)" = "$LS_COPY" ] && ok "(g) mid-run hddPath names the copy" || bad "(g) mid-run hddPath is '$(cat "$RDIR/pref.midrun" 2>/dev/null)', not the copy"
[ "$(cat "$RDIR/copy.mode" 2>/dev/null)" = 660 ] && ok "(g) the copy was made mode 660 (it was 644)" || bad "(g) the copy is mode $(cat "$RDIR/copy.mode" 2>/dev/null), not 660"
[ "$(cat "$RDIR/marker.midrun" 2>/dev/null)" = present ] && ok "(g) the owner's path was in the marker mid-run" || bad "(g) no hddPath marker mid-run: a dead worker could not put the pref back"
ls_json "$RDIR/hdd_scene.json" "d['action'] == 'set' and d['was'] == '$LS_OWNER' and d['want'] == '$LS_COPY' and d['restored'] is True" \
    && ok "(g) hdd_scene.json: set, was the owner's image, restored" || bad "(g) hdd_scene.json wrong: $(cat "$RDIR/hdd_scene.json" 2>/dev/null)"
ls_json "$RDIR/hdd.json" "d['path'] == '$LS_COPY' and d['scene_hdd'] == 'hdd-scene-gta3.img' and d['mode_found'] == '644'" \
    && ok "(g) hdd.json records the copy as the booted disk" || bad "(g) hdd.json wrong: $(cat "$RDIR/hdd.json" 2>/dev/null)"
cmp -s "$LS/prefs.before" "$LS_PREFS" && ok "(g) x1box_prefs.xml is back byte for byte" || bad "(g) x1box_prefs.xml differs after scene_hdd_after"
ls_owner_intact && ok "(g) the owner's image is untouched (sha256 and mode 660)" || bad "(g) the owner's image changed"
ls_no_hdd_marker && ok "(g) no hddPath marker left" || bad "(g) an hddPath marker was left behind"

echo "== load-state (g2): hddPath already names the copy -- kept, no write, no marker"
RDIR="$LS/rdir-g2"
LS_N0=$(wc -l < "$LS_ADBLOG")
ls_case_g "$TESTING/dispatcher.sh" "$RDIR" "$LS_COPY"
ls_json "$RDIR/hdd_scene.json" "d['action'] == 'kept' and d['restored'] is None" && ok "(g2) hdd_scene.json: kept" || bad "(g2) hdd_scene.json wrong: $(cat "$RDIR/hdd_scene.json" 2>/dev/null)"
[ "$(cat "$RDIR/marker.midrun" 2>/dev/null)" != present ] && ls_no_hdd_marker && ok "(g2) no marker, mid-run or after" || bad "(g2) a marker was written for a pref that did not move"
sed -n "$((LS_N0 + 1)),\$p" "$LS_ADBLOG" | grep -q "cat > shared_prefs" && bad "(g2) x1box_prefs.xml was written although hddPath already named the copy" || ok "(g2) x1box_prefs.xml was not written"

# --------------------------------------------------- (h) scene_hdd_check
echo "== load-state (h): scene_hdd_check refuses, by name, before anything is installed"
ls_reset_hdd
LS_H_ROWS=(
    "|names no hdd"
    "x/y|is a path"
    "bad name|is not a plain file name"
    "-x|is not a plain file name"
    "hdd-owner-1018.img|is the owner's image"
    "HDD-Owner-1018.img|is the owner's image"
    "titles.qcow2|is a harness disk"
    "hdd.img|is a harness disk"
    "hdd-scene-missing.img|does not exist on the device"
    "states|is not a file"
)
LS_I=0
for LS_ROW in "${LS_H_ROWS[@]}"; do
    LS_NAME=${LS_ROW%%|*} LS_PHRASE=${LS_ROW#*|}
    RDIR="$LS/rdir-h$LS_I"; LS_I=$((LS_I + 1))
    LS_RC=$(ls_check_rc "$TESTING/dispatcher.sh" "$RDIR" "$LS_NAME")
    if [ "$LS_RC" = 3 ] && grep -qF "$LS_PHRASE" "$RDIR/scene_hdd.refused" 2>/dev/null; then
        ok "(h) hdd '$LS_NAME' refused: $LS_PHRASE"
    else
        bad "(h) hdd '$LS_NAME': expected rc 3 and '$LS_PHRASE'; got rc=$LS_RC: $(cat "$RDIR/scene_hdd.refused" 2>/dev/null)"
    fi
done
[ "$(ls_check_rc "$TESTING/dispatcher.sh" "$LS/rdir-hok" hdd-scene-gta3.img)" = 0 ] && ok "(h) the copy, present on the device, passes" || bad "(h) the copy was refused: $(cat "$LS/rdir-hok/scene_hdd.refused" 2>/dev/null)"
LS_N0=$(wc -l < "$LS_ADBLOG")
LS_RC=$(ls_check_rc "$TESTING/dispatcher.sh" "$LS/rdir-hnone" "" "")
[ "$LS_RC" = 0 ] && [ "$(wc -l < "$LS_ADBLOG")" = "$LS_N0" ] && ok "(h) a title run with no load passes with no adb call" || bad "(h) a no-load run: rc=$LS_RC, $(( $(wc -l < "$LS_ADBLOG") - LS_N0 )) adb call(s)"
ls_owner_intact && cmp -s "$LS/prefs.before" "$LS_PREFS" && ok "(h) no check changed the owner's image or the prefs" || bad "(h) a check changed the owner's image or the prefs"

# ------------------------------------------------ (i) request.sh, same words
echo "== load-state (i): request.sh refuses the same names in the same words, at queue time"
( ls_src "$TESTING/dispatcher.sh"
  LS_I=0
  for LS_ROW in "${LS_H_ROWS[@]}"; do scene_hdd_name_refusal "${LS_ROW%%|*}" > "$LS/want.$LS_I"; LS_I=$((LS_I + 1)); done )
LS_I=0
for LS_ROW in "${LS_H_ROWS[@]}"; do
    LS_NAME=${LS_ROW%%|*}; LS_WANT=$(cat "$LS/want.$LS_I" 2>/dev/null); LS_I=$((LS_I + 1))
    # Whether the file is on the device is the dispatcher's alone to say.
    [ -n "$LS_WANT" ] || continue
    LS_ARGS=(); [ -z "$LS_NAME" ] || LS_ARGS=(--load-hdd "$LS_NAME")
    LS_OUT=$(DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$TESTING/request.sh" --who ls-selftest \
        --title "Grand Theft Auto III" --load-state 5 "${LS_ARGS[@]}" --no-expect "selftest (i)" 2>&1)
    LS_RC=$?
    if [ "$LS_RC" = 2 ] && printf '%s\n' "$LS_OUT" | grep -qxF "refusing to queue: $LS_WANT"; then
        ok "(i) request.sh refuses hdd '$LS_NAME' with the dispatcher's words"
    else
        bad "(i) request.sh on hdd '$LS_NAME': rc=$LS_RC, wanted 'refusing to queue: $LS_WANT'; got: $LS_OUT"
    fi
done
LS_OUT=$(DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$TESTING/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --load-hdd hdd-scene-gta3.img --no-expect "selftest (i)" 2>&1)
case "$?:$LS_OUT" in
    2:*"--load-hdd names the disk for a save-state load, and this request loads none"*) ok "(i) --load-hdd with no load is refused" ;;
    *) bad "(i) --load-hdd with no load was not refused: $LS_OUT" ;;
esac
LS_OUT=$(DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$TESTING/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --scene gta3-incar --no-expect "selftest (i)" 2>&1)
case "$LS_OUT" in
    *"scene hdd '"*|*"names no hdd"*) bad "(i) the real scenes.tsv gta3-incar row was refused for its disk: $LS_OUT" ;;
    *) ok "(i) the real scenes.tsv gta3-incar row names an acceptable disk" ;;
esac
# A scenes.tsv of this fragment's own, beside a mirrored request.sh (it reads
# the scenes.tsv next to itself): an owner's-image row, and a row from before
# the hdd column.
LS_RT="$LS/rtree"; rm -rf "$LS_RT"; mkdir -p "$LS_RT"
for _ls_x in "$TESTING"/*; do
    _ls_b="$(basename "$_ls_x")"
    [ "$_ls_b" = scenes.tsv ] || ln -s "$_ls_x" "$LS_RT/$_ls_b"
done
printf 'name\ttitle_id\tslot\tstate_file\tdefault_hold\thdd\nownerrow\t5454000e\t5\tdevice\trt:60\thdd-owner-1018.img\noldrow\t5454000e\t5\tdevice\trt:60\n' > "$LS_RT/scenes.tsv"
LS_OUT=$(DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$LS_RT/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --scene ownerrow --no-expect "selftest (i)" 2>&1)
case "$?:$LS_OUT" in
    2:*"refusing to queue: scene hdd 'hdd-owner-1018.img' is the owner's image"*) ok "(i) a scenes.tsv row naming the owner's image is refused" ;;
    *) bad "(i) the owner's-image scenes.tsv row was not refused: $LS_OUT" ;;
esac
LS_OUT=$(DISPATCH_DIR="$LS_FQ" DISPATCH_TREE="$LS_TREE" bash "$LS_RT/request.sh" --who ls-selftest \
    --title "Grand Theft Auto III" --scene oldrow --no-expect "selftest (i)" 2>&1)
case "$?:$LS_OUT" in
    *Traceback*|*KeyError*) bad "(i) a row with no hdd column crashed request.sh: $LS_OUT" ;;
    2:*"refusing to queue: a save-state load names no hdd"*) ok "(i) a row from before the hdd column is refused for naming no hdd" ;;
    *) bad "(i) a row with no hdd column was not refused: $LS_OUT" ;;
esac

# ------------------------------------------------- (j) serve_one, end to end
echo "== load-state (j): serve_one boots the copy, not the titles disk, and the owner's image is never booted"
LS_SERVE="$LS/serve"; ls_mirror "$LS_SERVE"
cmp -s "$LS_SERVE/dispatcher.sh" "$TESTING/dispatcher.sh" || bad "(j) the mirror's dispatcher.sh is not the real one"
ls_reset_hdd
ls_hreq "$LS/req-j.json" hdd-scene-gta3.img
ls_serve "$LS_SERVE" "$LS/req-j.json" lsj
RDIR="$LS/dispatch/results/lsj"
[ "$(cat "$LS/serve-lsj.rc" 2>/dev/null)" = 0 ] && [ -e "$RDIR/DONE" ] && ok "(j) serve_one ran the scene to DONE" || bad "(j) serve_one rc=$(cat "$LS/serve-lsj.rc" 2>/dev/null), DONE $([ -e "$RDIR/DONE" ] && echo present || echo missing); ERROR: $(cat "$RDIR/ERROR" 2>/dev/null)"
[ "$(cat "$RDIR/soak.hdd" 2>/dev/null)" = "$LS_COPY" ] && ok "(j) the title booted with hddPath on the copy" || bad "(j) the title booted with hddPath '$(cat "$RDIR/soak.hdd" 2>/dev/null)'"
[ ! -e "$RDIR/titles_disk_prepare.called" ] && [ ! -e "$RDIR/titles_disk_after.called" ] && ok "(j) the titles disk was neither prepared nor harvested" || bad "(j) the scene run went through the titles disk"
[ ! -e "$RDIR/verify_profile.called" ] && ok "(j) no composed-profile check on the copy" || bad "(j) verify_profile_on_device ran on a scene's copy"
ls_owner_intact && ok "(j) the owner's image is untouched" || bad "(j) the owner's image changed"
[ "$(tail -c 11 "$LS_COPY")" = ROLLED-BACK ] && ok "(j) the load's write landed on the copy" || bad "(j) the copy was not the disk the run wrote to"
cmp -s "$LS/prefs.before" "$LS_PREFS" && ok "(j) x1box_prefs.xml is back byte for byte (hddPath and savestate_auto_load)" || bad "(j) x1box_prefs.xml differs after the run"
ls_no_hdd_marker && ok "(j) no hddPath marker left" || bad "(j) an hddPath marker was left behind"
ls_json "$RDIR/result.json" "d['hdd']['path'] == '$LS_COPY' and d['hdd']['pref']['action'] == 'set' and d['hdd']['pref']['restored'] is True" \
    && ok "(j) result.json hdd names the copy and the pref's restore" || bad "(j) result.json hdd wrong: $(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("hdd"))' "$RDIR/result.json" 2>&1)"

echo "== load-state (j2): a request naming the owner's image is refused before the install"
ls_reset_hdd
ls_hreq "$LS/req-j2.json" hdd-owner-1018.img
LS_N0=$(ls_installs)
ls_serve "$LS_SERVE" "$LS/req-j2.json" lsj2
RDIR="$LS/dispatch/results/lsj2"
case "$(cat "$RDIR/ERROR" 2>/dev/null)" in
    "refused before the install: scene hdd 'hdd-owner-1018.img' is the owner's image"*) ok "(j2) ERROR names the refusal" ;;
    *) bad "(j2) ERROR is not the owner's-image refusal: $(cat "$RDIR/ERROR" 2>/dev/null)" ;;
esac
[ "$(ls_installs)" = "$LS_N0" ] && ok "(j2) nothing was installed" || bad "(j2) adb install ran for a refused scene"
[ -f "$RDIR/request.json" ] && [ ! -e "$LS/dispatch/running/lsj2.req" ] && ok "(j2) the request left running/ for its result dir" || bad "(j2) the refused request was not moved to its result dir"
ls_owner_intact && cmp -s "$LS/prefs.before" "$LS_PREFS" && ok "(j2) the owner's image and the prefs are untouched" || bad "(j2) the refusal changed the owner's image or the prefs"

# ----------------------------------------------- (k) the states dir is app-only
# A scene writes into x1box/states/<ttid>/, which the app made and `adb shell`
# can read and cannot write (the header). Each case below runs the real
# set_scene_pref/restore_scene_pref against the fake's closed dir, reads the
# device back by the host paths, and records its findings as lines in
# <rdir>/facts ("ok   text" / "bad  text") through ls_f. The same scenario is
# then run against a mutant, which must produce at least one "bad" line.
LS_SD="$LS_DEV/x1box/states/5454000e"
printf 'PUSHED-STATE' > "$LS/src/heavy2.hxs"

ls_manifest() {   # every name in the title's dir with its mode, then each file's sha256
    find "$LS_SD" -mindepth 1 -printf '%f %m\n' 2>/dev/null | sort
    find "$LS_SD" -mindepth 1 -type f -exec sha256sum {} + 2>/dev/null | sed "s|  $LS_SD/|  |" | sort -k2
}
ls_f() {   # <facts file> <text> <command...>: append "ok   <text>" or "bad  <text>"
    local out="$1" text="$2"; shift 2
    if "$@" >/dev/null 2>&1; then echo "ok   $text" >> "$out"; else echo "bad  $text" >> "$out"; fi
}
ls_facts_show() {   # <rdir>: the facts through ok/bad; with the log and manifest diff when any is bad
    local l
    while IFS= read -r l; do
        case "$l" in
            "ok   "*) ok "${l#ok   }";;
            "bad  "*) bad "${l#bad  }";;
        esac
    done < "$1/facts"
    if grep -q '^bad' "$1/facts"; then
        tail -n 25 "$1/log" 2>/dev/null | sed 's/^/        log: /'
        [ ! -s "$1/manifest.diff" ] || sed 's/^/        manifest: /' "$1/manifest.diff"
    fi
}
ls_facts_red() { grep -q '^bad' "$1/facts"; }   # <rdir>: a mutant's case found something wrong
ls_marker() { ls -A "$LS/dispatch" | grep '^\.scene_files\.' | head -1; }
ls_no_marker() { [ -z "$(ls_marker)" ]; }
ls_log_since() { sed -n "$(($1 + 1)),\$p" "$LS_ADBLOG"; }   # <adb.log line count taken before>
ls_count_since() { ls_log_since "$1" | grep -c -- "$2"; }
ls_no_writes_since() { ! ls_log_since "$1" | grep -qE ' push | shell (cp|mv|rm|touch|mkdir|chmod 660) '; }
ls_has() { case "$1" in *"$2"*) return 0;; esac; return 1; }   # <text> <substring>
ls_lacks() { ! grep -qF -- "$1" "$2"; }                        # <text> <file>

echo "== load-state (k0): the fake device refuses what the real one refuses, and run-as can still write"
ls_reset_device
LS_ADB="$LS/bin/adb" LS_PKG=com.jreinach.hakux.debug
if "$LS_ADB" shell "touch '$LS_SD/probe'" >/dev/null 2>&1; then
    bad "(k0) a plain-shell create worked in the app-only dir (uid $(id -u): the kernel does not refuse root, so no (k) case would prove anything)"
    rm -f "$LS_SD/probe"
else
    ok "(k0) a plain-shell create in the app-only dir is refused"
fi
"$LS_ADB" shell "mv '$LS_SD/slot3.hxs' '$LS_SD/slot3.hxs.hld'" >/dev/null 2>&1
[ -e "$LS_SD/slot3.hxs" ] && [ ! -e "$LS_SD/slot3.hxs.hld" ] && ok "(k0) a plain-shell mv in it is refused" || bad "(k0) a plain-shell mv worked in the app-only dir"
"$LS_ADB" shell "rm -f '$LS_SD/slot3.hxs'" >/dev/null 2>&1
[ -e "$LS_SD/slot3.hxs" ] && ok "(k0) a plain-shell rm in it is refused" || bad "(k0) a plain-shell rm worked in the app-only dir"
"$LS_ADB" push "$LS/src/heavy2.hxs" "$LS_SD/p.new" >/dev/null 2>&1
[ ! -e "$LS_SD/p.new" ] && ok "(k0) an adb push into it is refused" || bad "(k0) an adb push worked in the app-only dir"
[ "$("$LS_ADB" shell "ls '$LS_SD'" | tr '\n' ' ')" = "slot3.hxs slot5.hxs " ] \
    && [ "$("$LS_ADB" shell "stat -c %s '$LS_SD/slot5.hxs'")" = 14 ] \
    && [ "$("$LS_ADB" shell "sha256sum '$LS_SD/slot5.hxs'" | cut -d' ' -f1)" = "$(sha256sum "$LS_SD/slot5.hxs" | cut -d' ' -f1)" ] \
    && ok "(k0) ls, stat and sha256sum still work from the plain shell" || bad "(k0) a read from the plain shell failed in the app-only dir"
"$LS_ADB" shell "run-as $LS_PKG touch '$LS_SD/probe'" >/dev/null 2>&1
[ -e "$LS_SD/probe" ] && [ "$(stat -c %a "$LS_SD")" = 555 ] && ok "(k0) run-as writes into it, and the dir is still closed afterwards" || bad "(k0) run-as could not write the app-only dir"
chmod u+w "$LS_SD"; rm -f "$LS_SD/probe"; chmod u-w "$LS_SD"
"$LS_ADB" shell "run-as $LS_PKG chmod g+w '$LS_SD'" >/dev/null 2>&1
"$LS_ADB" shell "touch '$LS_SD/probe'" >/dev/null 2>&1
[ -e "$LS_SD/probe" ] && [ "$(stat -c %a "$LS_SD")" = 755 ] && ok "(k0) after run-as chmod g+w the plain shell can create in it" || bad "(k0) run-as chmod g+w did not open the dir"
"$LS_ADB" push "$LS/src/heavy2.hxs" "$LS_SD/p.new" >/dev/null 2>&1
[ "$(cat "$LS_SD/p.new" 2>/dev/null)" = PUSHED-STATE ] && ok "(k0) and an adb push lands in it" || bad "(k0) an adb push did not land in the opened dir"
"$LS_ADB" shell "rm -f '$LS_SD/probe' '$LS_SD/p.new'" >/dev/null 2>&1
"$LS_ADB" shell "run-as $LS_PKG chmod g-w '$LS_SD'" >/dev/null 2>&1
"$LS_ADB" shell "touch '$LS_SD/probe'" >/dev/null 2>&1
[ ! -e "$LS_SD/probe" ] && [ "$(stat -c %a "$LS_SD")" = 555 ] && ok "(k0) run-as chmod g-w closes it again" || bad "(k0) run-as chmod g-w did not close the dir"
: > "$LS_FAKE.stuck"
"$LS_ADB" shell "run-as $LS_PKG chmod g+w '$LS_SD'" >/dev/null 2>&1
"$LS_ADB" shell "touch '$LS_SD/probe'" >/dev/null 2>&1
[ ! -e "$LS_SD/probe" ] && [ "$(stat -c %a "$LS_SD")" = 555 ] && ok "(k0) with the stuck fault on, run-as chmod g+w opens nothing" || bad "(k0) the stuck fault did not hold the dir closed"
ls_reset_device

# ls_k1 <dispatcher.sh> <rdir> [open]: a host-file load into slot 5 -- backup,
# push, park, load, restore -- on a closed dir, or an already-open one.
ls_k1() {
    local disp="$1" rdir="$2" kind="${3:-closed}" F="$2/facts" N0 modein=555 wantmb="555 dr-xr-xr-x" wantop=True
    rm -rf "$rdir"; mkdir -p "$rdir"; : > "$F"
    if [ "$kind" = open ]; then modein=755 wantmb="" wantop=False; ls_reset_device open; else ls_reset_device; fi
    ls_req "$rdir/req.json" 5 "$LS/src/heavy2.hxs" ""
    ls_manifest > "$rdir/before"
    N0=$(wc -l < "$LS_ADBLOG")
    (
        ls_src "$disp"
        set_scene_pref "$rdir/req.json" "$rdir" 5454000e; set_rc=$?
        ls_f "$F" "set_scene_pref returned 0 for a host-file load into the $kind dir" [ "$set_rc" = 0 ]
        ls_f "$F" "mid-run the dir is writable by adb shell (mode 755)" [ "$(stat -c %a "$LS_SD")" = 755 ]
        ls_f "$F" "mid-run slot5 holds the pushed state, mode 660" [ "$(cat "$LS_SD/slot5.hxs" 2>/dev/null):$(stat -c %a "$LS_SD/slot5.hxs" 2>/dev/null)" = PUSHED-STATE:660 ]
        ls_f "$F" "mid-run the displaced slot5 is kept as slot5.hxs.orig.hld" [ "$(cat "$LS_SD/slot5.hxs.orig.hld" 2>/dev/null)" = ORIGINAL-SLOT5 ]
        ls_f "$F" "mid-run slot3 is parked, not deleted, and no slot file is left to win the auto-load" \
            [ "$(cat "$LS_SD/slot3.hxs.hld" 2>/dev/null):$([ -e "$LS_SD/slot3.hxs" ] && echo there || echo gone)" = ORIGINAL-SLOT3:gone ]
        ls_f "$F" "mid-run savestate_auto_load is true" ls_pref_is true
        ls_f "$F" "mid-run the marker holds the plan (opened=$wantop, pushed, slot3.hxs, mode '$wantmb')" \
            ls_json "$LS/dispatch/$(ls_marker)" "d['opened'] is $wantop and d['pushed'] is True and d['parked'] == ['slot3.hxs'] and d['mode_before'] == '$wantmb'"
        printf '10-23 12:00:00.000  111  111 I hakuX-lane: [savestate] op=load slot=5 ok=1 build=test\n' > "$rdir/logcat.txt"
        start_scene_watch "$rdir" "$rdir/req.json"
        wait "$SCENE_WATCH_PID" 2>/dev/null
        scene_verdict "$rdir" "$rdir/req.json" testsha > "$rdir/verdict.out"
        ls_f "$F" "the load line is a good load (no void)" [ ! -s "$rdir/verdict.out" ]
        restore_scene_pref; rrc=$?
        ls_f "$F" "restore_scene_pref returned 0" [ "$rrc" = 0 ]
    ) 2> "$rdir/log"
    ls_manifest > "$rdir/after"
    diff "$rdir/before" "$rdir/after" > "$rdir/manifest.diff"
    ls_f "$F" "after restore every file is back: names, modes and sha256 as before" [ ! -s "$rdir/manifest.diff" ]
    ls_f "$F" "after restore the dir mode is $modein again" [ "$(stat -c %a "$LS_SD")" = "$modein" ]
    ls_f "$F" "after restore savestate_auto_load is false again" ls_pref_is false
    ls_f "$F" "after restore no scene marker is left" ls_no_marker
    if [ "$kind" = open ]; then
        ls_f "$F" "an already-open dir is neither chmodded nor closed" [ "$(ls_count_since "$N0" 'chmod g[+-]w')" = 0 ]
        ls_f "$F" "the log does not claim to have opened it" ls_lacks "SCENE: opened" "$rdir/log"
    else
        ls_f "$F" "the dir was opened once and closed once" [ "$(ls_count_since "$N0" 'chmod g+w'):$(ls_count_since "$N0" 'chmod g-w')" = 1:1 ]
        ls_f "$F" "the log names the dir and its mode before and after opening" \
            grep -qF "SCENE: opened $LS_SD for adb shell: 555 dr-xr-xr-x -> 755 drwxr-xr-x (run-as chmod g+w)" "$rdir/log"
        ls_f "$F" "the log names the mode it closed the dir back to" \
            grep -qF "SCENE: closed $LS_SD again: mode 555 dr-xr-xr-x (was 555 dr-xr-xr-x before the run)" "$rdir/log"
    fi
}
echo "== load-state (k1): a closed dir plus a host-file push -- opened, backed up, pushed, parked, loaded, restored"
ls_k1 "$TESTING/dispatcher.sh" "$LS/rdir-k1"
ls_facts_show "$LS/rdir-k1"
echo "== load-state (k1b): the same load into a dir that is already open"
ls_k1 "$TESTING/dispatcher.sh" "$LS/rdir-k1b" open
ls_facts_show "$LS/rdir-k1b"

# ls_k2 <dispatcher.sh> <rdir>: run-as chmod does nothing (a dir run-as cannot open).
ls_k2() {
    local disp="$1" rdir="$2" F="$2/facts" N0 msg
    rm -rf "$rdir"; mkdir -p "$rdir"; : > "$F"
    ls_reset_device; : > "$LS_FAKE.stuck"
    ls_req "$rdir/req.json" 5 "$LS/src/heavy2.hxs" ""
    ls_manifest > "$rdir/before"; cp "$LS_PREFS" "$rdir/prefs.before"
    N0=$(wc -l < "$LS_ADBLOG")
    (
        ls_src "$disp"
        set_scene_pref "$rdir/req.json" "$rdir" 5454000e; echo $? > "$rdir/set.rc"
        printf '%s' "$SCENE_WHY" > "$rdir/why"
    ) 2> "$rdir/log"
    msg="$LS_SD is not writable by adb shell; run-as chmod g+w did not open it"
    ls_f "$F" "set_scene_pref returned 1 for a dir run-as cannot open" [ "$(cat "$rdir/set.rc" 2>/dev/null)" = 1 ]
    ls_f "$F" "the reason is exactly '<sdir> is not writable by adb shell; run-as chmod g+w did not open it'" [ "$(cat "$rdir/why" 2>/dev/null)" = "$msg" ]
    ls_f "$F" "the log carries 'SCENE: <that reason>'" grep -qF "SCENE: $msg" "$rdir/log"
    ls_f "$F" "the log names the dir's mode before and after the chmod" \
        grep -qF "SCENE: $LS_SD mode 555 dr-xr-xr-x -> 555 dr-xr-xr-x after run-as chmod g+w" "$rdir/log"
    ls_manifest > "$rdir/after"; diff "$rdir/before" "$rdir/after" > "$rdir/manifest.diff"
    ls_f "$F" "the dir's files are unchanged" [ ! -s "$rdir/manifest.diff" ]
    ls_f "$F" "the dir's mode is unchanged (555)" [ "$(stat -c %a "$LS_SD")" = 555 ]
    ls_f "$F" "x1box_prefs.xml is unchanged" cmp -s "$rdir/prefs.before" "$LS_PREFS"
    ls_f "$F" "no scene marker is left" ls_no_marker
    ls_f "$F" "no push, cp, mv, rm or touch was sent to the device" ls_no_writes_since "$N0"
}
echo "== load-state (k2): a dir run-as cannot open -- the named failure, and nothing changes"
ls_k2 "$TESTING/dispatcher.sh" "$LS/rdir-k2"
ls_facts_show "$LS/rdir-k2"

# ls_k3 <dispatcher.sh> <rdir> [lie]: the park of slot3 fails (slot1 is parked
# before it and has to come back); with `lie` the mv reports success and moves nothing.
ls_k3() {
    local disp="$1" rdir="$2" kind="${3:-fail}" F="$2/facts" want
    rm -rf "$rdir"; mkdir -p "$rdir"; : > "$F"
    ls_reset_device slot1
    printf "slot3.hxs' '" > "$LS_FAKE.failmv"
    [ "$kind" = lie ] && : > "$LS_FAKE.failmv.lie"
    ls_req "$rdir/req.json" 5 "$LS/src/heavy2.hxs" ""
    ls_manifest > "$rdir/before"
    (
        ls_src "$disp"
        set_scene_pref "$rdir/req.json" "$rdir" 5454000e; echo $? > "$rdir/set.rc"
        printf '%s' "$SCENE_WHY" > "$rdir/why"
    ) 2> "$rdir/log"
    if [ "$kind" = lie ]; then want="slot3.hxs is still in $LS_SD"; else want="could not park slot3.hxs"; fi
    ls_f "$F" "set_scene_pref returned 1: a failed park ($kind) fails the setup" [ "$(cat "$rdir/set.rc" 2>/dev/null)" = 1 ]
    ls_f "$F" "the reason names slot3.hxs ('$want...')" ls_has "$(cat "$rdir/why" 2>/dev/null)" "$want"
    ls_manifest > "$rdir/after"; diff "$rdir/before" "$rdir/after" > "$rdir/manifest.diff"
    ls_f "$F" "every file is back as it was: slot1 (parked before the failure), slot3, and slot5 (pushed, then restored)" [ ! -s "$rdir/manifest.diff" ]
    ls_f "$F" "slot1 is back under its own name, with its own bytes" [ "$(cat "$LS_SD/slot1.hxs" 2>/dev/null)" = ORIGINAL-SLOT1 ]
    ls_f "$F" "slot5 holds its original bytes again" [ "$(cat "$LS_SD/slot5.hxs" 2>/dev/null)" = ORIGINAL-SLOT5 ]
    ls_f "$F" "the dir is closed again (555)" [ "$(stat -c %a "$LS_SD")" = 555 ]
    ls_f "$F" "savestate_auto_load was never turned on" ls_pref_is false
    ls_f "$F" "no scene marker is left" ls_no_marker
}
echo "== load-state (k3): a park that fails -- the setup fails, the files it moved come back"
ls_k3 "$TESTING/dispatcher.sh" "$LS/rdir-k3"
ls_facts_show "$LS/rdir-k3"
echo "== load-state (k3b): a park that reports success and moves nothing -- caught by listing the dir"
ls_k3 "$TESTING/dispatcher.sh" "$LS/rdir-k3b" lie
ls_facts_show "$LS/rdir-k3b"

echo "== load-state (k5): an upper-case title id names the app's lower-case dir"
RDIR="$LS/rdir-k5"; rm -rf "$RDIR"; mkdir -p "$RDIR"; LS_KF="$RDIR/facts"; : > "$LS_KF"
ls_reset_device
ls_req "$RDIR/req.json" 5 "" ""
ls_manifest > "$RDIR/before"
(
    ls_src "$TESTING/dispatcher.sh"
    set_scene_pref "$RDIR/req.json" "$RDIR" 5454000E; set_rc=$?
    ls_f "$LS_KF" "set_scene_pref returned 0 for 5454000E" [ "$set_rc" = 0 ]
    ls_f "$LS_KF" "the marker names .../states/5454000e (lower case)" ls_json "$LS/dispatch/$(ls_marker)" "d['dir'] == '$LS_SD'"
    restore_scene_pref; echo $? > "$RDIR/restore.rc"
) 2> "$RDIR/log"
ls_f "$LS_KF" "restore_scene_pref returned 0" [ "$(cat "$RDIR/restore.rc" 2>/dev/null)" = 0 ]
ls_f "$LS_KF" "the log never spells the dir 5454000E" ls_lacks "5454000E" "$RDIR/log"
ls_manifest > "$RDIR/after"; diff "$RDIR/before" "$RDIR/after" > "$RDIR/manifest.diff"
ls_f "$LS_KF" "every file is back, the dir is closed again" [ "$(stat -c %a "$LS_SD")" = 555 -a ! -s "$RDIR/manifest.diff" ]
ls_facts_show "$RDIR"

echo "== load-state (k6): a title with no states dir -- refused with the reason, nothing created"
RDIR="$LS/rdir-k6"; rm -rf "$RDIR"; mkdir -p "$RDIR"; LS_KF="$RDIR/facts"; : > "$LS_KF"
ls_reset_device
chmod -R u+w "$LS_DEV/x1box/states"; rm -rf "$LS_SD"; chmod 555 "$LS_DEV/x1box/states"
ls_req "$RDIR/req.json" 5 "$LS/src/heavy2.hxs" ""
cp "$LS_PREFS" "$RDIR/prefs.before"
LS_KN0=$(wc -l < "$LS_ADBLOG")
(
    ls_src "$TESTING/dispatcher.sh"
    set_scene_pref "$RDIR/req.json" "$RDIR" 5454000e; echo $? > "$RDIR/set.rc"
    printf '%s' "$SCENE_WHY" > "$RDIR/why"
) 2> "$RDIR/log"
ls_f "$LS_KF" "set_scene_pref returned 1" [ "$(cat "$RDIR/set.rc" 2>/dev/null)" = 1 ]
ls_f "$LS_KF" "the reason says the dir does not exist" ls_has "$(cat "$RDIR/why" 2>/dev/null)" "$LS_SD does not exist"
ls_f "$LS_KF" "no dir was made" [ ! -e "$LS_SD" ]
ls_f "$LS_KF" "x1box_prefs.xml is unchanged" cmp -s "$RDIR/prefs.before" "$LS_PREFS"
ls_f "$LS_KF" "no scene marker is left" ls_no_marker
ls_f "$LS_KF" "nothing was written to the device" ls_no_writes_since "$LS_KN0"
ls_facts_show "$RDIR"

echo "== load-state (k7): a request with no title id -- refused, nothing touched"
RDIR="$LS/rdir-k7"; rm -rf "$RDIR"; mkdir -p "$RDIR"; LS_KF="$RDIR/facts"; : > "$LS_KF"
ls_reset_device
ls_req "$RDIR/req.json" 5 "$LS/src/heavy2.hxs" ""
ls_manifest > "$RDIR/before"
LS_KN0=$(wc -l < "$LS_ADBLOG")
(
    ls_src "$TESTING/dispatcher.sh"
    set_scene_pref "$RDIR/req.json" "$RDIR" ""; echo $? > "$RDIR/set.rc"
    printf '%s' "$SCENE_WHY" > "$RDIR/why"
) 2> "$RDIR/log"
ls_manifest > "$RDIR/after"; diff "$RDIR/before" "$RDIR/after" > "$RDIR/manifest.diff"
ls_f "$LS_KF" "set_scene_pref returned 1" [ "$(cat "$RDIR/set.rc" 2>/dev/null)" = 1 ]
ls_f "$LS_KF" "the reason says the request names no title id" ls_has "$(cat "$RDIR/why" 2>/dev/null)" "names no title id"
ls_f "$LS_KF" "the dir is unchanged and closed" [ "$(stat -c %a "$LS_SD")" = 555 -a ! -s "$RDIR/manifest.diff" ]
ls_f "$LS_KF" "nothing was written to the device" ls_no_writes_since "$LS_KN0"
ls_facts_show "$RDIR"

# ------------------------------------------------ the scene's disk: mutants
echo "== load-state MUTANTS: each reinstates a weaker rule; the check above that refuses it must fail"
LS_MUT_HDD_SET='        elif set_hdd_pref "$want" "$(hdd_pref_marker)" >/dev/null; then'
LS_MUT_BRANCH='            scene_hdd_prepare "$rdir" "$req"; trc=$?'
LS_MUT_OWNER="        hdd-owner-*) echo \"scene hdd '\$n' is the owner's image"
LS_MUT_EXISTS="            none) why=\"scene hdd '\$name' does not exist on the device"
LS_MUT_NOHDD='    [ -n "$load_slot$name" ] || return 0'
LS_MUT_AFTER='scene_hdd_after() {   # <rdir>'
ls_mut() {   # <tag> <old> <new>: LS_M = the mutant's dir, or "" if it could not be built
    LS_M="$LS/mut-$1"
    ls_mirror "$LS_M"
    if ! ls_mutate "$LS_M/dispatcher.sh" "$2" "$3" >/dev/null 2>&1 || cmp -s "$LS_M/dispatcher.sh" "$TESTING/dispatcher.sh"; then
        bad "MUTANT $1: could not build it (the anchor is not in dispatcher.sh exactly once)"
        LS_M=""
    fi
}

ls_mut hddset "$LS_MUT_HDD_SET" '        elif true; then #MUTANT: hddPath never moved'
if [ -n "$LS_M" ]; then
    ls_case_g "$LS_M/dispatcher.sh" "$LS/rdir-m-hddset"
    [ "$(cat "$LS/rdir-m-hddset/pref.midrun" 2>/dev/null)" = "$LS_COPY" ] \
        && bad "MUTANT hddset: hddPath named the copy with the set dropped -- (g) does not see the pref" \
        || ok "MUTANT hddset: with the set dropped, (g)'s mid-run hddPath check fails"
fi

ls_mut branch "$LS_MUT_BRANCH" '            titles_disk_prepare "$id" "$rdir" "$req_env" "$ttid" "$tstate" "$tsave"; trc=$? #MUTANT'
if [ -n "$LS_M" ]; then
    ls_reset_hdd
    ls_serve "$LS_M" "$LS/req-j.json" lsmb
    if [ "$(cat "$LS/dispatch/results/lsmb/soak.hdd" 2>/dev/null)" = "$LS_COPY" ] && ls_owner_intact; then
        bad "MUTANT branch: a scene through the titles disk still booted the copy -- (j) does not see the disk"
    else
        ok "MUTANT branch: through the titles disk the scene boots '$(cat "$LS/dispatch/results/lsmb/soak.hdd" 2>/dev/null)' and (j) fails"
    fi
fi

ls_reset_hdd
ls_mut owner "$LS_MUT_OWNER" "        hdd-owner-MUTANT-*) echo \"scene hdd '\$n' is the owner's image"
if [ -n "$LS_M" ]; then
    [ "$(ls_check_rc "$LS_M/dispatcher.sh" "$LS/rdir-m-owner" hdd-owner-1018.img)" = 3 ] \
        && bad "MUTANT owner: the owner's image is still refused with its refusal dropped" \
        || ok "MUTANT owner: with the refusal dropped the owner's image passes, and (h) fails"
fi

ls_mut exists "$LS_MUT_EXISTS" "            none) return 0;; #MUTANT
            none-MUTANT) why=\"scene hdd '\$name' does not exist on the device"
if [ -n "$LS_M" ]; then
    [ "$(ls_check_rc "$LS_M/dispatcher.sh" "$LS/rdir-m-exists" hdd-scene-missing.img)" = 3 ] \
        && bad "MUTANT exists: a missing disk is still refused with the existence check dropped" \
        || ok "MUTANT exists: with the existence check dropped a missing disk passes, and (h) fails"
fi

ls_mut nohdd "$LS_MUT_NOHDD" '    [ -n "$name" ] || return 0 #MUTANT: a load with no hdd goes through'
if [ -n "$LS_M" ]; then
    [ "$(ls_check_rc "$LS_M/dispatcher.sh" "$LS/rdir-m-nohdd" "")" = 3 ] \
        && bad "MUTANT nohdd: a load naming no hdd is still refused with the rule dropped" \
        || ok "MUTANT nohdd: with the rule dropped a load naming no hdd passes, and (h) fails"
fi

ls_mut after "$LS_MUT_AFTER" 'scene_hdd_after() { return 0 #MUTANT: no restore'
if [ -n "$LS_M" ]; then
    ls_case_g "$LS_M/dispatcher.sh" "$LS/rdir-m-after"
    cmp -s "$LS/prefs.before" "$LS_PREFS" \
        && bad "MUTANT after: the prefs came back with the restore dropped -- (g) does not see the restore" \
        || ok "MUTANT after: with the restore dropped hddPath stays on the copy, and (g) fails"
fi
ls_reset_hdd

# ------------------------------------------------- (k) mutants: the permission
echo "== load-state (k) MUTANTS: the weaker rule each case exists to refuse; that case must go red"
LS_MUT_OPEN='        scene_dir_open "$sdir" || { rm -f "$marker"; return 1; }'
LS_MUT_CLOSE='            scene_dir_chmod "$m_dir" g-w'
LS_MUT_PARK='            || { scene_abort "could not park $f ($sdir/$f.hld): another slot file could win the auto-load"; return 1; }'
LS_MUT_LIST='    if [ -n "$left" ] || [ -s "${ADB_HUNG_FILE:-}" ]; then'

# 1. the dir is never opened: the pre-fix behaviour. The backup cp is the
# first write and the closed dir refuses it, so (k1) fails.
ls_mut dropopen "$LS_MUT_OPEN" '        true #MUTANT: the dir is never opened'
if [ -n "$LS_M" ]; then
    ls_k1 "$LS_M/dispatcher.sh" "$LS/rdir-m-dropopen"
    ls_facts_red "$LS/rdir-m-dropopen" \
        && ok "MUTANT dropopen: with the open step dropped, (k1) goes red ($(grep -c '^bad' "$LS/rdir-m-dropopen/facts") of $(wc -l < "$LS/rdir-m-dropopen/facts") facts)" \
        || bad "MUTANT dropopen: (k1) stayed green with the open step dropped -- the fake lets a closed dir be written"
fi

# 2. restore never closes what the scene opened: the dir is left at 755.
ls_mut noclose "$LS_MUT_CLOSE" '            true #MUTANT: the dir is never closed again'
if [ -n "$LS_M" ]; then
    ls_k1 "$LS_M/dispatcher.sh" "$LS/rdir-m-noclose"
    ls_facts_red "$LS/rdir-m-noclose" \
        && ok "MUTANT noclose: with the close dropped, (k1) goes red ($(grep -c '^bad' "$LS/rdir-m-noclose/facts") of $(wc -l < "$LS/rdir-m-noclose/facts") facts)" \
        || bad "MUTANT noclose: (k1) stayed green with the close dropped"
fi

# 3. a failed park is silent, as `&& parked+=` made it: the status is not
# read and the dir is not listed, so setup goes on with slot3 in place.
ls_mut silentpark "$LS_MUT_PARK" '            || true #MUTANT: a failed park is ignored'
if [ -n "$LS_M" ] && ! ls_mutate "$LS_M/dispatcher.sh" "$LS_MUT_LIST" '    if false; then #MUTANT: the dir is not listed after parking' >/dev/null 2>&1; then
    bad "MUTANT silentpark: could not build the second substitution (the listing check is not in dispatcher.sh exactly once)"
    LS_M=""
fi
if [ -n "$LS_M" ]; then
    ls_k3 "$LS_M/dispatcher.sh" "$LS/rdir-m-silentpark"
    ls_facts_red "$LS/rdir-m-silentpark" \
        && ok "MUTANT silentpark: with a failed park ignored, (k3) goes red ($(grep -c '^bad' "$LS/rdir-m-silentpark/facts") of $(wc -l < "$LS/rdir-m-silentpark/facts") facts)" \
        || bad "MUTANT silentpark: (k3) stayed green with a failed park ignored"
    ls_k3 "$LS_M/dispatcher.sh" "$LS/rdir-m-silentpark-b" lie
    ls_facts_red "$LS/rdir-m-silentpark-b" \
        && ok "MUTANT silentpark: and (k3b) goes red" || bad "MUTANT silentpark: (k3b) stayed green"
fi

# 4. only the listing dropped: a mv that says it worked and did not (the
# fake's lie) now gets through, so (k3b) goes red; a mv that fails loudly is
# still caught by its status, so (k3) stays green -- each check has its own case.
ls_mut nolisting "$LS_MUT_LIST" '    if false; then #MUTANT: the dir is not listed after parking'
if [ -n "$LS_M" ]; then
    ls_k3 "$LS_M/dispatcher.sh" "$LS/rdir-m-nolisting" lie
    ls_facts_red "$LS/rdir-m-nolisting" \
        && ok "MUTANT nolisting: with the post-park listing dropped, (k3b) goes red" \
        || bad "MUTANT nolisting: (k3b) stayed green with the listing dropped"
    ls_k3 "$LS_M/dispatcher.sh" "$LS/rdir-m-nolisting-b"
    ls_facts_red "$LS/rdir-m-nolisting-b" \
        && bad "MUTANT nolisting: (k3) went red too -- the status check alone should still catch a loud failure" \
        || ok "MUTANT nolisting: (k3) stays green: a mv that fails loudly is caught by its status alone"
fi
ls_reset_device

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
# The app-only dirs are host mode 555: open them so selftest.sh's `rm -rf "$T"` can clear them.
chmod -R u+w "$LS" 2>/dev/null
