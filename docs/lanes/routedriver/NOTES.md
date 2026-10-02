# routedriver (#433): a route that looks at the screen

## Session 1

Base: merged `lane/titleroutes` (bdea9b8ecd) into this branch first -- the
brief says it is not yet folded, and `drive` reuses its `waitfor_match.py`
region-score comparator and `routes/refs/<route>/` reference-crop
convention rather than inventing a second one. Merge was clean (only
`targets.toml` touched by both sides).

Plan, in the order the brief's expected-impact framing favours (build the
thing that reads the screen DURING play first -- cheap heuristics are not
a reason to defer it -- then measure what it costs, then convert two real
routes and read the frames):

1. `docs/testing/titles/classify.py`: the classifier (liveness diff +
   reference crops + dim-overlay + capped Haiku fallback), importable and
   with its own selftest against real frames already on disk.
2. `route.sh` grammar: `drive <profile> <seconds>`.
3. `drive-profiles/`: per-title policy files.
4. Capture-cost measurement on the Nova (1 Hz / 0.2 Hz / none), before
   shipping a default rate.
5. `title_verdict.py`: `play_share`, "menu time" failure, fps judged over
   play seconds, `timeline: none` label for old blind routes.
6. Convert Burnout Revenge (driving) and Sonic Heroes (on-foot) to `drive`,
   replay each once on the Nova, read the frames across the whole window.

Recording as I go; this file is updated, not replaced, each step.
