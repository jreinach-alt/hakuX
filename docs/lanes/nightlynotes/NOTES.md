# lane.nightlynotes

Two things: the release notes that reported the harness instead of the
emulator, and the 78-second nightly the brief asked me to check.

## 0. Why attempt 1 did not finish, and what attempt 2 did

Attempt 1 finished the work. It did not finish the *lane*: the PR was open,
green and marked ready at `4293c8ffb0`, and then `master` moved 62 commits
underneath it and `8613ae0ae1` ("harness: show Pacific to the reader, keep
UTC in the data") edited `nightly_build.sh` in exactly the region this lane
rewrote. fold.sh could not merge, labelled the PR `needs-rebase`, and handed
it back. Nothing was wrong with the work; the merge base moved. Sections 1
and 2 below are attempt 1's and stand unchanged.

Attempt 2 is the merge, and nothing else. See §3.

## 1. The notes

### What was wrong

`docs/testing/nightly_build.sh:47`, as it stood at `6ca12eb803`:

```bash
mapfile -t SUBJECTS < <(git log --since="$SINCE" --format='- %s' | head -40)
```

`git log` is reverse-chronological. `head -40` is therefore not a sample of
the day, it is the most recent forty commits, whatever churned last. The
harness folds on a 30-minute timer, so on any busy day the last forty commits
before 00:30 are folds and fold-adjacent harness work, and the emulator work
-- the point of the project -- falls into the `_…and N more commits._` tail.

### The measurement, re-derived

The brief quoted 40 listed / 0 emulator / 29 emulator in window / 259 total.
I re-derived it rather than reusing it, and the three numbers do not all
reproduce, because **the window's contents depend on when you ask**. Folds
rewrite nothing, but a lane branch whose commits carry committer dates inside
the window folds *after* 00:30 and joins the window retroactively. So:

| source | total | emulator | listed | emulator listed |
|---|---|---|---|---|
| the nightly's own log, at 00:30 | 239 | — | 40 | — |
| brief | 259 | 29 | 40 | **0** |
| `origin/master` reconstructed with `--until 00:30`, measured 06:40 | 310 | 33 | 40 | **0** |
| same window, no `--until`, measured 06:40 | 400 | 37 | 40 | **0** |

The count of emulator commits moves with the observation time. The thing that
does not move, on every reconstruction, is the one that matters: **0 of the
40 listed commits touched `hw/ target/ accel/ ui/ audio/`.** That is the
defect, and it is time-invariant. Do not treat any single total in this table
as *the* number; cite the invariant instead.

### What I built

`nightly_build.sh` now classifies each commit in the window by area in a
single `git log` pass and prints three capped sections:

- **Emulator** -- `hw/ target/ accel/ ui/ audio/`, cap 60. A commit touching
  both sides counts here; that is the side a reader cares about.
- **Harness and tooling** -- `docs/testing/ .github/`, cap 8.
- **Docs and the rest** -- cap 8.

Each section that is capped says how many it left out, *in that section*, and
a footer states the three counts and the merges. Over the real 2026-09-18
window it emits all 37 emulator subjects, including
`target/i386: FIST honours the rounding mode` -- the exact commit the brief
named as the thing the notes could not show.

`--no-merges`: a `fold: PR #131 lane/x -- ...` subject describes the lane, not
the change, and every commit it folds is listed on its own anyway. Checked
what that costs before committing to it: over the real window it drops 70
merges out of 400, and **one** of those was classified emulator (fold.sh's
conflict resolutions produce merges with a diff). So the emulator section
loses at most a fold subject that named a lane, never a change. Merges are
still counted and the footer names them.

### Two things I deliberately did not do

- **No grep over `nightly_build.sh`'s source in the selftest.** The file's
  own comment quotes the line it replaced, so any grep for the old
  truncation matches the explanation of why it is gone. The checks are
  behavioural only.
- **The emulator post-condition warns, it does not exit.** A nightly with
  imperfect notes still beats no nightly. The warning lands in `$LOG`, which
  is the file the owner reads when something looks wrong.

### The falsification -- run against the genuine old file, not a paraphrase

The brief asks that the new check fail against the code it replaces. I ran it
two ways.

**End to end, against the real pre-change file.** `git show
origin/master:docs/testing/nightly_build.sh` (sha256 `7f4792b991b29972`,
truncation at line 47) into a temp dir, `NIGHTLY_TREE` pointed at a fixture
whose tip is 45 harness commits over 3 emulator commits, with `android/gradlew`
and `gh` stubbed so it reaches its notes block. Never at the real path.

```
old file, exit 0:  40 subjects listed, emulator subjects named: 0
                   has "### Emulator" section: NO
                   tail: "_…and 9 more commits._"   <- all 3 emulator commits were in there
new file, same fixture: emulator subjects named: 3, all of them
```

**Permanently, in the selftest.** `selftest.d/86-nightly-notes.sh` builds the
same shape and runs the replaced two statements verbatim over it, requiring
that `emu_section_names_the_work` FAILS on their output and passes on the new
output. Both legs are asserted, so a check that had become vacuous would show
up as the second leg going green for free.

The negation is a shell **function**, not `bash -c '! ...'`. A function is not
exported into a child shell, so the negated form there succeeds against
anything at all, including a missing file.

### `notes` mode

`nightly_build.sh notes [SINCE]` writes the body to stdout and stops before
`./gradlew`. Both modes generate the body through the same code, so a green
selftest is a statement about what the nightly will actually publish -- not
about a reimplementation of it. It is inert by construction: it redirects
`$OUT` to a `mktemp -d` and sends progress to stderr, so a test run cannot
overwrite tonight's notes or log. The selftest asserts that
(`notes mode writes nothing into the nightly output directory`).

### A known limitation, stated rather than left to be discovered

The emulator set is exactly the five directories the brief named --
`hw/ target/ accel/ ui/ audio/` -- because those are the ones every other
brief and gate already uses, and inventing a sixth here would put the notes
out of step with them. But it is not a complete description of emulator work.
A commit touching **only** `include/` -- say `include/exec/target_page.h`, or
`include/hw/xbox/...` -- is emulator work and lands in "Docs and the rest".
Same for a change confined to `tests/` or to the meson/build files.

I did not widen it, because the right fix is to change the shared definition
in one place rather than to let this script drift from the gates. If someone
does widen it, `86-nightly-notes.sh` will not notice: no check there asserts
that `include/` is *excluded*, so adding it breaks nothing.

### For the next lane

- Don't add a source grep for `head -40` here; see above.
- If you change the section headings, `86-nightly-notes.sh` anchors on
  `^### Emulator$` and on `/^### Emulator$/,/^### Harness/` ranges. Change both.
- The caps (60/8/8) are judgement, not measurement. 37 emulator commits was
  the busiest day observed; 60 has headroom but is not a proof of anything.
- Every new invariant has a mutant that trips it. All six were run against a
  mutated copy of the script at a temp path, never the real one, and
  confirmed to fail; none of the checks is vacuous. Re-run the sweep if you
  change the classification.

  | mutant | invariant it trips |
  |---|---|
  | drop `--no-merges` | the fold subject takes no line |
  | `EMU_CAP=1` | all four emulator commits are named |
  | harness wins over emulator | a both-sides commit counts as emulator |
  | count merges as work | the tally adds up |
  | `HARN_CAP=45` | a capped section says how many it left out |
  | `EMU_CAP=0` | **the in-script post-condition warns** |

  The last one is the check the brief asked for -- "never let the emulator
  section be empty when emulator commits exist". Under `EMU_CAP=0` the script
  logs `WARNING: 4 emulator commit(s) in the window and the notes name none`,
  exits 0, and still writes the notes. That is deliberate: the warning is not
  allowed to cost the nightly.

## 2. The 78-second nightly: **real build, not a stale APK**

The brief flagged this as potentially far more serious than the notes. It is
not a defect. The evidence, from `/home/justin/hakux-work/nightly/2026-09-19.log`
and the published release:

| | |
|---|---|
| script start (`say`) | `00:30:00` |
| APK copied and hashed | `00:31:06` |
| published | `00:31:18` |
| **total** | **78 s** |
| Gradle's own verdict | `BUILD SUCCESSFUL in 1m 5s` |
| task accounting | `53 actionable tasks: 7 executed, 46 up-to-date` |
| `:app:buildCMakeRelease[arm64-v8a]` | **executed** (no `UP-TO-DATE`) |
| `:app:packageRelease` | **executed** |
| `:app:assembleRelease` | **executed** |
| APK size / asset | 24,635,435 bytes, `hakuX-0.4.0-j1-nightly-2026-09-19-bdeab36f75.apk` |
| asset uploaded | `2026-09-19T07:31:18Z` = `00:31:18` local, i.e. the same run |
| sha256 (first 16) | `4fc7d743b8cb82ff` |

The decisive lines are the task accounting and the ninja output. The log
contains real compiler diagnostics from this run -- `ninja: Entering
directory .../arm64-v8a` followed by warnings from `accel/tcg/tb-maint.c`,
`accel/tcg/cputlb.c`, `accel/tcg/translator.c`, `hw/xbox/nv2a/*.c`,
`hw/xbox/nv2a/pgraph/gl/*.c`, `hw/xbox/mcpx/apu/*.c` and others. ninja
re-emits diagnostics only for translation units it actually recompiles, so
those files were compiled at 00:30 on 2026-09-19. `packageRelease` and
`assembleRelease` are among the 7 executed tasks, not among the 46 up-to-date
ones, so the APK was packaged fresh in this run and is not a previous day's
file re-uploaded.

**So: warm incremental, and genuine.** 78 seconds is what an incremental
NDK/ninja build costs when the previous nightly left `android/app/.cxx/Release/`
populated and only the day's changed translation units need recompiling. 7 of
53 Gradle tasks executed; the other 46 were legitimately up to date.

Two things I could **not** establish, stated so nobody mistakes my silence for
a clean bill:

- I could not stat the APK on disk. Reads outside this worktree are refused in
  this session except through `Read` on a named file, and directory listing of
  `/home/justin/hakux-work/nightly/` is refused outright. The size and upload
  time above come from the GitHub release asset and the log's own `du`/`sha256sum`
  output, not from the filesystem.
- I did not verify that the compiled sources correspond to `bdeab36f75`
  specifically. The log records `head=bdeab36f75` with no unpushed-commits and
  no dirty-tree warning, so the script's own provenance check passed; I did not
  independently confirm the working tree matched that sha at 00:30.

Neither gap weakens the conclusion that a real compile and a real package
happened in that 78 seconds. Per the brief I have not changed anything about
the build path.

## 3. Attempt 2: the merge with `master`

### What conflicted, and how both sides were kept

One file, `docs/testing/nightly_build.sh`, against master's `8613ae0ae1`
("harness: show Pacific to the reader, keep UTC in the data"). The two changes
are not rivals -- that commit converts the file's *display* timestamps to the
display zone, this lane rewrites the file's *notes block* -- they simply landed
within a few lines of each other three times.

| hunk | resolution |
|---|---|
| the header | both. `localtime.sh` is sourced **above** the `notes` mktemp, because `local_day()` names the file `OUT` then holds. |
| `say()` | this lane's two arms, each stamping through master's `say_time_s`. |
| `SINCE` | this lane's `${2:-...}` override, carrying master's comment for why the bare host-local `date` there is deliberate. |
| `SINCE`/`TOTAL`/`head -40` | gone -- that trio is what this lane exists to replace. |

The `SINCE` comment is worth keeping rather than dropping as a merge artefact:
it is the one place that records why this line must *not* become a
`localtime.sh` helper. The window has to line up with `OnCalendar=00:30:00`,
which carries no `Timezone=` and so fires at 00:30 local; making it UTC would
slide the window seven hours off the boundary it names.

### One check of master's had to change, and it is not in my Files: line

`selftest.d/55-localtime.sh:136` pinned nightly_build.sh's `say()` on its
whole one-line form:

```bash
grep -q 'say() { echo "$(say_time_s) \$\*" | tee -a "\$LOG"; }' .../nightly_build.sh
```

`say()` here has two arms and cannot match that, so the merged file failed a
check it in fact satisfies. The fragment's own comment three lines above says
the four sibling checks are "pinned on the call itself -- `$(say_time_s)`
inside the `say()` body -- rather than on any word in the surrounding prose";
the grep was stricter than that sentence. I made it match the sentence, for
nightly_build.sh only -- the other four sites are still one-liners and keep
the original grep:

- `say()` stamps through `say_time_s` **in both arms** (`grep -c` = 2, so
  converting one arm back is caught, not just both);
- and the file keeps **no bare clock stamp** -- the half a positive grep
  cannot state.

Neither check is vacuous. Run against two mutants at a temp path:

| file | two-arms | no-bare-stamp |
|---|---|---|
| the merged file | PASS | PASS |
| this lane at `4293c8ffb0` (two arms, `date '+%H:%M:%S'`) | **FAIL** (0) | **FAIL** |
| `origin/master` (one arm, `say_time_s`) | **FAIL** (1) | PASS |

Each check is tripped by a mutant the other lets through, which is why it is
two checks and not one.

`docs/testing/jobs/selftest.d/55-localtime.sh` is therefore a fourth file on
this PR, added to the body's `Files:` line. It is one check in another lane's
fragment, loosened to what that fragment says it is testing; the localtime
lane's invariant is intact.

### The selftest is not green, and 10 of the 11 failures are master's

Measured, not assumed. `origin/master` at `6db8217cdb` fails its own `jobs
selftest` workflow in CI (run `35456001861`) with exactly these ten, all in
`selftest.d/86-fold-regressed.sh`, which exercises `fold.sh`:

```
FAIL   and the fold comment names the issue the trade is argued on
FAIL   it says the failing verdict still stands as measured
FAIL a bare regression-accepted does NOT fold
FAIL `regression-accepted:` is not an override
FAIL `regression-accepted:none` is not an override
FAIL `regression-accepted:91x` is not an override
FAIL `regression-accepted-later` is not an override
FAIL   the spelling is said once as well
FAIL   list stays read-only: it folds nothing
FAIL   but list folded nothing
```

This branch touches neither `fold.sh` nor that fragment, and `86-fold-` sorts
before `86-nightly-`, so nothing of this lane's has even been sourced when
they run.

On this branch at `d10af53ce4`: **520 passed, 10 failed**, and the ten are
that list, name for name and in that order. The eleventh -- the `say_time_s`
grep -- is fixed, and all eighteen checks in `86-nightly-notes.sh` plus the
two new ones in `55-localtime.sh` pass:

```
ok   nightly_build.sh's say() stamps through say_time_s, in both arms
ok   nightly_build.sh keeps no bare clock stamp
ok   THE CHECK: the notes have an Emulator section naming the buried target/i386 fix
ok   notes mode writes nothing into the nightly output directory
ok     and prints no empty Emulator section
```

**This lane adds no failure and removes none**; the fold-regressed ten are a
live defect on master and belong to whoever owns `86-fold-regressed.sh`. I did
not touch them: guessing at another lane's fold semantics from a red check is
how one lane's bug becomes two lanes' bugs.

The consequence for this PR is that its `jobs selftest` check cannot go green
while master's is red, and `fold.sh` gates on CI green -- so this is not a
condition this lane can clear from inside. See the closing note.

### A hazard that cost this attempt a full redo

At 09:50:09 and 09:50:28 something outside this session ran `git reset` in
this worktree -- twice, 19 seconds apart, both recorded in the reflog as
`reset: moving to HEAD`. The first merge resolution was uncommitted at the
time, so `MERGE_HEAD` and every resolved hunk went with it and the tree came
back clean at `4293c8ffb0` as though nothing had happened. It was silent: no
error, no output, and `git status` looked like a lane that had simply not
started.

I did not identify the actor and am not going to guess at one. What I can say
is bounded: it was not `fold.sh`, whose reset is `git -C "$WT"` with
`WT="$WORK/fold-wt"`, and nothing under `docs/testing/` contains another
`git reset`. It did not recur on the second and third selftest runs, so
"the selftest did it" is not established either -- only that the window
overlapped one.

**The working practice that survives this, and is in `AGENTS.md` already for a
different reason: commit a conflict resolution before running anything long.**
The second resolution was committed and pushed within a minute of being
finished, and the two selftest runs after that left it alone. A lane that
resolves a merge and then runs a 10-minute gate over it is holding the only
copy in the working tree for ten minutes.

### Where this PR is left

The merge is done and `master` merges into it cleanly again -- GitHub reports
`mergeable: MERGEABLE` at `d10af53ce4` -- so `needs-rebase`, which means "the
fold conflicted; bring master into the lane branch", is no longer true and
comes off. `fold-ready` goes on: this lane is finished.

What it cannot do is hand over a green head. The same ten `86-fold-regressed.sh`
failures reproduce in three independent places, with identical counts:

| run | result |
|---|---|
| `origin/master` @ `6db8217cdb`, CI run `35456001861` | the ten |
| this branch @ `d10af53ce4`, locally | 520 passed, **10 failed** |
| this branch @ `d10af53ce4`, CI run `35457071969` | 520 passed, **10 failed** |

`fold.sh` gates on CI green, so this PR will sit at `fold-ready` and wait --
which is the designed state for it, and `ci_report` comments once per
(PR, head, state), not once a tick. It will fold on the first tick after
`86-fold-regressed.sh` goes green on master. Nothing else stands in its way,
and no push to this branch can change that.
