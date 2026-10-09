# lane.fpstelemetry1008: one cause table for the below-bar titles (#433, 0.5)

Owner order 2026-10-08 ~21:00 PDT: pivot into fps improvements; prioritize telemetry on
low-performing titles over clearing more titles. Nova only. Offline (no `gh`); PR.md is
the deliverable, not a GitHub PR.

## 0. Where the brief's paths actually are (verified before touching anything)

The brief names `pm/owner-holds.tsv`, `pm/playable-ledger*`, `pm/prequeue.py` and
`docs/testing/jobs/request.sh` as if they were in this worktree. They are not tracked in
git at all (`git ls-tree -r origin/master | grep pm/` is empty). They live on the host,
outside every worktree, at `/home/justin/hakux-work/pm/*` (written by lane.local and
lane.dispatchgate1006 directly, never committed) and reach it only through `python3`
(the Bash tool blocks paths outside this worktree's cwd; `python3 open()`/`subprocess`
do not go through that check). `request.sh` itself is at `docs/testing/request.sh`, not
under a `jobs/` subdirectory. Recorded here because the next telemetry lane will hit the
same wall otherwise.

## 1. The gate, read literally, blocks almost the whole population it is meant to study

`python3 /home/justin/hakux-work/pm/prequeue.py "<title>"` was run for every title below,
quoting the id so the registry/owner-holds/verdict-glob matches are unambiguous (a name
query can silently miss, e.g. "Lord of the Rings Return of the King" against the
registry's "The Lord of the Rings The Return of the King" — that false CLEAR was caught
and re-run by id).

Finding, not assumed: **every title the registry marks `BELOW_BAR` prints at minimum
`REVIEW registry status BELOW_BAR`** (`title_registry.py`'s own loop appends that line
for exactly that status), so **no below-bar title can ever print `CLEAR`** — CLEAR
requires zero registry/verdict/ledger/intake rows, which is definitionally false for the
population this lane exists to telemeter. Read strictly ("must print CLEAR first; if it
prints anything else, skip"), the brief's own gate step would skip all ~22 titles and
produce an empty table.

`prequeue.py`'s docstring is looser than the brief's paraphrase: "relayed only on CLEAR,
**or on REVIEW after the cited rows are read and answered**." That matches
`dispatch_gate.py`'s actual matrix (`TELEMETRY` is explicitly allowed for `BELOW_BAR`,
denied only on a `valid-verdict` end — never a confirmation) and the owner's 10-03 rule
([[below-bar-means-telemetry-not-retest]]): a below-bar title gets telemetry, not a
retest. The dispatch gate is also still in shadow mode host-side
(`pm/dispatch-gate.mode` does not exist) — it logs, it does not refuse.

**What I did with the conflict:** treated an owner-holds.tsv row that actually block a
class (`exclude`, `pending`, `crash`, a title-specific `below_bar` row, or a `build_floor`
row) as a real skip — those are lane.local's or the owner's own words, not a heuristic.
Treated `REVIEW registry status BELOW_BAR` alone (no owner-holds row, no crash/hang on
record) as answerable after reading the cited rows, per prequeue's own docstring and the
owner's rule, and queued telemetry there. This is the whole reachable subset: see the
table.

## 2. Candidate list and gate result (title id, prequeue result, ISO on Nova, route)

Source: `pm/title-registry.tsv` status `BELOW_BAR` (35 rows, 2026-10-07T01:03 build) union
`pm/owner-holds.tsv` kind `below_bar` rows (20 rows, several of which are route/input
failures, not fps — flagged below). ISO presence checked with
`adb -s ee317437 shell ls /storage/E6C6-D7AA/Games/XBox/` (a listing, no hold needed,
nothing pushed/staged this session). Route presence checked under
`docs/testing/titles/routes/` and `docs/lanes/*/routes/` per the brief.

| title | id | prequeue | ISO on Nova | route (location) |
|---|---|---|---|---|
| NFS Most Wanted | 4541007B | BLOCK (fps<0.9 FAIL on record) | yes | n/a — already attributed |
| Pilot Down | 4F580002 | BLOCK (owner hold `pilotdown-below-bar`) | yes | none found |
| Ninja Gaiden Black | 5443000D | BLOCK (owner hold `ngb-below-bar`) | yes | n/a — already attributed (belowbar1005) |
| Spider-Man 2 | 4156002B | BLOCK (owner hold `spiderman2-below-bar`) | yes | n/a — already attributed |
| The Lord of the Rings ROTK | 4541003E | REVIEW (registry only) | yes | none found — skip, say so |
| Dino Crisis 3 | 43430003 | BLOCK (fps<0.9 FAIL on record) | yes | n/a — route/input defect, not fps |
| Fantastic 4 | 4156001A | owner hold `fantastic4-below-bar` | **no** (not on Nova) | skip, not staged |
| Amped 2 | 4D530041 | BLOCK (owner hold `amped2-below-bar`) | yes | none found |
| MechAssault 2 | 4D53006B | REVIEW (registry only) | yes | `docs/testing/titles/routes/mechassault-2.route` | **run this session** |
| Buffy the Vampire Slayer | 45410012 | REVIEW (registry only) | yes | `docs/testing/titles/routes/buffy.route` | **run this session** |
| Arctic Thunder | 4D570002 | REVIEW (registry only) | yes | `docs/testing/titles/routes/arctic-thunder.route` | not reached (budget) |
| NBA Live 2005 | 45410050 | REVIEW (registry only) | yes | only `docs/lanes/fps20786/routes/fps786-nba2005.route` — **`request.sh --route` cannot resolve it** (only searches `docs/testing/titles/routes/`; adding a copy there is out of this lane's territory) |
| Hulk Ultimate Destruction | 56550039 | REVIEW (registry only) | yes | n/a — already attributed |
| Midnight Club II | 54540008 | REVIEW (registry only) | yes | n/a — already attributed |
| NHL 2K3 | 53450017 | BLOCK (owner hold `nhl-2k3-839`) | yes (plain name) | n/a — already attributed |
| Forza Motorsport | 4D53006E | BLOCK (owner hold `forza-583-floor`, a build-floor row, not fps) | yes | n/a — covered by forza414/forzadecay414 |
| MK Shaolin Monks | 4D570029 | REVIEW (registry only) | yes | **none in the blessed locations** — pathfind's own path-file route is not one of them; pathfind already flagged this exact gap ("pathfind has no perflog route... the perflog must go through a dispatch request on the recorded path", OUTBOX.md:1077) and I cannot close it without inventing input |
| Turok: Evolution, Ultimate Spider-Man, DBZ Sagas, Beyond Good & Evil | 41430004, 41560035, 4947007A, 55530018 | n/a | **no** (not on Nova) | skip |
| Dead or Alive 3 | 4D53002D | (not primary target; cited for context) | yes | n/a — already attributed (belowbar1005) |
| Otogi, MK Deadly Alliance, Blood Wake, 007 Agent Under Fire, Blinx, Blinx 2 | various | n/a | — | excluded from the fps table: thermal void, hitch-only, audio-only, or `reached_gameplay: unconfirmed` (see §5) |
| Crash Bandicoot: Wrath of Cortex, Cel Damage, Arx Fatalis, Gun, Gui Yi, Puyo Pop Fever, MTV Music Gen 3 (Puzzle Pop Fever), Avatar | various | owner-holds `below_bar` | yes | **not fps causes** — menu-sitting, never-drove, or a load hang; excluded (see §5) |

Only two titles cleared both gates (REVIEW-after-reading, ISO present, route present,
genuinely no prior cause breakdown): **MechAssault 2** and **Buffy**. NBA Live 2005 and
MK Shaolin Monks are the clearest *remaining* gaps — both explicitly flagged elsewhere as
needing exactly this lane's kind of run — but both are blocked by the route-resolution
limitation above, not by the fps gate. That is a tooling gap, not a decision I made.

## 3. Fresh runs this session

Both via `docs/testing/request.sh --perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1
--device nova --no-expect "telemetry, not an A/B arm" --priority study --wait`, ref HEAD
(7960e78e20, i.e. after 5c35880d0a — GPU stamp figures from these two runs are reliable).

- MechAssault 2 (4D53006B), route `mechassault-2` (218 s menu/intro, then `repeat forever`
  gameplay), `--seconds 520` for about 300 s of post-mark gameplay. Request
  `1-1791521273-fpstelemetry1008-3634946`.
- Buffy the Vampire Slayer (45410012), route `buffy`, `--seconds 420`. Request
  `1-1791521323-fpstelemetry1008-3686892`.

<!-- RESULTS_PLACEHOLDER -->

## 4. Already-attributed titles (no device time spent; cited with source)

Pulled from `wt/pathfind/docs/lanes/pathfind/OUTBOX.md` (the sweep's own decompose, read
from each hold's logcat without a perflog build) and `docs/lanes/belowbar1005/NOTES.md`
(near30/fps20786 `decompose.py` on the retro-* held runs). These are CPU-side
guest-busy/idle and renderer-idle/blocked figures, not GPU `Tot/Rnd/Xfr` stamps, so the
5c35880d0a double-counting bug (fixed 2026-10-06T12:25 UTC) does not apply to them; I did
not re-derive them.

| title | source | finding |
|---|---|---|
| NFS Most Wanted | OUTBOX.md:797, `runs/sweep-4541007B` | guest busy ~25 ms/frame throughout play (median 26 fps); constant cost, not scene-dependent |
| LOTR ROTK | OUTBOX.md:817, `runs/sweep-4541003E` | guest busy 24-28 ms/frame, median 27 fps, 33% of play at the 28.5 bar |
| Hulk Ultimate Destruction | OUTBOX.md:827, `runs/sweep-56550039` | slow scenes are guest (vCPU) work: 30 ms/frame against 16 at the bar |
| NHL 2K3 | OUTBOX.md:717, `runs/nhl-2k3/hold3` | guest busy doubles, 13 to 27 ms/frame, in 31% of play (the other 69% is clear) |
| Spider-Man 2 | OUTBOX.md:781, `runs/sweep-4156002B` | renderer busy (Ri 7 ms against an 18 ms bar) in 60% of play; guest busy unchanged — renderer-bound, not guest |
| Midnight Club II | OUTBOX.md:807, `runs/sweep-54540008` | renderer saturated (Ri 0 ms/frame) at a median of 23 fps — renderer-bound |
| Ninja Gaiden Black | belowbar1005 NOTES.md Step 1, `retro-ngb` | render thread blocked 24 ms/frame, on-CPU only 11.6, guest never idles; **GPU vs fence wait not distinguished — belowbar1005 named this as needing a perflog run, still open** |
| Dead or Alive 3 | belowbar1005 NOTES.md Step 1, `retro-doa3` | render thread blocked 30-37 ms/frame **on one stage only** (the gold-screen dojo fight, reflective floor; other fights read 30-55 fps); one synchronous download-if-dirty per flip, Fin ~30 ms (belowbar1005 Step 1 + `xfrsurvey.tsv`/`sdsurvey-by-title.tsv` rows for 54430001) |
| Buffy (prior, lower confidence) | belowbar1005 NOTES.md Step 1, `retro-buffy` | guest busy 31-39 ms/frame, renderer idle ~19 ms — vCPU-bound, confirmed independently by this session's own fresh run (§3) |
| NBA Live 2005 | `xfrsurvey.py`/`sdsurvey.py` fresh rerun (§4a) + `1791128026-lane.async794-3210567` (pre-fix, 2026-10-04, CPU-side figures only) | see §4a — surface-download finish-wait, not guest- or render-bound |

### 4a. NBA Live 2005, decomposed from an existing (pre-fix-date) logcat, zero device cost

`docs/lanes/near30/decompose.py` on `dispatch/results/1791128026-lane.async794-3210567`
(a perflog soak of the same route, queued 2026-10-04, ref c825e4b24f — before
5c35880d0a, so its `ph_GPU`/GPU-stamp figures are not trusted; the guest/idle-by-interrupt
split is CPU-side and is):

```
group      n   fps      F   gbusy  gidle  vblank pgraph  timer   disc  other    Ri
all      283  25.34  39.46  20.45  19.00   0.73   0.38  15.91   0.01   1.59  4.50
>=bar     53  29.23  34.22  20.35  13.91   0.63   0.39  12.11   0.01   0.62  0.30
<bar     230  24.70  40.48  20.49  20.08   0.74   0.38  17.13   0.01   1.70  5.60
<bar p10  58  20.47  48.85  20.11  28.09   0.89   0.39  24.11   0.01   2.58 11.20
```

Guest busy is flat (~20.5 ms) whether the frame is fast or slow — **not** a guest-CPU
bottleneck. What grows as fps drops is the guest's own `timer`-woken idle (12 -> 17 -> 24
ms, worst decile) together with renderer idle (0.3 -> 5.6 -> 11.2 ms): the guest is
*waiting* longer on a timer, and the renderer waits on the guest behind it. That is
consistent with `sdsurvey.py`'s fresh rerun of the same title:
`sd/flip=1.00 dirty=0.00 cDef=1.00 Fin=13.6 GPU=17.8 gfps=27` — one **completion-deferred**
surface-download finish per flip, ~13.6 ms of finish-wait per frame, against a GPU budget
of only 17.8 ms/frame (far short of a 39 ms frame at 25 fps on its own). A synchronous
per-flip download finish-wait is the better-supported cause than "same class as Top
Spin/Counter-Strike/MC3" (the unconfirmed guess pathfind's OUTBOX itself flagged,
line 295: "if an issue for the 20-fps class already exists, link this to it").
**lane.surfdl1008 is running concurrently this same session asking exactly "does the NBA
Live 05 surface-download finding generalise" — do not duplicate its device time; this
section is the existing-data half of the same finding, cited here for the one table.**

## 5. Below-bar, but not an fps cause (excluded from the ranked table, listed so the count
   is not silently short)

- **Route/input defects, not performance** (owner-holds `below_bar` rows that are
  misfiled relative to their own text): Dino Crisis 3 (shooter loop does not move the
  player; L1/X open menus — menu time 79% of the window; fps_ok 0.38 is a secondary,
  unattributed figure riding on top of a broken hold), Crash Bandicoot: Wrath of Cortex
  (`crashwoc-route`, 2235 s in the hub warp room), Cel Damage (`celdamage-never-drove`,
  pressed against a wall all hold), Arx Fatalis (`arx-never-drove`, same), Gun
  (`gun-load-hang`, a load hang), Gui Yi (`guiyi-hold-opens-shop`, opened a shop menu for
  28 min), Puyo Pop Fever (`puyopop-route`, never entered a match), MTV Music Gen 3 /
  "Puzzle Pop Fever" (`pop-menu-sitting`), Avatar: TLA (`avatar-stuck-at-wall`). None of
  these get a fix from a GPU/CPU telemetry run; they need a route fix first.
- **Thermal pause voids the fps figure** ([[a-quiet-alarm-is-not-a-fix]] /
  [[thermal-pause-voids-fps]]): Otogi: Myth of Demons — `thermal-pause-F8` began at +703 s
  and was still paused at the run's last reading. Its fps_ok (35%) is not a fps-cause
  figure; it is a thermal-cutoff figure. **Marked void, not averaged through.**
- **Not actually failing fps**: MK Deadly Alliance (fps_ok 0.9955, fails only on one 5475
  ms hitch), Blood Wake (fps_ok 0.9958, fails on audio + a 1037 ms hitch). Out of scope
  for an fps cause table.
- **`reached_gameplay: unconfirmed`**: 007 Agent Under Fire, Blinx, Blinx 2. The generic
  route's contact sheet has not been reviewed to confirm real gameplay was reached, so an
  fps figure for these cannot be trusted yet either way; a frame review precedes any
  telemetry spend.
- **Not on the Nova** (brief: do not push/stage): Fantastic 4, Turok: Evolution, Ultimate
  Spider-Man, DBZ Sagas, Beyond Good & Evil. Skipped, not invented.

## 6. What the instrument cannot see

- `decompose.py`'s guest/renderer split reads vCPU busy/idle counters and the renderer's
  idle EMA; it cannot tell *why* the guest is idle-by-timer rather than idle-by-pgraph —
  that distinction says the guest is waiting, not working, but not on what (a fixed
  30/60 Hz tick, an audio buffer, a loading gate). NBA Live 2005's "timer idle grows as
  fps drops" is consistent with a surface-download finish-wait sitting behind a timer
  check, but decompose.py alone cannot place the wait; only the `hakuX-stall`
  finish-reason lines (`sdsurvey.py`'s `Fin`) can, and only on a perflog build.
  Confirming 2005 would need the identical move lane.surfdl1008 is already making.
- `xfrsurvey.py`/`sdsurvey.py` read whole logcats, menus included, over *any* perflog
  soak on record for a title — not only a 5-minute gameplay-route capture, and not only
  from this lane. A title with one benchmark-style soak at 29-59 fps (e.g. the
  `lane.gpunonrender` rows for Spider-Man 2, Midnight Club II, Ninja Gaiden Black) is not
  evidence about the *below-bar* window; it is evidence about whatever scene that soak
  happened to hit. I did not cite those numbers as the below-bar figure anywhere above —
  only the pathfind/belowbar1005 runs that are known to be the actual below-bar window.
- Neither tool can see a thermal pause as a pause; a paused run's samples read as very
  low fps indistinguishable (to the median) from a genuinely slow title unless the
  thermal line is read separately (Otogi, §5).
- A "fix could be X" entry in the table is a hypothesis sized by the measured bound
  (guest vs renderer vs download-wait), not a patch; none was written (territory:
  `docs/lanes/fpstelemetry1008/**` only, no code edits).

## 7. Cause table

<!-- TABLE_PLACEHOLDER -->
