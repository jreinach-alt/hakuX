#!/usr/bin/env bash
#
# Nightly build and publish. 00:30 America/Los_Angeles.
#
# A build needs no device, so this never contends with the dispatcher's queue.
# It deliberately does NOT run tests: a nightly that grabbed the Nova at half
# past midnight would collide with an overnight sweep, and running belongs to
# the dispatcher.
#
# It reports either way. A silent failure is worse than no nightly at all,
# because a missing release looks like a day with no work.
#
# Two modes:
#   nightly_build.sh                    build, write the notes, publish
#   nightly_build.sh notes [SINCE]      write the notes to stdout and stop
#
# `notes` exists so the note-writing -- the part with all the judgement in it
# -- is testable without a device, a toolchain or an hour. It builds nothing
# and publishes nothing; selftest.d/86-nightly-notes.sh drives it over fixture
# histories. Both modes generate the body through the same code, so a green
# test is a statement about what the nightly will actually publish.
set -u

REPO="${NIGHTLY_REPO:-jreinach-alt/hakuX}"
TREE="${NIGHTLY_TREE:-/home/justin/hakuX}"
OUT="${NIGHTLY_OUT:-/home/justin/hakux-work/nightly}"
export JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}"
export PATH="/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"

MODE="${1:-build}"
case "$MODE" in
    build|notes) ;;
    *) echo "usage: ${0##*/} [build|notes [SINCE]]" >&2; exit 64 ;;
esac
# notes mode writes nothing into the real nightly directory and never touches
# the day's log: a test run must not be able to overwrite tonight's record.
if [ "$MODE" = notes ]; then
    OUT=$(mktemp -d "${TMPDIR:-/tmp}/nightly-notes.XXXXXX") || OUT="${TMPDIR:-/tmp}/nightly-notes.$$"
fi

mkdir -p "$OUT"
DAY=$(date +%Y-%m-%d)
LOG="$OUT/$DAY.log"
# In notes mode the body goes to stdout, so progress goes to stderr instead --
# otherwise say() would corrupt the very thing being generated.
say() {
    if [ "$MODE" = notes ]; then echo "$(date '+%H:%M:%S') $*" >&2
    else echo "$(date '+%H:%M:%S') $*" | tee -a "$LOG"; fi
}

cd "$TREE" || { echo "no tree at $TREE"; exit 1; }
BRANCH=$(git rev-parse --abbrev-ref HEAD)
SHA=$(git rev-parse --short HEAD)
say "nightly $DAY  branch=$BRANCH  head=$SHA"

# Reproducibility: say plainly whether this sha exists on the remote. A
# release built from an unpushed HEAD cannot be rebuilt by anyone else, so it
# is labelled rather than quietly published as if it could.
UNPUSHED=$(git log --oneline "origin/$BRANCH..HEAD" 2>/dev/null | wc -l)
if [ "$UNPUSHED" -gt 0 ]; then
    say "WARNING: $UNPUSHED commit(s) not on origin; the release will say so"
    PROV="built from **unpushed** \`$SHA\` on \`$BRANCH\` ($UNPUSHED commits ahead of origin)"
else
    PROV="built from \`$SHA\` on \`$BRANCH\`"
fi

DIRTY=$(git status --porcelain | grep -v '^??' | wc -l)
[ "$DIRTY" -gt 0 ] && say "WARNING: $DIRTY tracked file(s) modified; build is not the commit"

# ------------------------------------------------------------ the day's work
#
# Subjects only -- bodies are long here -- GROUPED BY AREA, not truncated by
# recency.
#
# WHY. This was `git log --since="$SINCE" --format='- %s' | head -40`. git log
# is reverse-chronological, so that is not a sample of the day: it is the most
# recent forty commits, whatever churned last. On 2026-09-18 a burst of
# harness folds in the hours before 00:30 took all forty slots, and the
# 2026-09-19 release notes named 0 emulator commits -- every one of them was
# in the "…and N more commits" tail. The owner read the notes and asked
# whether any emulator work had happened at all.
#
# (How many were in that window depends on when you ask, because a lane
# branch folds after 00:30 and joins the window retroactively: the nightly
# logged 239 commits, a reconstruction at 06:40 the same morning found 310.
# The time-invariant fact is the one above -- 0 of the 40 listed touched an
# emulator directory, on every reconstruction. docs/lanes/nightlynotes.)
#
# It was not a one-off. The harness folds on a 30-minute timer, so the busier
# a day is the more completely it erases the emulator work from the record,
# and the release notes are the only artefact most people read. ROADMAP.md is
# explicit that passing the tests is not the goal; notes that cannot show a
# target/i386 FIST rounding fix are reporting against the wrong thing.
#
# The areas are the ones every brief and gate already uses -- emulator is
# hw/ target/ accel/ ui/ audio/, harness is docs/testing/ and .github/, and
# the patterns in the loop below are the only definition of that. A commit
# touching both sides counts as emulator: that is the side a reader cares
# about.
EMU_CAP=60          # a high cap: this is the point of the project
HARN_CAP=8          # a handful, then a count
OTHER_CAP=8

SINCE="${2:-$(date -d 'yesterday 00:30' -Iseconds 2>/dev/null || date -v-1d -Iseconds)}"

# --no-merges. A `fold: PR #131 lane/notespath -- ...` subject describes the
# lane, not the change, and the commits it folds are listed anyway -- so a
# merge adds a line that says nothing and hides one that does. Merges are
# still counted, and the footer says how many were left out.
SUB_EMU=(); SUB_HARN=(); SUB_OTHER=()
N_EMU=0; N_HARN=0; N_OTHER=0
cur_subject=""; cur_area=""
flush_commit() {
    [ -n "$cur_area" ] || return 0
    case "$cur_area" in
        emu)  N_EMU=$((N_EMU+1))
              [ "${#SUB_EMU[@]}"   -lt "$EMU_CAP" ]   && SUB_EMU+=("- $cur_subject") ;;
        harn) N_HARN=$((N_HARN+1))
              [ "${#SUB_HARN[@]}"  -lt "$HARN_CAP" ]  && SUB_HARN+=("- $cur_subject") ;;
        *)    N_OTHER=$((N_OTHER+1))
              [ "${#SUB_OTHER[@]}" -lt "$OTHER_CAP" ] && SUB_OTHER+=("- $cur_subject") ;;
    esac
    return 0
}
# One `git log` for the whole window: \x01 marks a subject, every other
# non-blank line is a path of the commit above it.
while IFS= read -r line; do
    case "$line" in
        $'\x01'*) flush_commit; cur_subject="${line#$'\x01'}"; cur_area=other ;;
        '')       ;;
        hw/*|target/*|accel/*|ui/*|audio/*)   cur_area=emu ;;
        docs/testing/*|.github/*)  [ "$cur_area" = emu ] || cur_area=harn ;;
    esac
done < <(git log --no-merges --since="$SINCE" --format=$'\x01%s' --name-only 2>/dev/null)
flush_commit

N_WORK=$((N_EMU + N_HARN + N_OTHER))
TOTAL=$(git log --since="$SINCE" --oneline 2>/dev/null | wc -l)
N_MERGE=$((TOTAL - N_WORK))
say "$TOTAL commit(s) since $SINCE: $N_EMU emulator, $N_HARN harness, $N_OTHER other, $N_MERGE merge(s)"

BODY="$OUT/$DAY.notes.md"
# A capped section says how many it left out, per section, so the counts in
# the notes always add up to the counts in the log line above.
section() {   # <heading> <total in this area> <subject...>
    local heading=$1 n=$2; shift 2
    [ "$n" -gt 0 ] || return 0
    echo "### $heading"; echo
    [ "$#" -gt 0 ] && printf '%s\n' "$@"
    [ "$n" -gt "$#" ] && { echo; echo "_…and $((n - $#)) more._"; }
    echo
    return 0
}
TALLY="$N_WORK commit(s) did the work: $N_EMU emulator, $N_HARN harness, $N_OTHER other."
[ "$N_MERGE" -gt 0 ] && TALLY="$TALLY $N_MERGE merge commit(s) are not listed."
{
    echo "Automated nightly. $PROV."
    echo
    [ "$DIRTY" -gt 0 ] && echo "> Built with $DIRTY modified tracked file(s): the binary is not exactly this commit."
    echo
    if [ "$N_WORK" -gt 0 ]; then
        section "Emulator"            "$N_EMU"   ${SUB_EMU[@]+"${SUB_EMU[@]}"}
        section "Harness and tooling" "$N_HARN"  ${SUB_HARN[@]+"${SUB_HARN[@]}"}
        section "Docs and the rest"   "$N_OTHER" ${SUB_OTHER[@]+"${SUB_OTHER[@]}"}
        echo "_${TALLY}_"
    else
        echo "No commits in the last day."
    fi
    echo
    echo "Installs alongside an official hakuX build and upgrades a previous fork build in place."
    echo "Launching from ES-DE needs the two files in \`docs/es-de/\`."
} > "$BODY"

# The post-condition this whole section exists for: a window that contains
# emulator work must produce notes that NAME some of it. Asserted against the
# written file rather than the variables, so an edit to the block above trips
# it too. It warns rather than exits: a nightly with imperfect notes still
# beats no nightly, and the warning lands in the log the owner reads.
if [ "$N_EMU" -gt 0 ]; then
    if [ "${#SUB_EMU[@]}" -eq 0 ] || ! grep -qxF -- "${SUB_EMU[0]}" "$BODY"; then
        say "WARNING: $N_EMU emulator commit(s) in the window and the notes name none"
    fi
fi

if [ "$MODE" = notes ]; then
    cat "$BODY"
    [ -n "$OUT" ] && rm -rf "$OUT"
    exit 0
fi

say "building release"
if ! (cd android && ./gradlew assembleRelease) >>"$LOG" 2>&1; then
    say "BUILD FAILED -- see $LOG"
    exit 2
fi

APK=$(find android/app/build/outputs/apk/release -name '*.apk' | head -1)
[ -n "$APK" ] || { say "no APK produced"; exit 3; }
VER=$(grep -oP 'versionName = "\K[^"]+' android/app/build.gradle.kts | head -1)
NAME="hakuX-${VER}-nightly-${DAY}-${SHA}.apk"
cp "$APK" "$OUT/$NAME"
say "built $NAME ($(du -h "$OUT/$NAME" | cut -f1)), sha256 $(sha256sum "$OUT/$NAME" | cut -c1-16)"

TAG="nightly-$DAY"
# $BODY was written before the build, from the same code `notes` mode runs.

if gh release create "$TAG" "$OUT/$NAME" --repo "$REPO" --prerelease \
        --title "hakuX nightly $DAY ($SHA)" --notes-file "$BODY" >>"$LOG" 2>&1; then
    say "published $TAG"
else
    say "release create failed; retrying as an upload to an existing tag"
    gh release upload "$TAG" "$OUT/$NAME" --repo "$REPO" --clobber >>"$LOG" 2>&1 \
        && say "uploaded to existing $TAG" || { say "PUBLISH FAILED"; exit 4; }
fi
say "done"
