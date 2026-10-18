# Sourced by ../selftest.sh with the harness already built: $T, $TESTING,
# ok/bad/check. Not executable, no shebang, no exit -- `fail` is shared.
#
# dispatchdoctor1017 Section 1: a soak whose title missed every device root
# (devices.sh device_title_path) no longer ERRORs immediately. dispatcher.sh
# now tries staging_find_tid (devices.sh: a host D: staging root, matched by
# the TitleID HEAD) and, if the push would leave the device under
# FREE_FLOOR_BYTES free, make_room_for_push -- which deletes an on-device ISO
# only when it is unclaimed by any queued or running request AND verifies by
# sha256 against a copy this host still holds on D:.
#
# Driven against a fake adb: `push` copies into a fake fs, `pull` copies back
# out of it (added for Section 1c's dev_pull use), and `shell` runs real
# coreutils against the same fake fs with /storage/ remapped under it --
# so sha256sum, stat, chmod, mv, rm and ls all behave exactly as the real
# device's shell would, except `df -k`, which is special-cased to report
# capacity-minus-actual-file-bytes so a deletion or a push moves the reported
# free space exactly, in bytes, with no filesystem block rounding to chase.
#
# THE LEGS:
#   staging find   staging_find_tid matches by TitleID head, not full name.
#   sha sidecar     staging_file_sha reads a `.sha` sidecar rather than
#                   recomputing -- proven by a sidecar that is WRONG on
#                   purpose; a recompute would not have returned it.
#   stage           device empty, plenty of room: the title is pushed under
#                   the REQUEST's own title string, not the staging file's.
#   floor refuses   device empty, capacity == the floor exactly: nothing to
#                   delete, the push is refused, nothing lands.
#   room            an unclaimed, D:-verified ISO on the device is deleted to
#                   clear the floor, then the push lands.
#   claimed kept    the same ISO, but a queued request names its title_id:
#                   it is kept, the floor stays short, the push is refused.
#
# Section 1b (ensure_route_attached, claim-time fallback for a request that
# named no route): a proven route (dispatch/results history, "mark
# gameplay" plus a reached_gameplay verdict) outranks a merely-configured
# targets.toml one; neither is invented when nothing is known or proven;
# and a request already naming its own route is never touched. The same
# suggest-route/route-refs titlestate.py subcommands drive request.sh's
# queue-time attach (97-dispatch-deploy.sh does not cover this; smoke-tested
# by hand against request.sh directly while writing this -- see NOTES.md).

echo "== dispatch doctor: the staging fast path finds, verifies and clears room for a missing title"
DD="$T/dispatchdoctor"; rm -rf "$DD"; mkdir -p "$DD/bin" "$DD/stage"
DDT="${DD_TESTING:-$TESTING}"
NOVA="/storage/E6C6-D7AA/Games/XBox"

cat > "$DD/bin/adb" <<'EOF'
#!/usr/bin/env bash
[ "$1" = -s ] && shift 2
case "$1" in
    devices) printf 'List of devices attached\nee317437\tdevice\n' ;;
    push)    local="$2" remote="$3"
             dest="${remote//\/storage\//$DD_FS/storage/}"
             mkdir -p "$(dirname "$dest")" 2>/dev/null
             cp "$local" "$dest" ;;
    pull)    remote="$2" local="$3"
             src="${remote//\/storage\//$DD_FS/storage/}"
             mkdir -p "$(dirname "$local")" 2>/dev/null
             cp "$src" "$local" 2>/dev/null ;;
    shell)   shift; cmd="$*"
             case "$cmd" in
                 df\ -k*)
                     used=$(find "$DD_FS$NOVA" -type f -exec stat -c %s {} + 2>/dev/null \
                            | awk '{s+=$1} END{print s+0}')
                     cap=$(cat "$DD_CAPACITY_BYTES" 2>/dev/null || echo 999999999999)
                     printf '/dev/x %s 1 %s 1%% /storage\n' $((cap/1024)) $(((cap-used)/1024)) ;;
                 *) sh -c "${cmd//\/storage\//$DD_FS/storage/}" | sed "s#$DD_FS##g" ;;
             esac ;;
esac
exit 0
EOF
chmod +x "$DD/bin/adb"

# dd_run <capacity bytes> <function + args...>: a fresh fake device (empty
# NOVA root unless the leg populates it first), DISPATCH_DIR under $DD, the
# fixture's stage/ as the only staging root, floor 10240 bytes (10 KiB).
dd_run() {
    local cap="$1"; shift
    echo "$cap" > "$DD/capacity.bytes"
    ( export PATH="$DD/bin:$PATH" DD_FS="$DD/fs" NOVA="$NOVA" \
             DD_CAPACITY_BYTES="$DD/capacity.bytes" \
             DISPATCH_DIR="$DD/dispatch" HAKUX_STAGING_ROOTS="$DD/stage" \
             FREE_FLOOR_BYTES=10240
      . "$DDT/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      device_env ee317437 >/dev/null
      log() { :; }
      "$@" )
}

# --- staging find / sha sidecar: no device, no dispatch dir needed ---
mkdir -p "$DD/stage"
head -c 2048 /dev/zero > "$DD/stage/ABCD0001-Some_Game_Region.xiso.iso"
printf '%064d\n' 0 | tr '0' 'a' > "$DD/stage/ABCD0001-Some_Game_Region.xiso.iso.sha"   # deliberately wrong
out=$(dd_run 1 staging_find_tid abcd0001)
[ "$out" = "$DD/stage/ABCD0001-Some_Game_Region.xiso.iso" ] \
    && ok "staging find: a lowercase title id matches the staged file's (uppercase) head" \
    || bad "staging find: got [$out]"
out=$(dd_run 1 staging_file_sha "$DD/stage/ABCD0001-Some_Game_Region.xiso.iso")
[ "$out" = "$(printf '%064d' 0 | tr '0' a)" ] \
    && ok "sha sidecar: staging_file_sha reads the (wrong-on-purpose) sidecar, not a recompute" \
    || bad "sha sidecar: got [$out]"
rm -f "$DD/stage/ABCD0001-Some_Game_Region.xiso.iso.sha"   # real sha from here on

# --- stage: empty device, plenty of room ---
rm -rf "$DD/fs" "$DD/dispatch" "$DD/rdir"; mkdir -p "$DD/fs$NOVA" "$DD/dispatch/queue" "$DD/dispatch/running" "$DD/rdir"
echo '{"title_id":"ABCD0001"}' > "$DD/req.json"
rc=0; dd_run 999999999999 ensure_title_staged "Some Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
pushed="$DD/fs$NOVA/Some Game (USA).iso"
if [ "$rc" = 0 ] && [ -f "$pushed" ] && cmp -s "$pushed" "$DD/stage/ABCD0001-Some_Game_Region.xiso.iso"; then
    ok "stage: pushed under the REQUEST's title string, matching the staged file's bytes"
else
    bad "stage: rc=$rc, pushed=$([ -f "$pushed" ] && echo yes || echo no)"
fi

# --- floor refuses: device empty, capacity == the floor exactly ---
rm -rf "$DD/fs" "$DD/dispatch" "$DD/rdir"; mkdir -p "$DD/fs$NOVA" "$DD/dispatch/queue" "$DD/dispatch/running" "$DD/rdir"
rc=0; dd_run 10240 ensure_title_staged "Some Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
[ "$rc" != 0 ] && [ ! -f "$DD/fs$NOVA/Some Game (USA).iso" ] \
    && ok "floor refuses: nothing to clear, the push does not happen" \
    || bad "floor refuses: rc=$rc, pushed=$([ -f "$DD/fs$NOVA/Some Game (USA).iso" ] && echo yes || echo no)"

# --- room: an unclaimed, D:-verified on-device ISO is deleted to clear it ---
# capacity 14336: 4096 used by FEED0002 leaves 10240 free, short of 10240 +
# the 2048 the push needs; freeing FEED0002's 4096 leaves exactly 14336 free,
# enough for the push and the floor besides.
rm -rf "$DD/fs" "$DD/dispatch" "$DD/rdir"; mkdir -p "$DD/fs$NOVA" "$DD/dispatch/queue" "$DD/dispatch/running" "$DD/rdir"
head -c 4096 /dev/zero > "$DD/fs$NOVA/FEED0002-Old_Game.xiso.iso"
head -c 4096 /dev/zero > "$DD/stage/FEED0002-Old_Game.xiso.iso"
rc=0; dd_run 14336 ensure_title_staged "Some Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
if [ "$rc" = 0 ] && [ -f "$DD/fs$NOVA/Some Game (USA).iso" ] && [ ! -f "$DD/fs$NOVA/FEED0002-Old_Game.xiso.iso" ] \
   && grep -q 'deleted FEED0002-Old_Game.xiso.iso' "$DD/rdir/room.log" 2>/dev/null; then
    ok "room: the unclaimed, D:-verified ISO is deleted and logged, then the push lands"
else
    bad "room: rc=$rc, old=$([ -f "$DD/fs$NOVA/FEED0002-Old_Game.xiso.iso" ] && echo kept || echo gone), new=$([ -f "$DD/fs$NOVA/Some Game (USA).iso" ] && echo yes || echo no)"
fi

# --- claimed kept: the same ISO, but a queued request names its title_id ---
rm -rf "$DD/fs" "$DD/dispatch" "$DD/rdir"; mkdir -p "$DD/fs$NOVA" "$DD/dispatch/queue" "$DD/dispatch/running" "$DD/rdir"
head -c 4096 /dev/zero > "$DD/fs$NOVA/FEED0002-Old_Game.xiso.iso"
echo '{"title_id":"FEED0002","title":"Old Game (USA).iso"}' > "$DD/dispatch/queue/other.req"
rc=0; dd_run 14336 ensure_title_staged "Some Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
if [ "$rc" != 0 ] && [ -f "$DD/fs$NOVA/FEED0002-Old_Game.xiso.iso" ] && [ ! -f "$DD/fs$NOVA/Some Game (USA).iso" ]; then
    ok "claimed kept: a queued request's title is never deleted to make room, so the push stays refused"
else
    bad "claimed kept: rc=$rc, old=$([ -f "$DD/fs$NOVA/FEED0002-Old_Game.xiso.iso" ] && echo kept || echo gone)"
fi

echo "== dispatch doctor: Section 1b, the dispatcher attaches a recorded route to a soak that named none"
# A title id CAFE1001 gets a route only from targets.toml (unproven: "target"
# source). CAFE1002 gets one only from dispatch/results history (a route
# whose text declares `mark gameplay`, reached by a judged, reached_gameplay
# result: "proven" source, titlestate.py's own known_path/proven_route).
# CAFE9999 has neither -- nothing to attach, same as before this existed.
mkdir -p "$DD/route/routes" "$DD/route/dispatch/results/1-1700000000-cp-1"
cat > "$DD/route/targets.toml" <<'TOML'
[titles.CAFE1001]
route = "cafe-target"
TOML
cat > "$DD/route/routes/cafe-target.route" <<'ROUTE'
# state: any
mark gameplay
wait 1
ROUTE
cat > "$DD/route/routes/cafe-proven.route" <<'ROUTE'
# state: any
mark gameplay
wait 1
ROUTE
cat > "$DD/route/routes/survey.route" <<'ROUTE'
# state: any
wait 1
ROUTE
python3 -c '
import json
json.dump({"title": "CAFE1002-Proven_Game.iso", "route_name": "cafe-proven"},
          open("'"$DD"'/route/dispatch/results/1-1700000000-cp-1/request.json", "w"))
json.dump({"reached_gameplay": True},
          open("'"$DD"'/route/dispatch/results/1-1700000000-cp-1/verdict.json", "w"))
'

# dd_route_run <function + args...>: dispatcher.sh sourced with TITLE_TARGETS
# and TITLE_ROUTES pointed at the fixture above, DISPATCH_DIR at its own
# dispatch/ (so title_routes/reached_result see the "proven" result), and
# log() appended to route.log instead of discarded, so a leg can check what
# ensure_route_attached said about why it did or did not attach.
dd_route_run() {
    : > "$DD/route.log"
    ( export TITLE_TARGETS="$DD/route/targets.toml" TITLE_ROUTES="$DD/route/routes" \
             DISPATCH_DIR="$DD/route/dispatch"
      . "$DDT/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      log() { printf '%s\n' "$*" >> "$DD/route.log"; }
      "$@" )
}
req_field() { python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get(sys.argv[2]) or "")' "$1" "$2"; }

# --- target: no route named, nothing proven, targets.toml has one ---
echo '{}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE1001 "Some Target Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
if [ "$(req_field "$DD/req1b.json" route_name)" = cafe-target ] \
   && grep -q "mark gameplay" <(req_field "$DD/req1b.json" route) \
   && grep -q "auto-attached 'cafe-target' (target)" "$DD/route.log"; then
    ok "1b target: an unproven, targets.toml-configured route is attached and logged"
else
    bad "1b target: route_name=$(req_field "$DD/req1b.json" route_name), log=$(cat "$DD/route.log")"
fi

# --- proven: no route named, dispatch history proves one, outranks a target ---
echo '{}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE1002 "Some Proven Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
if [ "$(req_field "$DD/req1b.json" route_name)" = cafe-proven ] \
   && grep -q "auto-attached 'cafe-proven' (proven)" "$DD/route.log"; then
    ok "1b proven: a route proven by dispatch history is attached, preferred over a merely-configured one"
else
    bad "1b proven: route_name=$(req_field "$DD/req1b.json" route_name), log=$(cat "$DD/route.log")"
fi

# --- nothing known: no route named, nothing proven, nothing configured ---
echo '{}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE9999 "Some Unknown Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
if [ -z "$(req_field "$DD/req1b.json" route_name)" ] && grep -q "no recorded or proven route" "$DD/route.log"; then
    ok "1b nothing known: no route is invented; the request is left exactly as queued"
else
    bad "1b nothing known: route_name=$(req_field "$DD/req1b.json" route_name), log=$(cat "$DD/route.log")"
fi

# --- already named: a request that already names a specific route is untouched ---
echo '{"route_name":"some-other-route","route":"# state: any\nwait 1\n"}' > "$DD/req1b.json"
before=$(cat "$DD/req1b.json")
dd_route_run ensure_route_attached CAFE1001 "Some Target Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
after=$(cat "$DD/req1b.json")
if [ "$before" = "$after" ]; then
    ok "1b already named: a request naming its own route is never overridden by the claim-time fallback"
else
    bad "1b already named: request.json changed: before=[$before] after=[$after]"
fi

echo "== dispatch doctor: Section 1c, profile-backup discovery/restore before launch, and post-push verification"
# ensure_profile_restored looks, in order, at: a save already in the store but
# never promoted (titlestate.py backup-candidates, kind=store); an HDD-GUARD
# reset's saves/<TID> tree (same subcommand, kind=hdd-reset); a
# nova-archive-*/lanelocal-* staging root's saves/<TID> tree
# (archive_backup_dir); this device's own hdd.img.bak-auto
# (device_bak_auto_dir). First one found is restored as the title's FIRST
# golden only -- never a replace, and never a search at all once a golden
# already exists. verify_profile_on_device then pulls back whatever
# titles_disk_prepare pushed (or kept) and confirms the claimed save is
# really on it with saves.py list, refusing (hdd.refused, rc=3) on a
# mismatch the way compose's own NoGolden does.
PF="$DD/profile"; rm -rf "$PF"; mkdir -p "$PF/fs"
PFTS="$DDT/titles/titlestate.py"

# pf_mksave <outdir> <tid> -> prints the save_id: a save dir shaped like
# saves.py's own pull output (save.json + UDATA/<tid>/<12-hex>/data.bin), its
# save_id hashed for real so import_save's own re-hash check passes. Carries
# the two ancestor "dir" entries (UDATA/<tid>, UDATA/<tid>/<12-hex>) that a
# real saves.py pull always records alongside a file -- FatxWriter.add_file
# creates them on build() regardless of what save.json lists, and pull()'s
# own walk() always re-discovers them, so a savedir round-tripped through
# pf_build_image + a real device pull (device_bak_auto_dir) comes back with
# those two extra entries. save_id() ignores "times", only path+sha256/dir,
# so this value is stable across that round trip either way; omitting the
# dirs here (as an earlier version did) made the store/hdd-reset/archive
# legs -- which import_save straight off this directory, no image involved
# -- pass on a self-consistent but round-trip-incompatible id, and only the
# device-bak-auto leg's real build+pull caught the mismatch.
pf_mksave() {
    python3 - "$1" "$2" <<'PY'
import hashlib, json, os, sys
outdir, tid = sys.argv[1], sys.argv[2]
rel = f"UDATA/{tid}/BEEFBEEFBEEF/data.bin"
os.makedirs(os.path.dirname(os.path.join(outdir, rel)), exist_ok=True)
data = f"profile-backup-fixture-{tid}-{outdir}".encode()
open(os.path.join(outdir, rel), "wb").write(data)
sha = hashlib.sha256(data).hexdigest()
m = {"title_id": tid, "entries": [
    {"path": f"UDATA/{tid}", "dir": True, "times": {}},
    {"path": f"UDATA/{tid}/BEEFBEEFBEEF", "dir": True, "times": {}},
    {"path": rel, "dir": False, "bytes": len(data), "sha256": sha, "times": {}},
]}
h = hashlib.sha256()
for e in sorted(m["entries"], key=lambda e: e["path"]):
    h.update(f"{e['path'].upper()}\0{e.get('sha256', 'dir')}\n".encode())
m["save_id"] = h.hexdigest()[:12]
json.dump(m, open(os.path.join(outdir, "save.json"), "w"))
print(m["save_id"])
PY
}
# pf_build_image <out qcow2> <savedir>: a real FATX/qcow2 image carrying one
# save, the same way saves.py's own CLI would build it (99-hdd-split.sh's
# pattern) -- device_bak_auto_dir and verify_profile_on_device both read a
# real image, not a stand-in.
pf_build_image() {
    python3 -c '
import sys
sys.path.insert(0, sys.argv[1]); import saves
saves.build(sys.argv[2], [sys.argv[3]])
' "$DDT/titles" "$1" "$2"
}
# pf_env <function + args...>: dispatcher.sh sourced with DISPATCH_DIR and
# TITLESTATE_DIR under $PF, HAKUX_STAGING_ROOTS pointed at the fixture's own
# nova-archive-x root, and the fake adb (now with a `pull` case) on PATH.
pf_env() {
    : > "$PF/log"
    ( export DISPATCH_DIR="$PF/dispatch" TITLESTATE_DIR="$PF/dispatch/titlestate" \
             HAKUX_STAGING_ROOTS="$PF/archive/nova-archive-x" \
             SERIAL=ee317437 PATH="$DD/bin:$PATH" DD_FS="$PF/fs" ADB_RETRY_SLEEP=0
      . "$DDT/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      log() { printf '%s\n' "$*" >> "$PF/log"; }
      "$@" )
}
pf_golden_save() {   # <tid>: the save id of a title's golden, or empty
    python3 -c 'import json,sys
try: g=json.load(open(sys.argv[1]))["titles"].get(sys.argv[2],{}).get("golden")
except Exception: g=None
print((g or {}).get("save") or "")' "$PF/dispatch/titlestate/golden.json" "$1" 2>/dev/null
}
pf_pb_field() {   # <field>: a field out of $PF/rdir/profile-backup.json
    python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get(sys.argv[2]))
except Exception: print("<missing>")' "$PF/rdir/profile-backup.json" "$1" 2>/dev/null
}
pf_verify_field() {   # <field>: a field out of $PF/rdir/hdd.verify.json
    python3 -c 'import json,sys
try: print(json.load(open(sys.argv[1])).get(sys.argv[2]))
except Exception: print("<missing>")' "$PF/rdir/hdd.verify.json" "$1" 2>/dev/null
}
TDEV="$PF/fs/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box"

# --- store: a save already in the store (never promoted) is the first golden ---
rm -rf "$PF/dispatch" "$PF/rdir" "$PF/scratch"; mkdir -p "$PF/dispatch" "$PF/rdir" "$PF/scratch/a"
sid=$(pf_mksave "$PF/scratch/a" CAFE1011)
TITLESTATE_DIR="$PF/dispatch/titlestate" python3 "$PFTS" import-save --dir "$PF/scratch/a" >/dev/null
echo '{}' > "$PF/req.json"
pf_env ensure_profile_restored CAFE1011 returning "$PF/rdir" "$PF/req.json"
if [ "$(pf_golden_save CAFE1011)" = "$sid" ] && [ "$(pf_pb_field found)" = store ] && [ "$(pf_pb_field restored)" = True ]; then
    ok "1c store: CAFE1011's own unpromoted store save becomes its first golden (kind=store)"
else
    bad "1c store: golden-save=$(pf_golden_save CAFE1011) want=$sid found=$(pf_pb_field found) restored=$(pf_pb_field restored); log: $(cat "$PF/log")"
fi

# --- already golden: a second call is a no-op, no search attempted at all ---
rm -f "$PF/rdir/profile-backup.json"
pf_env ensure_profile_restored CAFE1011 returning "$PF/rdir" "$PF/req.json"
[ ! -f "$PF/rdir/profile-backup.json" ] \
    && ok "1c already golden: a title that already has a golden is left alone, no backup search attempted" \
    || bad "1c already golden: profile-backup.json was written even though CAFE1011 already had a golden"

# --- hdd-reset: an HDD-GUARD reset's saves/<TID> tree is the first golden ---
rm -rf "$PF/dispatch" "$PF/rdir"; mkdir -p "$PF/dispatch/hdd-reset/2026-10-17T00-00-00/saves" "$PF/rdir"
sid=$(pf_mksave "$PF/dispatch/hdd-reset/2026-10-17T00-00-00/saves/CAFE1012" CAFE1012)
echo '{}' > "$PF/req.json"
pf_env ensure_profile_restored CAFE1012 returning "$PF/rdir" "$PF/req.json"
if [ "$(pf_golden_save CAFE1012)" = "$sid" ] && [ "$(pf_pb_field found)" = hdd-reset ] && [ "$(pf_pb_field restored)" = True ]; then
    ok "1c hdd-reset: a reset's exported saves/<TID> tree becomes the first golden (kind=hdd-reset)"
else
    bad "1c hdd-reset: golden-save=$(pf_golden_save CAFE1012) want=$sid found=$(pf_pb_field found) restored=$(pf_pb_field restored); log: $(cat "$PF/log")"
fi

# --- archive: a nova-archive-x staging root's saves/<TID> tree is the first golden ---
rm -rf "$PF/dispatch" "$PF/rdir" "$PF/archive"; mkdir -p "$PF/dispatch" "$PF/archive/nova-archive-x/saves" "$PF/rdir"
sid=$(pf_mksave "$PF/archive/nova-archive-x/saves/CAFE1013" CAFE1013)
echo '{}' > "$PF/req.json"
pf_env ensure_profile_restored CAFE1013 returning "$PF/rdir" "$PF/req.json"
if [ "$(pf_golden_save CAFE1013)" = "$sid" ] && [ "$(pf_pb_field found)" = archive ] && [ "$(pf_pb_field restored)" = True ]; then
    ok "1c archive: a staging-archive saves/<TID> tree becomes the first golden (kind=archive)"
else
    bad "1c archive: golden-save=$(pf_golden_save CAFE1013) want=$sid found=$(pf_pb_field found) restored=$(pf_pb_field restored); log: $(cat "$PF/log")"
fi

# --- device-bak-auto: only this device's own hdd.img.bak-auto has it ---
rm -rf "$PF/dispatch" "$PF/rdir" "$PF/fs" "$PF/scratch"; mkdir -p "$PF/dispatch" "$PF/rdir" "$TDEV" "$PF/scratch/d"
sid=$(pf_mksave "$PF/scratch/d" CAFE1014)
pf_build_image "$TDEV/hdd.img.bak-auto" "$PF/scratch/d"
echo '{}' > "$PF/req.json"
pf_env ensure_profile_restored CAFE1014 returning "$PF/rdir" "$PF/req.json"
if [ "$(pf_golden_save CAFE1014)" = "$sid" ] && [ "$(pf_pb_field found)" = device-bak-auto ] && [ "$(pf_pb_field restored)" = True ]; then
    ok "1c device-bak-auto: the device's own hdd.img.bak-auto is pulled, listed and imported as the first golden"
else
    bad "1c device-bak-auto: golden-save=$(pf_golden_save CAFE1014) want=$sid found=$(pf_pb_field found) restored=$(pf_pb_field restored); log: $(cat "$PF/log")"
fi
check "  ... the bak-auto pull's scratch files are cleaned up" \
      test ! -e "$PF/dispatch/titlestate/pull/dev-bak-auto.img" -a ! -e "$PF/dispatch/titlestate/pull/dev-bak-auto-CAFE1014"

# --- nothing found: no backup anywhere leaves a readable trail, nothing invented ---
rm -rf "$PF/dispatch" "$PF/rdir" "$PF/fs" "$PF/archive"; mkdir -p "$PF/dispatch" "$PF/rdir" "$PF/fs"
echo '{}' > "$PF/req.json"
pf_env ensure_profile_restored CAFE1099 returning "$PF/rdir" "$PF/req.json"
if [ "$(pf_pb_field found)" = None ] && [ "$(pf_pb_field searched)" = "['store', 'hdd-reset', 'archive', 'device-bak-auto']" ]; then
    ok "1c nothing found: profile-backup.json records all four places looked, found=null, nothing invented"
else
    bad "1c nothing found: found=$(pf_pb_field found) searched=$(pf_pb_field searched)"
fi

# --- first-run: never triggers a backup search, even when a backup exists ---
rm -rf "$PF/dispatch" "$PF/rdir"; mkdir -p "$PF/dispatch/hdd-reset/2026-10-17T00-00-00/saves" "$PF/rdir"
pf_mksave "$PF/dispatch/hdd-reset/2026-10-17T00-00-00/saves/CAFE1017" CAFE1017 >/dev/null
echo '{}' > "$PF/req.json"
pf_env ensure_profile_restored CAFE1017 first-run "$PF/rdir" "$PF/req.json"
if [ ! -f "$PF/rdir/profile-backup.json" ] && [ -z "$(pf_golden_save CAFE1017)" ]; then
    ok "1c first-run: a first-run route is skipped even though a backup exists, no golden created"
else
    bad "1c first-run: profile-backup.json exists=$([ -f "$PF/rdir/profile-backup.json" ] && echo yes || echo no), golden-save=$(pf_golden_save CAFE1017)"
fi

# --- verify: the pushed titles disk really carries the save hdd.json claims.
# Two DIFFERENT saves for CAFE1015 (distinct content -> distinct save_id),
# both genuinely imported into the store so `store-dir` resolves to a real
# save.json either way; the device image is built from save A only. Claiming
# A verifies; claiming B (a real store save, just not the one on this image)
# is the faithful "disk pushed but not really carrying this save" mismatch --
# content differs under the same path, not a missing store dir to crash on.
rm -rf "$PF/dispatch" "$PF/rdir" "$PF/fs" "$PF/scratch"
mkdir -p "$PF/dispatch" "$PF/rdir" "$TDEV" "$PF/scratch/g" "$PF/scratch/h"
sid_a=$(pf_mksave "$PF/scratch/g" CAFE1015)
sid_b=$(pf_mksave "$PF/scratch/h" CAFE1015)
TITLESTATE_DIR="$PF/dispatch/titlestate" python3 "$PFTS" import-save --dir "$PF/scratch/g" >/dev/null
TITLESTATE_DIR="$PF/dispatch/titlestate" python3 "$PFTS" import-save --dir "$PF/scratch/h" >/dev/null
pf_build_image "$TDEV/titles.qcow2" "$PF/scratch/g"
python3 -c 'import json,sys; json.dump({"title_id":"CAFE1015","save":sys.argv[1]}, open(sys.argv[2],"w"))' "$sid_a" "$PF/rdir/hdd.json"
pf_env verify_profile_on_device CAFE1015 returning "$PF/rdir"; rc=$?
if [ "$rc" = 0 ] && [ "$(pf_verify_field verified)" = True ] && [ ! -f "$PF/rdir/hdd.refused" ]; then
    ok "1c verify ok: the pushed disk's claimed save is confirmed present (rc=0)"
else
    bad "1c verify ok: rc=$rc verified=$(pf_verify_field verified) refused=$(cat "$PF/rdir/hdd.refused" 2>/dev/null)"
fi

# --- verify mismatch: hdd.json claims a real store save that is not really on this image ---
rm -f "$PF/rdir/hdd.refused" "$PF/rdir/hdd.verify.json"
python3 -c 'import json,sys; json.dump({"title_id":"CAFE1015","save":sys.argv[1]}, open(sys.argv[2],"w"))' "$sid_b" "$PF/rdir/hdd.json"
pf_env verify_profile_on_device CAFE1015 returning "$PF/rdir"; rc=$?
if [ "$rc" = 3 ] && [ "$(pf_verify_field verified)" = False ] && [ -s "$PF/rdir/hdd.refused" ]; then
    ok "1c verify mismatch: a claimed save not really on the pushed disk refuses (rc=3), hdd.refused written"
else
    bad "1c verify mismatch: rc=$rc verified=$(pf_verify_field verified) refused=$(cat "$PF/rdir/hdd.refused" 2>/dev/null)"
fi

# --- verify nothing-loaded: no save claimed is not a failure, same as before this existed ---
rm -f "$PF/rdir/hdd.refused" "$PF/rdir/hdd.verify.json"
echo '{"title_id":"CAFE1015"}' > "$PF/rdir/hdd.json"
pf_env verify_profile_on_device CAFE1015 returning "$PF/rdir"; rc=$?
if [ "$rc" = 0 ] && [ "$(pf_verify_field verified)" = None ] && [ ! -f "$PF/rdir/hdd.refused" ]; then
    ok "1c verify nothing-loaded: no save claimed means nothing to verify, not a failure"
else
    bad "1c verify nothing-loaded: rc=$rc verified=$(pf_verify_field verified) refused=$(cat "$PF/rdir/hdd.refused" 2>/dev/null)"
fi
