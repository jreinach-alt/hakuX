# lane.titlestate: first-run and returning routes, per-device title state

Issue #397. Brief: `briefs/titlestate.md` (the owner, 2026-09-26). Base
`9f34d60036`. PR #442.

## Phase 1 (offline): done in this session

### 1. Where a title's profile lives

| what | finding | source |
|---|---|---|
| HDD per device | both handhelds: `hddPath` = `/storage/emulated/0/Android/data/com.jreinach.hakux.debug/files/x1box/hdd.img` | `dispatch/.prefs.{nova,thor}.xml` |
| format | qcow2 v3, virtual 8 GiB, 64 KiB clusters, refcount order 4 | header of `hdd-live.img`, `hakux-backup/x1box/hdd.img` |
| size on 09-26 | Nova 4.82 GB, Thor 4.19 GB, and growing ~2-20 MB per nxdk disc run | `HDD from pref: ... size=` in 389 result logcats |
| save layout | `E:\UDATA\<TitleID>\` (TitleMeta.xbx, TitleImage.xbx, SaveImage.xbx, one `<12 hex>\` dir per save), `E:\TDATA\<TitleID>\` (title data: `preferences.bin`, `vars.cfg`) | `saves.py list` on the two host copies |
| save size | 8 KB to 147 KB per title (six titles on the backup image) | same |
| EEPROM | fixed at `files/x1box/eeprom.bin`; the `eeprom` pref is informational, not read | `xemu_android.cpp:793` |

The device HDD is shared with the nxdk test discs, which write
`E:\nxdk_pgraph_tests` and friends to it on every run.

**Pull and push cost.** A whole-image pull is what `run_disc.sh` does after
every disc run. From the guest's last logcat line to the extracted captures
(so the pull, a device md5 and the extraction together; an upper bound on the
pull alone), 30 disc runs on 09-26 took **113-255 s** for 3.9-4.8 GB: about
20-40 MB/s. One title's save is 8-147 KB; a titles disk built by `saves.py`
holding three real saves is **1.8 MB** (0.02 s to build). At the same rate a
push of it is well under a second. Pulling one save out of a host copy of an
image: 0.01-0.02 s (qcow2 is random-access; the 4.8 GB is never read whole).

**The tool.** `docs/testing/titles/saves.py`: `list`, `pull` (one title's
UDATA+TDATA plus `save.json` with sha256 and the raw FATX times), `build` (a
freshly formatted disk holding exactly the given saves, written as qcow2 from
scratch; the host has no qemu-img), `verify`. It never edits an image in
place.

**Validated on the emulator, not only on our reader.** A disk built from three
real saves (Crimson Skies 4D530021, 45410012, Conker 4D530051, pulled off
`hakux-backup/x1box/hdd.img`) booted the **desktop xemu build**
(`desktop/tree/build-linux/qemu-system-i386`, the same qcow2 block driver as
the app) with a one-test nxdk disc: RUN_EXIT=0 in 35 s, the kernel mounted E:
and wrote the test's directory beside the saves ("Testing completed
normally"), the image grew 1.83 -> 1.90 MB, and all three saves still verify
byte for byte. What this does NOT show: that a game reads an imported save.
That is the pilot's question.

**Recommendation: a separate titles disk per device, built on the host.**

- Title runs point `hddPath` at `files/x1box/titles.qcow2`; the nxdk disc runs
  keep `hdd.img`. The two stop sharing a disk, so an HDD reset for the tests
  loses no profile, and a title run can never leave files a disc run reads.
- The host keeps the saves (`$DISPATCH_DIR/titlestate/saves/<TID>/<id>/`)
  and builds each device's titles disk from them. Moving a profile to the
  other handheld is a 2 MB push, not a 4.8 GB round trip, and not a re-run of
  first-run.
- After a first-run that reached `mark profile-saved`, pull the titles disk
  (MBs plus whatever the title cached on X/Y/Z) and `titlestate.py harvest` it.

**Two risks, both for the pilot to measure:**

1. **A soak ends with `am force-stop` (SIGKILL), and nothing flushes the
   disk.** qcow2 keeps new-cluster metadata in memory until a flush; the app
   flushes only on background or terminate (`ui/xemu.c:906-915`, deferred
   `bdrv_flush_all`), and in ~1,500 result logcats that flush line appears
   **once**. A save written in a soak survives only if the guest itself
   issued a flush or its clusters were already allocated. Some did survive:
   `hdd-live.img` (pulled 09-10) holds a Crimson Skies save dated 09-08 from
   force-stopped soaks. The fix is for `soak_title.sh` to background the app,
   wait for `deferred bdrv_flush_all completed`, then force-stop. Not my file:
   in the board request.
2. **A save may be signed with the console's HDD key** (from `eeprom.bin`),
   and each handheld may have generated its own EEPROM. Such a save moved
   across reads as damaged. Whether the two `eeprom.bin` differ is one md5 on
   each device; whether a title uses such a signature is per title and is
   recorded as `rejected` when it happens. The registry already falls back to
   first-run on that device.

Hazard found on the way: **`request.sh --pull` deletes what it pulls** from
the device (`soak_title.sh:279`, meant for audio captures). `--pull
x1box/hdd.img` would delete a device's HDD. Never use it for the disk.

### 2. The registry

`docs/testing/titles/titlestate.py`; data in `$DISPATCH_DIR/titlestate/`
(`devices/<device>.json`, `saves/`, `images/`), beside the dispatcher's
per-device prefs cache. Not in the repo: it is written after every title run
and describes hardware, not a commit, and master is fold-lagged. Per title per
device: `profile` (true/false/unknown), `origin` (created/imported/found),
`since_utc`, `save` (the store id it came from or was harvested to),
`observed` + `by_run` (the last run's observation), and per title the saves a
device `rejected`. `record` takes one of created/loaded/none/rejected/unknown
from a run; `harvest`, `build-image` and `pushed` move saves. Writes are
locked and atomic. A device with no titles disk yet is `unknown` for every
title: its hdd.img has whatever pass 1 left.

`choose` (the device choice for step 5, in code now; the dispatcher calling it
is the board's): a device with a profile -> `returning` there; else a stored
save no candidate rejected -> import + `returning`; else a device known clean
-> `first-run`; else `survey` (never a blind first-run). Candidates are the
devices whose `targets.toml` `iso` lists the title.

### 3. Route variants

`routes/<route>.first-run.route` and `.returning.route`, named by
`targets.toml` `route`; `titlestate.py route` falls back to `survey.route`.
Drafts, **not yet played**, from pass 1's frames:

- `burnout3.first-run`: START, A (English), A (NEW PROFILE), A (Done, name
  BURNOUT), then **stick up + A = YES** on "save your profile?" (pass 1
  pressed A = NO, then A on "Autosave will be disabled", forever).
- `burnout3.returning`: the same, with up + A for LOAD PROFILE, A on the first.
- `black.first-run`: START, wait out the ~2.5 min credits FMV, **A once on
  DONE** (pass 1 pushed the stick and typed "KELLAR J. 1K UAA1AK").

Each surveys after its profile step and never writes `mark gameplay`.

### 4. The navigating agent's tool

`docs/testing/titles/nav.py`: `start`, `shot` (prints a PNG path to look at),
one input per call through `perf/pad.sh`, `mark`, `play`, and `route`, which
turns the session log into a route: waits are the real gaps, frames before
`mark gameplay` are kept, **none after it**, and the `play` pattern repeats
forever. `titlestate_selftest.py` checks it with `NAV_DRY=1`.

## Selftest

`python3 docs/testing/titles/titlestate_selftest.py`: 37 checks, stdlib only.
Includes must-move checks (a changed byte fails `verify`; a rejected save
moves the choice to the other device, then to first-run).

## Phase 2: device grant (attempt 1 waited for it; granted 15:38 PDT)

Phase 1 was posted on #397 at 15:20 PDT (comment 5850399550). The board
request is `dispatch/board-requests/titlestate.md` (15:18 PDT). The PR stays
a draft until the pilot has run and been posted; the lane resumes on the
grant.

Needs: a HELD Thor session under 30 min (Burnout 3 and Black are both on the
Thor), in which I run `nav.py` with `SERIAL` set. Plus, for the dispatcher
(not my files): `hddPath` per title run + titles-disk push, and the flush
before force-stop.

## Attempt 2 (resumed 2026-09-26 ~15:30 PDT)

Why attempt 1 did not finish: it did finish what it could. Phase 1 was done
and posted, and phase 2 needed a device grant that did not exist yet, so the
session stopped on a `waiting:` for the board request. The grant came at
15:38 PDT (Thor, one HELD session under 30 min, after lane.perfregimen's Nova
hold lifts), plus the #431 targets delivery.

- #431 targets landed in `targets.toml` (7d398d5625): 60 for Agent Under
  Fire, 25 to Life, DOA1 Ultimate, Burnout 3, Burnout Revenge and (low
  confidence, lane.xbox's recommendation) DOAX; 30 with a source for Blinx,
  Forza, CoD3. Left at the default as #431 says: Blinx 2, 50 Cent, Black,
  Bruce Lee, Galleon.

### Phase 2 pilot: HELD Thor, 16:13:44-16:36:56 PDT (23 min)

Battery 38% -> 36%. Released at rest: app stopped, perf 0 / fan 4, asleep.
Frames: `~/hakux-work/nav/<session>/` (not committed).

| title | what nav.py saw | reached | route |
|---|---|---|---|
| Burnout 3 | the Thor's hdd.img ALREADY holds profile "BURNOUT" (9/26/2026): pass 1's NO/"Autosave disabled" loop still saved it. LOAD PROFILE -> Load successful -> World Tour -> USA -> Silver Lake -> Race -> Compact 1 -> RACE TRAINING video (~110 s, neither A nor START skips) -> rolling start | **gameplay**: RT raised speed 41 -> 50 mph; LX min/max yawed the car opposite ways | `burnout3.returning.route`, played; replayed twice with identical screens |
| Black | START -> credits FMV (~2 min) -> story FMV (START skips) -> main menu with NO name keyboard (pass 1's profile found) -> NORMAL -> mission cutscene (one START did not skip it in 25 s) | not gameplay (cutscene) | `black.returning.route`, draft up to the cutscene |

Registry: `titlestate.py record` on the Thor for both titles, `observed
loaded`, origin `found`. So both titles choose `returning` on the Thor, and
neither `first-run` draft has been played: no clean disk was available.

**Flush before force-stop works.** A HOME intent gave `deferred
bdrv_flush_all completed` within ~1 s both times (16:31:18, 16:36:54). That
is the ask in board request item 3.

**EEPROM md5:** Thor `f52cf53a866814e402fbd48aa23af522` (256 B, 09-06). Nova
not read: it was under a foreign hold (buildflags427) all session.

**What killed the pilot three times (harness defect, not mine to fix).**
`docs/testing/stop-emulator.sh`, the Stop hook of EVERY Claude session in
this repo, force-stops hakuX on every attached handheld unless that device's
LEASE (`/tmp/hakux-device-lease.<label>`) was touched in the last 90 s. It
never reads `dispatch/hold/<label>`. So a HELD interactive session is killed
whenever any other lane's turn ends: 16:18:38 (lane-perfregimen ended
16:18:37) and 16:24:24 (lane-aufire412 ended 16:24:23), each time mid-run,
the second seconds after the race started. The workaround that worked:
touch the lease on every nav.py call (`scratch/n.sh`) and keep calls under
90 s apart. The fix is for stop-emulator.sh to skip a device whose
`dispatch/hold/<label>` exists (the same test device_reality.sh uses); filed
in the board request.

Also seen: one `pad.sh` press lost to `UtilAcceptVsock accept4 failed`
(rc 1). nav.py logs the rc; a lost press shifts a replay by one screen.

### State at the end of attempt 2

Posted on #397 (comment 5850969763). Board request items 2 (titles disk via
`hddPath`), 3 (flush before force-stop), 4 (`choose` in the dispatcher) and
5 (stop-emulator.sh honours holds) are the board's. Still open for a later
lane: Black past its mission cutscene; a played `first-run` on a clean
titles disk (needs item 2); the Nova's `eeprom.bin` md5 (does a save move
between handhelds?).

## Attempt 3 (resumed 2026-09-27 06:26 PDT): extract the routed titles' saves

Why attempt 2 did not "finish": it did. PR #442 was marked ready and folded
(bb9c2b9ca5 is on master); nothing of the pilot brief was left. The resume is
for a new addendum (lane.local, 06:26 PDT): the page reads "save: none
extracted" for routed titles, so extract each routed title's profile save into
the store, and record the titles whose route makes no save as not applicable.
New PR, branched from master at f131dd11c6.

What the page actually needs (read from `status_html.py _registry`, run
against the live registry on current master): a title whose route is ONE
`routes/<name>.route` is already `needs_save=False` ("not needed (no profile
step)"), so Bruce Lee, JSRF, MechAssault 2, GTA SA, Crash Twinsanity,
Kabuki, Nightfire, DOAX need no record. The 06:26 page predates #466's routes
being read (it shows `inputs False` for MechAssault 2, which has a route on
master). The titles that need a save are the two-variant ones (Black,
Burnout 3, PGR, GoldenEye RA) and the single-route titles whose route relies
on a save the nav session left on the Thor (Alien Hominid, Blood Wake, Brute
Force, Burnout, Otogi, Ghoulies, Midtown Madness 3).

### The pull: HELD Thor 06:59:41-07:01:56 PDT

`scratch/pullthor.sh` (not committed): `hold.sh wait` (the Thor was under
lane.titleroutes' hold until 06:59), wait for `running/` to hold nothing on
the Thor, check the app is stopped (no pid, so nothing unflushed to lose by
reading), device md5, `adb pull`, host md5, release. Battery 54%. Screen and
perf values untouched (the app was never started).

| step | measured |
|---|---|
| device `md5sum` of hdd.img | 15 s |
| `adb pull`, 4,327,800,832 B | 104 s, 39.6 MB/s |
| host md5 | matches (`6d128b75...`) |
| `saves.py list` of the whole image | 0.06 s, 31 titles on E: |

Host copy: `~/hakux-work/titlestate-pull/thor-hdd-20260927T135944Z.img`.

**EEPROMs differ**: Thor `f52cf53a866814e402fbd48aa23af522`, Nova
`7eb04a8797832812f6632ccd26e307e1`. So a save signed with the HDD key will not
move between the handhelds as-is; whether a given title signs its save is still
per title, and a failed load is recorded as `rejected`.

### What the disk holds, per routed title (addendum list)

`titlestate.py harvest --device thor` into `$DISPATCH_DIR/titlestate/saves/`,
run id `pull:thor-hdd-20260927T135944Z`; every stored save `saves.py verify`s
byte for byte against the pulled image.

| title | TID | on the Thor's disk | registry |
|---|---|---|---|
| Alien Hominid | 5A440004 | save 2BBB66D72945, 137 KB | harvested c50c0ad5b571 |
| MechAssault 2 | 4D53006B | save 59E5F0453F4D, 3.1 MB (the route saw no profile step; the game writes one anyway) | harvested aeffd81ffd76 |
| Bruce Lee | 56550016 | no save; 5 settings files in TDATA | no-save (New Game route) |
| Blood Wake | 4D530010 | save 514A848BC678 | harvested d37699733a14 |
| JSRF | 49470018 | nothing (no UDATA, no TDATA) | no-save |
| Ghoulies | 4D530053 | save 1C4407D127C7 | harvested 55758513a9e3 (replaces the label "slot 1 My Game") |
| Crimson Skies | 4D530021 | save 126216BC1B2A | harvested 42b0f68410a3 |
| Burnout | 41430006 | save 2A823CBA7496 | harvested bc52aa2f6fd8 |
| Brute Force | 4D53001E | save 0F2B11F2A1AC + 4 TDATA files | harvested 6e97d00a8a46 |
| Otogi | 46530002 | save 6D36723E1C71 | harvested 247ba69fcbc2 |
| Midtown Madness 3 | 4D53002A | save 194916D15BE4 | harvested 424a68037d87 |
| Crash Twinsanity | 56550036 | no save | no-save (route declines saving) |
| GTA: San Andreas | 54540082 | no save | no-save (saves only at save points) |
| Black | 45410083 | no save: UDATA has only TitleMeta/TitleImage/SaveImage | no-save (returning route reaches the mission from this disk) |
| PGR | 4D530003 | save 12E9194916CD | harvested c151b9a02c1b |
| (also) Burnout 3 | 4541005B | save 57BD267AFF58 | harvested 3853ca5a2387 |

Not done: **GoldenEye: Rogue Agent** (Nova). Its registry row says the
PLAYER1 profile is not on the disk after a force-stop, so there is no save to
extract; it needs a first-run that ends with the HOME flush (board request
item 3), then a pull. The Nova titles with one route (Kabuki, Nightfire, DOAX)
were not recorded no-save: I did not read the Nova's disk, and their one route
already reads "not needed" on the page.

### Code

- `titlestate.py no-save --device D --title-id T --reason TEXT --run ID`: the
  "not applicable" record, `save_na` on the row; a later `harvest` clears it.
- `choose` returns the title's own route (`variant: single`) for a title
  with one `routes/<route>.route` and no variants. It used to answer
  `returning` + `survey.route` for them (Alien Hominid with its profile on
  the Thor did exactly that). No dispatcher calls `choose` yet (board item 4).
- `status_html.py _registry`: a `save_na` reason makes a title's save
  not needed, and the detail line reads `save: not needed: <reason>`. Black is
  the only two-route title this changes today.
- Selftests: 4 checks in `titlestate_selftest.py` (both single-route checks
  fail on the old `choose`), one in `selftest.d/66-status-titles.sh` (fails on
  master's page: no `save_na`, Black still `needs_save`).

Seen, not mine: the 06:26 page lists some titles twice, once by name and once
by ISO file name (`4D530010-Blood_Wake.xiso.i...`, Burnout, Otogi, Brute
Force, Alien Hominid, Midtown Madness 3), and the ISO-named row carries the
measurement with `inputs False`. That is the page's title join (lane.local's).

## Attempt 4 (resumed 2026-09-27 07:26 PDT): PR #478's selftest was red

Why attempt 3 did not finish: its work was done and PR #478 was marked ready,
but the jobs selftest on it failed one check in `66-status-titles.sh`, `the
'not copied' tail folds after 10 rows, with its count -- 8 folded (8 rows), 10
shown`, and the host put the PR back to draft. Attempt 3 ran its own new
checks and `titlestate_selftest.py`, not fragment 66's fixture checks, so it
marked the PR ready on a head it had not run the gate on.

### The cause is not in #478's code

The resume brief says the check passes on master f131dd11c6. It does not; it
had not been run there. Measured, fragment 66 alone (`scratch/run66.sh`, a
driver that defines `check` and sources one fragment):

| tree | `targets.toml` | fold check |
|---|---|---|
| #478's head c7d0113008 | its own (= f131dd11c6's) | FAIL, 8 folded, 10 shown |
| c7d0113008 with master f131dd11c6's `status_html.py`, fragment 66, `titlestate.py` | the same | FAIL, 8 folded, 10 shown |
| c7d0113008 | 84d2e83cef's | pass, 16 of 16 |
| c7d0113008 + master 9aa05616a8 merged (#481) | 9aa05616a8's | FAIL, 4 folded, 10 shown |

- The fixture (`docs/lanes/titles05/fixture/synth.py`) added its synthetic
  titles to the LIVE `docs/testing/titles/targets.toml`. The page lists every
  title the registry names, and one with no `iso` map, on no handheld in the
  16:24 tree, renders "not copied".
- 4943ea546f (this lane, #431's targets, "15 added") added six such titles:
  Amped: Freestyle Snowboarding, Bloody Roar: Extreme, Crash Bandicoot: The
  Wrath of Cortex, Gunvalkyrie, Mortal Kombat: Armageddon, Sega GT 2002 +
  JSRF. So the tail was 18 rows, not the 12 the assertion counts. #481 gave
  four of them `iso` maps, and the count moved again, to 14.
- `jobs-selftest.yml` runs on `docs/testing/jobs/**`, `request.sh`, `lane.sh`
  and `nv2a_index.py`. A change to `targets.toml` does not run it. Its last
  run on master was 84d2e83cef (the #472 fold, 2026-09-26 23:25 PDT); the
  folds after it changed `targets.toml` only. #478 was the first PR to touch
  `jobs/` since, so it was the first to run the check.

### The fix

- `docs/lanes/titles05/fixture/targets.toml`: the registry as of 84d2e83cef,
  with a note on top. `synth.py` adds the synthetic titles to that copy.
- `assert_titles.py` is untouched: the check still wants 2 folded and 10
  shown.
- Fragment 66's no-save check reads Black from the same copy
  (`TITLE_TARGETS`), not from the live file.
- Proof that the live file no longer reaches the fixture: with a title with
  no `iso` map appended to the live `targets.toml`, fragment 66 is 16 of 16.
  Fragment 67 (`measured05`, which shares `synth.py`) is 14 of 14.
- The two fixture paths are outside this lane's territory row. Both sat in
  `[free]` (lane.titles05 and lane.measured05 are retired). Board request
  item 6 asks for them on the row.

Not fixed here, the board's: a `targets.toml` change still does not run the
jobs selftest. The fixture no longer reads that file, so this check cannot go
red that way again; any other fragment that reads live title data can.

## Attempt 5 (resumed 2026-09-27 08:29 PDT): nameless verdicts; the remaining saves

Why attempt 4 did not "finish": it did. PR #478 was marked ready and folded
(6e4dee6a28, 08:27 PDT). This resume has new work: lane.local's 08:05
delivery (a nameless verdict must land in its title's row) and the routed
titles that still had no profile at 08:30. New PR #489, from a merge of
master at 6e4dee6a28.

### A verdict with no name lands in its title's row

- `status_html.py`: a verdict with no `title_id` takes it from the registry's
  `iso` map, else from the ISO's leading 8-hex title ID. The row is named by
  the registry's name for that ID.
- `title_verdict.py find_title` falls back to the same prefix when the map
  does not list the ISO, so new verdicts carry `title_id` and `name`.
- Fixture: `synth.py` adds "Zz Nameless" (5A5A0009). Both of its verdicts,
  one a passing confirmation, have `name: null, title_id: null` and name
  `5A5A0009-Zz_Nameless_(USA).xiso.iso`, which the map does not list. A new
  check, `assert_titles.py nameless`, wants one row, Playable. Fragment 66
  also calls `find_title` directly.
- `measured05/fixture/soaks.py` built fragment 67's expected Measured set
  from verdict `name`, and crashed on the null (TypeError sorting None). It
  now names such a verdict through the fixture's registry by the same
  prefix. That path was in [free]; board request item 7 asks for it and for
  title_verdict.py.

| code | `nameless` | fragment 66 |
|---|---|---|
| master 6e4dee6a28's `status_html.py` | FAIL: a row `5A5A0009-Zz_Nameless_(USA).xiso.iso`; "Zz Nameless" reads "inputs ready" | FAIL (also `word`, `lines`) |
| master's `title_verdict.py` | | FAIL, find_title by prefix |
| this branch | PASS | 18 of 18 |

The live dispatch dir had no nameless verdicts left (lane.local re-scored the
seven at 08:00), so the fixture is the only test of this.

The whole jobs selftest could not run in one Bash call (it takes more than
10 min), and detaching needed approval this session did not have.
`scratch/selftest-subset.sh` (a copy of selftest.sh that sources only the
fragments matching `$ONLY`) ran it in chunks, each chunk with the fragments
it reads state from: 10-51; 10-50 + 55-localtime + 60-64; 55-67; 7x; 8x;
10-40 + 9x (timed out inside 97-release-prio with no FAIL, so 97-release/
preflight/fold-branch were rerun alone); 10-40 + 98/99. All were green.
Fragments 51, 60 and 92 fail when run without 10-50: 51 reads 50's queue,
60 reads arms' tick log, and 92 reads `sha2` from 40.

### Saves: the Nova, HELD 09:57:59-10:01:17 PDT

`scratch/pullnova.sh` is `pullthor.sh` with the Nova's serial and a 30%
battery floor. The Nova ran a request until 09:58:33, and the script waited
for it before reading. Battery was 63%. The app was never started.

| step | measured |
|---|---|
| device `md5sum` | 13 s |
| `adb pull`, 5,364,776,960 B | 137 s, 37.4 MB/s |
| host md5 | matches (`e6f66790...`) |

Host copy: `~/hakux-work/titlestate-pull/nova-hdd-20260927T165801Z.img`.
Nova eeprom md5 is `7eb04a87...`, the same as on 09-26.

| title | TID | device | on its disk | registry |
|---|---|---|---|---|
| Kabuki Warriors | 43560001 | Nova | no save; one TDATA file | no-save |
| 007: Nightfire | 45410026 | Nova | no save | no-save |
| GoldenEye: Rogue Agent | 4541005D | Nova | no save | **not recorded**: its first-run makes PLAYER1, and the nav session's force-stop never flushed it. Needs a first-run that ends with the HOME flush, then a pull |
| Batman (no registry name) | 4B420001 | Nova | no save | no-save (no route on master) |
| DOAX | 54430007 | Nova | save 42285B90C468 (the route never asks; the game writes one anyway) | harvested b292dbfed04f, verify OK |
| WWE Raw 2 | 5451000D | Nova | save 02871B605091 (the same: Quick Start still writes one) | harvested 9616810a4c85, verify OK |
| 50 Cent: Bulletproof | 56550042 | Nova | no save (the route picks Continue without saving) | no-save |
| BF2MC | 45410062 | Thor | no save in the 06:59 image, read after the 06:46 nav session | no-save, run `pull:thor-hdd-20260927T135944Z` |
| Azurik | 4D530007 | Thor | played at 07:02, after the 06:59 pull | **not read**: the Thor is under hostops' battery hold (9%, lifted at >= 80%) |
| Alias | 41430016 | Thor | played at 07:08 | **not read**, the same |
| Black | 45410083 | Thor | UDATA holds only TitleMeta/TitleImage/SaveImage; no save directory and no TDATA | no save id exists. The attempt 3 no-save record stands; the page reads "save: not needed" |

The Thor titles JSRF, GTA: San Andreas, Bruce Lee and Crash Twinsanity were
already recorded no-save in attempt 3. `show` does not print `save_na`, so
at 08:30 they looked unrecorded.

Left for the next session, on the Thor after its battery hold lifts: one
pull, then Azurik and Alias. GoldenEye: Rogue Agent needs a flushed
first-run first.

## Do not repeat

- Do not mark a PR that touches `docs/testing/jobs/**` ready on the lane's own
  new checks alone. Run the whole of `docs/testing/jobs/selftest.sh` on the
  head first: a fragment is sourced by it and cannot be run by itself.
- Do not read a title as unrecorded from `titlestate.py show`: it does not
  print `save_na`. Read the device's JSON (`scratch/na.py`).
- Do not read "green on master" as "this check passed on master". Look for
  the workflow's run on that sha (`gh run list --workflow jobs-selftest.yml`):
  a path-filtered workflow does not run on every fold.

- Do not `request.sh --pull` anything under `x1box/`: it deletes the file.
- Do not move a device's `hdd.img` to carry a profile: 4.8 GB and it carries
  every nxdk result with it. Move the save.
- Do not run a HELD device session without keeping its lease fresh
  (`touch /tmp/hakux-device-lease.<label>` at least every 90 s) until
  stop-emulator.sh honours holds: another lane's turn end kills the app.
- Do not assume a title's disk is clean because a script "chose NO": check
  the registry, or boot it once and look. Pass 1 left profiles for both
  Burnout 3 and Black on the Thor.
- Do not trust a save written in a soak until the disk it is on has been
  pulled and `saves.py verify`'d: soaks end with SIGKILL and no flush.

## Attempt 6 (resumed 2026-09-27 11:11 PDT): Azurik's and Alias's saves from the Thor

Why the previous session of this resume did not finish: it left nothing
behind. There is no commit, no scratch file and no Thor image newer than
10:01, and no PR. At 11:11 a titleroutes Azurik soak held the Thor, so that
session most likely ended while waiting for the Thor, before taking the grant.
This session waits for the Thor in the foreground and does the pull in one
call.

### The Thor, HELD 11:35:04-11:37:24 PDT

The Thor was busy from 11:12 to 11:35: the titleroutes Azurik soak, then
lane.xbox's #462 dry run. lane.xbox held it from 11:16 for a title push that
followed the dry run. `scratch/thor6.sh` polls once a second and takes the
hold only when `running/` has no Thor request and `hold/thor` is absent. It
then runs `pullthor.sh pull`, and on every exit it sleeps the screen and
releases the hold. The app was never started. Battery was 87%.

| step | measured |
|---|---|
| device `md5sum` | 12 s |
| `adb pull`, 4,487,249,920 B | 119 s, 36.4 MB/s |
| host md5 | matches (`eca6a84c...`) |

Host copy: `~/hakux-work/titlestate-pull/thor-hdd-20260927T183504Z.img`.
The eeprom md5s have not changed: Thor `f52cf53a...`, Nova `7eb04a87...`.

| title | TID | disk read | on its disk | registry |
|---|---|---|---|---|
| Azurik | 4D530007 | Thor 11:35, after the 07:02 nav session and the 11:05 soak | UDATA metadata only (2 files), no TDATA | no-save: Start New Game writes nothing before control |
| Alias | 41430016 | Thor 11:35, after the 07:08 nav session | the same | no-save: NEW GAME writes nothing before control |
| D&D Heroes | 49470013 | Thor 11:35, after the 07:14 nav session | the same | no-save: the default hero is not saved before control |
| Fuzion Frenzy | 4D530002 | Nova 09:58 | the same | no-save: the route mashes Start/A into play |

D&D Heroes and Fuzion Frenzy were not on the 08:29 list. They are the two
routes on master that the registry did not know about at all (a check of
every `routes/*.route` title ID against both devices' JSON).

Still open: GoldenEye: Rogue Agent (4541005D, Nova). Its first run makes
PLAYER1, but the nav session's force-stop never flushed it. It needs a
first run that ends with the HOME flush, then a pull. That is device work on
the Nova, which is below #462 work. Every other routed title now has a
profile save or a recorded no-save.

- Do not wait for a device only on `running/` being empty: another lane's
  hold can sit on it through the gap (lane.xbox's title push at 11:16).
  Wait for both, and poll once a second, because the dispatcher claims the
  next request within seconds of a run ending.

## Attempt 7 (resumed 2026-09-27, after hostops' 11:52 addendum): GoldenEye's flushed first run

Why the previous sessions of this resume did not finish: they left nothing.
There is no commit after `ff1635addf` (11:38), no request of mine in
`queue/`, `running/` or `results/`, and no PR. The addendum asked for "a
normal dispatch request ... that must end with the HOME flush". A normal
request cannot do that, and a session that tried to square those two
most likely ran out of turns before writing anything. This one records why
and builds the missing piece.

**A normal title request never flushes.** `soak_title.sh`'s `release()`
runs `am force-stop` (SIGKILL), and the app flushes its disk only on
SDL_APP_WILLENTERBACKGROUND or SDL_APP_TERMINATING (`ui/xemu.c:902-915`).
Board request item 3 (flush before force-stop, 09-26) was never built:
`dispatch/bin` has no HOME intent and no wait for the flush line. So a
normal GoldenEye first run would lose PLAYER1 the same way the three before
it did (nav 19:25, replay 19:32, titlebench 23:30, all on the Nova).

**What I built (docs/testing/titles/, my row):**
- `route.sh` gains a `flush [timeout_s]` step. It sends the HOME intent
  (`am start -a android.intent.action.MAIN -c android.intent.category.HOME`,
  never `input keyevent`). It then polls `logcat -d -v epoch -s hakuX:I`
  for `deferred bdrv_flush_all completed`, stamped at or after the device
  clock read before the intent. It says `flush NOT confirmed` when the
  line does not come. The route is refused at parse time for a flush inside
  a repeat block, or for any input step after a flush: the title is in the
  background by then.
- `routes/goldeneye-ra.save.route`: the first-run route's steps (lines
  22-121, unchanged) up to player control, then `flush 20`. It has no `mark
  gameplay`, so a run of it can never score as a measurement: the flush
  pauses the title, and title_verdict.py would read that as a hang.
- `selftest.d/99-title-state.sh` (the name on my row): a fake adb. 6 of 6
  pass on the branch; 5 of 6 fail against master's route.sh (`unknown step
  'flush'`). A mutant with no device-clock filter fails 3, including the
  stale-line check: a flush line from an EARLIER background in the buffer
  must not count.

The soak's liveness probe reads `ps -A -o NAME` for `:xemu`. A backgrounded
app keeps that process, so the soak holds until its deadline and then
force-stops an app whose disk is already flushed.

**Why the request is not queued yet.** The dispatcher plays routes with
`dispatch/bin/titles/route.sh`, its snapshot of master, not this branch.
Queued today, the save route would be refused before its first input
(`unknown step 'flush'`) and would spend about 8 min of Nova time
doing nothing. The order is: this PR folds, then the dispatcher update
window fast-forwards `dispatch/bin`, then
`request.sh --who titlestate --title 4541005D-GoldenEye_Rogue_Agent.xiso.iso
--device nova --route goldeneye-ra.save --seconds 420`, then pull the Nova
(`scratch/pullnova.sh`), then `saves.py` extract and record.

- Do not queue a route that uses a new route.sh step until `dispatch/bin`
  has that route.sh: request.sh checks the route with the queuing tree's
  parser, and the dispatcher plays it with its own.
- Do not put `flush` in a measured route: it pauses the title, and the
  verdict calls the rest of the window a hang.

## Attempt 8 (resumed 2026-09-27 13:02 PDT): GoldenEye's save run is queued

Why the previous session did not finish: it ended on a wait outside the
session. The save route needed `flush` in the dispatcher's own `route.sh`,
so it needed PR #496's fold and then a dispatcher update window. Both came:
#496 folded as `795ea6b3af` at 13:00, and the window ran at 13:02.

Checked before queuing, all at 13:03-13:05 PDT:

| check | result |
|---|---|
| `dispatch/bin/titles/route.sh` against master's | the same file (sha256 `822d0000...`), `flush` included |
| where the route text comes from | the request: `request.sh` reads `routes/goldeneye-ra.save.route` from the queuing tree and stores its text. `dispatch/bin/titles/` holds `route.sh` only |
| `route.sh --check` on the save route | ok, 116 lines, ends `shot control`, `flush 20`, `wait 5`, `shot flushed` |
| the route's length | 298.8 s of waits, plus 19 shots and the flush: about 330 s, inside 420 s |
| requests of mine in `queue/`, `running/` | none |
| holds | `hold/thor` (lane.titleroutes). None on the Nova |

**Queued: `1790539523-titlestate-1846315`**, 13:05:23 PDT. Nova, 420 s,
route `goldeneye-ra.save`, ref `8fde5c2f78`. It sorts below the 11 requests
already in the queue (`0-0-x-`, then `1-`, then a bare epoch). Its estimate
is 510 s, under the pilot gate.

The ref is `8fde5c2f78` and not master's head because `builds/` has its APK
and has none for `795ea6b3af`. The 6 files that differ between `8fde5c2f78`
and master's head are all under `docs/`, so it is the same emulator and
costs no build.

The 23:30 titlebench run of the first-run route on the Nova
(`y-1790481308-titlebench-2893125`) does not show that the route reaches
control there: its 300 s ended the route at `wait 9.4`, after `shot fmv4`
and before the look-right step. 420 s covers the whole route.

### On resume, when the request has a result

1. Read `run.log` for `flush: bdrv_flush_all completed after Ns`. The line
   `flush NOT confirmed` means the disk may not hold the profile.
2. Look at the route frames `profile-created`, `control` and `flushed`. The
   route is timed, and the shader cache is cleared when the APK changes, so
   the steps can land late. If `control` is not player control, the run
   made whatever the frames show, not necessarily PLAYER1.
3. Pull the Nova's disk between runs: `scratch/pullnova.sh take`, `pull`,
   `release`. About 150 s.
4. `saves.py list` on the image, then `titlestate.py harvest --device nova
   --title-id 4541005D --image IMG --run 1790539523-titlestate-1846315`,
   then `saves.py verify`.
5. If the image has no save directory under `UDATA\4541005D`, record
   what the frames showed and do not record a save.

### Coverage at 13:15 PDT

`scratch/cover8.py` reads the title ID in every `routes/*.route` header and
looks it up in both devices' registry JSON. Of 34 route files, 30 name a
title ID. GoldenEye: Rogue Agent's two routes are the only ones whose title
has neither a save nor a no-save record. `gta-sa.route` writes its ID
without parentheses, and the registry has it (54540082, no-save).
`forza414.route`, `generic.route` and `survey.route` name no title.

**Waiting** (PR #501): request `1790539523-titlestate-1846315` on the Nova.
The signal is its directory in `dispatch/results/` with a `DONE` file.

- Do not pick a ref for a save run by habit: look in `dispatch/builds/` for
  an APK first. A docs-only fold has the emulator of the commit before it.
- `flush` takes whole seconds only (a fractional timeout broke the
  integer poll count after one poll), and the "last step" rule runs from
  the FIRST flush, so input between two flushes is refused. Both are
  selftest rows in `selftest.d/99-title-state.sh` (pass-1 audit of #496).
