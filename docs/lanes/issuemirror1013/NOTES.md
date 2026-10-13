# lane.issuemirror1013 notes

Fixing lane.issuemirror1012's one install-blocking defect: `github_gateway.py`'s own
flock (exit 75 on contention) was treated as a hard failure everywhere in the staged
`issue_mirror.py.new`, and the gateway's day-cap refusal (rc 1, "REFUSED: N GitHub reads
today") was indistinguishable from a real crash. Full writeup is in `PR.md`; this file is
what the next lane touching this code should not have to re-derive.

## What I did

- Copied round-1's staged files from `/home/justin/hakuX/docs/lanes/issuemirror1012/`
  into `/home/justin/hakux-work/lanes/issuemirror1013/` and edited the copies there, per
  the brief. `github_gateway.py.new` was rebased onto the *live* gateway file (which
  already has `MAX_READS_DAY=1200`, lane.local's direct edit), not round-1's stale
  600-cap version -- round-1's stale copy is kept alongside as
  `github_gateway.py.new.OLDBASE` for reference only, not copied into this PR.
- Added one shared helper, `_run_gateway()`, that every gateway subprocess call in
  `issue_mirror.py.new` now goes through. Retries only on rc 75 (5/10/20/40/60s backoff,
  ~135s bound), because that's the one code `github_gateway.py main()` returns *before*
  doing anything -- the flock is the very first thing it takes, right after checking the
  subcommand name. Recognizes the gateway's own day-cap refusal text (two regexes, built
  from the live gateway's exact strings) and raises immediately with no retry at all.
- `GatewayBusy`/`GatewayCapRefused` are plain `Exception` subclasses, not
  `RuntimeError` -- checked every `except (MirrorStop, RuntimeError)` in the file (there
  are 7 bare/broad excepts total; only `GH.reachable()`'s catch-all needed an explicit
  re-raise added) to make sure these two pass through untouched rather than being
  swallowed as "one pair's failure" deep in a sync/backfill loop.
- `cmd_sync`/`cmd_backfill` each catch the two exceptions next to their existing
  `except StateLockHeld:`, so the existing direct-call test style
  (`silent(im.cmd_sync, gh, fg, True)`) still works unchanged. `main()` wraps every
  dispatch in the same catch as a backstop for the commands that don't take
  `state_lock()` (`plan`/`mirror-down`'s own path/`new`/`check`/`close-pr` -- actually
  `mirror-down` *does* take `state_lock()`; the backstop matters for `plan`, `new`,
  `check`, `close-pr`, none of which have their own catch).
- `github_gateway.py.new`: added `cmd_budget()` (unchanged logic from round-1) and moved
  its dispatch in `main()` to before the flock, with a comment on why (`.gateway-state.json`
  is always written via `os.replace()`, so a reader is never torn) and a note that
  `status` could move the same way but wasn't touched this round.
- `hourly_report.sh.new`: split the one combined ALARM check into a staleness check and
  an exit-code check, with exit 76 getting its own named line instead of falling into the
  generic "exit code neither 0 nor 75" one.
- Four new selftests (see `PR.md` for the list and reasoning) using the existing
  `im.subprocess.run = <fake>` pattern from `github_gateway_selftest.py` -- had to add a
  local `_FakeCompletedProcess` class to `issue_mirror_selftest.py.new` (the live file
  predates round-1 and never needed one).

## What tripped me up, for the next lane

- **`GH._get_raw()` and `GH.create()` aren't safe test subjects for a "fake returns busy
  then succeeds" test.** They write their gateway's stdout to a real file
  (`H + '/.issue-mirror-get-N.json'`, or parse `CREATED #N` and then still expect
  `--out`-style side effects elsewhere) and then `open()` it back -- a fake `subprocess.run`
  that doesn't actually create that file makes the *success* path blow up with
  `FileNotFoundError`, which has nothing to do with the retry logic under test. Use
  `GH.budget_remaining()` (parses `r.stdout` directly, no file) for a "read" test subject,
  and `GH.comment()` (same, parses `COMMENTED #N comment (\d+)` from stdout) for a
  "write" one. This only matters for the *succeeds-eventually* tests -- the
  *always-busy* test is fine with any gateway call, since `_run_gateway` raises before
  ever returning control to the caller, so the file is never touched.
- **`importlib.util.spec_from_file_location` can't infer a loader from a `.new`
  extension.** It returns a spec with `spec.loader is None`, and `spec.loader.exec_module(...)`
  then fails with a confusing `AttributeError: 'NoneType' object has no attribute
  'loader'`-shaped error (actually `'exec_module'`, but same idea). Pass an explicit
  `importlib.machinery.SourceFileLoader(name, path)` as the `loader=` kwarg.
- **The live `host-tools/issue_mirror_selftest.py` and `issue_mirror_rehearsal.py` are
  NOT what you'd guess from round-1's PR alone.** `issue_mirror_rehearsal.py` is already
  live, byte-identical to round-1's staged copy (round-1 never changed it, so installing
  it is a no-op -- don't bother copying it again). `issue_mirror_selftest.py` is live too,
  but it's the *pre-round-1* version (24 tests) -- round-1's staged copy (29 tests) and
  this round's (33) were never installed. Diff against the live file, not against
  round-1's `.new`, or the diff will look emptier than it should and hide round-1's own
  changes.
- Never ran `issue_mirror.py` or `github_gateway.py` against anything live -- every test
  ran from a scratch dir (`/tmp/issuemirror1013-test-run/`) with `issue_mirror.py.new`
  copied in as plain `issue_mirror.py` purely so Python's `import issue_mirror` could find
  it; `host-tools/` was never written to. The rehearsal ran from its existing cached
  snapshot (`/tmp/claude-1000/.../issuesync1012-rehearsal-snapshot.json`), no
  `--refresh-snapshot`, so it cost 0 live reads.

## Left for lane.local

Install steps are in `PR.md`, in order, with the one thing that changed from round-1's
steps called out (skip `issue_mirror_rehearsal.py.new`, it's already live and unchanged).
Nothing else needs a decision -- this closes the one defect lane.local found, and finds no
second one.
