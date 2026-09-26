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
#                                       (SINCE only matters if no nightly-* tag
#                                       is an ancestor of HEAD; see RANGE below)
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
#   unreachable refuse too (exit 8). We cannot know the tip, so we cannot
#               claim to be it. This used to publish with a caveat at the top
#               of the release body; the owner's standing order (2026-09-25,
#               AGENTS.md PR #239) is that the public body carries no process
#               commentary, so a build that needs one is not published. It
#               costs little: origin and `gh release` are the same host, so a
#               night that cannot fetch almost never could have published.
#   at the tip  the normal path, and the only one that publishes.
#
# Every refusal, and every WARNING, goes to say() -- the day's $LOG and the
# unit's journal -- and never into the release body.
#
# `ahead` keeps the old unpushed-HEAD label rather than becoming a fourth
# refusal: it is the same question (can anyone else rebuild this?) asked
# against the trunk rather than against whatever branch happened to be checked
# out. A tree that is purely ahead contains every trunk commit, so nothing a
# reader is owed is MISSING from it -- which is the thing that went wrong --
# and the release says "unpushed" in its first line. A tree that is ahead AND
# behind is diverged, and the `elif` order is deliberate: behind is tested
# first, so divergence refuses.
TRUNK_OK=0; TRUNK=""; BEHIND=0; AHEAD=0
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
    say "REFUSING: cannot reach origin/$TIP, so $SHA cannot be confirmed as the trunk (last fetch: $LAST_FETCH)"
    PROV="built from \`$SHA\` on \`$BRANCH\`"
elif [ "$BEHIND" -gt 0 ]; then
    say "REFUSING: HEAD $SHA is $BEHIND commit(s) behind origin/$TIP ($TRUNK); the nightly publishes the trunk or nothing"
    PROV="built from \`$SHA\` on \`$BRANCH\`"
elif [ "$AHEAD" -gt 0 ]; then
    say "WARNING: $AHEAD commit(s) not on origin/$TIP; the release will say so"
    PROV="built from **unpushed** \`$SHA\` on \`$BRANCH\` ($AHEAD commits ahead of origin/$TIP)"
else
    PROV="built from \`$SHA\` on \`$BRANCH\` (the tip of \`origin/$TIP\`)"
fi

# Refuse BEFORE ./gradlew, not after: ten minutes of build time spent on a
# tree we already know is stale buys nothing, and the exit code is the signal.
# Not in `notes` mode -- that mode publishes nothing, and its job is to show
# what the body would say; the refusal is in its stderr.
if [ "$MODE" = build ] && [ "$BEHIND" -gt 0 ]; then
    say "nothing published; the nightly must run from a tree at origin/$TIP (jobs/run-nightly.sh keeps one)"
    exit 5
fi
if [ "$MODE" = build ] && [ "$TRUNK_OK" = 0 ]; then
    say "nothing published; origin/$TIP was unreachable, so this tree cannot be shown to be the trunk"
    exit 8
fi

# A modified tracked file means the binary is not exactly $SHA. That used to be
# a line at the top of the release body; now it refuses, since the body names
# $SHA and would otherwise be false. run-nightly.sh's worktree is only ever
# checked out, never edited, so on the intended path this does not fire.
DIRTY=$(git status --porcelain | grep -v '^??' | wc -l)
if [ "$DIRTY" -gt 0 ]; then
    if [ "$MODE" = build ]; then
        say "REFUSING: $DIRTY tracked file(s) modified; the binary would not be $SHA. Nothing published"
        exit 7
    fi
    say "WARNING: $DIRTY tracked file(s) modified; a build here would refuse (exit 7)"
fi

# ------------------------------------------------------------ the day's work
#
# ONE LINE PER MERGED CHANGE, in a player's words, grouped by what it does for
# a player. The release body is the only artefact most people read, and it is
# public: it carries no process commentary (owner, 2026-09-25, AGENTS.md
# PR #239).
#
# WHY. Until 2026-09-26 this listed COMMITS: every lane commit that touched an
# emulator directory, then capped "Harness and tooling" and "Docs and the
# rest" sections, then a tally. nightly-2026-09-26 listed 54 emulator commits
# and counted 563 in all. A lane's commits are its working notes -- a
# diagnostic trace marked not for merge, the scaffolding for a comparison, a
# change and its own revert, "fix the two MEDIUMs from pass 1" -- so the list
# told a player nothing and showed everyone our internals. (Before that it was
# `git log --since=... | head -40`, which on 2026-09-19 named no emulator work
# at all; docs/lanes/nightlynotes has both histories.)
#
# So the unit is the MERGE, not the commit: the fold commits on the trunk's
# first-parent line, each judged by its NET diff against the trunk it landed
# on. A PR whose commits add a change and then revert it has no net diff
# there, and a fold that fold.sh later reverts in the same window cancels
# with its revert, so neither reaches the notes.
#
# Each change's line comes from, in order:
#   1. $MAP, one `PR<TAB>category<TAB>line` per row -- the curated lines for
#      PRs merged before (2) existed, and the way to correct one afterwards;
#   2. a `Release note: <line>` or `Release note (<category>): <line>` line in
#      the PR's own body -- the author says what it does for a player;
#   3. the PR title, stripped of its lane prefix and of anything after " -- ",
#      with a category guessed from its words.
# A line of `none` in (1) or (2) leaves the change out: instrumentation that is
# off by default changes nothing a player can see. Categories: performance,
# stability, rendering, other.
#
# A line that still reads as process after all that -- it names an arm, a
# lane, an audit, a probe -- is not printed. It is logged, and the change is
# named by number only at the end of "Other". Harness, docs and every other
# non-emulator change are one sentence, not a list.
#
# Emulator code is the directories the brief named: hw/ target/ accel/
# android/ tcg/ ui/, plus audio/, which every other gate already counts.
EMU_RE='^(hw|target|accel|android|tcg|ui|audio)/'
MAP="${NIGHTLY_NOTES_MAP:-$TREE/docs/lanes/nightlynotes/release_notes.tsv}"
INTERNAL_RE='\b(arms?|a_ref|b_ref|lanes?|audit(s|ed)?|remediat[a-z]*|diagnos[a-z]*|probes?|scaffold[a-z]*|instrument[a-z]*|not for merge|hunks?|triage|analysis|investigat[a-z]*|priced|goldens?|selftest)\b'

# Deliberately bare `date`, i.e. host-local, and NOT one of localtime.sh's
# helpers: this window has to line up with the timer that started the run, and
# OnCalendar=00:30:00 with no Timezone= means the timer fires at 00:30 LOCAL.
# Making this UTC would shift the window seven hours off the boundary it is
# meant to name. -Iseconds carries the offset ("2026-09-18T00:30:00-07:00"),
# so the line say() prints below is unambiguous without the display helper.
# The positional override is for `notes [SINCE]`; it goes to `git log --since=`
# unchanged, so a fixture can name its own window.
SINCE="${2:-$(date -d 'yesterday 00:30' -Iseconds 2>/dev/null || date -v-1d -Iseconds)}"

# THE RANGE IS BY ANCESTRY, and $SINCE is only the fallback. The window above
# is over COMMIT dates, and a lane's commits keep the dates they were written
# and reach master in a fold days later -- so nightly-2026-09-25 listed 4 of
# the 14 commits it added over nightly-2026-09-24 and said "0 emulator" while
# 637b4f1d2a (nv2a/gl, written 09-19, folded 09-24 23:41) was in the build.
# "What is new in this build" is `<previous nightly>..HEAD`, whatever dates
# the commits carry.
#
# The previous nightly is the newest nightly-* tag that is an ancestor of
# HEAD. Newest by NAME, not by creatordate: the tags are lightweight (gh
# release create makes them), so their "creator date" is the tagged commit's
# date -- nightly-2026-09-24 reads 2026-09-21 -- and the name is the day it
# was published. Today's own tag is skipped, so a same-day rerun still
# reports against yesterday. The tags are made on origin by `gh release`, so
# fetch them first; a failure there only means the fallback below, which logs.
git fetch -q origin 'refs/tags/nightly-*:refs/tags/nightly-*' 2>/dev/null || true
BASE_TAG=""
while IFS= read -r t; do
    [ "$t" = "nightly-$DAY" ] && continue
    git merge-base --is-ancestor "$t" HEAD 2>/dev/null && { BASE_TAG=$t; break; }
done < <(git tag -l 'nightly-*' --sort=-refname 2>/dev/null)
if [ -n "$BASE_TAG" ]; then
    RANGE=("$BASE_TAG..HEAD")
    WINDOW="since $BASE_TAG ($(git rev-parse --short "$BASE_TAG^{commit}"))"
    NONE_LINE="No commits since \`$BASE_TAG\`."
else
    RANGE=(--since="$SINCE" HEAD)
    WINDOW="dated since $SINCE"
    NONE_LINE="No commits in the last day."
    # Logged, not printed in the body: the release body carries no process
    # commentary (owner, 2026-09-25). The log is where a short list is chased.
    say "WARNING: no nightly-* tag is an ancestor of HEAD; falling back to commits dated since $SINCE"
fi

# One `git log` over the first-parent line: \x01 marks a commit's subject,
# every other non-blank line is a path its merge (or it) changed against the
# trunk commit before it. --diff-merges=first-parent is what makes a fold's
# paths its net change rather than nothing.
declare -A REVERTED=() REVERT_EMU=()
CH_PR=(); CH_TITLE=()
N_INTERNAL=0
cur_sub=""; cur_emu=0; have=0
flush_change() {
    [ "$have" = 1 ] || return 0
    local pr="" title=$cur_sub
    case "$cur_sub" in
        "fold: revert #"*|'Revert "fold: PR #'*)
            pr=${cur_sub#*#}; pr=${pr%%[!0-9]*}
            if [ -n "$pr" ]; then
                REVERTED[$pr]=1
                [ "$cur_emu" = 1 ] && REVERT_EMU[$pr]=1
            fi
            return 0 ;;
        "fold: PR #"*)
            pr=${cur_sub#fold: PR #}; pr=${pr%%[!0-9]*}
            case "$cur_sub" in *" -- "*) title=${cur_sub#* -- } ;; esac ;;
    esac
    if [ "$cur_emu" = 1 ]; then
        CH_PR+=("$pr"); CH_TITLE+=("$title")
    else
        N_INTERNAL=$((N_INTERNAL+1))
    fi
    return 0
}
#
# BOTH logs name HEAD explicitly, and HEAD is the ref the gate above just
# checked and the ref ./gradlew will build. That is the whole point: on
# 2026-09-20 the notes said "No commits in the last day" about a 34-hour-old
# checkout while 89 commits landed on the trunk. The range and the binary must
# be answers about the same ref, so neither may be implicit.
while IFS= read -r line; do
    case "$line" in
        $'\x01'*) flush_change; cur_sub=${line#$'\x01'}; cur_emu=0; have=1 ;;
        '')       ;;
        *)        [[ $line =~ $EMU_RE ]] && cur_emu=1 ;;
    esac
done < <(git log --first-parent --diff-merges=first-parent --format=$'\x01%s' --name-only "${RANGE[@]}" 2>/dev/null)
flush_change
TOTAL=$(git log --first-parent --oneline "${RANGE[@]}" 2>/dev/null | wc -l)

map_line() {   # <pr> -> "category<TAB>line" from $MAP
    [ -n "$1" ] && [ -f "$MAP" ] || return 1
    awk -F'\t' -v pr="$1" '$1 == pr { print $2 "\t" $3; found = 1; exit }
                           END { exit !found }' "$MAP"
}
body_line() {   # <pr> -> "category<TAB>line" from the PR body's `Release note:` line
    local body
    if [ -n "${NIGHTLY_PR_BODIES:-}" ]; then
        body=$(cat "$NIGHTLY_PR_BODIES/$1.md" 2>/dev/null)
    else
        body=$(gh api "repos/$REPO/pulls/$1" --jq .body 2>/dev/null)
    fi
    printf '%s\n' "$body" | tr -d '\r' | sed -nE \
        's/^[[:space:]]*[Rr]elease[ -][Nn]otes?( \(([A-Za-z ]+)\))?:[[:space:]]*(.*[^[:space:]])[[:space:]]*$/\2\t\3/p' \
        | head -1
}
norm_cat() {   # <word> -> performance|stability|rendering|other|none, or empty
    case "${1,,}" in
        '')                   ;;
        none|skip)            echo none ;;
        perf*|speed*)         echo performance ;;
        stab*|crash*)         echo stability ;;
        render*|graphic*)     echo rendering ;;
        *)                    echo other ;;
    esac
}
guess_cat() {   # <line> -> a category from its words
    if grep -qiE '\b(fps|slow(s|er|down)?|stutter[a-z]*|faster|speed[a-z]*|frame ?rate|latency|performance)\b' <<<"$1"; then
        echo performance
    elif grep -qiE '\b(crash[a-z]*|hangs?|freez[a-z]*|abort[a-z]*|deadlock[a-z]*|segfault[a-z]*|leak[a-z]*)\b' <<<"$1"; then
        echo stability
    elif grep -qiE 'nv2a|pgraph|render|textur|surface|shader|depth|blend|colou?r|fog|vertex|pixel|clip|draw|vsh|psh|glsl|\bvk\b|\bgl\b' <<<"$1"; then
        echo rendering
    else
        echo other
    fi
}
# The "(analysis)" and "(investigating)" a title ends with are kept: they are
# how an inert study PR says so, and $INTERNAL_RE then lists it by number.
clean_title() {   # <PR title> -> the title without its lane prefix or its tail
    sed -E 's#^(docs/)?lanes?[./][A-Za-z0-9_-]+: *##
            s# -- .*$##' <<<"$1"
}

L_PERF=(); L_STAB=(); L_REND=(); L_OTHER=(); BY_NUMBER=()
N_EMU=${#CH_PR[@]}; N_DROPPED=0
for i in "${!CH_PR[@]}"; do
    pr=${CH_PR[$i]}
    if [ -n "$pr" ] && [ -n "${REVERTED[$pr]:-}" ]; then
        say "notes: #$pr was folded and reverted in this window; neither is listed"
        unset "REVERTED[$pr]"; N_DROPPED=$((N_DROPPED+1)); continue
    fi
    r=""
    r=$(map_line "$pr") || { [ -n "$pr" ] && r=$(body_line "$pr"); }
    cat=$(norm_cat "${r%%$'\t'*}"); text=""
    [ -n "$r" ] && text=${r#*$'\t'}
    [ "${text,,}" = none ] && cat=none
    if [ "$cat" = none ]; then
        N_DROPPED=$((N_DROPPED+1)); N_INTERNAL=$((N_INTERNAL+1)); continue
    fi
    [ -n "$text" ] || text=$(clean_title "${CH_TITLE[$i]}")
    [ -n "$cat" ] || cat=$(guess_cat "$text")
    [ -n "$pr" ] && ! [[ $text =~ \#[0-9] ]] && text="$text (#$pr)"
    if grep -qiE "$INTERNAL_RE" <<<"$text"; then
        who="a direct commit"; [ -n "$pr" ] && who="#$pr"
        say "notes: the line for $who reads as process, so it is listed by number only: $text"
        if [ -n "$pr" ]; then BY_NUMBER+=("#$pr"); else N_DROPPED=$((N_DROPPED+1)); fi
        continue
    fi
    case "$cat" in
        performance) L_PERF+=("- $text") ;;
        stability)   L_STAB+=("- $text") ;;
        rendering)   L_REND+=("- $text") ;;
        *)           L_OTHER+=("- $text") ;;
    esac
done
# A revert whose fold is not in this window withdraws something an earlier
# nightly shipped, and a player may notice that.
for pr in "${!REVERTED[@]}"; do
    [ -n "${REVERT_EMU[$pr]:-}" ] && L_OTHER+=("- An earlier change (#$pr) was withdrawn.")
done
if [ "${#BY_NUMBER[@]}" -gt 0 ]; then
    L_OTHER+=("- Further emulator changes: $(printf '%s, ' "${BY_NUMBER[@]}" | sed 's/, $//').")
fi
N_LISTED=$(( ${#L_PERF[@]} + ${#L_STAB[@]} + ${#L_REND[@]} + ${#L_OTHER[@]} ))
say "$TOTAL commit(s) $WINDOW: $N_EMU emulator change(s), $N_LISTED line(s), $N_DROPPED left out, $N_INTERNAL internal"

BODY="$OUT/$DAY.notes.md"
section() {   # <heading> <line...>
    local heading=$1; shift
    [ "$#" -gt 0 ] || return 0
    echo "### $heading"; echo
    printf '%s\n' "$@"
    echo
}
{
    echo "Automated nightly. $PROV."
    echo
    if [ "$TOTAL" -eq 0 ]; then
        # A tree that is not the trunk never reaches publish (exit 5 or 8
        # above), so this sentence is only ever published about the trunk.
        echo "$NONE_LINE"
        echo
    else
        section "Performance"     ${L_PERF[@]+"${L_PERF[@]}"}
        section "Stability"       ${L_STAB[@]+"${L_STAB[@]}"}
        section "Rendering fixes" ${L_REND[@]+"${L_REND[@]}"}
        section "Other"           ${L_OTHER[@]+"${L_OTHER[@]}"}
        if [ "$N_LISTED" -eq 0 ]; then
            echo "No player-facing changes in this build."
            echo
        fi
        if [ "$N_INTERNAL" -gt 0 ]; then
            echo "Plus internal test-harness work."
            echo
        fi
    fi
    echo "Installs alongside an official hakuX build and upgrades a previous fork build in place."
    echo "Launching from ES-DE needs the two files in \`docs/es-de/\`."
    echo
    echo "_Notes updated $(date -u '+%F %H:%M') UTC._"
} > "$BODY"

# The post-condition: a window with emulator changes that were not all left
# out on purpose must produce notes that list something. Asserted against the
# written file, so an edit to the block above trips it too. It warns rather
# than exits: a nightly with imperfect notes still beats no nightly, and the
# warning lands in the log the owner reads.
if [ "$N_EMU" -gt "$N_DROPPED" ] && ! grep -q '^- ' "$BODY"; then
    say "WARNING: $((N_EMU - N_DROPPED)) emulator change(s) in the window and the notes list none"
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
