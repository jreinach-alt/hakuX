# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# nightly_build.sh: the nightly publishes THE TRUNK, or it publishes nothing.
#
# Builds its own git fixtures under $T/nightlytrunk -- a bare origin, a clone
# at its tip, and a clone pinned five commits behind it. No shared state; the
# gradle step is a committed stub, so nothing here compiles anything.
#
# WHAT THIS PINS. nightly-2026-09-20 and nightly-2026-09-21 were both built
# from 20e4708d50, a commit from the evening of 2026-09-19, and both were
# published under a current date with an APK attached and the sentence "No
# commits in the last day". 89 commits landed on origin/master on 09-20 alone;
# the trunk was 152 ahead of the sha that shipped. The cause was that
# hakux-nightly.service ExecStarted out of /home/justin/hakuX -- whatever
# branch the owner last checked out there -- and nightly_build.sh asked that
# checkout what it was:
#
#     BRANCH=$(git rev-parse --abbrev-ref HEAD)
#     SHA=$(git rev-parse --short HEAD)
#
# It never fetched and never compared, so a checkout nobody had pulled for 34
# hours produced a confident, current-dated, wrong release. Twice.
#
# WHY THE FIXTURE IS PINNED BEHIND AND NOT CURRENT. A check that only ever
# runs against a tree that happens to be at the tip passes against the broken
# version for free -- that is the entire shape of this bug. So the central
# check runs on a tree that IS five commits behind, and the falsification at
# the bottom runs the replaced lines verbatim over that same tree and requires
# that the check FAILS against them.
#
# The behind tree's commits are backdated three days and the trunk's five new
# ones are dated now, so with a one-day window the behind tree's own log is
# empty. That is not decoration: it reproduces the exact sentence the two bad
# releases printed, which a same-day fixture cannot.

echo "== nightly_build.sh: the nightly builds the trunk, or refuses"
NT="$T/nightlytrunk"
NIGHTLY="$TESTING/nightly_build.sh"
rm -rf "$NT"; mkdir -p "$NT"

nt_commit() {   # <repo> <subject> <date> <path...>
    local d=$1 subject=$2 when=$3; shift 3
    local p
    for p in "$@"; do mkdir -p "$d/$(dirname "$p")"; echo "$subject" >> "$d/$p"; done
    git -C "$d" add -A
    GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" \
        git -C "$d" commit -q -m "$subject"
}

# Absolute, not "3 days ago": git's date parser on the CI runner rejects the
# relative form for GIT_AUTHOR_DATE and commits at the wall clock instead,
# which would collapse the whole point of the fixture -- and do it silently,
# which is why the "really five commits behind" check above exists.
OLD=$(date -d '3 days ago' -Iseconds)
# The trunk commits land two hours ago, not at the wall clock: they must be
# inside a "since yesterday 00:30" window AND outside the short window the
# empty-window control below uses. Both bounds relative, never a fixed date --
# a hardcoded one in a windowed fixture goes red at some hour of the day.
NOW=$(date -d '2 hours ago' -Iseconds)
SEED="$NT/seed"
git -c init.defaultBranch=master init -q "$SEED"
git -C "$SEED" config user.email s@t; git -C "$SEED" config user.name s

# The android/ stub. Committed, so every clone below has it, and it is what
# makes build mode runnable in a selftest at all: nightly_build.sh runs
# `(cd android && ./gradlew assembleRelease)` and then looks for the apk and
# greps the versionName out of the kts. Faking those three facts is what lets
# the publish path -- the one that labels the release with a sha -- be checked
# here instead of only at 00:30 on the owner's box.
mkdir -p "$SEED/android/app"
cat > "$SEED/android/gradlew" <<'GRADLEW'
#!/usr/bin/env bash
# selftest stub: produce the one artifact the real assembleRelease produces.
mkdir -p app/build/outputs/apk/release
echo "fake apk for $*" > app/build/outputs/apk/release/app-release.apk
GRADLEW
chmod +x "$SEED/android/gradlew"
echo 'versionName = "0.9-selftest"' > "$SEED/android/app/build.gradle.kts"
nt_commit "$SEED" "base: the android stub" "$OLD" README.md

# What the pinned checkout knows about: old, and nothing in a one-day window.
nt_commit "$SEED" "hw/xbox/nv2a: something from three days ago" "$OLD" hw/xbox/nv2a/old.c

ORIGIN="$NT/origin.git"
# -c init.defaultBranch=master: a bare repo made without it gets HEAD ->
# refs/heads/main, and every clone below then checks out nothing at all --
# which turns each negative grep in this file green against an empty file.
git -c init.defaultBranch=master init -q --bare "$ORIGIN"
git -C "$SEED" remote add origin "$ORIGIN"
git -C "$SEED" push -q origin master

BEHIND="$NT/behind"          # the owner's checkout, as it stood on 09-21
git clone -q "$ORIGIN" "$BEHIND"

# The trunk moves. Five commits, today, exactly as it did on 09-20.
for i in 1 2 3 4 5; do
    nt_commit "$SEED" "target/i386: trunk commit $i, landed today" "$NOW" "target/i386/new$i.c"
done
git -C "$SEED" push -q origin master

CURRENT="$NT/current"        # a tree at the tip, for the control
git clone -q "$ORIGIN" "$CURRENT"
TRUNK=$(git -C "$SEED" rev-parse --short HEAD)
STALE=$(git -C "$BEHIND" rev-parse --short HEAD)
DAY_L=$(TZ="${HAKUX_TZ:-America/Los_Angeles}" date '+%F' 2>/dev/null || date '+%F')
# The premise of every check below, asserted rather than assumed: a fixture
# that quietly failed to pin would make the whole fragment green for free --
# which is the same failure mode as the bug.
check "the fixture is really five commits behind the trunk" \
    bash -c 'git -C "$1" fetch -q origin master && [ "$(git -C "$1" rev-list --count HEAD..FETCH_HEAD)" = 5 ]' \
        _ "$BEHIND"
check "  and the behind tree's own one-day window is empty, as the owner's was" \
    bash -c '[ "$(git -C "$1" log --oneline --since="$(date -d "yesterday 00:30" -Iseconds)" | wc -l)" = 0 ]' \
        _ "$BEHIND"

nt_notes() {   # <script> <tree> <outfile> [since]
    NIGHTLY_TREE="$2" NIGHTLY_TIP=master NIGHTLY_OUT="$NT/must-not-exist" \
        bash "$1" notes "${4:-$(date -d 'yesterday 00:30' -Iseconds)}" >"$3" 2>"$3.err"
}

# --------------------------------------------------------------- the checks
#
# THE CHECK, as two functions so the falsification below can put the replaced
# code through the identical test. A release is honest when it either carries
# the trunk's sha, or says out loud that it is not the trunk -- and when the
# flat sentence "No commits in the last day." is reserved for a window that is
# actually the trunk's.
notes_do_not_claim_to_be_the_trunk() {   # <notes file>
    grep -qF "$TRUNK" "$1" || grep -qiE 'behind|unreachable' "$1"
}
# -s first. Every predicate here but this one is positive, and a negative grep
# passes against a missing or empty file -- so the one predicate that IS a
# negation has to assert the notes exist before it can say anything about them.
notes_avoid_the_bare_sentence() {        # <notes file>
    [ -s "$1" ] && ! grep -qxF 'No commits in the last day.' "$1"
}
# Negated as functions, not as `bash -c '! ...'`: a shell function is not
# exported into a child shell, so the negation there would succeed against
# anything at all, including a missing file, and prove nothing.
notes_claim_to_be_the_trunk_falsely() { ! notes_do_not_claim_to_be_the_trunk "$1"; }
notes_print_the_bare_sentence()       { ! notes_avoid_the_bare_sentence "$1"; }

nt_notes "$NIGHTLY" "$BEHIND" "$NT/behind.md"; rc=$?
check "notes mode on a tree behind the trunk still exits 0 and builds nothing" \
    bash -c '[ "$1" = 0 ] && [ ! -e "$2" ]' _ "$rc" "$NT/must-not-exist"
check "THE CHECK: the notes say this tree is not the trunk, and name the tip" \
    notes_do_not_claim_to_be_the_trunk "$NT/behind.md"
check "  the count is right: five commits behind" \
    grep -qF '5 commit(s) behind' "$NT/behind.md"
check "  and the empty window is not reported as the trunk's empty window" \
    notes_avoid_the_bare_sentence "$NT/behind.md"
check "  the reader is told what the qualification is about" \
    grep -qF 'No commits in the last day **on this tree**' "$NT/behind.md"

# Build mode, same tree: it must refuse, before ./gradlew and before gh.
GH_BEHIND="$NT/gh-behind.log"; : > "$GH_BEHIND"
NIGHTLY_TREE="$BEHIND" NIGHTLY_TIP=master NIGHTLY_OUT="$NT/out-behind" \
    SELFTEST_GH_LOG="$GH_BEHIND" bash "$NIGHTLY" >"$NT/behind-build.log" 2>&1
rc=$?
check "build mode on a tree behind the trunk refuses (exit 5)" [ "$rc" = 5 ]
check "  and says why, naming both shas" \
    bash -c 'grep -q "REFUSING" "$1" && grep -qF "$2" "$1" && grep -qF "$3" "$1"' \
        _ "$NT/behind-build.log" "$STALE" "$TRUNK"
check "  it refuses BEFORE ./gradlew: no apk was produced" \
    bash -c '[ -z "$(find "$1" -name "*.apk" 2>/dev/null)" ]' _ "$NT/out-behind"
check "  and nothing was published: gh was never asked to create a release" \
    bash -c '! grep -q "release create" "$1"' _ "$GH_BEHIND"

# ------------------------------------------------------------- the controls
#
# A refusal is easy to get by refusing always, so the tip must publish, and
# the flat sentence must still be reachable when it is true.
GH_CUR="$NT/gh-current.log"; : > "$GH_CUR"
NIGHTLY_TREE="$CURRENT" NIGHTLY_TIP=master NIGHTLY_OUT="$NT/out-current" \
    SELFTEST_GH_LOG="$GH_CUR" bash "$NIGHTLY" >"$NT/current-build.log" 2>&1
rc=$?
check "build mode on a tree AT the tip publishes (exit 0)" [ "$rc" = 0 ]
check "  the apk is named with the trunk's sha, not the checkout's" \
    bash -c '[ -n "$(find "$1" -name "*-$2.apk")" ] && [ -z "$(find "$1" -name "*-$3.apk")" ]' \
        _ "$NT/out-current" "$TRUNK" "$STALE"
check "  the release title carries the trunk's sha" \
    bash -c 'grep -q "release create nightly-" "$1" && grep -qF "($2)" "$1"' _ "$GH_CUR" "$TRUNK"
check "  and the notes call it the tip rather than qualifying it" \
    bash -c 'grep -qF "the tip of" "$1" && ! grep -qiE "behind|unreachable" "$1"' \
        _ "$NT/out-current/$DAY_L.notes.md"
check "  the day's five trunk commits are in the notes" \
    grep -qF 'target/i386: trunk commit 5, landed today' "$NT/out-current/$DAY_L.notes.md"

# The flat sentence is not simply deleted: at the tip, with an empty window,
# it is the correct sentence and it must still appear.
nt_notes "$NIGHTLY" "$CURRENT" "$NT/current-empty.md" "$(date -d '30 minutes ago' -Iseconds)"
check "at the tip with a genuinely empty window, the flat sentence is still used" \
    notes_print_the_bare_sentence "$NT/current-empty.md"

# Origin unreachable: it must SAY so, not silently fall back to the local sha.
UNREACH="$NT/unreachable"
git clone -q "$ORIGIN" "$UNREACH"
git -C "$UNREACH" remote set-url origin "$NT/no-such-repo.git"
nt_notes "$NIGHTLY" "$UNREACH" "$NT/unreachable.md"
check "an unreachable origin is named in the notes, not silently ignored" \
    bash -c 'grep -qF "origin was unreachable" "$1" && grep -qF "Could not reach" "$1"' \
        _ "$NT/unreachable.md"
check "  the last successful fetch is dated, so the reader can price the risk" \
    grep -qF 'last fetched at' "$NT/unreachable.md"
check "  and the empty window is qualified there too" \
    notes_avoid_the_bare_sentence "$NT/unreachable.md"

# ------------------------------------------------------------ falsification
# nightly_build.sh lines 66-80 and the notes else-branch as they stood at
# bda6c52d9c, verbatim, over the SAME five-commits-behind tree. The lines
# cannot be reached through the real script any more, so they are run
# directly. If the checks above pass against this, they are testing nothing.
cat > "$NT/legacy-notes.sh" <<'LEGACY'
#!/usr/bin/env bash
set -u
cd "$NIGHTLY_TREE" || exit 1
BRANCH=$(git rev-parse --abbrev-ref HEAD)
SHA=$(git rev-parse --short HEAD)
UNPUSHED=$(git log --oneline "origin/$BRANCH..HEAD" 2>/dev/null | wc -l)
if [ "$UNPUSHED" -gt 0 ]; then
    PROV="built from **unpushed** \`$SHA\` on \`$BRANCH\` ($UNPUSHED commits ahead of origin)"
else
    PROV="built from \`$SHA\` on \`$BRANCH\`"
fi
SINCE="${2:-$(date -d 'yesterday 00:30' -Iseconds)}"
TOTAL=$(git log --since="$SINCE" --oneline 2>/dev/null | wc -l)
echo "Automated nightly. $PROV."
echo
if [ "$TOTAL" -gt 0 ]; then
    git log --no-merges --since="$SINCE" --format='- %s'
else
    echo "No commits in the last day."
fi
LEGACY
nt_notes "$NT/legacy-notes.sh" "$BEHIND" "$NT/legacy.md"
check "the falsification ran and produced notes at all" \
    grep -qF 'Automated nightly.' "$NT/legacy.md"
check "  it reproduces the shipped defect: the stale sha, stated as fact" \
    grep -qF "built from \`$STALE\` on \`master\`" "$NT/legacy.md"
check "FALSIFIED: the replaced code claims to be the trunk while five behind" \
    notes_claim_to_be_the_trunk_falsely "$NT/legacy.md"
check "FALSIFIED: and prints 'No commits in the last day.' while the trunk moved" \
    notes_print_the_bare_sentence "$NT/legacy.md"
check "  not vacuous (1): the new notes name the trunk, on the same tree" \
    notes_do_not_claim_to_be_the_trunk "$NT/behind.md"
check "  not vacuous (2): the new notes avoid the bare sentence, on the same tree" \
    notes_avoid_the_bare_sentence "$NT/behind.md"
