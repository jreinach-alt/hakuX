# Sourced by ../selftest.sh with the harness already built: $T, $HERE, $REPO,
# $TESTING, the shims on PATH, ok/bad/check. Not executable, no shebang, no
# exit -- `fail` is shared and is the run's verdict.
#
# THE TWO SWEEPS AND THE LANE THIS HOST CANNOT DRIVE.
#
# `lane.remote` is a cloud session on `claude/docs-tooling-agentic-coding-u152m1`.
# It has no local systemd unit BY DESIGN and, between PRs, no open PR either.
# Both sweeps decided a lane was dead from exactly that absence:
#
#   - issue-sweep.sh reported three of its live territory claims (#62, #60,
#     #34) as "that lane has no unit and no open PR", handing them to the
#     board to release. Releasing a live lane's territory is how two agents end
#     up editing one file, which is the single thing territory.toml exists to
#     prevent.
#   - pr-sweep.sh derived the lane name as `branch[5:] if branch.startswith
#     ("lane/") else ""`, so a `claude/*` head produced the EMPTY lane name --
#     which then fed the draft-strand class, whose whole content is naming
#     `handback.sh` as the actor that should resume it.
#
# `jobs/remote-lane.sh` (lane.laneshape, folded 2026-09-19T23:59Z) already
# answered both questions and neither sweep called it: `grep -c remote-lane
# issue-sweep.sh` was 0. This fragment is the proof that they call it now and
# that calling it is what makes the difference.
#
# 78, after 76-pr-sweep.sh and 77-issue-sweep.sh, because it is about the same
# two jobs and must not disturb their fixtures: everything here lives under
# $SR and both sweeps are run from scratch `docs/testing` trees of their own.
#
# THE BRANCH TIP IS MEASURED, NOT STUBBED. The liveness question for a remote
# lane is "has that branch moved", so the fixture is a real bare origin with a
# branch committed a minute ago and a branch committed a month ago, and the
# sweep reads them with the same `git log -1 --format=%ct` it runs on the host.
# A shimmed answer there would test the shim.
#
# EVERY EXEMPTION IS RUN AS A PAIR. A check that a live remote lane is not
# reported is satisfied by a sweep that reports nothing at all -- which is the
# failure these sweeps exist to catch, wearing the face of the fix. So each
# one carries, in the same run, either a lane that IS reported or the same
# lane with the single `remote` field deleted.

echo "== the sweeps and the lane this host cannot drive"
SR="$T/sweep-remote"; rm -rf "$SR"
mkdir -p "$SR/ibin" "$SR/pbin" "$SR/work"
export SR_DIR="$SR" SR_LOG="$SR/calls.log"

# ------------------------------------------- a real origin, with real tips
sg() { git -C "$SR/repo" -c user.email=s@t -c user.name=s "$@"; }
sg_commit_at() {   # <iso8601> <msg> -- the env goes in a SUBSHELL: a bash
                   # assignment prefixing a FUNCTION call outlives the call.
    ( export GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1"
      git -C "$SR/repo" -c user.email=s@t -c user.name=s commit -q -m "$2" )
}
git -c init.defaultBranch=master init -q --bare "$SR/origin.git"
git -c init.defaultBranch=master clone -q "$SR/origin.git" "$SR/repo" 2>/dev/null
echo base > "$SR/repo/f"; sg add -A; sg commit -q -m base; sg push -q origin master
sg checkout -q -b claude/live-u1
echo live > "$SR/repo/g"; sg add -A
sg_commit_at "$(date -u '+%FT%TZ')" live
sg push -q origin claude/live-u1
sg checkout -q master
sg checkout -q -b claude/stale-u1
echo stale > "$SR/repo/h"; sg add -A
sg_commit_at "$(date -u -d '30 days ago' '+%FT%TZ')" stale
sg push -q origin claude/stale-u1
sg checkout -q master
# THE FIXTURE IS ONLY A FIXTURE IF THE TWO TIPS REALLY DIFFER IN AGE. Both
# branches exist either way, and a `git commit` that ignored the date env would
# make every "stale" leg below pass or fail for a reason that is not the code's.
sr_tip_age() { git -C "$SR/repo" log -1 --format=%ct "$1"; }
check "the fixture's stale branch really is a month behind its live one" \
    bash -c '[ $(( $2 - $1 )) -gt 2000000 ]' _ "$(sr_tip_age claude/stale-u1)" "$(sr_tip_age claude/live-u1)"

# ------------------------------------------------------------ the shims
cat > "$SR/ibin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${SR_LOG:?}"
case "$1 $2" in
    "auth status") exit 0 ;;
    "issue list") cat "$SR_DIR/issues.json" 2>/dev/null || echo "[]"; exit 0 ;;
    "pr list")    cat "$SR_DIR/pr-heads" 2>/dev/null; exit 0 ;;
    *) exit 0 ;;
esac
EOF
cat > "$SR/pbin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "${SR_LOG:?}"
args="$*"
case "$1 $2" in
    "auth status") exit 0 ;;
    "pr list") cat "$SR_DIR/prs.json" 2>/dev/null || echo "[]"; exit 0 ;;
    "pr view")
        [[ "$args" == *comments* ]] && { cat "$SR_DIR/claim.body" 2>/dev/null; exit 0; }
        exit 0 ;;
    "pr comment")
        b=0; for a in "$@"; do [ "$b" = 1 ] && { printf '%s\n--- end comment\n' "$a" >> "$SR_DIR/comments.log"; b=0; }; [ "$a" = --body ] && b=1; done
        exit 0 ;;
    *) exit 0 ;;
esac
EOF
for d in ibin pbin; do
    cat > "$SR/$d/systemctl" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    *list-units*) cat "$SR_DIR/active" 2>/dev/null; exit 0 ;;
    *is-active*)  echo active; exit 0 ;;
    *) exit 0 ;;
esac
EOF
done
chmod +x "$SR/ibin/"* "$SR/pbin/"*

# --------------------------------------------- two scratch docs/testing trees
#
# Both sweeps find board_files.py at `dirname $J`, so a jobs/ directory on its
# own is not enough: the map read would come back `unreadable` and the tick
# would refuse for a fault the fixture invented rather than for the one under
# test. Two trees and not one, because the pr-sweep tree gets STUBS written
# into it and the issue-sweep tree must stay pure symlinks.
sr_tree() {   # <dir>
    mkdir -p "$1/jobs"
    ln -sf "$TESTING/board_files.py" "$1/board_files.py"
    for f in "$HERE"/*.sh "$HERE"/*.py "$HERE"/*.env "$HERE"/allowed-tools.*; do
        [ -e "$f" ] && ln -sf "$f" "$1/jobs/$(basename "$f")"
    done
    ln -sfn "$HERE/roles" "$1/jobs/roles" 2>/dev/null || true
}
SRT="$SR/itesting"; sr_tree "$SRT"
SRP="$SR/ptesting"; sr_tree "$SRP"

# `rm -f` BEFORE THE WRITE, and it is not tidiness: `cat > $SRP/jobs/x.sh`
# FOLLOWS the symlink and truncates the real file in the real worktree. 76's
# header records the run where that happened to four jobs at once.
sr_stub() { rm -f "$SRP/jobs/$1"; cat > "$SRP/jobs/$1"; chmod +x "$SRP/jobs/$1"; }
sr_stub handback.sh <<'EOF'
#!/usr/bin/env bash
# Records that it was asked AT ALL, which is the whole point here: a remote
# lane's PR must never reach the actor whose only move is `lane.sh resume`.
echo "handback.sh $*" >> "${SR_LOG:?}"
[ "${1:-}" = list ] || exit 0
cat "$SR_DIR/handback.list" 2>/dev/null
exit 0
EOF
sr_stub arms.sh <<'EOF'
#!/usr/bin/env bash
echo "arms.sh $*" >> "${SR_LOG:?}"
[ "${1:-}" = state ] || exit 0
cat "$SR_DIR/arms.state" 2>/dev/null
exit 0
EOF
sr_stub cloud.sh <<'EOF'
#!/usr/bin/env bash
# The real one PUSHES to origin/board. This one records.
echo "cloud.sh $*" >> "${SR_LOG:?}"
exit 0
EOF
sr_not_link() { [ -f "$SRP/jobs/$1" ] && [ ! -L "$SRP/jobs/$1" ]; }
check "the handback.sh stub is a real file, not a symlink into the repo" sr_not_link handback.sh
check "the arms.sh stub is a real file, not a symlink into the repo"     sr_not_link arms.sh
check "the cloud.sh stub is a real file, not a symlink into the repo"    sr_not_link cloud.sh
check "and the real handback.sh is still the real handback.sh" \
    grep -q "THE LANE NAME IS NOT THE PR" "$HERE/handback.sh"

# ------------------------------------------------------------- the fixtures
sr_board() {   # <dir> <lane>|<issues csv>|<remote branch or empty> ...
    local dir=$1; shift
    { printf 'wave = 1\nupdated_utc = "2026-09-19T00:00:00Z"\n'
      local spec l i r
      for spec in "$@"; do
          IFS='|' read -r l i r <<< "$spec"
          printf '\n[lane.%s]\nissues = [%s]\nfiles = []\nstanding = false\nnote = "x"\n' \
              "$l" "$([ -n "${i:-}" ] && echo "$i" | sed 's/[^,]*/"&"/g')"
          [ -n "${r:-}" ] && printf 'remote = "%s"\n' "$r"
      done
    } > "$dir/territory.toml"
}
sr_issues() {   # <num>|<labels csv>|<quiet secs> ...
    python3 - "$SR/issues.json" "$@" <<'PY'
import datetime, json, sys
out = sys.argv[1]
now = datetime.datetime.now(datetime.timezone.utc)
rows = []
for spec in sys.argv[2:]:
    num, labels, quiet = spec.split("|")
    rows.append({"number": int(num), "title": "issue %s" % num,
                 "labels": [{"name": l} for l in labels.split(",") if l],
                 "updatedAt": (now - datetime.timedelta(seconds=int(quiet)))
                              .strftime("%Y-%m-%dT%H:%M:%SZ")})
json.dump(rows, open(out, "w"))
PY
}
# A COMPLETE row, deliberately: a half-filled one lands in the untriaged class
# and every check below would pass for a reason that is not what it tests.
sr_row() { printf '\n[issue.%s]\ntitle = "issue %s"\ndisposition = "defect"\nstatus = "open"\n' \
                  "$1" "$1" >> "$SRT/nv2a_issues.toml"; }
sr_pr() {   # <num> <branch> <draft true|false> <labels csv> <quiet secs>
    python3 - "$SR/prs.json" "$@" <<'PY'
import datetime, json, os, sys
out, num, branch, draft, labels, quiet = sys.argv[1:7]
now = datetime.datetime.now(datetime.timezone.utc)
rows = json.load(open(out)) if os.path.exists(out) else []
rows.append({"number": int(num), "headRefName": branch, "headRefOid": "cafe" + num,
             "isDraft": draft == "true", "mergeable": "MERGEABLE",
             "labels": [{"name": l} for l in labels.split(",") if l],
             "updatedAt": (now - datetime.timedelta(seconds=int(quiet)))
                          .strftime("%Y-%m-%dT%H:%M:%SZ"),
             "statusCheckRollup": [], "title": "a PR the fixture made"})
json.dump(rows, open(out, "w"))
PY
}

sr_reset() { rm -rf "$SR/work"; mkdir -p "$SR/work/board" "$SR/work/logs/board"
             touch "$SR/work/logs/board/tick.log"
             : > "$SR_LOG"; : > "$SR/comments.log"; : > "$SR/active"; : > "$SR/pr-heads"
             : > "$SR/handback.list"; : > "$SR/arms.state"; : > "$SR/claim.body"
             rm -f "$SR/prs.json" "$SR/issues.json"
             printf '[issue]\n' > "$SRT/nv2a_issues.toml"; }

# HAKUX_BOARD_REF= is what makes each fixture's own territory.toml the BOARD
# rather than a fold-lagged fallback -- the deliberate-disable path in
# remote-lane.sh's header. The mutants below set it, and HAKUX_TERRITORY,
# differently on purpose.
sr_is() { ( export PATH="$SR/ibin:$PATH" HAKUX_WORK="$SR/work" HAKUX_REPO_DIR="$SR/repo" \
                   HAKUX_BOARD_REF=
            bash "$SRT/jobs/issue-sweep.sh" "$@" 2>&1 ); }
sr_ps() { ( export PATH="$SR/pbin:$PATH" HAKUX_WORK="$SR/work" HAKUX_REPO_DIR="$SR/repo" \
                   HAKUX_BOARD_REF=
            bash "$SRP/jobs/pr-sweep.sh" "$@" 2>&1 ); }
# Negatives are FUNCTIONS over $got, never `bash -c '! grep ... "$1"'`: a child
# shell sees only exported variables, and $got is fragment-local.
sr_in()      { grep -q -- "$1" <<< "$got"; }
sr_notin()   { ! grep -q -- "$1" <<< "$got"; }
sr_said()    { grep -qF -- "$1" "$SR/comments.log"; }
sr_unsaid()  { ! grep -qF -- "$1" "$SR/comments.log"; }
sr_asked()   { grep -q "^$1" "$SR_LOG"; }
sr_unasked() { ! grep -q "^$1" "$SR_LOG"; }
sr_no_heading() { ! grep -q '^### ' <<< "$got"; }
sr_findings_intact() { grep -qF "nobody has read yet" "$SR/work/board/issue-sweep.findings"; }

# ==================================================================== part 1
# issue-sweep.sh: the territory claim of a lane with no unit and no open PR.
#
# ONE FIXTURE, THREE LANES, so every verdict below is measured against the
# other two in the same run: a local lane that IS dead, a remote lane that is
# working, and a remote lane that has gone quiet for a month.
sr_reset
sr_board "$SRT" "deadlocal|21|" "livecloud|22|claude/live-u1" "stalecloud|23|claude/stale-u1"
sr_issues "21||900" "22||900" "23||900"
sr_row 21; sr_row 22; sr_row 23
got=$(sr_is list)
check "a LOCAL lane with no unit and no open PR is still reported stale" \
      sr_in 'territory row `lane.deadlocal`'
check "  and still in the words that say what was looked for" \
      sr_in 'lane.deadlocal` claims it and that lane has no unit and no open PR'
check "a REMOTE lane whose branch tip moved this minute is NOT reported" \
      sr_notin 'territory row `lane.livecloud`'
check "a REMOTE lane whose branch has not moved in a month IS reported" \
      sr_in 'territory row `lane.stalecloud`'
check "  and the finding says it is remote and names the branch it judged" \
      sr_in 'is a REMOTE lane on `claude/stale-u1`'
check "  and never tells the board it merely has no unit -- true of every cloud lane" \
      sr_notin 'lane.stalecloud` claims it and that lane has no unit'
check "the report names the remote lanes and how it judged them" \
      sr_in 'Remote lanes, judged by branch tip'
check "  naming each of them, so a dropped marker does not read like having none" \
      sr_in 'lane.livecloud on `claude/live-u1`'

# THE MUTANT THE DEFECT ASKS FOR: the SAME fixture with one field deleted.
# `remote = "claude/live-u1"` is the only difference between these two runs,
# and it flips the verdict -- so the exemption comes from the board's marker
# and from nothing else about the lane, its name or its issues.
sr_reset
sr_board "$SRT" "deadlocal|21|" "livecloud|22|" "stalecloud|23|claude/stale-u1"
sr_issues "21||900" "22||900" "23||900"
sr_row 21; sr_row 22; sr_row 23
got=$(sr_is list)
check "MUTANT: with the \`remote\` field gone, that same live lane IS reported stale" \
      sr_in 'territory row `lane.livecloud`'
check "  by the no-unit-no-PR rule, which is correct for a lane that is local" \
      sr_in 'lane.livecloud` claims it and that lane has no unit and no open PR'

# THE OPEN-PR HALF, AND IT IS THE REMOTE BRANCH'S PR AND NOT `lane/<name>`'s.
# `lane/stalecloud` is not that lane's branch and never will be; a check that
# did not separate these would pass with the old predicate left in place.
sr_reset
sr_board "$SRT" "stalecloud|23|claude/stale-u1" "deadlocal|21|"
sr_issues "23||900" "21||900"; sr_row 23; sr_row 21
echo "claude/stale-u1" > "$SR/pr-heads"
got=$(sr_is list)
check "an open PR on the remote lane's OWN branch keeps its claim, old tip and all" \
      sr_notin 'territory row `lane.stalecloud`'
check "  (control: the dead local lane in the same fixture is still reported)" \
      sr_in 'territory row `lane.deadlocal`'

sr_reset
sr_board "$SRT" "stalecloud|23|claude/stale-u1"
sr_issues "23||900"; sr_row 23
echo "lane/stalecloud" > "$SR/pr-heads"
got=$(sr_is list)
check "  while an open PR on lane/<name> does not: that is not its branch" \
      sr_in 'territory row `lane.stalecloud`'

# A TIP THAT CANNOT BE READ IS NOT AN OLD TIP. The branch may be on a fork, or
# on no remote this host can reach. "Cannot tell" must not be answered by
# handing the claim to the board -- the cost of being wrong that way is two
# agents on one branch, and the cost of the other way is one file held a day
# too long.
sr_reset
sr_board "$SRT" "ghostbranch|24|claude/never-pushed" "deadlocal|21|"
sr_issues "24||900" "21||900"; sr_row 24; sr_row 21
got=$(sr_is list)
check "a remote branch this origin does not carry is \"cannot tell\", not \"dead\"" \
      sr_notin 'territory row `lane.ghostbranch`'
check "  (control: the dead local lane in the same fixture is still reported)" \
      sr_in 'territory row `lane.deadlocal`'
check "  and the report says the tip was unreadable rather than going quiet about it" \
      sr_in 'tip unreadable here'

# A `lane:` LABEL FOR A REMOTE LANE WITH NO ROW. The label shape asks
# lane_exists (unit, row, or PR) and its message used to hardcode
# "no open PR on lane/<name>", which is the wrong branch to have looked at.
sr_reset
sr_board "$SRT" "livecloud|22|claude/live-u1"
sr_issues "25|lane:livecloud|900"; sr_row 25
got=$(sr_is list)
check "a \`lane:\` label naming a live remote lane is not an orphaned label" \
      sr_notin 'label `lane:livecloud`'

# ==================================================================== part 2
# THE SECOND MUTANT: the map is not the board's. remote_authoritative is rc 0
# ONLY for a board read; a fold-lagged in-tree copy is exactly the copy missing
# a `remote` marker the board has just written, so trusting it reproduces this
# whole defect with no symptom. The sweep must act on NOTHING -- and "nothing"
# must not be spelt "Nothing stuck", which is a verdict it has not earned.
#
# THE POSITIVE CONTROL RUNS FIRST, on the same fixture: without it, every
# check below is satisfied by a sweep that has simply stopped working.
sr_reset
sr_board "$SRT" "deadlocal|21|"
sr_issues "21||900"; sr_row 21
got=$(sr_is list)
check "(control) with the board readable, this fixture IS a finding" \
      sr_in 'territory row `lane.deadlocal`'

echo "findings nobody has read yet" > "$SR/work/board/issue-sweep.findings"
got=$( ( export PATH="$SR/ibin:$PATH" HAKUX_WORK="$SR/work" HAKUX_REPO_DIR="$SR/repo" \
                HAKUX_TERRITORY="$SR/nosuch.toml"
         bash "$SRT/jobs/issue-sweep.sh" 2>&1 ) )
check "MUTANT: an unreadable board map makes the issue sweep report no class at all" \
      sr_no_heading
check "  and it does not say \"Nothing stuck\" either -- it established nothing" \
      sr_notin "Nothing stuck"
check "  it names the source it got, so the refusal is diagnosable" \
      sr_in 'came back `unreadable`'
check "  and the one command that cures it" sr_in "git fetch origin board"
check "  and it leaves the unread findings alone" sr_findings_intact

# AND THE FOLD-LAGGED READ, WHICH IS THE ONE THAT LOOKS LIKE A SUCCESS.
# board_files.load() falls back to the in-tree copy and RETURNS IT, so this
# state is indistinguishable from a clean board read through `remote_readable`.
got=$( ( export PATH="$SR/ibin:$PATH" HAKUX_WORK="$SR/work" HAKUX_REPO_DIR="$SR/repo" \
                HAKUX_BOARD_REF=refs/nosuch
         bash "$SRT/jobs/issue-sweep.sh" list 2>&1 ) )
check "MUTANT: a read that fell back to the in-tree copy refuses the tick too" \
      sr_no_heading
check "  and says \`worktree\`, not \`board\` -- the states are three, not two" \
      sr_in 'came back `worktree`'

# ==================================================================== part 3
# pr-sweep.sh: the empty lane name, and where a remote lane's draft is routed.
sr_reset
sr_board "$SRP" "cloudy||claude/live-u1"
sr_pr 301 claude/live-u1 true "" 90000
sr_ps >/dev/null
check "a remote lane's draft never reaches handback.sh at all" sr_unasked "handback.sh"
check "  and is not called a strand: there is no unit for it to be missing" \
      sr_unsaid "[job.pr-sweep] this PR is a draft and"
check "  it is told its own routine is the only actor" \
      sr_said "only actor for this PR is your own routine"
check "  by the lane name the BOARD gave the branch, not by a prefix" \
      sr_said 'lane.cloudy'
check "  and says out loud that nothing local may resume it" \
      sr_said "nothing local will resume it"
check "  while still not marking the PR ready" sr_said "nothing here marks a PR ready"

# THE CONTROL, in the shape that matters: an ordinary lane/* draft must still
# go to the actor that owns it. The target is narrowed, never widened.
sr_reset
sr_board "$SRP"
sr_pr 302 lane/localdraft true "" 90000
sr_ps >/dev/null
check "(control) an ordinary lane/* draft still asks handback.sh" sr_asked "handback.sh list"
check "(control) and is still reported as a strand" \
      sr_said "[job.pr-sweep] this PR is a draft and"

# THE OTHER EMPTY-LANE SITE. `regressed` was guarded on `and lane`, so a
# `claude/*` head fell out of class 5 entirely: the label could disagree with
# every verdict on disk forever and this sweep would never ask.
sr_reset
sr_board "$SRP" "cloudy||claude/live-u1"
sr_pr 303 claude/live-u1 false regressed 9000
echo "STATE=regressed" > "$SR/arms.state"
sr_ps >/dev/null
check "a \`regressed\` PR on a remote lane's head is classified at all now" \
      sr_said "still recomputes"
check "  and arms.sh was asked about the branch, which is what it keys on" \
      sr_asked "arms.sh state claude/live-u1"

# NARROW. A `claude/*` head that NO territory row names is still not a lane --
# an interactive session's branch, a person's. It is neither class.
sr_reset
sr_board "$SRP"
sr_pr 304 claude/somebodys-branch true "" 90000
got=$(sr_ps list)
check "a claude/* head no territory row names is not a remote lane" sr_notin "remote-draft"
check "  and is not a strand either: there is no lane to strand" sr_notin "draft-strand"

# THE SECOND MUTANT AGAIN, on the sweep that takes OUTWARD actions. pr-sweep
# runs `cloud.sh finish` and comments on PRs unattended every three hours, and
# both are keyed on which lane a head belongs to.
sr_reset
sr_board "$SRP"
sr_pr 305 lane/orphan false claimed:cloud 90000
echo "[job.cloud] claimed for audit1 (unit hakux-lane-cloud-audit1-305, model x, attempt 1 of 4)." > "$SR/claim.body"
sr_ps >/dev/null
check "(control) with the board readable, the orphaned claim IS repaired" \
      sr_asked "cloud.sh finish audit1 305"

sr_reset
sr_board "$SRP"
sr_pr 305 lane/orphan false claimed:cloud 90000
echo "[job.cloud] claimed for audit1 (unit hakux-lane-cloud-audit1-305, model x, attempt 1 of 4)." > "$SR/claim.body"
got=$( ( export PATH="$SR/pbin:$PATH" HAKUX_WORK="$SR/work" HAKUX_REPO_DIR="$SR/repo" \
                HAKUX_TERRITORY="$SR/nosuch.toml"
         bash "$SRP/jobs/pr-sweep.sh" 2>&1 ) )
check "MUTANT: an unreadable board map makes the PR sweep repair nothing" \
      sr_unasked "cloud.sh"
check "  and comment on nothing" test ! -s "$SR/comments.log"
check "  and ask gh for the PR list at all -- it refuses before it looks" \
      sr_unasked "gh pr list"
check "  while naming the source it got and the command that cures it" \
      sr_in "git fetch origin board"

got=$( ( export PATH="$SR/pbin:$PATH" HAKUX_WORK="$SR/work" HAKUX_REPO_DIR="$SR/repo" \
                HAKUX_BOARD_REF=refs/nosuch
         bash "$SRP/jobs/pr-sweep.sh" list 2>&1 ) )
check "MUTANT: the fold-lagged in-tree read refuses the PR sweep too" \
      sr_in 'came back `worktree`'
check "  and it reports nothing stuck-shaped on the way out" sr_notin "would repair"

# ==================================================================== part 4
# THE READER ITSELF. Both sweeps load remote-lane.sh with a guard, for lane.sh's
# reason: neither has `set -e`, so a bare `.` of an absent file leaves
# remote_authoritative undefined, command-not-found does not stop the script,
# and the gate above would run to completion having checked nothing. A jobs/
# directory holding the sweep and models.env and nothing else is that mutant.
mkdir -p "$SR/nohelper/jobs"
cp "$HERE/issue-sweep.sh" "$HERE/pr-sweep.sh" "$SR/nohelper/jobs/"
cp "$HERE/localtime.sh" "$HERE/localtime.py" "$HERE/models.env" "$SR/nohelper/jobs/" 2>/dev/null
got=$( ( export PATH="$SR/ibin:$PATH" HAKUX_WORK="$SR/work"
         bash "$SR/nohelper/jobs/issue-sweep.sh" list 2>&1 ) )
check "MUTANT: issue-sweep refuses outright when remote-lane.sh is not there to load" \
      sr_in "could not load"
check "  and reports no class on the way out" sr_no_heading
got=$( ( export PATH="$SR/pbin:$PATH" HAKUX_WORK="$SR/work"
         bash "$SR/nohelper/jobs/pr-sweep.sh" list 2>&1 ) )
check "MUTANT: pr-sweep refuses outright when remote-lane.sh is not there to load" \
      sr_in "could not load"

# AND THE THING THAT STARTED THIS: both sweeps must actually name the reader.
# `grep -c remote-lane issue-sweep.sh` was 0 on 2026-09-19 while the helper had
# been folded for hours, which is the defect in its most compressed form.
check "issue-sweep.sh sources remote-lane.sh" grep -q 'remote-lane.sh' "$HERE/issue-sweep.sh"
check "pr-sweep.sh sources remote-lane.sh"    grep -q 'remote-lane.sh' "$HERE/pr-sweep.sh"
# ANCHORED ON THE CALL, NOT ON THE WORDS: both files discuss `remote_readable`
# in their headers to say why they do NOT use it, so an unanchored grep for the
# name matches the prose that forbids it. `$(` and a line start are the two
# places a call can begin here.
check "issue-sweep decides with remote_authoritative and not remote_readable" \
      bash -c '! grep -vE "^#" "$1" | grep -qE "remote_readable"' _ "$HERE/issue-sweep.sh"
check "pr-sweep decides with remote_authoritative and not remote_readable" \
      bash -c '! grep -vE "^#" "$1" | grep -qE "remote_readable"' _ "$HERE/pr-sweep.sh"
check "issue-sweep calls remote_authoritative" \
      bash -c 'grep -vE "^#" "$1" | grep -q "remote_authoritative"' _ "$HERE/issue-sweep.sh"
check "pr-sweep calls remote_authoritative" \
      bash -c 'grep -vE "^#" "$1" | grep -q "remote_authoritative"' _ "$HERE/pr-sweep.sh"
