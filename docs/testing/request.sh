#!/usr/bin/env bash
#
# Ask the dispatcher to run tests, and wait for the result.
#
#   request.sh --who bump-agent --purpose "bump map baseline" \
#              --suites "Bump map,Bump env lum" [--ref HEAD] [--runs 1] [--wait] \
#              (--expect predictions/x.json | --no-expect "why not")
#
# Agents never touch the device. This is the only way in, and it is deliberately
# narrow: a request names a *ref*, not "what is in my tree", because with
# several implementers holding uncommitted work "run my build" is ambiguous the
# moment two of them ask.
#
# --wait blocks until the result lands and then prints the summary. Without it,
# the request id is printed and the caller can poll result.json.
set -u
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
WHO=""; PURPOSE=""; SUITES=""; REF="HEAD"; RUNS=1; WAIT=0; ARM="company"; TESTS=""
TITLE=""; SECONDS_HOLD=60; PULL_GLOB=""; EXPECT=""; NO_EXPECT=""
while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;
        --purpose) PURPOSE="$2"; shift 2;;
        --suites) SUITES="$2"; shift 2;;
        --tests) TESTS="$2"; shift 2;;
        --ref) REF="$2"; shift 2;;
        --arm) ARM="$2"; shift 2;;
        --runs) RUNS="$2"; shift 2;;
        --title) TITLE="$2"; shift 2;;
        --seconds) SECONDS_HOLD="$2"; shift 2;;
        --pull) PULL_GLOB="$2"; shift 2;;
        --expect) EXPECT="$2"; shift 2;;
        --no-expect) NO_EXPECT="$2"; shift 2;;
        --wait) WAIT=1; shift;;
        *) echo "unknown option $1" >&2; exit 2;;
    esac
done
# A soak request names a title instead of suites: it boots a real game and
# keeps the log, for questions with no golden framebuffer (the test discs are
# silent, so nothing about audio can be asked of them).
[ -n "$WHO" ] || { echo "need --who" >&2; exit 2; }
[ -n "$SUITES" ] || [ -n "$TITLE" ] || { echo "need --suites, or --title for a soak" >&2; exit 2; }

# A measurement request must name the prediction it is going to be judged
# against, and must do so NOW. Two arms on 2026-09-12 -- the F24 subnormal
# flush and the NV04 solid line -- were dispatched with their predictions
# only in prose, so both had to be registered after the results existed and
# ab_compare stamped both POST-HOC: correct, and it cost a real verdict on two
# changes that in fact passed. The fix is not discipline, it is that the queue
# refuses the request.
#
# The binding is by CONTENT HASH, not by mtime. An mtime check catches a
# prediction written late; it does not catch one written on time and then
# quietly widened once the numbers are in, which is the same failure with
# better paperwork. The sha recorded here is of the file as it stood when the
# device work was asked for, so ab_compare can tell the two apart.
if [ -n "$SUITES" ]; then
    if [ -n "$EXPECT" ]; then
        [ -f "$EXPECT" ] || { echo "--expect $EXPECT does not exist. Register it first: ab_compare.py --register $EXPECT --a-ref ... --b-ref ..." >&2; exit 2; }
        EXPECT_SHA=$(sha256sum "$EXPECT" | cut -d" " -f1)
        EXPECT=$(cd "$(dirname "$EXPECT")" && pwd)/$(basename "$EXPECT")
    elif [ -n "$NO_EXPECT" ]; then
        EXPECT_SHA=""
        echo "queuing without a prediction: $NO_EXPECT" >&2
    else
        cat >&2 <<'MSG'
refusing to queue: a suites request needs --expect FILE or --no-expect REASON.

  --expect docs/testing/predictions/<thing>.json
        the registered prediction this arm will be judged against. Write it
        with ab_compare.py --register before asking for the device; its
        content is hashed here so a later edit is detectable.

  --no-expect "REASON"
        for a request that is not an A/B arm -- a baseline, a survey, a
        noise-floor run. The reason is recorded with the request.
MSG
        exit 2
    fi
fi

# Resolve the ref to a concrete sha AT QUEUE TIME. "HEAD" in a queued request
# is a moving target: the queue is served later, and any commit in between
# silently changes which tree gets built -- which is how a baseline arm came to
# be queued against a HEAD that had gained two merges by the time it ran. A
# request must name the tree the requester meant.
if RESOLVED=$(git -C "$(dirname "$0")/../.." rev-parse --short "$REF" 2>/dev/null); then
    [ "$RESOLVED" = "$REF" ] || echo "resolved --ref $REF to $RESOLVED" >&2
    REF="$RESOLVED"
else
    echo "cannot resolve --ref $REF to a commit" >&2; exit 2
fi

ID="$(date +%s)-$WHO-$$"
mkdir -p "$D/queue"
python3 - "$D/queue/$ID.req" "$ID" "$WHO" "$PURPOSE" "$SUITES" "$REF" "$ARM" "$RUNS" "$TESTS" "$TITLE" "$SECONDS_HOLD" "$PULL_GLOB" "$EXPECT" "${EXPECT_SHA:-}" "$NO_EXPECT" <<'PY'
import json, sys
(p, i, who, purpose, suites, ref, arm, runs, tests, title, seconds,
 pull_glob, expect, expect_sha, no_expect) = sys.argv[1:16]
json.dump({"id": i, "requester": who, "purpose": purpose,
           "suites": [s.strip() for s in suites.split(",") if s.strip()],
           "tests": [t.strip() for t in tests.split(",") if t.strip()],
           "ref": ref, "arm": arm, "runs": int(runs),
           "title": title, "seconds": int(seconds),
           "pull_glob": pull_glob,
           "expect": expect, "expect_sha": expect_sha,
           "no_expect": no_expect,
           "queued_utc": __import__("datetime").datetime.now(
               __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(p, "w"), indent=2)
PY
echo "queued $ID"
[ "$WAIT" = 1 ] || exit 0

# Device work is 1-10 minutes and the queue may be busy; a long ceiling is
# correct here. A requester that gives up early and reads a partial result is
# the failure this is meant to prevent.
for _ in $(seq 1 360); do
    if [ -f "$D/results/$ID/DONE" ]; then
        echo "--- result ---"
        python3 -c "
import json,sys
m=json.load(open('$D/results/$ID/result.json'))
print('binary  ', m['apk_sha'], ' disc', m['disc_id'], ' classifier', m.get('classifier_rev'))
for r in m['runs']:
    print('run     ', r['tsv'], r['captures'], 'captures', r['exact'], 'exact',
          format(r['px'],','), 'px', '' if r['progress_log_proof'] else '  *** NO PROGRESS-LOG PROOF ***')
part=[s for s,c in m['captures_vs_goldens'].items() if c['partial']]
if part: print('PARTIAL ', ', '.join('%s %d/%d'%(s,m['captures_vs_goldens'][s]['scored'],m['captures_vs_goldens'][s]['goldens']) for s in part))
print('tsv     ', '$D/results/$ID/' + m['runs'][0]['tsv'] if m['runs'] else '(none)')
"
        exit 0
    fi
    if [ -f "$D/results/$ID/ERROR" ]; then
        echo "--- error ---"; cat "$D/results/$ID/ERROR"; exit 1
    fi
    sleep 10
done
echo "timed out waiting for $ID; check $D/results/$ID" >&2
exit 1
