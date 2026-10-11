# lane.nfsdefault1011 -- the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)

## 0. Base

Base is `origin/master` at `6d8947bb47` (fold of lane/fastpaths1010), already checked out for this worktree.
`git merge-base --is-ancestor fa45851449 HEAD` -- true: fastpaths1010's "Fast renderer paths" toggle is in this
base, so step 1(b) extends an existing block rather than adding a new one. No merge needed.

## 1. Code

**(a) Submit frame buffering default, 3 everywhere.** `SettingsActivity.kt` already defaulted to 3 in both
places (the brief's own table marked it so); the two places that still said 2 were
`xemu_android.cpp:1188` (`GetPrefInt(..., "submit_frames", 2)`, what a fresh install with no pref ever written
runs) and `PerGameSettingsActivity.kt:94` (`globalValue("submit_frames", "2", ...)`, the per-game screen's
label for the global default). Both changed to `3`. `draw.c`'s own C default was already 3 (desktop
unchanged) and was not touched. `PerGameSettingsManager.kt` lists `submit_frames` as a per-game override key
with no default value in that file -- nothing to change there, and it is not in the brief's file list, so it
was left alone (a one-word comment edit there was reverted before committing: the board reads `Files:` to keep
lanes off each other's files, and that file is not on this lane's list).

**(b) `HAKUX_POSTED_PUT` and `HAKUX_LOCKFREE_WAKE` folded into "Fast renderer paths".** `MainActivity.kt`'s
`FASTPATHS_VARS` array (set together from the `fastpaths` pref, on by default) grew from six entries to eight;
the two doc comments above it and above `fastpathsEnabled()` now name all eight and the four lanes that folded
them (reportasync1010, texscan1010, drawrec1010, perdrawon1010, postput1010, lockwake1011). The `hakuX-build`
log line (`fastpaths: ON/OFF (#433)`) now also lists `FASTPATHS_VARS` by name, so a logcat read can tell which
switches a given build actually carries without opening the source -- useful now that the array has grown past
what one log word covers. `strings.xml`'s `settings_fastpaths_desc` gained one clause: "...and the hand-off of
GPU commands from the emulated CPU", keeping the existing "turn off only if" sentence. No change to `pfifo.c`,
`draw.c`, or any native file besides the one `GetPrefInt` default in (a); the switches' own env-var names and
semantics are unchanged from postput1010/lockwake1011/coldstart1010.

**Checked:**
- `cd android && ./gradlew compileDebugKotlin --offline -q` -- exit 0, no diagnostics.
- `python3 docs/lanes/flip474/ndkcheck.py android/app/src/main/cpp/xemu_android.cpp` (NDK compile line of the
  main checkout's newest arm64 Release configure, `-fsyntax-only`) -- exit 0, 0 error lines, 0 warnings in the
  file. The one-line default-value change is the only native edit, and it carries no new logic.
- `python3 docs/testing/check_android_guards.py` -- ok (3305 files).

## 2. NFS MW proof it reaches native

Prediction `docs/testing/predictions/nfsdefault1011-nfs.json`, reader `nfsread.py` (this directory), modeled on
fastpaths1010's `fpread.py`/`raread.py` (same route, same ON-no-env/OFF-explicit-env shape) rather than
lockwake1011's `wakeread.py`/`ppread.py` (those carry instrumentation-arm plumbing, `HAKUX_PROBE_WAITS`/
`HAKUX_FRAMETRACE`, that this plain-build A/B does not use). Legs: V (validity: marks, valid starts, boot
inputs, per-arm pace-line counts, and the on/off log lines -- `[postput] on`, `[lockwake] on`, `submit frames:
3` on ON; none of `[postput]`/`[lockwake]` and `submit frames: 2` on OFF); K (ON's cold start 1 <= 34.5 ms,
lockwake1011's own K bound); N (ON not slower than OFF at the cold start).

Queued in two batches of two per the pilot gate (no `pilots/nfsdefault1011.ok` on file; `(500+90)*4` = 2360 s =
39.3 min, over the 30 min that always goes through with no reviewed pilot; `(500+90)*2` = 19.7 min does not
need one): OFF + ON first, pilot verdict written, then ON + OFF.

**OFF1 (`1-1791735965-nfsdefault1011-3581025`) read:** found and fixed a leg bug, not a code bug. OFF's
logcat carries `env: HAKUX_SUBMIT_FRAMES=2` and draw.c's own `[coldstart1010] submit_frames=2
(HAKUX_SUBMIT_FRAMES; pref 3)` -- the engine ran at 2 submit frames as the arm intends. But
`xemu_android.cpp`'s `"submit frames: %d"` line (the one step 1a's brief cited as "the proof") logs the
*pref* value fed into `xemu_set_submit_frames` (3, since step 1a's change), not the value draw.c actually
runs with once `HAKUX_SUBMIT_FRAMES` overrides it -- so that line reads "submit frames: 3" on OFF too, and
was never going to prove the OFF arm's switch. This is pre-existing coldstart1010 behavior, not something
introduced by this lane's step 1a, and not a reason to touch `xemu_android.cpp` beyond the one default
already changed: draw.c's own log is the authoritative line for what the engine ran with when an env
override is in play, and `nfsread.py`'s `LOG_SUBMIT2` now matches that line instead
(`\[coldstart1010\] submit_frames=2 \(HAKUX_SUBMIT_FRAMES`). `[postput]`/`[lockwake]`/marks/valid-starts/
boot-input legs all PASS on OFF1; cold start 1 read 43.94 ms, 12/12 valid starts, 2 cold pace lines pooled
so far (floor is 3, needs OFF2 too). Full V/K/N verdict waits on all four runs.
