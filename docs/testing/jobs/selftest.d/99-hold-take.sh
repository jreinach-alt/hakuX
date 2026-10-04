# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# jobs/hold.sh: a hold is taken only when free and removed only by its taker.
#
# THE INCIDENT, 2026-09-26. The host update window held the Thor (16:58:52
# PDT); a lane took it anyway, overwrote hold/thor.why, and removed hold/thor
# at 17:02:28; fifteen seconds later the Thor claimed a request inside the
# window. Legs (b) and (c) replay that: the host holds, the lane tries to take
# and then to release, and the host's two files must come out byte-identical.
#
# Each leg names the world in which it fails:
#   (a) take on a free device writes a file that is not the tag (a bare
#       touch, as the host tools did): release could then never tell whose
#       hold it is.
#   (b) take overwrites or rewrites an existing hold or its .why (the
#       incident's first half) -- a naive `touch hold/x; echo > x.why`.
#   (c) release removes a hold that is not the caller's (the incident's
#       second half) -- a naive `rm -f hold/x hold/x.why`.
#   (d) release by the right taker leaves either file behind, so the device
#       stays out of service or keeps a stale reason.
#   (e) take is a check-then-create rather than O_EXCL, so two takers both
#       see "free" and both report success.
#   (f) a running request blocks take (the brief says it must not: a hold
#       stops new claims only), or `wait` never gives up.
#   (g) wait-idle, the 2026-10-01 incident (lane.holdwait): legs g1-g8,
#       listed with their failing worlds where they start.
#
# SELFTEST_HOLD_SH points the legs at another implementation; the lane's
# NOTES.md runs them against a naive touch/rm version that way.
#
# Uses its own DISPATCH_DIR, never the harness's shared one and never the
# host's real hold/ directory.

echo "== hold.sh: a hold is removed only by its taker"

HT_SH="${SELFTEST_HOLD_SH:-$HERE/hold.sh}"
HT_D="$T/holdtake/dispatch"
mkdir -p "$HT_D/running"
ht() { DISPATCH_DIR="$HT_D" HOLD_WAIT_INTERVAL=1 HOLD_IDLE_INTERVAL=1 bash "$HT_SH" "$@"; }
ht_rc() { local want=$1; shift; ht "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }
ht_is() { [ -f "$1" ] && [ "$(cat "$1")" = "$2" ]; }
ht_same() { [ -f "$1" ] && cmp -s "$1" "$2"; }
ht_gone() { [ ! -e "$1" ]; }

check "hold.sh parses (bash -n)" bash -n "$HERE/hold.sh"

# (a) free device
check "(a) take on a free device exits 0" ht_rc 0 take thor hostupd-100 host update window
check "(a) hold/thor holds exactly the taker's tag" ht_is "$HT_D/hold/thor" hostupd-100
check "(a) hold/thor.why carries the reason" grep -q 'hostupd-100: host update window' "$HT_D/hold/thor.why"
check "(a) who reports the holder, exit 0" ht_rc 0 who thor

cp "$HT_D/hold/thor" "$T/holdtake/thor.before"
cp "$HT_D/hold/thor.why" "$T/holdtake/thor.why.before"

# (b) the lane takes a held device
check "(b) take on a held device exits 3" ht_rc 3 take thor lane.perfregimen write proof
check "(b) hold/thor is byte-identical after the refused take" ht_same "$HT_D/hold/thor" "$T/holdtake/thor.before"
check "(b) hold/thor.why is byte-identical after the refused take" ht_same "$HT_D/hold/thor.why" "$T/holdtake/thor.why.before"

# (c) the lane releases a hold it did not take
check "(c) release with the wrong tag exits 3" ht_rc 3 release thor lane.perfregimen
check "(c) hold/thor survives the wrong-tag release" ht_same "$HT_D/hold/thor" "$T/holdtake/thor.before"
check "(c) hold/thor.why survives the wrong-tag release" ht_same "$HT_D/hold/thor.why" "$T/holdtake/thor.why.before"
: > "$HT_D/hold/nova"
check "(c) an untagged (touched) hold is released by no tag" ht_rc 3 release nova hostupd-100
check "(c) the touched hold survives" [ -e "$HT_D/hold/nova" ]
rm -f "$HT_D/hold/nova"

# (d) the taker releases
check "(d) release with the right tag exits 0" ht_rc 0 release thor hostupd-100
check "(d) hold/thor is gone" ht_gone "$HT_D/hold/thor"
check "(d) hold/thor.why is gone" ht_gone "$HT_D/hold/thor.why"
check "(d) who reports free, exit 1" ht_rc 1 who thor

# (e) eight concurrent takers: exactly one wins, and the file names the winner
rm -rf "$T/holdtake/race"; mkdir -p "$T/holdtake/race"; ht_pids=()
for i in 1 2 3 4 5 6 7 8; do
    ( ht take thor "racer$i" race >/dev/null 2>&1; echo $? > "$T/holdtake/race/$i" ) &
    ht_pids+=($!)
done
wait "${ht_pids[@]}"   # by PID: a bare wait would also wait on other fragments' jobs
ht_winners=$(grep -lx 0 "$T/holdtake/race/"* 2>/dev/null | wc -l)
ht_losers=$(grep -lx 3 "$T/holdtake/race/"* 2>/dev/null | wc -l)
ht_winner=$(grep -lx 0 "$T/holdtake/race/"* 2>/dev/null | head -1 | xargs -r basename)
check "(e) exactly one of eight concurrent takes exits 0 (got $ht_winners)" [ "$ht_winners" = 1 ]
check "(e) the other seven exit 3 (got $ht_losers)" [ "$ht_losers" = 7 ]
check "(e) hold/thor names the one winner" ht_is "$HT_D/hold/thor" "racer${ht_winner:-none}"
ht release thor "racer${ht_winner:-none}" >/dev/null 2>&1; rm -f "$HT_D/hold/thor" "$HT_D/hold/thor.why"

# (f) a running request does not block take; wait gives up
echo thor > "$HT_D/running/1790000000-lane.x-1.owner"
check "(f) take succeeds while a request runs on the device" ht_rc 0 take thor lane.holdtake proof
check "(f) wait on a held device times out with exit 3" ht_rc 3 wait thor other 2 waiting
check "(f) the timed-out wait left the holder's tag" ht_is "$HT_D/hold/thor" lane.holdtake
ht release thor lane.holdtake >/dev/null 2>&1
check "(f) wait on a free device takes it, exit 0" ht_rc 0 wait thor other 2 waiting
check "(f) and the file names the waiter" ht_is "$HT_D/hold/thor" other
rm -f "$HT_D/hold/thor" "$HT_D/hold/thor.why" "$HT_D/running/1790000000-lane.x-1.owner"

# (g) wait-idle: the second half of "take, then wait for running/ to empty".
#
# THE INCIDENT, 2026-10-01 21:58 PDT. lane.titleroutes took the Nova 2.5 min
# into lane.ibcache's #507 run, read "taken:", and force-stopped hakuX; the
# run died at 132 of 420 s. The legs, and the world each one fails in:
#   g1  a running/*.owner names the label: wait-idle returns 0 (a wait-idle
#       that never looks, `exit 0`), or gives up without naming the run, or
#       the timeout drops the caller's hold.
#   g2  nothing runs there: wait-idle blocks anyway (a wait-idle that never
#       finds the device idle, or that waits a full interval before looking).
#   g3  the owner names ANOTHER label: wait-idle blocks on it (matches any
#       owner file, or a substring: "nova" vs "nova2").
#   g4  there is no hold: wait-idle returns 0, though nothing stops a claim.
#   g5  lanes/<label> names a live dispatcher.sh: wait-idle returns 0 (checks
#       running/ only, so a claim inside the worker's last unheld queue walk,
#       after the take, is missed) -- or it blocks on a dead pid or on a
#       pid that is not a dispatcher (a stale registration jams it forever).
#   g6  the owner outlives its .req (result being written, device torn
#       down): wait-idle reads running/*.req instead of the owner.
#   g7  the run ends mid-wait: wait-idle does not notice and runs out its
#       timeout.
#   g8  take on a busy device stays exit 0 with its stdout unchanged, and
#       says NOT IDLE on stderr; on an idle device it says nothing more.
ht_err() { local want=$1 pat=$2; shift 2; ht "$@" 2>"$T/holdtake/err" >"$T/holdtake/out"; [ $? -eq "$want" ] && grep -q -- "$pat" "$T/holdtake/err"; }
ht_out() { local want=$1 pat=$2; shift 2; ht "$@" 2>"$T/holdtake/err" >"$T/holdtake/out"; [ $? -eq "$want" ] && grep -q -- "$pat" "$T/holdtake/out"; }
HT_RUN="$HT_D/running/1790914021-lane.ibcache-3203127"
mkdir -p "$HT_D/lanes"
ht take nova lane.titleroutes s61 >/dev/null 2>&1

# g1: blocks, exits 3 at the timeout, names the run, keeps the hold
echo nova > "$HT_RUN.owner"; echo '{}' > "$HT_RUN.req"
check "(g1) wait-idle with a run on the device exits 3 at its timeout, naming the run" \
    ht_err 3 '1790914021-lane.ibcache-3203127' wait-idle nova 2
check "(g1) the timed-out wait-idle kept the caller's hold" ht_is "$HT_D/hold/nova" lane.titleroutes
check "(g1) with timeout 0 it looks once and still exits 3" ht_rc 3 wait-idle nova 0

# g3: a run on ANOTHER device does not block
echo nova2 > "$HT_RUN.owner"
check "(g3) an owner naming nova2 does not block nova (exit 0)" ht_rc 0 wait-idle nova 0
echo thor > "$HT_RUN.owner"
check "(g3) an owner naming thor does not block nova (exit 0)" ht_rc 0 wait-idle nova 0
rm -f "$HT_RUN.owner" "$HT_RUN.req"

# g2: idle -> 0 on the first look (timeout 0 allows exactly one)
check "(g2) nothing running on the device: wait-idle exits 0 on its first look" \
    ht_out 0 'idle: nova' wait-idle nova 0

# g4: no hold -> 1, even though nothing runs
check "(g4) wait-idle on an unheld device exits 1" ht_err 1 'no hold' wait-idle thor 0

# g5: the worker's registration
cat > "$T/holdtake/dispatcher.sh" <<'EOF'
trap 'kill $! 2>/dev/null; exit 0' TERM
sleep 60 & wait
EOF
bash "$T/holdtake/dispatcher.sh" & ht_disp=$!
true & ht_dead=$!; wait "$ht_dead"
echo "$ht_disp" > "$HT_D/lanes/nova"
check "(g5) lanes/nova naming a live dispatcher.sh blocks (exit 3)" \
    ht_err 3 "dispatcher pid $ht_disp has not seen the hold" wait-idle nova 0
echo "$ht_dead" > "$HT_D/lanes/nova"
check "(g5) lanes/nova naming a dead pid does not block (exit 0)" ht_rc 0 wait-idle nova 0
echo "$$" > "$HT_D/lanes/nova"
check "(g5) lanes/nova naming a live non-dispatcher pid does not block (exit 0)" ht_rc 0 wait-idle nova 0
echo "$ht_disp" > "$HT_D/lanes/thor"
check "(g5) lanes/thor's live dispatcher does not block nova (exit 0)" ht_rc 0 wait-idle nova 0
rm -f "$HT_D/lanes/nova" "$HT_D/lanes/thor"
kill "$ht_disp" 2>/dev/null; wait "$ht_disp" 2>/dev/null

# g6: owner without its .req still blocks
echo nova > "$HT_RUN.owner"
check "(g6) an owner whose .req has left running/ still blocks (exit 3)" \
    ht_err 3 'torn down' wait-idle nova 0

# g7: the run ends two seconds into a ten-second wait
( sleep 2; rm -f "$HT_RUN.owner" ) & ht_end=$!
ht_t0=$(date +%s)
check "(g7) wait-idle returns 0 when the run ends mid-wait" ht_rc 0 wait-idle nova 10
ht_dt=$(( $(date +%s) - ht_t0 ))
wait "$ht_end"
check "(g7) and returned within 2-6 s, not at its timeout (took ${ht_dt}s)" [ "$ht_dt" -ge 2 -a "$ht_dt" -le 6 ]
ht release nova lane.titleroutes >/dev/null 2>&1

# g8: take's notice
echo nova > "$HT_RUN.owner"; echo '{}' > "$HT_RUN.req"
check "(g8) take on a busy device still exits 0 with 'taken:' on stdout" \
    ht_out 0 '^taken: nova by lane.titleroutes$' take nova lane.titleroutes s62
check "(g8) take's stdout is still exactly one line" [ "$(wc -l < "$T/holdtake/out")" -eq 1 ]
check "(g8) and stderr says NOT IDLE" grep -q '^NOT IDLE: nova' "$T/holdtake/err"
check "(g8) and names the run" grep -q '1790914021-lane.ibcache-3203127' "$T/holdtake/err"
ht release nova lane.titleroutes >/dev/null 2>&1
rm -f "$HT_RUN.owner" "$HT_RUN.req"
check "(g8) take on an idle device exits 0" ht_out 0 '^taken: nova' take nova lane.titleroutes s62
check "(g8) and prints nothing on stderr" [ ! -s "$T/holdtake/err" ]
ht release nova lane.titleroutes >/dev/null 2>&1
rm -f "$HT_D/hold/nova" "$HT_D/hold/nova.why"
