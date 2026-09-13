#!/usr/bin/env bash
#
# Ask the dispatcher to run tests, and wait for the result.
#
#   request.sh --who bump-agent --purpose "bump map baseline" \
#              --suites "Bump map,Bump env lum" [--ref HEAD] [--runs 1] [--wait] \
#              [--skip-tests "Suite::Test,..."] [--device nova|thor] \
#              (--expect predictions/x.json | --no-expect "why not")
#
#   request.sh --who audio --purpose "baseline" --title "Galleon (USA).xiso.iso" \
#              --seconds 90 --pull 'apu_monitor.s16le48k2ch.pcm*' \
#              --device nova --no-expect "survey, not an A/B arm"
#
# --device pins the request to one handheld. The dispatcher and affinity.py
# have honoured a `device` field since the second device arrived; this is the
# only thing that could not set it, so a soak on a title only one device has
# had to be queued by hand. Use it for exactly that -- an A/B does not need
# it, because affinity.py already pins both arms to wherever the first landed.
#
# --skip-tests drops named tests from the disc. Needed when a test poisons the
# tests after it: "Texture render target::RenderTextureLoop" leaves the texture
# stage disabled, and the 40 TexFmt_* tests after it then render flat black --
# 3,209,634 px against 324,349 for the same build on a no-loop disc.
#
# Agents never touch the device. This is the only way in, and it is deliberately
# narrow: a request names a *ref*, not "what is in my tree", because with
# several implementers holding uncommitted work "run my build" is ambiguous the
# moment two of them ask.
#
# --wait blocks until the result lands and then prints the summary. Without it,
# the request id is printed and the caller can poll result.json.
#
# --device nova|thor pins the request to one handheld. The dispatcher side has
# honoured a `device` field since affinity.py's rule 1 -- "an explicit device
# field in the request wins" -- but there was no way for a requester to set it,
# so the only pin available was the implicit A/B one (both arms follow their
# shared prediction file). Two things need the explicit pin: a soak on a title
# only one device has, and a repeat run that must land on the SAME handheld as
# the baseline it is being compared with. The second is the one that bites
# quietly: an unpinned repeat is free, so it lands wherever is idle, and a level
# measured on the Nova then gets compared against one from the Thor while being
# reported as a repeat of the same experiment.
set -u
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
WHO=""; PURPOSE=""; SUITES=""; REF="HEAD"; RUNS=1; WAIT=0; ARM="company"; TESTS=""
SKIP_TESTS=""
TITLE=""; SECONDS_HOLD=60; PULL_GLOB=""; EXPECT=""; NO_EXPECT=""; DEVICE=""
AUDIO_CAPTURE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;
        --purpose) PURPOSE="$2"; shift 2;;
        --suites) SUITES="$2"; shift 2;;
        --tests) TESTS="$2"; shift 2;;
        --skip-tests) SKIP_TESTS="$2"; shift 2;;
        --ref) REF="$2"; shift 2;;
        --arm) ARM="$2"; shift 2;;
        --runs) RUNS="$2"; shift 2;;
        --device) DEVICE="$2"; shift 2;;
        --title) TITLE="$2"; shift 2;;
        --seconds) SECONDS_HOLD="$2"; shift 2;;
        --pull) PULL_GLOB="$2"; shift 2;;
        --device) DEVICE="$2"; shift 2;;
        --audio-capture) AUDIO_CAPTURE="$2"; shift 2;;
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

# A misspelt device label does not fail loudly; it matches no worker, so the
# request is simply never claimed and sits in the queue looking queued. Check
# it against the device table rather than against a hardcoded pair, so adding a
# third handheld to devices.sh does not silently start rejecting it here.
if [ -n "$DEVICE" ]; then
    KNOWN=$(sed -n 's/.*DEVICE_LABEL="\([a-z0-9]*\)".*/\1/p' "$(dirname "$0")/devices.sh")
    printf '%s\n' "$KNOWN" | grep -qx "$DEVICE" || {
        echo "unknown --device '$DEVICE'; devices.sh knows:" >&2
        printf '  %s\n' $KNOWN >&2
        exit 2
    }
fi

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
        # Resolve and hash under the BUILD LOCK. The dispatcher detaches this
        # same checkout to build a baseline ref, so for the length of any
        # build the prediction file is whatever that commit carried: absent
        # if it is newer than the ref -- which is how this was found, a queue
        # refusing a file that plainly existed -- or, far worse, an OLDER
        # VERSION of the same path, which hashes cleanly and binds the arm to
        # a prediction nobody wrote. flock is the same lock build_ref takes,
        # so this waits for the build rather than reading through it.
        EXPECT_LOCK="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}/.build.lock"
        : > "$EXPECT_LOCK" 2>/dev/null || true
        read -r EXPECT EXPECT_SHA < <(flock "$EXPECT_LOCK" bash -c '
            [ -f "$1" ] || exit 3
            printf "%s %s\n" \
                "$(cd "$(dirname "$1")" && pwd)/$(basename "$1")" \
                "$(sha256sum "$1" | cut -d" " -f1)"' _ "$EXPECT") || {
            echo "--expect $EXPECT does not exist. Register it first: ab_compare.py --register $EXPECT --a-ref ... --b-ref ..." >&2
            exit 2; }
        [ -n "$EXPECT_SHA" ] || { echo "could not hash --expect $EXPECT" >&2; exit 2; }
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

# A skip_tests request served by a dispatcher that does not understand the
# field is the worst possible outcome: the field is silently ignored, the disc
# is built WITH the poisoning test, and the result is filed as though it were
# the measurement that was asked for. For `Texture render target` that is the
# difference between 324,349 px and 3,209,634 px, and the run would look
# perfectly healthy.
#
# So check the dispatcher that will actually serve this -- the one under
# DISPATCH_TREE, not the copy in the requester's own worktree -- and refuse
# loudly instead. The check clears itself the moment the change is merged and
# the serving dispatcher is restarted.
if [ -n "$SKIP_TESTS" ]; then
    SERVER="${DISPATCH_TREE:-/home/justin/hakuX}/docs/testing"
    if ! grep -q skip_tests "$SERVER/dispatcher.sh" 2>/dev/null \
       || ! grep -q -- --skip-test "$SERVER/make_test_iso.py" 2>/dev/null; then
        cat >&2 <<MSG
refusing to queue: --skip-tests was asked for, but the dispatcher that will
serve this request does not support it:

  $SERVER

An older dispatcher ignores skip_tests silently and builds the disc WITH the
test you asked to drop, then files the result as the measurement you wanted.
Merge the --skip-test support and restart the serving dispatcher first.
MSG
        exit 2
    fi
fi

# A skip naming a suite that is not being run is refused HERE, not by the disc
# builder. make_test_iso.py already refuses it -- correctly, because a skip
# whose suite is absent is a typo and silently honouring it would build a disc
# nobody asked for -- but it refuses on the DEVICE side: after the claim, after
# a build, after the install. On 2026-09-12 that cost an A/B arm a queue slot
# and a detached-checkout build to learn that "Texture render target" was not
# in the seven suites the arm ran. The information needed to say so was in the
# request the whole time.
if [ -n "$SKIP_TESTS" ] && [ -n "$SUITES" ]; then
    BAD=$(python3 - "$SKIP_TESTS" "$SUITES" <<'PYEOF'
import sys
skips, suites = sys.argv[1], sys.argv[2]
have = {s.strip() for s in suites.split(",") if s.strip()}
bad = []
for t in skips.split(","):
    t = t.strip()
    if not t:
        continue
    suite = t.split("::")[0].strip()
    if suite not in have:
        bad.append(suite)
print(",".join(sorted(set(bad))))
PYEOF
)
    if [ -n "$BAD" ]; then
        cat >&2 <<MSG
refusing to queue: --skip-tests names a suite that --suites does not run.

  skip names a test in: $BAD
  suites being run:     $SUITES

make_test_iso.py refuses this too, and is right to -- a skip whose suite is
absent is a typo, and honouring it silently builds a disc nobody asked for.
But it refuses after the claim, the build and the install, which is a queue
slot and a detached-checkout build spent on a typo. Fix the name, or drop the
skip if that suite is genuinely not in this arm.
MSG
        exit 2
    fi
fi

# Same shape as the skip_tests guard above, and for a failure that has already
# happened rather than one that might. A dispatcher that does not understand
# `audio_capture` ignores it silently, runs the soak with the capture unarmed,
# and the pull then returns whatever PCM an EARLIER experiment left on the
# device -- which measures as a clean, plausible baseline. That is precisely
# what a 24 MB file from a soak four hours earlier did on 2026-09-12; it was
# caught only because 126.976 s of audio cannot come out of a 95 s app
# lifetime. Refuse instead.
if [ -n "$AUDIO_CAPTURE" ]; then
    case "$AUDIO_CAPTURE" in
        ''|*[!0-9]*) echo "--audio-capture takes a size cap in MB, got '$AUDIO_CAPTURE'" >&2; exit 2;;
    esac
    [ -n "$TITLE" ] || { echo "--audio-capture only means anything on a soak (--title)" >&2; exit 2; }
    # Check the SNAPSHOT, not the source tree. The worker does not run
    # docs/testing/dispatcher.sh: it copies the scripts to $DISPATCH_DIR/bin at
    # startup and `exec`s that copy, deliberately, so that build_ref detaching
    # the source tree cannot exec a foreign ref's dispatcher mid-build.
    #
    # The consequence is that the source tree supporting a field says nothing
    # about whether the running worker does, and the snapshot has no way to
    # notice it is stale -- once a worker has re-execed into the snapshot,
    # $HERE IS the snapshot, so the re-exec hash at dispatcher.sh:537 compares
    # the copy against itself and can never fire again.
    #
    # This guard checked the source tree and therefore passed on 2026-09-12
    # while the 22:16 snapshot silently dropped audio_capture: the request
    # recorded "audio_capture": "30", the soak ran with the capture off, and
    # the pull came back empty. That empty pull is the good outcome and only
    # because the previous pass made soak_title delete the old capture first --
    # with a stale PCM on the device it would have been filed as the
    # measurement. Check both, and name whichever one is behind.
    SERVER="${DISPATCH_TREE:-/home/justin/hakuX}/docs/testing"
    SNAP="${DISPATCH_DIR:-$D}/bin"
    STALE=""
    for where in "$SERVER" "$SNAP"; do
        [ -f "$where/dispatcher.sh" ] || continue
        if ! grep -q audio_capture "$where/dispatcher.sh" 2>/dev/null \
           || ! grep -q AUDIO_CAPTURE_MB "$where/soak_title.sh" 2>/dev/null; then
            STALE="$STALE $where"
        fi
    done
    if [ -n "$STALE" ]; then
        cat >&2 <<MSG
refusing to queue: --audio-capture was asked for, but the dispatcher that will
serve this request does not arm the capture:
$(printf '\n  %s' $STALE)

It would run the soak with the capture off. The pull then returns nothing, or
-- worse -- whatever PCM an earlier experiment left on the device, which
measures as a clean, plausible baseline. That is exactly what a 24 MB file from
a soak four hours earlier did on 2026-09-12; it was caught only because
126.976 s of audio cannot come out of a 95 s app lifetime.

If the path above ends in /bin it is the SNAPSHOT the worker execs, not the
source tree. Merging is not enough: the serving dispatcher must be RESTARTED,
because a worker that has already re-execed into the snapshot hashes it against
itself and will never pick the change up on its own.

Until then the capture can be armed by hand, once, on the device:
  adb -s <serial> shell 'echo 30 > /sdcard/Android/data/com.jreinach.hakux.debug/files/audio_capture.on'
and a capture taken that way MUST be dated against the run that produced it --
captured seconds cannot exceed the app's lifetime -- because an unarmed
soak_title also does not delete the previous capture.
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
# Written to a dotfile and renamed into place, because the dispatcher globs
# `queue/*.req` and a claim is an atomic rename of whatever it finds. Writing
# the JSON directly into the queue leaves a window in which a worker can claim
# and parse a half-written request -- and `jq_get` answers a missing field with
# its default rather than an error, so the visible outcome of losing that race
# is not a crash. It is a request that silently ran with `device` empty, i.e.
# on whichever handheld was idle, which is the one thing the field exists to
# prevent.
python3 - "$D/queue/.$ID.req.tmp" "$ID" "$WHO" "$PURPOSE" "$SUITES" "$REF" "$ARM" "$RUNS" "$TESTS" "$TITLE" "$SECONDS_HOLD" "$PULL_GLOB" "$EXPECT" "${EXPECT_SHA:-}" "$NO_EXPECT" "$SKIP_TESTS" "$DEVICE" "$AUDIO_CAPTURE" <<'PY'
import json, sys
(p, i, who, purpose, suites, ref, arm, runs, tests, title, seconds,
 pull_glob, expect, expect_sha, no_expect, skip_tests, device,
 arm_audio) = sys.argv[1:19]
json.dump({"id": i, "requester": who, "purpose": purpose,
           "suites": [s.strip() for s in suites.split(",") if s.strip()],
           "tests": [t.strip() for t in tests.split(",") if t.strip()],
           "skip_tests": [t.strip() for t in skip_tests.split(",") if t.strip()],
           "ref": ref, "arm": arm, "runs": int(runs),
           "title": title, "seconds": int(seconds),
           "device": device,
           "pull_glob": pull_glob,
           "device": device,
           "audio_capture": arm_audio,
           "expect": expect, "expect_sha": expect_sha,
           "no_expect": no_expect,
           "queued_utc": __import__("datetime").datetime.now(
               __import__("datetime").timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(p, "w"), indent=2)
PY
mv "$D/queue/.$ID.req.tmp" "$D/queue/$ID.req"
echo "queued $ID${DEVICE:+ (pinned to $DEVICE)}"
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
