nfsdefault1011: the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)

State: draft (step 1 built and checked; step 2 VOID on a route desync, waiting on nfsroute1011's
addendum before requeuing -- see NOTES.md; steps 3-4 continuing in the meantime)

Lane: nfsdefault1011      Issue: #433 (umbrella), none filed
Base: master @ 6d8947bb47 (fastpaths1010 folded; fa45851449 confirmed an ancestor)
Files: android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt, android/app/src/main/res/values/strings.xml, android/app/src/main/cpp/xemu_android.cpp, docs/lanes/nfsdefault1011/**, docs/testing/predictions/nfsdefault1011-*
Prediction: docs/testing/predictions/nfsdefault1011-nfs.json @ 1422f53bae47dea23dee81b442a2ea891970130875e38ef4674f26deeefd15de
Needs device: yes (Nova)
Needs NDK: yes

## Step 0: base

`6d8947bb47` already carries fastpaths1010 (`fa45851449` confirmed an ancestor). No merge needed.

## Step 1: code (NOTES.md section 1)

`SettingsActivity.kt` already defaulted `submit_frames` to 3 in both its places; `xemu_android.cpp`'s
`GetPrefInt` default and `PerGameSettingsActivity.kt`'s `globalValue` label were the two still at 2, now both 3.
`draw.c`'s own default was already 3 and is untouched.

`MainActivity.kt`'s `FASTPATHS_VARS` (the "Fast renderer paths" toggle) grew from six entries to eight,
`HAKUX_POSTED_PUT` and `HAKUX_LOCKFREE_WAKE` joined the six already there. The doc comments and the
`hakuX-build` logcat line now name all eight. `strings.xml`'s `settings_fastpaths_desc` gained one clause
naming the GPU-command hand-off. No native file touched besides the one `GetPrefInt` default; the switches'
semantics in `pfifo.c` are unchanged from postput1010/lockwake1011.

Checked: `./gradlew compileDebugKotlin --offline -q` (exit 0, no diagnostics); `ndkcheck.py` against the
main checkout's newest arm64 Release compile database, `-fsyntax-only` (exit 0, 0 errors, 0 warnings);
`check_android_guards.py` (ok, 3305 files). Built at `7002282149`.

## Step 2: NFS MW proof it reaches native (NOTES.md section 2)

Prediction registered at `7002282149`, modeled on fastpaths1010's `fpread.py` (same route, same ON-no-env/
OFF-explicit-env shape). Queued in two batches of two per the pilot gate (no `pilots/nfsdefault1011.ok` on
file yet): OFF+ON, then ON+OFF once the pilot's read is in.

**VOID -- blocked on a route fix, not a code finding.** Pilot batch (OFF1 `...3581025`, ON1 `...3581205`)
read clean: both logged their arm's switch lines exactly right (including a reader bug found and fixed --
`xemu_android.cpp`'s `submit frames: %d` logs the pref, not draw.c's env-overridden runtime value, so OFF's
proof is draw.c's own `[coldstart1010] submit_frames=2 (HAKUX_SUBMIT_FRAMES; pref 3)` line instead), 12/12
and 11/12 valid starts. Second batch (ON2 `...87617`, OFF2 `...87778`) desynced: lane.local caught it from
the route-frames screenshots (one run never left the name-entry keyboard, the other hit an autosave dialog
then attract-mode demo footage at its `gameplay`/`go12` marks) -- input-success-only validity
(`raread.bad_starts`) could not see it, since every route input still "succeeded". Added a frame-content
HUD check to `nfsread.py` (PIL, reads each start's `sN-g11.png` for the race HUD's speedometer dial) that
now drops both VOID runs correctly while passing the two good pilot runs' 24 frames. NOTES.md section 2 has
the full readout. nfsroute1011 is building a screen-gated route; **this step's two voided arms wait on that
addendum before requeuing**, per lane.local (2026-10-11). Steps 3-4 below do not depend on it.

| | OFF (pre-lane shipped) | ON (this lane's default) |
|---|---|---|
| pilot result id | `1-1791735965-nfsdefault1011-3581025` | `1-1791735970-nfsdefault1011-3581205` |
| pilot `[postput]`/`[lockwake]`/`submit_frames` lines | correct (none / "2" via draw.c's line) | correct (`on`/`on`/"3") |
| pilot valid starts | 12/12 | 11/12 (go6 pad.sh timeout, unrelated) |
| pilot cold start 1 | 43.94 ms | 45.55 ms |
| batch 2 result id | `1-1791741306-nfsdefault1011-87778` -- VOID (route desync, 0/12 valid) | `1-1791741301-nfsdefault1011-87617` -- VOID (route desync, 10/12 valid incl. `gameplay`) |
| K / N | pending requeue after nfsroute1011's addendum | |

## Steps 3-4

Not started. Step 3 (Simpsons free roam route + A/B) and step 4 (37-title screen) remain, pending step 2's
read and the lane's own device-time budget on the Nova.

## Switch list

All three switches (`HAKUX_POSTED_PUT`, `HAKUX_LOCKFREE_WAKE`, `HAKUX_SUBMIT_FRAMES=3`) are in this draft's
default. None excluded yet; step 3's Simpsons A/B and step 4's screen are what could take one back out.

## Release note (performance)

Pending step 2's figures: "NFS Most Wanted's first race runs at ... fps (from ...)" and "Submit frame
buffering now applies its Triple default".
