# lane.holdwait -- `hold.sh wait-idle`

Brief: `briefs/holdwait.md` (hostops, 2026-10-01 ~22:25 PDT). Harness defect, no tracker issue.

## The defect

`hold.sh take` stops the dispatcher claiming NEW work on a device. It does not stop the request already
running there. Its header said "take and then wait for running/ to empty of <label> yourself". Nothing
enforced that second half. It has now been skipped three times:

| when (PDT) | who | what died |
|---|---|---|
| 2026-09-27 20:01 | lane.titleroutes session 27, Thor | arm `1-1790560694-arms-pacing-base-2707775`: claimed at 20:01:23, the lane took the hold at 20:01:24 and launched at 20:01:39 (titleroutes NOTES, session 27) |
| 2026-09-28 19:53 | coldslot-hostops, Thor | nothing died; `host-tools/coldslot.sh:19-22` records that the hold landed at 19:53:17 and forzadecay414 still claimed at 19:53:18 |
| 2026-10-01 21:58 | lane.titleroutes session 61, Nova | `1790914021-lane.ibcache-3203127` (#507 leg 5b arm B): force-stopped at 132 of 420 s (am_kill 21:58:26 and :29) |

The 09-28 row is the race that "check running/ once after the take" misses. The worker checks `hold/` at
the top of its tick, then walks the queue: an `affinity.py` call and a battery read per request, which takes
seconds. Only then does it claim. A take that lands inside that walk is followed by a claim.

## What the callers were told (all three are wrong or missing)

1. **`briefs/titleroutes.md` ADDENDUM 14 (22:22 PDT, the interim fix) checked nothing.** Its command was
   `ls running/*.owner | xargs -r grep -l '"device": *"nova"'`. An owner file holds the bare label
   (`dispatcher.sh:1102`, `printf '%s\n' "$DEVICE_LABEL"`; on disk the bytes are `6e6f 7661 0a`, "nova\n").
   That grep matches no owner file, ever. Run against a copy of the live dispatch dir at ~22:50 PDT, it
   listed nothing while `1790918365-titleroutes-76920` was running on the Nova; `grep -lx nova` listed it.
2. **ADDENDUM 7(a) said `hold.sh wait` "takes the hold once the run in flight finishes".** It does not.
   `wait` retries only while someone else HOLDS the device. It takes the hold immediately over a running
   request. routedriver's and titlestate's briefs give the same `hold.sh wait ... around every replay` recipe.
3. **titleroutes' own `scratch/dev.sh take` calls `hold.sh wait`** and writes "waits for running/ to empty
   first" into the hold's `.why`. Its separate `scratch/takeloop.sh` (written after session 27) does wait, but
   only on `running/*.owner`, so it is open to the 09-28 race.

## What changed

`docs/testing/jobs/hold.sh`:

- **`wait-idle <label> <timeout_s>`** polls every 5 s (`HOLD_IDLE_INTERVAL`). It returns 0 only when all of
  these are true in one poll:
  1. `hold/<label>` exists, with any tag. Otherwise it exits 1 at once, because nothing stops a claim a
     second later.
  2. The device's worker has seen the hold. `lanes/<label>` is gone, or it names a pid that is not a live
     `dispatcher.sh` process (read from `/proc/<pid>/cmdline`). The worker writes its pid there on every
     unheld tick (`lane_claim`), and removes it on its first held tick (`lane_release`, `dispatcher.sh:2065`).
     So once the file is gone, any claim from the last unheld walk has already written its owner file. This
     condition is checked BEFORE condition 3 for that reason.
  3. No `running/*.owner` holds exactly `<label>`. The owner file is used, not the `.req`. The `.req` moves to
     `results/` at `dispatcher.sh:1733`. The owner file stays until `:1774`, after the result is written and
     before the after-run force-stop.

  On timeout it prints every blocker, says the hold is still the caller's, and exits 3.
- **`take` and `wait` print a `NOT IDLE:` notice on stderr** when the device they just took is busy. It names
  the run and the command to use. Exit codes, stdout (`taken: ...`) and the hold files do not change. This
  puts the second half in front of the existing callers (dev.sh, the three briefs' `hold.sh wait`) from the
  moment they merge master, without anyone having to read a new instruction first.
- The header's usage block now opens with the one sequence: `hold.sh take ... && hold.sh wait-idle <label> 900`.

**Not changed:** what `take`, `release`, `who` and `wait` decide. `wait` was considered (every lane caller
believes it waits for idle). It was rejected: lane.local's host tools (`coldslot.sh`, `updwin_after_run.sh`,
`doa_cache_pull.sh`, `coldcap/cold_*.sh`) call `wait` with 3600-7200 s timeouts and do their own idle loop
afterwards. A `wait` that released on an idle timeout would drop their hold during an arm longer than an hour.

## Proof

`selftest.d/99-hold-take.sh`, new legs g1-g8. Each leg says which wrong implementation it fails. Run alone:

    env SELFTEST_ONLY=99-hold-take bash docs/testing/jobs/selftest.sh
    selftest: 45 passed, 0 failed  (legs a-f, the holdtake lane's, unchanged and passing)

The brief's three legs are g1 (an owner names the label: exit 3 at the timeout, naming the run, hold kept), g2
(nothing runs: exit 0 on the first look, `timeout 0`) and g3 (owners naming `thor` and `nova2` do not block
`nova`). The extra legs are: g4 (no hold: exit 1), g5 (the worker registration, live / dead /
non-dispatcher / another label's), g6 (an owner whose `.req` has left: blocks), g7 (the run ends 2 s into a
10 s wait: returns in 2-6 s) and g8 (take's notice; stdout still exactly the one `taken:` line).

**The legs fail when the code is wrong.** `docs/lanes/holdwait/mutants.sh` builds eight broken copies of
hold.sh and runs the fragment against each through `SELFTEST_HOLD_SH`:

| mutant | what is broken | legs that fail |
|---|---|---|
| always-idle | wait-idle never looks | 9: g1 x2, g2, g4, g5, g6, g7, g8 x2 |
| always-busy | never idle | 9: g2, g3 x2, g5 x3, g7 x2, g8 |
| no-lane-check | running/ only (the 09-28 race) | g5 live dispatcher |
| any-pid | any registered pid blocks | g5 non-dispatcher pid, g5 other label |
| req-not-owner | reads .req, not .owner | g6, g7 |
| substring | "nova" matches "nova2" | g3 nova2 |
| no-hold-check | idle without a hold answers 0 | g4 |
| silent-take | pre-holdwait take | g8 x2 |

Every mutant fails at least one leg, and every new leg fails under at least one mutant. Legs a-f pass under
all eight mutants, so the new code does not touch what they check.

**Against the live formats:** a copy of the real `running/` and `lanes/` taken at ~22:50 PDT, plus a fake
`hold/nova`. `wait-idle nova 0` printed both blockers, `dispatcher pid 4176221 has not seen the hold yet` and
`running: 1790918365-titleroutes-76920 on nova`, and exited 3. The live dispatch dir was only read: no hold
was taken on a real device.

## The titleroutes convention

- **Done now (interim, works with the current hold.sh):** in `briefs/titleroutes.md`, ADDENDUM 14's grep is
  replaced in place with `grep -lx nova .../running/*.owner`. ADDENDUM 7(a)'s false sentence about `wait` is
  corrected in place and points at ADDENDUM 14's check. No addendum was added.
- **After this branch folds:** rewrite those same lines (2, 7(a), 14, and the "Getting a device" item) to the
  one path: `bash docs/testing/jobs/hold.sh take <dev> <tag> <why> && bash docs/testing/jobs/hold.sh wait-idle
  <dev> 900`, touching the device only on exit 0. If wait-idle prints the usage text, the checkout predates
  the fold: merge origin/master. This cannot be written before the fold, because titleroutes' tree has no
  `wait-idle` until then, and a session following it would stop at the usage text.
- **titleroutes' own `scratch/dev.sh take`** is in that lane's worktree and is not mine to edit. Once it
  merges master, its `hold.sh wait` call prints the NOT IDLE notice. Its `.why` text ("waits for running/ to
  empty first") is still false, and the lane should switch `take` to `wait ... && wait-idle ...`.

## Status

[lane.holdwait] waiting: the fold of lane/holdwait into master (PR.md `State: ready`, pushed 2026-10-01
~23:00 PDT; `hakux-foldqueue.timer` picks it up). Resolved when `git merge-base --is-ancestor 379883645f
origin/master` holds. Then the one remaining step: rewrite `briefs/titleroutes.md`'s hold lines (Build step
2, "Getting a device", ADDENDUM 7(a), ADDENDUM 14's command) in place to `take && wait-idle`, as above. If
the fold fails, read `offline-git/fold-failures.log`.

## For the next lane

- Do not check `running/` once after a take and call the device idle. The 09-28 race is real: claims land
  seconds after the hold.
- Do not grep owner files for JSON. They hold a bare label.
- routedriver and titlestate briefs carry the same `hold.sh wait` recipe. The notice covers them once their
  trees merge master. Their brief owners should switch them to `take && wait-idle` too.
- `hold.sh` returns to [lane.toolsmith]'s standing claim when this folds (territory note).
