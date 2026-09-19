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
