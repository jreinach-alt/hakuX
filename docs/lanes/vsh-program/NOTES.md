# vsh-program (lane.toolsmith, 2026-09-25)

Brief: run nxdk_vsh_tests on a handheld through `request.sh`, refuse a vsh
disc that would hang at queue time, and diff the printed values against the
console's with `vsh_score.py`. Consumers: #112 item 4, #223. PR #229.

## What changed

| file | change |
|---|---|
| `request.sh` | `--program pgraph\|vsh` (recorded as `"program"`). For vsh the disc is BUILT into a scratch file with the dispatcher's arguments and `--inspect`ed before queueing. A vsh ISO queued as pgraph is refused. |
| `make_test_iso.py` | `--program vsh` writes `vsh_tests.cnf` (one suite per line), never the pgraph JSON. The program is read off `default.xbe`, not trusted from the caller. `--inspect` prints what an image will do and exits 1 if it would not complete. |
| `run_disc.sh` | `PROGRAM=vsh`: extracts with `--manifest`, and completion is `log.txt` containing "Testing completed normally", never the duration. |
| `extract_results.py` | `listdir` also yields the FATX created time. `--manifest` writes per-file guest-clock times. |
| `dispatcher.sh` | a vsh request builds with `--program vsh`, runs with guest dir `nxdk_vsh_tests` and a 900 s timeout, then runs `vsh_score.py` instead of `score_sweep.py`. The result carries `program` (every result now does), `kind: "vsh"`, a `vsh:` disc_id prefix and vsh `runs[]` rows. `vsh_score.py` is shipped and hashed. |
| `ab_compare.py` | refuses a non-pgraph result by name, not with a KeyError on `runs[].tsv`. |
| `vsh_score.py` | new. Exact `.txt` diff per test: IDENTICAL / DIFFERS (lines shown) / MISSING / STALE / NO-REFERENCE. PNG compare as a side column. |
| `jobs/selftest.d/57-vsh-disc.sh` | 27 legs, with synthesised fixture xisos because CI has no Xbox images. |

## Four ways a vsh disc hangs, all refused at queue time

1. **No cnf** (the brief's trap). Most reachable as a vsh ISO passed as a plain
   `--base-iso`: the old dispatcher writes the pgraph JSON and no cnf.
2. **A rebooting build.** The console build (`hakux/completion-marker` c3dde45
   as built) has `ENABLE_SHUTDOWN` off, so it prints "Rebooting in 4 seconds"
   and reboots. On hakuX a reboot boots the same disc again, and the program
   reruns until the timeout (same failure as pgraph discs without
   `--shutdown-on-completion`, overnight-2026-09-12-log.md item 1). **The
   brief's ISO would have hung every run even with its cnf.** Built a shutdown
   variant of the same source, only the ending differs:
   `/home/justin/hakux-work/vsh-build/nxdk_vsh_tests-c3dde45-shutdown.iso`
   (sha256 `5eb34203102a...`, recipe in `vsh-build/build.sh`, flags
   `-DAUTORUN_IMMEDIATELY -DENABLE_PROGRESS_LOG -DENABLE_SHUTDOWN`).
3. **An unknown suite name.** `process_config()` drops unknown names and, when
   none are left, runs EVERY suite. So a typo is a full run filed as the one
   suite asked for. The suite list is closed (`VSH_SUITES`, from
   `register_suites` + the console cnfs).
4. **A serving snapshot without vsh support.** It would build the pgraph disc
   (case 1). request.sh checks `$DISPATCH_DIR/bin` for all three halves.

## Falsification

The fragment was run against origin/master 9a4cce6570 in a scratch worktree,
with only 57 present. Result: 6 passed, 20 failed. The falsifier leg fails
because the old request.sh QUEUED the cnf-less disc
(`1790322907-vshpgraph-462927.req`, no `program`, base `vsh.iso`, suites
`['ILU RCP Tests']`). The old make_test_iso.py then built that image into a
disc that the new `--inspect` refuses twice: no cnf, and pgraph JSON present.

Two mistakes on the way, so they are not repeated:
- The first fixture used the new module's constants (`m.XBE_VSH_MARK`). Under
  the old code the fixture died with AttributeError, and the falsifier leg
  "passed" because request.sh refused a file that did not exist. Fixture bytes
  are now literals, a leg asserts the fixtures exist, and the falsifier leg
  requires the refusal's REASON as well as the empty queue.
- The first scratch copy was a `git archive` tree, not a repo. request.sh then
  refused on `--ref HEAD`, which is also the wrong reason. Use a real
  `git worktree add --detach`.

Legs that pass vacuously on the old code ("program vsh ... is refused") are
pinned by their "naming ..." partner legs, which do fail on it.

Full selftest on this branch: 1171 passed, 0 failed.

## Desktop plumbing check (not a scored result)

Desktop GL binary from 09-19, `ILU RCP Tests` + `Exceptional Float` + `MAC mov`,
run by hand as desktop_channel.sh's `cmd_run` does it (script:
`/tmp/claude-1000/desk.sh`, not kept):

- disc built, cnf 90 bytes. The guest ran Exceptional Float, then started ILU RCP Tests.
- **xemu aborted**: `vsh-prog.c:383: decode_opcode: Assertion
  '!"TODO: Emulate writeable const registers"' failed`, RUN_EXIT=134 after 28 s.
  The assert is still on master and in the shared GLSL translator the Vulkan
  path also uses. Android defines no NDEBUG, so the handheld will
  probably abort the same way on RCP. (Already listed in
  investigations/sweeps/sweep-shaders.md.)
- extract with manifest: 3 files. The log has no completion marker, and
  vsh_score said so first ("this run did not finish"), then: Exceptional_Float/Float
  DIFFERS (GL prints all-zero rows where silicon has inf/-inf/nan and ±3.4e38),
  RCP and MAC mov MISSING.

So the plumbing works end to end, and the completion check correctly refused
to call a crashed run complete.

## What is left: the handheld run, which can only happen after the fold

Workers execute the SNAPSHOT of the serving tree (master), not a lane branch.
Until this PR folds and a worker re-execs, a vsh request would be built by the
old dispatcher as a pgraph disc, which is the hang. request.sh refuses exactly
that, so the handheld proof is post-fold by construction. After the fold:

```
docs/testing/request.sh --who vsh --purpose "vsh: Exceptional Float vs silicon" \
  --program vsh --base-iso /home/justin/hakux-work/vsh-build/nxdk_vsh_tests-c3dde45-shutdown.iso \
  --suites "Exceptional Float,MAC mov" --device thor --no-expect "vsh text diff vs console" --wait
docs/testing/request.sh --who vsh --purpose "vsh: ILU RCP vs silicon" \
  --program vsh --base-iso /home/justin/hakux-work/vsh-build/nxdk_vsh_tests-c3dde45-shutdown.iso \
  --suites "ILU RCP Tests" --device thor --no-expect "vsh text diff vs console" --wait
```

The two are split because the program runs suites in REGISTRATION order
(Exceptional Float before ILU RCP). If RCP aborts the emulator as it did on
desktop, the first request still completes on the log marker, and the second
records the abort as hakuX's RCP verdict. Expected handheld verdict for RCP if
the assert fires: log marker absent, IluRcpTests MISSING. Post both on #112
and #223.

## Do not repeat

- The console ISO reboots. Do not queue it for hakuX, and never judge a vsh
  run by its duration.
- `e:\nxdk_vsh_tests` persists on hdd.img across runs. A file older than
  log.txt's created time is STALE, not a result.
- log.txt persists too. A run that dies before main.cpp leaves the previous
  run's log, and every file postdates it (audit M1, remediated 2026-09-25).
  run_disc.sh keeps a per-device ledger (`VSH_LOG_LEDGER`, default
  `~/hakux-work/vsh-last-log-<label>`) of the last extracted log's created
  time. A log with the same time is the old one: run_disc.sh exits 1
  "STALE LOG", and vsh_score marks every file STALE with `log_completed`
  false. The first vsh run on a device has no record and says so in
  `staleness`. The dispatcher now records `run_disc_exit` per vsh run.
- Test FILE names are not log test names: log `Exceptional Float::ExceptionalFloat`
  writes `Exceptional_Float/Float.txt`. vsh_score keys on files.

## Attempt 2, 2026-09-25: the handheld proof is blocked on queue permission

**Why attempt 1 did not finish:** it did everything that could run before the
fold. Workers run master's snapshot, so the handheld proof could only happen
after #229 folded (`6e99456e70`) and the dispatcher re-execed (06:06:49). That
was the right place to stop, not a failure.

**What happened in attempt 2:** I reset the branch to `origin/master @
6e99456e70`. The dispatch queue was empty, `hold/` said `lifted`, and the ISO
and the console references (`stage1b` ILU_RCP_Tests, `stage2`
Exceptional_Float) are all on disk. Then the queue step failed.
**This lane session's permission mode refuses to run `docs/testing/request.sh`.**
Every form came back "This command requires approval": with `--wait` and
without, absolute path and relative path, backgrounded and not. The
session is non-interactive, so nobody can approve it. I did NOT get round the
refusal by wrapping the script in python3 or `bash -c`: a denied call is a
decision, not an obstacle.

**No handheld run exists yet.** There are no verdicts to post on #112, #223
or #233, and none are implied.

**Unblock:** grant the lane `Bash(docs/testing/request.sh:*)`, or have the
host queue these two:

```
docs/testing/request.sh --who vsh --purpose "vsh: Exceptional Float + MAC mov vs silicon" \
  --program vsh --base-iso /home/justin/hakux-work/vsh-build/nxdk_vsh_tests-c3dde45-shutdown.iso \
  --suites "Exceptional Float,MAC mov" --device thor --no-expect "vsh text diff vs console" --wait
docs/testing/request.sh --who vsh --purpose "vsh: ILU RCP vs silicon (#233)" \
  --program vsh --base-iso /home/justin/hakux-work/vsh-build/nxdk_vsh_tests-c3dde45-shutdown.iso \
  --suites "ILU RCP Tests" --device nova --no-expect "vsh text diff vs console" --wait
```

Score each with `vsh_score.py <result>/nxdk_vsh_tests --reference
.../stage2/console --reference .../stage1b/console`. Before reading any
verdict, check `log_completed` and that no row is MISSING or STALE. As of this
writing #234 is OPEN, so master still has #233's abort. If the RCP run ends
with no log marker and IluRcpTests MISSING, that confirms #233 on Android;
re-run it once #234 folds.

## Attempt 3, 2026-09-25: the handheld proof ran, and the verdicts are posted

**Why attempt 2 did not finish:** the lane's permission mode refused
`docs/testing/request.sh`, and I would not wrap the script to get round the
refusal. The host queued the four runs instead. The fix for next time is to
call the script as `bash docs/testing/request.sh`, because the allowlist
prefix is literal (hardening item 8).

| request | build | device | log marker | run_disc | verdicts |
|---|---|---|---|---|---|
| `1790344835-vsh-2413308` | `a4d2fb823b` (no #234) | thor | absent, stops at `Starting MAC mov` | 1 | Float DIFFERS, mov MISSING; logcat `fault in abort` / `pgraph_glsl_gen_vsh_prog` |
| `1790344836-vsh-2413360` | `a4d2fb823b` | nova | absent, stops at `Starting ILU RCP Tests` | 1 | RCP MISSING; same abort (#233 confirmed on Android) |
| `1790346001-vsh-2643051` | `84a67b9cf8` (has #234) | thor | `Testing completed normally` | 0 | Float **DIFFERS**, MAC mov **IDENTICAL**, 0 missing/stale |
| `1790346001-vsh-2643087` | `84a67b9cf8` | nova | `Testing completed normally` | 0 | ILU RCP **IDENTICAL**, 0 missing/stale |

The harness behaved as designed on the crashed runs. It refused to call them
complete, and it recorded MISSING rather than a match.

**Exceptional Float's zeros are not a float-handling result.** The test's
draw lambda sends `SET_VERTEX4F` with no Begin/End. Silicon runs the program
for that vertex, and c[188] = v0. hakuX only buffers the vertex
(`pgraph.c` SET_VERTEX4F), never draws it or runs the writeback (that happens
only at SET_BEGIN_END END), and the next Begin resets the buffer, so the
preset c[188]=0 is read back. Even finite ±Max reads 0. **New defect, no open
issue:** a vertex outside Begin/End does not execute the vertex program. It
is left for the board to file. #112 item 4 (`_MUL` zero, `_RCC` clamp) is
still unconfirmed.

**Scope of the IDENTICAL rows (lane.xbox's caveat, checked in the code).** From
#234 on, c[188..191] are written by `pgraph_vsh_writeback_constants`
(`pgraph.c:4289`, nv2a_vsh_emu on the CPU) at End. MAC mov and ILU RCP both
draw inside Begin/End, so both rows are that evaluator's output, not the
GLSL's. They say nothing about #223 or the GLSL RCC path.

Posted on #233, #112 and #223.

**Unexplained, not chased:** the PNG column reports nonzero pixel diffs on the
IDENTICAL rows (mov 11976 px, RCP 123498 px). The text is the verdict, and the
PNG diff has not been checked for being a font or overlay difference. Read it
before treating it as signal.

## Do not repeat (attempt 3)

- Read what drives a vsh test (Begin/End or not) before you attribute a
  DIFFERS to the arithmetic. Exceptional Float looked like a NaN/Inf finding,
  but it is a vertex-submission finding.
