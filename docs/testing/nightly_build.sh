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
# It builds THE TRUNK. Not the tree it happens to be started in: it fetches
# origin/master every run and refuses to publish anything that is not that
# tip. See "is this the trunk?" below for what went wrong without that.
# jobs/run-nightly.sh is what the systemd unit runs; it keeps the private
# worktree this builds in.
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
# The tree to build. DEFAULTS TO THIS SCRIPT'S OWN REPOSITORY, not to a fixed
# path: under jobs/run-nightly.sh this file is the copy inside the nightly's
# private worktree, so the default resolves to the fetched trunk. The old
# default was a hardcoded /home/justin/hakuX -- the owner's checkout, whatever
# branch they last left it on -- and on 2026-09-20 and -21 that published a
# 09-19 sha twice under a current date. The trunk gate below is what actually
# makes that impossible; this default only removes the easiest way to trip it.
TREE="${NIGHTLY_TREE:-$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/../.." && pwd)}"
TIP="${NIGHTLY_TIP:-master}"
OUT="${NIGHTLY_OUT:-/home/justin/hakux-work/nightly}"
export JAVA_HOME="${JAVA_HOME:-/home/justin/toolchains/jdk21}"
export PATH="/home/justin/Android/Sdk/cmake/3.30.3/bin:$PATH"

MODE="${1:-build}"
case "$MODE" in
    build|notes) ;;
    *) echo "usage: ${0##*/} [build|notes [SINCE]]" >&2; exit 64 ;;
esac

# The display zone, and the reason this file needs it at all: DAY and say()
# were ALREADY local -- bare `date`, following the host, which is
# America/Los_Angeles -- they just never said which zone that was, so a
# reader who knew the rest of the harness printed UTC would read "00:31:12"
# as UTC and be seven hours out. hakux-nightly.timer's OnCalendar=00:30:00
# carries no Timezone= and so follows the host too; that is the same 00:30
# this file's header names, and it stays that way.
#
# Sourced by absolute path, so `notes` mode works from any cwd -- and BEFORE
# the mktemp below, because local_day() names the file that mktemp's OUT holds.
. "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/jobs/localtime.sh"

# notes mode writes nothing into the real nightly directory and never touches
# the day's log: a test run must not be able to overwrite tonight's record.
if [ "$MODE" = notes ]; then
    OUT=$(mktemp -d "${TMPDIR:-/tmp}/nightly-notes.XXXXXX") || OUT="${TMPDIR:-/tmp}/nightly-notes.$$"
fi

mkdir -p "$OUT"
DAY=$(local_day)
LOG="$OUT/$DAY.log"
# In notes mode the body goes to stdout, so progress goes to stderr instead --
# otherwise say() would corrupt the very thing being generated. Both arms
# print say_time_s, which carries the zone: a bare "00:31:12" on a page where
# everything else ended in Z was being read seven hours out.
say() {
    if [ "$MODE" = notes ]; then echo "$(say_time_s) $*" >&2
    else echo "$(say_time_s) $*" | tee -a "$LOG"; fi
}

cd "$TREE" || { echo "no tree at $TREE"; exit 1; }
BRANCH=$(git rev-parse --abbrev-ref HEAD)
# run-nightly.sh parks its worktree detached on the fetched tip, where
# --abbrev-ref prints the literal "HEAD". "built from `abc1234` on `HEAD`" is
# not a sentence; the branch it is detached AT is the one to name.
[ "$BRANCH" = HEAD ] && BRANCH="$TIP"
SHA=$(git rev-parse --short HEAD)
say "nightly $DAY  branch=$BRANCH  head=$SHA"

# ------------------------------------------------------- is this the trunk?
#
# THE DEFECT THIS EXISTS FOR. nightly-2026-09-20 and nightly-2026-09-21 were
# both built from 20e4708d50, an evening-of-09-19 commit, because the script
# asked the owner's checkout what it was and that checkout had not been pulled
# for 34 hours. origin/master was 152 commits ahead. Both releases shipped an
# APK under a current date and said "No commits in the last day".
#
# So: ASK ORIGIN, every run, and treat the three answers separately.
#
#   behind      refuse. A release whose sha is not the trunk's tip is worse
#               than no release, because it is indistinguishable from a good
#               one at every place a person looks -- the tag, the date, the
#               APK. A missing nightly at least reads as a missing nightly,
#               and this exits non-zero so systemd records it as a failure.
#   unreachable label. We cannot know the tip, so we cannot claim to be it;
#               the notes say the fetch failed and when this host last
#               succeeded. Silently falling back to the local sha is today's
#               failure with a different cause.
#   at the tip  the normal path, and the only one that publishes.
#
# `ahead` keeps the old unpushed-HEAD label: it is the same question (can
# anyone else rebuild this?) asked against the trunk rather than against
# whatever branch happened to be checked out.
TRUNK_OK=0; TRUNK=""; BEHIND=0; AHEAD=0; STALE_NOTE=""
if git fetch -q origin "$TIP" 2>>"${LOG:-/dev/null}"; then
    TRUNK_OK=1
    TRUNK=$(git rev-parse --short FETCH_HEAD)
    BEHIND=$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null || echo 0)
    AHEAD=$(git rev-list --count FETCH_HEAD..HEAD 2>/dev/null || echo 0)
fi

if [ "$TRUNK_OK" = 0 ]; then
    # The mtime of FETCH_HEAD is when this host last heard from origin at all
    # -- not a commit date, which would be the trunk's age and not ours.
    FH=$(git rev-parse --git-path FETCH_HEAD 2>/dev/null)
    LAST_FETCH="never"
    [ -n "$FH" ] && [ -e "$FH" ] && LAST_FETCH=$(date -r "$FH" '+%F %H:%M %Z' 2>/dev/null || echo unknown)
    say "WARNING: cannot reach origin/$TIP; cannot confirm $SHA is the trunk (last fetch: $LAST_FETCH)"
    PROV="built from \`$SHA\` on \`$BRANCH\` -- **origin was unreachable**, so this is the last sha this host had, not necessarily the trunk's tip"
    STALE_NOTE="> Could not reach \`origin/$TIP\` at build time (this host last fetched at $LAST_FETCH). The sha below is what was on disk; it may be behind the trunk."
elif [ "$BEHIND" -gt 0 ]; then
    say "REFUSING: HEAD $SHA is $BEHIND commit(s) behind origin/$TIP ($TRUNK); the nightly publishes the trunk or nothing"
    PROV="built from \`$SHA\` on \`$BRANCH\` -- **$BEHIND commit(s) behind \`origin/$TIP\`** (\`$TRUNK\`)"
    STALE_NOTE="> This tree is $BEHIND commit(s) behind \`origin/$TIP\` (\`$TRUNK\`). A nightly must publish the trunk's tip, so this build is refused."
elif [ "$AHEAD" -gt 0 ]; then
    say "WARNING: $AHEAD commit(s) not on origin/$TIP; the release will say so"
    PROV="built from **unpushed** \`$SHA\` on \`$BRANCH\` ($AHEAD commits ahead of origin/$TIP)"
else
    PROV="built from \`$SHA\` on \`$BRANCH\` (the tip of \`origin/$TIP\`)"
fi

# Refuse BEFORE ./gradlew, not after: ten minutes of build time spent on a
# tree we already know is stale buys nothing, and the exit code is the signal.
# Not in `notes` mode -- that mode publishes nothing, and its job is to show
# what the body would say, banner included, which is what the mutant reads.
if [ "$MODE" = build ] && [ "$BEHIND" -gt 0 ]; then
    say "nothing published; the nightly must run from a tree at origin/$TIP (jobs/run-nightly.sh keeps one)"
    exit 5
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

# Deliberately bare `date`, i.e. host-local, and NOT one of localtime.sh's
# helpers: this window has to line up with the timer that started the run, and
# OnCalendar=00:30:00 with no Timezone= means the timer fires at 00:30 LOCAL.
# Making this UTC would shift the window seven hours off the boundary it is
# meant to name. -Iseconds carries the offset ("2026-09-18T00:30:00-07:00"),
# so the line say() prints below is unambiguous without the display helper.
# The positional override is for `notes [SINCE]`; it goes to `git log --since=`
# unchanged, so a fixture can name its own window.
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
#
# BOTH logs name HEAD explicitly, and HEAD is the ref the gate above just
# checked and the ref ./gradlew will build. That is the whole point: on
# 2026-09-20 the notes said "No commits in the last day" about a 34-hour-old
# checkout while 89 commits landed on the trunk. The range and the binary must
# be answers about the same ref, so neither may be implicit.
done < <(git log --no-merges --since="$SINCE" --format=$'\x01%s' --name-only HEAD 2>/dev/null)
flush_commit

N_WORK=$((N_EMU + N_HARN + N_OTHER))
TOTAL=$(git log --since="$SINCE" --oneline HEAD 2>/dev/null | wc -l)
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
    # The same shape of warning, one question earlier: the dirty line says the
    # binary is not exactly this commit, this one says this commit may not be
    # the one a reader is owed.
    [ -n "$STALE_NOTE" ] && echo "$STALE_NOTE"
    echo
    if [ "$N_WORK" -gt 0 ]; then
        section "Emulator"            "$N_EMU"   ${SUB_EMU[@]+"${SUB_EMU[@]}"}
        section "Harness and tooling" "$N_HARN"  ${SUB_HARN[@]+"${SUB_HARN[@]}"}
        section "Docs and the rest"   "$N_OTHER" ${SUB_OTHER[@]+"${SUB_OTHER[@]}"}
        echo "_${TALLY}_"
    elif [ "$TRUNK_OK" = 1 ]; then
        # Reachable and at the tip (behind already refused above), so this is
        # a statement about the trunk and is safe to make flatly.
        echo "No commits in the last day."
    else
        # Unreachable. An empty window here is a fact about a tree we could
        # not confirm, and the bare sentence is exactly the one the two
        # mislabelled releases printed. Say what it is a fact ABOUT.
        echo "No commits in the last day **on this checkout** -- origin was unreachable, so the trunk may have moved."
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

# The last gate, and the one that makes the guarantee hold across the build's
# own duration: $SHA, the sha in the tag title, the APK filename and the notes,
# was read before ./gradlew and the build takes minutes. If anything moved HEAD
# under us in that time -- a checkout in a shared tree, a launcher racing
# itself -- then every one of those labels now names a commit that is not what
# was compiled, which is the same lie as the stale nightly wearing a different
# hat. The trunk is allowed to move during a build (we publish its tip AT BUILD
# TIME); our own tree is not.
SHA_NOW=$(git rev-parse --short HEAD)
if [ "$SHA_NOW" != "$SHA" ]; then
    say "PUBLISH REFUSED: HEAD moved $SHA -> $SHA_NOW during the build; $NAME is labelled with a commit it was not built from"
    exit 6
fi

if gh release create "$TAG" "$OUT/$NAME" --repo "$REPO" --prerelease \
        --title "hakuX nightly $DAY ($SHA)" --notes-file "$BODY" >>"$LOG" 2>&1; then
    say "published $TAG"
else
    say "release create failed; retrying as an upload to an existing tag"
    gh release upload "$TAG" "$OUT/$NAME" --repo "$REPO" --clobber >>"$LOG" 2>&1 \
        && say "uploaded to existing $TAG" || { say "PUBLISH FAILED"; exit 4; }
fi
say "done"
