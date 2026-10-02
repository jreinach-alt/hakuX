# lane.pathfind -- NOTES

## Scoreboard (10-02)

Lot: the brief's 35 never-routed Nova titles, shuffled with
`random.Random('pathfind-2026-10-02')`; the first 10 in that order are the acceptance set, run in order,
none swapped out. Order: Star Wars III, Midnight Club 3, Bruce Lee, Black Stone, Panzer Dragoon Orta,
Amped 2, Counter-Strike, Top Spin, Ninja Gaiden Black, Spikeout (spares after: Conker, Ghoulies, Tork,
DOAX, DOA3, JSRF, ...). pathfind never reads the retired `.route` files some of these have.

| # | title | device | result | min | model calls (haiku/sonnet) | steps | gameplay frame |
|---|---|---|---|---|---|---|---|
| 1 | Star Wars Episode III | nova | **gameplay** | 3.5 | 17 (16/1) | 18 | runs/star-wars-iii/gameplay_frame.jpg |

Cross-title (Thor, sibling after a recorded path):

| title | path guide | result | min | model calls | steps |
|---|---|---|---|---|---|

## Measurements

- `claude -p` with a 640-px JPEG via the Read tool, custom system prompt, `--tools Read`: Haiku 4.2 s on
  a trivial image (10-02 09:24), 8-10 s on real steps (~400 output tokens incl. thinking), ~$0.027/call.
  Under the brief's 15 s threshold, so no persistent session.

## What the next lane should not repeat

- Star Wars III's opening crawl and FMV ignore START/A: the agent pressed through 9 cutscene steps
  harmlessly. Its FMV renders as green blocks (rendering defect, not a pathfind problem).
