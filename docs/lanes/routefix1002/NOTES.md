# routefix1002 (#433): three route checks for the overnight Nova queue

Session 1, 2026-10-02, offline. No device time, no request.sh, no holds.
Base: origin/lane/titleroutes2 merged into this branch (merge, no rebase).

## Gunvalkyrie (5345000B) -- QUEUED, route unchanged except the state header

- The brief asked for a v5: forward always, no turn-cancel, a moving play loop.
  NOT written. That loop is v4 (`bd03a589f7`), and it was measured:
  replay 4 (`1790944628-titleroutes2-2686999`) pinned Kelly to a rock face from
  060508 to the end. Re-writing it would queue a known-worse route.
- The file's loop is replay 2's (`685c52e514`, run `1790940485-titleroutes2-1611958`),
  steps byte-identical to what titleroutes2 nominated under #433. It played the
  whole window (100% at 30+, no hang), with one ~2-min cliff (044546-044755).
- Added `# state: first-run`: the route picks NEW GAME at the title menu.
  No other route in the repo carries a `# state:` line, so the header is new.
- Queued at 840 s. P of PASS: moderate. Replays 2 and 4 both reached play in full,
  but 600 s of play with no wall-pinned stretch has never been shown. Win: one
  more Playable title (the 420-s miss was duration only, per the PM).
- Ref: the brief names `effb0d001b`, which is `origin/lane/uberdefault569`'s
  commit, not a titleroutes2 commit. Earlier Gunvalkyrie replays used
  `685c52e514`. Flag for the PM: confirm the build wanted here.

## Buffy (45410012) -- NOT QUEUED

- The route is the survey's loop with B jumps added. Its runs reached play
  (Load Game path, checkpoint, canyon) and then stalled in the stream bed at
  the ledge gap (routedriver2 b5-b18).
- The jump itself is unsolved (routedriver2 NOTES: B and Y timings tried, "do
  not try more"). Nothing offline separates a timing fault from a missing
  button map, so a blind loop change here would be a guess that costs a
  600-s device slot.
- Candidates for the next Buffy step, scored P x win:
  1. Options probe (routedriver2 `scratch/mk_probe_options.py`, ~70 s held):
     reads the controller map. P high that it answers the question (the map
     is on the screen); win high (Buffy Playable unblocked). Cost: one ~70 s
     device run. Picked first: it decides between "a button is mis-mapped"
     and "the jump is timing".
  2. A human with a pad makes the jump once and the frames show it. P high,
     win high, cost: owner time.
  3. Blind loop variants. P low (b7-b14 all ended in the pit), win high, cost:
     600 s each. Not recommended.

## Halo CE (4D530004) -- STOPPED: golden profile is not past training

- `titlestate.py golden` lists 4D530004 as golden `90ebd6a27bd1` (promoted by
  lane.local, owner order 10-02).
- Its `savegame.bin` (3,670,016 bytes) is entirely zero: no level state at all.
- Its `blam.sav` (512 bytes) holds the profile name "New001" and 29 nonzero
  bytes, no level or checkpoint strings. Nothing in the save shows the
  training checkpoint.
- So the golden does not get past training. Per the brief, no returning
  route was written and Halo is not queued. The route stays a DRAFT.
- Next for Halo, scored: a held run that clears training and saves past the
  checkpoint (P high, since the held nav already found the path; win high, the
  most-played title in the library; cost: one held run of several minutes).
  That is the step that makes a returning route possible.

## Queue

`docs/lanes/routefix1002/queue.tsv`: one line, gunvalkyrie, 840 s.
