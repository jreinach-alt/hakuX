# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# affinity: the lane registration, and saying so when there is none.
# Landed on master as an append to selftest.sh (#126, lane/armpin); carried
# here unchanged when that fold met this split.
#
# Builds its own dispatch tree under $T/aff, but the last group writes into
# the real $DISPATCH_DIR/splits and reads it back through status.sh, so it
# runs after the arms fragments. LAST in the order, as it was on master.
#
# Starts a `sleep 600 &` as a certainly-live pid and kills it at the end; a
# fragment inserted after this one must not rely on $LIVEPID.

echo "== affinity: the lane registration, and saying so when there is none"
# WHY. On 2026-09-19 #89's A/B pair ran base on the `thor` and fix on the
# `nova`. affinity.py exists to stop exactly that, and it was INERT: $D/lanes/
# was empty, so serving() returned [], so rule 2's _live() was false for a
# device that was in fact serving and rule 3 had no devices to hash over. The
# lane pid file was written once per worker process, so a single `rm` by
# anyone disabled pinning until the dispatcher was restarted -- and no log
# line, no status field and no note reachable by a reader said a word.
#
# These checks pin the three things that were missing, not the remover, which
# is still unidentified (NOTES.md on lane/armpin has the refuted hypotheses).
export AD="$T/aff"; mkdir -p "$AD"/{lanes,running,results,splits,queue,logs}
export TESTING AFF="$TESTING/affinity.py"
sleep 600 & export LIVEPID=$!               # a pid that is certainly alive
sleep 0   & DEADPID=$!; wait $DEADPID 2>/dev/null   # and one that certainly is not
disp() {   # run shell inside a sourced dispatcher.sh, as the nova, against $AD
    ( export DISPATCH_DIR="$AD" SERIAL=ee317437 DISPATCH_TREE="$REPO" DISPATCH_REPO="$REPO"
      . "$TESTING/dispatcher.sh" selftest-not-a-subcommand >/dev/null 2>&1
      eval "$1" )
}

# --- serving(): the single input every rule above is decided over.
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
printf '%s\n' "$DEADPID" > "$AD/lanes/thor"
printf '%s\n' "2026-09-14" > "$AD/lanes/remote.lastbrief"   # check_coverage.py's stamp
check "serving lists the lane whose pid is alive and not the one whose pid is dead" \
    [ "$(python3 "$AFF" "$AD" --serving 2>/dev/null)" = "nova" ]
# Counted, not grepped for absence: "no lastbrief in the output" is also true
# of no output at all, and a check that a missing feature satisfies has
# measured nothing. Three files in lanes/, exactly one device.
check "a <lane>.lastbrief stamp sharing the directory is not mistaken for a device" \
    [ "$(python3 "$AFF" "$AD" --serving 2>/dev/null | wc -w)" = 1 ]

# --- the two behaviours the brief says must stay true. CONTROLS: these pass
# against the old file too, and are here to show the fix did not buy its
# visibility by making a pin block a claim.
mkdir -p "$AD/results/r-old"
printf '{"expect":"/p/e7d2.json"}\n' > "$AD/results/r-old/request.json"
printf '{"device_label":"thor"}\n'   > "$AD/results/r-old/result.json"
printf '{"requester":"arms-x-fix","expect":"/p/e7d2.json"}\n' > "$AD/q.req"
check "CONTROL: a pin to a device that is NOT serving falls through rather than stalling" \
    [ -z "$(python3 "$AFF" "$AD" "$AD/q.req" 2>/dev/null)" ]
printf '{"device_label":"nova"}\n' > "$AD/results/r-old/result.json"
check "CONTROL: a pin to a device that IS serving is still honoured" \
    [ "$(python3 "$AFF" "$AD" "$AD/q.req" 2>/dev/null)" = "nova" ]

# --- the fallthrough must stop being silent. This is the defect: every rule
# ran over an empty device set and printed the same "" a request with no
# sibling prints.
rm -rf "$AD/lanes" "$AD/splits"; mkdir -p "$AD/lanes" "$AD/splits"
python3 "$AFF" "$AD" "$AD/q.req" >/dev/null 2>&1
check "a request that could not be pinned AT ALL leaves a note" \
    bash -c '[ -n "$(ls "$AD"/splits/*.blind.txt 2>/dev/null)" ]'
check "the note names the prediction whose pair may now split" \
    bash -c 'grep -q "e7d2.json" "$AD"/splits/*.blind.txt'
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"; printf '%s\n' "$LIVEPID" > "$AD/lanes/thor"
rm -f "$AD"/splits/*.blind.txt
python3 "$AFF" "$AD" "$AD/q.req" >/dev/null 2>&1
check "CONTROL: a request pinned normally leaves no blind note" \
    bash -c '[ -z "$(ls "$AD"/splits/*.blind.txt 2>/dev/null)" ]'

# --- the lane file itself. It was written once per process; that permanence,
# not the removal, is what cost five hours.
# Chained with && throughout, never `;`. Sequenced with `;` these all pass
# against a file that has no lane_claim in it at all -- the missing function
# fails, nothing is ever created, and "the file is absent" comes out true.
check "lane_claim restores a registration removed from outside, so a removal costs a tick not a restart" \
    disp 'lane_claim && rm -f "$D/lanes/nova" && lane_claim && [ "$(cat "$D/lanes/nova")" = "$$" ]'
check "lane_release drops my own registration" \
    disp 'lane_claim && [ -e "$D/lanes/nova" ] && lane_release && [ ! -e "$D/lanes/nova" ]'
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
check "lane_release SUCCEEDS and leaves a registration holding ANOTHER pid (a dead predecessor cannot evict its live successor)" \
    disp 'lane_release && [ "$(cat "$D/lanes/nova")" = "'"$LIVEPID"'" ]'
check "no lane file is removed by name anywhere; every removal goes through lane_release" \
    bash -c '! grep -q "rm -f \"\$D/lanes/" "$TESTING/dispatcher.sh"'
check "the registration is re-asserted after the hold check, not only at worker startup" \
    python3 -c 'import sys; s=open(sys.argv[1]).read(); i=s.index("$D/hold/$DEVICE_LABEL"); sys.exit(0 if "lane_claim" in s[i:] else 1)' "$TESTING/dispatcher.sh"
check "a held device does not re-register itself thirty seconds later" \
    python3 -c 'import sys; s=open(sys.argv[1]).read(); h=s.index("$D/hold/$DEVICE_LABEL"); sys.exit(0 if s.index("lane_claim", h) > s.index("lane_release", h) else 1)' "$TESTING/dispatcher.sh"

# --- the dispatcher must say it out loud, once, not per claim.
rm -rf "$AD/lanes"; mkdir -p "$AD/lanes"; : > "$AD/logs/dispatcher.log"
disp 'lane_blind_check one; lane_blind_check two' >/dev/null 2>&1
check "claiming with no lane registered logs AFFINITY BLIND" \
    grep -q "AFFINITY BLIND" "$AD/logs/dispatcher.log"
check "it is logged once per outage, not once per claim (the sweep queues one request per suite)" \
    [ "$(grep -c 'AFFINITY BLIND' "$AD/logs/dispatcher.log")" = 1 ]
: > "$AD/logs/dispatcher.log"
check "the outage has an END as well as a start: coming back is logged too" \
    disp 'lane_blind_check one && printf "%s\n" "'"$LIVEPID"'" > "$D/lanes/nova" && lane_blind_check two &&
          grep -q "AFFINITY BLIND" "$D/logs/dispatcher.log" && grep -q "lanes registered again" "$D/logs/dispatcher.log"'
: > "$AD/logs/dispatcher.log"
printf '%s\n' "$LIVEPID" > "$AD/lanes/nova"
check "a claim made with a lane registered logs nothing at all" \
    disp 'lane_blind_check one && lane_blind_check two && [ ! -s "$D/logs/dispatcher.log" ]'

# --- $D/splits/ gets a reader. The note was always written correctly; it was
# discoverable only by someone who already suspected it and knew the path.
mkdir -p "$DISPATCH_DIR/splits" "$DISPATCH_DIR/lanes"
printf 'prediction e7d2d739.json was pinned to thor, which is not serving; freed this request\n' \
    > "$DISPATCH_DIR/splits/1789793572-arms-blitsafe-fix-3718905.req.txt"
sout=$(bash "$HERE/status.sh" --print 2>&1)
check "status.sh reports what affinity is doing at all" grep -q '^- affinity:' <<< "$sout"
check "status.sh warns when no lane is registered and pinning is inert" \
    grep -q 'no device lane is registered' <<< "$sout"
check "status.sh surfaces a recent split note, with the prediction in it" \
    grep -q 'e7d2d739.json was pinned to thor' <<< "$sout"
kill "$LIVEPID" 2>/dev/null; wait "$LIVEPID" 2>/dev/null
