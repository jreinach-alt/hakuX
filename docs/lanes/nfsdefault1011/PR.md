nfsdefault1011: the three NFS switches on by default, and "Submit frame buffering" honoured (#433, 0.5)
State: ready

Lane: nfsdefault1011      Issue: #433 (umbrella), none filed
Base: master @ 6d8947bb47 (fastpaths1010 folded; fa45851449 an ancestor); origin/master c975179b51 merged at c5e4c0e4a7
Files: android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt, android/app/src/main/res/values/strings.xml, android/app/src/main/cpp/xemu_android.cpp, docs/lanes/nfsdefault1011/**, docs/testing/predictions/nfsdefault1011-*, docs/testing/titles/routes/simpsons-hit-run.route
Prediction: docs/testing/predictions/nfsdefault1011-simpsons.json @ b47eb7b3b9286eb0b4bff4297fb06bad112f1b8f194e8c911f34a281f07f564e (PASS); docs/testing/predictions/nfsdefault1011-screen.json @ 821fb0af67fc791541c771cc3b7b845cca178e04019c1e9bde77d59b4b1607a0 (10 of 38 screened, no fail; 28 withdrawn by the owner); docs/testing/predictions/nfsdefault1011-nfs.json @ 1422f53bae47dea23dee81b442a2ea891970130875e38ef4674f26deeefd15de (not judged; the owner dropped step 2)
Needs device: yes (Nova)    Needs NDK: yes

Release note (performance): NFS Most Wanted's first race now starts at 29.8 fps (from 26.4), and Submit frame buffering now applies its Triple default.

## What changed

"Fast renderer paths" (on by default) now also sets `HAKUX_POSTED_PUT` and `HAKUX_LOCKFREE_WAKE`. Its
description adds "...and the hand-off of GPU commands from the emulated CPU". Submit frame buffering defaults to
Triple (3) in all three places:
- the settings screen, already 3;
- `xemu_android.cpp`'s `GetPrefInt` default, 2 -> 3;
- `PerGameSettingsActivity.kt`'s global label, 2 -> 3.

A player who picked a value keeps it. An `env_vars` line still overrides any switch. No change to pfifo.c, draw.c
or any other native file except the one default. Checks: `compileDebugKotlin` is clean, the NDK `-fsyntax-only`
compile is clean, and `check_android_guards.py` passes.

## Switch list

| switch | in the default | evidence |
|---|---|---|
| `HAKUX_POSTED_PUT=1` (postput1010) | yes | Simpsons free-roam A/B (postput1010's condition): ON not slower |
| `HAKUX_LOCKFREE_WAKE=1` (lockwake1011) | yes | same A/B; lockwake1011's own K PASS on NFS MW |
| Submit frame buffering 3 (coldstart1010) | yes | same A/B; coldstart1010's depth A/B on NFS MW |

None was left out. No title failed in the 10 screened.

## Proof the defaults reach native without env (NOTES.md section 2, "Attempt 4")

Step 3's two ON runs have no env (`...620739`, `...874556`). Both logcats show:
- `[postput] on`;
- `[lockwake] on`;
- `submit frames: 3`;
- buffer.c's runtime `per-frame staging created (3 frames`.

Both OFF runs show `(2 frames`.

draw.c's `[coldstart1010] submit_frames=` line prints only when `HAKUX_SUBMIT_FRAMES` is set in the environment
(draw.c:1268). So it cannot appear on a no-env run, and the staging line is the runtime proof in its place.

## Step 2: NFS MW (dropped by the owner)

Between 16:26 and 16:39 the owner played a full NFS MW race on the Nova with the three switches on, called the
frame rate "SO good", and asked for the fold. The step-2 re-run on `nfs-mw-race.returning` was dropped. Earlier
runs on `nfs-mw-quickrace`, kept as evidence only:

| | OFF (pre-lane shipped) | ON (this lane's default) |
|---|---|---|
| pilot | `1-1791735965-nfsdefault1011-3581025`: 43.94 ms cold, 12/12 valid | `1-1791735970-nfsdefault1011-3581205`: 45.55 ms cold, 11/12 valid |
| second | `1-1791741306-nfsdefault1011-87778`: VOID (route desync) | `1-1791741301-nfsdefault1011-87617`: VOID (route desync) |

`nfsread.py` now checks the race HUD in each start's frame, and that check drops both VOID runs.

The release-note figure is NFS MW's cold race start, from two lanes' measurements:

| configuration | cold start 1 | fps | lane, runs |
|---|---|---|---|
| shipped: six fastpaths switches, depth 2 | 37.93 ms | 26.4 | coldstart1010 arm A: `1-1791697258-coldstart1010-3142274`, `1-1791697260-coldstart1010-3142523`, `1-1791697261-coldstart1010-3142581` |
| + posted store + lock-free wake + depth 3 | 33.58 ms | 29.8 | lockwake1011 arm B: `0-1791717604-lockwake1011-1989057`, `0-1791717605-lockwake1011-1989154`, `0-1791717611-lockwake1011-1989918` |

These are two binaries, so the figure is a chain of two measurements, not one A/B. The configuration the two
lanes share agrees: posted store + depth 3 measured 34.79 ms in coldstart1010 and 34.54 ms in lockwake1011. The
warm countdown and post-GO frames were already about 30 fps (33.4-33.75 ms) in every configuration.

## Step 3: Simpsons Hit & Run free roam (PASS)

The route is `simpsons-hit-run.route`, a new file. It uses frametrace's entry. Its play loop was fixed to back out
of the house corner that parked Homer in every earlier run, including frametrace's original.

| | OFF (pre-lane shipped) | ON (this lane's default) |
|---|---|---|
| run 1 | `1-1791744545-nfsdefault1011-620311`: 46.72 gfps | `1-1791744548-nfsdefault1011-620739`: 59.29 gfps |
| run 2 | `1-1791745785-nfsdefault1011-877404`: 48.65 gfps | `1-1791745784-nfsdefault1011-874556`: 59.19 gfps |
| mean | 47.69 | 59.24 |

W PASS: ON 59.24 >= OFF 47.69 - 1.0. V PASS: Homer moves in free roam after the mark in all four runs.
`c2dfca18a1` (#507), an earlier form of the store, took this title from 40.05 to 36.22 fps; this lane's
default does not regress it.

## Step 4: screen (scope cut by the owner, 10 of 38)

The owner cancelled the screen after batch 1 (Addendum 5). This lane screened 10 of
`nfsdefault1011-screen.json`'s 38 titles. Of the other 28, batch 2's 10 were withdrawn before they ran and 18 were
never queued; none of the 28 is a pass. One run per arm, `screenread.py`:

| title | fatal ON/OFF | frames ON/OFF | gfps ON/OFF |
|---|---|---|---|
| Crimson Skies: High Road to Revenge | none/none | 3/3 | 29.97/30.01 |
| Spikeout: Battle Street | none/none | 8/8 | 60.03/60.01 |
| Jet Set Radio Future | none/none | 4/4 | 59.87/59.76 |
| Tork: Prehistoric Punk | none/none | 16/15 | 30.37/29.21 |
| Kabuki Warriors | none/none | 16/16 | 52.65/59.37 (not judged, #787) |
| 187: Ride or Die | none/none | 21/21 | 60.02/60.09 |
| Tony Hawk's Pro Skater 2x | none/none | 13/13 | 59.40/59.48 |
| KOF: Maximum Impact - Maniax | none/none | 11/11 | 59.76/59.98 |
| Alien Hominid | none/none | 1/1 | 59.96/59.87 |
| WWE Raw 2 | none/none | 15/15 | 59.07/59.94 |

No ON-only fatal and no fail. Kabuki Warriors' gap is placement of its known stall #787, which the Wall carries
as a watch (owner, Addendum 7). The rerun pair, telemetry only, read ON 54.16 and OFF 58.11
(`...3829286`/`...3829494`).

🤖 Generated with [Claude Code](https://claude.com/claude-code)
