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
#   s3 ...          Section 3: every staging, route and profile outcome
#                   writes one line to the result dir's inputs.txt (disc:,
#                   route:, profile:) saying where it looked, what it found
#                   and what it did; a recorded route that fails its own
#                   --check (a missing crop) refuses the claim, naming the
#                   crop; the console mirror is a fake, never the real one.
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
             # dev_push hands adb a wslpath -w'd source (#433); wslpath -u
             # round-trips it back to the real path this fake device copies from.
             cp "$(wslpath -u "$local")" "$dest" ;;
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
                 # dispatchdoctor1017 Section 2: dd_gate's own two live reads.
                 # Unset DD_BATTERY_LEVEL simulates an unreadable level (the
                 # generic fallback below would try to run a literal
                 # `dumpsys` on the host and fail the same way, but naming it
                 # here makes the "unreadable" leg's intent readable).
                 dumpsys\ battery*)
                     [ -n "${DD_BATTERY_LEVEL:-}" ] && printf 'level: %s\n' "$DD_BATTERY_LEVEL" ;;
                 ps\ -A\ -o\ NAME*)
                     printf '%s\n' "${DD_PS_OUTPUT:-}" ;;
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
             FREE_FLOOR_BYTES=10240 STAGE_XISO="${DD_STAGE_XISO:-$DD/no-stage_xiso.py}" \
             HAKUX_XISO_DIR="${DD_XISO_DIR:-$DD/xiso}"
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

echo "== dispatch doctor: Section 3, every staging outcome says in the result dir what it found and did"
# Every fixture here points STAGE_XISO at a script that does not exist (or a
# fake below): no leg in this file may reach the real console mirror.
dd_s3_reset() {
    rm -rf "$DD/fs" "$DD/dispatch" "$DD/rdir" "$DD/xiso"
    mkdir -p "$DD/fs$NOVA" "$DD/dispatch/queue" "$DD/dispatch/running" "$DD/rdir" "$DD/xiso"
}
SG="$DD/stage/ABCD0001-Some_Game_Region.xiso.iso"

# --- pushed: the disc line names source, destination, size and the sha check ---
dd_s3_reset; echo '{"title_id":"ABCD0001"}' > "$DD/req.json"
dd_run 999999999999 ensure_title_staged "Some Game (USA).iso" "$DD/rdir" "$DD/req.json"
check "s3 pushed: inputs.txt says 'disc: pushed <src> -> <dst> (2048 bytes, sha checked)'" \
      grep -qxF "disc: pushed $SG -> $NOVA/Some Game (USA).iso (2048 bytes, sha checked)" "$DD/rdir/inputs.txt"

# --- floor: found on staging, not pushed, and the line says why in numbers ---
dd_s3_reset
rc=0; dd_run 10240 ensure_title_staged "Some Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
want="disc: NOT STAGED: found $SG (2048 bytes) but did not push it: $NOVA has 10240 bytes free and must keep 10240 bytes after the push"
if [ "$rc" != 0 ] && grep -qF "$want" "$DD/rdir/inputs.txt"; then
    ok "s3 floor: the refusal names the file it found, the free space and the floor"
else
    bad "s3 floor: rc=$rc inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
fi
out=$(dd_run 10240 stage_summary "$DD/rdir")
case "$out" in
    "staging: found $SG (2048 bytes) but did not push it:"*) ok "s3 floor: stage_summary leads the miss ERROR with what staging found, not 'none had it'" ;;
    *) bad "s3 floor: stage_summary=[$out]" ;;
esac

# --- console paused: not on staging, and the console is not touched ---
dd_s3_reset; touch "$DD/xiso/PAUSE"; echo '{"title_id":"CAFE7777"}' > "$DD/req.json"
rc=0; dd_run 999999999999 ensure_title_staged "Absent Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
if [ "$rc" != 0 ] && grep -qxF "disc: NOT STAGED: no CAFE7777-* image under $DD/stage; console: not tried, $DD/xiso/PAUSE is set" "$DD/rdir/inputs.txt"; then
    ok "s3 console paused: names the roots searched and that PAUSE kept it off the console"
else
    bad "s3 console paused: rc=$rc inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
fi

# --- console answers: a fake stage_xiso.py drops the image on a staging root,
# and the same claim pushes it (Done means #2, against a fixture console) ---
cat > "$DD/fake_stage_xiso.py" <<'PY'
import os, sys
tid = sys.argv[sys.argv.index("--only") + 1]
if os.environ.get("DD_CONSOLE") == "down":
    print("ftp: connection refused"); sys.exit(3)
root = os.environ["HAKUX_STAGING_ROOTS"].split()[0]
open(os.path.join(root, tid + "-Console_Game.xiso.iso"), "wb").write(b"\0" * 2048)
PY
dd_s3_reset; echo '{"title_id":"CAFE7778"}' > "$DD/req.json"
rc=0; DD_STAGE_XISO="$DD/fake_stage_xiso.py" dd_run 999999999999 ensure_title_staged "Console Game (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
if [ "$rc" = 0 ] && [ -f "$DD/fs$NOVA/Console Game (USA).iso" ] \
   && grep -qxF "staged CAFE7778 from the console (console-stage.log)" "$DD/rdir/console-stage.result" \
   && grep -qF "disc: pushed $DD/stage/CAFE7778-Console_Game.xiso.iso -> $NOVA/Console Game (USA).iso" "$DD/rdir/inputs.txt"; then
    ok "s3 console answers: the console's copy is staged, pushed, and both steps are recorded"
else
    bad "s3 console answers: rc=$rc console=[$(cat "$DD/rdir/console-stage.result" 2>/dev/null)] inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
fi
mv "$DD/stage/CAFE7778-Console_Game.xiso.iso" "$DD/console-staged.iso.aside"

# --- console down: the miss says plainly that the console did not answer ---
dd_s3_reset; echo '{"title_id":"CAFE7779"}' > "$DD/req.json"
rc=0; DD_CONSOLE=down DD_STAGE_XISO="$DD/fake_stage_xiso.py" dd_run 999999999999 ensure_title_staged "Console Game 2 (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
if [ "$rc" != 0 ] && grep -qF "console: the console did not answer (stage_xiso.py exit 3); console-stage.log" "$DD/rdir/inputs.txt"; then
    ok "s3 console down: 'the console did not answer' with the mirror's exit code"
else
    bad "s3 console down: rc=$rc inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
fi

# --- no TitleID: the line says why staging was never searched ---
dd_s3_reset; echo '{}' > "$DD/req.json"
rc=0; dd_run 999999999999 ensure_title_staged "No Id Anywhere (USA).iso" "$DD/rdir" "$DD/req.json" || rc=$?
[ "$rc" != 0 ] && grep -qF "disc: NOT STAGED: not looked up, 'No Id Anywhere (USA).iso' has no TitleID" "$DD/rdir/inputs.txt" \
    && ok "s3 no TitleID: says staging was not searched, and why" \
    || bad "s3 no TitleID: rc=$rc inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"

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

echo "== dispatch doctor: Section 3, the route step says which route and why; a missing crop refuses the claim"
# CAFE1003's configured route has a `waitfor` whose crop sits beside it: it
# travels with that crop base64'd in route_refs. CAFE1004's route names a
# crop that is not there: the claim is refused naming the crop, and the
# request is left exactly as queued (no fallback to the generic loop).
cat >> "$DD/route/targets.toml" <<'TOML'
[titles.CAFE1003]
route = "cafe-crops"
[titles.CAFE1004]
route = "cafe-nocrop"
TOML
for r in cafe-crops cafe-nocrop; do
    printf '# state: any\nwaitfor title_screen 10 0,0,10,10 5\nmark gameplay\nwait 1\n' > "$DD/route/routes/$r.route"
done
mkdir -p "$DD/route/routes/refs/cafe-crops"
printf 'PNGBYTES' > "$DD/route/routes/refs/cafe-crops/title_screen.png"
rt_reset() { rm -rf "$DD/rdir"; mkdir -p "$DD/rdir"; }

rt_reset; echo '{}' > "$DD/req1b.json"
rc=0; dd_route_run ensure_route_attached CAFE1003 "Crop Game (USA).iso" "$DD/rdir" "$DD/req1b.json" || rc=$?
refs=$(python3 -c 'import json,sys; print(",".join(sorted((json.load(open(sys.argv[1])).get("route_refs") or {}).keys())))' "$DD/req1b.json" 2>/dev/null)
if [ "$rc" = 0 ] && [ "$(req_field "$DD/req1b.json" route_name)" = cafe-crops ] && [ "$refs" = title_screen.png ] \
   && grep -qF "route: attached 'cafe-crops' for CAFE1003, state=any, 1 reference crop(s); why: the title's configured route in targets.toml" "$DD/rdir/inputs.txt"; then
    ok "s3 route with crops: attached with its crop in route_refs, and inputs.txt says which route and why"
else
    bad "s3 route with crops: rc=$rc route=$(req_field "$DD/req1b.json" route_name) refs=[$refs] inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
fi

rt_reset; echo '{}' > "$DD/req1b.json"
rc=0; dd_route_run ensure_route_attached CAFE1004 "No Crop Game (USA).iso" "$DD/rdir" "$DD/req1b.json" || rc=$?
if [ "$rc" = 3 ] && [ "$(cat "$DD/req1b.json")" = '{}' ] \
   && grep -qF "no reference crop $DD/route/routes/refs/cafe-nocrop/title_screen.png" "$DD/rdir/route.refused" \
   && grep -qF "route: REFUSED: recorded route 'cafe-nocrop' (target) for CAFE1004 fails its own check:" "$DD/rdir/inputs.txt"; then
    ok "s3 route missing crop: the claim is refused (rc=3) naming the missing crop; request untouched"
else
    bad "s3 route missing crop: rc=$rc req=[$(cat "$DD/req1b.json")] refused=[$(cat "$DD/rdir/route.refused" 2>/dev/null)]"
fi

rt_reset; echo '{}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE1002 "Some Proven Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
check "s3 route proven: the why names a judged run that reached gameplay" \
      grep -qF "route: attached 'cafe-proven' for CAFE1002, state=any, 0 reference crop(s); why: proven, a judged run on it reached gameplay" "$DD/rdir/inputs.txt"

rt_reset; echo '{"route_name":"survey"}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE9999 "Some Unknown Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
check "s3 route none: says no recorded route exists and that the requested survey runs" \
      grep -qF "route: none: no proven or recorded route for CAFE9999 (no recorded or proven route); the generic survey does not reach gameplay for most titles; running the survey the request asked for" "$DD/rdir/inputs.txt"

# the lookup itself crashes (a dispatcher snapshot with no targets.toml,
# lane.snaptargets1018's defect): the line says the lookup failed, never
# "no recorded route", and the request runs as queued.
rt_reset; echo '{}' > "$DD/req1b.json"
( export TITLE_TARGETS="$DD/route/no-such-targets.toml" TITLE_ROUTES="$DD/route/routes" \
         DISPATCH_DIR="$DD/route/dispatch"
  . "$DDT/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
  log() { printf '%s\n' "$*" >> "$DD/route.log"; }
  ensure_route_attached CAFE1001 "Some Target Game (USA).iso" "$DD/rdir" "$DD/req1b.json" )
rc=$?
if [ "$rc" = 0 ] && [ "$(cat "$DD/req1b.json")" = '{}' ] \
   && grep -qF "route: none: could not look up a route for CAFE1001, titlestate.py suggest-route failed (FileNotFoundError" "$DD/rdir/inputs.txt" \
   && ! grep -qF "no proven or recorded route" "$DD/rdir/inputs.txt"; then
    ok "s3 route lookup crash: inputs.txt says the lookup failed, not that no route exists"
else
    bad "s3 route lookup crash: rc=$rc req=[$(cat "$DD/req1b.json")] inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
fi

rt_reset; echo '{"route_name":"some-other-route"}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE1001 "Some Target Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
check "s3 route named: a requester's own route is recorded as theirs, untouched" \
      grep -qxF "route: 'some-other-route', named by the request (left as is)" "$DD/rdir/inputs.txt"

rt_reset; echo '{"find_route":"no route recorded for this title yet, finding one"}' > "$DD/req1b.json"
dd_route_run ensure_route_attached CAFE1001 "Some Target Game (USA).iso" "$DD/rdir" "$DD/req1b.json"
if [ -z "$(req_field "$DD/req1b.json" route_name)" ] \
   && grep -qF "route: none attached: the request carries --find-route/--remake-profile/--path-broken" "$DD/rdir/inputs.txt"; then
    ok "s3 route override: --find-route suppresses the attach (the guard 99-profile-gate relied on, now its own leg)"
else
    bad "s3 route override: route=$(req_field "$DD/req1b.json" route_name) inputs=[$(cat "$DD/rdir/inputs.txt" 2>/dev/null)]"
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
check "s3 profile restored: inputs.txt says it restored the first golden from which backup" \
      grep -qxF "profile: restored CAFE1011's first golden from a backup (store: $sid; copied, the backup is untouched)" "$PF/rdir/inputs.txt"

# --- already golden: a second call is a no-op, no search attempted at all ---
rm -f "$PF/rdir/profile-backup.json" "$PF/rdir/inputs.txt"
pf_env ensure_profile_restored CAFE1011 returning "$PF/rdir" "$PF/req.json"
[ ! -f "$PF/rdir/profile-backup.json" ] \
    && ok "1c already golden: a title that already has a golden is left alone, no backup search attempted" \
    || bad "1c already golden: profile-backup.json was written even though CAFE1011 already had a golden"
check "s3 profile golden: inputs.txt names the golden save the disk is composed with" \
      grep -qxF "profile: CAFE1011's golden (save $sid) is in the store; the titles disk is composed with it" "$PF/rdir/inputs.txt"

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
check "s3 profile nothing: inputs.txt lists where it looked and that no profile was created" \
      grep -qxF "profile: CAFE1099 has no golden and no backup was found (looked: store, hdd-reset, archive, device-bak-auto); nothing restored, no profile created" "$PF/rdir/inputs.txt"

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
check "s3 profile verified: inputs.txt records the device-side check by save id" \
      grep -qF "profile: device check: save $sid_a pulled back off" "$PF/rdir/inputs.txt"

# --- verify mismatch: hdd.json claims a real store save that is not really on this image ---
rm -f "$PF/rdir/hdd.refused" "$PF/rdir/hdd.verify.json"
python3 -c 'import json,sys; json.dump({"title_id":"CAFE1015","save":sys.argv[1]}, open(sys.argv[2],"w"))' "$sid_b" "$PF/rdir/hdd.json"
pf_env verify_profile_on_device CAFE1015 returning "$PF/rdir"; rc=$?
if [ "$rc" = 3 ] && [ "$(pf_verify_field verified)" = False ] && [ -s "$PF/rdir/hdd.refused" ]; then
    ok "1c verify mismatch: a claimed save not really on the pushed disk refuses (rc=3), hdd.refused written"
else
    bad "1c verify mismatch: rc=$rc verified=$(pf_verify_field verified) refused=$(cat "$PF/rdir/hdd.refused" 2>/dev/null)"
fi
check "s3 profile verify failed: inputs.txt says the claimed save is not on the pushed disk" \
      grep -qF "profile: device check FAILED: save $sid_b is not on the pushed titles disk" "$PF/rdir/inputs.txt"

# --- verify nothing-loaded: no save claimed is not a failure, same as before this existed ---
rm -f "$PF/rdir/hdd.refused" "$PF/rdir/hdd.verify.json"
echo '{"title_id":"CAFE1015"}' > "$PF/rdir/hdd.json"
pf_env verify_profile_on_device CAFE1015 returning "$PF/rdir"; rc=$?
if [ "$rc" = 0 ] && [ "$(pf_verify_field verified)" = None ] && [ ! -f "$PF/rdir/hdd.refused" ]; then
    ok "1c verify nothing-loaded: no save claimed means nothing to verify, not a failure"
else
    bad "1c verify nothing-loaded: rc=$rc verified=$(pf_verify_field verified) refused=$(cat "$PF/rdir/hdd.refused" 2>/dev/null)"
fi

echo "== dispatch doctor: Section 2, classify/gate/cap and the full diagnose contract"
# dispatch_doctor.sh sources dispatcher.sh the same dummy-arg way pf_env/dd_run
# already do, so it shares the fake adb above -- plus a fake `claude`, since
# diagnose must never spend a real model call in a selftest. The fake claude
# reads DD2_CLAUDE_CTL (set per-leg) off its own environment to decide what to
# write to doctor.md and what JSON shape to emit; HAKUX_BRIEF (set by
# dispatch_doctor.sh itself before invoking claude, same as run-claude-job.sh)
# is how it finds the request's rdir with no argument parsing needed.
DD2="$T/dispatchdoctor2"; rm -rf "$DD2"; mkdir -p "$DD2/stage" "$DD2/work"
DOCTOR_SH="$DDT/dispatch_doctor.sh"

cat > "$DD/bin/claude" <<'EOF'
#!/usr/bin/env bash
brief="${HAKUX_BRIEF:?}"; rdir="$(dirname "$brief")"
case "${DD2_CLAUDE_CTL:-}" in
    windowhit)
        printf '{"type":"result","subtype":"error","is_error":true,"result":"Claude AI usage limit reached|9999999999"}\n'
        exit 0 ;;
    maxturns)
        printf '{"type":"result","subtype":"error_max_turns","is_error":true,"result":"hit the cap"}\n'
        exit 0 ;;
    noverdict)
        printf 'looked at it, made no decision\n' > "$rdir/doctor.md" ;;
    retry:*)
        action="${DD2_CLAUDE_CTL#retry:}"
        bash "${DD2_DOCTOR_SH:?}" fix "$action" "$rdir" > "$rdir/fix-output.txt" 2>&1
        printf 'ran fix %s; it reported success\nretry\n' "$action" > "$rdir/doctor.md" ;;
    give-up:*)
        printf 'looked at it, nothing applies\n%s\n' "${DD2_CLAUDE_CTL}" > "$rdir/doctor.md" ;;
    *)
        printf 'fixture default\ngive-up: no DD2_CLAUDE_CTL set for this leg\n' > "$rdir/doctor.md" ;;
esac
printf '{"type":"result","subtype":"success","is_error":false,"result":"ok","total_cost_usd":0.01}\n'
EOF
chmod +x "$DD/bin/claude"

# dd2_env <subcommand + args...>: dispatch_doctor.sh itself, sandboxed --
# DISPATCH_DIR and HAKUX_WORK both under $DD2 (HAKUX_WORK matters only for
# window.sh's limits.tsv, so a windowhit leg never writes outside the
# fixture), the fake adb+claude on PATH, SERIAL matching the fake device.
dd2_env() {
    ( export PATH="$DD/bin:$PATH" DD_FS="$DD2/fs" NOVA="$NOVA" \
             DD_CAPACITY_BYTES="$DD/capacity.bytes" SERIAL=ee317437 \
             DISPATCH_DIR="$DD2/dispatch" HAKUX_WORK="$DD2/work" \
             HAKUX_STAGING_ROOTS="$DD2/stage" FREE_FLOOR_BYTES=10240 \
             DD2_DOCTOR_SH="$DOCTOR_SH" DD2_CLAUDE_CTL="${DD2_CLAUDE_CTL:-}" \
             DD_PS_OUTPUT="${DD_PS_OUTPUT:-}" DD_BATTERY_LEVEL="${DD_BATTERY_LEVEL-90}" \
             BATTERY_CACHE_S=0 DOCTOR_TIMEOUT=30s DOCTOR_TURNS=4 \
             STAGE_XISO="$DD/no-stage_xiso.py" HAKUX_XISO_DIR="$DD/xiso"
      bash "$DOCTOR_SH" "$@" )
}
dd2_reset() {
    rm -rf "$DD2/dispatch" "$DD2/work" "$DD2/fs" "$DD2/rdir"
    mkdir -p "$DD2/dispatch/queue" "$DD2/dispatch/running" "$DD2/dispatch/results" "$DD2/dispatch/logs" \
             "$DD2/work" "$DD2/fs$NOVA" "$DD2/rdir"
    echo 999999999999 > "$DD/capacity.bytes"
}
# mr_env <id> <rdir>: dispatcher.sh's own maybe_run_doctor (Section 3), in
# the same sandbox dd2_env gives dispatch_doctor.sh -- it calls through to
# the real $DOCTOR_SH via $HERE, so the fake adb/claude above cover that
# nested call too. Tests the ERROR-enrichment wiring, not diagnose's
# contract again (that's dd2_env's job, above).
mr_env() {
    ( export PATH="$DD/bin:$PATH" DD_FS="$DD2/fs" NOVA="$NOVA" \
             DD_CAPACITY_BYTES="$DD/capacity.bytes" SERIAL=ee317437 \
             DISPATCH_DIR="$DD2/dispatch" HAKUX_WORK="$DD2/work" \
             HAKUX_STAGING_ROOTS="$DD2/stage" FREE_FLOOR_BYTES=10240 \
             DD2_DOCTOR_SH="$DOCTOR_SH" DD2_CLAUDE_CTL="${DD2_CLAUDE_CTL:-}" \
             DD_PS_OUTPUT="${DD_PS_OUTPUT:-}" DD_BATTERY_LEVEL="${DD_BATTERY_LEVEL-90}" \
             BATTERY_CACHE_S=0 DOCTOR_TIMEOUT=30s DOCTOR_TURNS=4 \
             STAGE_XISO="$DD/no-stage_xiso.py" HAKUX_XISO_DIR="$DD/xiso"
      . "$DDT/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      maybe_run_doctor "$@" )
}

# --- classify: the brief's named recoverable classes, matched off ERROR's
# first line (plus a logcat grep for the crash/ANR variant). One check per
# class, and one ERROR text classify must NOT recognise (a build failure --
# the doctor is never billed for a class nobody taught it). ---
dd2_classify_is() {   # <want> <err text> [<logcat text>]
    dd2_reset
    printf '%s\n' "$2" > "$DD2/rdir/ERROR"
    [ -n "${3:-}" ] && printf '%s\n' "$3" > "$DD2/rdir/logcat.txt"
    out=$(dd2_env classify "$DD2/rdir"); rc=$?
    if [ "$1" = NONE ]; then
        [ "$rc" != 0 ] && [ -z "$out" ] \
            && ok "classify: '$2' is not a recognised class (no model session billed on it)" \
            || bad "classify: '$2' got rc=$rc out=[$out], wanted no class"
    else
        [ "$rc" = 0 ] && [ "$out" = "$1" ] \
            && ok "classify: '$2' -> $1" \
            || bad "classify: '$2' got rc=$rc out=[$out], wanted $1"
    fi
}
dd2_classify_is title-not-on-device "staging searched sweep, xiso, none had it; title not on device: /storage/x/Some Game.iso"
dd2_classify_is install-failed "install failed"
dd2_classify_is titles-disk-failed "could not prepare the titles disk; see dispatcher.log"
dd2_classify_is env-vars-failed "could not set the requested env_vars pref; see dispatcher.log"
dd2_classify_is zero-captures "ran but produced 0 captures; see run1.log and captures1/"
dd2_classify_is zero-captures-crash "0 captures: emulator started and CRASHED after 4s"
dd2_classify_is zero-captures-crash "ran but produced 0 captures; see run1.log and captures1/" "FATAL EXCEPTION: main"
dd2_classify_is zero-captures-interop-exhausted "adb interop failure: 0 captures, and run1.log carries the WSL UtilAcceptVsock signature -- the captures were lost between device and host, not unrendered; this was the one requeue, so it is final"
dd2_classify_is NONE "build failed for ref a1b2c3d4"
dd2_classify_is NONE "refusing to install: it reports applicationId com.jreinach.hakux (the release package)"

# --- gate: a hold, the owner playing, an unreadable level, a level under
# the admit floor, and a clean admit -- in that order, per dd_gate's own
# priority. ---
dd2_reset
mkdir -p "$DD2/dispatch/hold"; echo "Halo work has priority" > "$DD2/dispatch/hold/nova.why"
touch "$DD2/dispatch/hold/nova"
out=$(DD_PS_OUTPUT="" DD_BATTERY_LEVEL=90 dd2_env gate nova)
case "$out" in
    "refuse: device held: Halo work has priority") ok "gate: a hold file refuses, naming its .why" ;;
    *) bad "gate: hold -> [$out]" ;;
esac
rm -f "$DD2/dispatch/hold/nova" "$DD2/dispatch/hold/nova.why"

out=$(DD_PS_OUTPUT="com.jreinach.hakux:xemu" DD_BATTERY_LEVEL=90 dd2_env gate nova)
case "$out" in
    refuse:*"owner is playing"*) ok "gate: the release package running refuses as owner-play" ;;
    *) bad "gate: owner-play -> [$out]" ;;
esac

out=$(DD_PS_OUTPUT="" DD_BATTERY_LEVEL="" dd2_env gate nova)
case "$out" in
    refuse:*"unreadable"*) ok "gate: an unreadable battery level fails closed" ;;
    *) bad "gate: unreadable battery -> [$out]" ;;
esac

out=$(DD_PS_OUTPUT="" DD_BATTERY_LEVEL=10 dd2_env gate nova)
case "$out" in
    refuse:*"below the admit floor"*) ok "gate: a level under the admit floor refuses" ;;
    *) bad "gate: low battery -> [$out]" ;;
esac

out=$(DD_PS_OUTPUT="" DD_BATTERY_LEVEL=90 dd2_env gate nova)
[ "$out" = admit ] && ok "gate: no hold, no owner-play, battery well above the floor -> admit" \
    || bad "gate: clean admit -> [$out]"

# --- cap: the hourly cap (rows this fixture writes itself, so no real
# session needs to run to exercise it) and the per-id cap (an id that
# already has a row gets no second session, even hours later). ---
dd2_reset
TSV2="$DD2/dispatch/logs/dispatch-doctor.tsv"; mkdir -p "$(dirname "$TSV2")"
now=$(date +%s)
for i in 1 2 3; do printf '%s\told-%s\tinstall-failed\tgive-up: x\t1\n' "$now" "$i" >> "$TSV2"; done
out=$(DISPATCH_DOCTOR_HOURLY_CAP=3 dd2_env cap new-id "$DD2/rdir")
case "$out" in
    refuse:*"last hour"*) ok "cap: the hourly cap (3) refuses a 4th session in the trailing hour" ;;
    *) bad "cap: hourly -> [$out]" ;;
esac
out=$(DISPATCH_DOCTOR_HOURLY_CAP=10 dd2_env cap new-id "$DD2/rdir")
[ "$out" = ok ] && ok "cap: a wider hourly cap admits the same id" || bad "cap: wider hourly -> [$out]"
old=$((now - 7200))
printf '%s\told-4\tinstall-failed\tretry\t5\n' "$old" >> "$TSV2"
out=$(DISPATCH_DOCTOR_HOURLY_CAP=10 dd2_env cap old-4 "$DD2/rdir")
case "$out" in
    refuse:*"one doctor attempt"*) ok "cap: a request that already has a row gets no second session, hours later" ;;
    *) bad "cap: per-id -> [$out]" ;;
esac

# --- fix push-iso: the model's own narrow wrapper derives title/ttid from
# request.json and calls through to the same ensure_title_staged this
# lane's Section 1 already proved -- no duplicated staging logic. ---
dd2_reset
head -c 2048 /dev/zero > "$DD2/stage/BEEF2001-Some_Fixable_Game.xiso.iso"
echo '{"title":"Some Fixable Game (USA).iso","title_id":"BEEF2001"}' > "$DD2/rdir/request.json"
out=$(dd2_env fix push-iso "$DD2/rdir"); rc=$?
pushed="$DD2/fs$NOVA/Some Fixable Game (USA).iso"
if [ "$rc" = 0 ] && [ -f "$pushed" ]; then
    ok "fix push-iso: derives the title from request.json and pushes it via ensure_title_staged"
else
    bad "fix push-iso: rc=$rc out=[$out] pushed=$([ -f "$pushed" ] && echo yes || echo no)"
fi
dd2_reset
echo '{"title":"Nothing Staged Anywhere (USA).iso","title_id":"DEAD0000"}' > "$DD2/rdir/request.json"
out=$(dd2_env fix push-iso "$DD2/rdir"); rc=$?
[ "$rc" != 0 ] && ok "fix push-iso: a title on no staging root reports failure, not a false success" \
    || bad "fix push-iso: wrongly reported success -- out=[$out]"

# --- diagnose: the full contract, end to end. ---
# gate/cap refusals short-circuit with no model call and no TSV row (the cap
# counts sessions that actually ran, not every ERROR the doctor glanced at).
dd2_reset
mkdir -p "$DD2/dispatch/hold"; touch "$DD2/dispatch/hold/nova"
printf 'install failed\n' > "$DD2/rdir/ERROR"
echo '{"title":"X.iso"}' > "$DD2/rdir/request.json"
out=$(DEVICE_LABEL=nova dd2_env diagnose req-gate "$DD2/rdir")
if printf '%s' "$out" | grep -q '^VERDICT give-up: refuse: device held' \
   && [ ! -s "$TSV2" -o "$(wc -l < "$TSV2" 2>/dev/null)" = 0 ]; then
    ok "diagnose: a held device gives up with no model call and no TSV row"
else
    bad "diagnose: gate short-circuit -> [$out], tsv=$(cat "$TSV2" 2>/dev/null)"
fi
rm -f "$DD2/dispatch/hold/nova"

# retry: the fake claude runs fix push-iso (the ERROR's title really is on
# a staging root) and writes `retry`; diagnose logs one TSV row and one
# doctor-lessons.md line.
dd2_reset
head -c 2048 /dev/zero > "$DD2/stage/CAFE3001-Retry_Game.xiso.iso"
printf 'install failed\n' > "$DD2/rdir/ERROR"
echo '{"title":"Retry Game (USA).iso","title_id":"CAFE3001"}' > "$DD2/rdir/request.json"
out=$(DEVICE_LABEL=nova DD2_CLAUDE_CTL="retry:push-iso" dd2_env diagnose req-retry "$DD2/rdir")
tsv_row=$(grep -F $'\treq-retry\t' "$DD2/dispatch/logs/dispatch-doctor.tsv" 2>/dev/null)
if printf '%s' "$out" | grep -qx 'VERDICT retry' \
   && [ -f "$DD2/fs$NOVA/Retry Game (USA).iso" ] \
   && [ -n "$tsv_row" ] \
   && grep -q "install-failed" <<< "$tsv_row" \
   && grep -q "install-failed -> retry" "$DD2/dispatch/doctor-lessons.md" 2>/dev/null; then
    ok "diagnose retry: the model's fix lands, VERDICT retry, one TSV row and lessons line"
else
    bad "diagnose retry: out=[$out] pushed=$([ -f "$DD2/fs$NOVA/Retry Game (USA).iso" ] && echo yes || echo no) tsv=[$tsv_row]"
fi

# give-up via the model: no fix applies, the model says so, still one row.
dd2_reset
printf 'could not prepare the titles disk; see dispatcher.log\n' > "$DD2/rdir/ERROR"
echo '{"title":"No Fix Applies (USA).iso"}' > "$DD2/rdir/request.json"
out=$(DEVICE_LABEL=nova DD2_CLAUDE_CTL="give-up: nothing in the inventory explains it" dd2_env diagnose req-giveup "$DD2/rdir")
if printf '%s' "$out" | grep -qF 'VERDICT give-up: nothing in the inventory explains it' \
   && grep -qF "req-giveup" "$DD2/dispatch/logs/dispatch-doctor.tsv" 2>/dev/null; then
    ok "diagnose give-up: the model's own reason becomes the verdict, and still logs a row"
else
    bad "diagnose give-up: out=[$out]"
fi

# the account's usage window: exit-75 shaped JSON gives up on the WINDOW,
# not the failure, records it the same way run-claude-job.sh does, and
# never writes outside this fixture's own sandboxed HAKUX_WORK.
dd2_reset
printf 'install failed\n' > "$DD2/rdir/ERROR"
echo '{"title":"X.iso"}' > "$DD2/rdir/request.json"
out=$(DEVICE_LABEL=nova DD2_CLAUDE_CTL=windowhit dd2_env diagnose req-window "$DD2/rdir")
if printf '%s' "$out" | grep -qF "VERDICT give-up: hit the account's usage window" \
   && [ -s "$DD2/work/window/limits.tsv" ]; then
    ok "diagnose window: an exit-75-shaped run gives up on the window, not the failure, and records it sandboxed"
else
    bad "diagnose window: out=[$out] limits.tsv=$(cat "$DD2/work/window/limits.tsv" 2>/dev/null)"
fi

# no verdict line at all: still a row, a readable reason, never silent.
dd2_reset
printf 'install failed\n' > "$DD2/rdir/ERROR"
echo '{"title":"X.iso"}' > "$DD2/rdir/request.json"
out=$(DEVICE_LABEL=nova DD2_CLAUDE_CTL=noverdict dd2_env diagnose req-noverdict "$DD2/rdir")
printf '%s' "$out" | grep -qF "VERDICT give-up: the doctor session wrote no doctor.md verdict line" \
    && ok "diagnose no-verdict: a session that wrote no retry/give-up line still ends in a readable give-up" \
    || bad "diagnose no-verdict: out=[$out]"

echo "== dispatch doctor: Section 3, maybe_run_doctor enriches the ERROR a human reads"
# retry: the ERROR line gains "doctor: retry (see doctor.md)" and travels
# with the moved-aside result dir -- a reader of $rdir.doctor1/ERROR sees
# both the original failure and the doctor's decision with no other file.
dd2_reset
head -c 2048 /dev/zero > "$DD2/stage/CAFE4001-ErrText_Game.xiso.iso"
printf 'install failed\n' > "$DD2/rdir/ERROR"
echo '{"title":"ErrText Game (USA).iso","title_id":"CAFE4001"}' > "$DD2/rdir/request.json"
DEVICE_LABEL=nova DD2_CLAUDE_CTL="retry:push-iso" mr_env errtext-retry "$DD2/rdir" > /dev/null
aside="$DD2/rdir.doctor1"
if [ -f "$aside/ERROR" ] && grep -qxF "install failed" "$aside/ERROR" \
   && grep -qxF "doctor: retry (see doctor.md)" "$aside/ERROR" \
   && [ ! -e "$DD2/rdir" ]; then
    ok "maybe_run_doctor retry: ERROR gains 'doctor: retry (see doctor.md)', moves aside with the dir"
else
    bad "maybe_run_doctor retry: aside=[$aside] error=[$(cat "$aside/ERROR" 2>/dev/null)] rdir-exists=$([ -e "$DD2/rdir" ] && echo yes || echo no)"
fi

# give-up via the model: the ERROR stays in place (no retry, no move) and
# gains the model's own reason.
dd2_reset
printf 'could not prepare the titles disk; see dispatcher.log\n' > "$DD2/rdir/ERROR"
echo '{"title":"No Fix Applies (USA).iso"}' > "$DD2/rdir/request.json"
DEVICE_LABEL=nova DD2_CLAUDE_CTL="give-up: nothing in the inventory explains it" \
    mr_env errtext-giveup "$DD2/rdir" > /dev/null
if [ -e "$DD2/rdir" ] && grep -qxF "could not prepare the titles disk; see dispatcher.log" "$DD2/rdir/ERROR" \
   && grep -qxF "doctor: give-up: nothing in the inventory explains it (see doctor.md)" "$DD2/rdir/ERROR"; then
    ok "maybe_run_doctor give-up: ERROR gains the model's reason, dir stays put"
else
    bad "maybe_run_doctor give-up: error=[$(cat "$DD2/rdir/ERROR" 2>/dev/null)]"
fi

# a class the doctor does not recognise: no doctor.md ever gets written, so
# the ERROR line names that plainly instead of claiming "see doctor.md".
dd2_reset
printf 'build failed for ref deadbeef\n' > "$DD2/rdir/ERROR"
echo '{"title":"X.iso"}' > "$DD2/rdir/request.json"
mr_env errtext-unclassified "$DD2/rdir" > /dev/null
if grep -qxF "doctor: give-up: not a class the doctor recognises" "$DD2/rdir/ERROR" \
   && [ ! -f "$DD2/rdir/doctor.md" ]; then
    ok "maybe_run_doctor unclassified: ERROR says so with no false 'see doctor.md'"
else
    bad "maybe_run_doctor unclassified: error=[$(cat "$DD2/rdir/ERROR" 2>/dev/null)] doctor.md=$([ -f "$DD2/rdir/doctor.md" ] && echo exists || echo none)"
fi

# an empty request.json: nothing to requeue, so the doctor does not run and
# the ERROR is left exactly as written (99-iso-roots.sh reads the miss
# ERROR's suffix on just such a dir).
dd2_reset
printf 'install failed\n' > "$DD2/rdir/ERROR"
: > "$DD2/rdir/request.json"
DEVICE_LABEL=nova DD2_CLAUDE_CTL="retry:push-iso" mr_env errtext-empty "$DD2/rdir" > /dev/null
if [ -e "$DD2/rdir" ] && [ "$(cat "$DD2/rdir/ERROR")" = "install failed" ] \
   && [ ! -f "$DD2/rdir/doctor.md" ]; then
    ok "maybe_run_doctor empty request: no doctor session, the ERROR is untouched"
else
    bad "maybe_run_doctor empty request: error=[$(cat "$DD2/rdir/ERROR" 2>/dev/null)] doctor.md=$([ -f "$DD2/rdir/doctor.md" ] && echo exists || echo none)"
fi

echo "== dispatch doctor: Section 2, classify replays real dispatch history (Done means #5)"
# One real ERROR per still-current-format recoverable class, read-only, off
# the live dispatch tree's own history -- never copied content is edited,
# never a real result dir is touched. "title not on device" keeps
# device_title_miss's text as the ERROR's tail in every format this lane
# has written (pre-lane bare, Section 1 "staging searched ...", Section 3
# "staging: <what staging found>; ..."), and dd_classify matches it
# anywhere in the line, so the ~45 pre-lane results replay as they are; the
# two classify_is lines after the replays pin the Section 1 and Section 3
# wordings, which no real result carries yet.
REALD="/home/justin/hakux-work/dispatch/results"
dd2_replay() {   # <want class> <grep pattern>
    local want="$1" pat="$2" f out
    f=$(grep -lF "$pat" "$REALD"/*/ERROR 2>/dev/null | head -1)
    if [ -z "$f" ]; then
        ok "replay $want: no real result on disk currently carries '$pat' (nothing to replay, not a failure)"
        return
    fi
    dd2_reset
    cp "$f" "$DD2/rdir/ERROR"
    [ -f "$(dirname "$f")/logcat.txt" ] && cp "$(dirname "$f")/logcat.txt" "$DD2/rdir/logcat.txt"
    out=$(dd2_env classify "$DD2/rdir")
    [ "$out" = "$want" ] \
        && ok "replay $want: $f classifies correctly against the real ERROR text" \
        || bad "replay $want: $f -> [$out], wanted $want ($(head -1 "$f"))"
}
dd2_replay install-failed "install failed"
dd2_replay titles-disk-failed "could not prepare the titles disk"
dd2_replay env-vars-failed "could not set the requested env_vars pref"
dd2_replay zero-captures "ran but produced 0 captures"
dd2_replay title-not-on-device "title not on device"
dd2_classify_is title-not-on-device "staging searched sweep, xiso, lanelocal-1, none had it; title not on device: /storage/388C-68F7/ROMS/xbox/Jet Set Radio Future (USA).xiso.iso"
dd2_classify_is title-not-on-device "staging: no 4D530004-* image under /mnt/d/hakux-staging/sweep /mnt/d/hakux-staging/xiso; console: the console did not answer (stage_xiso.py exit 2); console-stage.log; title not on device: Jet Set Radio Future (USA).xiso.iso -- searched /storage/E6C6-D7AA/Games/XBox"
