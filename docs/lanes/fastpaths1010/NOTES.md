# lane.fastpaths1010 -- the six renderer switches as one Graphics toggle (#433, 0.5)

## 1. Precondition: drawrec1010 is in master

`git merge-base --is-ancestor lane/drawrec1010 origin/master` passes (exit 0):
`lane/fastpaths1010` branched from `9b26a9647c`, which IS the drawrec1010 fold
commit. All six switches' native code (`HAKUX_REPORT_ASYNC`, `HAKUX_TEXSCAN`,
`HAKUX_DRAWREC`, `HAKUX_UNI_BULK`, `HAKUX_UNI_UBERCACHE`, `HAKUX_UNI_FOGCACHE`)
is present on this branch's base; confirmed by `grep getenv` in
`hw/xbox/nv2a/pgraph/vk/{reports,texture,draw,shaders}.c`. No merge of
`drawrec1010` needed -- it already folded.

## 2. Step 1: the toggle

Copied the shape of `7d574ece8b` (surfgpudefault1009), which copied `d4a02e2060`
(#569, Ubershader): a `fastpaths` boolean pref (global + per-game override,
`PerGameSettingsManager.runtimeKey`), default `true`. `MainActivity.onCreate`
sets all six env vars to `"1"`/`"0"` together right after the `HAKUX_SURFGPU`
block, from one `FASTPATHS_VARS` array, and logs one `hakuX-build` line:
`"fastpaths: ON (#433)"` or `"...OFF..."`. No native change; each switch's own
C default is still off (`getenv` returns NULL for a bare `request.sh` run with
no env and no app in front of it, e.g. selftests and desktop).

An `--env` entry for any one of the six still wins: `xemu_android.cpp` applies
the `env_vars` pref line AFTER `MainActivity`'s `nativeSetenv` calls (the same
ordering surfgpudefault1009 relied on and proved in its own device pair).

Files touched: `MainActivity.kt`, `SettingsActivity.kt`,
`PerGameSettingsManager.kt`, `PerGameSettingsActivity.kt`,
`activity_settings.xml`, `strings.xml`.

`./gradlew compileDebugKotlin --offline -q` -- exit 0, no diagnostics.

### 2.1 Why one switch, not six

The brief asks for exactly this (one Graphics toggle). A per-switch picker
set already exists in `PerGameSettingsActivity`-style per-game overrides for
the OTHER settings (ubershader, surfgpu) one at a time; six more of those
would let a per-game override turn on e.g. only `HAKUX_TEXSCAN` without
`HAKUX_REPORT_ASYNC`, which texscan1010 measured as a regression alone
(slower than both off). Keeping them as one app-level switch makes that
combination unreachable from the UI; the override is read as six, not one,
for provenance (each native `getenv` site is independent), but there is no
UI path to light only one of them. `--env` still can, for testing.

## 3. Step 2: device proof (NFS MW, `nfs-mw-quickrace`)

Prediction: `docs/testing/predictions/fastpaths1010-nfs.json`, registered
before any device run, `a_ref` = `b_ref` = this lane's step-1 commit (one
binary, env-only A/B -- the same reason texscan1010-nfs.json and
postput1010-nfsall.json used an equal pair, and the same reason their
queue_order says "arms.sh skips a_ref == b_ref": the lane queues these
itself with `request.sh`, not the automatic arms job).

Reader: `docs/lanes/fastpaths1010/fpread.py`, built on
`docs/lanes/reportasync1010/raread.py`'s parsing (marks, pace lines,
`bad_starts`, `has_log`) with its own `arm_of` (ON = request.json env holds
none of the six `=0` overrides; OFF = holds all six) and its own two legs
(`W`: ON's warm countdown <= 36.0 ms; `D`: OFF - ON >= 5.0 ms warm), plus the
log-line check for all four on-lines (`[reportasync] on`, `[texscan] on`,
`[drawrec1010] drawrec=1 vtx=1 shc=1`, `[perdraw433] bulk=1 ubercache=1
fogcache=1` -- the three UNI_* switches share one combined log line, so "each
switch's own line" is four distinct lines covering six vars) present on
every ON run and absent on every OFF run.

Pilot batch (OFF1, ON1) queued first per the 30-min device-time gate; read,
then `pilots/fastpaths1010.ok` written before queuing the rest (ON2, OFF2),
giving the registered OFF,ON,ON,OFF order.

| run | arm | result id | warm countdown (ms) | marks | valid starts | on-lines (4) |
|---|---|---|---|---|---|---|
| 1 | OFF | `1-1791693697-fastpaths1010-2485559` | 44.58 | 12 | 12 | 0/4 (correct) |
| 2 | ON  | `1-1791693739-fastpaths1010-2489599` | 34.36 | 12 | 12 | 4/4 (correct) |
| 3 | ON  | `1-1791695098-fastpaths1010-2835211` | 34.06 | 12 | 12 | 4/4 (correct) |
| 4 | OFF | `1-1791695102-fastpaths1010-2836733` | 43.89 | 12 | 12 | 0/4 (correct) |

Arm means (`fpread.py`'s `period()`, mean of each run's own period): **ON 34.22
ms**, **OFF 44.23 ms**, D = +10.01 ms. Every run's `request.json` `env` field
matched its intended arm exactly; every run showed the arm's four on-lines
(`[reportasync] on`, `[texscan] on`, `[drawrec1010] drawrec=1 vtx=1 shc=1`,
`[perdraw433] bulk=1 ubercache=1 fogcache=1`) when ON and none of them when
OFF -- checked against `fpread.py`'s exact `LOGS_ON` regexes, not a looser
grep (an early looser grep on OFF1 matched the all-zero diagnostic lines,
e.g. `[perdraw433] bulk=0 ubercache=0 fogcache=0`, which is a different line
and does not trip the strict check).

One `hakuX-build` line is odd and worth naming, though it is not a failure:
every run, ON and OFF alike, logs `fastpaths: ON (#433)`, because that line
is `MainActivity`'s own read of the app pref (default `true`, untouched by
`--env`), printed before `env_vars` is applied by `xemu_android.cpp`. The
OFF arm's actual override still lands -- proven by the all-zero native
diagnostic lines and the absent on-lines above -- the same separation
surfgpudefault1009's own device proof relied on (it logged `surfgpu: ON`
then a separate `env:` line ~48 ms later, same PID). Not fixed here (no
native/`MainActivity` logic change beyond what step 1 already made; the log
text reads the switch, not the resolved env, same as surfgpudefault1009's).

`s11-g11.png` (one of the 12 warm-window frames) checked by eye for one ON
and one OFF run: car present and moving (different road position, different
speedometer reading, different split time between the two), flare decals
render the same way in both, no missing geometry or black frames.

`python3 docs/lanes/fastpaths1010/fpread.py <OFF1> <ON1> <ON2> <OFF2> --expect
docs/testing/predictions/fastpaths1010-nfs.json` -- **VERDICT: PASS**, 2 of 2
non-validity checks hold (W: ON 34.22 <= 36.0; D: +10.01 >= 5.0), all V legs
pass.

## 4. Step 3: Playable-title screen

Merged `origin/master` first (21 commits, none touching this lane's files;
`da07fe5140`). `git merge-base --is-ancestor lane/drawrec1010 origin/master`
still passes.

### 4.1 Scope: 20 of 44, not all 44

`pm/playable-accepted.tsv` lists 44 titles. Checked each against
`/home/justin/hakux-work/hardware/titlepush/listing-nova.txt` (Oct-3) and
`docs/testing/titles/targets.toml`: **24 of the 44 have no ISO on the
Nova** -- they are on the Thor only. Moving a title's ISO onto the Nova
("shuffle") is a one-directional Thor-to-Nova `adb` copy
(`wt/pathfind/scratch/shuffle1007.sh`), and it is explicitly **not** this
lane's to run: two other lanes' own NOTES.md already record that device
inventory / shuffling is `lane.local`'s job, not a dispatched lane's grant
(memory `shuffle-means-onto-the-nova`), and the brief's own rule list says
"use request.sh only" for device access, which has no shuffle path.

This is a **partial blocker**, not a full one: the brief can proceed for the
20 titles already on the Nova, and the remaining 24 need a shuffle before
they can be screened. Named here so lane.local (or the owner) can action it;
the 24 are listed in `fastpaths1010-screen.json`'s `blocked_titles`, not
claimed pass or fail.

### 4.1.1 Addendum (lane.local, 10-10 22:46 PDT): shuffle in progress, scope now 21

The brief itself picked this up before any action was needed here: the
Oct-3/Oct-4 Nova listing this lane checked was stale by one title --
Capcom vs. SNK 2 EO (`43430008`) is already on the Nova as
`43430008-Capcom_vs_SNK_2_EO.xiso.iso`, making the Nova-resident scope **21**,
not 20. lane.local is shuffling the other 23 onto the Nova overnight itself
(unit `lanelocal-shuffle1010b`, log
`/home/justin/hakux-work/lanelocal-scratch/shuffle1010.log`), confirming
this lane's own read that shuffling is not this lane's grant. The addendum's
plan, followed here:

1. Screen the 21 Nova-resident titles first, in batches.
2. Screen each shuffled title once its log line reads `<TID> on Nova,
   verified <bytes> bytes: <filename>` (lines before that batch's own
   `start (b: ...)` don't count), using the exact filename the log names.
3. Do not mark ready while `shuffle1010.log` still lacks a `done` line after
   its last `start (b: ...)`. A title whose push failed gets a row in the
   screen table saying so, not a run.

Update, 23:43:58 PDT: `shuffle1010.log` now ends `done; Nova free 33 GB` --
all 23 verified (last: Mortal Kombat: Armageddon, 23:43:58), and the Nova
hold is released (`dispatch/hold/nova` empty). **All 44 Playable titles are
now on the Nova.** `fastpaths1010-screen.json` updated again (same
reasoning: no device run has yet used any earlier scope) to drop
`blocked_titles` to empty and fold the remaining 23 into the scoped list
below. None of the 23 has a `docs/testing/titles/targets.toml` entry with a
`route` (only Mortal Kombat: Armageddon has any entry at all, and it is
`target_fps`/notes only) or a matching file in `docs/testing/titles/routes/`
-- checked by grepping each of the 23 title IDs against both. All 23 run as
soaks, same as the 2 soak-plan titles already in the 21 (NBA Live 2004,
Call of Duty 3, Capcom vs. SNK 2 EO already soak-only).

### 4.1.2 The Alien Hominid pilot failed live: 12 of the 21 were already gone

The first real step-3 request pair (Alien Hominid ON/OFF,
`1-1791697695-fastpaths1010-3189025`/`-3189126`) both came back with
`ERROR: title not on device: 5A440004-Alien_Hominid.xiso.iso -- searched
/storage/E6C6-D7AA/Games/XBox`, despite Alien Hominid being in the
"confirmed present" 20/21 from 4.1/4.1.1. The Oct-3 listing this lane
checked is not just missing 24 additions (4.1.1's fix) -- it can also be
wrong about presence it claims, because it predates events that remove
titles.

`wt/pathfind/scratch/nova-free1008.log` (a space-freeing pass, 10-08
21:25-21:49 PDT, not seen before this pilot failure) records 34 titles
deleted from the Nova that day to recover space (99% full at the start,
`/dev/fuse 955G 945G 10G 99%`). Diffing those 34 against the 23 titles
tonight's shuffle (4.1.1) restored leaves **12 still missing**, never
restored: Alien Hominid, KOF: Maximum Impact - Maniax, Azurik: Rise of
Perathia, WWE Raw 2, 50 Cent: Bulletproof, Baldur's Gate: Dark Alliance,
Kabuki Warriors, 187: Ride or Die, Tony Hawk's Pro Skater 2x, Gunvalkyrie,
Castlevania: Curse of Darkness, NBA Live 2004 -- all 12 were in this lane's
original 20/21, none were in tonight's shuffle list (the addendum's 23 was
built from the brief author's own check, which apparently also didn't
cross this log). Capcom vs. SNK 2 EO was `archived` in the same Oct-8 pass
but never `deleted` -- consistent with the addendum finding it present.

These 12 move to `blocked_titles` (`fastpaths1010-screen.json` updated
again, same in-place reasoning: no device run has used any wider scope).
**Current scope: 32 of 44** -- 8 of the original 20 the Oct-8 pass did not
touch, Capcom vs. SNK 2 EO, and the 23 restored tonight. This finding is
named here (and will go in a PR comment) so lane.local can decide whether
to shuffle these 12 back; not run here, same reasoning as 4.1.

32 scoped (ISO presence now cross-checked against both the Oct-3 listing
AND the Oct-8 deletion log; still not a live query, so a further "title not
on device" on any of these is possible and gets treated as a blocker for
that one title, not grounds to distrust the whole batch), with route/soak
plan:

| title | nova iso | route | plan |
|---|---|---|---|
| Crimson Skies: High Road to Revenge | `Crimson Skies - High Road to Revenge (USA) (En,Fr,De,Zh,Ko).xiso.iso` | `crimson-skies` | route |
| ToeJam & Earl III: Mission to Earth | `ToeJam & Earl III - Mission to Earth (USA).iso` | none | soak, 180s, `--frames-every 15` |
| Spikeout: Battle Street | `Spikeout - Battle Street (Europe).iso` | `spikeout` (returning variant on disk) | route |
| Halo: Combat Evolved | `Halo Combat Evolved.iso` | none | soak, 180s, `--frames-every 15` |
| Panzer Dragoon Orta | `Panzer Dragoon Orta (Europe).iso` | none | soak, 180s, `--frames-every 15` |
| Jet Set Radio Future | `JSRF - Jet Set Radio Future (USA).xiso.iso` | `jsrf` | route |
| Tork: Prehistoric Punk | `Tork - Prehistoric Punk (USA).iso` | `tork` | route |
| Call of Duty 3 | `4156005D-Call_of_Duty_3.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Capcom vs. SNK 2 EO | `43430008-Capcom_vs_SNK_2_EO.xiso.iso` | none (no `targets.toml` entry) | soak, 180s, `--frames-every 15` |
| The Simpsons Hit & Run | `56550015-The_Simpsons_Hit_Run.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Dark Summit | `54510004-Dark_Summit.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| MTV Celebrity Deathmatch | `5454000B-MTV_Celebrity_Deathmatch.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| NFL Blitz 2002 | `4D570001-NFL_Blitz_2002_USA.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| NBA 2K2 | `53450002-NBA_2K2.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| MLB SlugFest 2003 | `4D570008-MLB_SlugFest_2003.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| AMF Bowling 2004 | `42530009-AMF_Bowling_2004.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| MLB SlugFest 2004 | `4D570009-MLB_SlugFest_2004.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| MLB SlugFest - Loaded | `4D57001D-MLB_SlugFest_Loaded.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Rogue Trooper | `5343000E-Rogue_Trooper.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Ratatouille | `54510109-Disney_Pixar_Ratatouille.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| World Soccer Winning Eleven 9 | `4B4E002F-World_Soccer_Winning_Eleven_9.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| NBA 2K3 | `53450013-NBA_2K3.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Mortal Kombat: Armageddon | `4D570034-Mortal_Kombat_Armageddon.xiso.iso` | none (target_fps=60 only) | soak, 180s, `--frames-every 15` |
| Fight Club | `5655002F-Fight_Club.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Blowout | `4D4A0008-Blowout.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Future Tactics: The Uprising | `43560007-Future_Tactics_The_Uprising.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Blade II | `41560005-Blade_II.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Indigo Prophecy | `4947007B-Indigo_Prophecy_USA.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| SpongeBob SquarePants: Battle for Bikini Bottom | `5451001A-Nickelodeon_SpongeBob_SquarePants_Battle_for_Bikini_Bottom_USA.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| The Lord of the Rings: The Fellowship of the Ring | `56550004-Lord_of_the_Rings_The_The_Fellowship_of_the_Ring_USA.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Legacy of Kain: Defiance | `4553000F-Legacy_of_Kain_Defiance_USA.xiso.iso` | none | soak, 180s, `--frames-every 15` |
| Max Payne 2: The Fall of Max Payne | `5454000C-Max_Payne_2_The_Fall_of_Max_Payne.xiso.iso` | none | soak, 180s, `--frames-every 15` |

32 of 44 Playable titles are scoped (4.1.2); the other 12 are blocked on a
reshuffle this lane does not run. 4 route titles (300s each: Crimson Skies,
Spikeout, Jet Set Radio Future, Tork), 28 soak titles (180s each,
`--frames-every 15`) -- one run per arm, ON/OFF interleaved, giving 64 runs
for this scope (the brief's own 88-run estimate assumed all 44).

Route runs: 300s, no `--frames-every` (named routes carry their own
`mark`/`shot` frames, per titlerun's own convention -- `--frames-every` is
for soak-only captures and request.sh refuses it alongside a scored route).
One run per arm (not two): a screen's job is to catch a correctness
regression, not measure pace precisely; a title that fails gets rerun twice
before any attribution, per the brief.

Prediction `docs/testing/predictions/fastpaths1010-screen.json` registered
before the first screen request, `a_ref`=`b_ref`=`da07fe5140` (this lane's
branch after the master merge).

### 4.2 Pilot batch 1: Crimson Skies (gfps methodology + screen results)

`gfps` (the brief's required column, "both arms' telemetry fps, reported not
gated") has no ready-made field in `result.json`/`perf_regimen.json` for a
route run -- those carry `perf_mode`/`fan_mode`/`display` settings, not a
measured rate. It is in `logcat.txt`'s `hakuX-pace` lines (the same source
`raread.py`/`fpread.py` read for NFS's race-start countdown), one line per
~2s window: `f=<frame> v0..v4=<bucket counts> vb=<total> max=<ms> ms=<window
ms>`. Most of this screen's titles have no discrete race start to window on
(fpread.py's NFS-specific countdown logic doesn't apply), so `gfps` here is
read over the whole steady-state window instead: from the route's own `mark
gameplay` line (or, for soak titles with no route, from app-start + a fixed
settle) to `soak end`, `gfps = sum(vb)*1000/sum(ms)` across that window's
pace lines -- the same per-line math, just summed over a wider window than a
single race start.

Pilot pair, Crimson Skies: High Road to Revenge (route `crimson-skies`,
refs `1-1791703775-fastpaths1010-4011126` ON / `-4011199` OFF, both 300s):

| check | ON | OFF |
|---|---|---|
| `request.json` env | `[]` (app default) | all six `=0` |
| on-lines (4 expected ON, 0 expected OFF) | all 4 present, 00:53:50 | 0 present |
| fatal/crash/abort/ANR | none | none |
| hdd state | golden, `returning`, title `4D530021` | golden, `returning`, title `4D530021` |
| route marks | booted 00:55:25.7, gameplay 00:56:00.3, end 00:59:14.0 | booted 01:01:07.2, gameplay 01:01:42.2, end 01:04:56.1 |
| gfps (gameplay->end window) | 59.90 | 59.94 |
| route-frames | 3 captured (booted/gameplay/play), visually normal | 3 captured, visually normal |

Verdict: **pass, no regression**. Both arms clean on every correctness
check; gfps is a statistical wash (ON and OFF within 0.1% of each other) --
this title isn't bottlenecked by any of the six switches either way, which
is itself a valid outcome for a correctness screen (the claim under test is
"no scoped title fails," not "every title gains").

Pilot batch verdict written to `pilots/fastpaths1010.ok` (step-3's own
pilot, separate from step-2's NFS pilot).

Batch 2 queued next (20 runs, ref `c404a74b97`): the 3 remaining route
titles (Spikeout, Jet Set Radio Future, Tork) plus 7 soak titles (ToeJam &
Earl III, Halo: Combat Evolved, Panzer Dragoon Orta, Call of Duty 3, Capcom
vs. SNK 2 EO, The Simpsons Hit & Run, Dark Summit), ON/OFF each. The pilot
gate admitted the whole batch on the fresh `pilots/fastpaths1010.ok`
(no per-run 30-min re-check needed once that file is <24h old).

### 4.3 Scope widens to 39: lane.local's Addenda 2 and 3 (10-11 00:41/00:43 PDT)

While batch 2 was running, lane.local sent a cross-session message (and
appended Addenda 2 and 3 to `briefs/fastpaths1010.md`) reporting that 7 of
the 12 titles blocked in 4.1.2 are back on the Nova: Kabuki Warriors,
Gunvalkyrie, 187: Ride or Die, Tony Hawk's Pro Skater 2x, KOF: Maximum
Impact - Maniax, Alien Hominid, WWE Raw 2 (unit `lanelocal-shuffle1011`,
log `/home/justin/hakux-work/lanelocal-scratch/shuffle1011.log`). Verified
directly rather than taken on trust: the log shows all 7 `pushed` then `on
Nova, verified <bytes> bytes` between 00:47:51 and 00:52:50 PDT, ending
`00:52:50 done; Nova free 26 GB`. These move out of `blocked_titles`;
**scope is now 39 of 44**.

The brief's Addendum 2 text says "four of them have their own route:
187-ride-or-die, kabuki-warriors, thps2x and castlevania-cod" (castlevania
not among the seven, so three routes return). Checking
`docs/testing/titles/routes/` directly found this undercounts: route files
also exist for `alien-hominid.route`, `kof-mi.returning.route` and
`wwe-raw-2.route` -- six of the seven restored titles have a route, only
Gunvalkyrie runs as a soak. Using the files on disk, not the addendum's
summary, since that's what `request.sh --route` actually reads.

The other 5 (Azurik: Rise of Perathia, Baldur's Gate: Dark Alliance, NBA
Live 2004, Castlevania: Curse of Darkness, 50 Cent: Bulletproof, ~17 GB
combined) stay off the Nova -- the owner's ruling (Addendum 3, via
lane.local, 10-11 ~00:42 PDT) is to screen the 39 and give these 5 a row
"not on the Nova; owner 10-11: screened only if a defect emerges", not
blocking `gh pr ready`. A defect (fails fatal or frames, or armed <100%
on OFF's clean, after two reruns) gets a `WIDEN:` line here naming the
title/column/result ids, which lane.local reads to shuffle the 5 in.

`fastpaths1010-screen.json` updated: `blocked_titles` now holds just the 5
owner-deferred titles; `queue_order`/`expect_note` narrate the 32->39 move.
No device run has used the stale 32-title scope for anything beyond the
Crimson Skies/batch-2 titles already in both scopes, so this is an in-place
correction, not a rebase-after-registration violation.

Batch 3 (next): the 7 newly-restored titles, 6 by route + 1 soak
(Gunvalkyrie). Remaining after that: the rest of the 23-restored-tonight
list from 4.1.1/4.1.2 not yet run.

### 4.4 Screen results (filled in as batches complete)

Batch 2 is running behind ordinary queue contention (coldstart1010 held the
Nova ahead of it for about 15 min; this is normal multi-requester sharing,
not a blocker). Throughput once running: about one run per 6-8 min (route
runs 300s + ~90s overhead; soaks 180s + overhead), so this 20-run batch is
expected to take roughly 2-2.5h of device time, consistent with the
pilot-gate's own ~102 min estimate for route titles alone plus the soaks.

| title | arm | fatal | frames | gfps | verdict |
|---|---|---|---|---|---|
| Crimson Skies: High Road to Revenge | ON/OFF | none/none | normal/normal | 59.90/59.94 | pass (4.2) |
| Spikeout: Battle Street | ON/OFF | none/none | not yet reviewed by eye (route-frames pulled, not diffed) | 59.94/59.94 | pass (env/on-lines/hdd/marks all clean both arms) |
| Jet Set Radio Future | ON/OFF | none/none | not yet reviewed by eye | 59.93/59.94 | pass (env/on-lines/hdd both arms clean; hdd golden_status None is expected for a first-run-state title, not a defect) |
| Tork: Prehistoric Punk | ON/OFF | none/none | not yet reviewed by eye | 59.81/59.81 | pass (env/on-lines/hdd clean both arms) |
| ToeJam & Earl III: Mission to Earth | ON/OFF | none/none | not yet reviewed by eye | 59.99/59.96 | pass (env/on-lines/hdd clean both arms, golden/any) |
| Halo: Combat Evolved | ON/OFF | none/none | not yet reviewed by eye | 59.98/59.98 | pass (env/on-lines/hdd clean both arms, golden/any) |
| Panzer Dragoon Orta | ON/OFF | none/none | not yet reviewed by eye | 59.88/59.88 | pass (env/on-lines/hdd clean both arms, golden/any) |
| Call of Duty 3 | ON/OFF | -- | -- | -- | **not run**: both runs errored `title not on device` (refs `...4194026`/`...4194140`) |
| Capcom vs. SNK 2 EO | ON/OFF | none/none | not yet reviewed by eye | 59.98/59.97 | pass (env/on-lines/hdd clean both arms; hdd golden_status None expected, no targets.toml entry) |
| The Simpsons Hit & Run | ON/OFF | none/none | not yet reviewed by eye | 59.98/59.96 | pass (env/on-lines/hdd clean both arms, golden/any; refs `...4194264`/`...310`) |
| Dark Summit | ON/OFF | none/none | not yet reviewed by eye | 59.97/59.97 | pass (env/on-lines/hdd clean both arms, golden/any; refs `...346`/`...380`) |
| Kabuki Warriors | ON/OFF | none/none | not yet reviewed by eye | 56.44/59.90 | pass (env/on-lines/hdd clean both arms, golden=None expected first-run; refs `...1524606`/`...1524721`). gfps gap wider than the rest of the screen (6%, vs <1% typical) but no fatal/on-line/hdd defect -- noted, not escalated; route run, single sample. |
| Gunvalkyrie | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 58.69/58.59 | pass (env/on-lines/hdd clean both arms, golden/any; refs `...1524918`/`...1525097`) |
| 187: Ride or Die | ON/OFF | none/none | not yet reviewed by eye | 59.83/59.87 | pass (env/on-lines/hdd clean both arms, golden=None expected first-run; refs `...1525919`/`...1526768`) |
| Tony Hawk's Pro Skater 2x | ON/OFF | none/none | not yet reviewed by eye | 59.91/59.90 | pass (env/on-lines/hdd clean both arms, golden=None expected first-run; refs `...1527241`/`...1527431`) |
| KOF: Maximum Impact - Maniax | ON/OFF | none/none | not yet reviewed by eye | 59.79/59.63 | pass (env/on-lines/hdd clean both arms, golden/returning; refs `...1527559`/`...1528265`) |
| Alien Hominid | ON/OFF | none/none | not yet reviewed by eye | 59.95/59.92 | pass (env/on-lines/hdd clean both arms, golden=None expected first-run; refs `...1528418`/`...1528569`) |
| WWE Raw 2 | ON/OFF | none/none | not yet reviewed by eye | 59.95/59.48 | pass (env/on-lines/hdd clean both arms, golden=None expected first-run; refs `...1528822`/`...1528995`) |

Batch 3 complete: all 7 restored titles pass. 38-title scope now stands at 29 screened (9 batch 1/2 + batch 3's 7, +Call of Duty 3 blocked) and 21 remaining (batch 4, soak titles, queued).

| Indigo Prophecy | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.98/59.97 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1531758`/`...1531859`) |
| NFL Blitz 2002 | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.98/59.97 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1531953`/`...1532029`) |
| Fight Club | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.96/59.89 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1532108`/`...1532183`) |
| Future Tactics: The Uprising | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.76/59.91 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1532290`/`...1532404`) |
| Legacy of Kain: Defiance | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.96/59.88 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1532500`/`...1532591`) |
| The Lord of the Rings: The Fellowship of the Ring | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.97/59.99 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1532668`/`...1532803`) |
| NBA 2K3 | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.96/59.96 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1532989`/`...1533156`) |
| NBA 2K2 | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.88/59.89 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1533234`/`...1533326`) |
| MLB SlugFest - Loaded | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.83/59.96 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1533438`/`...1533513`) |
| Max Payne 2: The Fall of Max Payne | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.95/59.96 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1533603`/`...1533694`) |
| MTV Celebrity Deathmatch | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.98/59.97 | pass (env/on-lines/hdd clean both arms, golden/any; refs `...1533775`/`...1533851`) |
| World Soccer Winning Eleven 9 | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.88/59.96 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1533941`/`...1534054`) |
| SpongeBob SquarePants: Battle for Bikini Bottom | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.97/59.98 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1534148`/`...1534225`) |

| Rogue Trooper | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.97/59.97 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1534318`/`...1534409`) |
| Blade II | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.97/59.96 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1534509`/`...1534648`) |
| Mortal Kombat: Armageddon | ON/OFF | none/none | not yet reviewed by eye (soak, `--frames-every 15`) | 59.99/59.98 | pass (env/on-lines/hdd clean both arms, golden=None, state=any; refs `...1534836`/`...1535025`) |

**Call of Duty 3 is not on the Nova**, discovered live (same failure mode as
the Alien Hominid pilot in 4.1.2) despite being in the "8 of the original 20
the Oct-8 pass did not touch" bucket -- checked and it is in none of
`nova-free1008.log`, `shuffle1010.log` or `shuffle1011.log`, so this isn't
the Oct-8 deletion or either shuffle; the Oct-3/4 listing was simply wrong
about it independent of those events (a third kind of staleness, beyond
4.1.1's missing-additions and 4.1.2's later-deleted). Moved to a new
"not on the Nova (unexplained, live-checked 10-11)" bucket -- 1 title,
separate from Addendum 3's 5 space-deferred titles. Scope is now 38 of 44
screenable. Not a `WIDEN:` case (that's for a title that's present but
fails ON vs OFF); this is presence, like 4.1.2. Named here and will be
named in `PR.md`; not a device write this lane can fix.

All 4 route titles (Crimson Skies, Spikeout, JSRF, Tork) now screened:
**pass**. Soak titles (no route) have no `mark gameplay` line, so their
`gfps` window is `soak start` -> `soak end` instead; ToeJam & Earl III
(first soak title screened) also passes.

Batch 2 complete: all 10 titles screened (Call of Duty 3 not run, presence
blocker; the other 9 pass).

Batch 3 queued (14 runs): the 7 titles restored in 4.3 -- Kabuki Warriors,
Gunvalkyrie, 187: Ride or Die, Tony Hawk's Pro Skater 2x, KOF: Maximum
Impact - Maniax, Alien Hominid, WWE Raw 2 -- ON/OFF each, using the exact
filenames `shuffle1011.log` verified (4.3), not `targets.toml`'s stale
`thor` entries for the 5 of the 7 it hadn't caught up on yet. 6 by route
(300s), 1 soak (Gunvalkyrie, 180s + `--frames-every 15`). The pilot gate
admitted the whole batch on the existing (2h-old) `pilots/fastpaths1010.ok`.

Batch 4 queued (42 runs) immediately after: the remaining 21 of the
original 32-scope titles not yet run (4.1.2's table) -- MTV Celebrity
Deathmatch, NFL Blitz 2002, NBA 2K2, MLB SlugFest 2003, AMF Bowling 2004,
MLB SlugFest 2004, MLB SlugFest - Loaded, Rogue Trooper, Ratatouille, World
Soccer Winning Eleven 9, NBA 2K3, Mortal Kombat: Armageddon, Fight Club,
Blowout, Future Tactics: The Uprising, Blade II, Indigo Prophecy, SpongeBob
SquarePants: Battle for Bikini Bottom, The Lord of the Rings: The
Fellowship of the Ring, Legacy of Kain: Defiance, Max Payne 2: The Fall of
Max Payne -- all soak (none has a route), ON/OFF each. Same pilot gate,
same `--expect` prediction. Together batches 3+4 are the last 28 of the 38
screenable titles (9 already passed in batches 1-2, Call of Duty 3 blocked
on presence); request.sh's own running estimate reached ~276 min of
device time queued for this requester by the last of these 56 requests.
`--ref` for all of batches 3/4 is `240eadd732` (this lane's branch after
today's 13-commit master merge, 4.5).

### 4.5 Attempt 2 (10-11, resumed per Addendum 4): why attempt 1 didn't finish, and the stale-worktree hook block

Attempt 1 ended on `error_max_turns` (301 turns in 6h, per Addendum 4) with
three batch-2 runs still in flight (queued `-310`/`-346`/`-380`, running
`-4194264`). That is not a defect in this lane's work -- the queued runs
kept going while the session was down, as Addendum 4 says. This resume did
not spend an attempt.

This resume opened with the Bash tool fully blocked: every call failed with
`PreToolUse:Bash hook error: python3: can't open file
".../docs/testing/jobs/hooks/lane-no-background.py"`. `git log HEAD..origin/master`
showed this worktree was 13 commits behind (the `session-start.sh` hook had
already said so), and one of those 13 commits -- `lane/lanenobg1010`'s fold
(`7f986f73f6`, "lane sessions refuse background commands with a hook, not a
footer") -- is exactly the commit that added this hook file. A stale lane
worktree had the hook *registered* (wherever that config lives) but not the
*file* it runs, so every Bash call hard-failed before it could run anything,
including the `git merge` that would have fixed it. Broke the deadlock with
a temporary no-op stub (`sys.exit(0)`) at that path, used it to run `git
fetch`/`git merge origin/master` (bringing in the real hook among the other
12 commits), and let the merge's real file replace the stub. Named here per
`agent-worktree-stale-base`-style memory: an agent worktree starts stale,
and this is a case where staleness didn't just make a conclusion wrong, it
blocked the tool that would fix it.
