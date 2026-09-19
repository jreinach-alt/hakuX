# lane.nightlynotes

Two things: the release notes that reported the harness instead of the
emulator, and the 78-second nightly the brief asked me to check.

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

### For the next lane

- Don't add a source grep for `head -40` here; see above.
- If you change the section headings, `86-nightly-notes.sh` anchors on
  `^### Emulator$` and on `/^### Emulator$/,/^### Harness/` ranges. Change both.
- The caps (60/8/8) are judgement, not measurement. 37 emulator commits was
  the busiest day observed; 60 has headroom but is not a proof of anything.

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
