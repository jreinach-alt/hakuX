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
ht() { DISPATCH_DIR="$HT_D" HOLD_WAIT_INTERVAL=1 bash "$HT_SH" "$@"; }
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
