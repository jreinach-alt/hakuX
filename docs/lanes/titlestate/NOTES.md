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

## Do not repeat

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
