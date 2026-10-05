# lane.framereview -- overnight frame review of pathfind holds (#433)

Started 2026-10-05 05:08 UTC (10-04 22:08 PDT). Stop: 07:30 PDT 10-05, then DONE here.
Budget: Sonnet, about $12; frames cost the most. Stop at the cap and say so here.

## Scope and rules followed

- Read only: `/home/justin/hakux-work/wt/pathfind/docs/lanes/pathfind/runs/<run>/`. Pathfind worktree untouched.
- Outputs: `candidates/<run>.md` per reviewed run, `INDEX.md` (one line per run, newest last). No ledger, Wall or board files.
- One Read per frame image. No batched images, no contact sheets as the review basis (hold strips only for orientation).
- Candidate rule: `reached_gameplay`, play_share >= 0.85 and fps_ok_share >= 0.85 on the verdict, not already in the brief's
  "do not redo" list. Near misses (play >= 0.90 or fps >= 0.90 missed narrowly) get a short note.

## Runs found at 05:08 UTC

Ready (verdict present, numeric bar met, not on the brief's do-not-redo list):

| run | play_share | fps_ok | status |
|---|---|---|---|
| black-stone-hold2 | 0.9996 | 1.0 | review (pathfind's own strip says the fighter stands still) |
| panzer-dragoon-hold3 | 0.9997 | 0.9962 | on the ledger already (row 17, lane.local frame review, 10-04). Not redone; see below |
| spikeout-hold | 0.9996 | 1.0 | on the ledger already (row 15, lane.local frame review, 10-03). Not redone; see below |

Still being held: retro-tron (hold.jsonl growing at 05:08 UTC). Wait.

Not candidates (verdict fails the numeric bar, nothing to review here): black-stone-hold3 (play 0.09), black-stone-walk (0.64),
dino-crisis-3-hold (play 0.79, fps 0.38), panzer-dragoon-hold (0.81), panzer-dragoon-hold2 (0.84), retro-amped2 (fps 0.44),
retro-buffy (fps 0.55, 34% static), retro-doa3 (play 0.70), retro-ngb (fps 0.25), nba-live-2005-hold (fps 0.00),
screen-amped (fps 0.35), screen-avp-extinction (play 0.71), screen-guilty-gear-xx (play 0.52), screen-lego-star-wars (play 0.68),
toejam-earl-3-hold (fps 0.73, play 0.95: fps miss, below the near-miss line).

Ledger-accepted runs (panzer-dragoon-hold3, spikeout-hold): the brief lists six "do not redo" runs but not these two, and
pm/playable-accepted.tsv already has a lane.local frame-review row for each. I did not spend frames on them. lane.local: say if
you want them redone.

## Notes on inputs

- The OUTBOX has no "SCENE SHOULD CONTAIN" line yet (0 occurrences at 05:08 UTC). Scene lists are derived here from the title
  and the first frames, and are marked as derived in each candidate file.
- `pm/playable-accepted.tsv` header: `date_pdt  title  title_id  result  accepted_by  evidence`. Column order used for the
  candidate line.
