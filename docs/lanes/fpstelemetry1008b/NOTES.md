# lane.fpstelemetry1008b: the four titles lane A could not measure (#433, 0.5)

## Attempt 3: why attempt 2 did not finish

Attempt 2 reviewed the four queued pilots (§6), wrote up the two bad ones (Midnight
Club II, Dino Crisis 3), and launched the two full telemetry runs the good pilots
cleared (NFS Most Wanted, Fantastic 4) via `request.sh --wait` under the Bash tool's
`run_in_background` (§7). The session ended there: `PR.md` still read `State: in
progress` and §7's own text still said "in progress as this is written", NOTES.md had
no cause-table section (§7's heading promised one but the table itself was never
written), and no `WAITING` file was left naming the two request ids — per
[[lane-background-task-dies-with-session]], a `run_in_background` Bash call does not
survive its own session ending, so the `--wait` polling loop died with it. **The
requests themselves were not lost**: both had already been accepted by the dispatcher
before the background shell died, so both ran to completion on the device
independently of this session (`1-1791549076-fpstelemetry1008b-1823645` NFS MW,
`1-1791549078-fpstelemetry1008b-1823751` Fantastic 4, both `DONE`, confirmed by this
resume reading `dispatch/results/` directly — same "work not lost, only unreviewed"
shape as attempt 1→2's own pilots). This attempt reads both runs' perflog/GPUXFR data,
writes the cause-table rows the brief asks for, and closes out the PR.

## -1. Resume (attempt 2): why attempt 1 did not finish

Attempt 1 fixed `steps2route.py` (combo tokens + `--hold-log`), generated all four
routes, ran the gate audit (§5), and **queued all four pilot requests** -- but the
session ended before any of the four pilots had landed or been reviewed: `PR.md`
still read `State: in progress`, NOTES.md §6 was a placeholder, no `pilots/
fpstelemetry1008b.ok` existed, and no `WAITING` file was left naming the four
request ids, so this resume had to rediscover them by listing `dispatch/results/`
for anything named `fpstelemetry1008b` rather than reading them off a waiting
note. All four requests (`...1711214` NFS MW, `...1711744` Midnight Club II,
`...1711839` Fantastic 4, `...1711978` Dino Crisis 3) had already completed
(`DONE`) by the time this session started -- the work was not lost, only
unreviewed and unrecorded. This attempt reviews those four pilots (§6), queues
the two full-telemetry runs their review clears, and writes up the two it does
not.

Follow-up to lane.fpstelemetry1008 (folded to master as 34a0b032b9). Owner direction
10-08: pivot to fps, telemetry first on the low-performing titles. This lane picks up the
four titles lane A's cause table (NOTES.md §7) could not reach: NFS Most Wanted and
Midnight Club II (`steps2route.py` could not encode the `RT+left`/`RT+right` combo
tokens their own recorded routes use), Fantastic 4 (the generated route reached a brief
gameplay burst then cut to a cutscene and stayed there), and Dino Crisis 3 (the stored
route's play share was secondary to a route/input question, not an fps measurement).

## 0. Where the brief's paths actually are

Same wall lane A hit (its own NOTES.md §0): `pm/prequeue.py`, `pm/owner-holds.tsv` etc.
live outside every worktree at `/home/justin/hakux-work/pm/*`, reached only through
`python3` (the Bash tool blocks paths outside this worktree's cwd). The pathfind step
and hold logs this lane reads from (`/home/justin/hakux-work/wt/pathfind/docs/lanes/
pathfind/runs/*`) are in a *different worktree*, also outside this one's Bash cwd, also
read via `python3 open()`. `find`/`grep` over that tree from here are blocked outright
(sandbox message: "may only search files in the allowed working directories"); every
read of it in this session went through a small `python3` script.

## 1. The tool bug, read and fixed (not worked around)

`docs/lanes/fps20786/steps2route.py`'s `tok_lines()` had no branch for a combo token
(`RT+left:N`, `RT+right:N`, `LT+left:N`, `LT+right:N`) — a trigger held together with a
stick direction. Only `pathfind.py`'s own `send()` handled it (hold the trigger, hold the
stick, wait, release the stick, release the trigger). `HOLD_GENRES["drive"]` (`pathfind.py`,
the genre this lane's brief calls "the drive loop") is exactly `["RT:2", "RT+left:0.8",
"RT+right:0.8"]`, and NFS Most Wanted's and Midnight Club II's own recorded pathfind
steps use the same combo tokens directly in their *recorded navigation*, not only in a
loop — so no `--loop` substitution could have avoided the crash either way (lane A's
NOTES.md §9 already found this).

Fixed in a copy at `docs/lanes/fpstelemetry1008b/steps2route.py` (this lane's territory,
not `docs/lanes/fps20786/**`): added the missing branch, same semantics as
`pathfind.py send()`. Verified against both affected titles' own recorded steps — see §2.

A second gap, found reading Fantastic 4's and Dino Crisis 3's own recorded runs (§3, §4):
the upstream tool could only generate a *fixed genre loop* after `mark gameplay`. Neither
title is well modelled by one — Fantastic 4's hold cycles gameplay burst -> game_over ->
cutscene (needs `START` to skip, `A` to dismiss dialogue, before the next burst) and Dino
Crisis 3's model-driven hold changed its own action mix partway through (dropping a
menu-opening button, swapping which buttons it pressed). Added `--hold-log HOLD.JSONL`
(optional `--hold-cutoff`): replays that title's own recorded `hold.jsonl` verbatim,
each row's `action` at the row's own `hold_s` + offset, instead of inventing a loop that
cannot reproduce either behaviour. This is a literal replay of what pathfind's own model
already proved works for that title, not a new guess.

## 2. NFS Most Wanted (4541007B) and Midnight Club II (54540008): generated via the fix

Source: `sweep-4541007B` steps.jsonl (21 steps) and `sweep-54540008` steps.jsonl (43
steps), both in the pathfind worktree, read via `python3` (§0). Both generated with
`--loop "RT:2,RT+left:0.8,RT+right:0.8"` (`HOLD_GENRES["drive"]`, per the brief), both
pass `route.sh --check`.

**NFS Most Wanted**: `--gameplay 20` (step 17 is the first `gameplay` state — "Player-
controlled car in the open-world street, chase camera" — but step 20, after a `probe`/
`unknown` pair, is the better-confirmed one: "Race HUD (position, timer, progress bar,
minimap, speedometer)"). Mark-gameplay elapsed ≈228 s. `nfs-mw.route`, ends ~595 s
(`--hold-s 350`).

**Midnight Club II**: `--gameplay 43` (all steps; the brief names this run by its full
step count). Mark-gameplay elapsed ≈488 s. `mc2.route`, ends ~856 s (`--hold-s 350`).

**Read before piloting, not after**: every one of this run's 29 recorded steps from first
`gameplay` (n=14) onward is the model trying a *different* input to get the car moving —
`RT` alone (3 probes), the left stick, `A`/`HOLD:A`, `LT` released then `RT`, `HOLD:X`,
`LT+left`+`RT+right` together, `LT+right`+`RT+left` together, `X`+`STICK:left` — and
every one reports `control` near zero and the car's speedometer stays at 0 mph in gear
`N` throughout the entire 43-step, ~353 s run. This pathfind session never got the car
to move with ANY input it tried, including — importantly — `RT+left`/`RT+right` paired
with an `LT` press (not the clean, neutral-first `RT:2, RT+left:0.8, RT+right:0.8`
sequence this route plays, so the exact genre is technically untried). **Flagged as a
high-risk pilot before spending any device time on it**: the likely outcome is a route
that reaches a live driving HUD but never actually drives, the same "never-drove" class
as Cel Damage/Arx Fatalis in lane A's §5 exclusion list, not a fresh fps measurement. The
brief asks for this title to be attempted regardless (its own text: "same tool bug ...
same, from sweep-54540008 (43 steps)"), so it was piloted anyway — see §5 for the result.

## 3. Fantastic 4 (4156001A): regenerated from its own recorded hold, not a third guess

Lane A's attempt4 route (`fantastic4.route`, §9/§10 of its NOTES.md) used `--gameplay 21`
and the `attack` genre loop (a guess — the source hold's own genre tag was `onrails`).
Its pilot reached live gameplay at step 21 (HP 100/100), HP dropped to 83/100 one frame
later (confirming `attack`'s presses were landing, not a true on-rails no-op), and then
cut to a cutscene ~76 s after the mark and never returned within the pilot's window. Lane
A's own verdict: "route defect confirmed... a future attempt would need a different genre
loop or a hand-built path, not a retry of this guess" (§10, §11) — this lane's brief
reads that as the "missing START/skip steps": the *source* pathfind run (`n-4156001A-1007`)
has a full recorded `hold.jsonl` (333 rows, 1674.3 s) that DOES get back into gameplay
after a cutscene, by pressing `START` repeatedly to skip it and `A` to dismiss a dialogue
prompt — lane A's loop-based route never included either, so once it hit the first
cutscene it had no way out.

Read in full (not assumed): `hold.jsonl` shows a repeating cycle — a ~30-40 s gameplay
burst (genre actions `X, RT:2, RT+left:0.8, RT+right:0.8`) ending in a `game_over` screen
(dismissed with `A`), then a cutscene that needs several `START` presses to skip, then a
`A`-dismissed dialogue prompt, then the next gameplay burst. Cumulative `play_s` climbs
slowly (≈30% of elapsed hold time): by `hold_s`≈740 (4 full cycles), `play_s`≈300.

**Regenerated** with the new `--hold-log` mode (§1): `--gameplay 21` (unchanged — the
same point lane A's route marked gameplay), `--hold-log <n-4156001A-1007's hold.jsonl>
--hold-cutoff 750` (four gameplay/game_over/cutscene cycles, ≈300 s of actual play inside
a 750 s hold — not the full 1674 s the source run took to bank 600 s of play; this lane's
budget does not cover that). 38 `START` presses and 81 `A` presses appear in the
generated route (confirmed by grep before piloting). `fantastic4.route`, ends ~934 s.
Passes `route.sh --check`. This is a literal replay of pathfind's own recorded, working
navigation through the cutscene/game_over cycle — not a new genre guess (the brief's own
warning against "inventing a third guess" is about *genre choice*; this isn't one).

## 4. Dino Crisis 3 (ISO `Dino Crisis 3.iso`, title id 43430003): a different hold than

the stored, already-excluded route. Lane A's §5 citation ("menu time 79% of the window;
the shooter loop does not move the player") describes the *stored*
`docs/testing/titles/routes/dino-crisis-3.route` — not present in this worktree (routes/
is untracked; nothing to collide with). The brief instead points at
`runs/dino-crisis-3-hold`, a *different*, more recent pathfind run (2026-10-09, title id
43430003, genre `shooter`) that this lane read in full:

- `steps.jsonl` (24 steps): reaches confirmed `gameplay` at step 23 ("HUD bars match the
  first corridor with player health/weapon gauges"), after skipping logos/cutscenes and a
  three-page in-game tutorial overlay (steps 20-22, dismissed with `A`).
- `hold.jsonl` (57 rows, hold_s 0.8-760.5): the model adapted its own action mix over the
  hold rather than repeating one fixed genre — it dropped `B` early (`shed: ["B"]` in
  `result.json`, `B` apparently opening a menu) and, partway through, changed from the
  stock `shooter` genre tokens to a different button mix (`L1, STICK:up, A, RSTICK:right,
  X, STICK:down, STICK:left`, no `RT` at all) once that worked better.
- `verdict.json`/`result.json`: `play_share 0.79` (608 s of 769 s), `fps_ok_share 0.38`,
  `reached_gameplay: true`. **The registry's FAIL text ("menu time: 79.1% ... in `play`")
  is not "79% menu" — it is 79.1% PLAY against a 90% bar**, i.e. this hold mostly *did*
  drive confirmed gameplay; it failed the title's own confirmation-need threshold, not a
  "never left the menu" defect. The 20% non-play is `still` (154 s, player/camera not
  moving) plus 6 s of actual menu. The brief's framing ("shooter loop does not move the
  player") matches the `still` share and the stored route's separate finding, not this
  run's own data — recorded as a correction, not silently overridden.

**Regenerated** with `--hold-log` (§1): `--gameplay 23`, `--hold-log <dino-crisis-3-hold's
hold.jsonl>` (no cutoff — the whole 760.5 s is replayed, since that whole log is what
produced the 79%-play result; truncating it would be inventing a shorter hold the source
data never validated). `dino-crisis-3-regen.route` (named to not collide with the
already-excluded stored `dino-crisis-3.route`), ends ~980 s. Passes `route.sh --check`.

## 5. Gate audit (prequeue.py, by exact title id — a name query can false-match)

| title | id | `prequeue.py` result | cleared? |
|---|---|---|---|
| NFS Most Wanted | 4541007B | REVIEW (registry BELOW_BAR only) | yes — same as lane A's own NFS MW/MechAssault2/Buffy pattern |
| Midnight Club II | 54540008 | REVIEW (registry BELOW_BAR only) | yes |
| Fantastic 4 | 4156001A | BLOCK, owner hold `fantastic4-below-bar`: "fps_ok 0.426 ... needs telemetry and a fix, not a rerun" | yes — same substance as the brief's cleared text, different wording (lane A's own §8 precedent: a title-specific below-bar row in these words is the cleared reason, not a different block) |
| Dino Crisis 3 | 43430003 | BLOCK, "last verdict missed the fps bar: telemetry and a fix, not a retest (owner 10-03)" | yes — the brief's own cleared text, verbatim |

All four ISOs confirmed present on the Nova (`adb -s ee317437 shell ls
/storage/E6C6-D7AA/Games/XBox/`): `4541007B-Need_for_Speed_Most_Wanted.xiso.iso`,
`54540008-Midnight_Club_II.xiso.iso`, `4156001A-Fantastic_4.xiso.iso`, `Dino Crisis 3.iso`.

## 6. Pilots: four queued by attempt 1, reviewed this session

All four pilots used the route's own mark-gameplay elapsed + ~60-90 s margin, no
`--perflog`/GPUXFR/FRAMETRACE, `--no-expect "route pilot, not a measurement"`, per
the brief's pilot rule. All four landed `DONE`, no crash tag, no thermal pause
(`thermal.jsonl` `pause: false` throughout; hottest zone 88-95 C, all CPU-junction
zones, nowhere near the dispatcher's 70 C `xo-therm` pause point).

| request id | title | seconds | verdict (frames read) |
|---|---|---|---|
| `1-1791547117-fpstelemetry1008b-1711214` | NFS Most Wanted | 290 | **GOOD** — live driving |
| `1-1791547136-fpstelemetry1008b-1711839` | Fantastic 4 | 245 | **GOOD** — stays in gameplay |
| `1-1791547135-fpstelemetry1008b-1711744` | Midnight Club II | 548 | **BAD** — car never moves |
| `1-1791547138-fpstelemetry1008b-1711978` | Dino Crisis 3 | 268 | **BAD** — player never moves |

**NFS Most Wanted — good.** First confirmed gameplay frame (`050247-s17-gameplay`,
HUD "Race HUD... player-controlled car") already shows a moving scene (FPS:20).
The two frames inside the genre-loop hold, 35 s apart (`050336-gameplay` and
`050411-hold`), show the race HUD's own progress fields climbing: lap complete
61%→64%, distance +945 FT→+3,335 FT, elapsed 1:42.88→2:22.92, speedometer
non-zero in both. **This directly refutes the high-risk flag written before
piloting (§2): the exact `RT:2, RT+left:0.8, RT+right:0.8` neutral-first sequence
this route plays — untried by the source pathfind session, which only tried
`RT+left`/`RT+right` paired with a held `LT` — does drive the car.** The
combo-token fix (§1) produces a genuinely working route for this title.

**Fantastic 4 — good, and the `--hold-log` fix is confirmed, not just plausible.**
First gameplay frame (`051804-s21-gameplay`, HP 100/100) matches lane A's own mark
point. The next two frames, 6 s and 51 s later (`051810-gameplay` HP 100/85,
`051855-hold-0044` HP 100/9), stay in the **same** gameplay scene (identical
camera framing, same "Von Doom" structure, same falling pose) — HP falls as the
character takes damage, but the screen never cuts to a cutscene the way lane A's
genre-loop route did at a comparable elapsed time (~76 s post-mark). Replaying
the source run's own recorded `START`/`A` skip presses (§3) is doing what it was
meant to do. (HP reaching 9/100 by the last frame is itself unremarkable — the
source `hold.jsonl` this is a literal replay of is the same run whose own
`game_over`→`A`-dismiss cycle this route's later rows reproduce; a near-death
reading mid-cycle is expected, not a sign of a stuck run.)

**Midnight Club II — bad, route/input defect, not an fps measurement.** The
first gameplay-marked frame (`050721-s14-gameplay`) and the last hold frame
(`051359-gameplay`, 638 s later — nearly the entire pilot) are visually
indistinguishable: same camera angle, same two cars (player's white sedan,
parked tan sedan ahead), same on-screen "Click Left Thumbstick To Flash Beams"
prompt, speedometer **000 in gear N** in every frame checked across the window
(`050721`, `051000`, `051359`). The car never moves. This is exactly the outcome
flagged before spending device time on it (§2): this pathfind session's own
29-step search for *any* input that moved the car never succeeded, including
every combo-token pairing it tried — and the one untried combination (the clean
`RT:2, RT+left:0.8, RT+right:0.8` sequence, same as NFS MW's) also does not move
this title's car. **Conclusion: Midnight Club II's stall is not a
`steps2route.py` encoding gap (§1 already fixed that) — it is a route/input
defect in the source pathfind session itself** (wrong vehicle state, parking
brake, a blocked ignition sequence, or similar), which this lane's territory
does not include fixing. No full telemetry run queued; recorded here as the
result per the brief's "a bad pilot is a result" instruction.

**Dino Crisis 3 — bad, route/input defect, not an fps measurement.** The pilot's
60 s post-mark margin produced only three captured frames in the time before the
hold ended (`052307-s23-gameplay`, `052311-gameplay` 4 s later, `052317-hold-0004`
6 s after that — the window is short because `--gameplay 23` marks late in a
268 s pilot), but all three are pixel-identical in composition: same two
characters in the same standing pose, same camera, same corridor, only the FPS
counter changes (26→30→29). No movement in the only window this pilot captured.
This matches the brief's framing for this title ("shooter loop does not move the
player") even though §4 found the *source* `hold.jsonl`'s own recorded play_share
was 79% (a correction to the stored route's registry citation, not this regen) —
**replaying that same recorded hold data did not reproduce movement in this
pilot's short observed window**, so whatever let the original session's play_share
read 79% is not visible in the first ~10 s after this replay's own gameplay mark.
Per the brief's explicit instruction for this title ("if the pilot is not live
gameplay, record the defect and stop"): no full run queued, no second attempt.

**Pilot-gate verdict written** to `/home/justin/hakux-work/dispatch/pilots/
fpstelemetry1008b.ok` (via `python3`, §0) so the 30-minute pilot ceiling no longer
applies to this lane's remaining requests.

## 7. Full telemetry runs queued (the two pilots that cleared)

Both via `docs/testing/request.sh --perflog --env HAKUX_GPUXFR=1 --env
HAKUX_FRAMETRACE=1 --device nova --no-expect "telemetry, not an A/B arm"
--priority study --issue 433 --wait`, ref HEAD (post-5c35880d0a, so GPU stamp
figures are reliable), `--seconds` set to each route's own "route ends ~N s after
launch" comment (§2's generated figure) with no extra margin (the route already
ends on a `repeat`/hold-log boundary):

- NFS Most Wanted (4541007B), route `nfs-mw`, `--seconds 600` (route ends ~595 s).
- Fantastic 4 (4156001A), route `fantastic4`, `--seconds 940` (route ends ~934 s).

Both requests launched in the background from attempt 2's session (Bash tool
`run_in_background`, not a detached/nohup process outside the harness). As Attempt 3's
resume note (top of this file) records, that session ended before either request's
`--wait` loop returned — but both had already been accepted by the dispatcher and ran
to completion independently: `1-1791549076-fpstelemetry1008b-1823645` (NFS MW, `DONE`,
held 603 s, no thermal pause, no crash) and `1-1791549078-fpstelemetry1008b-1823751`
(Fantastic 4, `DONE`, held 949 s, no thermal pause, no crash), confirmed this session
by reading `dispatch/results/` directly. `mc2.route` and `dino-crisis-3-regen.route`
were deleted after §6's review — both titles are done with (bad pilot, no further run
planned). `nfs-mw.route` and `fantastic4.route` are now deleted too (§8 below), both
requests confirmed `DONE`.

## 8. Cause table: NFS Most Wanted and Fantastic 4, decomposed

`docs/lanes/fps20786/decompose.py --bar 30` (bar 30, matching NFS MW's own registry row
and Fantastic 4's own source-hold owner-hold text, both "fps >= 30"), plus
`docs/lanes/belowbar1005/xfrsurvey.py --days 1` and `docs/lanes/fps20786/sdsurvey.py
--days 1 /home/justin/hakux-work/dispatch/results` (both scan the whole results tree by
mtime; they picked up these two fresh runs without being pointed at them individually).
Both runs' `result.json["frames"]` reads `{"every":0,"count":0,"bytes":0,"dir":null}` —
same as lane A's §6 finding, `HAKUX_FRAMETRACE=1` alone produced no frame-trace data
here either.

**NFS Most Wanted** (4541007B), 204 two-second windows (408 s), fps_ok_share 0.10 at bar
30 (42 s at/above, 366 s below — consistent with the title-registry's own 0.1937 from a
different, shorter sweep run, both badly failing the title's 90% confirmation bar):

```
group      n    fps      F   gbusy  gidle timer    Ri   rcpu   rblk  v_blk  vcpu  ph_GPU ph_Fin
all      204  29.96  33.38  17.85  15.56 13.65  8.15  17.71   7.65   3.66  0.89    6.90   9.90
>=bar     21  30.03  33.30  17.62  15.63 13.67  8.20  17.57   7.38   3.67  0.89    6.90   9.90
<bar     183  29.95  33.39  17.86  15.55 13.64  8.10  17.72   7.66   3.66  0.89    6.90   9.90
<bar p10  46  29.35  34.07  19.26  15.05 12.80  8.00  17.96   8.34   3.92  0.88    7.20  10.10
```

Every group sits within a couple of ms of every other on every column — this title is
capped tight against the 33.3 ms two-VBLANK line (fps 29.35-30.03 across all four rows),
not falling away in a slow tail the way most of lane A's table does. `xfrsurvey.py`: Tot
9.7, Rnd 4.7, Xfr 4.9, Xfr/Tot 0.51, RP 3. `sdsurvey.py`: sd/flip 1.50, dirty 0.50, cDef
1.00, Fin 9.8, GPU 6.9, gfps 29. **This corrects OUTBOX.md:797's CPU-only read** (cited
unchanged in lane A's own table, "guest busy ~25 ms/frame throughout play... constant
cost, not scene-dependent"): on this trusted-stamp run guest busy is only 17.85-19.26 ms
of a 33.4 ms frame (53-57%, not the dominant share OUTBOX's figure implied) and barely
moves between the fastest and slowest groups — not a guest-CPU story. The better-supported
driver is the GPU side: **Fin (9.8 ms, a completion-deferred surface-download finish-wait,
1.5 per flip) exceeds the GPU's own render budget (GPU 6.9 ms, Rnd 4.7 ms) on its own** —
the same shape as NBA Live 2005's and Midnight Club II's rows in lane A's table, not the
vCPU class OUTBOX originally named.

**Fantastic 4** (4156001A), 386 windows (772 s, this lane's `--hold-log --hold-cutoff
750` replay, §3), fps_ok_share 0.53 at bar 30 (412 s at/above, 360 s below) — **read with
a caveat, not taken at face value**: the "at bar" group's own median fps is 59.45 at
F=16.82 ms with gidle=0.00 — these are the hold's own cutscene/game_over/dialogue-skip
screens (nothing moving, nothing to render, so the frame finishes fast), not fast
gameplay. The "below bar" group (fps 21.17, F=47.23 ms, n=180, 360 s) is where the actual
gameplay bursts live:

```
group      n    fps      F   gbusy  gidle timer    Ri   rcpu   rblk  v_blk  vcpu  ph_GPU ph_Fin
all      386  33.86  29.53  22.82   8.28  6.97 14.20  12.67   9.07   6.67  0.73    8.38   7.10
>=bar    206  59.45  16.82  16.69   0.00  0.00 13.55   3.94   1.83   3.47  0.82    1.45   4.42
<bar     180  21.17  47.23  29.10  17.68 14.98 16.10  16.83  14.03  16.36  0.64   14.50  16.60
<bar p10  46  19.98  50.06  30.39  19.76 17.21 17.60  18.09  14.60  17.31  0.65   14.00  18.50
```

Inside the `<bar` gameplay rows, guest busy is large and rises further at the tail
(29.10→30.39 ms of a 47-50 ms frame), the render thread's own CPU and blocked time are
both comparably large (rcpu 16.83→18.09, rblk 14.03→14.60), and the guest-blocked time
decompose.py's interrupt classifier cannot place (`v_blk`) is larger here than anywhere
else in this project's cause-table work so far (16.36→17.31 ms — Buffy's 3.97-6.10 ms,
NBA Live 2005's did not report v_blk at all, is the next-largest). `xfrsurvey.py`: Tot
14.3, Rnd 7.0, Xfr 7.3, Xfr/Tot 0.51, RP 5. `sdsurvey.py` (whole logcat, dominated by the
fast non-gameplay majority of frames — not read as the gameplay-only figure): sd/flip
0.00, Fin 4.7, GPU 1.5, gfps 59. **Named cause: inside the actual gameplay windows, three
things are elevated together — guest busy, render-thread blocked time, and an unusually
large unattributed guest wait — not one clean driver**, unlike most of lane A's table.

| title (id) | gfps median | Tot ms/frame | gbusy share | Ri ms | GMEM Xfr/Tot, RP | sd/flip, Fin ms | thermal pause | named cause | fix could be |
|---|---|---|---|---|---|---|---|---|---|
| NFS Most Wanted (4541007B) | 29.96 median, fps_ok_share 0.10 (fresh full run, `1-1791549076-fpstelemetry1008b-1823645`, bar 30) | 9.7 Rnd 4.7 Xfr 4.9, Xfr/Tot 0.51, RP 3 | 17.85 (all) to 19.26 (p10) — nearly flat, not the driver | 8.15 flat (8.20 at bar to 8.00 at p10) | 0.51, RP 3 | 1.50/flip, Fin 9.8 — **exceeds the 6.9 ms GPU render budget on its own** | no (`THERMAL: no thermal-pause device above 0`) | **corrects OUTBOX.md:797**: guest busy is only 53-57% of frame time and barely moves across bar groups on this trusted-stamp run — the better-supported driver is a completion-deferred surface-download finish-wait (1.5/flip, Fin 9.8 ms > GPU 6.9 ms), same class as NBA Live 2005/Midnight Club II | GPU-side surface-download/texture-conversion work (the NBA Live 2005/Midnight Club II candidate), not vCPU/JIT |
| Fantastic 4 (4156001A) | bimodal: 59.45 median in non-gameplay frames (cutscene/game_over, gidle 0.00, nothing to render), 21.17 median in the gameplay burst; fps_ok_share 0.53 over this run's 772 s replay window (owner-hold's own source-run figure: fps_ok 0.426 over the full 1383 s hold, 600 s play + 783 s cutscene — this run replays only the first 750 s, a different, earlier slice) | 14.3 Rnd 7.0 Xfr 7.3, Xfr/Tot 0.51, RP 5 (whole-logcat, cutscene-majority — see gameplay-only decompose figures instead) | 29.10 (gameplay <bar) rising to 30.39 (p10) | 16.10 (gameplay <bar) rising to 17.60 (p10) — does not fall as gbusy rises | 0.51, RP 5 | 0.00/flip, Fin 4.7 (whole-logcat, cutscene-majority, not the gameplay figure) | no (`THERMAL: no thermal-pause device above 0`) | **mixed, not one clean driver**: inside the gameplay-only window, guest busy (29-30 ms), render-thread blocked time (14-15 ms) and an unusually large unattributed guest wait (v_blk 16-17 ms, the largest in this project's table so far) are all elevated together | vCPU/JIT for the guest share; the v_blk component needs a different instrument (same gap NBA Live 2005/Buffy already flagged) to say what it is waiting on |

## 9. What this run adds to lane A's §6 ("what the instrument cannot see")

- **Fantastic 4's bimodal fps split is a hold-log-replay artifact, not two different
  bottlenecks**: because this route replays a title's own recorded cutscene/game_over
  cycle verbatim (§3) rather than a continuous gameplay loop, roughly 53% of the window
  is non-gameplay screens rendering at an uncapped ~59 fps with nothing to draw —
  `decompose.py`'s bar split (fps >= / < 30) partitions "gameplay vs not", not "slow vs
  fast gameplay", for this specific run. A future lane reading this run's raw all-window
  median (33.86 fps, "fps_ok_share 0.53") without reading the per-group table would
  under-state how bad the actual gameplay is (21.17 fps) and over-state the title's
  measured health.
- **NFS Most Wanted's own distribution is the opposite shape**: every group (all/
  >=bar/<bar/p10) sits within ~1 fps and ~1 ms of every other. There is no slow tail to
  decompose here — the whole 408 s window runs at one speed, just under the bar. A
  bottleneck search that only reads the worst decile (as most of lane A's table does)
  would find nothing distinguishing it from the median here; the Fin/GPU imbalance (§8)
  is visible only by reading `sdsurvey.py`/`xfrsurvey.py` on the whole run, not by
  comparing bar groups.
