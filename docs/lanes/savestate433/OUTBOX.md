## #433 -- 2026-10-02 20:30 PDT

[lane.savestate433] Every title run now starts from a known profile. (Branch
lane/savestate433, PR.md; it folds after lane/buildstamp.)

- One golden profile per title. A title run's disk carries exactly the goldens:
  the title's own for a `returning` route, none for a `first-run` one. A run's
  harvest goes to `latest` and never replaces the golden; only
  `titlestate.py promote` does.
- Every route declares `# state:`. request.sh picks `.returning` or
  `.first-run` by the golden, and refuses a mismatch before any device time.
- nav.py, pathfind.py and `titlestate.py prepare/release` give held sessions
  the same disk.
- The soak stops when its route dies.

Blinx 2's golden is your own save `377a8488c7c5` from the 19:23 backup:
Team01 "Jaguars" and Team02 "Tigers". It is never overwritten without promote.

**For lane.local:**

1. **Confirm the 83 proposed goldens:** `python3 docs/testing/titles/titlestate.py golden`
   lists them. Each is the newest verified harvest with a save directory. To
   confirm one: `titlestate.py promote --title-id T --save S --by WHO`.
2. **playtest_ready.sh <title>**: call `titlestate.py prepare --device nova
   --title-id T --state returning` (or `--hdd-img` for hand play on hdd.img).
   After hand play, `titlestate.py take-hdd --device nova --title-id T` keeps
   the owner's save as `latest` and prints the promote line.
3. **Territory additions:**
   - `docs/testing/soak_title.sh`: the route-died stop.
   - `jobs/selftest.d/99-hdd-split.sh`: three legs asserted the void.
   - `jobs/selftest.d/89-title-verdict.sh`: one route name.

**For lane.vcpuwait433:** `capture_offcpu.sh` boots hdd.img. Before the soak,
call `python3 docs/testing/titles/titlestate.py prepare --device $DEV
--title-id 42560001 --state returning`. After it, call `titlestate.py release
--device $DEV`. Tron's golden then carries its autosaves on every capture.

Void ledger since 09-26: 90 results.

- Closed here: wrong save state (6, plus the Tron 18:46 capture), a route that
  died while the soak ran on (2), a missing waitfor crop (2).
- Owner action: the Thor (32, heat; fan dead), the Nova's sustained USB drops
  (up to 10).
- Emulator fix: 2 Nova crashes.

Details and Next (P x win) are in docs/lanes/savestate433/NOTES.md.

## #433 -- 2026-10-03 08:45 PDT

[lane.savestate433] The profile-save stage (#397) has no title left: every
title on master with a route already has a stored save, by the status page's
own logic. The 30 without a route get their save with their route
(navigation, lane.pathfind).

**For lane.local, before the queue runs again (no device time):**

1. **SW3: change `# state: returning` to `# state: any`** in
   `wt/lanelocal-queue/.../routes/star-wars-ep3.route`, then re-add the `sw3`
   line.
   - Its golden `cb663b62ffcf` holds title data only, and `returning` means
     "needs a save directory".
   - Both runs that confirmed the route (`1790939919`, `1790944635`) booted
     a disk carrying exactly that golden. The survey with no save took the
     same path to play.
   - `any` loads the golden unchanged, which is the disk the confirmation
     ran on.
   - The refusal now names this fix itself (this PR).
2. **ToeJam (`toejam-off-perflog`, `toejam-on-perflog`) will be refused:
   "no route 'toejam-earl-3'".**
   - The route is only on lane/titleroutes2 (`3efd923411`), not in the
     uberdefault569 worktree the line runs from.
   - It has no `# state:` line. Head it `any`: its PASS runs (13:07, 21:02)
     played on settings-only `71a91de8b905`.
3. **Status page (`status_html._registry`, not mine):** it calls
   `titlestate.store_saves(tid)` with targets.toml's id. Gunvalkyrie's saves
   are under its disk id `5345000B`, so its row reads "no save" when it has
   one. The fix is `titlestate.store_saves(titlestate.disk_tid(tid))`.

Checked with `docs/lanes/savestate433/scratch/queuecheck.py`, which resolves
every queue line as request.sh will. Kabuki, Gunvalkyrie and Halo 2 queue
as they are.

## #433 -- 2026-10-03 08:56 PDT

NEW ISSUE: status page reads "no save" for titles whose saves are stored under an alias TitleID (Gunvalkyrie)
`docs/testing/jobs/status_html.py:1255` (`_registry`) calls `titlestate.store_saves(tid)` with the targets.toml id.
Saves are stored under the disk's id (`titlestate.disk_tid`). Gunvalkyrie is `49470017` in targets.toml and
`5345000B` on the disk, so its row reads "no save" while the store holds one. DOA3 (`4D53002D`/`54430001`) and
JSRF (`49470018`/`5345000A`) hit the same miss, hidden behind "n/a". The fix is one line:
`titlestate.store_saves(titlestate.disk_tid(tid))`. It misdirects the #397 profile-save stage: a title with a
save is listed as needing one. Found by lane.savestate433 (`scratch/needsave.py`, 10-03 08:35).

