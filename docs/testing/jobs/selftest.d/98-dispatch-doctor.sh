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
# Driven against a fake adb: `push` copies into a fake fs, and `shell` runs
# real coreutils against the same fake fs with /storage/ remapped under it --
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
