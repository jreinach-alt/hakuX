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

## Session 2 (attempt 2, Opus 5.5), 2026-10-01 ~22:20 PDT

**Why attempt 1 did not finish.** It got as far as a first-cut
`classify.py` (flat classes: play/paused/menu/loading/cutscene/black/unknown)
and a bash `drive_step` in `route.sh`, both uncommitted, plus ONE capture-cost
request (`1790917588-routedriver-4171714`, Crimson Skies, no capture, 195 s),
and then the session ended with nothing measured, nothing committed beyond
the draft-PR commit, and no `waiting:` note. Its NOTES.md held only the plan.
Nothing in its code was run against a frame. The session-1 WIP is committed
as ffb2fc0327 so the history shows what it was; this session replaces most of
it (ADDENDUM 2 asks for a named-state machine with a skip ladder, which a
per-capture bash loop calling a stateless classifier could not carry).

Attempt 2 starts by merging origin/master (titleroutes bdea9b8ecd is now
folded: 0f07dbfede) and queueing the two missing capture-cost arms beside
attempt 1's no-capture run, same title/route/seconds/ref:
`1790918323-routedriver-72414` (every 1 s) and
`1790918326-routedriver-72649` (every 5 s).

### CAPTURE COST (brief item 4)

Three dispatch soaks on the Nova, the same title, route, ref (abfd3ece0f) and
length (Crimson Skies, `crimson-skies` route, 195 s), differing only in
`--frames-every` (soak_title.sh's `adb exec-out screencap -p` loop). Read with
scratch/costab.py: per-window fps = 60 / dt between consecutive hakuX-perf
lines after `mark gameplay`, and the hakuX-pace counters over the same span.

| run | capture | frames | windows | fps median | fps mean | fps min | flips at 3+ vblanks | worst flip gap (median / p90 / max ms) |
|---|---|---|---|---|---|---|---|---|
| 1790917588-routedriver-4171714 | none | 0 | 42 | 30.00 | 29.77 | 26.57 | 0.81% | 35.4 / 61.6 / 292.3 |
| 1790918323-routedriver-72414 | every 1 s | 139 | 43 | 30.00 | 29.98 | 29.84 | 0.42% | 34.5 / 37.0 / 44.8 |
| 1790918326-routedriver-72649 | every 5 s | 38 | 43 | 30.00 | 29.98 | 29.50 | 0.95% | 34.9 / 38.2 / 74.0 |

A screencap a second costs Crimson Skies nothing this instrument can see:
the no-capture run is the one with the worst stalls, so the spread is run
noise, not capture. LIMIT, stated so nobody reads more into it: Crimson
Skies paces itself to 30 and has headroom on the Nova; a title running at its
limit (60 with no slack) could still lose frames to a capture, and this does
not price that. One run per arm. So the driver's rates are: `fast_s` 1.0 s
everywhere that is not stable play (boot, logos, intros, title, menus,
cutscenes: nothing is scored there anyway), `slow_s` 5.0 s once play is
confirmed in a scored (`--mark`) run -- the 0.2 Hz arm, the rate the old
blind routes already captured at (their `shot play` every ~10 s) -- and
back to 1 s for one capture after any press. `--find` runs stay at 1 s
throughout: they end at confirmed play and score nothing.

IN-PROCESS SIGNALS (brief: prefer one if it exists). Searched the emulator
for a cheaper signal than a screencap. None names the screen:
- `hakuX-pace` / `hakuX-perf` (hw/xbox/nv2a/pgraph/profile.c:621-634) are
  flip pacing only; a 60 fps menu and 60 fps play print the same line. They
  stop only when the guest stops flipping.
- `[shd413] dph=` (profile.c:666-711) tracks pipeline lookups per 60 flips,
  roughly draws; a menu over a 3D scene draws like play.
- the frame dump (vk/renderer.c:1691-2499; marker file `frame_dump.on` in
  the app's files dir, polled once a second) gives an exact per-frame draw
  count and, with `images`, a 900 KB PPM per frame with a fence wait per
  frame. It still has to be fetched over adb and still does not say "pause
  menu": it is a costlier screencap, not a cheaper one.
- no guest pause/menu flag and no pad feedback are exposed.
So the driver reads screencaps.
