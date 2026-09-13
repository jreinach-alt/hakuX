#!/usr/bin/env bash
#
#   queue_full_sweep.sh <ref> [label]
#
# Queue one idle-priority request per golden suite, so the whole corpus is
# scored against one binary.
#
# Why this is a script and not a loop someone types
# -------------------------------------------------
#
# The sweep is the campaign's headline measurement and it is easy to get
# subtly wrong. On 2026-09-12 the collected column turned out to have been
# built from a binary 22 -- then 31, then 35 -- commits behind the tip as the
# day's fixes landed, and it was labelled `today-partial`. Every row carried a
# consistent `apk_sha`, so the existing mixed-binary warning saw nothing:
# consistency is not currency. The column read as though the day's work had
# achieved nothing.
#
# So the ref is a REQUIRED argument and is resolved to a concrete sha here.
# `HEAD` in a queued request is a moving target -- the queue is served later,
# and a sweep that takes hours would otherwise span several binaries while
# every row claimed to be one.
#
# The `z-` prefix is load-bearing. The dispatcher serves its queue in filename
# order, so `z-*` sorts after every epoch-prefixed request and the sweep is
# pre-empted by any agent measurement. That is the whole reason a full sweep
# can run during active work instead of blocking it.
#
# Requests are written directly rather than through request.sh, because
# request.sh names its requests by epoch and they would jump the queue. They
# carry `no_expect` for the same reason request.sh demands it: a sweep is a
# survey, not an A/B arm, and nothing should later read it as a confirmation
# of anything.
#
# Tests dropped from the sweep
# ----------------------------
#
# A test that leaves state behind poisons every test the framework runs after
# it, and the sweep is exactly where that does the most damage: it is the
# number the scoreboard reports and the number issues get ranked by.
#
# `Texture render target::RenderTextureLoop` is the measured case. It ends with
# `texture_stage.SetEnabled(false)` and `SetShaderStageProgram(STAGE_NONE)`;
# the suite's other 40 tests rely on the suite `Initialize()` rather than
# setting the stage up themselves, and `RunAll` walks a `std::map`
# alphabetically, so the loop runs first and the other 40 then render with no
# texture stage. Measured 2026-09-12 on one build, one set of goldens, two
# runs, RGBA:
#
#   loop included   41 captures, 1 exact, 3,209,634 px   <- the sweep's figure
#   loop skipped    40 captures, 5 exact,   324,349 px
#
# In the loop-included captures the whole 285x285 quad is a single colour,
# opaque black, in all 40 -- and every pixel outside the quad matches the
# golden exactly. That is a disabled texture stage, not a render-to-texture
# defect, and it made this suite the largest single residual in the corpus for
# eleven issue comments.
#
# Add a row here only with that kind of measurement behind it: the cost of
# dropping a test wrongly is a silently unmeasured test.
# Keyed by the results-directory spelling. A lookup function, not an indirect
# variable expansion: two golden directories are `2D_Lines` and `3D_primitive`,
# which are not valid shell identifiers, so `${!var}` would abort the sweep.
skip_tests_for() {
    case "$1" in
        Texture_render_target) echo "Texture render target::RenderTextureLoop";;
        *) echo "";;
    esac
}

set -u

REF="${1:?usage: queue_full_sweep.sh <ref> [label]}"
LABEL="${2:-}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
GOLDENS="${GOLDENS:-/home/justin/goldens/results}"

SHA=$(git rev-parse --short "$REF") || { echo "cannot resolve $REF" >&2; exit 2; }
[ "$SHA" = "$REF" ] || echo "resolved $REF to $SHA" >&2

# A LABEL MUST DESCRIBE THE CONTENT, NOT THE INTENT. An aspirational label is
# guaranteed to become false: a corpus sweep takes hours, the branch moves
# under it, and a column called `tip` is a column that WAS the tip. This has
# now happened twice -- the `after` column was collected 28 hw/ commits behind
# what it was named for, and a column queued as `tip` was 27 behind before its
# last suite had even run. Both were flagged stale by collect_sweep.sh, which
# is correct and also too late: the name is what the next reader sees first.
#
# So the label DEFAULTS to the sha, and the words that describe a moving target
# are refused. `before`/`after` stay allowed -- they name a position in a
# sequence, which does not rot.
case "$LABEL" in
    tip|latest|current|now|head|HEAD|today|new|newest)
        cat >&2 <<MSG
refusing: "$LABEL" describes a moving target, and a corpus sweep takes hours.

A column labelled "$LABEL" is a column that WAS $LABEL. It has happened twice:
the 'after' column was collected 28 hw/ commits behind, and a 'tip' column was
27 behind before its last suite ran.

Use the sha (the default), or a name that will still be true tomorrow --
'before'/'after' name a position in a sequence and do not rot.
MSG
        exit 2 ;;
    "") LABEL="$SHA"
        echo "no label given; using the sha: $LABEL" >&2 ;;
esac

BEHIND=$(git rev-list --count "$SHA..HEAD" -- hw/ 2>/dev/null || echo '?')
if [ "$BEHIND" != "0" ]; then
    echo "NOTE: $SHA is $BEHIND hw/ commit(s) behind HEAD. The column will be" >&2
    echo "      labelled stale by collect_sweep.sh, correctly." >&2
fi

mkdir -p "$D/queue"
n=0
for dir in "$GOLDENS"/*/; do
    suite_fs=$(basename "$dir")
    [ -d "$dir" ] || continue
    suite=${suite_fs//_/ }
    n=$((n+1))
    id=$(printf 'z-%s-%03d-%s' "$LABEL" "$n" "$suite_fs")
    skip=$(skip_tests_for "$suite_fs")
    [ -z "$skip" ] || echo "  $suite_fs: skipping $skip" >&2
    python3 - "$D/queue/$id.req" "$id" "$suite" "$SHA" "$LABEL" "$skip" <<'PY'
import datetime, json, sys
p, i, suite, ref, label, skip = sys.argv[1:7]
json.dump({"id": i, "requester": "full-sweep", "arm": label,
           "purpose": "full-corpus sweep of %s at %s" % (suite, ref),
           "suites": [suite], "tests": [],
           "skip_tests": [t for t in skip.split(",") if t.strip()],
           "ref": ref, "runs": 1,
           "title": "", "seconds": 0, "pull_glob": "",
           "expect": "", "expect_sha": "", "no_expect":
           "full-corpus survey at one pinned binary, not an A/B arm",
           "queued_utc": datetime.datetime.now(datetime.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(p, "w"), indent=2)
PY
done
echo "queued $n idle-priority suite requests at $SHA (label $LABEL)"
echo "collect with: docs/testing/collect_sweep.sh $LABEL"
