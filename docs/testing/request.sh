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
REF_WAS_DEFAULTED=1
SKIP_TESTS=""
TITLE=""; SECONDS_HOLD=60; PULL_GLOB=""; EXPECT=""; NO_EXPECT=""; DEVICE=""
AUDIO_CAPTURE=""; BASE_ISO=""; PERFLOG=""; ONLY_TESTS=""
while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;
        --purpose) PURPOSE="$2"; shift 2;;
        --suites) SUITES="$2"; shift 2;;
        --tests) TESTS="$2"; shift 2;;
        --skip-tests) SKIP_TESTS="$2"; shift 2;;
        --only-tests) ONLY_TESTS="$2"; shift 2;;
        --ref) REF="$2"; REF_WAS_DEFAULTED=0; shift 2;;
        --arm) ARM="$2"; shift 2;;
        --runs) RUNS="$2"; shift 2;;
        --device) DEVICE="$2"; shift 2;;
        --title) TITLE="$2"; shift 2;;
        --seconds) SECONDS_HOLD="$2"; shift 2;;
        --pull) PULL_GLOB="$2"; shift 2;;
        --device) DEVICE="$2"; shift 2;;
        --audio-capture) AUDIO_CAPTURE="$2"; shift 2;;
        --base-iso) BASE_ISO="$2"; shift 2;;
        --perflog) PERFLOG=true; shift;;
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
# --runs is honoured only on the disc path; the soak path runs once and always
# has. Accepting it there and ignoring it hands the requester a one-sample
# noise floor while they believe they asked for N, which is worse than
# refusing -- and a repeat is what the no-oracle streams judge on, so the
# error lands where it costs most. Queue N separate soaks under one --who; the
# per-run median is the replicate, not the window.
if [ -n "$TITLE" ] && [ "${RUNS:-1}" != "1" ]; then
    cat >&2 <<MSG
refusing to queue: --runs $RUNS on a soak is silently ignored by the dispatcher.

The soak path runs the title once. Queue $RUNS separate soak requests with the
same --who instead: the replicate for a no-oracle measurement is the RUN, not
the window, and a rule over all windows tightens with every window a longer
soak happens to produce.
MSG
    exit 2
fi

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
# A SOAK needs this as much as a suites request, and used to get none of it:
# this whole block sat inside `if [ -n "$SUITES" ]`, so `--expect` on a soak
# was ACCEPTED, the file never hashed, and `expect_sha` never recorded -- so
# the verdict reads UNBOUND and the arm proves nothing. Silent, and it is the
# same shape as the detached-checkout hash fixed earlier today: the binding
# machinery present, the binding not taken.
#
# The no-oracle streams are exactly the ones that queue soaks, which makes
# this the second time a guard keyed on the suites path has exempted the runs
# with the weakest oracle. The first was affinity.py pinning on a prediction
# that soaks do not have.
if [ -n "$SUITES" ] || [ -n "$TITLE" ]; then
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

        # EVERY `expect` KEY MUST NAME A CAPTURE THAT EXISTS, checked here,
        # because after the device has run it is too late to find out that a
        # leg tested nothing.
        #
        # Measured 2026-09-13 on the #67 FRNDINT arm. Ten legs were registered
        # as `Blend tests::#spot_0_ADD` -- the DERIVED suite spelling with the
        # `::` separator used everywhere in nv2a_issues.toml and in the test
        # binary's own capture filenames. ab_compare keys its rows as
        # `"%s/%s" % r["key"]`, the RESULTS-DIRECTORY spelling: `Blend_tests/
        # #spot_0_ADD`. So all ten matched nothing. The arm came back
        # PRE-REGISTERED, every capture it named went to exactly the predicted
        # value, and the prediction's entire machine-readable half had been
        # inert -- ten legs that could not fail, on an arm whose prose called
        # them the legs a trivial fix could not satisfy.
        #
        # ab_compare does report "matched no capture" as a violation, which is
        # the right design and is also a post-mortem. Two spellings of the same
        # suite exist on purpose (the index carries results_name separately) so
        # this is not fixable by picking one; it is fixable by checking.
        #
        # The check is against the GOLDEN TREE, not the queued suites: a leg
        # naming a capture in a suite this request does not run is a different
        # error and ab_compare will catch it with real rows in hand.
        #
        # IT CHECKS ALL FOUR PREDICTION FIELDS, NOT JUST `expect`, and it
        # matches them THE WAY ab_compare MATCHES THEM. Both halves of that
        # were wrong until 2026-09-14, and one probe file showed both:
        #
        #   * `must_not_move`, `must_not_regress` and `expect_counts` were
        #     never looked at. A probe carrying `must_not_move:
        #     ["Blend tests::*"]` -- the very `::` spelling that cost the #67
        #     arm ten legs -- plus `must_not_regress: ["Nonexistent_suite/*"]`
        #     and `expect_counts: {"worst": 0}` passed all three straight
        #     through. judge() does report them afterwards, so they were not
        #     silent; they were merely discovered a device run too late, which
        #     is the cost this gate exists to avoid.
        #   * `expect` keys were compared by EXACT membership while judge()
        #     matches them with fnmatch. So `Surface_clip/*`, a legitimate leg
        #     that would have bound to all 47 Surface_clip captures, was
        #     REFUSED -- and refused with a message telling the author to
        #     write `SUITE/TestName`, which is what they had written. A gate
        #     stricter than the thing it guards sends people to fix code that
        #     is already right.
        #
        # `expect_counts` keys are checked against the four class names
        # because there is nothing else they can be. A typo there does fail in
        # judge() -- tally.get("worst") is None and None != 0 -- so this is
        # the same "a run too early" argument, not a new hole.
        python3 - "$EXPECT" "${GOLDENS:-/home/justin/goldens/results}" <<'PYEXP' || exit 2
import fnmatch, json, os, sys
exp_path, goldens = sys.argv[1], sys.argv[2]
try:
    exp = json.load(open(exp_path))
except Exception as e:
    print("--expect %s is not readable JSON: %s" % (exp_path, e), file=sys.stderr)
    sys.exit(2)

known = set()
for suite in os.listdir(goldens):
    d = os.path.join(goldens, suite)
    if not os.path.isdir(d):
        continue
    for png in os.listdir(d):
        if png.endswith(".png"):
            known.add("%s/%s" % (suite, png[:-4]))
if not known:
    print("REFUSED: no goldens under %s, so no prediction key can be checked. "
          "This gate cannot tell a good key from a bad one without them."
          % goldens, file=sys.stderr)
    sys.exit(2)

# ab_compare matches every one of these with fnmatch, so match with fnmatch.
def binds(pat):
    return any(fnmatch.fnmatch(n, pat) for n in known)

bad = []
for field in ("expect", "must_not_move", "must_not_regress"):
    v = exp.get(field)
    pats = list(v.keys()) if isinstance(v, dict) else list(v or [])
    for pat in pats:
        if not binds(pat):
            bad.append((field, pat))

CLASSES = ("better", "worse", "same", "noise")
badcount = [k for k in (exp.get("expect_counts") or {}) if k not in CLASSES]

if not bad and not badcount:
    sys.exit(0)

if bad:
    print("REFUSED: %d prediction key(s) match no capture in the goldens:"
          % len(bad), file=sys.stderr)
    for field, pat in bad:
        print("  %-16s %s" % (field, pat), file=sys.stderr)
        # The two spellings exist on purpose -- the index carries
        # results_name separately -- so offer the translation rather than
        # pretending one of them is wrong.
        cand = pat.replace(" ", "_").replace("::", "/")
        if cand != pat and binds(cand):
            print("      did you mean  %s" % cand, file=sys.stderr)
if badcount:
    print("REFUSED: %d `expect_counts` key(s) are not a capture class: %s"
          % (len(badcount), ", ".join(sorted(badcount))), file=sys.stderr)
    print("  The classes are: %s" % ", ".join(CLASSES), file=sys.stderr)
print("\n  Capture keys are RESULTS_DIRECTORY_SPELLING/TestName -- underscores\n"
      "  in the suite, a single slash -- and may contain glob wildcards, which\n"
      "  ab_compare expands against the captures both arms actually scored.\n"
      "  The `Suite name::Test` form is what the test binary and\n"
      "  nv2a_issues.toml use, and ab_compare will never match it.\n"
      "  A leg that matches no capture cannot fail, and an arm full of them\n"
      "  comes back PRE-REGISTERED with nothing measured.", file=sys.stderr)
sys.exit(2)
PYEXP
    elif [ -n "$NO_EXPECT" ]; then
        EXPECT_SHA=""
        echo "queuing without a prediction: $NO_EXPECT" >&2
    else
        cat >&2 <<'MSG'
refusing to queue: this request needs --expect FILE or --no-expect REASON.

A SOAK needs it too. A soak writes no captures, so ab_compare cannot judge it
and its legs have to be read off the logcat by hand -- which makes the
registered prediction the only thing standing between a soak result and a
story told afterwards. --no-expect is the right answer for a baseline, a
survey or a noise-floor run; say which.

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
# --tests IS ACCEPTED, RECORDED, DOCUMENTED, AND SILENTLY IGNORED. It is parsed
# above, written into the request JSON, and named in dispatcher.sh's own header
# as "optional, solo arm only" -- but the dispatcher builds make_test_iso.py's
# arguments from `suites` and `skip_tests` ONLY and never reads `tests`. So a
# requester narrowing a run to three captures silently gets the whole suite, and
# an arm that was meant to isolate one test measures hundreds.
#
# Refused rather than quietly honoured-as-nothing, which is the rule the rest of
# this file follows. Implementing it is a real change to make_test_iso.py -- the
# config schema has the right polarity already (`skip_tests_by_default`, which
# it sets for `--suite`), so an allow-list is a few hundred bytes -- but a silent
# drop must not wait for that.
if [ -n "$TESTS" ]; then
    # Quoted heredoc: the message names shell-ish identifiers, and an unquoted
    # one ran them as commands. Third time that footgun has landed today.
    cat >&2 <<'MSG'
refusing to queue: --tests is not implemented and would be silently ignored.

The dispatcher builds the disc from "suites" and "skip_tests" only; it never
reads "tests", so this request would run the WHOLE suite while reporting that
it was narrowed. dispatcher.sh's header documented the field, which is worse
than not mentioning it; that line now says NOT IMPLEMENTED.

Use --only-tests "Suite::Test,Suite::Other" instead. That is the allow-list and
it IS implemented: make_test_iso.py --only-test sets the suite to
{"skipped": true} and each named test to {"skipped": false}, which
runtime_config.cpp's ApplyConfig resolves in that order -- a per-test entry
overrides the suite default, and a suite left with no enabled tests is dropped.
MSG
    exit 2
fi

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
# --only-tests: validated here, and checked against the SNAPSHOT the dispatcher
# actually runs rather than against the tree.
#
# That distinction is the whole point. `dispatcher.sh` copies its helpers into
# $DISPATCH_DIR/bin at re-exec and runs THOSE, and its re-exec hash covers only
# dispatcher.sh, soak_title.sh, run_disc.sh and score_sweep.py -- make_test_iso.py
# is snapshotted but NOT hashed. So a tree that has --only-test can be served by
# a snapshot that does not, and the request would reach an argparse that has
# never heard of the flag. Checking the tree, as the --skip-tests guard above
# does, is a proxy; checking the snapshot is the truth, and it distinguishes
# "not merged yet" from "merged, restart the dispatcher".
if [ -n "$ONLY_TESTS" ]; then
    SNAPBIN="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}/bin"
    SERVER="${DISPATCH_TREE:-/home/justin/hakuX}/docs/testing"
    if ! grep -q -- --only-test "$SNAPBIN/make_test_iso.py" 2>/dev/null \
       || ! grep -q only_tests "$SNAPBIN/dispatcher.sh" 2>/dev/null; then
        # BOTH files, because this flag needs both halves: make_test_iso.py to
        # understand --only-test and dispatcher.sh to pass it. Checking one
        # would print "merged, restart the dispatcher" while the other half was
        # still unmerged, sending the reader to restart something that cannot
        # help -- a refusal whose remedy does not work is worse than a blunt one.
        if grep -q -- --only-test "$SERVER/make_test_iso.py" 2>/dev/null \
           && grep -q only_tests "$SERVER/dispatcher.sh" 2>/dev/null; then
            echo "refusing to queue: --only-tests is merged but the SERVING dispatcher" >&2
            echo "still runs an older snapshot ($SNAPBIN). Restart it, or touch one of" >&2
            echo "dispatcher.sh/soak_title.sh/run_disc.sh/score_sweep.py to force its" >&2
            echo "re-exec -- make_test_iso.py alone does not trigger one." >&2
        else
            echo "refusing to queue: --only-tests is not supported by the dispatcher" >&2
            echo "that will serve this request. Merge the --only-test support first." >&2
        fi
        exit 2
    fi
    if [ -z "$SUITES" ]; then
        echo "--only-tests needs --suites: the allow-list narrows WITHIN a suite." >&2
        exit 2
    fi
    BADO=$(python3 - "$ONLY_TESTS" "$SUITES" <<'PYEOF'
import sys
only, suites = sys.argv[1], sys.argv[2]
have = {s.strip() for s in suites.split(",") if s.strip()}
bad = []
for t in only.split(","):
    t = t.strip()
    if not t:
        continue
    if "::" not in t:
        print("MALFORMED:" + t)
        raise SystemExit(0)
    suite = t.split("::")[0].strip().replace("_", " ")
    if suite not in have and suite.replace(" ", "_") not in have:
        bad.append(suite)
print(",".join(sorted(set(bad))))
PYEOF
)
    case "$BADO" in
        MALFORMED:*)
            echo "refusing to queue: --only-tests wants \"Suite::Test\", got \"${BADO#MALFORMED:}\"." >&2
            exit 2 ;;
    esac
    if [ -n "$BADO" ]; then
        echo "refusing to queue: --only-tests names $BADO, which --suites does not run." >&2
        echo "  suites being run: $SUITES" >&2
        echo "make_test_iso.py refuses this too, but after the claim and the build." >&2
        exit 2
    fi
    if [ -n "$SKIP_TESTS" ]; then
        echo "refusing to queue: --only-tests and --skip-tests both given. They" >&2
        echo "resolve through the same per-test map, so combining them cannot mean" >&2
        echo "what it looks like. Use one." >&2
        exit 2
    fi
fi

# A NARROWED REQUEST IS USUALLY HALF OF A COMPARISON, AND --ref DEFAULTS TO
# HEAD, WHICH IS USUALLY THE WRONG HALF.
#
# `--only-tests` and `--skip-tests` narrow a disc to compare its numbers with
# something -- the same captures in company, an earlier arm, a scoreboard
# column. That partner was almost never taken at HEAD, and HEAD is what this
# script fills in when nobody says otherwise. So the default silently adds a
# second variable to a measurement built to have one.
#
# Twice within an hour on 2026-09-13, and the second time it mattered: a
# leakage probe was queued at HEAD to be compared against a sweep column
# 31 hw/ commits behind, which would have mixed disc composition with 31
# commits of renderer change. It was already claimed before I noticed, and the
# recovery was to queue the in-company half at the SAME ref rather than to
# reuse the column.
#
# Advisory rather than refusal: a narrowed disc at HEAD is perfectly correct
# when the partner is also at HEAD, and this script cannot know which arm you
# mean. Printing the ref it chose is enough to make the question askable.
if { [ -n "$ONLY_TESTS" ] || [ -n "$SKIP_TESTS" ]; } && [ "$REF_WAS_DEFAULTED" = 1 ]; then
    echo "note: this request narrows the disc and no --ref was given, so it" >&2
    echo "      resolved to HEAD ($REF). A narrowed disc is usually compared" >&2
    echo "      with the same captures elsewhere -- if that partner is at a" >&2
    echo "      different ref, pass --ref to match it, or the comparison" >&2
    echo "      carries a binary difference as well as a disc difference." >&2
fi

# A NAMED BASE ISO IS RESOLVED AND CHECKED HERE, not on the device.
#
# The dispatcher refuses a request whose base_iso is missing rather than
# falling back to stock, which is right -- but it refuses AFTER a claim, after
# a build, and to a log nobody is reading. The same check costs nothing here
# and fails in front of the person who typed the path.
#
# Resolved to an absolute path because the dispatcher's cwd is not the
# requester's, and because disc_id keys on the BASENAME plus size plus mtime:
# a relative path that happened to resolve differently would tag two different
# discs identically, which is the one thing that field exists to prevent.
if [ -n "$BASE_ISO" ]; then
    if [ ! -f "$BASE_ISO" ]; then
        echo "--base-iso: no such file: $BASE_ISO" >&2
        exit 2
    fi
    BASE_ISO=$(cd "$(dirname "$BASE_ISO")" && printf '%s/%s' "$(pwd)" "$(basename "$BASE_ISO")")
    # A soak plays a commercial title and never builds a test disc, so a base
    # ISO there is a request that reads as meaningful and is silently ignored.
    if [ -n "$TITLE" ]; then
        echo "--base-iso is meaningless on a soak (--title): the disc is the title." >&2
        exit 2
    fi
fi

python3 - "$D/queue/.$ID.req.tmp" "$ID" "$WHO" "$PURPOSE" "$SUITES" "$REF" "$ARM" "$RUNS" "$TESTS" "$TITLE" "$SECONDS_HOLD" "$PULL_GLOB" "$EXPECT" "${EXPECT_SHA:-}" "$NO_EXPECT" "$SKIP_TESTS" "$DEVICE" "$AUDIO_CAPTURE" "$BASE_ISO" "$PERFLOG" "$ONLY_TESTS" <<'PY'
import json, sys
(p, i, who, purpose, suites, ref, arm, runs, tests, title, seconds,
 pull_glob, expect, expect_sha, no_expect, skip_tests, device,
 arm_audio, base_iso, perflog, only_tests) = sys.argv[1:22]
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
           "base_iso": base_iso,
           "perflog": perflog,
           "only_tests": [t.strip() for t in only_tests.split(",") if t.strip()],
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
# A SOAK has no disc_id, no runs[] and no captures_vs_goldens, so the disc
# reader below died with KeyError: 'disc_id' rather than printing anything --
# which made --wait unusable for exactly the stream that most needs to watch a
# run finish, since a soak's legs are read off the logcat by hand.
if m.get('kind') == 'soak':
    print('binary  ', m['apk_sha'], ' device', m.get('device_label') or '(UNRECORDED)',
          ' classifier', m.get('classifier_rev', '?'))
    print('soak    ', m.get('title','?'), m.get('seconds','?'), 's,',
          m.get('logcat_lines','?'), 'log lines')
    for f in m.get('pulled') or []:
        print('pulled  ', f['file'], format(f['bytes'],','), 'bytes')
    if not (m.get('pulled') or []):
        print('pulled   (nothing)')
    print('logcat  ', '$D/results/$ID/logcat.txt')
    raise SystemExit(0)
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
