# lane.savestate433: every title run starts from a known profile

Issue #433 (0.5: 50 Playable). Brief: `briefs/savestate433.md` (owner, 2026-10-02
~20:05 PT). Base `9550493846`, plus lane/buildstamp (`568ec87e95`, merged as a
fast-forward because it also edits `dispatcher.sh`; its guard is kept).

Session 1: 2026-10-02 19:57-20:4x PDT.

## What changed, in one paragraph

A title run's titles disk is no longer "whatever the device's last run left".
Every title has at most one **golden** profile (`$DISPATCH_DIR/titlestate/golden.json`).
Before a title run, the disk is **composed** from the goldens: every title's
golden, minus the run's own title when its route is `first-run`. A harvest after
a run goes to the title's `latest` slot and never touches its golden. Only
`titlestate.py promote` replaces a golden, and the replaced one goes to
`history`. No save is ever removed. Every route declares `# state:
returning|first-run|any`. `request.sh --route` resolves a variant family by the
golden and **refuses** a route whose state the disk cannot match, before any
device time. nav.py, pathfind.py and `titlestate.py prepare/release` give held
sessions the same disk. The soak now stops when its route dies.

## A. One archived profile per title

| piece | where |
|---|---|
| golden / latest / history per title, TitleID aliases | `titlestate.py` GOLDENS (docstring), `golden.json` |
| `promote` (the only way a golden changes), `propose-all [--refresh]`, `import-save`, `first-run-saved` | `titlestate.py` |
| the disk for a run: `compose(device, title, state)` | `titlestate.py` |
| `plan()`: keep only a pristine disk of exactly the composed goldens; `preserve` (pull whole to `unharvested/`) instead of keep-over-a-failed-harvest; `refuse` | `titlestate.py` |
| dispatcher: title + state from the request, `refuse` -> ERROR before the soak, `preserve`, hdd.json records `title_id`, `disk_title_id`, `state`, `save`, `loaded` (golden/none), `golden_status` | `dispatcher.sh` `titles_disk_prepare` |
| first-run that reached `mark profile-saved` on a title with no golden: its harvested save becomes the golden | `dispatcher.sh` `titles_first_run_golden` |

**A profile is a save directory.** A harvest that holds only title data
(`TDATA`, `TitleMeta.xbx`) is not a profile. Castlevania's newest harvest
(`53f0a40fe626`) is such a harvest, while `20235e93867b` holds the slot-1 save
its returning route continues from. That is the 10-01 17:01 New Game run. So:

- a `returning` disk from a settings-only golden is refused;
- a variant family resolves to `.first-run` when the golden has no save directory;
- `propose-all` prefers the newest verified harvest that has a save directory.

**TitleID aliases.** `targets.toml` keys are the compat CSV's canonical ids, not
the disk's: DOA3 is `4D53002D` there and `54430001` on the disk; JSRF is
`49470018` / `5345000A`; Gunvalkyrie is `49470017` / `5345000B` (its TitleMeta
spells it "Gunvalkrye"). Without an alias, a first-run disk keeps the save it
was meant to drop. `titlestate.py alias [--suggest]`.

**Seeded live (20:17 PDT, `seed_goldens.py`, idempotent):**

- **Blinx 2 (4D530065): GOLDEN `377a8488c7c5`**, the owner's own save from the
  19:23 hdd-reset backup (`dispatch/hdd-reset/nova-20261003T022340Z/`):
  Team01 "Jaguars" (`13C91777168C`) and Team02 "Tigers" (`13C91777168D`).
  Neither of the two Blinx 2 saves already in the store was this one: `40aebe552f6f`
  is an older Jaguars (09-30), and `dfef8d4d6ced` (Thor) is "Crystal Cats".
- Every other title in the store (83): **proposed** = its newest verified
  harvest that has a save directory, else its newest verified harvest. These
  load exactly like a golden. lane.local or the owner confirms one with
  `titlestate.py promote --title-id T --save S --by WHO`. The list is
  `titlestate.py golden`.
- Aliases: `4D53002D->54430001`, `49470018->5345000A`, `49470017->5345000B`.

## B. Route by state

- 65 route files now carry `# state:` on line 1 (48 first-run, 12 returning,
  5 any). `add_state_headers.py` wrote them; the basis is in its docstring:
  the state the route was RECORDED in.
  - 46 of the single routes name a nav.py `<title>.first-run-<stamp>` session
    from 09-26/27 (each title's first play) or a survey run made before the
    title had a save.
  - `crimson-skies` is `returning`: its only frame-proven 600-s window ran on a
    disk carrying "Nathan".
  - `sonic-heroes` is `returning`: it was written on slot 01.
  - The drive routes, generic, survey and forza414 are `any`, except
    `castlevania-cod.drive`, which is FIRST RUN by its own header.
  - Caveat: nav.py's default variant is `first-run`, so a session's name proves
    the disk state only because each of those was the title's first play.
- `request.sh --route <base>`: `titlestate.py resolve-route`. A family goes to
  `.returning` with a profile golden, else `.first-run`. A named variant is
  taken as named. **Refused at queue time:**
  - a `returning` route with no golden, a rejected golden, or a settings-only golden;
  - a route with no `# state:` line;
  - a `returning` route on a title targets.toml cannot identify.

  The request carries `title_id` and `title_state`.
- `route_audit.py` (output `route_audit.out`): all 52 routed targets titles
  queue today. Before the save-directory rule, Black and GoldenEye would have
  been refused (settings-only goldens, families resolving to `.returning`).

## C. One prepare step for every path

- `titlestate.py prepare --device D (--title-id T | --iso N | --hdd-img) --state S`
  and `release --device D`. These are the dispatcher's steps in Python: plan rounds,
  push via `.new` with the sha256 read back, **mode 660 before the rename**, the
  pref written and read back. They use the dispatcher's own marker file
  (`.hdd_pref.<device>`), so a session that never releases is put back by the
  next request's `restore_hdd_pref`, and its writes are harvested by the next
  `plan()`.
- `nav.py start` needs `--title-id`/`--iso` (it prepares the disk) or
  `--hdd-img` (hand play, said out loud). `end` releases.
- `pathfind.py --state S` prepares before launch and releases in a `finally`.
  `--hdd-img` opts out.
- `titlestate.py take-hdd --device D --title-id T`: after hand play on hdd.img,
  pull it, harvest T as `latest`, and print the `promote` line. This is the
  "offer to harvest and promote" step for the owner's play.
- **Not mine, sent to the owners (OUTBOX):**
  - lane.vcpuwait433's `capture_offcpu.sh` should call `titlestate.py prepare
    --device $DEV --title-id 42560001 --state returning` before the soak and
    `release` after it.
  - lane.local's `host-tools/playtest_ready.sh <title>` should call `prepare`
    for a title, and `take-hdd` + `promote` after hand play.

## D. The void ledger: cause -> guard

Source: a read-only pass over `dispatch/results/*` since 09-26 00:00 UTC
(`scratch/voids_research.md`, not committed; method: routerca433's ledger.tsv
plus a wider scan of VOID.txt / WITHDRAWN.txt / ERROR / verdict reasons). 90
void-like results:

| cause | voids | guard before today | gap | guard added here | selftest |
|---|---|---|---|---|---|
| wrong save state (187 name keyboard, Castlevania x3, SMB Stage Select, Sonic pause; Tron 18:46 held) | 6 + held | none; plan() kept whatever the last run left | the disk's state was not chosen, and nothing compared a route's assumption with it | goldens + compose + `# state:` + refusal at queue and at dispatch; held sessions prepare | `titlestate_selftest.py` goldens/plan/resolve/prepare legs; `85-savestate.sh` legs 1-3 |
| route died, soak ran on (CAPA T16) | 2 (904 s, 661 s) | none: the hold loop never read route.sh's exit | a dead route held the whole window | the hold loop stops on route.sh rc != 0 (`route-died:`, exit 6) | `85-savestate.sh` "route that dies"; red on master (30 s, rc 0) |
| waitfor ref crop missing (T5) | 2 | request.sh refuses crop routes (snapdrive, 10-02) | a route that dies anyway ran on | the route-died guard | as above; `97-dispatch-snapshot-drive.sh` |
| heat (Thor) | 32 | coldconfirm cold slot, xo 70 C stop; soak cool-down gate | start temperature does not predict the pause; the fan is dead | none: **owner action** (fan; Thor rule) | - |
| foreground loss (ES-DE 4, odin.settings 3, Daijishou 2, USB dialog 2, shade 1, unreadable 4, other 1) | 17 | fg_wait, fg_watch, usb_dialog, FG_UNREADABLE_MAX; verdict voids | after the fact by design: a launcher grabbing focus mid-run is not visible before it happens | none new (see Next) | `99-fg-unreadable.sh`, `99-usb-dialog.sh`, `99-display-covered.sh` |
| Nova post-restart burst | 7 | 1 of 7 root-caused and fixed (0644 disk, hddcrash) | the other 6 are unexplained beyond "right after a restart" | none (see Next) | `99-hdd-split.sh` (mode legs) |
| adb / device absent | 10 | alive() retries, FG_UNREADABLE_MAX | a sustained USB drop reads as foreground loss | none: hardware link (Nova below 30%: battery_admit floor) | - |
| media.extractor misattribution | 3 | fixed by crashattr (title_verdict.py) | - | - | `89-title-verdict.sh` |
| battery | 0 | battery_admit.py (Nova floor 30%) | none observed | - | `99-battery-admit.sh` |
| build failure / env pref | 2 | ERROR after claim | transient | none | - |
| emulator crash (Nova) | 2 | - | **emulator fix** | - | - |
| title missing on device | 6 (all 09-26) | `devices.sh` roots fix 09-26 | closed | - | `99-iso-roots.sh` |

**Harness-side and closed here:** wrong save state, route died, missing crop
(through the route-died stop). **Needs owner action:** the Thor (fan / Thor
rule), the Nova's sustained USB drops. **Needs an emulator fix:** the two Nova
crashes.

## E. Profile-required titles

Titles whose stored harvests differ in carrying a profile (their menus differ
with and without one): Tron 2.0, Buffy, Burnout Revenge, Castlevania, Spikeout,
187, Tork (`route_audit.out`). Titles with a `.returning` variant: Black, Burnout
3, Burnout Revenge, Castlevania, KOF MI, Midnight Club 3, Midtown Madness 3, PGR,
RalliSport 2, Spikeout. Those that lack a returning route among the profile
titles: Tron 2.0 (no route on master at all), Buffy, 187, Tork. Their routes are
`first-run` (recorded without a save), so they run deterministically from no
save. No returning route is needed for them to be judged.

The ten in flight (`inflight.py`, 20:20 PDT):

| title | id | golden (save dirs) | route | state | today |
|---|---|---|---|---|---|
| Tron 2.0 | 42560001 | 5489ae7f9b58 proposed (2 autosaves) | none on master (lane.vcpuwait433's tron-newgame, lane-local) | - | **gap**: no route in targets.toml; the lane's held capture uses hdd.img. Its route reaches the same in-level end from either state (v5 note), so `any` would be honest. Closed by the capture script calling `prepare` (OUTBOX) |
| Blinx 2 | 4D530065 | 377a8488c7c5 **golden** (Jaguars, Tigers) | none | - | golden loads on every run (state `any`); no route: **needs navigation** (a route recorded from the golden) |
| Kabuki Warriors | 43560001 | bbb88f4302f6 proposed (settings only) | kabuki-warriors | first-run | OK |
| Dead or Alive 3 | 4D53002D -> 54430001 | 220536a66fe2 proposed (settings only) | doa3 | first-run | OK (alias) |
| ToeJam & Earl III | 5345000F | 71a91de8b905 proposed (settings only) | none | - | golden loads (`any`); no route: **needs navigation** |
| Battlefield 2: MC | 45410062 | dcf7307455f0 proposed (settings only) | bf2mc | first-run | OK |
| GTA San Andreas | 54540082 | 7da19befd45b proposed (settings only) | gta-sa | first-run | OK |
| Crimson Skies | 4D530021 | 42b0f68410a3 proposed (Nathan) | crimson-skies | returning | OK |
| 007 Nightfire | 45410026 | faf449621348 proposed (settings only) | nightfire | first-run | OK |
| Castlevania | 4B4E002D | 20235e93867b proposed (slot-1 save) | castlevania-cod -> .returning | returning | OK after the save-directory rule (was the 10-01 void) |

## Device proof (Nova, held 20:25-20:30 PDT, 2 boots of the 4 allowed)

`proof_tron.sh`: Tron 2.0 (42560001) on the Nova, with `hold.sh` and the
held-session path (`titlestate.py prepare` / `release`). The route is
`tron-menu.route`: vcpuwait433's tron-newgame v5, cut at the Single Player menu.

| state | loaded (hdd.json) | disk | Single Player menu (`menu-cursor`) |
|---|---|---|---|
| returning | golden `5489ae7f9b58` (2 autosaves) | build, keep; 18.1 MB | cursor on **Auto Load**; Load Game enabled (`proof-tron-returning-menu.png`) |
| first-run | none | build, keep; 17.2 MB | Auto Load and Load Game **greyed**, cursor on **New Game** (`proof-tron-first-run-menu.png`) |

Those are the two states of the 18:46 void (tron1: "Auto Load and Load Game
are greyed and the cursor starts on New Game"). Now the request picks the
state, not the last run. Both releases harvested with no errors.

- The first-run's leftover (`d2aff0a53543`, title data only) went to Tron's
  `latest`, and the golden is unchanged.
- hddPath went back to hdd.img, and the marker was removed.
- Battery 80% at the start.

The composed disk (every title's golden) is 17-18 MB, so the push takes seconds.

## Checks run

- `python3 docs/testing/titles/titlestate_selftest.py`: all checks passed (90+).
- `SELFTEST_ONLY=85-savestate.sh selftest.sh`: 27 passed. **Against master's
  titlestate.py, dispatcher.sh and request.sh, 18 of 24 legs fail**, including
  the void itself (the next disk carries the run's bare save, not Nathan). The
  route-died legs fail on master's soak_title.sh (holds 30 s, rc 0).
- `SELFTEST_ONLY=99-hdd-split.sh`: 63 passed. Three of its legs asserted the
  old behavior and were changed: the second run's disk carried the run's new
  save; a disk whose harvest failed was kept and booted (twice).
- `89-title-verdict.sh`: its `--route` leg queued `crimson-skies` (now
  `returning`) for a title no targets entry names; it now uses `gta-sa`.

## Territory

Requested in the brief: `docs/lanes/savestate433/**`, titlestate.py,
titlestate_selftest.py, saves.py (unchanged), request.sh, dispatcher.sh, nav.py,
pathfind.py, `85-savestate.sh`, and the `# state:` line of every route.

**Also edited, for the board to add:**

- `docs/testing/soak_title.sh`: the route-died stop, 18 lines, additive. No
  open lane edits it.
- `jobs/selftest.d/99-hdd-split.sh`: 3 legs asserted the void.
- `jobs/selftest.d/89-title-verdict.sh`: one route name.

## Do not repeat

- Do not treat a harvest as a profile: check for a save directory
  (`save_dirs`).
- Do not key a disk on targets.toml's id without `disk_tid` (the aliases).
- Do not let any path boot a titles disk a run already wrote to. Harvest it,
  preserve it if the harvest fails, then rebuild.
- The Bash tool here rejects heredocs with quoted braces and `$VAR`; patch
  files through a script under `scratch/`.

## Session 2 (2026-10-03 08:31-08:4x PDT): the profile-save stage

**Why attempt 1 "did not finish":** it did. PR.md went `ready` at
`0c8ab805e0` (10-02 ~20:45). It then sat unfolded for 11 h on the board's
side, not the lane's: foldqueue read the first PR.md in the branch's diff
(buildstamp's draft) until 22:55, then refused the branch at 23:25 on
territory (`dispatcher.sh`, `pathfind.py` were not on the row). The grant
and the fold landed at 07:57 (`cfa37a359e`). This session is the 08:30
addendum's continuation: the #397 profile-save stage.

**The stage's work list, read from the status page's own logic**
(`status_html._registry`, `scratch/needsave.py`, 08:35):

- Every title on master with a route (inputs) already has a stored save.
  None is waiting on "extract the profile save".
- 30 titles have no route on master. Their save comes with their route: any
  title run harvests to the store, and a first-run that reaches `mark
  profile-saved` with no golden makes its save the golden. They need
  navigation (lane.pathfind), not this stage.
- So **no title with a working route lacks a save**. The stage has nothing
  to extract today.

**What the queue hit instead (hostops 08:12, "runner refused sw3, no save
dir"):** my own guard, working as built, with a reason that named no way
forward.

- lane.local headed `star-wars-ep3.route` `# state: returning` ("its PASS-like
  runs played on the profile that is now its golden").
- That golden, `cb663b62ffcf`, holds title data only. `returning` means "needs
  a save directory", so the guard refused.
- The record (`scratch/hddstate.py`):
  - replay 1 (`1790939919`) and run 2 (`1790944635`) both booted a disk
    carrying `cb663b62ffcf`;
  - the survey (`1790921690`) booted with no 4C410017 save at all and took
    the same path to play (cycle 13).
- So the honest header is `any`. `any` loads the golden unchanged, which is
  exactly the disk the confirmation ran on.
- **Guard change:** both settings-only refusals (`resolve_route`, `compose`)
  now end with the fix: head it `# state: any` if the route was confirmed on
  this golden, else `promote` a save with a save directory.
- **Selftest:** `titlestate_selftest.py`'s SW3 leg was red before the change.
  It asserts the reason names `# state: any`, the `any` header queues, and
  its disk carries the golden unchanged.

**The rest of lane.local's queue (`scratch/queuecheck.py`, resolved as
request.sh will, from each line's worktree, 08:36):**

| key | golden (save dirs) | route state | result |
|---|---|---|---|
| sw3 | cb663b62ffcf (0) | returning | REFUSE: settings-only; fix is `# state: any` |
| kabuki | bbb88f4302f6 (0) | first-run | OK |
| gunvalkyrie | 4e2a12123171 (1) | first-run | OK |
| halo2 | 0a4742f1e45d (2) | returning | OK |
| toejam-off/on-perflog | 71a91de8b905 (0) | - | REFUSE: `toejam-earl-3.route` is not in the uberdefault569 worktree. It exists only on lane/titleroutes2 (`3efd923411`) and has no `# state:` line. Its two PASS runs (13:07, 21:02) played on settings-only `71a91de8b905`, so it should be headed `any` too |

**Status page, not mine:** `status_html._registry` calls
`titlestate.store_saves(tid)` with targets.toml's id. Gunvalkyrie's saves are
stored under its disk id `5345000B`, so its row reads "no save" when it has
one. The fix is one line: `titlestate.store_saves(titlestate.disk_tid(tid))`.
DOA3 and JSRF hide the same miss behind their single routes ("n/a").

## Next (P x win)

1. **lane.local: head SW3 and ToeJam `# state: any`, and put ToeJam's route
   where the runner reads it.** P 0.95: the guard accepts `any` on these
   goldens (selftest leg), and both routes reached play on exactly these
   disks. Win: 2 of the 4-5 titles the owner wants today stop being refused
   (SW3 is the plan's top P, 0.55). Cost: two header lines and a copy, no
   device time.
2. **Confirm or replace the proposed goldens.** Done by lane.local overnight:
   all are `golden` now.
3. **Record routes from the goldens for Blinx 2 and ToeJam & Earl III.**
   Re-scored:
   - ToeJam has a working route on its golden, so it needs none.
   - Blinx 2 is lane.near30's held session today, and navigation is
     lane.pathfind's.
   - Dropped from this lane.
4. **Nova post-restart hold** (dispatcher: hold requests N min after a device
   reconnect). P 0.3: 6 of 7 burst voids are unexplained, and the one
   explained was the disk mode. Win: up to 6 voids per 6 days. A cheap
   measurement decides it first: correlate the 6 with `devwatch` reconnect
   times. If they follow a reconnect within 5 min, do the hold. If not, drop it.
5. **Foreground pre-admission**: P 0.1. A launcher in front BEFORE the app
   starts is normal, and the 17 losses happened mid-run. Not recommended.
