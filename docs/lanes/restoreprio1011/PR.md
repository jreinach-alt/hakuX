Lane: restoreprio1011            Issue: #433
Base: master @ 7f986f73f6
Files: docs/testing/jobs/device_build.py, docs/testing/jobs/hold.sh, docs/testing/jobs/selftest.d/99-build-gate.sh, docs/testing/jobs/selftest.d/99-restore-priority.sh, docs/lanes/restoreprio1011/NOTES.md, docs/lanes/restoreprio1011/PR.md
Prediction: none: harness defect, no device arm
Needs device: no    Needs NDK: no
State: ready

## What this fixes

idlewatch's `queue-starved` jam fired on a lone `dispatch.restore` request
7+ times since 15:36 PDT 10-10. `device_build.py`'s `restore_request` names
the restore with a bare `<epoch>-dispatch.restore-<run8>` id, and the
dispatcher serves `queue/*.req` in ASCII order (`request.sh:726-732`), so
that bare id sorts behind every `HAKUX_RELEASE_PRIO=1` request -- which is
every request a lane queues while the restore waits. hostops cleared it by
hand each time, renaming it to a `0-` id.

Hostops proposed giving `restore_request`'s id a `0-` prefix
unconditionally. **NOTES.md verifies the premise that would make that
unnecessary cost**: reading `dispatcher.sh`'s `serve_one` (the only place a
queued request is served) shows every request -- restore, title soak, or
suites/program run alike -- builds its own apk (`:1375`), installs it
(`:1410`), and writes its own env or explicitly clears a stale one
(`:1425`), all unconditionally and all before any branch on the request's
kind (the restore's own exit is at `:1445`, the title path at `:1468`, the
suites path at `:1605`). So a starved restore costs a SERVED measurement
nothing -- the next real request overwrites the device's state regardless.
It only matters to a caller who takes a hold and runs something BY HAND on
whatever the hold leaves installed.

So the fix lives in that caller: `jobs/hold.sh`'s build gate
(`docs/testing/jobs/hold.sh`, called at `take`'s line and `wait`'s line,
see NOTES.md for both). On a refusal (exit 4, the device's newest run is
off master) it now calls a new `device_build.py promote <dispatch_dir>
<label>`, which renames the device's pending `dispatch.restore` request to
a `0-`-prefixed name (atomic: tmp file + `os.replace`, in the same
directory), or queues one at that priority if none is pending. `take` keeps
its exit 4 (a caller that reads the exit code still knows it holds
nothing); `wait` now loops on the gate (instead of exiting on the first
refusal) until it passes or its own timeout expires -- a promoted restore
takes about 60 s to be served. `restore_request()` itself stays bare, so
the dispatcher's own post-run hook (`queue_master_restore`, with no hold or
human involved) still queues normal-priority restores that wait their turn
-- only a caller stuck behind a refused hold gets the `0-` treatment.

## Addendum 1 (lane.local, 10-11): a race in `wait`, found before fold

Attempt 1 (above) was right about the premise, the 2a choice, and the
idlewatch patch, but its `wait` loop had a race: the dispatcher claims its
next request the instant a served request ends -- it checks
`hold/<label>` only at the top of its tick, before the queue
(`dispatcher.sh:2354-2363`) -- which can land seconds before `wait`'s next
poll. A poll that trusted `build_gate` alone would read the just-finished
restore's own result.json (still the newest on disk; the new request has
not written one yet), pass, and take the hold while a fresh off-master
request is running right now -- exactly what the gate exists to prevent,
and silent where attempt 1's refusal was at least honest.

**Fix.** New `device_build.py running <dispatch_dir> <label>` answers from
`running/*.req`: exit 0 "restore: <id>" (the label's own restore is
running now -- take the hold before it finishes, since the dispatcher's
claim loop stops right after it), exit 1 "other: <id>" (something else is
-- do not even ask `build_gate`, its answer would be the stale pass above;
keep polling until that run's own completion re-queues a bare restore and
a later refusal promotes it), exit 2 "none" (nothing is -- `build_gate`'s
answer is current, act on it as before). `hold.sh`'s `wait` loop now asks
this first, for a gated label only (`label_gated`, the same
`HOLD_RELEASE_LABELS` membership check `build_gate` already did, extracted
so both can use it -- an ungated label like the Thor, whose screening runs
routinely show as "other" by design, must not have `wait` start blocking
on them). The poll interval drops to 5 s (from `HOLD_WAIT_INTERVAL`,
default 15 s) once a restore has been promoted, so the "restore running"
case cannot be missed between polls.

## Mutant results

`device_build.py`'s `promote` command, with its `_promote()` rename calls
replaced by a plain `os.path.basename` (so it still prints "promoted"/
"queued" but never renames the file), turns `99-restore-priority.sh`'s leg
(a) red: the bare request handed to it stays bare and is never given the
`0-` prefix. Verified directly (not vacuous).

`hold.sh`'s `wait` loop, with its `rrc=$?` (the running-check's exit code)
forced to `rrc=2` ("nothing running"), reproduces attempt 1's race
exactly -- gate-only, trusting whatever `build_gate`'s last-result read
says -- and turns both new legs red: (e) a running restore is no longer
taken early (times out instead of exiting 0), and (f) a non-restore
request running for the label is missed and the hold is taken anyway
(exits 0 instead of timing out). Both verified directly.

## Testing

`SELFTEST_ONLY="99-build-gate.sh 99-restore-priority.sh 99-hold-take.sh"
bash docs/testing/jobs/selftest.sh`: 121 passed, 0 failed (run in the
foreground, after the addendum-1 fix). Breakdown in NOTES.md, including
why `99-hold-take.sh` needed no change (its fixture `running/` only ever
holds `.owner` marker files, never the `.req` files `device_build.py
running` globs for, so the new check sees "none" there regardless; a real
claim's `running/` holds both) and what changed in `99-build-gate.sh`
(one renamed check, a cleanup line so the gate's own promotion side
effect does not leak into that file's restore-queueing counts, and two
mutant-check patterns widened from `'build_gate "$label" ||'` to
`'build_gate "$label"'` -- both still match unchanged after addendum 1,
since `wait`'s gate call keeps the literal substring `build_gate "$label"
&& break`, now reached down two paths, gated and ungated, instead of one).

## idlewatch patch (lane.local applies at fold)

Premise 2a (verified above): a `dispatch.restore` request is not starved
in any way that matters, because `jobs/hold.sh`'s build gate promotes it
the moment any caller's hold actually needs it. The `queue-starved` check
should not alarm on one. The `restore-pileup` check just above it in the
same file is untouched -- it still catches duplicates piling up unserved,
which this lane does not change.

In `/home/justin/hakux-work/host-tools/idlewatch.py`, inside the
`queue-starved` loop (currently lines 140-146):

```diff
     for f in files:
         base = os.path.basename(f)
         if base.startswith('0-') or base.startswith('1-') or base.startswith('z-'): continue
+        # jobs/hold.sh's build gate promotes this on its own refusal now
+        # (#433 lane.restoreprio1011) -- a bare dispatch.restore is not
+        # starved, it is waiting for a caller who needs it. The
+        # restore-pileup check above still covers duplicates piling up.
+        if 'dispatch.restore' in base: continue
         age_min = (now - os.path.getmtime(f)) / 60
         if age_min >= 20:
             jams['queue-starved:' + base] = "%s queued %d min for %s, outranked by a live '1-' critical-path stream (ASCII sort: '1-' always beats a bare epoch id) -- promote it: rename to a '0-' prefix in dispatch/queue/" % (
                 base, age_min, dev)
```

One line (plus a comment). The surrounding `restore-pileup` check a few
lines above already globs `*dispatch.restore*.req`, so matching on the
substring `'dispatch.restore'` in the basename is consistent with that
check's own style rather than reading each request's JSON.

## Not this lane's

- `request.sh` and `dispatcher.sh`: read-only per the brief; no change was
  needed there since every path the premise required was already readable
  from `serve_one` and `request.sh`'s `--ref` resolution.
- `docs/testing/jobs/selftest.d/99-hold-take.sh`: not touched. See NOTES.md
  for why its legs are unaffected by this change.
- The idlewatch patch above is written here for lane.local to apply; this
  lane does not and cannot edit that file (outside the repo).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
