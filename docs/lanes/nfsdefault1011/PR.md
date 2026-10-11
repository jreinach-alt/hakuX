nfsdefault1011: the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)

State: draft (step 1 built and checked; step 2 held on nfsroute1011's golden profile route per Addendum 3;
step 3 PASS; step 4 next -- see NOTES.md)

Lane: nfsdefault1011      Issue: #433 (umbrella), none filed
Base: master @ 6d8947bb47 (fastpaths1010 folded; fa45851449 confirmed an ancestor)
Files: android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt, android/app/src/main/res/values/strings.xml, android/app/src/main/cpp/xemu_android.cpp, docs/lanes/nfsdefault1011/**, docs/testing/predictions/nfsdefault1011-*, docs/testing/titles/routes/simpsons-hit-run.route
Prediction: docs/testing/predictions/nfsdefault1011-nfs.json @ 1422f53bae47dea23dee81b442a2ea891970130875e38ef4674f26deeefd15de, docs/testing/predictions/nfsdefault1011-simpsons.json @ b47eb7b3b9286eb0b4bff4297fb06bad112f1b8f194e8c911f34a281f07f564e (PASS)
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
| K / N | pending -- held, see Addendum 3 below | |

**Addendum 3 (lane.local, 2026-10-11):** step 2's re-run moves to `nfs-mw-race.returning` on the golden
profile nfsroute1011's step 3 is building, not a gated `nfs-mw-quickrace` -- the owner ruled runs need a
profile, and the gate under construction will refuse the quickrace route anyway. Run a fresh OFF/ON set on
the new route when it lands; do not pool with OFF1/ON1. Held until an addendum says the route is live.

## Step 3: Simpsons Hit & Run free roam (NOTES.md section 3) -- PASS

Route: `docs/testing/titles/routes/simpsons-hit-run.route` (new file, in Files: above), copied
near-verbatim from lane.frametrace's `simpsons-frametrace.route`. The copied entry sequence (cutscenes/
menus) was correct, but the free-roam play loop it was given drove Homer into a concave corner of the
house and he stayed wedged there -- deterministically, reproduced in this lane's first OFF1/ON1 pair
*and*, re-checked with `hitch_report.py`, in frametrace's own "proven" run too (94% of pixels never moved
over its scored window). The route's claimed proof traced to pathfind's interactively-driven hold session,
not a measurement of this blind route's own play loop. Fixed: the play loop now backs up and turns wider
before resuming forward motion, every lap, so a re-wedge later in the window also clears. Confirmed by a
validation pilot before committing device time to the full batch; NOTES.md section 3 has the frame-by-frame
readout.

Four runs, OFF/ON/ON/OFF interleaved, all B and V legs PASS:

| | OFF (pre-lane shipped) | ON (this lane's default) |
|---|---|---|
| run 1 | `1-1791744545-nfsdefault1011-620311` -- 46.72 gfps | `1-1791744548-nfsdefault1011-620739` -- 59.29 gfps |
| run 2 | `1-1791745785-nfsdefault1011-877404` -- 48.65 gfps | `1-1791745784-nfsdefault1011-874556` -- 59.19 gfps |
| mean | 47.69 | 59.24 |

**W PASS: ON mean 59.24 >= OFF mean 47.69 - 1.0.** ON is not slower than OFF on this GPU-paced title in
free roam -- the opposite of the ~4 fps regression `c2dfca18a1` (#507) produced, satisfying postput1010's
PR.md condition for `HAKUX_POSTED_PUT` going default-on. All three switches stay in the default.

## Step 4

Starting the 37-title screen (fastpaths1010's title list, minus Call of Duty 3 (not on the Nova), the five
space-deferred titles, and RalliSport).

## Switch list

All three switches (`HAKUX_POSTED_PUT`, `HAKUX_LOCKFREE_WAKE`, `HAKUX_SUBMIT_FRAMES=3`) are in this draft's
default. Step 3's Simpsons A/B passed clean; none excluded. Step 4's screen is what could still take one
back out.

## Release note (performance)

Pending step 2's figures (held on Addendum 3's route): "NFS Most Wanted's first race runs at ... fps (from
...)" and "Submit frame buffering now applies its Triple default". Step 3: Simpsons Hit & Run's free-roam
fps is unaffected (59.2 vs 47.7 mean, ON not slower).
