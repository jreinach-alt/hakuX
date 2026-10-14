# savestateconv1014 -- pathfind: reach gameplay once, keep it as a save state (#433)

Scope delivered this session: **Part A, done** (merge, from-state admission, mutants).
**Part B, done** -- names a blocker with evidence, per the brief's own readiness allowance
("A-D done, or B names a blocker with its evidence"). Parts C/D/E are **not implemented**:
see "Why C/D/E stop here" below. This matches the brief's stated priority ("deliver A and B
finished rather than C-E half done").

## Part A -- R3 admits `--from-state`

Merged `lane/holdfollow1013` (a45f88b319): R3 (the profile gate's refusal of blind
re-navigation on a known-path title) now admits a `--no-record` re-hold. Both of
holdfollow1013's own selftest runs (pre-merge and on the merged tree) reported
`pathfind_selftest: all ok`.

Added the `from_state` case to `r3_refusal()` (`docs/testing/titles/pathfind.py`): a hold
started from a captured save state does no navigation at all, so it is admitted
unconditionally on a known-path title -- stronger than `--no-record`, since no replay
happens either. A title with no known path is untouched by this branch: `--from-state` on
such a title has nothing to load (a state is only ever taken on a run that already reached
gameplay once), and that is refused by the state-load check itself (Part D), not by R3.
Three new `check("r3", ...)` cases in `pathfind_selftest.py` cover it directly (no other
flags; with `--no-replay`/`--no-guide` set; with no known path at all).

Both selftest runs (merge, then again after the `from_state` addition) on this tree:
`pathfind_selftest: all ok`.

### Mutants (commit 2bd51331ed's code; each applied, run, reverted via `git checkout --`)

| # | Mutation | Selftest result |
|---|---|---|
| 1 | drop the final refusal (`return (...)` -> `return None`): admits a known-path title **without** `--no-record` | `FAIL r3` |
| 2 | drop the `--no-replay`/`--no-guide` narrowing inside `if no_record:` (admits `--no-record` even when the kept path is dropped) | `FAIL r3` |
| 3 | drop the `--no-record` admission entirely (today's/pre-Part-A code: known-path title always refused) | `FAIL r3` |
| 4 | drop the `if from_state: return None` admission entirely | `FAIL r3` |

All four mutants are caught by the `r3`-tagged checks; the clean tree passes both runs.
Mutant 2 stands in for holdfollow1013's brief's "`--no-record` only admitted together with
`--perflog`" case: that case no longer applies to the current code, because the merged
design deliberately keeps `--perflog` out of `r3_refusal()`'s signature entirely (its own
test: "`--perflog` never reaches `r3_refusal`... perflog is orthogonal to R3's own
admission"), so there is no "narrower rule keyed on perflog" left to mutate. Mutant 2 is the
surviving safety-relevant boundary in its place: an admission that doesn't check
`no_replay`/`no_guide` would let a `--no-record` run navigate blind with nothing recorded.

## Part B -- the five questions

### B1. Disk binding: does a save state survive the dispatcher's next-run rebuild?

**No -- already a named, re-confirmed defect** (`titlestate.py`'s `plan()`,
`docs/lanes/savestate1011/NOTES.md`'s "Owner checks": *"The dispatcher rebuilds the title
disk on every run, so a state's disk snapshot never survives into the next run (the state is
then refused as `disk-snapshot-missing`)."*)

Reconfirmed live on the Nova today, 2026-10-14, no hold needed for the read (device-sha and
device-bytes are read-only `adb shell` reads; `plan()` itself takes them as plain arguments,
so this never touches the device beyond that):

- Host bookkeeping (`dispatch/titlestate/devices/nova.json`), from a harvest at
  `2026-10-14T12:10:53Z` (run `held-nova-20261014T045538`): `device_sha256` =
  `faaf0578e3...` (the sha harvested that run), but `image.sha256` (the pushed, composed
  goldens) = `66412857d0...` -- already different from the harvest's own sha, i.e. the disk
  had writes beyond the composed goldens even as of that harvest.
- Live read on the Nova just now: `adb -s ee317437 shell sha256sum
  .../files/x1box/hdd.img` = `8b8d575f58ac0608450bf83005a945035ba032620064202449fddb9362af416a`,
  size 1044775746 B -- different again from both of the above (more play has happened since
  04:55:38Z).
- `python3 titlestate.py plan --device nova --device-bytes 1044775746 --device-sha
  8b8d575f... --title-id 55530040 --state any` (host-only, no device touch):
  `{"action": "harvest", "reason": "the device's disk changed since its last harvest"}`
- Same call with the device-sha the 04:55:38Z harvest itself recorded (`faaf0578e3...`,
  19529728 B -- i.e. simulating "harvest just completed, nothing more written since"):
  `{"action": "build", "reason": "the disk carries a run's writes since it was pushed; every
  run starts from the goldens"}`

So: the disk is harvested (preserving per-title TDATA into the host-side store) before it is
ever rebuilt, but the rebuild step itself still fires on every ordinary run once harvested,
because the composed-goldens sha (`image.sha256`) never moves unless a title's `golden.json`
record changes. A save state's qcow2-internal snapshot (`hxs-<root8>-<title>-<tag>-<uuid8>`,
inside `hdd.img`) is not part of any title's golden record, so `build` discards it on the very
next run of **any** title (the disk is shared), regardless of `--from-state`.

**This blocks Part C/D's actual promise** (a soak restarting from a state tomorrow night):
unless a title's golden record is made to include "load this state", or the conversion
pipeline bypasses `titlestate.py`'s goldens entirely for state-bearing runs, a state taken
tonight does not exist by the time a later run's `plan()` looks at the disk.

### B2. Prefs routing: does a per-title savestate override reach a harness launch?

**No**, confirmed by code reading (not reopened this session, same conclusion as before):
`PerGameSettingsManager`'s per-game overrides are written into `x1box_per_game_settings`
(keyed by a sha256 of the lowercased relative ROM path) and copied into
`runtime_override_*` keys only by `applyRuntimeOverridesToEditor()`, called from
`GameLibraryActivity`/`SettingsActivity` -- never from `LauncherActivity`, which is the
activity `pathfind.py` launches via `am start ... --es rom_path ...`. `saveStateBool()`
(Kotlin) and `GetPrefBool()` (native, `xemu_android.cpp`) both check the runtime-override key
first, else the global pref -- so a harness launch always falls through to the global
`savestate_auto_save`/`savestate_auto_load` booleans. This is exactly the brief's
pre-approved fallback (write the global pref, restore after, verified by read-back) --
exercised live below.

### B3. Trigger behavior: does the already-shipped auto-save-on-quit fire reliably?

**Measured live, 2026-10-14, Nova (serial ee317437), title Tork: Prehistoric Punk
(55530040), chosen because it is absent from every existing `x1box/states/` folder (see
below) -- nothing of anyone else's could collide.**

Hold: `lane.savestateconv1014`, taken, `wait-idle` returned `idle` before any device touch.

1. **First device action, logged before anything else**: read-only listing of
   `/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box/states/`:
   ```
   drwxr-s--- 2 u0_a145 ext_data_rw 3452 2026-10-13 17:41 41560037
   drwxr-s--- 2 u0_a145 ext_data_rw 3452 2026-10-13 22:58 43430001
   drwxr-s--- 2 u0_a145 ext_data_rw 3452 2026-10-12 16:13 4541007b
   drwxr-s--- 2 u0_a145 ext_data_rw 3452 2026-10-13 22:12 4553000a
   drwxr-s--- 2 u0_a145 ext_data_rw 3452 2026-10-13 22:34 4d570029   <- MKSM; never entered/touched
   drwxr-s--- 2 u0_a145 ext_data_rw 3452 2026-10-13 22:30 54510105
   -rw-r----- 1 u0_a145 ext_data_rw 2200 2026-10-14 04:55 sessions.log
   ```
2. Read `x1box_prefs.xml` (run-as cat): no `savestate_auto_save`/`savestate_auto_load` keys
   at all (both default `false`). Logged in full before any write.
3. Pushed a prefs file identical except for `savestate_auto_save=true` and
   `savestate_auto_load=true` appended, copied into place with `run-as ... cp`, **read back
   and confirmed** both keys now read `true`.
4. Launched Tork (`am start -a android.intent.action.VIEW -n
   com.jreinach.hakux.debug/com.rfandango.haku_x.LauncherActivity --es rom_path '...Tork -
   Prehistoric Punk (USA).iso'`, the same sequence `pathfind.py`'s `Device.launch()` uses).
   After ~20 s, confirmed alive (`ps` shows `com.jreinach.hakux.debug:xemu`) and foreground
   (`dumpsys window`: `MainActivity`). logcat (`hakuX-lane`, `hakuX-savestate`, cleared
   beforehand) shows the boot-time auto-load check running cleanly with nothing to load:
   `[savestate] auto-load result="none" after_ms=1342` (no prior state existed for this
   title, as expected).
5. Backgrounded it cleanly (`am start -a android.intent.action.MAIN -c
   android.intent.category.HOME`, not `force-stop`, so `onStop()`'s auto-save thread gets a
   chance to run before the process dies) -- confirmed it actually backgrounded
   (`dumpsys window` now shows `org.es_de.frontend`, the launcher, focused).
6. `pace526`/`rwait526` pacing log lines continue for about 10-20 s after backgrounding (the
   emulator core keeps rendering/pacing in the background), then **stop appearing entirely**.
   At `07:28:40.459`, ~37 s after the background intent: `W hakuX-savestate: auto-save (stop)
   not done after 10000 ms` -- the 10 s join timeout elapsed and `onStop()` returned without
   waiting further (as designed, "a quit never hangs on it"), but the save thread itself kept
   running.
7. Waited roughly another 50 s (several short polls, device stayed held and idle the whole
   time). The save thread never logged a completion line (`ok=...`/`reason=...` from
   `autoSaveOnQuit`'s own `Log.i`), no `x1box/states/55530040/` directory was ever created,
   and `top -b -n1` showed the `com.jreinach.hakux.debug:xemu` process at **0.0% CPU** the
   whole time -- not slow, genuinely stalled/blocked on something, not merely a big write in
   progress.
8. Cleaned up: `am force-stop` (ends the stalled thread along with the process -- confirmed
   no `55530040/` folder was ever created, so there was nothing partial to worry about
   cleaning up), restored `x1box_prefs.xml` to byte-identical original content, **read back
   and confirmed** no `savestate_auto_save`/`savestate_auto_load` keys remain, removed the two
   pushed scratch files under `/data/local/tmp/`, confirmed the six pre-existing
   `x1box/states/<title>/` folders (including `4d570029`, never entered) are unchanged, then
   released the hold.

**Finding: triggering auto-save-on-quit by backgrounding cleanly ("go home", `onStop()`)
stalls the native save with zero CPU activity, for this title, on this build, for at least
~90 s past the trigger**, rather than completing late or failing with a refusal reason. The
prior UX test plan (`docs/lanes/savestate1011/NOTES.md`) only exercises "Pause menu, Exit"
(an explicit UI action) and "swipe-away from recents" (documented as best-effort, "Android
may end the process first") -- neither is the same lifecycle path as a clean `am start`-to-home
backgrounding exercised here, so this may be a path nobody has driven before. This is a
Kotlin/native question (why does the core stop producing frames and never finish the
snapshot once backgrounded this way -- a GL surface/context teardown blocking the pause, a
lock the UI thread holds that the save thread needs, or something else in `hxs.c`'s pause
path), not something this harness session can diagnose further: **those files
(`MainActivity.kt`, `xemu_android.cpp`, `savestate/hxs.c`) are lane.playsecs1013's territory,
not mine.**

**WAITING: a native/Kotlin-side look at why `nativeSaveStateAutoQuit()` stalls (0% CPU, no
completion log, no refusal log) after a clean "go home" backgrounding, as opposed to the
already-tested pause-menu-Exit and swipe-away paths. Until that's understood, an automated
state-capture pipeline (Part C) cannot safely rely on backgrounding as its trigger.**

### B4. Load behavior: timing/hitches of `--from-state` vs cold boot

**Not measured.** B3's stall means no auto-save ever completed during this session, so there
was no state to load and no "Loaded the auto slot" message to time. Blocked on the same
B3 finding.

### B5. Snapshot limits: is the 13-snapshot cap per-title or per-image?

**Per-title**, confirmed by code reading (`hxs.c`'s snapshot name scheme is
`hxs-<root8>-<title>-<tag>-<uuid8>` -- the title ID is embedded in the name, so the dispatcher's
bookkeeping of "13 live" (10 slots + auto + undo-save + undo-load) counts snapshots sharing a
title, not all snapshots on the shared `hdd.img`). One disk can hold many titles' states
simultaneously, up to whatever `CAP`/`CEILING` (512 MiB / 4 GiB) the disk's total size allows
before `plan()` rebuilds it anyway for size, independent of the state question.

## Why C/D/E stop here

Parts C (`--save-state`) and D (`--from-state` beyond the R3 gate landed in Part A) both
depend on B1's blocker being resolved first: there is no point writing a `--save-state` path
that takes a state the very next dispatcher run throws away, nor a `--from-state` path that
loads a state that `plan()`'s `build` action has already deleted. B3's stall is a second,
independent blocker on the measurement side -- even a correct conversion pipeline needs a
working, timed capture trigger to convert anything with. Part E
(`convert.tsv`/`tonight.sh`) has nothing to list or script without C/D.

Per the brief's own readiness condition ("A-D are done, or B names a blocker with its
evidence"): Part B names its blocker (B1, re-confirmed live with today's data) and a second
one found live (B3's stall), both with device evidence above. The design decision B1 needs --
how a title's golden record should carry "load this state instead of a cold composed
disk" -- is bigger than this lane's remit to invent unreviewed, and B3's stall is
Kotlin/native territory this lane does not hold.

## Device time used

Two short Nova holds, back to back: the first (read-only listing + sha/plan probes) and the
second (the prefs mutation + Tork round-trip attempt + restore). Both held-idle promptly;
total device time well under the 75-minute budget (on the order of 15-20 minutes including
the two `wait-idle` waits).

## Territory

Touched: `docs/testing/titles/pathfind.py`, `docs/testing/titles/pathfind_selftest.py` (both
released to this lane by the merge), `docs/lanes/savestateconv1014/**`. Nothing else.
`titlestate.py` was read but not modified (not this lane's to touch, and B1's fix needs a
reviewed design decision first, not a unilateral change here).
