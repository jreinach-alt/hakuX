[job.cloud] Audit pass 1 of PR #622 (lane.hddsplit, #397): two MEDIUM findings and two LOW.
M1 can leave `hddPath` on the titles disk for every later disc run, with no marker to undo it. M2 repeats a multi-GB reset attempt before every disc run once a reset fails. The PR moves to needs-remediation.

# Audit pass 1: PR #622, lane/hddsplit

- Head audited: `fa2e37531b` (`origin/lane/hddsplit`), 2 commits ahead of `origin/master`.
- Diff read: `git diff origin/master...HEAD`. It covers `docs/testing/dispatcher.sh`,
  `titles/titlestate.py`, `titles/saves.py`, `jobs/selftest.d/99-hdd-split.sh` and the lane NOTES.
- CI on the head: build ×2 and selftest (0–3) all pass.

## What I checked and found sound

- **The `plan()` loop terminates.** The possible sequences are seed → build → keep,
  harvest → build → keep, and harvest(failed) → keep(alert). All of them fit in the 5 rounds, and
  any other sequence fails the request.
- **A failed harvest is never rebuilt over below the ceiling.** `after_run` moves `device_sha256`
  only on a clean harvest. `plan` then returns `keep`+alert for that sha.
- **Worker concurrency on the shared store.** Harvest temp dirs are per device and per pid.
  `store_saves` skips dot dirs. `os.replace` onto a dir that the other worker already created is
  tolerated. Image pruning is per device prefix, and `nova-`/`thor-` do not overlap.
- **`hdd_pref_edit`.** It edits only the `hddPath` key, in place, and keeps every other byte.
  Unset → remove → read back `""` round-trips.
- **The app honours the pref.** `xemu_android.cpp:1029` takes `hddPath` when the file exists,
  ahead of `hddUri`. `hdd.img` is already qcow2 (`saves.py` docstring, `extract_results.py`), so
  pushing a `write_qcow2` output as `hdd.img` changes no format.
- **Disc runs do not need C:.** `saves.build` formats all partitions and writes only E: saves.
  nxdk pgraph/vsh discs boot from the DVD and write E:\nxdk_*.
- **Soak `PULL_GLOB` does not read hdd.img.** It lists `$GUEST_FILES/`, so moving the title's disk
  does not affect it.

## Findings

### M1 (MEDIUM): the restore marker is written after the pref, so a failed read-back leaves `hddPath` on titles.qcow2 with nothing to undo it, and the next title run makes that permanent

`dispatcher.sh:618-621`:

```
was=$(set_hdd_pref "$dpath") || return 1
[ -f "$(hdd_pref_marker)" ] || printf '%s' "$was" > "$(hdd_pref_marker)"
```

`set_hdd_pref` writes the prefs file first and reads it back after. It returns 1 when the
read-back does not match. That happens when the `run-as read back` call hits its 30 s timeout, or
when the read-back is empty.

**Failure scenario, part 1.** The write lands and the read-back hangs:
1. `titles_disk_prepare` returns 1 and no marker has been written.
2. `serve_one` calls `restore_hdd_pref`. It finds no marker and returns 0, so the device is left
   with `hddPath=.../titles.qcow2`.
3. The next pgraph or vsh request passes `restore_hdd_pref`, which again finds no marker. The disc
   boots with its E:\nxdk_* output going to titles.qcow2.
4. `run_disc.sh:196` pulls `hdd.img`, which is hard-coded. It holds an earlier run's output, so
   every result is STALE or MISSING, and nothing names the cause.

The same happens if the worker dies between the write and the `printf`.

**Failure scenario, part 2: it becomes permanent.** The next title run sees `was` =
`.../titles.qcow2`. With no marker present, it records that value as the one to restore. From
then on `restore_hdd_pref` "restores" the titles disk after every title run, and disc runs never
go back to hdd.img.

**Fix.** Write the marker before the write, using the value that was read (or have
`set_hdd_pref` write it before its `cat >`). Also refuse to record `was == $dpath` as the
original: record `$(x1box_dir)/hdd.img`, or fail loudly.

### M2 (MEDIUM): a reset that fails deterministically is retried in full before every disc run

`hdd_img_guard` (`dispatcher.sh:669-700`) keeps no state between requests. If `saves.py reset`
refuses the disk, it refuses the same disk every time. For example, one title's save might not
pull or verify, and the 6.9 GB disks that filled up are the likeliest to have a damaged FATX
chain. The same holds when the on-device `cp` to `hdd.img.bak-auto` fails because the device
lacks another ~7 GB.

**Failure scenario.** In either case, every later pgraph or vsh request on that handheld:
- first runs a device-side sha256 of the 7 GB file,
- then pulls it with `dev_pull` (up to 3 × 600 s),
- then runs the reset or the `cp` again, and fails again.

That costs minutes to tens of minutes per request, with no end. The only record is `hdd_guard.json`
`action: alert` in each result. On the `cp` path, a partial `hdd.img.bak-auto` is also left on
the device (`guard_fail` removes only host files). That partial file takes up the space the next
attempt needs.

**Fix.**
- Record the failed hdd.img sha on the host, per device, and skip the guard while the device's
  sha still matches it. Log the alert once rather than paying for it each run.
- Remove a `.bak-auto` whose sha does not match.

### L1 (LOW): `dev_bytes` reports an adb failure as "file absent", and `plan` builds over that disk

`dev_bytes` echoes -1 both when `stat` finds no file and when the adb call fails or times out
(`dispatcher.sh:541`). `plan()` returns `build` for `device_bytes < 0`
(`titlestate.py:359`) before it checks for unharvested writes.

**Scenario.** The previous run's harvest failed (the `keep`+alert state), or the worker died
before `titles_disk_after`. Then a transient stat failure pushes a store-built disk over the saves
that were never harvested. This takes two faults in a row, so it is LOW.

**Fix.** Separate "absent" from "unreadable" (for example, `ls` exit status versus adb exit
status), as `apply_env_pref` does for a hung call.

### L2 (LOW): seed errors do not stop the first build

`plan()` checks only that `seeded` is truthy. A title whose save failed to harvest from hdd.img
during `seed` gets a titles disk without its profile. The registry does agree with that disk, so
this is consistent, not wrong. The save is still on hdd.img, but no later step retries it, and
the only record is `hdd.seed.json` / `seeded.errors`. The PR body reports 0 seed errors on the
Thor's pull. The Nova's hdd.img was not tried.

**Suggestion.** Put seed errors in `hdd.json` as an alert, so that a status reader can see them.

## Verdict

M1 and M2 are to be fixed; L1 and L2 are at the lane's discretion. Label: needs-remediation.
