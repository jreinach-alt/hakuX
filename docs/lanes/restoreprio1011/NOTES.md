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

## Why attempt 1 did not finish (addendum 1, resumed 10-11)

The first attempt wrote the premise, the promote command, and the gate-side
fix above, marked PR.md `State: ready`, and stopped there -- before
lane.local's addendum 1 review caught a race in the `wait` loop it added.
Everything in this file up to here is attempt 1's work and stands; this
section and the fix below are the resumed attempt.

**The race.** `dispatcher.sh`'s claim loop checks `hold/<label>` only at
the top of its tick, before it reads the queue (`dispatcher.sh:2354`,
comment at :2352-2353: "a hold placed mid-run takes effect after the
current request rather than interrupting it"). So the instant the promoted
restore finishes, nothing stops the dispatcher from claiming the very next
`1-` release-tier request in the same tick -- seconds before attempt 1's
`wait` loop polls again. That poll calls `build_gate`, which asks
`device_build.py check` for the device's NEWEST result.json; the restore
that just finished is still the newest result (the new arm has not
finished and written one yet), so the gate reads "on master" and passes.
`wait` then takes the hold while an off-master arm is running RIGHT NOW --
exactly the state `HOLD_RELEASE_LABELS` exists to prevent, and worse than
attempt 1's refusal: before this fix a stuck caller was at least refused
honestly.

**The fix: ask what is running, not only what last finished.** New
`device_build.py running <dispatch_dir> <label>` (device_build.py:191-207
in this revision) answers from `running/*.req` (the same files
`_restore_path` already read for `promote`'s "already running" case) with
one of three exit codes: 0 "restore: <id>" (the label's own restore is
running now), 1 "other: <id>" (something else is), 2 "none" (nothing is).
`hold.sh`'s `wait` loop (only for a gated label -- `label_gated`, the same
membership check `build_gate` already did, extracted so `wait` can ask it
too without duplicating the case pattern) now asks this before trusting a
gate pass:

- **running: a restore** -- take the hold now, before it finishes. The
  dispatcher's claim loop stops right after it (the hold is now in place
  for its next tick), and the device is left on master. `cmd_promote`
  already special-cased this ("already running:"); this is the same
  check, used by `wait` instead of only by a human reading `promote`'s
  stdout.
- **running: something else** -- do NOT call `build_gate` at all this
  iteration (it would read the stale newest-result pass incorrectly, per
  the race above). Keep polling. That run finishing off master is exactly
  what `queue_master_restore` (the dispatcher's own post-run hook, run
  with no hold or human involved) queues a fresh bare restore for; the
  next iteration's refusal promotes it, and the "running: a restore" case
  above then catches it.
- **running: nothing** -- `build_gate`'s answer is current (nothing
  finished between the check and now that it would miss); act on it as
  attempt 1 did.

For an ungated label (anything but `nova` today -- the Thor's screening
runs vary env on purpose and must not be slowed by this), `label_gated`
short-circuits `wait`'s loop straight to `build_gate`, which itself
short-circuits to pass, exactly as before this addendum. Without that
guard, calling `device_build.py running` unconditionally would make
`wait thor ...` block on the Thor's normal running arms (which are
routinely "other", by design) -- a regression `99-hold-take.sh`'s leg (f)
happens not to catch only because its fixture's `running/` holds `.owner`
marker files, not the `.req` files `device_build.py running` globs for;
real production `running/` holds both for a live claim. Confirmed by
reading `_restore_path`'s glob (`running/*.req`) against what
`dispatcher.sh` actually writes there for a claimed request, and by
tracing `99-hold-take.sh`'s leg (f) fixture at
`docs/testing/jobs/selftest.d/99-hold-take.sh:94` (an `.owner` file only).

While a promoted restore is the thing being waited for, the poll interval
drops to 5 s (capped, never longer) so case "running: a restore" cannot be
missed between polls (addendum 1's instruction); it starts at
`HOLD_WAIT_INTERVAL` (default 15 s) and only drops to 5 s after the first
refusal, matching attempt 1's unmodified behavior when nothing is starved
yet.

**Selftest.** `99-restore-priority.sh` gained legs (e) and (f) (addendum
1's exact two conditions) and a new mutant: a one-line change forcing
`wait`'s `rrc` to always read 2 ("nothing running"), which reproduces
attempt 1's race exactly (gate-only, trusting a possibly-stale pass) and
turns both new legs red. `99-build-gate.sh`'s existing hold.sh mutant
(the `sed` pair at its "MUTANTS" section) still matches: `wait`'s gate
call keeps the literal substring `build_gate "$label" && break` (now
reached down two different paths -- gated and ungated -- instead of one),
so that file needed no edit.

One fixture bug found and fixed while writing legs (e)/(f): `last_run()`
picks the device's newest result by mtime across ALL of `results/`, not
just what one leg writes, and `results/` accumulates for the whole script
(legs (a)-(d) never clean it up). Leg (d)'s `off3` fixture (mtime 4000,
off master) was still the chronological "newest" when legs (e)/(f) and
their mutants ran, so the first version of each mutant check passed or
failed for the wrong reason (confirmed by running leg (f)'s mutant alone:
it failed because `build_gate` read `off3`, not the leg's own
"restoredFm" master-restore record). Fixed by resetting `results/` before
each of (e), (f), and their two mutant fixtures, so each reads only its
own intended "newest" record. Reran the full three-file selftest after
the fix: 121 passed, 0 failed.

## Not done here

- `docs/testing/request.sh` and `docs/testing/dispatcher.sh` are read-only
  in this lane (per brief); no change needed there since the fix lives
  entirely in `hold.sh`'s gate and `device_build.py`'s new `promote`
  command.
- The idlewatch patch (outside this repo) is written out in PR.md for
  lane.local to apply at fold, not applied here.

## Why attempt 2 did not finish (addendum 2, resumed 10-11, attempt 3)

Attempt 2 (the resumed session above, "addendum 1") fixed the race between
the promoted restore finishing and the dispatcher's next claim, set PR.md
`State: ready`, and stopped there -- before lane.local's addendum 2 review
found that the `wait` loop still starves on a fed queue, which is the exact
case this lane exists for. Everything above this section stands; this
section and the fix below are the resumed (third) attempt.

**What goes wrong.** In `wait`'s `rrc=1` branch ("other" is running,
hold.sh:322-324 before this fix), the loop only echoes a message and
sleeps -- it never calls `promote`. Promotion only happens inside
`build_gate`'s refusal (hold.sh:213-225), and that is only reached from the
`rrc=2` branch ("nothing running"). On a queue that is actually fed (the
case the brief opens with: 15:36-10-10's 7+ starvations, every night this
weekend's fastpaths/coldstart streams), the dispatcher reclaims within
seconds of any run ending (`dispatcher.sh:2354-2363`, same race addendum 1
described), so `running/` holds something for the label almost every time
`wait` polls. `rrc` reads 1 almost every poll; `rrc=2` (and therefore
`build_gate`, and therefore `promote`) is reached only in the rare instant
between one run ending and the next being claimed. So on a fed queue
`wait` times out at `rrc=1` without ever promoting anything -- worse than
before this lane, when hostops at least promoted it by hand. The live
dispatch dir has exactly this case right now: `0-1791706988-dispatch.restore--4043569.req`
already promoted by hand again, per the addendum.

**The fix: promote from the `rrc=1` branch too, not only from `build_gate`'s
refusal.** Before sleeping in that branch, make sure a `0-`-prefixed
restore for the label is in `queue/`, so the dispatcher's very next claim
-- the moment the in-flight "other" request ends -- is the restore, and
the `rrc=0` branch (already fixed by addendum 1) catches it immediately.
Two sub-cases, both handled by one new `device_build.py promote ... --force`
call:

- **A bare restore is already pending** (the usual steady state:
  `queue_master_restore`, the dispatcher's own post-run hook, leaves one
  after every off-master run, deduped to one by `restore_pending()`) --
  `cmd_promote`'s existing pending-check (`_restore_path(..., "queue")`)
  finds it and promotes it exactly as before; `--force` changes nothing
  here, since that branch runs before the force-skippable check.
- **None is pending**, because the in-flight "other" request has not
  finished and written its result.json yet, so `last_run()` still reads
  whatever ran before it -- which, on a fed release-tier queue, is
  typically another master run, so `restore_needed()` reads false and
  plain `promote` would print "already on master; no restore needed" and
  queue nothing (confirmed by reading `cmd_promote`, device_build.py:213-
  219: the `rec is None` and `not restore_needed(rec)` returns both happen
  before any queuing). `--force` skips both of those checks and queues +
  promotes unconditionally.

`--force` is a new keyword arg on `cmd_promote` (device_build.py:204),
threaded from a `--force` CLI flag in `main` (device_build.py:282-283).
It changes nothing about the pending/running short-circuits (they still
run first and return early either way) -- it only removes the "is a
restore even needed" guard on the final queue-a-new-one path, since that
guard is reading stale state by construction in this call site.

**Confirmed `restore_pending()` matches the `0-` file, so no duplicate.**
`restore_pending()` (device_build.py:153-172) globs `queue/*.req` and
`running/*.req` with no prefix filter, matching on `requester ==
"dispatch.restore"` and `device == label` alone -- a `0-`-prefixed file
satisfies that exactly as a bare one would. So when the in-flight "other"
request finishes and the dispatcher's own `queue_master_restore` hook runs
for it, `restore_pending()` sees the already-promoted `0-...` file and
queues nothing more. Verified with leg (g) below, not just read.

**Poll interval.** The `rrc=1` branch now also drops `interval` to 5 (the
same cap addendum 1 uses in the `rrc=2` branch once a restore is promoted
there), since once this branch has promoted a restore, missing its
transition to `running/` for up to 15 s is exactly the gap addendum 1
closed for the other path -- a promoted restore waiting in `queue/` should
always be polled at the 5 s cap, regardless of which branch did the
promoting.

**Selftest.** `99-restore-priority.sh` leg (f) is extended with two more
checks in the same fixture (a bare restore already queued gets promoted in
place; none queued gets exactly one new `0-`-prefixed one), and a new leg
(g) confirms the forced queue does not get a duplicate from
`device_build.py restore` once the in-flight run's result lands. A new
mutant (the `--force` branch's queuing call replaced with the unforced
`cmd_promote` path, i.e. `force=False` hardcoded) turns both of (f)'s new
checks red: with the master-reading guard back in place, the "none
pending, other running, last result on master" case queues nothing, same
as the defect this addendum fixes.

Ran `SELFTEST_ONLY="99-build-gate.sh 99-restore-priority.sh 99-hold-take.sh"
bash docs/testing/jobs/selftest.sh` in the foreground after the fix: see
the final count below.
