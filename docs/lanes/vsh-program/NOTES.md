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
- Test FILE names are not log test names: log `Exceptional Float::ExceptionalFloat`
  writes `Exceptional_Float/Float.txt`. vsh_score keys on files.
