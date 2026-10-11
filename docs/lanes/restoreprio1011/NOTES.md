# lane.restoreprio1011 (#433) -- promote a starved master restore from the hold path

## The premise, verified

restoreleak1009's NOTES said "every real run already sets its own ref/env
explicitly at soak start" as the reason a starved restore costs latency, not
correctness. The brief's first job was to verify that from the serve path
itself, not take it on faith.

**`docs/testing/dispatcher.sh`'s `serve_one`** (the only place a queued
request is served) does this, in this order, for EVERY request before any
branch on its kind:

- `ref=$(jq_get "$req" ref HEAD)` -- :1345. `jq_get` is `dict.get(key,
  default)` (:194), so this is the request's own `ref` if the key is
  present (even `""`), else the literal string `"HEAD"`. There is no path
  through `request.sh` that writes an empty `ref`: `request.sh:710-716`
  resolves `--ref` to a concrete sha with `git rev-parse --short`
  (`request.sh:720`) and exits 2 if it cannot (`:724`), before the request
  ever reaches `queue/`. The one caller
  that writes a literal non-sha string is `device_build.py`'s
  `restore_request`, which writes `"ref": "master"` -- not empty either.
  An empty `ref` would reach `_build_ref_locked` (:1008) and fail at
  `git rev-parse --short ""` (no commit named ""), which fails the whole
  request with `rc != 0` at :1375-1388 -- it never reaches a soak. So
  "empty ref" is not a live path; it is a hard failure, not a "run whatever
  is installed" fallback.
- `apk=$(build_ref "$ref" "$perflog")` -- :1375. Unconditional, run before
  the restore/title/suite branch at :1445. `build_ref` resolves the ref to a
  sha, serves a cached apk if one exists for that sha (:1043-1044) or builds
  one (:1045 on). Either way it names a concrete apk for THIS request's ref.
- `adb_call ... install -r "$apk"` -- :1410. Unconditional, after the build,
  before any branch. `adb install -r` always reinstalls, even over the
  identical apk -- there is no "skip install, keep what's there" path. A
  failure here ends the request (:1410-1413) rather than falling through to
  run on the previous apk.
- `apply_env_pref "$req"` -- :1425. Unconditional, after the install, before
  any branch. On a request with no `env` and no stale marker this costs
  zero `adb` calls (per its own comment at :241-246), but it is still CALLED
  for every request, and it clears a previous request's env if one was left.
- `restore_hdd_pref` -- :1433. Unconditional too, before the branch.

Only AFTER all four of the above does `serve_one` branch:
- a `requester == dispatch.restore` request ends here (:1445-1458) -- the
  comment at :1439-1444 says explicitly: "THE MASTER RESTORE ENDS HERE
  ... Its build, install and env reset above are the whole job."
- a request with a `title` runs `soak_title.sh` (:1468 on).
- a request with `suites` runs the disc path (:1605 on, the "NO SUITES"
  refusal at :1615 for a request with neither a title nor suites).

I read the title path (:1468-1604) and the first part of the suites path
(:1605-1620, where it reads `suites.txt`/`skip_tests.txt`) looking for a
branch that skips the build/install/env block above and found none -- both
begin only after :1445's restore exit, i.e. only after the four
unconditional steps already ran.

**Conclusion: every served request installs its own apk and writes its own
env (or explicitly clears a stale one) before any soak or disc starts.
There is no path that runs whatever happens to be installed already.**
So a starved `dispatch.restore` costs a SERVED measurement nothing -- the
next real request overwrites the device's state regardless of what the
restore would have put there. This is premise 2a, not 2b: the restore only
matters to a caller who takes a hold and runs something BY HAND on whatever
state the hold leaves installed -- `jobs/hold.sh`'s build gate is exactly
that caller.

## The fix

`jobs/hold.sh`'s `build_gate` (:191-215 after this change) already refuses
`take`/`wait` with exit 4 when `device_build.py check` says the device's
newest run was off master. It now also calls a new `device_build.py
promote <dispatch_dir> <label>` on that refusal, which:

- renames the label's pending `dispatch.restore` request (bare id) to a
  `0-`-prefixed name via a tmp file + `os.replace` (atomic on the same
  filesystem, the python equivalent of "temp file, then mv"), so the
  dispatcher's own ASCII-ordered `queue/*.req` serve loop reaches it ahead
  of any `1-`-prefixed release-tier stream;
- or, if none is pending (and none is already `running/`), queues one with
  the existing `restore_request()` (unchanged -- still writes a bare id)
  and immediately promotes that file the same way.

`take` keeps its exit 4 on refusal (the brief: "Keep exit 4, so a caller
that reads the exit code still knows it holds nothing") -- it promotes as a
side effect but does not wait. `wait` now loops on `build_gate` itself
(instead of exiting at once on the first refusal) until the gate passes or
its own timeout expires, since the restore it just promoted takes about
60 s to be served.

`restore_request()` itself is untouched -- it still writes a bare id, so
the dispatcher's own post-run hook (`queue_master_restore`, called with no
hold or human involved) keeps queuing bare, unprioritized restores that
wait their normal turn. Only a caller stuck behind a refused hold gets the
`0-` treatment, and only for its own device's restore.

## Why not promote on every off-master run (hostops' original proposal)

Hostops proposed giving `restore_request`'s own id a `0-` prefix
unconditionally. Given the premise above -- no served request reads
whatever is already installed -- that would spend a 60 s restore after
every off-master run (every fastpaths OFF arm, every coldstart env arm,
every fold gate) for a benefit that provably does not exist: nothing
downstream ever starts "on the build the restore would have put there"
instead of installing its own. The cost (~25% more Nova time on a night of
short arms, per the brief) buys nothing. Gating the promotion behind an
actual hold-taker's need -- the only caller that can be affected by what is
installed -- gets the same "never starves forever" property for free,
without touching the steady state of served measurements at all.

## Selftest

`docs/testing/jobs/selftest.d/99-restore-priority.sh` (new): legs (a)-(d)
per the brief, plus a mutant (device_build.py's `_promote` rename
disabled) that turns leg (a) red -- the bare request given to `promote`
stays bare and never gets the `0-` prefix.

`docs/testing/jobs/selftest.d/99-build-gate.sh`: leg (b)'s `wait` case no
longer refuses "at once" (renamed the check accordingly) since `wait` now
polls the gate until its own timeout; added a cleanup line after legs
(b)/(c) so the restore their refused `take`/`wait` calls promote as a side
effect does not leak into (f)-(l)'s own restore-queueing counts. Updated
the two call-site mutant checks (`grep -c 'build_gate "$label" ||'` ->
`grep -c 'build_gate "$label"'`, matching both `take`'s `|| exit $?` and
`wait`'s new `&& break`) and its mutant generator (two `sed` substitutions
now, one per call site).

`docs/testing/jobs/selftest.d/99-hold-take.sh`: unaffected. Its fixture
dispatch dir has no `results/` tree at all, so `device_build.py check`
always answers "no run recorded on this device" (release) for every
`take`/`wait` call in that file -- `build_gate` never refuses there, so
`promote` is never invoked. Confirmed by running it unmodified: 45 passed,
0 failed.

Ran `SELFTEST_ONLY="99-build-gate.sh 99-restore-priority.sh 99-hold-take.sh"
bash docs/testing/jobs/selftest.sh` in the foreground: 111 passed, 0
failed, PARTIAL (3 of 134 fragments, as expected for a named subset).

## Not done here

- `docs/testing/request.sh` and `docs/testing/dispatcher.sh` are read-only
  in this lane (per brief); no change needed there since the fix lives
  entirely in `hold.sh`'s gate and `device_build.py`'s new `promote`
  command.
- The idlewatch patch (outside this repo) is written out in PR.md for
  lane.local to apply at fold, not applied here.
