# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# nightly_build.sh: the release notes must show the emulator work.
#
# Builds its own git fixtures under $T/nightlynotes. No shared state, and it
# builds nothing: `nightly_build.sh notes` stops before ./gradlew.
#
# WHAT THIS PINS. The 2026-09-19 nightly listed 40 commits and 0 of them
# touched hw/ target/ accel/ ui/ audio/, while 33 commits in the window did.
# The cause was `git log --since=... | head -40`: git log is
# reverse-chronological, so that is the most recent forty commits, not a
# sample of the day, and a burst of harness folds before 00:30 took every
# slot. The harness folds on a timer, so this recurs on any busy day -- and
# the busier the day, the more completely the emulator work is erased from
# the only artefact most people read.
#
# The fixture reproduces that shape exactly: three emulator commits, then a
# fold merge, then 45 harness commits on top. Under the replaced code the
# first forty subjects are all harness. The falsification at the bottom runs
# the replaced lines verbatim over this same fixture and requires that the
# central check FAILS against them -- a check that passes either way is not a
# check.
#
# There is deliberately no grep over nightly_build.sh's source here. The
# file's own comment quotes the line it replaced, so any grep for the old
# truncation matches the explanation of why it is gone. Behaviour only.

echo "== nightly_build.sh: the notes must show the emulator work"
NB="$T/nightlynotes"
NIGHTLY="$TESTING/nightly_build.sh"
rm -rf "$NB"; mkdir -p "$NB"

FIX="$NB/tree"
commit_touching() {   # <repo> <subject> <path...>
    local d=$1 subject=$2; shift 2
    local p
    for p in "$@"; do mkdir -p "$d/$(dirname "$p")"; echo "$subject" >> "$d/$p"; done
    git -C "$d" add -A
    git -C "$d" commit -q -m "$subject"
}
git -c init.defaultBranch=master init -q "$FIX"
git -C "$FIX" config user.email s@t; git -C "$FIX" config user.name s
commit_touching "$FIX" "base" README.md

# The three the notes exist to report, oldest first.
commit_touching "$FIX" "target/i386: FIST honours the rounding mode" target/i386/fpu_helper.c
commit_touching "$FIX" "nv2a/gl: the BLEND_AND blit must round, not truncate" hw/xbox/nv2a/pgraph/gl/blit.c
# One that touches BOTH sides: a reader cares about the emulator side.
commit_touching "$FIX" "accel/tcg: tier-1 promotion, and the gate that checks it" \
    accel/tcg/translate-all.c docs/testing/jobs/arms.sh

# Two that are neither.
commit_touching "$FIX" "docs: ROADMAP says what passing the tests is not" ROADMAP.md
commit_touching "$FIX" "audit: PR #115 pass 1 -- 1 HIGH, 5 MEDIUM" docs/lanes/x/NOTES.md

# A fold merge. Its subject names the lane, not the change, and every commit
# it folds is already listed -- so it must not take a line.
git -C "$FIX" checkout -q -b lane/fixture "HEAD~1"
commit_touching "$FIX" "ui/xemu: the pause overlay keeps its aspect" ui/xemu-settings.c
git -C "$FIX" checkout -q master
git -C "$FIX" merge -q --no-ff --no-edit -m "fold: PR #131 lane/fixture -- a lane, not a change" lane/fixture

# The burst that took all forty slots.
for i in $(seq 1 45); do
    commit_touching "$FIX" "harness: fold tick $i" "docs/testing/jobs/tick$i.sh"
done

run_notes() {   # <script> <outfile> ; SINCE is fixed so the wall clock cannot matter
    NIGHTLY_TREE="$FIX" NIGHTLY_OUT="$NB/must-not-exist" \
        bash "$1" notes 2000-01-01 >"$2" 2>"$2.err"
}
# The one assertion the whole lane is about, as a function, so the
# falsification below can put the replaced code through the identical test.
emu_section_names_the_work() {   # <notes file>
    grep -q '^### Emulator$' "$1" \
        && grep -qF 'target/i386: FIST honours the rounding mode' "$1"
}
# Negated as a function, not as `bash -c '! ...'`: a shell function is not
# exported into a child shell, so the negation there would succeed against
# anything at all -- including a missing file -- and prove nothing.
emu_section_misses_the_work() { ! emu_section_names_the_work "$1"; }

run_notes "$NIGHTLY" "$NB/new.md"; rc=$?
check "notes mode exits 0 and builds nothing" [ "$rc" = 0 ]
check "THE CHECK: the notes have an Emulator section naming the buried target/i386 fix" \
    emu_section_names_the_work "$NB/new.md"
check "  all four emulator commits are named, not just the newest" \
    bash -c '[ "$(sed -n "/^### Emulator$/,/^### Harness/p" "$1" | grep -c "^- ")" = 4 ]' _ "$NB/new.md"
check "  including the oldest, which the replaced code buried in the tail" \
    bash -c 'sed -n "/^### Emulator$/,/^### Harness/p" "$1" | grep -qF "target/i386: FIST"' _ "$NB/new.md"
check "  a commit touching both sides is counted as emulator, not harness" \
    bash -c 'sed -n "/^### Emulator$/,/^### Harness/p" "$1" | grep -qF "accel/tcg: tier-1 promotion"' _ "$NB/new.md"
check "the fold merge's subject takes no line (it names a lane, not a change)" \
    bash -c '! grep -qF "fold: PR #131" "$1"' _ "$NB/new.md"
check "  but the commit that fold brought in is listed on its own" \
    grep -qF 'ui/xemu: the pause overlay keeps its aspect' "$NB/new.md"

check "the harness section is capped" \
    bash -c '[ "$(sed -n "/^### Harness and tooling$/,/^### Docs/p" "$1" | grep -c "^- ")" = 8 ]' _ "$NB/new.md"
check "  and says how many it left out, in that section" \
    grep -qF '_…and 37 more._' "$NB/new.md"
check "the tally is honest: the three section counts add up, and the merge is named as not listed" \
    grep -qF '_52 commit(s) did the work: 4 emulator, 45 harness, 3 other. 1 merge commit(s) are not listed._' "$NB/new.md"
check "no warning is raised when the notes do name the emulator work" \
    bash -c '! grep -q "WARNING: .* emulator commit" "$1"' _ "$NB/new.md.err"
check "notes mode writes nothing into the nightly output directory" [ ! -e "$NB/must-not-exist" ]

# A window with no emulator work at all: no empty section, and no false alarm.
FIX2="$NB/harness-only"
git -c init.defaultBranch=master init -q "$FIX2"
git -C "$FIX2" config user.email s@t; git -C "$FIX2" config user.name s
commit_touching "$FIX2" "harness: the only thing that happened" docs/testing/jobs/only.sh
FIX_SAVE="$FIX"; FIX="$FIX2"
run_notes "$NIGHTLY" "$NB/none.md"; rc=$?
FIX="$FIX_SAVE"
check "a window with no emulator work still exits 0" [ "$rc" = 0 ]
check "  and prints no empty Emulator section" \
    bash -c '! grep -q "^### Emulator$" "$1"' _ "$NB/none.md"
check "  and raises no warning (there is nothing to have missed)" \
    bash -c '! grep -q "WARNING: .* emulator commit" "$1"' _ "$NB/none.md.err"

# ------------------------------------------------------------ falsification
# The replaced code, verbatim: nightly_build.sh lines 46-47 and 70-76 as they
# stood at 6ca12eb803. It cannot be invoked through the real script -- `notes`
# mode is what this lane adds -- so the two statements that did the work are
# run directly, over the same fixture. If the check above passes against this,
# it is testing nothing.
cat > "$NB/legacy-notes.sh" <<'LEGACY'
#!/usr/bin/env bash
set -u
cd "$NIGHTLY_TREE" || exit 1
SINCE="${2:-$(date -d 'yesterday 00:30' -Iseconds)}"
TOTAL=$(git log --since="$SINCE" --oneline | wc -l)
mapfile -t SUBJECTS < <(git log --since="$SINCE" --format='- %s' | head -40)
if [ "${#SUBJECTS[@]}" -gt 0 ]; then
    echo "### The day's work"; echo
    printf '%s\n' "${SUBJECTS[@]}"
    [ "$TOTAL" -gt "${#SUBJECTS[@]}" ] && { echo; echo "_…and $((TOTAL - ${#SUBJECTS[@]})) more commits._"; }
else
    echo "No commits in the last day."
fi
LEGACY
run_notes "$NB/legacy-notes.sh" "$NB/legacy.md"
check "the falsification ran and produced notes at all" \
    bash -c '[ "$(grep -c "^- " "$1")" = 40 ]' _ "$NB/legacy.md"
check "FALSIFIED: the replaced code lists 40 commits and names no emulator work" \
    emu_section_misses_the_work "$NB/legacy.md"
check "  and the check is not vacuous: it passes on the new notes" \
    emu_section_names_the_work "$NB/new.md"

# ------------------------------------------------ the range is by ancestry
# THE SECOND DEFECT. nightly-2026-09-25 built 82e460e863 over nightly-2026-09-24
# (3fe18366cd): 14 non-merge commits were new in the build, the notes listed
# the 4 COMMITTED on 09-24, and said "0 emulator". The window was
# `git log --since=<yesterday 00:30>`, a window over commit dates, and a lane
# commit keeps the date it was written: 637b4f1d2a (nv2a/gl) was written 09-19
# and folded at 09-24 23:41, and no date window starting 09-24 can see it.
#
# The fixture is that shape: yesterday's nightly tag, then a lane commit
# written three days ago that reaches the tip through a fold merge made now.
# Two decoy tags pin the choice of base, with the right one in the middle: an
# older ancestor, and a newer-named tag that is NOT an ancestor, forked from
# the root. Picking either as the base puts "before yesterday's nightly" in the
# range, and the log-line check names the tag that must have been chosen.
echo "== nightly_build.sh: the notes cover <previous nightly>..HEAD, not a date window"
FIX3="$NB/late-fold"
git -c init.defaultBranch=master init -q "$FIX3"
git -C "$FIX3" config user.email s@t; git -C "$FIX3" config user.name s
dated() {   # <when> <repo> <subject> <path...> -- commit_touching at a fixed date
    local when=$1; shift
    GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" commit_touching "$@"
}
# The day before the script's own DAY, which is local_day() (Pacific), not the
# runner's clock: from 00:00Z to 07:00Z a UTC runner's "yesterday" IS Pacific
# today, the script skips that tag as today's own, and the base falls through.
YDAY=$(. "$TESTING/jobs/localtime.sh"; date -d "$(local_day) -1 day" +%F)
dated "$(date -d '5 days ago 12:00' -Iseconds)" "$FIX3" "base" README.md
git -C "$FIX3" tag nightly-2000-01-01
dated "$(date -d '2 days ago 12:00' -Iseconds)" "$FIX3" "docs: before yesterday's nightly" docs/old.md
dated "$(date -d 'yesterday 00:10' -Iseconds)" "$FIX3" "harness: the tip yesterday's nightly built" docs/testing/jobs/y.sh
git -C "$FIX3" tag "nightly-$YDAY"
git -C "$FIX3" checkout -q -b lane/late "nightly-$YDAY"
dated "$(date -d '3 days ago 12:00' -Iseconds)" "$FIX3" \
    "nv2a/gl: clear to the surface's pad-bit constant" hw/xbox/nv2a/pgraph/gl/surface.c
git -C "$FIX3" checkout -q -b lane/elsewhere nightly-2000-01-01
commit_touching "$FIX3" "never merged" docs/elsewhere.md
git -C "$FIX3" tag nightly-9999-12-31
git -C "$FIX3" checkout -q master
git -C "$FIX3" merge -q --no-ff --no-edit -m "fold: PR #172 lane/late -- the late fold" lane/late
commit_touching "$FIX3" "harness: committed today" docs/testing/jobs/today.sh

# Both scripts get the SAME window argument: the old default, yesterday 00:30.
SINCE3=$(date -d 'yesterday 00:30' -Iseconds)
run_notes3() {   # <script> <outfile>
    NIGHTLY_TREE="$FIX3" NIGHTLY_OUT="$NB/must-not-exist" \
        bash "$1" notes "$SINCE3" >"$2" 2>"$2.err"
}
late_fold_is_listed_as_emulator() {   # <notes file>
    sed -n '/^### Emulator$/,/^### [HD]/p' "$1" \
        | grep -qxF -- "- nv2a/gl: clear to the surface's pad-bit constant"
}
late_fold_is_missing() { ! late_fold_is_listed_as_emulator "$1"; }

run_notes3 "$NIGHTLY" "$NB/late.md"; rc=$?
check "late-fold fixture: notes mode exits 0" [ "$rc" = 0 ]
check "THE CHECK: a commit written 3 days ago, folded today, is listed under Emulator" \
    late_fold_is_listed_as_emulator "$NB/late.md"
check "  the range reaches the tip: today's harness commit is listed" \
    grep -qxF -- '- harness: committed today' "$NB/late.md"
check "  the base is the NEWEST ancestor tag: nothing at or before it is listed" \
    bash -c '! grep -qF "before yesterday" "$1" && ! grep -qF "the tip yesterday" "$1"' _ "$NB/late.md"
check "  a newer-named tag that is not an ancestor is not the base" \
    bash -c '! grep -qF "never merged" "$1"' _ "$NB/late.md"
check "  the tally counts the same range: 2 did the work, 1 emulator, 1 harness, 1 merge" \
    grep -qF '_2 commit(s) did the work: 1 emulator, 1 harness, 0 other. 1 merge commit(s) are not listed._' "$NB/late.md"
check "  the log line names the tag it counted from" \
    grep -qF "3 commit(s) since nightly-$YDAY" "$NB/late.md.err"
check "  a tag-based range prints no fallback note" \
    bash -c '! grep -qF "tag is an ancestor of this build" "$1"' _ "$NB/late.md"
check "the tagless fixture falls back to the date window, and says so in the LOG" \
    grep -qF 'WARNING: no nightly-* tag is an ancestor of HEAD; falling back to commits dated since 2000-01-01' "$NB/new.md.err"

# ------------------------------------------- the body carries no caveats
# Owner's standing order, 2026-09-25 (AGENTS.md PR #239): the public release
# body carries no process commentary. The dirty-tree line, the not-the-trunk
# note and the date-window note were each a blockquote at the top of the body;
# all three now go to the log, and the builds that needed them refuse. The
# predicate is shared with 87-nightly-trunk.sh, which sources after this file,
# so every fixture scenario in both is put through the same test.
#
# -s first: a negative grep passes against a missing or empty file.
nightly_body_has_no_caveat() {   # <notes file>
    [ -s "$1" ] && grep -q '^Automated nightly\.' "$1" \
        && ! grep -qiE '^>|warning|refus|caveat|not exactly this commit|not confirmed|unreachable|could not reach|may be behind|commit\(s\) behind|on this tree|DATED since|fall(s|ing)? back' "$1"
}
nightly_body_has_a_caveat() { ! nightly_body_has_no_caveat "$1"; }
for f in new.md none.md late.md; do
    check "the published body carries no warning or caveat line: $f" \
        nightly_body_has_no_caveat "$NB/$f"
done
# Not vacuous: the top of the body as nightly_build.sh wrote it at 48f0618aff
# for a tree with no reachable origin -- which is every fixture in this file.
{ echo "Automated nightly. built from \`abc1234\` on \`master\` -- **origin was unreachable**, so this is the last sha this host had, not necessarily the trunk's tip."
  echo
  echo "> Could not reach \`origin/master\` at build time (this host last fetched at never). The sha below is what was on disk; it may be behind the trunk."
  echo; sed -n '/^### /,$p' "$NB/new.md"; } > "$NB/caveated.md"
check "  and the predicate catches the old top-of-body caveat" \
    nightly_body_has_a_caveat "$NB/caveated.md"

# Falsification: the replaced selection, verbatim from nightly_build.sh at
# 48f0618aff (the SINCE default and the `git log --since` it fed), with the
# same classification, over the same fixture and the same argument -- so the
# only difference between the two runs is the range.
cat > "$NB/legacy-range.sh" <<'LEGACY'
#!/usr/bin/env bash
set -u
cd "$NIGHTLY_TREE" || exit 1
SINCE="${2:-$(date -d 'yesterday 00:30' -Iseconds)}"
SUB_EMU=(); cur=""; area=""
flush() { [ "$area" = emu ] && SUB_EMU+=("- $cur"); return 0; }
while IFS= read -r line; do
    case "$line" in
        $'\x01'*) flush; cur="${line#$'\x01'}"; area=other ;;
        hw/*|target/*|accel/*|ui/*|audio/*) area=emu ;;
    esac
done < <(git log --no-merges --since="$SINCE" --format=$'\x01%s' --name-only HEAD 2>/dev/null)
flush
if [ "${#SUB_EMU[@]}" -gt 0 ]; then echo "### Emulator"; echo; printf '%s\n' "${SUB_EMU[@]}"; echo; fi
echo "### Harness and tooling"; echo
git log --no-merges --since="$SINCE" --format='- %s' HEAD
LEGACY
run_notes3 "$NB/legacy-range.sh" "$NB/late-legacy.md"
check "the falsification ran: the replaced range still sees today's commit" \
    grep -qxF -- '- harness: committed today' "$NB/late-legacy.md"
check "FALSIFIED: the replaced date window omits the late-folded emulator commit" \
    late_fold_is_missing "$NB/late-legacy.md"
check "  and the check is not vacuous: it passes on the new notes" \
    late_fold_is_listed_as_emulator "$NB/late.md"
