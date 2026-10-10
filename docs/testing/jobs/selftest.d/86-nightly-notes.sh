# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# the shims on PATH, ok/bad/check, and the live prediction's fixtures. Not
# executable, no shebang, no exit -- `fail` is shared and is the run's verdict.
#
# nightly_build.sh: the release notes are one player-facing line per merged
# change, and they carry none of our process.
#
# Builds its own git fixtures under $T/nightlynotes. No shared state, and it
# builds nothing: `nightly_build.sh notes` stops before ./gradlew.
#
# WHAT THIS PINS, three defects in the order they were found:
#   1. 2026-09-19: `git log --since | head -40` listed the newest forty
#      commits, all harness, and named no emulator work at all.
#   2. 2026-09-25: a window over commit DATES missed a lane commit written
#      days before its fold.
#   3. 2026-09-26: the notes listed every lane COMMIT that touched emulator
#      code -- "diagnostic trace ... NOT FOR MERGE", "arm scaffolding", a fix
#      and its own revert -- plus capped harness and docs sections and a
#      563-commit tally. The body is public and carries no process
#      commentary (owner, AGENTS.md PR #239), so the unit is now the merged
#      PR, written in a player's words, grouped by what it does for one.
# Each has a falsification below that runs the replaced code over the same
# fixture and requires that the check FAILS against it.
#
# There is deliberately no grep over nightly_build.sh's source here: its
# comments quote the lines they replaced. Behaviour only.

echo "== nightly_build.sh: one player-facing line per merged change"
NB="$T/nightlynotes"
NIGHTLY="$TESTING/nightly_build.sh"
rm -rf "$NB"; mkdir -p "$NB/bodies"

commit_touching() {   # <repo> <subject> <path...>
    local d=$1 subject=$2; shift 2
    local p
    for p in "$@"; do mkdir -p "$d/$(dirname "$p")"; echo "$subject" >> "$d/$p"; done
    git -C "$d" add -A
    git -C "$d" commit -q -m "$subject"
}
fold_pr() {   # <repo> <pr> <branch> <title> -- merges <branch> into master as fold.sh does
    git -C "$1" checkout -q master
    git -C "$1" merge -q --no-ff --no-edit -m "fold: PR #$2 $3 -- $4" "$3"
}
FIX="$NB/tree"
git -c init.defaultBranch=master init -q "$FIX"
git -C "$FIX" config user.email s@t; git -C "$FIX" config user.name s
commit_touching "$FIX" "base" README.md

# A direct emulator commit on the trunk (no PR): listed by its subject.
commit_touching "$FIX" "target/i386: FIST honours the rounding mode" target/i386/fpu_helper.c

# #201: a lane's working commits -- the trace, the scaffolding, the revert --
# and the fix. Its body carries the line a player should read.
git -C "$FIX" checkout -q -b lane/fix311
commit_touching "$FIX" "#91 diagnostic trace over #88's decline -- NOT FOR MERGE" hw/xbox/nv2a/pgraph/vk/surface.c
commit_touching "$FIX" "arm scaffolding -- #88's decline as #91's a_ref" hw/xbox/nv2a/pgraph/vk/draw.c
commit_touching "$FIX" "remediate: audit pass 2 of PR #194 -- fix the two MEDIUMs" hw/xbox/nv2a/pgraph/vk/surface.c
fold_pr "$FIX" 201 lane/fix311 "#311: release a reused surface slot's access watch (Ghoulies 2 -> 29 fps)"
printf '%s\n' "Lane: fix311" "" "Release note (performance): Grabbed by the Ghoulies no longer slows to 1-2 fps after a minute (#311)" \
    > "$NB/bodies/201.md"

# #202: a change and its revert inside the PR -- no net emulator diff.
git -C "$FIX" checkout -q -b lane/brdf315 master
commit_touching "$FIX" "#315: Texture_BRDF corner wedge" hw/xbox/nv2a/pgraph/glsl/psh.c
git -C "$FIX" revert --no-edit HEAD >/dev/null
commit_touching "$FIX" "docs/lanes/brdf315: refuted" docs/lanes/brdf315/NOTES.md
fold_pr "$FIX" 202 lane/brdf315 "#315: Texture_BRDF -- BRDF mode and the corner wedge"

# #203: no release note, no map row -- the cleaned title, category guessed.
git -C "$FIX" checkout -q -b lane/vshconst master
commit_touching "$FIX" "vsh: const writes" hw/xbox/nv2a/pgraph/glsl/vsh-prog.c
fold_pr "$FIX" 203 lane/vshconst "lane.vshconst: a vertex program writing a constant no longer aborts (#233) -- one arm each"

# #204: a jargon title, corrected by a map row.
git -C "$FIX" checkout -q -b lane/zdepth272 master
commit_touching "$FIX" "zdepth" hw/xbox/nv2a/pgraph/glsl/vsh-ff.c
fold_pr "$FIX" 204 lane/zdepth272 "#272 (+#275): fixed-function depth arithmetic (zdepth272)"

# #205: an investigation that touched emulator code: listed by number only.
git -C "$FIX" checkout -q -b lane/fmv303 master
commit_touching "$FIX" "fmv303 probe" hw/xbox/nv2a/pgraph/vk/display.c
fold_pr "$FIX" 205 lane/fmv303 "lanes/fmv303: #303 Spikeout FMV green blocks (investigating)"

# #206: off-by-default instrumentation, mapped to none.
git -C "$FIX" checkout -q -b lane/perfbase master
commit_touching "$FIX" "pace line" hw/xbox/nv2a/pgraph/profile.c
fold_pr "$FIX" 206 lane/perfbase "perfbase: hakuX-pace line (#68)"

# #207: folded, then reverted by fold.sh in the same window: neither listed.
git -C "$FIX" checkout -q -b lane/blend300 master
commit_touching "$FIX" "blend" hw/xbox/nv2a/pgraph/gl/blit.c
fold_pr "$FIX" 207 lane/blend300 "nv2a/gl: the BLEND_AND blit rounds (#300)"
git -C "$FIX" revert --no-commit -m 1 HEAD >/dev/null
git -C "$FIX" commit -q -m "fold: revert #207 to attribute master's red at abc1234"

# #208: a ui/ change that also touches the harness: emulator, category Other.
git -C "$FIX" checkout -q -b lane/overlay master
commit_touching "$FIX" "overlay" ui/xemu-settings.c docs/testing/jobs/arms.sh
fold_pr "$FIX" 208 lane/overlay "ui: the pause overlay keeps its aspect"

# #209: a harness fold, then the burst of harness commits that took all forty
# slots on 2026-09-19.
git -C "$FIX" checkout -q -b lane/toolsmith master
commit_touching "$FIX" "handback: defect 25" docs/testing/jobs/handback.sh
fold_pr "$FIX" 209 lane/toolsmith "handback.sh: resume a lane idle with no work"
for i in $(seq 1 45); do
    commit_touching "$FIX" "harness: fold tick $i" "docs/testing/jobs/tick$i.sh"
done

printf '%s\t%s\t%s\n' 204 rendering "Depth-buffered floors no longer read 2-5 units high (#272)." 206 none "" \
    > "$NB/map.tsv"

run_notes() {   # <script> <outfile> ; SINCE is fixed so the wall clock cannot matter
    NIGHTLY_TREE="$FIX" NIGHTLY_OUT="$NB/must-not-exist" \
        NIGHTLY_NOTES_MAP="$NB/map.tsv" NIGHTLY_PR_BODIES="$NB/bodies" \
        bash "$1" notes 2000-01-01 >"$2" 2>"$2.err"
}
# THE CHECKS, as functions so the falsifications below can put the replaced
# code through the identical test.
notes_name_the_buried_fix() {   # <notes file> -- a direct (non-lane) commit's subject is left exactly
                                # as the author wrote it; only an offline lane's own prose is capitalised
    grep -qxF -- '- target/i386: FIST honours the rounding mode' "$1"
}
# Our words, in a list line. A list line is what the replaced code filled with
# lane subjects; the prose lines around it are the generator's own.
PROCESS_RE='\b(arms?|a_ref|lanes?|audit|remediat[a-z]*|diagnostic|probe|scaffolding|instrumentation|not for merge|MEDIUMs?|harness|fold tick)\b'
notes_speak_for_players() {   # <notes file>
    [ -s "$1" ] && grep -q '^- ' "$1" && ! grep '^- ' "$1" | grep -qiE "$PROCESS_RE"
}
notes_speak_process() { ! notes_speak_for_players "$1"; }
section_of() {   # <notes file> <heading> -> that section's list lines
    awk -v h="### $2" '$0 == h { on = 1; next } /^### / { on = 0 } on && /^- /' "$1"
}

run_notes "$NIGHTLY" "$NB/new.md"; rc=$?
check "notes mode exits 0 and builds nothing" [ "$rc" = 0 ]
check "notes mode writes nothing into the nightly output directory" [ ! -e "$NB/must-not-exist" ]
check "THE CHECK: no list line carries our process words" \
    notes_speak_for_players "$NB/new.md"
check "  none of #201's working commits is listed" \
    bash -c '! grep -qiE "diagnostic trace|scaffolding|remediate" "$1"' _ "$NB/new.md"
check "  #201 is one line, from its body's Release note, under Performance" \
    bash -c '[ "$(grep -c "#311" "$1")" = 1 ] && grep -qxF -- "- Grabbed by the Ghoulies no longer slows to 1-2 fps after a minute (#311)" "$2"' \
        _ "$NB/new.md" <(section_of "$NB/new.md" Performance)
check "  a change and its revert inside one PR leave no line" \
    bash -c '! grep -qF "#315" "$1" && ! grep -qF "#202" "$1"' _ "$NB/new.md"
check "  a fold and fold.sh's revert of it leave no line" \
    bash -c '! grep -qF "#300" "$1" && ! grep -qF "#207" "$1"' _ "$NB/new.md"
check "  a title with no note loses its lane prefix and tail, and is guessed Stability" \
    bash -c 'grep -qxF -- "- a vertex program writing a constant no longer aborts (#233)" "$1"' \
        _ <(section_of "$NB/new.md" Stability)
check "  a map row replaces a jargon title, verbatim, under Rendering fixes" \
    bash -c 'grep -qxF -- "- Depth-buffered floors no longer read 2-5 units high (#272)." "$1" && ! grep -qF "zdepth" "$2"' \
        _ <(section_of "$NB/new.md" "Rendering fixes") "$NB/new.md"
check "  an investigation is named by number only" \
    grep -qxF -- '- Further emulator changes: #205.' "$NB/new.md"
check "  a map row of none leaves the change out" \
    bash -c '! grep -qF "#206" "$1" && ! grep -qF "pace line" "$1"' _ "$NB/new.md"
check "  a commit touching emulator and harness paths counts as emulator" \
    bash -c 'grep -qxF -- "- ui: the pause overlay keeps its aspect (#208)" "$1"' _ <(section_of "$NB/new.md" Other)
check "  a direct emulator commit is listed by its subject" \
    notes_name_the_buried_fix "$NB/new.md"
check "the sections come in player order: Performance, Stability, Rendering fixes, Other" \
    bash -c '[ "$(grep "^### " "$1" | tr "\n" "|")" = "### Performance|### Stability|### Rendering fixes|### Other|" ]' _ "$NB/new.md"
check "exactly six list lines: one per listed change" \
    bash -c '[ "$(grep -c "^- " "$1")" = 6 ]' _ "$NB/new.md"
check "the harness is one sentence, not a list or a tally" \
    bash -c '[ "$(grep -cxF "Plus internal test-harness work." "$1")" = 1 ] && ! grep -qiE "^### (Harness|Docs)|did the work|more\._|fold tick|handback" "$1"' _ "$NB/new.md"
check "the fold merge subjects take no line" \
    bash -c '! grep -qF "fold: " "$1"' _ "$NB/new.md"
check "the install lines and the ES-DE line are kept, and the body ends with the UTC stamp" \
    bash -c 'grep -qF "Installs alongside an official hakuX build" "$1" && grep -qF "docs/es-de/" "$1" && tail -1 "$1" | grep -qE "^_Notes updated [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2} UTC\._$"' _ "$NB/new.md"
check "the log counts the changes: 8 emulator, 6 lines, 2 left out" \
    grep -qF '8 emulator change(s), 6 line(s), 2 left out' "$NB/new.md.err"
check "the log says why #205 is listed by number" \
    grep -qF 'the line for #205 reads as process' "$NB/new.md.err"
check "no warning is raised when the notes do list the emulator work" \
    bash -c '! grep -q "WARNING: .* emulator change" "$1"' _ "$NB/new.md.err"

# Without the body or the map, the fallback still never prints our words.
NIGHTLY_TREE="$FIX" NIGHTLY_OUT="$NB/must-not-exist" NIGHTLY_NOTES_MAP=/nonexistent \
    NIGHTLY_PR_BODIES="$NB/no-bodies" bash "$NIGHTLY" notes 2000-01-01 >"$NB/bare.md" 2>"$NB/bare.md.err"
check "with no note and no map, titles alone still carry no process words" \
    notes_speak_for_players "$NB/bare.md"
check "  and the tail after ' -- ' is gone from every title" \
    bash -c '! grep -qF " -- " "$1"' _ "$NB/bare.md"

# A window with no emulator work at all: no empty section, and no false alarm.
FIX2="$NB/harness-only"
git -c init.defaultBranch=master init -q "$FIX2"
git -C "$FIX2" config user.email s@t; git -C "$FIX2" config user.name s
commit_touching "$FIX2" "harness: the only thing that happened" docs/testing/jobs/only.sh
FIX_SAVE="$FIX"; FIX="$FIX2"
run_notes "$NIGHTLY" "$NB/none.md"; rc=$?
FIX="$FIX_SAVE"
check "a window with no emulator work still exits 0" [ "$rc" = 0 ]
check "  and prints no section and no list" \
    bash -c '! grep -qE "^(###|- )" "$1"' _ "$NB/none.md"
check "  and says so in one line, then the harness sentence" \
    bash -c 'grep -qxF "No player-facing changes in this build." "$1" && grep -qxF "Plus internal test-harness work." "$1"' _ "$NB/none.md"
check "  and raises no warning (there is nothing to have missed)" \
    bash -c '! grep -q "WARNING: .* emulator change" "$1"' _ "$NB/none.md.err"

# ---------------------------------------- offline folds (lane.local merges)
# Since 2026-09-29, a fold made while GitHub was down is an `offline_fold.py`
# merge: `fold: lane/<lane> (offline) -- <title>`, not `fold: PR #N ... --
# title`. flush_change() used to leave a subject shaped like that whole, and
# "lane/<lane>" then matched $INTERNAL_RE's `\blanes?\b` -- so a night whose
# only changes were offline folds counted every one of them internal and
# printed "No player-facing changes in this build." 2026-10-05 through 10-09
# all did exactly that.
echo "== nightly_build.sh: an offline fold is a change, not process"
FIX4="$NB/offline"
git -c init.defaultBranch=master init -q "$FIX4"
git -C "$FIX4" config user.email s@t; git -C "$FIX4" config user.name s
commit_touching "$FIX4" "base" README.md

fold_offline() {   # <repo> <lane> <branch> <title> -- merges <branch> into master as offline_fold.py does
    git -C "$1" checkout -q master
    git -C "$1" merge -q --no-ff --no-edit -m "fold: lane/$2 (offline) -- $4" "$3"
}

# An offline fold with its own release note, in docs/lanes/<lane>/PR.md.
git -C "$FIX4" checkout -q -b lane/offlinenote master
commit_touching "$FIX4" "offlinenote: a made-up rendering fix" hw/xbox/nv2a/pgraph/offline.c
mkdir -p "$FIX4/docs/lanes/offlinenote"
printf '%s\n' "Lane: offlinenote" "" "Release note (rendering): Some made-up rendering fix text (#999)" \
    > "$FIX4/docs/lanes/offlinenote/PR.md"
git -C "$FIX4" add -A; git -C "$FIX4" commit -q -m "offlinenote: PR.md"
fold_offline "$FIX4" offlinenote lane/offlinenote "offlinenote: a made-up rendering fix (#433)"

# An offline fold with no PR.md: the cleaned title, category guessed.
git -C "$FIX4" checkout -q -b lane/offlinebare master
commit_touching "$FIX4" "offlinebare: a vertex buffer no longer drops its last row" hw/xbox/nv2a/pgraph/offlinebare.c
fold_offline "$FIX4" offlinebare lane/offlinebare "offlinebare: a vertex buffer no longer drops its last row (#433)"

# An offline fold touching only docs/: internal, same as any other lane.
git -C "$FIX4" checkout -q -b lane/offlinedocs master
commit_touching "$FIX4" "offlinedocs: just analysis notes" docs/lanes/offlinedocs/NOTES.md
fold_offline "$FIX4" offlinedocs lane/offlinedocs "offlinedocs: just analysis notes (#433)"

# Two folds that DO touch hw/ (so lane_body_line is consulted at all) but
# whose own PR.md says "none" with prose after it, the two forms addressed by
# the exact-match defect found reviewing c61abb39ce: `[ "${text,,}" = none ]`
# only caught the bare word, so "none. <prose>" and "none (<prose>)" fell
# through to guess_cat and were LISTED under Other, and a window whose only
# change was one of these said "would publish" instead of "would not
# publish". Both forms are ordinary: "none." is the second most common
# Release note shape on master, and this PR's own PR.md uses it.
git -C "$FIX4" checkout -q -b lane/offlinenonedot master
commit_touching "$FIX4" "offlinenonedot: nothing a player would see" hw/xbox/nv2a/pgraph/offlinenonedot.c
mkdir -p "$FIX4/docs/lanes/offlinenonedot"
printf '%s\n' "Lane: offlinenonedot" "" "Release note: none. This PR changes no emulator code." \
    > "$FIX4/docs/lanes/offlinenonedot/PR.md"
git -C "$FIX4" add -A; git -C "$FIX4" commit -q -m "offlinenonedot: PR.md"
fold_offline "$FIX4" offlinenonedot lane/offlinenonedot "offlinenonedot: nothing a player would see (#433)"

git -C "$FIX4" checkout -q -b lane/offlinenoneparen master
commit_touching "$FIX4" "offlinenoneparen: nothing a player would see either" hw/xbox/nv2a/pgraph/offlinenoneparen.c
mkdir -p "$FIX4/docs/lanes/offlinenoneparen"
printf '%s\n' "Lane: offlinenoneparen" "" "Release note: none (analysis only; no emulator code changed)" \
    > "$FIX4/docs/lanes/offlinenoneparen/PR.md"
git -C "$FIX4" add -A; git -C "$FIX4" commit -q -m "offlinenoneparen: PR.md"
fold_offline "$FIX4" offlinenoneparen lane/offlinenoneparen "offlinenoneparen: nothing a player would see either (#433)"

# A bogus map row and body file at the umbrella number: if either leaked into
# the output, the (#433) tail was looked up as a PR number, which it never is.
printf '%s\t%s\t%s\n' 433 other "SHOULD NOT APPEAR" > "$NB/offline-map.tsv"
mkdir -p "$NB/offline-bodies"
printf '%s\n' "Release note (other): SHOULD NOT APPEAR EITHER" > "$NB/offline-bodies/433.md"

NIGHTLY_TREE="$FIX4" NIGHTLY_OUT="$NB/must-not-exist" \
    NIGHTLY_NOTES_MAP="$NB/offline-map.tsv" NIGHTLY_PR_BODIES="$NB/offline-bodies" \
    bash "$NIGHTLY" notes 2000-01-01 >"$NB/offline.md" 2>"$NB/offline.md.err"
rc=$?
check "offline-fold fixture: notes mode exits 0" [ "$rc" = 0 ]
check "THE CHECK: an offline fold with a PR.md note is listed with that note" \
    bash -c 'grep -qxF -- "- Some made-up rendering fix text (#999)" "$1"' \
        _ <(section_of "$NB/offline.md" "Rendering fixes")
check "  an offline fold with no PR.md is listed with its cleaned title, under a guessed category" \
    bash -c 'grep -qxF -- "- A vertex buffer no longer drops its last row" "$1"' \
        _ <(section_of "$NB/offline.md" "Rendering fixes")
check "  neither offline fold's lane name nor \"(offline)\" survives into the body" \
    bash -c '! grep -qiE "offlinenote|offlinebare|offlinedocs|\(offline\)" "$1"' _ "$NB/offline.md"
check "  an offline fold touching only docs/ is internal: not listed, and counted" \
    bash -c '! grep -qF "just analysis notes" "$1" && grep -qxF "Plus internal test-harness work." "$1"' _ "$NB/offline.md"
check "THE CHECK: an EMU-path fold whose note is 'none. <prose>' is not listed" \
    bash -c '! grep -qiF "nothing a player would see" "$1"' _ "$NB/offline.md"
check "  neither is one whose note is 'none (<prose>)'" \
    bash -c '! grep -qiF "nothing a player would see either" "$1"' _ "$NB/offline.md"
check "  the umbrella tail (#433) is never looked up as a PR number" \
    bash -c '! grep -qF "SHOULD NOT APPEAR" "$1"' _ "$NB/offline.md"
check "  the fold merge subjects take no line" \
    bash -c '! grep -qF "fold: " "$1"' _ "$NB/offline.md"
check "  the log counts it right: 4 emulator, 2 lines, 2 left out, 4 internal" \
    grep -qF '4 emulator change(s), 2 line(s), 2 left out, 4 internal' "$NB/offline.md.err"
check "  and prints 'would publish' (something IS listed, from the other two folds)" \
    grep -qF 'would publish' "$NB/offline.md.err"

# A window whose ONLY change is one of these "none.
# <prose>"/"none (<prose>)" EMU-path folds: notes mode must say it would NOT
# publish. (Build mode's exit 9 for this shape is already covered by the
# docs-only fixture below; this is the same gate, reached through the
# regex fix instead of the docs/ path.)
FIX6="$NB/offline-nonedot-only"
git -c init.defaultBranch=master init -q "$FIX6"
git -C "$FIX6" config user.email s@t; git -C "$FIX6" config user.name s
commit_touching "$FIX6" "base" README.md
git -C "$FIX6" checkout -q -b lane/onlynonedot master
commit_touching "$FIX6" "onlynonedot: nothing a player would see" hw/xbox/nv2a/pgraph/onlynonedot.c
mkdir -p "$FIX6/docs/lanes/onlynonedot"
printf '%s\n' "Lane: onlynonedot" "" "Release note: none. This PR changes no emulator code." \
    > "$FIX6/docs/lanes/onlynonedot/PR.md"
git -C "$FIX6" add -A; git -C "$FIX6" commit -q -m "onlynonedot: PR.md"
fold_offline "$FIX6" onlynonedot lane/onlynonedot "onlynonedot: nothing a player would see (#433)"
NIGHTLY_TREE="$FIX6" NIGHTLY_OUT="$NB/must-not-exist" \
    bash "$NIGHTLY" notes 2000-01-01 >"$NB/offline-nonedot-only.md" 2>"$NB/offline-nonedot-only.md.err"
check "THE CHECK: a window with only a 'none.'-noted EMU fold lists nothing" \
    bash -c '! grep -qE "^(###|- )" "$1" && grep -qxF "No player-facing changes in this build." "$1"' \
        _ "$NB/offline-nonedot-only.md"
check "  and notes mode says it would NOT publish" \
    grep -qF 'would not publish: no player-facing change' "$NB/offline-nonedot-only.md.err"

# FALSIFICATION: the exact-match test this PR replaced, `[ "${text,,}" =
# none ]`, run directly against the two prose forms above. It must FAIL to
# recognise either as "none" -- that failure is exactly the defect found
# reviewing c61abb39ce (it fell through to guess_cat and was listed under
# Other) -- while the regex this PR uses catches both, and still leaves a
# real note that merely contains the word "none" later on alone.
check "FALSIFIED: the replaced exact-match test misses a 'none.' prose tail" \
    bash -c '[ "${1,,}" != none ]' _ "none. This PR changes no emulator code."
check "FALSIFIED:   and misses a 'none (' prose tail the same way" \
    bash -c '[ "${1,,}" != none ]' _ "none (analysis only; no emulator code changed)"
check "  not vacuous: the exact-match test does still catch a bare 'none'" \
    bash -c '[ "${1,,}" = none ]' _ "none"
check "  the new regex catches the 'none.' prose tail" \
    bash -c '[[ "${1,,}" =~ ^none([^a-z]|$) ]]' _ "none. This PR changes no emulator code."
check "  the new regex catches the 'none (' prose tail" \
    bash -c '[[ "${1,,}" =~ ^none([^a-z]|$) ]]' _ "none (analysis only; no emulator code changed)"
check "  and the new regex leaves alone a real note that merely mentions none later" \
    bash -c '! [[ "${1,,}" =~ ^none([^a-z]|$) ]]' _ "performance is fine, none of this regressed"

# --------------------------------- an offline fold's lane dir can differ from its branch
# A retry or a split takes a suffixed branch (forzadecay414-fix, uberspike569-gpl
# on master) while the title names the ORIGINAL lane with a "lane.<name>"
# token, and docs/lanes/<name>/ keeps that original name too. The REPLACED
# code looked up docs/lanes/<branch>/ (never existed for either real case) and
# only stripped a literal "<branch>: " prefix from the title, never
# "lane.<name>: " -- so "lane." stayed in the text, and $INTERNAL_RE's
# \blanes?\b matched it (the word boundary after "lane" is satisfied by the
# "."), dropping a real Release note as process instead of listing it. Model
# is e816bc35dd on master: branch forzadecay414-fix, title "lane.forzadecay414:
# ...", note under docs/lanes/forzadecay414/.
echo "== nightly_build.sh: an offline fold's PR.md can live under a name other than its branch"
FIX7="$NB/offline-branch-mismatch"
git -c init.defaultBranch=master init -q "$FIX7"
git -C "$FIX7" config user.email s@t; git -C "$FIX7" config user.name s
commit_touching "$FIX7" "base" README.md

# A branch suffixed "-fix", titled with a bare "lane.<name>" token (no
# qualifier) naming the ORIGINAL lane directory. Its own Release note starts
# lowercase, so this fixture also covers "a lowercase note is listed
# capitalised".
git -C "$FIX7" checkout -q -b lane/foo-fix master
commit_touching "$FIX7" "foo: a fix landed on a retry branch" hw/x/a.c
mkdir -p "$FIX7/docs/lanes/foo"
printf '%s\n' "Lane: foo" "" \
    "Release note (performance): a game you have played before no longer freezes at its loading screen" \
    > "$FIX7/docs/lanes/foo/PR.md"
git -C "$FIX7" add -A; git -C "$FIX7" commit -q -m "foo: PR.md"
fold_offline "$FIX7" foo-fix lane/foo-fix "lane.foo: x (#1)"

# The same shape, but the note is (none): nothing should be listed even
# though the branch/title mismatch is identical.
git -C "$FIX7" checkout -q -b lane/bar-fix master
commit_touching "$FIX7" "bar: a no-op fix landed on a retry branch" hw/x/b.c
mkdir -p "$FIX7/docs/lanes/bar"
printf '%s\n' "Lane: bar" "" "Release note (none): telemetry only, off by default" \
    > "$FIX7/docs/lanes/bar/PR.md"
git -C "$FIX7" add -A; git -C "$FIX7" commit -q -m "bar: PR.md"
fold_offline "$FIX7" bar-fix lane/bar-fix "lane.bar: y (#2)"

NIGHTLY_TREE="$FIX7" NIGHTLY_OUT="$NB/must-not-exist" \
    bash "$NIGHTLY" notes 2000-01-01 >"$NB/branch-mismatch.md" 2>"$NB/branch-mismatch.md.err"
rc=$?
check "branch-mismatch fixture: notes mode exits 0" [ "$rc" = 0 ]
check "THE CHECK: the PR.md under the title's lane.<name> token is found and listed, capitalised" \
    bash -c 'grep -qxF -- "- A game you have played before no longer freezes at its loading screen" "$1"' \
        _ <(section_of "$NB/branch-mismatch.md" Performance)
check "  neither \"lane.foo\" nor the branch name survives into the body" \
    bash -c '! grep -qiE "lane\.foo|foo-fix" "$1"' _ "$NB/branch-mismatch.md"
check "  the same mismatch with a (none) note lists nothing for it" \
    bash -c '! grep -qiE "no-op fix|lane\.bar|bar-fix" "$1"' _ "$NB/branch-mismatch.md"

# FALSIFICATION: the two causes named above, checked directly against this
# fixture, without re-deriving the whole pipeline.
check "FALSIFIED: the replaced lookup (docs/lanes/<branch>/PR.md) finds nothing" \
    bash -c '! git -C "$1" cat-file -e lane/foo-fix:docs/lanes/foo-fix/PR.md 2>/dev/null' _ "$FIX7"
check "  while docs/lanes/<the title's lane.<name> token>/PR.md (the new fallback) does exist" \
    bash -c 'git -C "$1" cat-file -e lane/foo-fix:docs/lanes/foo/PR.md 2>/dev/null' _ "$FIX7"
check "FALSIFIED: the replaced title-cleaning (strip only the literal branch prefix) leaves \"lane.\" in the text" \
    bash -c 'title=$(sed -E "s/^foo-fix( attempt [0-9]+)?: //" <<<"lane.foo: x (#1)"); \
             title=$(sed -E "s/ \(#[0-9]+\)\$//" <<<"$title"); [ "$title" = "lane.foo: x" ]'
check "  ...which \$INTERNAL_RE's \\blanes?\\b then matches (the boundary after \"lane\" is the \".\")" \
    bash -c 'grep -qiE "\\blanes?\\b" <<<"lane.foo: x"'
check "  not vacuous: the new title-cleaning does not leave \"lane.\" in the text" \
    bash -c '! grep -qiE "\\blanes?\\b" <<<"A game you have played before no longer freezes at its loading screen"'

# ------------------------------------- publish nothing when nothing changed
# Owner, 2026-10-09: "if any of them have no changes, take down the nightly."
# A window whose only change is internal (same shape as 10-05..10-09, which
# were offline folds that used to be miscounted the same way) must not reach
# `gh release create`, must still build and log, and must exit a documented,
# distinct code -- not 0 -- so systemd and anything reading
# nightly/<date>.log can tell a deliberate no-op from either a real publish
# or a real failure.
echo "== nightly_build.sh: nothing published when nothing changed"
FIX5="$NB/nopublish"
git -c init.defaultBranch=master init -q "$FIX5"
git -C "$FIX5" config user.email s@t; git -C "$FIX5" config user.name s

# The android/ stub (as in 87-nightly-trunk.sh's SEED) is what makes build
# mode runnable here at all. It is dated three days ago, like 87's $OLD, so
# the default one-day window never counts it -- otherwise its own path
# (android/...) would match $EMU_RE and the fixture would not be the "nothing
# changed" shape it is meant to be.
OLD5=$(date -d '3 days ago' -Iseconds)
NOW5=$(date -d '2 hours ago' -Iseconds)
mkdir -p "$FIX5/android/app"
cat > "$FIX5/android/gradlew" <<'GRADLEW'
#!/usr/bin/env bash
mkdir -p app/build/outputs/apk/release
echo "fake apk for $*" > app/build/outputs/apk/release/app-release.apk
GRADLEW
chmod +x "$FIX5/android/gradlew"
echo 'versionName = "0.9-selftest"' > "$FIX5/android/app/build.gradle.kts"
git -C "$FIX5" add -A
GIT_AUTHOR_DATE="$OLD5" GIT_COMMITTER_DATE="$OLD5" git -C "$FIX5" commit -q -m "base: the android stub"

# The one change in the window: an offline fold touching only docs/, same
# shape as a build-input-plumbing-only night. Dated two hours ago so it IS in
# the default window; the lane commit under it is never on the first-parent
# line, so its own date does not matter.
git -C "$FIX5" checkout -q -b lane/plumbing master
commit_touching "$FIX5" "plumbing: build-input wiring only" docs/lanes/plumbing/NOTES.md
git -C "$FIX5" checkout -q master
GIT_AUTHOR_DATE="$NOW5" GIT_COMMITTER_DATE="$NOW5" git -C "$FIX5" merge -q --no-ff --no-edit \
    -m "fold: lane/plumbing (offline) -- plumbing: build-input wiring only (#433)" lane/plumbing

ORIGIN5="$NB/nopublish-origin.git"
git -c init.defaultBranch=master init -q --bare "$ORIGIN5"
git -C "$FIX5" remote add origin "$ORIGIN5"
git -C "$FIX5" push -q origin master

NIGHTLY_TREE="$FIX5" NIGHTLY_OUT="$NB/must-not-exist" \
    bash "$NIGHTLY" notes >"$NB/nopublish-notes.md" 2>"$NB/nopublish-notes.md.err"
check "nothing-changed fixture: notes mode exits 0 and lists nothing" \
    bash -c '[ "$1" = 0 ] && grep -qxF "No player-facing changes in this build." "$2"' \
        _ "$?" "$NB/nopublish-notes.md"
check "  notes mode prints which way it would go: would not publish" \
    grep -qF 'would not publish: no player-facing change' "$NB/nopublish-notes.md.err"

GH_NOPUB="$NB/gh-nopublish.log"; : > "$GH_NOPUB"
NIGHTLY_TREE="$FIX5" NIGHTLY_TIP=master NIGHTLY_OUT="$NB/out-nopublish" \
    SELFTEST_GH_LOG="$GH_NOPUB" bash "$NIGHTLY" >"$NB/nopublish-build.log" 2>&1
rc=$?
check "THE CHECK: build mode on it exits 9 (documented, distinct from 0 and from a failure)" \
    [ "$rc" = 9 ]
check "  and says so in the log" \
    grep -qE 'not published: no player-facing change' "$NB/nopublish-build.log"
check "  the APK was still built -- it is just not published" \
    bash -c '[ -n "$(find "$1" -name "*.apk" 2>/dev/null)" ]' _ "$NB/out-nopublish"
check "  gh was never asked to create or upload a release" \
    bash -c '! grep -qE "release (create|upload)" "$1"' _ "$GH_NOPUB"

# ------------------------------------------------------------ falsification 1
# The 2026-09-19 code, verbatim: nightly_build.sh lines 46-47 and 70-76 as
# they stood at 6ca12eb803, run directly over the same fixture.
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
check "falsification 1 ran and produced notes at all" \
    bash -c '[ "$(grep -c "^- " "$1")" = 40 ]' _ "$NB/legacy.md"
check "FALSIFIED 1: head -40 misses the buried target/i386 fix" \
    bash -c '! grep -qxF -- "- target/i386: FIST honours the rounding mode" "$1"' _ "$NB/legacy.md"
check "  and the check is not vacuous: it passes on the new notes" \
    notes_name_the_buried_fix "$NB/new.md"

# ------------------------------------------------------------ falsification 3
# The 2026-09-26 code: every non-merge commit touching emulator code listed
# by subject (nightly_build.sh at a5b5b628f2, the classification loop and the
# Emulator section), over the same fixture.
cat > "$NB/legacy-commits.sh" <<'LEGACY'
#!/usr/bin/env bash
set -u
cd "$NIGHTLY_TREE" || exit 1
SUB_EMU=(); cur=""; area=""
flush() { [ "$area" = emu ] && SUB_EMU+=("- $cur"); return 0; }
while IFS= read -r line; do
    case "$line" in
        $'\x01'*) flush; cur="${line#$'\x01'}"; area=other ;;
        hw/*|target/*|accel/*|ui/*|audio/*) area=emu ;;
    esac
done < <(git log --no-merges --format=$'\x01%s' --name-only HEAD 2>/dev/null)
flush
echo "Automated nightly."; echo
echo "### Emulator"; echo; printf '%s\n' "${SUB_EMU[@]}"
LEGACY
run_notes "$NB/legacy-commits.sh" "$NB/legacy-commits.md"
check "falsification 3 ran: the commit list names the buried fix too" \
    notes_name_the_buried_fix "$NB/legacy-commits.md"
check "FALSIFIED 3: the per-commit list carries our process words" \
    notes_speak_process "$NB/legacy-commits.md"
check "  and lists the change its own PR reverted" \
    grep -qF '#315: Texture_BRDF corner wedge' "$NB/legacy-commits.md"
check "  and the check is not vacuous: it passes on the new notes" \
    notes_speak_for_players "$NB/new.md"

# ------------------------------------------------ the range is by ancestry
# THE SECOND DEFECT. nightly-2026-09-25 built 82e460e863 over nightly-2026-09-24
# (3fe18366cd) and said "0 emulator": the window was `git log --since=<yesterday
# 00:30>`, over commit dates, and 637b4f1d2a (nv2a/gl, written 09-19, folded
# 09-24 23:41) was outside it.
#
# The fixture is that shape: yesterday's nightly tag, then a lane commit
# written three days ago that reaches the tip through a fold merge made now.
# Two decoy tags pin the choice of base, with the right one in the middle: an
# older ancestor, and a newer-named tag that is NOT an ancestor. Every decoy
# commit touches emulator code, so it would be listed if the base were wrong.
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
dated "$(date -d '2 days ago 12:00' -Iseconds)" "$FIX3" "nv2a: before yesterday's nightly" hw/old.c
dated "$(date -d 'yesterday 00:10' -Iseconds)" "$FIX3" "nv2a: the tip yesterday's nightly built" hw/y.c
git -C "$FIX3" tag "nightly-$YDAY"
git -C "$FIX3" checkout -q -b lane/late "nightly-$YDAY"
dated "$(date -d '3 days ago 12:00' -Iseconds)" "$FIX3" \
    "surface pad bits" hw/xbox/nv2a/pgraph/gl/surface.c
git -C "$FIX3" checkout -q -b lane/elsewhere nightly-2000-01-01
commit_touching "$FIX3" "nv2a: never merged" hw/elsewhere.c
git -C "$FIX3" tag nightly-9999-12-31
fold_pr "$FIX3" 172 lane/late "nv2a/gl: clear to the surface's pad-bit constant"
commit_touching "$FIX3" "harness: committed today" docs/testing/jobs/today.sh

# Both scripts get the SAME window argument: the old default, yesterday 00:30.
SINCE3=$(date -d 'yesterday 00:30' -Iseconds)
run_notes3() {   # <script> <outfile>
    NIGHTLY_TREE="$FIX3" NIGHTLY_OUT="$NB/must-not-exist" NIGHTLY_PR_BODIES="$NB/no-bodies" \
        bash "$1" notes "$SINCE3" >"$2" 2>"$2.err"
}
late_fold_is_listed() {   # <notes file>
    grep -qF -- "- nv2a/gl: clear to the surface's pad-bit constant" "$1"
}
late_fold_is_missing() { ! late_fold_is_listed "$1"; }

run_notes3 "$NIGHTLY" "$NB/late.md"; rc=$?
check "late-fold fixture: notes mode exits 0" [ "$rc" = 0 ]
check "THE CHECK: a change written 3 days ago, folded today, is listed" \
    late_fold_is_listed "$NB/late.md"
check "  under Rendering fixes, with its PR number" \
    bash -c 'grep -qxF -- "- nv2a/gl: clear to the surface'"'"'s pad-bit constant (#172)" "$1"' \
        _ <(section_of "$NB/late.md" "Rendering fixes")
check "  the base is the NEWEST ancestor tag: nothing at or before it is listed" \
    bash -c '! grep -qF "before yesterday" "$1" && ! grep -qF "the tip yesterday" "$1"' _ "$NB/late.md"
check "  a newer-named tag that is not an ancestor is not the base" \
    bash -c '! grep -qF "never merged" "$1"' _ "$NB/late.md"
check "  today's harness commit is the one sentence, not a line" \
    bash -c 'grep -qxF "Plus internal test-harness work." "$1" && ! grep -qF "committed today" "$1"' _ "$NB/late.md"
check "  the log line names the tag it counted from, over the first-parent line" \
    grep -qF "2 commit(s) since nightly-$YDAY" "$NB/late.md.err"
check "  and counts one emulator change" \
    grep -qF '1 emulator change(s), 1 line(s)' "$NB/late.md.err"
check "the tagless fixture falls back to the date window, and says so in the LOG" \
    grep -qF 'WARNING: no nightly-* tag is an ancestor of HEAD; falling back to commits dated since 2000-01-01' "$NB/new.md.err"

# ------------------------------------------- the body carries no caveats
# Owner's standing order, 2026-09-25 (AGENTS.md PR #239): the public release
# body carries no process commentary. The dirty-tree line, the not-the-trunk
# note and the date-window note go to the log, and the builds that needed them
# refuse. The predicate is shared with 87-nightly-trunk.sh, which sources
# after this file, so every fixture scenario in both is put through it.
#
# -s first: a negative grep passes against a missing or empty file.
nightly_body_has_no_caveat() {   # <notes file>
    [ -s "$1" ] && grep -q '^Automated nightly\.' "$1" \
        && ! grep -qiE '^>|warning|refus|caveat|not exactly this commit|not confirmed|unreachable|could not reach|may be behind|commit\(s\) behind|on this tree|DATED since|fall(s|ing)? back' "$1"
}
nightly_body_has_a_caveat() { ! nightly_body_has_no_caveat "$1"; }
for f in new.md bare.md none.md late.md; do
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

# ------------------------------------------------------------ falsification 2
# The replaced selection, verbatim from nightly_build.sh at 48f0618aff (the
# SINCE default and the `git log --since` it fed), over the same fixture and
# argument -- so the only difference between the two runs is the range.
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
check "falsification 2 ran: the replaced range still sees today's commit" \
    grep -qxF -- '- harness: committed today' "$NB/late-legacy.md"
check "FALSIFIED 2: the replaced date window omits the late-folded change" \
    bash -c '! grep -qF "surface pad bits" "$1"' _ "$NB/late-legacy.md"
check "  and the check is not vacuous: it passes on the new notes" \
    late_fold_is_listed "$NB/late.md"
