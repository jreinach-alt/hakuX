# crashattr -- whose crash a title verdict counts

Harness defect, no issue (dispatched directly). Brief: `briefs/crashattr.md`.

## The defect

`title_verdict.py`'s `crash_lines` counted every `F/libc` and `F/DEBUG` line in
the logcat. Those tags belong to the whole device: crash_dump logs a tombstone
under `DEBUG` for any native crash. Three Nova runs on 2026-10-02 were scored
`crash: true` because Android's own `media.extractor` aborted
(`MPEG4Extractor.cpp:1991 CHECK_EQ`) while hakuX kept playing:
`1790951866-titleroutes2-46925` (4 tombstones), `1790951914-titleroutes2-68595`
(1) and `1790953776-titleroutes2-447685` (3). `0-0-x-1790465684-lane.remote-2069760`
(09-26) did the same for `surfaceflinger`.

## The brief's mechanism would have missed every real hakuX crash on disk

The brief said to keep a libc line only when its text names hakuX
(`Fatal signal N ... pid N (name)`). I scanned all 965 `dispatch/results/*/logcat.txt`.
No hakuX crash has ever produced a tombstone or a `Fatal signal` line. The
reason is that hakuX's handler (`android_crash_handler.cpp`) logs under `hakuX`
and then re-raises under `SIG_DFL`, so bionic's debuggerd never runs. What a
real hakuX native crash leaves is a nameless libc line from the crashing pid:

- `FORTIFY: pthread_mutex_lock called on a destroyed mutex (...)`
- `exiting due to SIG_DFL handler for signal 11, ...`

That is 9 runs (the 09-29 memfast, ibcache and verdict433 titles-disk crashes).
None of them has `guest exited` in run.log, so the libc line is the only thing
that makes them `crash: true`. A name-only check would have scored all nine
`crash: false`.

## The fix (`docs/lanes/crashattr/crashattr.diff`)

A line counts as hakuX's in three cases:

- **Tombstone:** the block from one `*** ***` line to the next counts if its
  `Cmdline:` names a hakuX process. Without a `Cmdline:` line, the
  `>>> name <<<` line is used. crash_dump logs under its own pid, so a
  tombstone is judged by name, never by pid.
- **libc line, by pid:** it counts if its pid also logs hakuX's own tags
  (`hakuX*`, `xemu*`). `hakuX-route` is excluded because route.sh and
  soak_title.sh write it from an adb shell. In all 9 real crashes the libc
  pid also logs hakuX's tags. The surfaceflinger pid and the media.extractor
  pids never do.
- **libc line, by name:** it also counts if its `pid N (name)` is a hakuX
  process. That name is `/proc/<pid>/comm`, which keeps only the last 15
  characters, e.g. `nach.hakux:xemu`.

The hakuX process names are the package plus `.debug`/`.debug2`, each with or
without `:xemu` (`build.gradle.kts`, `AndroidManifest.xml`). A tombstone that
names no process, such as a capture that opens mid-block, does not count.

`parse_logcat` takes an optional `pids` list that it fills in step with the
lines, so the `(t, level, tag, msg)` tuple every caller unpacks is unchanged.
`hakuX-crash` handling and `crash_warn` are unchanged.

## Measured (`falsify.py`, old vs new `judge()`, real result dirs)

| set | runs | old crash | new hakuX crash lines |
|---|---|---|---|
| media.extractor bystanders (10-02) | 3 | true x3 | 0, 0, 0 -> crash false |
| surfaceflinger bystander (09-26) | 1 | true | 0 (crash stays true: run.log `guest exited after 214s` -- the framework restart killed hakuX) |
| real hakuX libc crashes (09-29) | 9 | true x9 | 1-2 each -> crash true |
| hakuX-crash BugCheck runs | 2 | true x2 | 10 each -> crash true |
| twin of each bystander, the process renamed to `com.jreinach.hakux[:xemu]`, `.debug:xemu`, `.debug2:xemu`, comm `akux.debug:xemu` | 4 | true | 188 / 48 / 144 / 1 -> crash true |

0 of 19 rows wrong. Across all 965 result dirs, old and new crash lines differ
in exactly those four bystander runs.

**The three 10-02 runs still fail without the crash.** ToeJam (46925) and Tron
(447685) fail on duration (299 s and 232 s of gameplay, under the 600 s
screening bar). Tron (68595) fails on `reached_gameplay: unconfirmed (generic
route)`. The fix removes a false reason; it does not make any of them Playable.

Selftest `89-title-verdict.sh` gets four fixtures (`bystander`, `owntomb`,
`ownlibc`, `ownfatal`) and five mutants, each caught by its own fixture. Run in
a scratch worktree with the patch applied, `SELFTEST_ONLY=89-title-verdict`
gave 114 passed, 0 failed. `99-hitch-report` and `66-status-titles` (the other
`title_verdict` importers) gave 30 passed, 0 failed. Against the unpatched
classifier, the new `bystander` fixture fails
(`crash=True ... libmediandk.so`).

The full `jobs/selftest.sh` on that scratch tree (2026-10-02 09:05-10:05 PDT)
ran all 120 fragments with 0 failed: 97 in a first run that hit its 50-minute
timeout (2582 ok), then the other 23 (361 passed).

## Territory (why the patch is not applied yet)

`docs/testing/title_verdict.py` is in `[lane.routedriver2]`'s row. That lane's
branch (`80f8dd317c`) has no diff in that file or in `89-title-verdict.sh`.
`89-title-verdict.sh` is in `[free]`. My row has no files. On 2026-10-02
08:5x PDT I wrote a board request (`board-requests/crashattr.md`) for all
three paths. Once they are granted:
`git apply docs/lanes/crashattr/crashattr.diff`, then rerun `falsify.py` and
the fragment, commit, push, and set `State: ready`.

## Waiting (2026-10-02 11:02 PDT)

`[lane.crashattr]` is waiting on a territory grant for `docs/lanes/crashattr/**`,
`89-title-verdict.sh` ([free]) and `title_verdict.py` ([lane.routedriver2]).
I polled origin/board from 08:57 to 11:01 PDT with no change and no reply in
`board-requests/crashattr.md`. hostops was active the whole time (board edits
at 09:04-10:32), and at 10:32 the owner ordered it rebuilt as a model-free ops
layer (`[lane.opsrebuild]`). The follow-up request asks whoever grants the
paths to also run `lane.sh resume crashattr`, because nothing offline resumes
a lane on a territory change.

**On resume, in order:**
1. Confirm the grant: all three paths are in `[lane.crashattr].files` on
   origin/board.
2. `git merge origin/master`.
3. `git show origin/master:docs/testing/title_verdict.py > docs/lanes/crashattr/work/old_tv.py`
4. `git apply docs/lanes/crashattr/crashattr.diff`. If master moved
   title_verdict.py, use `git apply -3`.
5. `python3 docs/lanes/crashattr/falsify.py docs/testing/title_verdict.py docs/lanes/crashattr/work/old_tv.py`
   must give 0 of 19 rows wrong.
6. `SELFTEST_ONLY=89-title-verdict bash docs/testing/jobs/selftest.sh`, then
   `docs/testing/preflight.sh --allow-tracker`.
7. Commit and push both files. Delete `crashattr.diff`, since it is applied.
   Set PR.md `State: ready`, update its `Files:` line to match
   `git diff --stat origin/master...HEAD`, and add a line to OUTBOX.md.

## For the next lane

- Do not key hakuX crash identity on a process name alone. hakuX's own
  crashes never reach debuggerd (`SIG_DFL` re-raise). Pid identity is what
  catches them.
- Nova's media.extractor crashes every ~2 min on something in its storage.
  That is a device-hygiene item for hostops, not this classifier.
