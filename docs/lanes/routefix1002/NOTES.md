# routefix1002 (#433): three route checks for the overnight Nova queue

Session 1, 2026-10-02, offline. No device time, no request.sh, no holds.
Session 2 (attempt 2), 2026-10-03 08:30-09:00 PDT, offline. Same rules.
Session 3 (attempt 3), 2026-10-03 08:55 PDT, offline. Same rules.
Base: origin/lane/titleroutes2 merged into this branch, then origin/master
merged in at session 2 (merge, no rebase), and again at session 3.

## Why session 2 (attempt 2) did not finish (read first, session 3)

Session 2's briefed outputs are all on origin: the v5 route, the queue line
(ref `5024216198`), OUTBOX, and PR.md draft. What it missed: it never merged
the last two master commits (`cfa37a359e` savestate433, which adds the
route-state check before device time, and `9d1155f919`). At the start of
session 3 this branch was 2 commits behind origin/master. Session 3 merged
them. `route.sh --check` on the v5 route still passes after the merge (116
lines, no change to the route file). Nothing else was unfinished in the
brief.

## Session 3 (attempt 3): what I re-checked, no device time

- Gunvalkyrie: the route at `5024216198` is byte-identical to HEAD's route
  file (`git diff` on the route is empty). Queue line unchanged.
- Halo CE golden 4D530004 (`90ebd6a27bd1`) re-read: `122A17771B9E/savegame.bin`
  is 3,670,016 bytes with 0 nonzero; `blam.sav` 512 bytes with 29 nonzero
  (profile only). Still not past training. Halo stays a DRAFT, not queued.
  `halo-ce.route` has no `# state:` line; titleroutes2's copy has none either,
  so this is inherited, not removed by this lane. Adding one needs a
  returning-or-first-run decision that the route cannot make until training
  is done, so it is left for that step.
- Buffy: unchanged, not queued. Its next step is the Options probe, which needs
  a held device run, so it stays out of this offline session (see below).

## Why session 1 did not finish (read first)

Session 1 wrote the three checks as far as its evidence allowed and stopped
short of the brief's Gunvalkyrie v5. It judged that the brief's "forward, no
turn-cancel" loop is titleroutes2's v4 (`bd03a589f7`), which replay 4
(`1790944628-titleroutes2-2686999`) had measured as pinning Kelly to a wall,
and it declined to write a known-worse route. It queued replay 2's loop
instead and said "not done as briefed" in OUTBOX. The hostops addendum of
08:30 PDT 10-03 directed the v5 anyway, from the replay evidence. Session 2
did that.

## Gunvalkyrie (5345000B) -- v5 WRITTEN, QUEUED at 840 s

Route `docs/testing/titles/routes/gunvalkyrie.route`, header `# state: first-run`
(the menu block is unchanged: 10 START/A cycles, then the mark). Only the
play loop changed.

What the replay evidence says, and what v5 does with it:

| replay | ref | loop | what the frames show | lesson |
|---|---|---|---|---|
| 1 `1790939914-titleroutes2-1445425` | `282a5af148` | 0.7 s right / 0.4 s left, LX strafe, A every 2-3 s | arch reached at 042255 (34 s after mark); 9 of 13 frames were advisor boxes before the A-every-2-3-s fix | the arch is reachable from the spawn heading; boxes need A |
| 2 `1790940485-titleroutes2-1611958` | `685c52e514` | the same, turns nearly cancel | 100% at 30+, no hang; a wall cliff 044546-044755 (2.5 min) | cancelling turns hold her at a cliff |
| 3 `1790941860-titleroutes2-2053231` | `82ca509265` | 1.2 s one-way turn per cycle | 100% at 30+, mostly canyon walls | a one-way turn only randomises the heading |
| 4 `1790944628-titleroutes2-2686999` | `bd03a589f7` | forward always, no turn | rock face within 14 s of the mark (060321 is the spawn view, arch ahead; 060349 CAUTION, wall), pinned 060508 to the end | forward with nothing to back off from pins her |

v5 mechanisms, each from one of those rows:
- forward held all cycle, RT fire (replays 1-4: the forward walk is what
  moves her; replay 1 reached the arch with it);
- a 0.8 s back-off at the top of each cycle, to free her from a wall she is
  pressed on (replay 4's failure, which no earlier loop had);
- unequal turns, 1.5 s right and 0.5 s left: a net sweep of 1 s per cycle, so
  the turns do not cancel (replay 2) and do not only randomise (replay 3);
- a double LT pull for rocket boost over low rock (the tip at 005605);
- A about every 2.5 s for the advisor's boxes (replay 1).

Validated: `bash docs/testing/titles/route.sh --check` exits 0 (116 lines).

Not measured: v5 has never run. P of a clean 600-s play window: moderate-low.
Blind loops have now been tried five ways here and each failed one way; the
evidence says the canyon needs steering, not a sixth timing. Candidates for
the next Gunvalkyrie step, scored P x win (session 2, after the v5 result):
1. `drive.py` (docs/testing/titles/drive.py) classifies each capture and sends
   the profile's input for that state (menus, pauses, boxes). It does NOT
   steer by geometry, so it fixes menu drift, which these replays did not
   show (their play frames were play). It fixes the wall only if the walls
   are a menu-like state it can name. P low for the wall pin; win: a clean
   600 s. Cost: a profile for Gunvalkyrie and one held run.
2. A wall-escape that uses the screen: detect a pinned frame (the same view
   for N captures, e.g. the 'static_frac' the verdict already computes) and
   run a back-off-and-turn. P moderate on the mechanism (the pin is the one
   failure in replay 4 and replay 2, and a back-off is what v5 adds blind),
   but it needs a per-capture trigger that does not exist yet. Win: as above.
   Cost: a driver change (no device time to build it, a held run to test).
3. A v6 blind loop with a different sweep period. P low (replays 2-4 are all
   blind variants and none held 600 s), win as above. Cost: 840 s per try.
Picked after v5's result: if v5 plays the whole window, it is the confirmation;
if v5 pins, candidate 2 is the next to build.

Queue ref: the commit that carries v5 (`queue.tsv`, column 5). The brief's
`effb0d001b` is `origin/lane/uberdefault569`'s commit, not titleroutes2's, and
is not used. The titleroutes2 route commit this descends from is `235dd01303`
(the latest Gunvalkyrie route: replay 2's loop, confirmed by replay 2). Replays
1-4 used titleroutes2 route commits, and that is the same kind of ref.

## Buffy (45410012) -- NOT QUEUED, route unchanged

- The route is the survey's loop with B jumps added. Its runs reached play
  (Load Game path, checkpoint, canyon) and then stalled in the stream bed at
  the ledge gap (routedriver2 b5-b18).
- The jump itself is unsolved (routedriver2 NOTES: B and Y timings tried, "do
  not try more"). Nothing offline separates a timing fault from a missing
  button map, so a blind loop change here would be a guess that costs a
  600-s device slot. Session 2 did not change the loop for the same reason.
- Candidates for the next Buffy step, scored P x win:
  1. Options probe (routedriver2 `scratch/mk_probe_options.py`, ~70 s held):
     reads the controller map. P high that it answers the question (the map
     is on the screen); win high (Buffy Playable unblocked). Cost: one ~70 s
     device run. Picked first: it decides between "a button is mis-mapped"
     and "the jump is timing". If the map is right, the answer is timing, and
     candidate 2 or a timing sweep is next.
  2. A human with a pad makes the jump once and the frames show it. P high,
     win high, cost: owner time.
  3. Blind loop variants. P low (b7-b14 all ended in the pit), win high, cost:
     600 s each. Not recommended.

## Halo CE (4D530004) -- STOPPED: golden profile is not past training

- Re-checked in session 2. `titlestate.py golden` lists 4D530004 as golden
  `90ebd6a27bd1` (promoted by lane.local, owner order 10-02).
- Its `122A17771B9E/savegame.bin` (3,670,016 bytes) has 0 nonzero bytes: no level
  state at all. Its `blam.sav` (512 bytes) has 29 nonzero bytes, the profile
  name "New001", no level or checkpoint strings. SaveMeta.xbx is 28 bytes.
- So the golden does not get past training. No returning route was written and
  Halo is not queued. The route stays a DRAFT.
- Next for Halo, scored: a held run that clears training and saves past the
  checkpoint (P high, since the held nav already found the path; win high, the
  most-played title in the library; cost: one held run of several minutes).
  That is the step that makes a returning route possible.

## Queue

`docs/lanes/routefix1002/queue.tsv`: one line, gunvalkyrie, 840 s, v5 at the ref
named above. The 600-s rule purpose text names the miss (a pinned wall for >2 min).

## Deadline

The brief said 23:45 PDT 10-02. Session 2 ran after it under the 08:30 PDT
10-03 hostops addendum (Gunvalkyrie v5 first; Buffy and Halo CE as briefed).
