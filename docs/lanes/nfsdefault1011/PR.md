nfsdefault1011: the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)

State: draft (step 1 built and checked; step 2's device proof queued, not yet read)

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

**Device proof is queued, not yet read as of this draft.** Table below fills in once results land.

| | OFF (pre-lane shipped) | ON (this lane's default) |
|---|---|---|
| result id | pending | pending |
| `[postput]`/`[lockwake]` lines | pending | pending |
| `submit frames:` | pending | pending |
| cold start 1 (mean of 2) | pending | pending |
| K (ON <= 34.5 ms) | pending | |
| N (ON not slower than OFF) | pending | |

## Steps 3-4

Not started. Step 3 (Simpsons free roam route + A/B) and step 4 (37-title screen) remain, pending step 2's
read and the lane's own device-time budget on the Nova.

## Switch list

All three switches (`HAKUX_POSTED_PUT`, `HAKUX_LOCKFREE_WAKE`, `HAKUX_SUBMIT_FRAMES=3`) are in this draft's
default. None excluded yet; step 3's Simpsons A/B and step 4's screen are what could take one back out.

## Release note (performance)

Pending step 2's figures: "NFS Most Wanted's first race runs at ... fps (from ...)" and "Submit frame
buffering now applies its Triple default".
