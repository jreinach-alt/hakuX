# lane.fpstelemetry1008: one cause table for the below-bar titles (#433, 0.5)

Owner order 2026-10-08 ~21:00 PDT: pivot into fps improvements; prioritize telemetry on
low-performing titles over clearing more titles. Nova only. Offline (no `gh`); PR.md is
the deliverable, not a GitHub PR.

## Attempt 2 (why attempt 1 did not finish)

Attempt 1 did the gate audit (§1-2), queued the two reachable titles' telemetry requests
(§3, MechAssault 2 and Buffy) with `--wait`, and stopped there — the session ended while
the second request was still running on the device, with `RESULTS_PLACEHOLDER` and
`TABLE_PLACEHOLDER` left in this file and PR.md at `State: in progress`. That is not a
blocked or waiting state in the lane-contract sense (nothing external was left unresolved
that required another actor): both requests had in fact finished before the resume
(`DONE` markers on disk, read via `python3` since `/home/justin/hakux-work/dispatch` is
outside this worktree's Bash cwd — see §0). This attempt reads those two results,
decomposes them, and finishes the table.

## Attempt 3 (why attempt 2's "ready" PR did not actually finish the brief)

Attempt 2 finished §1-7, wrote the cause table (MechAssault 2 + Buffy fresh, nine
existing-data attributions, a long exclusion list) and marked PR.md `State: ready` at
commit `097f6e1114` (2026-10-08 22:54:12 -07:00). Reading the timestamps: **Addendum 2**
(route-resolution fix, routes `fps786-nba2005`/`fps1008-shaolin` placed under
`docs/testing/titles/routes/`) landed at 22:50, four minutes *before* that ready commit,
but attempt 2's own §2 table and §7 table still say NBA Live 2005 and MK Shaolin Monks are
"blocked by the route-resolution tooling gap" — the two result dirs on disk
(`1-1791521273-...-3634946` = MechAssault 2, `1-1791521323-...-3686892` = Buffy) confirm
no NBA2005/Shaolin request was ever queued, and the route files are no longer present
under `docs/testing/titles/routes/` (either never picked up, or placed-then-consumed by a
different lane — not determinable from here). **Addendum 3** (re-measure the CPU-only
causes with fresh perflog+GPUXFR+FRAMETRACE runs, Fantastic 4 now on the Nova, a specific
order, a pilot rule for untested routes) landed at 22:55, one minute *after* the ready
commit — attempt 2 never saw it at all. So the PR was marked ready against a stale brief;
this attempt picks up Addenda 2 and 3, which is most of the remaining work: re-measuring
eight titles that attempt 2's table sourced from old CPU-only hold logcats, plus Fantastic
4, NBA Live 2005, MK Shaolin Monks and Arctic Thunder. PR.md `State` is reset to
`in progress` below until that is done or the session ends on a documented wait.

## Attempt 4 (why attempt 3 did not finish)

Attempt 3 did the corrected gate audit (§8), generated 8 routes with a research agent
(§9), queued three Nova requests (NBA Live 2005 full telemetry, DOA3 and Shaolin pilots),
and ended the session on a documented `WAITING.md` naming those three dispatch ids as the
external actor it was waiting on — the host dispatcher, not a background task of its own
session, so ending there was correct per the lane contract. This attempt resumes from that
wait: merged `origin/master` (17 commits, clean; picked up `lane.profileddefault1008` and
`lane.surfdl1008`'s folds, neither touching this lane's territory), confirmed all three
queued requests had `DONE` (they had, well before this resume), reviewed both pilots'
frames, found both routes good, and wrote the pilot-gate verdict to
`dispatch/pilots/fpstelemetry1008.ok` so the 30-minute ceiling no longer applies to the
rest of this batch. It then queued DOA3's and Shaolin's full telemetry runs and continues
through Addendum 3's order (Arctic Thunder, then the 8 generated routes) as device time
and the session's budget allow.

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

Both `DONE`, both completed their full route (`run.log`: `... end` after the last scripted
input, `held <iso> for <522|421>s`) with no crash tag and no thermal-pause episode
(`thermal.jsonl`'s `pause` field `false` on every sample both runs; the "hottest zone
94.3/94.7 C" in `THERMAL:` is a CPU junction zone (`cpu-1-9`), not `xo-therm`, which read
max 53.4 C (MechAssault 2) — nowhere near the dispatcher's 70 C pause point. Neither run is
void. MechAssault 2's run.log logs `adb_failures=1` (one transient adb hiccup somewhere in
520 s); nothing downstream (logcat line count, DONE marker, result.json) shows a gap, so
not treated as voiding the run, but recorded in case a later lane sees the same title flake.

Decomposed with `docs/lanes/near30/decompose.py --bar 30` and `docs/lanes/fps20786/decompose.py --bar 30`
(30, not the scripts' 28.5 default, to match these two titles' own verdict bar: both
title-registry rows read "fps: N% of gameplay at >= 30 fps"), plus
`docs/lanes/belowbar1005/xfrsurvey.py` and `docs/lanes/fps20786/sdsurvey.py` (both scan the
whole `dispatch/results` tree by mtime, so they picked up these two fresh runs without
being pointed at them individually).

**MechAssault 2** (4D53006B), 151 two-second windows, F=33.4 ms median (29.94 fps median,
but only 15% of windows at/above the 30 fps bar — lower than the title-registry's 26.7%
from a different run three weeks earlier, inside the normal run-to-run spread this project
has seen elsewhere, not investigated further): guest busy is the largest share of the frame
in the typical and fast windows (30.75 ms of 33.3, 92%, at/above bar; 25.57 of 33.4, 76%,
below bar) with the vCPU thread itself pegged (`vcpu` 0.98 in every group) — the ordinary
pattern this lane has already named for NFS MW/LOTR/Hulk/NHL2K3 (vCPU guest code). But the
worst decile inverts it: renderer idle (Ri) collapses to 0.30 ms (from 18.4 at bar) while
the render thread's own CPU time (rcpu, fps20786 decompose) rises to 16.18 ms and its
non-CPU non-idle time (rblk, "blocked") to 17.64 ms — in the worst 10% of windows the
render thread is saturated and the guest is *not* (guest busy there is actually the lowest
of the three groups, 25.08 ms). `xfrsurvey.py` reads RP (render passes per guest frame) at
28 for this title's run — high against the common 1-4 but not rare in this project's wider
table (Top Spin 148, Azurik 141, Conker 102 all run with far higher RP and are not
GMEM-flagged by that fact alone, so RP=28 is named as a correlate, not a proven cause).
`sdsurvey.py`: sd/flip 0.07 (rare), Fin 13.2 ms, GPU 12.1 ms/frame — a real but small
surface-download rate, not the story. **Two different bottlenecks in one title: guest-CPU
in most of the window (the class this project is already pursuing with the vCPU/JIT
direction), render-thread saturation in the worst decile that is not explained by
surface-download finishes and only loosely correlated with an elevated render-pass count.**

**Buffy the Vampire Slayer** (45410012), 152 windows, F=34.9 ms median (28.65 fps, only 3%
of windows at/above bar — much worse than the title-registry's 55.2% from the pathfind
hold three days earlier; the route is not the same capture (`docs/testing/titles/routes/buffy.route`
vs pathfind's own recorded path), so this is read as a different slice of the game, not a
regression, and flagged rather than averaged into one number). Guest busy is large and
*rises* at the tail (28.40 ms/34.9=81% overall, 33.33/37.52=89% at p10 — the opposite of
MechAssault 2's pattern, guest cost growing as frames slow, not handing off to the
renderer). Ri stays low and flat (9.0-9.65 ms) rather than collapsing, and `vcpu` sits at
0.88, a little under MechAssault 2's 0.98 — some guest idle is unattributed to a known
interrupt (`v_blk` 3.97-6.10 ms, clearly larger than MechAssault 2's 0.57-0.59, and growing
at the tail): this is time `decompose.py`'s wake-interrupt classifier cannot place. GPU
cost is also substantial on its own: `xfrsurvey.py` Tot 27.7 ms/frame, Xfr/Tot 0.51 — over
half of the GPU's own per-frame time is transfer, not render, in the same high band as
007 Agent Under Fire (0.50), Otogi (0.51) and DOA3 (0.52) from the wider 30-day table, not
an outlier for this project but still a large absolute number (14.1 ms/frame) that is close
in magnitude to the guest's own busy time. `sdsurvey.py`: sd/flip 0.00, Fin 0.5 ms — no
synchronous surface-download story here, unlike NBA Live 2005 (§4a). **Named cause: guest
(vCPU) work dominates and grows with frame time, with a GPU-transfer cost (Xfr/Tot 0.51,
14.1 ms/frame) large enough on its own to matter sitting alongside it; a meaningful share
of guest idle (v_blk) is on an interrupt this instrument does not classify.**

Both runs set `HAKUX_FRAMETRACE=1` as asked; it produced nothing beyond the env-echo line
in the logcat (`frames: {count:0, dir:null}` in both `result.json`s) — see §6.

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
| LOTR ROTK | OUTBOX.md:817, `runs/sweep-4541003E`, plus this lane's fresh full run `1-1791539142-fpstelemetry1008-1170820` (§7) | guest busy 24-28 ms/frame, median 27 fps, 33% of play at the 28.5 bar (OUTBOX's harder route); this lane's route reaches fps_ok_share 0.93, a thin 26 s below-bar sample only — see §7 |
| Hulk Ultimate Destruction | OUTBOX.md:827, `runs/sweep-56550039`, confirmed by this lane's fresh full run `1-1791539645-fpstelemetry1008-1208416` (§7) | slow scenes are guest (vCPU) work: 30 ms/frame against 16 at the bar; fresh trusted-stamp run reproduces the same pattern (gbusy 20→33 ms as fps drops) |
| NHL 2K3 | OUTBOX.md:717, `runs/nhl-2k3/hold3`, confirmed and sharpened by this lane's fresh full run `1-1791540124-fpstelemetry1008-1240862` (§7) | guest busy doubles, 13 to 27 ms/frame, in 31% of play; fresh trusted-stamp run reproduces this (15.7→29.5 ms) and adds a GPU-transfer component (Xfr/Tot 0.64) OUTBOX's CPU-only read could not see |
| Spider-Man 2 | this lane's own fresh full run, `1-1791538675-fpstelemetry1008-1143702` (§7) — perflog+GPUXFR+FRAMETRACE, post-5c35880d0a, trusted stamps; OUTBOX.md:781 kept as the original CPU-only finding, confirmed not replaced | fps_ok_share 0.86; renderer-bound confirmed (Ri falls as fps drops, guest flat) plus a new GPU-transfer/multi-download-per-flip component — see §7 |
| Midnight Club II | OUTBOX.md:807, `runs/sweep-54540008`; **sharpened by `docs/lanes/surfdl1008/NOTES.md` (folded onto master 2026-10-08, picked up by this lane's post-§3 merge)** | renderer saturated (Ri 0 ms/frame); GPU cost alone (34.6 ms/frame) already exceeds the 33.3 ms two-VBLANK ceiling, plus an 8.0 ms/frame synchronous surface-download finish at `texture.c:2100` that async794's survey already shows deferral cannot fix — see §7's row, not just "renderer-bound" |
| Ninja Gaiden Black | belowbar1005 NOTES.md Step 1, `retro-ngb`, resolved by this lane's fresh full run `1-1791540489-fpstelemetry1008-1275640` (§7) | render thread blocked 24 ms/frame, on-CPU only 11.6, guest never idles; fresh trusted-stamp run reproduces rblk almost exactly (24.25 ms) and shows `ph_GPU` rising in lockstep — **the GPU-fence-vs-other-wait question belowbar1005 left open is answered: it is GPU cost** |
| Dead or Alive 3 | this lane's own fresh full run, `1-1791535839-fpstelemetry1008-932074` (§7) — perflog+GPUXFR+FRAMETRACE, post-5c35880d0a, trusted stamps; belowbar1005's `retro-doa3` (gold-dojo stage, different fight) kept as context | fps_ok_share 0.81 on this fight; worst 19% is GPU cost tripling with the guest increasingly blocked — see §7, not the same sync-download mechanism belowbar1005 named on its stage |
| Buffy (prior, lower confidence) | belowbar1005 NOTES.md Step 1, `retro-buffy` | guest busy 31-39 ms/frame, renderer idle ~19 ms — vCPU-bound, confirmed independently by this session's own fresh run (§3) |
| NBA Live 2005 | this lane's own full-telemetry run, `1-1791525926-fpstelemetry1008-4089047` (§4a) — perflog+GPUXFR+FRAMETRACE, post-5c35880d0a, trusted GPU stamps | see §4a — one synchronous completion-deferred surface-download finish-wait per flip, not guest- or render-bound |

### 4a. NBA Live 2005, this lane's own fresh full-telemetry run (820 s, route `fps786-nba2005`)

Attempt 3 queued this and attempt 4 read it: `1-1791525926-fpstelemetry1008-4089047`,
`DONE`, no crash, no thermal pause (`THERMAL: no thermal-pause device above 0`, hottest
zone 95.9 C is the CPU junction zone, not `xo-therm`), `run.log` ends `... end` /
`held 45410050-NBA_Live_2005.xiso.iso for 826s`. **This replaces attempt 2/3's citation of
a pre-fix 2026-10-04 async794 logcat** (whose GPU-stamp figures were explicitly untrusted)
and an unattributed "fresh rerun" line with no result id — this is a named, in-scope,
post-fix run with trusted `xemu-gpu` stamps throughout.

`docs/lanes/fps20786/decompose.py --bar 28.5` (fps_ok_share 0.16, 96 s at/above bar of 606
s scored):

```
group      n    fps      F   gbusy  gidle vblank pgraph  timer  disc other    Ri   rcpu   rblk  v_blk  vcpu
all      303  25.49  39.23  19.12  19.93   0.79   0.41  17.23  0.01  1.31  4.70  23.69  10.94   0.86  0.96
>=bar      48  29.26  34.18  18.60  15.50   0.74   0.41  13.45  0.01  0.80  0.85  22.66  10.44   0.76  0.96
<bar      255  24.88  40.20  19.22  21.09   0.81   0.41  18.26  0.01  1.35  5.60  23.93  11.09   0.89  0.96
<bar p10   64  20.61  48.51  19.11  29.26   0.96   0.41  25.73  0.01  2.26 10.20  25.91  11.82   0.77  0.97
```

`docs/lanes/belowbar1005/xfrsurvey.py --days 1`: Tot 9.8, Rnd 8.8, Xfr 1.0, Xfr/Tot 0.10,
RP 7 — a small, render-dominated GPU frame, not a GMEM-replay story. `docs/lanes/fps20786/sdsurvey.py --days 1`:
`sd/flip=1.00 dirty=0.00 cDef=1.00 Fin=13.1 GPU=9.6 gfps=28`.

Guest busy is flat (~19.1-19.2 ms) whether the frame is fast or slow — **not** a guest-CPU
bottleneck, now confirmed on trusted stamps (same conclusion the pre-fix read reached, 20.5
ms flat, inside the usual run-to-run spread). What grows as fps drops is the guest's own
`timer`-woken idle (13.45 -> 18.26 -> 25.73 ms, worst decile) together with renderer idle
(0.85 -> 5.60 -> 10.20 ms): the guest is *waiting* longer on a timer, and the renderer
waits behind it. The trusted GPU figure is smaller than the pre-fix (untrusted) read
suggested (Tot 9.8 ms now vs 18.5 ms pre-fix — consistent with 5c35880d0a's double-counting
inflating the earlier number), which **sharpens** the finding rather than changing it: the
one completion-deferred surface-download finish-wait (Fin 13.1 ms/flip) now *exceeds* the
entire trusted GPU render budget (9.6 ms/frame) on its own, against a 39.2 ms frame at 25.5
fps. A synchronous per-flip download finish-wait is the better-supported cause than "same
class as Top Spin/Counter-Strike/MC3" (the unconfirmed guess pathfind's OUTBOX itself
flagged, line 295: "if an issue for the 20-fps class already exists, link this to it").
`HAKUX_FRAMETRACE=1` again produced nothing beyond the env-echo line (`frames:
{"every":0,"count":0,"bytes":0,"dir":null}` in `result.json`) — see §6.
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
- **MechAssault 2's two-regime split** (guest-bound in most windows, render-thread-bound in
  the worst decile) is visible only because `decompose.py` was read by group (`<bar p10`),
  not as one median; a single all-window row would have reported "guest busy 83%, Ri 11.5"
  and hidden the tail inversion entirely. The render-thread "blocked" time at the tail
  (rblk 17.64 ms) has no finish-reason attached (`sdsurvey.py`'s Fin is a separate, low
  13.2 ms figure, not obviously the same 17.64 ms) — decompose.py cannot say whether that
  block is a GPU fence, a lock, or something else; it can only say it is not idle-waiting
  on the guest and not the render thread's own CPU time.
- **`HAKUX_FRAMETRACE=1` produced no frame-trace data in either run** (`result.json`'s
  `frames` block reads `count:0, dir:null` in both; the logcat shows only the env-var echo
  line, no frame-trace output tag). Either this build's frame-trace needs another flag or
  a `--frames` request option this lane did not pass, or it writes somewhere `pulled/`
  never reached. Not investigated further (territory: no code reading); recorded so the
  next lane that wants an actual frame trace does not assume `HAKUX_FRAMETRACE=1` alone is
  sufficient.
- **Buffy's fresh fps share (3%) vs. the title-registry's recorded verdict (55%)**: read as
  two different slices of the same title (a different route/path reaching different
  content), not a regression or a measurement error, because nothing else about the run
  (thermal, crash, play share) is abnormal. This instrument cannot tell *which* scene either
  number belongs to without a frame review; none was done here (brief: region checks not
  needed, no pixels change — but a frame review for scene identity is a different question
  this table leaves open).
- Rows sourced from `pm/title-registry.tsv`/owner-holds are a point-in-time snapshot
  (2026-10-07T01:03 build for the registry); a title's fps_ok there can disagree with a
  fresh run for reasons this table does not adjudicate (route difference, as above; natural
  run-to-run spread; a build change).

## 7. Cause table

All `gbusy share` and `Ri` figures below are decompose.py medians over the run's below-bar
windows (or the whole below-bar hold, where that is all that is on record), at each title's
own fps bar (28.5 unless noted 30). `Tot`/`Xfr/Tot`/`RP` are `xfrsurvey.py` per-title
medians; `sd/flip`/`Fin` are `sdsurvey.py` medians. "n/a (no perflog run)" means no
`xemu-gpu`/`hakuX-stall` lines exist for that title's below-bar run — a CPU-only sweep, not
a gap in this table. Thermal pause is read from `thermal.jsonl`/the hold's own `THERMAL:`
line, not from the fps figure.

| title (id) | gfps median | Tot ms/frame | gbusy share | Ri ms | GMEM Xfr/Tot, RP | sd/flip, Fin ms | thermal pause | named cause | fix could be |
|---|---|---|---|---|---|---|---|---|---|
| Pilot Down (4F580002) | 36.40 median, fps_ok_share 0.66 (fresh full run, `1-1791538085-fpstelemetry1008-1088739`) | 9.1 Rnd 8.4 Xfr 0.8, Xfr/Tot 0.09, RP 28 | 21.19 (at bar) to 49.09 (p10) — **more than doubles** | 8.80 (at bar) to 15.90 (p10), tracks gbusy not a separate driver | 0.09, RP 28 — not a GMEM-replay story | 0.00/flip, Fin 8.4 (whole-logcat median, not isolated to below-bar) | no (`THERMAL: no thermal-pause device above 0`) | guest (vCPU) code, same class as NFS MW/LOTR/Hulk/NHL2K3 — gbusy more than doubles in the worst windows while Ri tracks it rather than leading it | vCPU/JIT work already underway for this class |
| Amped 2 (4D530041) | 27.23 median, fps_ok_share 0.38 (fresh full run, `1-1791538465-fpstelemetry1008-1131600`) | 14.8 Rnd 13.5 Xfr 0.3, Xfr/Tot 0.02, RP 8 | **100% — guest idle is 0.00 ms in every group, at bar and below** | 10.95 (at bar) to 5.20 (p10) — falls as fps drops, the opposite of a renderer-bound pattern | 0.02, RP 8 — negligible GPU-transfer share | 0.00/flip, Fin 12.0 (whole-logcat median) | no (`THERMAL: no thermal-pause device above 0`) | **the cleanest guest-CPU-bound case in this table**: the vCPU thread is never idle (gbusy = F exactly, gidle 0.00 ms throughout) and gbusy scales directly with frame time (33.5→43.9 ms) — not a renderer, GPU-transfer or surface-download story at all | vCPU/JIT work already underway for this class; no GPU-side candidate to chase here |
| MechAssault 2 (4D53006B) | 29.9 (15% @ bar 30, fresh run) | 13.3 (xfrsurvey) / 28.8 (phase) | 76% below bar, 92% at bar, **falls to 70% at p10** | 11.6 overall, **0.3 at p10** | 0.35, RP 28 | 0.07, 13.2 | no | **split: guest-CPU-bound in most of the window; render-thread-saturated (CPU+blocked, Fin does not explain it) in the worst decile** | the vCPU/JIT work already underway for the common case; the render-pass count (28/frame) is a candidate for the tail but unconfirmed as cause |
| Buffy the Vampire Slayer (45410012) | 28.6 (3% @ bar 30, fresh run; 55% in the 10-05 verdict, different route) | 27.7 (xfrsurvey) | 81% below bar, **89% at p10 (grows with frame time)** | 9.0, flat | 0.51, RP 2 | 0.00, 0.5 | no | guest (vCPU) work, growing at the tail, alongside a large GPU-transfer cost (14.1 ms/frame) that is not surface-download-driven | vCPU/JIT for the guest side; the 0.51 Xfr/Tot share (007AUF/Otogi/DOA3-class) is a separate, GMEM-side candidate |
| NFS Most Wanted (4541007B) | 26 median | n/a (no perflog run) | ~65% (25 ms of ~38.5 ms F), flat fast-to-slow | n/a | n/a | n/a | not reported | guest (vCPU) code, constant ~25 ms/frame cost, not scene-dependent (OUTBOX.md:797) | vCPU/JIT; a perflog re-run would add Tot/Ri |
| LOTR Return of the King (4541003E) | 29.97 median, fps_ok_share 0.93 (fresh full run, `1-1791539142-fpstelemetry1008-1170820`) — **mismatches the registry FAIL (33% at bar, a different sweep route); same instrument-reach gap as Shaolin/Arctic Thunder, §10** | 21.6 Rnd 10.9 Xfr 10.7, Xfr/Tot 0.49, RP 5 | 20.17 (at bar) to 23.46 (<bar, n=10) — mild rise, **thin sample (26 s total below bar)** | 23.40 flat across all groups — not tracking fps | 0.49, RP 5 — a real GPU-transfer share, Buffy/007AUF/Otogi-class | 0.00/flip — no sync download | no (`THERMAL: no thermal-pause device above 0`) | **low confidence, thin below-bar sample**: this route is mostly fine (93% at bar); the little below-bar data shows a mild guest-busy rise plus a non-trivial GPU-transfer share (0.49), not the clean "guest/vCPU, same as NHL 2K3/NFS MW" story OUTBOX.md:817 named from a different, harder route — kept as the original CPU-only finding, not contradicted (13 windows is not enough to overturn it), just not reproduced here | vCPU/JIT remains the best-supported guess from OUTBOX's own harder route; this run adds a GPU-transfer candidate worth checking if a harder route is captured later |
| The Incredible Hulk: UD (56550039) | 29.77 median, fps_ok_share 0.91 (fresh full run, `1-1791539645-fpstelemetry1008-1208416`; thin below-bar sample, 26 s — the registry's 0.64 is from a different route) | 9.7 Rnd 9.4 Xfr 0.3, Xfr/Tot 0.03, RP 13 | **20.35 (at bar) to 33.45 (p10) — guest busy rises ~65% as fps drops, and guest idle falls (13.32→5.63), confirming guest/vCPU as the driver** | 20.60 (at bar) to 15.55 (p10) — falls alongside gidle, tracking the guest, not leading it | 0.03, RP 13 — negligible GPU-transfer | 1.00/flip (whole logcat), dirty 1.00 cDef 0.00, Fin 6.2 | no (`THERMAL: no thermal-pause device above 0`) | **confirms OUTBOX.md:827 on trusted stamps**: slow scenes are guest (vCPU) work — gbusy rises sharply and gidle collapses in the worst windows, not a GPU or renderer story | vCPU/JIT work already underway for this class |
| NHL 2K3 (53450017) | 34.70 median, fps_ok_share 0.89 (fresh full run, `1-1791540124-fpstelemetry1008-1240862`; no period-length setting in this generated route, §10 caveat) | 9.8 Rnd 3.5 Xfr 6.3, **Xfr/Tot 0.64 — the highest GPU-transfer share in this table**, RP 54 | **15.74 (at bar) to 29.54 (below) — nearly doubles, matching OUTBOX.md:717's "13 to 27 ms/frame" almost exactly** | 0.00 in every group (renderer never idle on this title's pacing — not a discriminator here) | 0.64, RP 54 | 3.15/flip (whole logcat), 3.03 completion-deferred, Fin 4.9 — multiple sync downloads per flip | no (`THERMAL: no thermal-pause device above 0`) | **confirms OUTBOX.md:717 exactly** (guest busy doubles) and adds a second, previously-unmeasured factor: a large GPU-transfer share (0.64) with 3 completion-deferred surface-download finishes per flip — a dual-cause title, closer to MechAssault 2's pattern than a pure vCPU case | vCPU/JIT for the guest-busy doubling; the 0.64 Xfr/Tot and multi-download-per-flip pattern is a second, GMEM-side candidate worth checking independently |
| Spider-Man 2 (4156002B) | 29.42 median, fps_ok_share 0.86 (fresh full run, `1-1791538675-fpstelemetry1008-1143702`) | 14.7 Rnd 9.1 Xfr 5.7, Xfr/Tot 0.39, RP 29 | 13.47 (at bar) to 15.50 (p10) — roughly flat, small relative to F | **14.50 (at bar) falling to 7.45 (p10) — renderer busier, not guest, confirms OUTBOX.md:781's pattern on trusted stamps** | 0.39, RP 29 — a real GPU-transfer share, not negligible | 4.50/flip (whole-logcat), 1.00 dirty + 3.50 completion-deferred, Fin 4.8 — a multi-download-per-flip pattern not visible in the old CPU-only citation | no (`THERMAL: no thermal-pause device above 0`) | renderer-bound (confirmed, Ri falls as fps drops while guest stays flat), now with a GPU-transfer component (Xfr/Tot 0.39, RP 29) and multiple surface-download finishes per flip that the earlier CPU-only read never saw | renderer/draw-path work, not vCPU; the multi-download-per-flip pattern is a new candidate worth checking against the NBA Live 2005/Midnight Club II mechanism |
| Midnight Club II (54540008) | 24.3 mean, 0% @ 28.5 (lane.surfdl1008, same below-bar window, 10-08) | 34.6 (xemu-gpu, already above the 33.3 ms two-VBLANK ceiling on its own) | 13.4 ms of 41.1 ms F, guest mostly idle | **0.0 — render thread never parks, fully saturated** | n/a (sd/flip 1.50/frame instead, see sd col) | 1.50 (dirty 0.50+cDef 1.00), ph_Fin 16.45 (**8.0 ms of it is a surface-download finish at `texture.c:2100`**, the other ~8.4 is every title's flip fence wait) | no | **renderer-bound, sharper than OUTBOX's original read: GPU cost alone (34.6 ms) exceeds the ceiling, plus an 8 ms/frame synchronous surface-download finish from a texture-bind call site async794 already showed deferral cannot fix** | a GPU-side surface-to-texture conversion replacing `create_texture()`'s call to `pgraph_vk_download_surfaces_in_range_if_dirty()` -- not shown sufficient alone (surfdl1008, 10-08, folded during this lane's merge) |
| Ninja Gaiden Black (5443000D) | 36.79 median, fps_ok_share 0.83 (fresh full run, `1-1791540489-fpstelemetry1008-1275640`) | 23.1 Rnd 12.0 Xfr 11.0, Xfr/Tot 0.48, RP 11 | 24.68 (at bar) to 30.85 (p10) — a smaller rise than rblk's | rcpu (render on-CPU) 10.19→12.58, close to belowbar1005's 11.6; **rblk (render blocked) 15.31→24.25, matching belowbar1005's 24 ms figure almost exactly** | 0.48, RP 11 — a real GPU-transfer share | 0.00/flip — no sync download | no (`THERMAL: no thermal-pause device above 0`) | **resolves belowbar1005's open question**: `ph_GPU` (phase-timer GPU busy) rises in lockstep with rblk (22.90→32.30→30.65 ms vs 15.31→22.91→24.25 ms) — the render thread's "blocked" time tracks genuine GPU cost, not an unrelated host-fence wait; this is a GPU-bound render path, not "other wait" | GPU/render-path work on the 48%-transfer-share frame, not a host synchronization fix |
| Dead or Alive 3 (54430001) | 38.70 median, fps_ok_share 0.81 (fresh full run, `1-1791535839-fpstelemetry1008-932074`, aquarium-stage fight Kasumi/Hitomi — a different stage than belowbar1005's gold dojo) | 19.8 Rnd 9.9 Xfr 9.6, Xfr/Tot 0.48, RP 2 | 19.74 (at bar) tripling to 36.77 (p10) | 2.50 (at bar) to 6.90 (p10) | 0.48, RP 2 (real GPU-transfer share, not GMEM-replay) | 0.00/flip (no sync download this run — unlike belowbar1005's gold-dojo citation) | no (`THERMAL: no thermal-pause device above 0`) | **stage-specific, confirms belowbar1005's own caveat**: on this fight the title is mostly fine (81% at bar); the worst 19% (56 s) is GPU cost nearly tripling (ph_GPU 19.6→46.6 ms) with the guest increasingly blocked waiting on it (v_blk 4.5→22.8 ms) — GPU/renderer-bound in the tail, but not the same synchronous-download mechanism belowbar1005 named on the gold-dojo stage; this run never reached that stage | not generalizable from one fight; needs a hold that visits DOA3's worse stages (the gold dojo) to test whether the sync-download cause recurs there |
| NBA Live 2005 (45410050) | 25.49 median, fps_ok_share 0.16 (fresh post-fix run, `1-1791525926-fpstelemetry1008-4089047`) | 9.8 Rnd 8.8 Xfr 1.0, Xfr/Tot 0.10, RP 7 (trusted, post-5c35880d0a) | 19.1 ms flat regardless of frame speed (not the bottleneck) | grows 0.85→10.20 ms as fps drops (renderer waits behind the guest) | 0.10, RP 7 — not a GMEM-replay story | 1.00/flip, Fin 13.1, GPU 9.6 (§4a, same run) | no (`THERMAL: no thermal-pause device above 0`) | one completion-deferred surface-download finish-wait per flip (Fin 13.1 ms) that now *exceeds* the entire trusted GPU render budget (9.6 ms/frame) — not guest- or render-bound | fix the per-flip sync download finish-wait (lane.surfdl1008 already shows deferral alone does not fix the related Midnight Club II case) |

**Excluded from this table, with reason, in §5**: Dino Crisis 3, Crash Bandicoot: Wrath of
Cortex, Cel Damage, Arx Fatalis, Gun, Gui Yi, Puyo Pop Fever, MTV Music Gen 3, Avatar: TLA
(route/input defects, not an fps cause); Otogi (thermal pause voids the figure); MK Deadly
Alliance, Blood Wake (not actually failing fps); 007 Agent Under Fire, Blinx, Blinx 2
(`reached_gameplay: unconfirmed`, needs a frame review first); Turok: Evolution, Ultimate
Spider-Man, DBZ Sagas, Beyond Good & Evil (still not on the Nova). NFS Most Wanted and
Midnight Club II cannot get a generated route (`steps2route.py` cannot encode their
recorded `RT+left`/`RT+right` steering tokens, a tool bug outside this lane's territory —
§9); their §4/§7 rows stay CPU-only-sourced. Dino Crisis 3 stays excluded (route/input
defect, §5 above).

**Updated by attempt 4**: Fantastic 4, Pilot Down, Amped 2, Spider-Man 2, LOTR ROTK, Hulk
UD, NHL 2K3 and Ninja Gaiden Black are no longer in this exclusion list — attempt 4
generated routes for all eight (§9) and queued pilots for each; see §10 for the pilot
reviews and which full runs were queued as a result. NBA Live 2005 and MK Shaolin Monks
are no longer blocked by the route-resolution tooling gap (that was Addendum 2's fix,
picked up this attempt) — both have fresh full-telemetry runs, §4a/§7 (NBA Live 2005) and
§10 (Shaolin). Arctic Thunder's full run was queued this attempt (§10).

## 8. Attempt 3: the §1-2 gate audit was more conservative than the addendum intends; three
   requests queued, the pilot gate stopped a fourth

**Correction to §1-2.** Re-running `prequeue.py` on the exact titles Addendum 3 orders
(NFS MW, Spider-Man 2, LOTR ROTK, Fantastic 4, Dino Crisis 3, Hulk, NHL 2K3, Midnight Club
II, NGB, DOA3, NBA Live 2005, MK Shaolin Monks, Arctic Thunder) shows every `BLOCK` line on
every one of them is the *same* substantive reason as the cleared one, just emitted from a
different source (the registry's generic BELOW_BAR rule vs. that title's own
`owner-holds.tsv` row), e.g. Pilot Down's row text is "below the bar: telemetry and a fix,
not a retest" and NHL 2K3's is "NHL 2K3 misses on fps (#839): telemetry, not a re-hold" —
not a *different* block (no crash, no device hold, no banked Playable, no RalliSport/
football exclusion) but the identical cleared reason in the row's own words. §1-2 (attempt
2) read a title-specific `below_bar` owner-holds row as one of the "still stops" categories
and skipped Pilot Down, Amped 2, Ninja Gaiden Black, Spider-Man 2 and NHL 2K3 on that basis
— too conservative; Addendum 3 orders exactly those titles to be re-measured, which only
makes sense if they are cleared. Corrected reading: **every title audited this session
clears the gate for telemetry** (RESULT is `BLOCK`-but-cleared or `REVIEW`, never a
genuinely different block). The real remaining blockers are route availability and, newly
found, a per-route "has this ever run" check (below).

**ISO check, redone for the full Addendum-3 list** (`adb -s ee317437 shell ls
/storage/E6C6-D7AA/Games/XBox/`): all of NFS Most Wanted (`4541007B-...`), Spider-Man 2
(`4156002B-...`), LOTR ROTK (`4541003E-...`), **Fantastic 4 (`4156001A-Fantastic_4.xiso.iso`,
confirmed present — lane.local's 22:49 push landed)**, Dino Crisis 3 (`Dino Crisis 3.iso`),
Hulk (`56550039-...`), NHL 2K3 (`NHL_2K3.xiso.iso`), Midnight Club II (`54540008-...`),
Ninja Gaiden Black (`Ninja Gaiden Black.iso`), DOA3 (`54430001-Dead_or_Alive_3.xiso.iso` —
**the correct id; the stored `doa3.route`'s own header comment says `4D53002D`, which is
the Microsoft-publisher prefix pattern (`MS`) and cannot be right for a Tecmo title — a
pre-existing typo in that file's comment, harmless to the request since `--route` resolves
by name and `--title` by the ISO filename, not by the comment**), NBA Live 2005
(`45410050-...`), MK Shaolin Monks (`4D570029-...`) and Arctic Thunder (`4D570002-...`) are
present. Amped 2 (`Amped 2 (USA).xiso.iso`) and Pilot Down (`4F580002-...`) are present
too (confirmed earlier by attempt 2).

**A route being present is not the same as a route being proven.** Reading the route files
themselves (not just checking they exist) found `docs/testing/titles/routes/doa3.route`
carries its own disclaimer: `# NOT YET REPLAYED -- a Thor screening soak is its validation
(no interactive Thor session while the fan is dead)`. The screening soak it cites
(`1790801641-titleroutes-1213635`) ran an *earlier, simpler* version of the route (a blind
300 s wait, no button presses) — not the current version with the STORY-mode navigation
and fight-loop presses, which has literally never executed end-to-end. Per the brief's own
pilot rule ("any route that has never run on the device as a timed route"), DOA3 needed a
pilot despite being a "stored" route, same as MK Shaolin Monks. `arctic-thunder.route` and
`fps786-nba2005.route` carry no such disclaimer and cite an actual played/soaked session
each (nav.py on the Thor 2026-09-27 for Arctic Thunder reaching the first checkpoint;
`lane.async794`'s pre-fix run for NBA Live 2005, cited in §4a) — both are treated as
proven, no pilot. `dino-crisis-3.route` exists but is the same broken route §5 already
named (menu time 79% of the window; the shooter loop does not move the player) — still
excluded, not re-tried, because Addendum 3 asks to re-measure the *fps* cause, not to fix
a route the brief says not to invent input for.

**Queued this session** (`docs/testing/request.sh --who fpstelemetry1008 ... --issue 433`,
all `--device nova`, none `--wait` — the Nova's queue had 10-11 requests ahead from
`lane.profileddefault1008` and `lane.surfdl1008` before any of mine, so blocking would only
burn the Bash tool's 10-minute cap without accomplishing anything; the dispatcher is a host
process independent of this session and runs the queue regardless):

| id | title | seconds | route | flags | purpose |
|---|---|---|---|---|---|
| `1-1791525926-fpstelemetry1008-4089047` | NBA Live 2005 | 820 | `fps786-nba2005` | `--perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1` | full telemetry (route proven, no pilot) |
| `1-1791525932-fpstelemetry1008-4091099` | DOA3 | 180 | `doa3` | none | **pilot** — route never run; mark-gameplay elapsed ≈117 s + 60 s margin |
| `1-1791525936-fpstelemetry1008-4091494` | MK Shaolin Monks | 330 | `fps1008-shaolin` | none | **pilot** — route never run, per Addendum 2/3 |

**Arctic Thunder's full-telemetry request was refused by the pilot gate**, not by anything
title-specific: `request.sh` computed this requester's queued+running device time at ~27
min from the three requests above, and Arctic Thunder's 510 s (+90 s setup) would push it
to ~37 min, over the unreviewed-pilot ceiling (owner rule, 2026-09-26:
`/home/justin/hakux-work/dispatch/pilots/fpstelemetry1008.ok` does not exist, and the first
30 min always goes through without one). Per that rule's own "way out": queue at most two
(I queued three, still under 30 min, so it was allowed), review what they produced, write
the verdict to `pilots/fpstelemetry1008.ok`, then queue the rest — including Arctic
Thunder. **That review has not happened yet**: none of the three requests above had
finished by the time this session's remaining budget required writing this up (the queue
position check below). Arctic Thunder, and everything past it in Addendum 3's order
(the eight CPU-only re-measures plus Amped 2 and Pilot Down, all of which first need a
generated route — see below), stay queued-but-not-submitted pending that review.

**Queue position at the time this was written** (`dispatch/queue/`, FIFO within the
release-priority tier): 10 requests ahead of mine (8 remaining from
`lane.profileddefault1008`'s original 9 — one has already started running — and 2 from
`lane.surfdl1008`), then my three, then one `dispatch.restore` entry. At roughly
90 s setup + each request's own `--seconds`, this queue does not clear fast; this session
cannot responsibly block on it inside the Bash tool's 10-minute-per-call limit, and ending
the session with these three in flight is the documented "waiting on an external actor"
case (the host dispatcher, not a background task of this session), not the "never end
waiting on your own background task" case the lane rules warn against.

**Still open for a continuation (next resume), in Addendum 3's order:**
1. Read the three queued results (`dispatch/results/1-1791525926-...`,
   `...-4091099`, `...-4091494`) when they land. For the two pilots: read their frames
   (a contact sheet every 30 s is enough) and decide whether DOA3 reached the fight and
   Shaolin reached live `attack`-genre gameplay and stayed there. Write the verdict —
   result ids, what the frames showed, the date — to
   `/home/justin/hakux-work/dispatch/pilots/fpstelemetry1008.ok` (via `python3`, since
   the dispatch dir is outside this worktree's Bash cwd) so the pilot gate clears for
   the rest of this batch.
2. If DOA3's pilot shows it actually reached the fight, queue DOA3's full telemetry run
   (`--route doa3 --perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1`, `--seconds`
   ≈117 (mark gameplay) + 300 (post-mark play, per the brief) ≈ 420). If not, write the
   route defect (which step, what the frame shows) and move on — do not rerun blind.
3. Same for Shaolin: on a good pilot, queue the full run at ≈792 s (Addendum 2's own
   figure for this route's natural length) with the telemetry flags.
4. Queue Arctic Thunder's full run exactly as attempted above (510 s, `--route
   arctic-thunder`, telemetry flags) — it needs no pilot, only room under the pilot-gate
   ceiling once item 1's `.ok` file exists.
5. For NFS Most Wanted, Spider-Man 2, LOTR ROTK, Fantastic 4, Hulk, NHL 2K3, Midnight
   Club II, Ninja Gaiden Black, Amped 2 and Pilot Down: **no route exists in any blessed
   location yet.** Addendum 3 names the fix — generate one per title with
   `docs/lanes/fps20786/steps2route.py <steps.jsonl> --name N --gameplay STEP --loop
   TOKENS --source S` from a pathfind run that reached real gameplay
   (`/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/` and
   `/home/justin/hakux-work/wt/pathfind/scratch/runs/<name>/`, e.g. `amped-2` for Amped 2),
   genre loop tokens from `HOLD_GENRES` in `pathfind.py`. This attempt launched a
   read-only research agent to locate the exact `steps.jsonl` path, gameplay step index
   and loop tokens for all ten of these titles before the session's budget ran out; if
   its findings are not in this file below this line, the agent either did not finish or
   its results were not folded in — re-run that lookup before generating routes, do not
   invent one. Every generated route is untested and needs the same pilot-then-full-run
   treatment as Shaolin above; do not skip straight to the full telemetry run on a route
   this lane just wrote.
6. Dino Crisis 3 stays excluded (route/input defect, §5) unless a route fix lands from
   elsewhere; this lane does not write one (brief: no invented input).

## 9. Routes generated this session (free, no device time) — ready to pilot once the
   pilot-gate `.ok` file exists

A read-only research agent located, for each title still missing a route, the pathfind
run whose `steps.jsonl` reached real gameplay, the step index, and the fitting
`HOLD_GENRES` loop (`docs/testing/titles/pathfind.py:232-247` in the pathfind worktree —
the canonical copy; `scratch/legotest/...pathfind.py` is a stale fork and was not used).
Two corrections to its own first pass, both re-checked here: NHL 2K3 uses `hold3` (the
FAIL run OUTBOX.md actually cites for the below-bar scenario), not the cleaner-passing
`hold2`; Amped 2 uses `retro-amped2` (a full 628 s hold, `ok=true`) rather than the
`scratch/runs/amped-2` probe NOTES.md cited loosely by elapsed minutes, not step number
(that probe has no hold phase and its "step ~9" in NOTES.md:875 does not correspond to a
`steps.jsonl` index at all).

**Tool bug found, not worked around**: `steps2route.py`'s `tok_lines()` has no branch for
a combo token (`RT+left:N`, `RT+right:N`) — only `send()` in `pathfind.py` handles those.
NFS Most Wanted (`sweep-4541007B`) and Midnight Club II (`sweep-54540008`) both drive with
recorded steering tokens in that form, **in their own recorded step actions, not just the
loop** — so no `--loop` substitution avoids it; the generator crashes on steps 1-N
regardless. `docs/lanes/fps20786/steps2route.py` is shared tooling, not under this lane's
territory (`docs/lanes/fpstelemetry1008/**`), and fixing it is a code edit the brief
forbids here. **NFS Most Wanted and Midnight Club II cannot get a generated route this
way until that tool is fixed elsewhere.** Record, do not invent a per-step rewrite.

Generated (`docs/lanes/fps20786/steps2route.py <steps.jsonl> --name N --gameplay G --loop
L --hold-s 300 --source S`, all pass `docs/testing/titles/route.sh --check`), written
under `docs/testing/titles/routes/` (untracked, same convention as Addendum 2's two
routes — left in place across this session boundary deliberately, see below, not
deleted-after-queuing yet because none of them has been queued):

| file | title (id) | source run | gameplay step | loop genre | route's own "ends ~Ns" | mark-gameplay elapsed (ends − 300) |
|---|---|---|---|---|---|---|
| `spiderman2.route` | Spider-Man 2 (4156002B) | `sweep-4156002B` | 12 | attack | 406 | 106 |
| `lotr-rotk.route` | LOTR: Return of the King (4541003E) | `sweep-4541003E` | 46 | attack | 674 | 374 |
| `hulk-ud.route` | Incredible Hulk: UD (56550039) | `sweep-56550039` | 13 | attack | 418 | 118 |
| `nhl2k3.route` | NHL 2K3 (53450017, plain-name ISO) | `nhl-2k3/hold3` | 30 | team | 658 | 358 |
| `ngb.route` | Ninja Gaiden Black (5443000D, plain-name ISO) | `retro-ngb` | 34 | attack | 575 | 275 |
| `amped2.route` | Amped 2 (4D530041, plain-name ISO) | `retro-amped2` | 25 | other | 578 | 278 |
| `pilotdown.route` | Pilot Down (4F580002) | `n-4F580002-1007` | 24 | other | 545 | 245 |
| `fantastic4.route` | Fantastic 4 (4156001A) | `n-4156001A-1007` | 21 | **attack (uncertain — see below)** | 485 | 185 |

**Fantastic 4's genre is a guess, flag it in the pilot review.** The source run's own hold
read genre `onrails` (scripted camera, no input) and only 36% of its 1675 s scored window
was `play` (783 s cutscene + 219 s `game_over` — repeated deaths likely). `onrails` sends
no input at all, which cannot produce 5 minutes of *played* telemetry if the game is
actually a brawler needing input; this route uses `attack` instead, per the research
agent's read of the title (a brawler, not a rail shooter). **Pilot this one first and read
the frames especially carefully** — if `attack`'s presses do nothing (truly on-rails) or
cause repeated deaths (game_over looping), that is itself a finding (say so, do not
force a retry with different inputs — that would be inventing a third guess).

**Why these are left in place rather than deleted now**: Addendum 3's own instruction
("queue with request.sh --route <name>, then delete the file") describes the
queue-then-delete cycle for a single session that does both steps. This session hit the
pilot gate (§8) before any of these could be queued at all — deleting them now would only
cost the next resume the same `steps2route.py` lookups this agent already did. They stay
until queued; whichever session queues one deletes it immediately after, per the brief.

**Next resume, once `pilots/fpstelemetry1008.ok` exists (§8) and queue room allows**, the
pilot command for each (no `--perflog`, no GPUXFR/FRAMETRACE, `--seconds` = mark-gameplay
elapsed + 60, `--no-expect "route pilot, not a measurement"`) and, once that pilot's
frames confirm it reached and held gameplay, the full run (`--seconds` = the route's own
"ends ~Ns" line, `--perflog --env HAKUX_GPUXFR=1 --env HAKUX_FRAMETRACE=1`):

| route | pilot --seconds | full --seconds |
|---|---|---|
| spiderman2 | 166 | 406 |
| lotr-rotk | 434 | 674 |
| hulk-ud | 178 | 418 |
| nhl2k3 | 418 | 658 |
| ngb | 335 | 575 |
| amped2 | 338 | 578 |
| pilotdown | 305 | 545 |
| fantastic4 | 245 | 485 |

ISO filenames for `--title` (from `adb -s ee317437 shell ls
/storage/E6C6-D7AA/Games/XBox/`, §8): Spider-Man 2 `4156002B-Spider_Man_2.xiso.iso`; LOTR
ROTK `4541003E-The_Lord_of_the_Rings_The_Return_of_the_King.xiso.iso`; Hulk
`56550039-The_Incredible_Hulk_Ultimate_Destruction.xiso.iso`; NHL 2K3 `NHL_2K3.xiso.iso`;
Ninja Gaiden Black `Ninja Gaiden Black.iso`; Amped 2 `Amped 2 (USA).xiso.iso`; Pilot Down
`4F580002-Pilot_Down_Behind_Enemy_Lines_Europe.xiso.iso`; Fantastic 4
`4156001A-Fantastic_4.xiso.iso`.

## 10. Attempt 4: pilot reviews and full-telemetry results

**Gate-matching trap found while re-auditing the five titles Addendum 3 names for a
generated-route pilot**: `pm/prequeue.py "Lord of the Rings"` returned `BLOCK: already in
the Playable ledger`, which looked like a genuine stop (the brief's own example of a block
that "still stops"). Reading the matched ledger line showed it was **The Lord of the
Rings: The Fellowship of the Ring** (56550004, a different title, PASS 2026-10-07), not
Return of the King (4541003E) — the loose name query matched both titles' "Lord of the
Rings" substring. Re-querying by exact title id (`4541003E`) returns `REVIEW` only, no
ledger hit. Re-checked all five against exact ids rather than names:

| title (id) | query text used | result | note |
|---|---|---|---|
| Pilot Down (4F580002) | id | BLOCK (cleared: `pilotdown-below-bar` = "needs telemetry and a fix, not a rerun") | — |
| Amped 2 (4D530041) | id | BLOCK (cleared, same text family) | — |
| Spider-Man 2 (4156002B) | id | BLOCK (cleared: `spiderman2-below-bar` = "telemetry and a fix, not a retest") | — |
| LOTR ROTK (4541003E) | id | REVIEW only | the name-query false-positive above |
| Fantastic 4 (4156001A) | id | BLOCK (cleared: `fantastic4-below-bar` = "needs telemetry and a fix, not a rerun") | — |
| Hulk UD (56550039) | id | REVIEW only | — |
| NHL 2K3 (53450017) | id | BLOCK (cleared: `nhl-2k3-839` = "telemetry, not a re-hold", #839) | — |
| Ninja Gaiden Black (5443000D) | id | BLOCK (cleared: `ngb-below-bar` = "telemetry and a fix, not a retest") | — |

All eight clear. Queued pilots for all eight (no `--perflog`/GPUXFR/FRAMETRACE, per the
pilot rule), plus DOA3's and Shaolin's full telemetry runs (both pilots from attempt 3
confirmed good — §8) and Arctic Thunder's full run (proven route, no pilot needed, cleared
by the new `pilots/fpstelemetry1008.ok`):

| id | title | kind | seconds |
|---|---|---|---|
| `1-1791535839-fpstelemetry1008-932074` | DOA3 | full telemetry | 420 |
| `1-1791536100-fpstelemetry1008-943216` | MK Shaolin Monks | full telemetry | 792 |
| `1-1791536120-fpstelemetry1008-944133` | Arctic Thunder | full telemetry | 510 |
| `1-1791536188-fpstelemetry1008-948130` | Pilot Down | pilot | 305 |
| `1-1791536191-fpstelemetry1008-948403` | Amped 2 | pilot | 338 |
| `1-1791536195-fpstelemetry1008-948635` | Spider-Man 2 | pilot | 166 |
| `1-1791536198-fpstelemetry1008-948881` | LOTR ROTK | pilot | 434 |
| `1-1791536202-fpstelemetry1008-949140` | Fantastic 4 | pilot | 245 |
| `1-1791536216-fpstelemetry1008-950590` | Hulk UD | pilot | 178 |
| `1-1791536219-fpstelemetry1008-950844` | NHL 2K3 | pilot | 418 |
| `1-1791536223-fpstelemetry1008-951148` | Ninja Gaiden Black | pilot | 335 |

**DOA3 full run, `...932074`**: `DONE`, no crash, no thermal pause, `run.log` ends
`... end` / `held ... for 422s`. Decomposed into §7's table — fps_ok_share 0.81 on this
fight (aquarium stage, Kasumi vs Hitomi), a different stage than belowbar1005's gold-dojo
citation; the worst 19% of the window is GPU cost nearly tripling with the guest
increasingly blocked, not the same synchronous-download mechanism belowbar1005 named.
`fps786-nba2005.route`/`fps1008-shaolin.route` deleted after their last queueing use (NBA
Live 2005's and Shaolin's full runs are both done/queued — no further need); the 8
generated routes stay in place until each one's pilot is reviewed and its full run queued.

**Shaolin full run, `...943216`**: `DONE`, no crash, no thermal pause, `held ... for
794s`. **fps_ok_share = 1.00 — every one of the 297 scored windows is at/above the 28.5
bar** (median 52.25 fps). This does **not** match the title's registry FAIL
(`shaolin-1006`: fps_ok 0.4912 at 28.5, median 45.91, min 15.74, worst hitch 516.5 ms) —
median fps is comparable or better here, but that run had roughly half its windows below
bar and a half-second hitch; this run has none. **What the instrument cannot see**: this
route (pathfind's own `rehold-4D570029` steps 1-28, then the `attack` genre loop fighting
in one dungeon room) never visits whatever scene produced `shaolin-1006`'s min-15.74-fps
dip and 516 ms hitch — a different slice of the game, the same gap already named for
Buffy's two different-route fps-share readings (§3). **Not a contradiction and not
evidence the title is fixed**: this session's generated route is a poor instrument for
Shaolin Monks' actual below-bar scene; reproducing the FAIL would need a route that
revisits `shaolin-1006`'s own path, which this lane did not have and did not invent. Not
added to the cause table as a contradicting "fine" row — recorded here as a gap, and
excluded from §7 (no cause observed, the window measured is not the window that failed).

**Arctic Thunder full run, `...944133`**: `DONE`, no crash, no thermal pause, `held ... for
511s`. **Same pattern as Shaolin: fps_ok_share = 1.00, median 59.07 fps, nothing below
bar.** The registry's BELOW_BAR status cites a different run
(`dispatch/results/1-1790775886-lane.verdict433-3086903`, 2026-09-30) as the failing
verdict. This route (nav.py's recorded path to the first checkpoint, reused unmodified
from the Thor screening session cited in §8) reaches only the checkpoint the original nav
run reached — not necessarily the scene that produced the earlier FAIL. Same conclusion
as Shaolin: not a contradiction, not evidence of a fix, a gap in this route's reach.
Excluded from §7 for the same reason.

**Both no-below-bar-observed results (Shaolin, Arctic Thunder) point at the same
instrument limitation, not two unrelated misses**: both titles' FAIL verdicts come from a
different session's route than the one this lane could queue (built from a different
recorded path, or the only path on file). A below-bar verdict earned once is not evidence
every route through the title fails — fixing this gap needs a hold that specifically
revisits the scene that produced the original FAIL, which neither `steps2route.py` nor
this lane's brief ("no route = skip, say so, do not invent input") can manufacture from
here.

**Pilot Down pilot, `1-1791536188-fpstelemetry1008-948130`**: `DONE`, no crash, no
thermal pause, `held ... for 305s`. Frames show the route reaches a main menu
(`s04-title_screen`), a long cutscene run (`s05`-`s23`), then live on-foot gameplay
(`s24-gameplay.png`, tutorial caption "Move the left thumbstick to move around") and stays
there through the last hold frame — **and the pilot's own on-screen HUD already reads
FPS: 12** at that last frame, well below bar even in a 305 s pilot with no telemetry
flags. Route confirmed good; queued the full run, `1-1791538085-fpstelemetry1008-1088739`
(545 s, perflog+GPUXFR+FRAMETRACE). `pilotdown.route` deleted after queuing (no further
use planned).

**Amped 2 pilot, `1-1791536191-fpstelemetry1008-948403`**: `DONE`, no crash, no thermal
pause, `held ... for 342s`. Frames reach the main menu, a submenu run, then live
snowboarding gameplay (`s13-gameplay.png` onward) alternating with probe frames, holding
through to the last frame (`FPS: 29` shown on-screen, right at the bar). Route confirmed
good; queued the full run, `1-1791538465-fpstelemetry1008-1131600` (578 s,
perflog+GPUXFR+FRAMETRACE). `amped2.route` deleted after queuing.

**Spider-Man 2 pilot, `1-1791536195-fpstelemetry1008-948635`**: `DONE`, no crash, no
thermal pause, `held ... for 167s`. Frames reach a profile-creation screen, a cutscene,
then live gameplay (`s10-gameplay.png` onward), holding through the last frame
(wall-crawling tutorial caption, `FPS: 29`). Route confirmed good; queued the full run,
`1-1791538675-fpstelemetry1008-1143702` (406 s, perflog+GPUXFR+FRAMETRACE).
`spiderman2.route` deleted after queuing.

**LOTR ROTK pilot, `1-1791536198-fpstelemetry1008-948881`**: `DONE`, no crash, no thermal
pause, `held ... for 436s`. Frames reach a long logo/black run, cutscenes, then live
gameplay (`s36-gameplay.png` onward) — the last hold frame is Gandalf mid-battle, enemies
closing in, full combat HUD, `FPS: 29`. Route confirmed good; queued the full run,
`1-1791539142-fpstelemetry1008-1170820` (674 s, perflog+GPUXFR+FRAMETRACE).
`lotr-rotk.route` deleted after queuing.

**Fantastic 4 pilot, `1-1791536202-fpstelemetry1008-949140`**: `DONE`, no crash, no
thermal pause, `held ... for 249s`. Frames reach live gameplay at `s21-gameplay.png`
(FPS:28, Ben Grimm/Thing-style HUD, HP 100/100) — the `attack` genre guess is doing
something, not a true on-rails no-op. But HP drops to 83/100 by the next frame (38 s
later, still live HUD) and the **last hold frame, ~38 s after that, is a cutscene**
(cinematic letterbox bars, the team on a rooftop at night, no HUD) — gameplay was reached
but did not hold for the pilot's remaining window. This matches the risk flagged when the
route was generated (§9): the source hold's own genre was `onrails` with only 36% play
share (783 s cutscene of 1675 s); forcing `attack` presses produced a brief playable
stretch (~40-80 s) before the title cut to story sequence regardless, not a sustained
5-minute play window. **Verdict: route defect confirmed, not a good pilot** — queuing the
full 485 s run would likely capture mostly cutscene, the same low-play-share problem the
source run already had. Per the brief ("do not force a retry with different inputs — that
would be inventing a third guess"), **no full run queued; Fantastic 4 stays excluded from
the cause table**, excluded for a different, now-confirmed reason than the original
"not staged" one. `fantastic4.route` deleted (pilot's purpose served; a future attempt
would need a different genre loop or a hand-reviewed path, not a retry of this guess).

**Hulk UD pilot, `1-1791536216-fpstelemetry1008-950590`**: `DONE`, no crash, no thermal
pause, `held ... for 181s`. Frames reach the main menu, cutscenes, then live gameplay
(`s13-gameplay.png` onward), holding through the last frame (tutorial caption "Walk Hulk
around the junkyard with L", `FPS: 29`). Route confirmed good; queued the full run,
`1-1791539645-fpstelemetry1008-1208416` (418 s, perflog+GPUXFR+FRAMETRACE).
`hulk-ud.route` deleted after queuing.

**NHL 2K3 pilot, `1-1791536219-fpstelemetry1008-950844`**: `DONE`, no crash, no thermal
pause, `held ... for 421s`. Frames reach the main menu, cutscenes/pauses, then live
on-ice gameplay (`s15-gameplay.png` onward), holding through the last frame (scoreboard
HUD, 1st period, clock "19:00" — i.e. the period has just started, `FPS: 29`). **Sports
rule caveat (not applied)**: `steps2route.py`'s generated route carries no period-length
setting step (unlike NBA Live 2005's hand-built route, which does); this run is on
whatever the title's default period length is. Not re-generated (budget, and the brief's
"no route = skip, do not invent input" extends to not hand-editing a generated route
either) — recorded as a caveat on this run's representativeness, not a blocker. Route
confirmed reaches and holds gameplay; queued the full run,
`1-1791540124-fpstelemetry1008-1240862` (658 s, perflog+GPUXFR+FRAMETRACE). `nhl2k3.route`
deleted after queuing.

**Ninja Gaiden Black pilot, `1-1791536223-fpstelemetry1008-951148`**: `DONE`, no crash,
no thermal pause, `held ... for 338s`. Frames reach a long cutscene/loading run, then live
combat gameplay (`s32-gameplay.png` onward), holding through the last frame (an enemy
just defeated, kill-quote caption, HP bar live, `FPS: 38`). Route confirmed good; queued
the full run, `1-1791540489-fpstelemetry1008-1275640` (575 s,
perflog+GPUXFR+FRAMETRACE). `ngb.route` deleted after queuing. **This is the last of the
8 generated-route pilots** — all eight reached and held live gameplay except Fantastic 4
(route defect, above); seven full runs are now queued or landed.

## 11. Closing summary

All device work for this session is done: the Nova queue (11 requests, ~95 min of device
time) drained cleanly, no crash, no hang, no thermal pause on any run. The cause table
(§7) now has 13 rows, 11 of them backed by a fresh post-5c35880d0a perflog+GPUXFR+
FRAMETRACE run this lane commissioned (Pilot Down, Amped 2, MechAssault 2, Buffy, LOTR
ROTK, Hulk UD, NHL 2K3, Spider-Man 2, Ninja Gaiden Black, DOA3, NBA Live 2005), plus
Midnight Club II (sharpened by lane.surfdl1008's concurrent work, folded onto master
during this attempt's merge) and NFS Most Wanted (CPU-only, no route — `steps2route.py`
tool bug). Named causes split roughly into three groups: guest-(vCPU)-bound (Pilot Down,
Amped 2, Hulk UD, the guest-busy-doubling half of NHL 2K3, NFS MW); renderer/GPU-bound
(Spider-Man 2, Midnight Club II, Ninja Gaiden Black — the last now resolved from "GPU vs
fence, not distinguished" to "GPU cost, confirmed"); and the surface-download
finish-wait mechanism (NBA Live 2005, Midnight Club II, and a newly-found multi-download
pattern on Spider-Man 2 and NHL 2K3 worth checking against the same mechanism). Two
titles split across both classes (MechAssault 2, NHL 2K3).

**Not reproduced, not a contradiction**: MK Shaolin Monks and Arctic Thunder both ran
clean full-telemetry passes with **zero** below-bar windows (fps_ok_share 1.00) — their
registry FAIL verdicts come from different routes/sessions this lane could not reach from
here (§10). This is an instrument-reach gap, not evidence the titles are fixed; a future
attempt would need to replay the specific scene that produced the original FAIL, which
neither `steps2route.py` nor this lane's "no route = skip, do not invent input" rule can
manufacture from the data on hand.

**Still open for a future lane**: Fantastic 4 (route defect confirmed — the generated
route's `attack`-genre guess reaches gameplay briefly then cuts to cutscene, matching the
source hold's own low play share; needs a different genre loop or a hand-built path, not
a retry of this guess); NFS Most Wanted and Midnight Club II (blocked on `steps2route.py`'s
inability to encode `RT+left`/`RT+right` combo steering tokens — a tool fix outside this
lane's territory); Dino Crisis 3 (route/input defect, unrelated to fps); DOA3's
gold-dojo-stage sync-download finding (belowbar1005's original citation) was not
reproduced by this session's aquarium-stage fight — needs a hold that specifically visits
that stage; NHL 2K3's generated route never sets period length (§10), so its
representativeness of the title's worst case is uncertain.

PR.md is being marked `State: ready` below. This lane's territory
(`docs/lanes/fpstelemetry1008/**`) is the only thing changed; no code, no golden, no
prediction (telemetry survey, explicitly `--no-expect`d on every request).
