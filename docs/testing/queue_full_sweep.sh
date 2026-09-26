#!/usr/bin/env bash
#
#   queue_full_sweep.sh [options] <ref> [label]
#
#     --base-iso PATH           run the main sweep off PATH instead of the stock
#                               disc (the 6743b6a disc, #293). The label then
#                               defaults to <sha>-iso-<name>, never the bare
#                               sha a stock column carries.
#     --with-depth-2025         + Depth_buffer on the v2025-03-14 disc (#291)
#     --with-blend-interactive  + Blend_tests on the interactive disc (#292)
#     --with-rtloop             + RenderTextureLoop alone, --only-tests (#294)
#     --dry-run                 print what would be queued; write nothing
#
# Queue one idle-priority request per golden suite, so the whole corpus is
# scored against one binary.
#
# LEGS ARE SEPARATE COLUMNS. Each optional leg is queued under its own label,
# `<label>.<leg>`, so collect_sweep.sh gathers it into its own column and the
# scoreboard says which disc produced every number. Folding a leg into the main
# column would put two discs' captures of one suite in one cell -- scoreboard.py
# keeps the later of two rows for one test and counts the collision, which is a
# rescoring, not a composition. collect_sweep.sh matches `z-<label>-NNN-*`
# exactly, and a label may not contain '.', so `z-<label>.depth2025-001-*` can
# never leak into the column `<label>`.
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
# eleven issue comments. `--with-rtloop` scores the loop itself on a disc that
# holds nothing else, so it has nothing to poison (#294). Upstream fixed the
# contamination in 448d0e6; on a --base-iso disc at or after that the skip is
# no longer needed, but it is kept, because this script cannot tell which
# upstream commit a disc was built from.
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

# The discs the legs name. Overridable for a selftest; the defaults are the
# files the issues measured on (#291: the v2025-03-14 disc; #292: the one-byte
# patched interactive disc, 1,673 of 1,673 on 2026-09-13).
DEPTH2025_ISO="${DEPTH2025_ISO:-/home/justin/hakux-work/iso-2025-03-14.iso}"
INTERACTIVE_ISO="${INTERACTIVE_ISO:-/home/justin/nxdk_pgraph_tests_xiso_interactive.iso}"
RTLOOP_TEST="Texture render target::RenderTextureLoop"

BASE_ISO="" LEG_DEPTH=0 LEG_BLEND=0 LEG_RTLOOP=0 DRY=0 POS=()
while [ $# -gt 0 ]; do
    case "$1" in
        --base-iso) [ $# -ge 2 ] || { echo "--base-iso needs a path" >&2; exit 2; }
                    BASE_ISO="$2"; shift 2 ;;
        --with-depth-2025) LEG_DEPTH=1; shift ;;
        --with-blend-interactive) LEG_BLEND=1; shift ;;
        --with-rtloop) LEG_RTLOOP=1; shift ;;
        --dry-run) DRY=1; shift ;;
        -h|--help) sed -n '3,12p' "$0"; exit 0 ;;
        -*) echo "unknown option: $1" >&2; exit 2 ;;
        *) POS+=("$1"); shift ;;
    esac
done
REF="${POS[0]:-}"
[ -n "$REF" ] || { echo "usage: queue_full_sweep.sh [options] <ref> [label]" >&2; exit 2; }
LABEL="${POS[1]:-}"
D="${DISPATCH_DIR:-/home/justin/hakux-work/dispatch}"
GOLDENS="${GOLDENS:-/home/justin/goldens/results}"

# Peel to the commit: an annotated tag resolves to its TAG OBJECT otherwise,
# and every result row and "behind" count then names a sha that is not a
# commit (v0.4.0-j1 wrote df3978f7b9, the tag, into 100 requests on 09-25).
SHA=$(git rev-parse --short --verify "$REF^{commit}") || { echo "cannot resolve $REF" >&2; exit 2; }
[ "$SHA" = "$REF" ] || echo "resolved $REF to $SHA" >&2

# A named disc that is not there is refused NOW. The dispatcher would refuse
# it too, correctly -- once per request, as a hundred ERRORs.
need_iso() { [ -f "$1" ] || { echo "no such disc: $1" >&2; exit 2; }; }
[ -z "$BASE_ISO" ] || need_iso "$BASE_ISO"
[ "$LEG_DEPTH" = 0 ] || need_iso "$DEPTH2025_ISO"
[ "$LEG_BLEND" = 0 ] || need_iso "$INTERACTIVE_ISO"

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
    *.*) echo "refusing: '.' in a label is reserved for legs (<label>.<leg>)" >&2
         exit 2 ;;
    "") LABEL="$SHA"
        # A non-stock main disc must not produce a column that reads like a
        # stock one, so the default names the disc as well as the binary.
        if [ -n "$BASE_ISO" ]; then
            b=$(basename "$BASE_ISO" .iso)
            LABEL="$SHA-iso-$(printf '%s' "$b" | tr -c 'A-Za-z0-9_-' _)"
        fi
        echo "no label given; using: $LABEL" >&2 ;;
esac

BEHIND=$(git rev-list --count "$SHA..HEAD" -- hw/ 2>/dev/null || echo '?')
if [ "$BEHIND" != "0" ]; then
    echo "NOTE: $SHA is $BEHIND hw/ commit(s) behind HEAD. The column will be" >&2
    echo "      labelled stale by collect_sweep.sh, correctly." >&2
fi

[ "$DRY" = 1 ] || mkdir -p "$D/queue"

# queue_one ID SUITE LABEL SKIP ONLY BASE_ISO
queue_one() {
    if [ "$DRY" = 1 ]; then
        echo "  would queue $1 suite=[$2] skip=[$4] only=[$5] base_iso=[$6]"
        return 0
    fi
    python3 - "$D/queue/$1.req" "$1" "$2" "$SHA" "$3" "$4" "$5" "$6" <<'PY'
import datetime, json, sys
p, i, suite, ref, label, skip, only, base_iso = sys.argv[1:9]
json.dump({"id": i, "requester": "full-sweep", "arm": label,
           "purpose": "full-corpus sweep of %s at %s%s" % (
               suite, ref, " on %s" % base_iso if base_iso else ""),
           "suites": [suite], "tests": [],
           "skip_tests": [t for t in skip.split(",") if t.strip()],
           "only_tests": [t for t in only.split(",") if t.strip()],
           "base_iso": base_iso,
           "ref": ref, "runs": 1,
           "title": "", "seconds": 0, "pull_glob": "",
           "expect": "", "expect_sha": "", "no_expect":
           "full-corpus survey at one pinned binary, not an A/B arm",
           "queued_utc": datetime.datetime.now(datetime.timezone.utc)
                         .strftime("%Y-%m-%dT%H:%M:%SZ")},
          open(p, "w"), indent=2)
PY
}

n=0
for dir in "$GOLDENS"/*/; do
    suite_fs=$(basename "$dir")
    [ -d "$dir" ] || continue
    suite=${suite_fs//_/ }
    n=$((n+1))
    id=$(printf 'z-%s-%03d-%s' "$LABEL" "$n" "$suite_fs")
    skip=$(skip_tests_for "$suite_fs")
    [ -z "$skip" ] || echo "  $suite_fs: skipping $skip" >&2
    queue_one "$id" "$suite" "$LABEL" "$skip" "" "$BASE_ISO"
done
echo "queued $n idle-priority suite requests at $SHA (label $LABEL)"
echo "collect with: docs/testing/collect_sweep.sh $LABEL"

# The legs: one request each, numbered 001 so collect_sweep.sh's
# `z-<label>-NNN-*` pattern finds it under the leg's own label.
leg() {  # leg NAME SUITE_FS ONLY ISO
    local l="$LABEL.$1"
    queue_one "$(printf 'z-%s-001-%s' "$l" "$2")" "${2//_/ }" "$l" "" "$3" "$4"
    echo "queued leg $l: $2 on ${4:-the stock disc}${3:+, only $3}"
    echo "collect with: docs/testing/collect_sweep.sh $l"
}
# #291: the current disc emits 144 of Depth_buffer's 784 goldens; the
# v2025-03-14 disc emits all of them.
[ "$LEG_DEPTH" = 0 ] || leg depth2025 Depth_buffer "" "$DEPTH2025_ISO"
# #292: TestDetailed is interactive-only upstream -- 1,568 of Blend's goldens.
[ "$LEG_BLEND" = 0 ] || leg blend-interactive Blend_tests "" "$INTERACTIVE_ISO"
# #294: the one test skip_tests_for drops, alone on the stock disc.
[ "$LEG_RTLOOP" = 0 ] || leg rtloop Texture_render_target "$RTLOOP_TEST" ""
exit 0
