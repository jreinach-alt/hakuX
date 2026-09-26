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

# `pg` holds 25.5 min: two soaks waiting and one RUNNING. A third soak (8.5 min)
# takes it to 34 min.
pg_fix queue   f100 pg 420
pg_fix queue   f101 pg 420
pg_fix running f102 pg 420

# A. Over budget, no pilot: refused. Fails in the world with no gate, and in the
# world where the gate counts only queue/ -- without the running soak `pg`
# holds 17 + 8.5 = 25.5 min and would be admitted.
out=$(pg_rq pg)
case "$out" in
    *"refusing to queue: the pilot gate"*"~34 min in all"*"there is no $PG/pilots/pg.ok"*"record the verdict"*)
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

# C. UNDER budget: another requester, with pg's 25.5 min still in the queue,
# queues its first 8.5 min. Fails in the world with a gate that refuses
# everything, and in the world where the gate sums every requester's time
# (25.5 + 8.5 = 34 min) rather than this requester's.
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
