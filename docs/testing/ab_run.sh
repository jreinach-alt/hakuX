#!/usr/bin/env bash
#
# Run one A/B: a fix commit against its own parent, same suites, same disc.
#
#   ab_run.sh --who blend48b --fix c6dd6fcdfb --suites "Blend surface,Blend tests" \
#             --prediction "DstAlpha_ARGB8 -> 0" \
#             --expect-value Blend_surface/DstAlpha_ARGB8=0 \
#             --must-not-move 'Blend_tests/*'
#
#   ab_run.sh ... --dry-run      print the two requests and stop
#   ab_run.sh --resume ID_A,ID_B [--expect FILE]   pick a wait back up
#
# About a dozen A/Bs were hand-rolled on 2026-09-12 and all of them were this:
# resolve two refs, queue two request.sh arms differing only in --ref, wait for
# both, compare per capture. The hand version is six commands and four of them
# have a trap in them, so this is the script that would have saved the most
# time that day.
#
# It refuses more than it runs. Each refusal below is a thing that actually
# went wrong:
#
#   * **The parent is derived, not typed.** A baseline ref typed by hand is a
#     ref that can be wrong by one commit and still look plausible.
#   * **A merge has two parents**, so "its parent" is not a thing. Refused
#     unless --parent names which one.
#   * **Refs are resolved in the tree the DISPATCHER builds in**, not in the
#     caller's, because that is the tree the APK comes out of. request.sh
#     resolves against its own checkout, which correctly fixes the --ref HEAD
#     problem but is the wrong tree when the two differ.
#
#     MEASURED, and narrower than it first looked: a git worktree SHARES the
#     object database -- `git rev-parse --git-common-dir` is
#     /home/justin/hakuX/.git for every agent worktree here -- so a commit
#     made in an agent's worktree is already resolvable, and buildable, from
#     the dispatch tree. The check below was written expecting to fire for
#     worktree agents and does not. It still fires for the remote lane, a
#     second session on another machine with its own checkout (see
#     docs/orchestration.md), where a ref really can be absent; and for a typo.
#   * **--ref HEAD is never passed on.** A baseline arm was queued as HEAD on
#     2026-09-12, sat in the queue while three commits landed, and would have
#     built the very change it was the baseline for. Both arms here are
#     concrete shas resolved before anything is queued.
#   * **A dirty dispatch tree** means the binary is not the ref. The
#     dispatcher refuses it -- but only for a ref it has to build, since a
#     cached APK needs no checkout, so this checks the cache and only refuses
#     when a build is actually required.
#   * **A prediction is registered before the arms are queued**, so its
#     timestamp is evidence rather than a claim. --no-expect opts out, loudly.
#
# The two request ids are printed as soon as they are queued, before the wait,
# because the wait is the part that gets killed: use --resume with them rather
# than queueing the device work a second time.
set -u

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TREE="${DISPATCH_TREE:-/home/justin/hakuX}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"

WHO=""; FIX=""; PARENT=""; SUITES=""; RUNS=1; PURPOSE=""; TIMEOUT=3600
EXPECT=""; PREDICTION=""; NO_EXPECT=0; DRY=0; RESUME=""; ISSUE=""
MNM=(); EV=(); EC=()

usage() { sed -n '2,45p' "$0" | sed 's/^#//; s/^ //'; exit "${1:-2}"; }

while [ $# -gt 0 ]; do
    case "$1" in
        --who) WHO="$2"; shift 2;;
        --fix) FIX="$2"; shift 2;;
        --parent) PARENT="$2"; shift 2;;
        --suites) SUITES="$2"; shift 2;;
        --runs) RUNS="$2"; shift 2;;
        --purpose) PURPOSE="$2"; shift 2;;
        --issue) ISSUE="$2"; shift 2;;
        --timeout) TIMEOUT="$2"; shift 2;;
        --expect) EXPECT="$2"; shift 2;;
        --prediction) PREDICTION="$2"; shift 2;;
        --must-not-move) MNM+=("$2"); shift 2;;
        --expect-value) EV+=("$2"); shift 2;;
        --expect-count) EC+=("$2"); shift 2;;
        --no-expect) NO_EXPECT=1; shift;;
        --dry-run) DRY=1; shift;;
        --resume) RESUME="$2"; shift 2;;
        -h|--help) usage 0;;
        *) echo "unknown option $1" >&2; usage;;
    esac
done

fail() { echo "ab_run: $*" >&2; exit 2; }

# ---------------------------------------------------------------- resume path
if [ -n "$RESUME" ]; then
    IDA="${RESUME%%,*}"; IDB="${RESUME##*,}"
    [ "$IDA" != "$IDB" ] || fail "--resume wants two ids separated by a comma"
    echo "resuming wait on $IDA and $IDB"
else
    [ -n "$WHO" ] || fail "need --who (names both result dirs: WHO-base, WHO-fix)"
    [ -n "$FIX" ] || fail "need --fix REF"
    [ -n "$SUITES" ] || fail "need --suites (identical in both arms, by construction)"

    # -- resolve, in the dispatcher's tree ---------------------------------
    in_tree() { git -C "$TREE" rev-parse --short --verify "$1^{commit}" 2>/dev/null; }
    FIX_SHA=$(in_tree "$FIX") || FIX_SHA=""
    if [ -z "$FIX_SHA" ]; then
        if git -C "$HERE/../.." rev-parse --verify "$FIX^{commit}" >/dev/null 2>&1; then
            fail "--fix $FIX exists in this checkout but NOT in the dispatch tree
       $TREE, which is where the dispatcher builds. Push or fetch it there
       first; queued as-is it would resolve now and fail to build later, and
       that failure reads like a device fault. (An agent worktree on this
       machine shares the object database and will not reach this; a separate
       checkout on another machine will.)"
        fi
        fail "cannot resolve --fix $FIX to a commit in $TREE"
    fi
    case "$FIX" in HEAD|head) echo "ab_run: --fix HEAD resolved to $FIX_SHA; the arms carry the sha, not the name" >&2;; esac

    if [ -n "$PARENT" ]; then
        PAR_SHA=$(in_tree "$PARENT") || fail "cannot resolve --parent $PARENT in $TREE"
    else
        # A merge has two parents, so "the parent" is not well defined and
        # picking ^1 silently would make the baseline the wrong side of the
        # merge -- which looks exactly like a working comparison.
        NPAR=$(git -C "$TREE" rev-list --parents -n1 "$FIX_SHA" | wc -w)
        if [ "$NPAR" -gt 2 ]; then
            fail "$FIX_SHA is a merge with $((NPAR-1)) parents; 'its parent' is
       ambiguous. Name the baseline explicitly with --parent."
        fi
        [ "$NPAR" -eq 2 ] || fail "$FIX_SHA is a root commit; it has no parent to compare against"
        PAR_SHA=$(in_tree "$FIX_SHA^") || fail "cannot resolve $FIX_SHA^"
    fi
    [ "$FIX_SHA" != "$PAR_SHA" ] || fail "both arms resolved to $FIX_SHA; there is no independent variable"

    # -- the tree must be clean, but only if a build is needed -------------
    DIRTY=$(git -C "$TREE" status --porcelain | grep -v '^??' | head -3 || true)
    NEED=()
    for s in "$FIX_SHA" "$PAR_SHA"; do
        [ -f "$D/builds/$s.apk" ] || NEED+=("$s")
    done
    if [ -n "$DIRTY" ] && [ "${#NEED[@]}" -gt 0 ]; then
        fail "$TREE has uncommitted changes and ${NEED[*]} still needs building.
       A dirty tree means the binary is not the ref, so the dispatcher will
       refuse the build. Commit or stash in that tree first.
$DIRTY"
    fi

    echo "=== A/B for ${ISSUE:+#$ISSUE }${WHO} ==="
    git -C "$TREE" log -1 --format='  fix      %h %ad %s' --date=short "$FIX_SHA"
    git -C "$TREE" log -1 --format='  baseline %h %ad %s' --date=short "$PAR_SHA"
    echo "  suites   $SUITES"
    echo "  runs     $RUNS per arm"
    if [ "${#NEED[@]}" -eq 0 ]; then
        echo "  builds   both APKs already cached; no gradle run needed"
    else
        echo "  builds   ${NEED[*]} must be built (~2-5 min each)"
    fi

    # -- register the prediction, BEFORE queueing --------------------------
    if [ -n "$EXPECT" ]; then
        [ -f "$EXPECT" ] || fail "--expect $EXPECT does not exist. Register it with
       ab_compare.py --register before the arms run, not after."
        echo "  expect   $EXPECT (already registered)"
    elif [ "$NO_EXPECT" = 1 ]; then
        echo "  expect   NONE (--no-expect). This measurement will be reported"
        echo "           UNJUDGED: four of 2026-09-12's retractions would have"
        echo "           been caught at the prediction stage."
    elif [ "${#MNM[@]}" -eq 0 ] && [ "${#EV[@]}" -eq 0 ] && [ "${#EC[@]}" -eq 0 ]; then
        fail "no prediction. Give --expect FILE, or at least one of
       --must-not-move GLOB / --expect-value CAPTURE=PX / --expect-count CLASS=N
       (optionally with --prediction 'prose'), or --no-expect to say so out loud.
       A prediction registered after the measurement is a description of it."
    else
        EXPECT="$D/expect/${WHO}-${PAR_SHA}-${FIX_SHA}.json"
        args=(--register "$EXPECT" --who "$WHO" --issue "$ISSUE"
              --a-ref "$PAR_SHA" --b-ref "$FIX_SHA" --prediction "$PREDICTION")
        for x in "${MNM[@]:-}"; do [ -n "$x" ] && args+=(--must-not-move "$x"); done
        for x in "${EV[@]:-}"; do [ -n "$x" ] && args+=(--expect-value "$x"); done
        for x in "${EC[@]:-}"; do [ -n "$x" ] && args+=(--expect-count "$x"); done
        if [ "$DRY" = 1 ]; then
            # A dry run creates nothing at all, not even the directory: it is
            # what gets used to check a command before spending device time,
            # so it has to be side-effect free to be worth anything.
            echo "  expect   would register $EXPECT"
        else
            mkdir -p "$D/expect"
            python3 "$HERE/ab_compare.py" "${args[@]}" >/dev/null || exit 2
            echo "  expect   registered $EXPECT"
        fi
    fi

    # -- queue both arms ---------------------------------------------------
    # Concrete shas, never a name. The baseline goes first so that if the
    # queue is only served once more today, the arm that does not exist yet
    # is the one that waits.
    PURP_A="BASE arm ${ISSUE:+#$ISSUE }$WHO at $PAR_SHA. ${PURPOSE:-}${PREDICTION:+ Predicted: $PREDICTION}"
    PURP_B="FIX arm ${ISSUE:+#$ISSUE }$WHO at $FIX_SHA. ${PURPOSE:-}${PREDICTION:+ Predicted: $PREDICTION}"
    if [ "$DRY" = 1 ]; then
        echo
        echo "--- dry run: would queue these two arms, and nothing else ---"
        echo "request.sh --who $WHO-base --ref $PAR_SHA --suites '$SUITES' --runs $RUNS \\"
        echo "           --purpose '$PURP_A'"
        echo "request.sh --who $WHO-fix  --ref $FIX_SHA --suites '$SUITES' --runs $RUNS \\"
        echo "           --purpose '$PURP_B'"
        echo
        echo "then: ab_compare.py --a \$D/results/<base-id> --b \$D/results/<fix-id>${EXPECT:+ --expect $EXPECT}"
        exit 0
    fi

    qa=$(bash "$HERE/request.sh" --who "$WHO-base" --ref "$PAR_SHA" \
             --suites "$SUITES" --runs "$RUNS" --purpose "$PURP_A") \
        || fail "queueing the baseline arm failed"
    qb=$(bash "$HERE/request.sh" --who "$WHO-fix" --ref "$FIX_SHA" \
             --suites "$SUITES" --runs "$RUNS" --purpose "$PURP_B") \
        || fail "queueing the fix arm failed"
    IDA="${qa##* }"; IDB="${qb##* }"
    echo
    echo "queued  base $IDA"
    echo "queued  fix  $IDB"
    echo "resume with: $0 --resume $IDA,$IDB${EXPECT:+ --expect $EXPECT}"
fi

# ------------------------------------------------------------------ the wait
RA="$D/results/$IDA"; RB="$D/results/$IDB"
echo
deadline=$(( $(date +%s) + TIMEOUT ))
last=""
while :; do
    sa="wait"; sb="wait"
    [ -f "$RA/DONE" ] && sa="done"; [ -f "$RA/ERROR" ] && sa="ERROR"
    [ -f "$RB/DONE" ] && sb="done"; [ -f "$RB/ERROR" ] && sb="ERROR"
    now=$(date +%s)
    line="base $sa   fix $sb"
    [ "$line" = "$last" ] || { echo "$(date '+%H:%M:%S')  $line"; last="$line"; }
    case "$sa$sb" in
        *ERROR*)
            echo "ab_run: an arm failed on the device:" >&2
            [ "$sa" = ERROR ] && { echo "  base:"; sed 's/^/    /' "$RA/ERROR"; }
            [ "$sb" = ERROR ] && { echo "  fix:";  sed 's/^/    /' "$RB/ERROR"; }
            echo "Requeue the failed arm. Do NOT compare against the arm that" >&2
            echo "did complete: a half-run arm is absent, not zero." >&2
            exit 2;;
    esac
    [ "$sa" = done ] && [ "$sb" = done ] && break
    if [ "$now" -ge "$deadline" ]; then
        echo "ab_run: timed out after ${TIMEOUT}s with base=$sa fix=$sb." >&2
        echo "The device work is not lost; resume with:" >&2
        echo "  $0 --resume $IDA,$IDB${EXPECT:+ --expect $EXPECT}" >&2
        exit 2
    fi
    sleep 15
done

echo
exec python3 "$HERE/ab_compare.py" --a "$RA" --b "$RB" ${EXPECT:+--expect "$EXPECT"}
