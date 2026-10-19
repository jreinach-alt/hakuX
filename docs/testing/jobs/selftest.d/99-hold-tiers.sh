# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# #433 lane.nova-tiers1019, 10-19. Owner: screening should be the lowest
# Nova priority, FPS work higher, a release-blocking defect highest -- and a
# HOLD had no such concept at all: overnight 10-17 and 10-18 a screening
# chain held the Nova directly while the FPS lane's `1-` requests sat queued
# behind the hold itself, not behind queue order, because a hold refuses
# every new claim regardless of what is queued. `hold.sh take|wait` now take
# an optional `--tier blocker|fps|sweep`; a sweep take/wait refuses while a
# higher-tier (`0-*`/`1-*`) request is queued or running for that device
# label, using the same affinity.py eligibility dispatcher.sh's serve_one
# uses; `yield-check` lets an in-force sweep hold release cooperatively.
#
# Each leg names the world in which it fails:
#   (a) a sweep take with a `1-*` request queued for this label is not
#       refused: a screening chain still beats the FPS lane it must yield to,
#       which is the exact incident this lane exists to fix.
#   (b) a sweep take with only a `z-*` (sweep-tier) request queued is
#       refused anyway: sweep work could never run, even against its own
#       tier, and no `<label>.tier` is written to say what was taken.
#   (c) with a sweep hold already in force, `yield-check` does not say
#       7 once a `1-*` request has been queued (not running) for at least
#       HOLD_YIELD_S, or says 7 too early (before that age) -- either one
#       breaks the cooperative release the chain depends on.
#   (d) adding `--tier` changes what an untiered take/wait/release/who does
#       today -- checked by re-running the existing 99-hold-take.sh fragment
#       against this same hold.sh (that fragment runs on its own too; this
#       leg exists so a failure here is attributed to tiers specifically).
#   (e) release removes `<label>.tier` for a taker whose tag does not match,
#       or leaves it behind for the one that does.
#
# MUTANT: reinstate the old (no-queue-check) sweep-take behaviour -- the
# world leg (a) is supposed to catch -- and show that leg then goes green
# for the wrong reason, i.e. the refusal it expects does not happen.
#
# Uses its own DISPATCH_DIR, never the harness's shared one and never the
# host's real dispatch/ directory.

echo "== hold.sh: tiers, so a sweep (screening) hold yields to queued FPS/blocker work (#433)"

HTIER_SH="${SELFTEST_HOLD_SH:-$HERE/hold.sh}"
HTIER_D="$T/holdtiers/dispatch"
rm -rf "$HTIER_D"
mkdir -p "$HTIER_D/queue" "$HTIER_D/running" "$HTIER_D/hold"

htr() { DISPATCH_DIR="$HTIER_D" HOLD_WAIT_INTERVAL=1 HOLD_IDLE_INTERVAL=1 HOLD_YIELD_S="${HOLD_YIELD_S:-60}" bash "$HTIER_SH" "$@"; }
htr_rc() { local want=$1; shift; htr "$@" >/dev/null 2>&1; [ $? -eq "$want" ]; }
htr_is() { [ -f "$1" ] && [ "$(cat "$1")" = "$2" ]; }
htr_gone() { [ ! -e "$1" ]; }

check "hold.sh parses (bash -n)" bash -n "$HERE/hold.sh"

# Fixture requests. An explicit "device" field is affinity.py's rule 1 and
# wins outright, so these are pinned to nova regardless of what else is (or
# is not) live/pooled on the fake host -- deterministic without a fake
# lanes/ registration.
mk_req() { printf '{"device":"nova","requester":"selftest"}' > "$HTIER_D/queue/$1.req"; }

# (a) sweep take refused while a 1-* request is queued for this label
mk_req "1-1790900000-fps.probe-1"
check "(a) sweep take is refused while a 1-* request is queued (exit 8)" htr_rc 8 take nova --tier sweep lane.sweep screening
check "(a) no hold was left behind by the refused sweep take" htr_gone "$HTIER_D/hold/nova"
check "(a) and no tier file either" htr_gone "$HTIER_D/hold/nova.tier"
rm -f "$HTIER_D/queue/1-1790900000-fps.probe-1.req"

# a 0-* (blocker) request queued refuses a sweep take just as hard
mk_req "0-1790900000-blocker.probe-1"
check "(a2) sweep take is refused while a 0-* request is queued (exit 8)" htr_rc 8 take nova --tier sweep lane.sweep screening
rm -f "$HTIER_D/queue/0-1790900000-blocker.probe-1.req"

# a running 1-* for this label refuses a sweep take too (queued or running)
mk_req "1-1790900000-fps.probe-2"
mv "$HTIER_D/queue/1-1790900000-fps.probe-2.req" "$HTIER_D/running/1-1790900000-fps.probe-2.req"
echo nova > "$HTIER_D/running/1-1790900000-fps.probe-2.owner"
check "(a3) sweep take is refused while a 1-* request is RUNNING on this label (exit 8)" htr_rc 8 take nova --tier sweep lane.sweep screening
rm -f "$HTIER_D/running/1-1790900000-fps.probe-2.req" "$HTIER_D/running/1-1790900000-fps.probe-2.owner"

# (b) sweep take succeeds with only sweep-tier (z-*) work queued, and writes
# the tier file
mk_req "z-1790900000-sweep.probe-1"
check "(b) sweep take succeeds with only z-* queued (exit 0)" htr_rc 0 take nova --tier sweep lane.sweep screening
check "(b) hold/nova names the taker" htr_is "$HTIER_D/hold/nova" lane.sweep
check "(b) hold/nova.tier reads sweep" htr_is "$HTIER_D/hold/nova.tier" sweep
rm -f "$HTIER_D/queue/z-1790900000-sweep.probe-1.req"

# (d) untiered take is unchanged: no --tier at all still writes hold/nova
# with no tier string leaking into it, and defaults to fps.
check "(d) release of the sweep hold by its taker exits 0" htr_rc 0 release nova lane.sweep
check "(d) hold/nova is gone" htr_gone "$HTIER_D/hold/nova"
check "(d) hold/nova.tier is gone too" htr_gone "$HTIER_D/hold/nova.tier"
check "(d) an untiered take still exits 0 with a 1-* request queued (today's behaviour, unchanged)" \
    bash -c "DISPATCH_DIR='$HTIER_D' HOLD_WAIT_INTERVAL=1 bash '$HTIER_SH' take nova lane.fps fps work >/dev/null 2>&1; [ \$? -eq 0 ]"
mk_req "1-1790900000-fps.probe-3"
check "(d) an untiered (fps) take still exits 3 against an existing hold, not 8" htr_rc 3 take nova lane.other probing
check "(d) hold/nova.tier reads fps (the untiered default), not sweep" htr_is "$HTIER_D/hold/nova.tier" fps
check "(d) release by the real taker exits 0" htr_rc 0 release nova lane.fps
rm -f "$HTIER_D/queue/1-1790900000-fps.probe-3.req" "$HTIER_D/hold/nova" "$HTIER_D/hold/nova.tier" "$HTIER_D/hold/nova.why"

# (e) release removes <label>.tier only for the matching taker
check "(e) sweep take with no competing work exits 0" htr_rc 0 take nova --tier sweep lane.e screening
check "(e) hold/nova.tier reads sweep" htr_is "$HTIER_D/hold/nova.tier" sweep
check "(e) release by the WRONG tag exits 3" htr_rc 3 release nova lane.not-e
check "(e) hold/nova.tier survives the wrong-tag release" htr_is "$HTIER_D/hold/nova.tier" sweep
check "(e) release by the right tag exits 0" htr_rc 0 release nova lane.e
check "(e) hold/nova.tier is gone after the matching release" htr_gone "$HTIER_D/hold/nova.tier"
check "(e) hold/nova itself is gone too" htr_gone "$HTIER_D/hold/nova"

# (c) yield-check: a sweep hold in force, then a 1-* request appears.
check "(c) sweep take (setup) exits 0" htr_rc 0 take nova --tier sweep lane.c screening
check "(c) yield-check with nothing queued exits 0 (keep going)" htr_rc 0 yield-check nova lane.c
# Age is read from the id's own epoch, so "30s old" and "90s old" are just
# different epochs in the fixture's filename -- no sleeping in the fixture.
# Margins wide of HOLD_YIELD_S=60 (30s short, 90s past) so the few seconds a
# loaded multi-shard run can spend between htr_now and the age.sh/yield-check
# process actually reading the clock cannot flip either side of the edge.
htr_now=$(date +%s)
mk_req "1-$(( htr_now - 30 ))-fps.young"
check "(c) a 1-* request 30s old does not yield yet (exit 0)" htr_rc 0 yield-check nova lane.c
rm -f "$HTIER_D/queue/1-$(( htr_now - 30 ))-fps.young.req"
mk_req "1-$(( htr_now - 90 ))-fps.old"
check "(c) the same request at 90s old does yield (exit 7)" htr_rc 7 yield-check nova lane.c
rm -f "$HTIER_D/queue/1-$(( htr_now - 90 ))-fps.old.req"
# any 0-* yields at once, regardless of age
mk_req "0-$htr_now-blocker.now"
check "(c) a brand-new 0-* request yields immediately (exit 7)" htr_rc 7 yield-check nova lane.c
rm -f "$HTIER_D/queue/0-$htr_now-blocker.now.req"
check "(c) with the queue clear again, yield-check is back to 0" htr_rc 0 yield-check nova lane.c
check "(c) release by the taker exits 0" htr_rc 0 release nova lane.c
rm -f "$HTIER_D/hold/nova" "$HTIER_D/hold/nova.tier" "$HTIER_D/hold/nova.why"

# wait, at --tier sweep, keeps retrying instead of exiting while a 1-* is
# queued, and takes only once it clears.
mk_req "1-1790900000-fps.wait"
( sleep 2; rm -f "$HTIER_D/queue/1-1790900000-fps.wait.req" ) &
htier_bg=$!
check "(f) sweep wait does not time out instantly against a 1-* that clears mid-wait (exit 0)" \
    htr_rc 0 wait nova --tier sweep lane.waiter 10 screening
wait "$htier_bg"
check "(f) the sweep wait took the hold once the queue cleared" htr_is "$HTIER_D/hold/nova" lane.waiter
htr release nova lane.waiter >/dev/null 2>&1
rm -f "$HTIER_D/hold/nova" "$HTIER_D/hold/nova.tier" "$HTIER_D/hold/nova.why"

# (d, continued): 99-hold-take.sh -- the pre-existing falsifier for
# untiered take/release/who/wait-idle -- runs as its own fragment in the
# same selftest.sh invocation and must still pass unchanged; it is not
# re-run here to avoid double-counting its checks under this fragment's
# pass/fail totals.

# MUTANT: reinstate the old (no-queue-check) sweep-take behaviour and show
# leg (a) then fails under it -- i.e. the sweep take it expects to be
# refused instead succeeds.
# Laid out as jobs/hold.sh + ../affinity.py, mirroring the real tree: build_gate
# resolves device_build.py off $0's directory and sweep_blocker resolves
# affinity.py off $HERE (BASH_SOURCE's directory) -- both need their real
# neighbours alongside the mutated file, or a mutant run fails on a missing
# file rather than exercising (or failing to exercise) the gate.
HTIER_MUT="$T/holdtiers/mut"; mkdir -p "$HTIER_MUT/jobs"
cp "$HERE/device_build.py" "$HTIER_MUT/jobs/device_build.py"
cp "$HERE/../affinity.py" "$HTIER_MUT/affinity.py"
sed 's/if \[ "\$TIER" = sweep \] && blocker=\$(sweep_blocker "\$label"); then/if false; then/' \
    "$HTIER_SH" > "$HTIER_MUT/jobs/hold.sh"
check "the real hold.sh carries both sweep-gate checks (take and wait)" \
    [ "$(grep -c 'if \[ "\$TIER" = sweep \] && blocker=\$(sweep_blocker "\$label"); then' "$HTIER_SH")" -eq 2 ]
check "mutant built: hold.sh with both sweep-gate checks disabled" \
    [ "$(grep -c 'if \[ "\$TIER" = sweep \] && blocker=\$(sweep_blocker "\$label"); then' "$HTIER_MUT/jobs/hold.sh")" -eq 0 ]
mk_req "1-1790900000-fps.mutant"
check "mutant: without the gate, a sweep take with a 1-* queued WRONGLY succeeds (leg (a) is not vacuous)" \
    bash -c "DISPATCH_DIR='$HTIER_D' bash '$HTIER_MUT/jobs/hold.sh' take nova --tier sweep lane.mut screening >/dev/null 2>&1"
rm -f "$HTIER_D/queue/1-1790900000-fps.mutant.req" "$HTIER_D/hold/nova" "$HTIER_D/hold/nova.tier" "$HTIER_D/hold/nova.why"
