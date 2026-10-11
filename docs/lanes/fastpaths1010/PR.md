# fastpaths1010: the six renderer switches as one Graphics toggle, on by default (#433, 0.5)

Lane: fastpaths1010          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 9b26a9647c
State: draft
Files: android/app/src/main/java/com/rfandango/haku_x/MainActivity.kt, android/app/src/main/java/com/rfandango/haku_x/SettingsActivity.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsManager.kt, android/app/src/main/java/com/rfandango/haku_x/PerGameSettingsActivity.kt, android/app/src/main/res/layout/activity_settings.xml, android/app/src/main/res/values/strings.xml, docs/lanes/fastpaths1010/**, docs/testing/predictions/fastpaths1010-*
Prediction: docs/testing/predictions/fastpaths1010-nfs.json @ PASS (step 2); docs/testing/predictions/fastpaths1010-screen.json @ PASS (step 3, fail_titles=[] as predicted)
Needs device: yes (Nova only)    Needs NDK: no
Release note (performance): "Fast renderer paths" graphics setting, on by default with a per-game override -- NFS Most Wanted's warm race-start countdown drops from a mean 44.23 ms to 34.22 ms (about 23% faster) with no correctness regression across 37 screened Playable titles.

## What changed (step 1)

Copies the shape of `7d574ece8b` (surfgpudefault1009, "GPU surface reuse"),
which copied `d4a02e2060` (#569, Ubershader): a "Fast renderer paths" switch
in Graphics settings, on by default, with a per-game override.
`MainActivity.onCreate` sets the six switches folded by reportasync1010,
texscan1010, drawrec1010 and perdrawon1010 together from the one switch,
right after the `HAKUX_SURFGPU` block, and logs one `hakuX-build` line
naming the state:

- `HAKUX_REPORT_ASYNC` (reports.c)
- `HAKUX_TEXSCAN` (texture.c)
- `HAKUX_DRAWREC` (draw.c)
- `HAKUX_UNI_BULK`, `HAKUX_UNI_UBERCACHE`, `HAKUX_UNI_FOGCACHE` (shaders.c)

An `env_vars` line for any one of the six still wins (applied after, by
`xemu_android.cpp`), so `request.sh --env` can still set each switch alone.
No native change: the C defaults stay off, so desktop, selftests and bare
runs are unchanged.

`./gradlew compileDebugKotlin --offline -q`: exit 0, no diagnostics.

## Step 2: NFS MW device proof -- PASS

Four runs on the Nova (OFF, ON, ON, OFF), ref `1ca4a6bd12`, route
`nfs-mw-quickrace`, 500s, `--perflog`:

| arm | mean warm countdown | runs |
|---|---|---|
| ON (app default, no `--env`) | 34.22 ms | 34.36, 34.06 |
| OFF (`--env` all six `=0`) | 44.23 ms | 44.58, 43.89 |

D = +10.01 ms (threshold 5.0), ON <= 36.0 ms threshold met. Every run's
logcat showed its arm's four on-lines correctly (present in ON, absent in
OFF, checked against the reader's exact regexes, not a loose grep).
`docs/lanes/fastpaths1010/fpread.py --expect fastpaths1010-nfs.json`:
**PASS**, all legs hold.

## Step 3: Playable-title screen -- PASS, 37/37 scoped titles

Scope: `pm/playable-accepted.tsv`'s 44 titles, narrowed to 38 screenable on
the Nova after two device-presence corrections (full history in
`docs/lanes/fastpaths1010/NOTES.md` sections 4.1-4.6): 6 titles stay off the
Nova by owner ruling (Azurik: Rise of Perathia, Baldur's Gate: Dark
Alliance, NBA Live 2004, Castlevania: Curse of Darkness, 50 Cent:
Bulletproof -- ~17 GB, would drop the Nova below its 25 GB floor; RalliSport
excluded per the brief). Of the 38, **Call of Duty 3 is not actually on the
Nova** despite its listing (discovered live, `title not on device` on both
arms) -- 37 titles ran.

Each title ran ON (app default, no `--env`) and OFF (`--env` all six `=0`),
read for: fatal (crash/hang/abort in logcat), frames (route-frames or
`--frames-every` capture, reviewed where a route exists), gfps (from
`hakuX-pace` logcat lines, `sum(vb)*1000/sum(ms)` over the gameplay window),
and hdd golden/state (disk-image consistency between arms). **All 37 pass**:
no fatal, correct on-line presence/absence per arm (4/4 on ON, 0/4 on OFF,
every title), consistent hdd golden/state between arms, gfps clustered near
the 59.9x vsync cap.

| title | gfps ON/OFF | verdict |
|---|---|---|
| Crimson Skies: High Road to Revenge | 59.90/59.94 | pass |
| Spikeout: Battle Street | 59.94/59.94 | pass |
| Jet Set Radio Future | 59.93/59.94 | pass |
| Tork: Prehistoric Punk | 59.81/59.81 | pass |
| ToeJam & Earl III: Mission to Earth | 59.99/59.96 | pass |
| Halo: Combat Evolved | 59.98/59.98 | pass |
| Panzer Dragoon Orta | 59.88/59.88 | pass |
| Call of Duty 3 | -- | **not run**: title not on device |
| Capcom vs. SNK 2 EO | 59.98/59.97 | pass |
| The Simpsons Hit & Run | 59.98/59.96 | pass |
| Dark Summit | 59.97/59.97 | pass |
| Kabuki Warriors | 56.44/59.90 | pass (gap wider than the rest of the screen, 6% vs <1% typical; no fatal/on-line/hdd defect, not escalated) |
| Gunvalkyrie | 58.69/58.59 | pass |
| 187: Ride or Die | 59.83/59.87 | pass |
| Tony Hawk's Pro Skater 2x | 59.91/59.90 | pass |
| KOF: Maximum Impact - Maniax | 59.79/59.63 | pass |
| Alien Hominid | 59.95/59.92 | pass |
| WWE Raw 2 | 59.95/59.48 | pass |
| Indigo Prophecy | 59.98/59.97 | pass |
| NFL Blitz 2002 | 59.98/59.97 | pass |
| Fight Club | 59.96/59.89 | pass |
| Future Tactics: The Uprising | 59.76/59.91 | pass |
| Legacy of Kain: Defiance | 59.96/59.88 | pass |
| The Lord of the Rings: The Fellowship of the Ring | 59.97/59.99 | pass |
| NBA 2K3 | 59.96/59.96 | pass |
| NBA 2K2 | 59.88/59.89 | pass |
| MLB SlugFest - Loaded | 59.83/59.96 | pass |
| Max Payne 2: The Fall of Max Payne | 59.95/59.96 | pass |
| MTV Celebrity Deathmatch | 59.98/59.97 | pass |
| World Soccer Winning Eleven 9 | 59.88/59.96 | pass |
| SpongeBob SquarePants: Battle for Bikini Bottom | 59.97/59.98 | pass |
| Rogue Trooper | 59.97/59.97 | pass |
| Blade II | 59.97/59.96 | pass |
| Mortal Kombat: Armageddon | 59.99/59.98 | pass |
| Blowout | 59.94/59.96 | pass |
| MLB SlugFest 2004 | 59.97/59.95 | pass |
| MLB SlugFest 2003 | 59.97/59.97 | pass |
| Ratatouille | 59.83/59.97 | pass |
| AMF Bowling 2004 | 59.87/59.84 | pass (golden both arms -- matches, no pixel regression) |

No `WIDEN:` condition was triggered: no title failed fatal/frames/on-lines/hdd
after any rerun, so the 5 owner-deferred titles (Azurik, Baldur's Gate: Dark
Alliance, NBA Live 2004, Castlevania: Curse of Darkness, 50 Cent:
Bulletproof) were never pulled in. Full per-title refs and run notes:
`docs/lanes/fastpaths1010/NOTES.md`.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
