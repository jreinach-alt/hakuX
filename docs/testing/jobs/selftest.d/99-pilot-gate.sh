# Sourced by ../selftest.sh with the harness already built: $T, $TESTING, the
# shims on PATH, ok/bad/check. Not executable, no shebang, no exit.
#
# request.sh's PILOT GATE (owner, 2026-09-26): a requester whose queued and
# running device time would pass 30 min is refused unless
# $DISPATCH_DIR/pilots/<requester>.ok is under 24 h old. titleplay's pass 1
# queued 29 soaks of 420 s with nobody looking at the first two runs' frames.
#
# A private dispatch dir, so nothing here is counted by a later fragment. The
# fixture requests are written straight into queue/ and running/ with the
# fields the estimate reads; each is (seconds + 90) x runs.
#
# Every refusal is judged on the WORDS and on the queue, not the exit code:
# request.sh exits 2 for a dozen reasons, and a refusal for some other reason
# (a missing title, an unresolvable ref) would pass a bare `! request.sh`.
echo "== request.sh: the pilot gate"
PG="$T/pilot-gate"; rm -rf "$PG"; mkdir -p "$PG"/{queue,running,results,pilots}
pg_fix() {  # <dir> <name> <requester> <seconds> [runs]
    printf '{"id": "%s", "requester": "%s", "seconds": %s, "runs": %s}\n' "$2" "$3" "$4" "${5:-1}" > "$PG/$1/$2.req"; }
pg_rq() {   # <requester>: a 420 s soak, the titleplay shape: ~8.5 min
    DISPATCH_DIR="$PG" bash "$TESTING/request.sh" --who "$1" --purpose "pilot gate selftest" \
        --no-expect selftest --title "Crimson Skies.iso" --seconds 420 2>&1; }
pg_n() { ls "$PG"/queue/*"-$1-"*.req 2>/dev/null | wc -l; }   # requests request.sh queued for <requester>
# An admission is the anchored "queued <id>" LINE. The refusal's own prose says
# "queued or running", so a bare *"queued "* pattern reads a refusal as an
# admission -- measured: the >= mutant passed leg D that way.
pg_ok() { grep -qE "^queued [0-9]+-$1-[0-9]+$" <<< "$2"; }   # <requester> <output>

# `pg` holds 1291 s: a runs-3 request (170 x 3 = 510 s) and one with no
# `seconds` (180 s) waiting, and one RUNNING (511 + 90 = 601 s). A soak (510 s)
# takes it to 1801 s, one second over. Every term is load-bearing, so each of
# these worlds admits it and fails leg A: the gate counts only queue/ (1200 s),
# it drops `* runs` (1461 s), or it counts a request with no `seconds` as
# anything under 181 s.
pg_fix queue   f100 pg 80 3
pg_fix queue   f101 pg 0
pg_fix running f102 pg 511

# A. Over budget, no pilot: refused. Fails in the world with no gate, and in the
# three worlds above.
out=$(pg_rq pg)
case "$out" in
    *"refusing to queue: the pilot gate"*"~30 min in all"*"there is no $PG/pilots/pg.ok"*"record the verdict"*)
        ok "A: over 30 min with no pilot is refused, naming the rule, the estimate and the way out" ;;
    *) bad "A: over 30 min with no pilot was not refused as the gate: $(tail -3 <<< "$out" | tr '\n' ' ')" ;; esac
check "A: and nothing was queued" [ "$(pg_n pg)" -eq 0 ]
check "A: and no temp record was left behind" bash -c '[ -z "$(ls -A "$1"/queue | grep "^\.")" ]' _ "$PG"

# B. A STALE pilot (25 h): still refused. Fails in the world where the gate
# checks that pilots/<requester>.ok exists and not how old it is.
printf 'results 1-pg-x 1-pg-y: route reached gameplay; 2026-09-26\n' > "$PG/pilots/pg.ok"
touch -d '25 hours ago' "$PG/pilots/pg.ok"
out=$(pg_rq pg)
case "$out" in
    *"refusing to queue: the pilot gate"*"h old; a pilot verdict is valid 24 h"*)
        ok "B: a 25 h old pilot verdict does not admit the batch" ;;
    *) bad "B: a stale pilot verdict admitted the batch, or refused for another reason: $(tail -3 <<< "$out" | tr '\n' ' ')" ;; esac
check "B: and nothing was queued" [ "$(pg_n pg)" -eq 0 ]

# C. UNDER budget: another requester, with pg's 1291 s still in the queue,
# queues its first 8.5 min. Fails in the world with a gate that refuses
# everything, and in the world where the gate sums every requester's time
# (1291 + 510 = 1801 s) rather than this requester's.
out=$(pg_rq pgnew)
if pg_ok pgnew "$out"; then ok "C: a requester under 30 min is admitted, whoever else is queued"
else bad "C: a requester under 30 min was refused: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "C: and its request is in the queue" [ "$(pg_n pgnew)" -eq 1 ]

# D. EXACTLY 30 min goes through ("over 30 min" is the rule). `pgedge` holds
# 1290 s; the soak adds 510 s: 1800 s. Fails in the world where the comparison
# is >= and the pilot itself -- the first 30 min -- is refused.
pg_fix queue f103 pgedge 1200
out=$(pg_rq pgedge)
if pg_ok pgedge "$out"; then ok "D: exactly 30 min is admitted (the first 30 min is the pilot)"
else bad "D: exactly 30 min was refused: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi

# F. A STAGING caller (titleplay's queue.py): DISPATCH_DIR is a private
# tempdir, PILOT_DISPATCH_DIR is the real one, which already holds pg's 1291 s.
# Refused, and the refusal names the REAL pilots/ path. Fails in the world
# where the gate counts DISPATCH_DIR: the staging queue is empty, 510 s passes,
# and a plan split over several invocations queues any amount (#397's shape).
PGS="$T/pilot-gate-stage"; rm -rf "$PGS"; mkdir -p "$PGS"/{queue,running,results,pilots}
out=$(DISPATCH_DIR="$PGS" PILOT_DISPATCH_DIR="$PG" bash "$TESTING/request.sh" --who pg \
        --purpose "pilot gate selftest" --no-expect selftest --title "Crimson Skies.iso" --seconds 420 2>&1)
case "$out" in
    *"refusing to queue: the pilot gate"*"~30 min in all"*"$PG/pilots/pg.ok"*)
        ok "F: a staged enqueue is judged against PILOT_DISPATCH_DIR's queue and pilots" ;;
    *) bad "F: a staged enqueue was not judged against the real dispatch dir: $(tail -3 <<< "$out" | tr '\n' ' ')" ;; esac
check "F: and nothing was staged" bash -c '[ -z "$(ls -A "$1"/queue)" ]' _ "$PGS"
rm -rf "$PGS"
check "F: queue.py hands request.sh the real dir as PILOT_DISPATCH_DIR" \
    grep -qE '^ +env = dict\(os\.environ, DISPATCH_DIR=stage, PILOT_DISPATCH_DIR=D\)$' \
    "$TESTING/../lanes/titleplay/tools/queue.py"

# G. An ARM is not judged: arms.sh records every refusal as permanent against
# the prediction, and `arms-remote-*` pools every remote lane. `arms-pgx-base`
# holds 1291 s; a soak takes it past 30 min and is
# admitted. Fails in the world where the gate judges arms.
pg_fix queue f110 arms-pgx-base 80 3
pg_fix queue f111 arms-pgx-base 511
pg_fix queue f112 arms-pgx-base 0
out=$(pg_rq arms-pgx-base)
if pg_ok arms-pgx-base "$out"; then ok "G: an arms-* requester is not held by the pilot gate"
else bad "G: an arms-* requester was refused: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
# H. A malformed record of a gated requester (`"seconds": "420s"`) is counted
# 180 s, and the gate still speaks: 180 + 1290 + 510 = 1980 s, refused. Fails in
# the world where est() raises and request.sh exits on a Python traceback.
printf '{"id": "f113", "requester": "pgbad", "seconds": "420s", "runs": "3x"}\n' > "$PG/queue/f113.req"
pg_fix queue f114 pgbad 1200
out=$(pg_rq pgbad)
case "$out" in
    *"refusing to queue: the pilot gate"*"~33 min in all"*) ok "H: a malformed record is counted 180 s, not a traceback" ;;
    *) bad "H: a malformed record broke the gate: $(tail -3 <<< "$out" | tr '\n' ' ')" ;; esac

# E. A FRESH pilot: admitted. Fails in the world where the gate never reads
# pilots/, or reads a different path than the one its refusal names.
touch "$PG/pilots/pg.ok"
out=$(pg_rq pg)
if pg_ok pg "$out" && grep -qF "reviewed pilot $PG/pilots/pg.ok" <<< "$out"; then
    ok "E: a fresh pilot verdict admits the batch, and says so"
else bad "E: a fresh pilot verdict did not admit the batch: $(tail -3 <<< "$out" | tr '\n' ' ')"; fi
check "E: and its request is in the queue" [ "$(pg_n pg)" -eq 1 ]
rm -rf "$PG"; unset PG out
unset -f pg_fix pg_rq pg_n pg_ok
