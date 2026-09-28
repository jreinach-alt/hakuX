# lane.fpsshare: the status page's title table misreads 30 fps titles

Reported by lane.local (hostops-inbox, 2026-09-27 19:56 PDT): the 0.5 title
table showed "29.0 ... 0% at 30+" for Galleon, Tork, CoD3, MC3, Azurik and
BF2MC, titles that run at full speed.

## What was actually wrong (the brief's candidates, tested)

- **No verdict was being passed over.** None of the six rows has a
  title_verdict.py verdict on the live results dir (26 verdicts, none named
  Galleon, Tork, Azurik, Call of Duty 3, Midnight Club 3 or Battlefield 2).
  The verdict the brief cites, `1790467160-titlebench-2612149` (29.97 / 0.8496),
  is **Crimson Skies**, and that row already rendered it: "30.0 85% at 30+".
  The one wrong word there was the label, since the share was scored at 28.5, not 30.
- Galleon and CoD3 have a hand-reviewed pass-1 row with no fps, so `_fps_read()`
  falls through to the newest soak (`soak_read`). The other four are soak-only.
- **"29.0" is the logged value, not page-side rounding.** profile.c:624 logs
  `gfps=%d` from `increment_fps`, an integer quarter-second sample. A 30 fps
  title logs `gfps=29` on every line (Tork's soak: 118 of 123 lines).
  `_soak_read` took the median of those and counted `g >= 30`, so 0%.
- title_verdict.py never judges gfps ("Reported only", its docstring). It
  scores 60 / dt between consecutive pacing lines (one per 60 guest flips),
  time-weighted, at `playable_fps x fps_tolerance` = 28.5.

## The change (docs/testing/jobs/status_html.py)

- `_soak_read` scores a soak as title_verdict.py scores a run. Its windows run
  between consecutive pacing lines (`gfps=N G:...`, the verdict's `PERF`
  shape) that both fall inside 90-240 s. A window across a `CAPTURE_BREAK` is
  dropped, and duplicate reprinted lines are dropped. fps is the windows'
  median, taken as the upper median to match the verdict. The share is
  time-weighted at the bar. A logcat with no pacing lines (an older format)
  falls back to the gfps median, still at the bar.
  `_soak_median` (the Ghoulies gate, release05) is unchanged: gfps median.
- `_fps_bar()` reads `[defaults] playable_fps x fps_tolerance` from
  targets.toml (`TITLE_TARGETS` as titlestate.py reads it), falling back to
  title_verdict.py's own defaults. Nothing hard-codes 28.5.
- Every measurement carries the bar its share was scored at. A verdict uses its
  `fps_bar` x the tolerance, because a verdict does not record the tolerance.
  Every verdict has applied one since title_verdict.py's first commit
  (2695e09853), so a verdict with no `fps_bar` gets the current bar. A soak
  uses `_fps_bar()`. The pass-1 backfill uses 30 (`share_30`).
- The cell reads "85% at 28.5+". The median is green at or above the same
  bar, so 29.97 is no longer amber. The legend, the detail line and "raise fps
  (...)" all name the bar.
- Cache: `$S/soak-gfps.json` entries become five fields (gfps median, n,
  share, fps, bar). A shorter entry, or one whose bar differs from
  targets.toml's, is re-read on the next tick.
- Stage and counts do not move. A soak row is `reached: unconfirmed`, so it
  never benches, and verdict and backfill shares are unchanged. All seven rows
  below keep their stage.

## Proof

selftest.d/67-status-measured.sh uses three fixtures. The first is a verdict at
29.97 / 0.85. The second is a soak of pacing lines 2.002 s apart (`gfps=29`, 29.97
per window). The third is a soak in the old format with gfps 29.4/29.8. The leg
runs at tolerance 0.95 and again at 0.9 (bar 27), so the bar is read from the
file, not assumed.

This branch:

```
ok   a 30 fps verdict reads 30.0 and 85% at 28.5+, and a soak of gfps=29 lines reads 30.0 and 100%, not 0%
ok   ...and the bar is targets.toml's playable_fps x fps_tolerance, not a constant (tolerance 0.9: at 27+)
Zz Old: 29.6 100% at 28.5+ Thor · 09-27 · unrecorded, soak
Zz Pace: 30.0 100% at 28.5+ Thor · 09-27 · unrecorded, soak
Zz Verdict: 30.0 85% at 28.5+ Nova · 09-27 · unrecorded
```

origin/master's status_html.py (f82e7e87fe), same leg:

```
FAIL a 30 fps verdict reads 30.0 and 85% at 28.5+, and a soak of gfps=29 lines reads 30.0 and 100%, not 0%
    Zz Old: 29.6 0% at 30+ Thor · 09-28 · unrecorded, soak
    Zz Pace: 29.0 0% at 30+ Thor · 09-28 · unrecorded, soak
    Zz Verdict: 30.0 85% at 30+ Nova · 09-28 · unrecorded
FAIL ...and the bar is targets.toml's playable_fps x fps_tolerance, not a constant (tolerance 0.9: at 27+)
```

The measured05 fixture's `fpscol` assert matched the literal "at 30+". It now
accepts "at <bar>+" (docs/lanes/measured05/fixture/assert_measured.py). All of
66-status-titles.sh and 67-status-measured.sh pass on this branch.

### The live rows (titles05 on /home/justin/hakux-work/dispatch, private $S cache), fps cell text

Before (origin/master):

```
Galleon                                  blocked  29.0 0% at 30+ Thor · 09-26 · unrecorded, soak
Crimson Skies: High Road to Revenge      below    30.0 85% at 30+ Nova · 09-27 · MAX | Thor 23.4
Azurik: Rise of Perathia                 inputs   29.0 8% at 30+ Thor · 09-27 · MAX, soak
Battlefield 2: Modern Combat             inputs   29.0 0% at 30+ Thor · 09-27 · MAX, soak
Call of Duty 3                           copied   29.0 0% at 30+ Nova · 09-26 · MAX, soak
Midnight Club 3: DUB Edition             copied   29.0 0% at 30+ Nova · 09-26 · unrecorded, soak
Tork: Prehistoric Punk                   copied   29.0 0% at 30+ Nova · 09-25 · unrecorded, soak
```

After (this branch):

```
Galleon                                  blocked  29.0 22% at 28.5+ Thor · 09-26 · unrecorded, soak
Crimson Skies: High Road to Revenge      below    30.0 85% at 28.5+ Nova · 09-27 · MAX | Thor 23.4
Azurik: Rise of Perathia                 inputs   30.0 88% at 28.5+ Thor · 09-27 · MAX, soak
Battlefield 2: Modern Combat             inputs   30.0 99% at 28.5+ Thor · 09-27 · MAX, soak
Call of Duty 3                           copied   29.4 100% at 28.5+ Nova · 09-26 · MAX, soak
Midnight Club 3: DUB Edition             copied   30.0 46% at 28.5+ Nova · 09-26 · unrecorded, soak
Tork: Prehistoric Punk                   copied   30.0 72% at 28.5+ Nova · 09-25 · unrecorded, soak
```

## For the next lane

- Not every title reads as full speed now. Tork (72%) and MC3 (46%) have
  medians at 29.97, but their slow windows weigh by time. Galleon's soak has
  only 6 samples in 90-240 s (28.99 median, 22%). These are real readings, not
  a renderer defect.
- A soak's window is still 90-240 s from the first perf line (the Ghoulies
  gate's clock), not the verdict's route mark to the end. For a titlebench run
  with a verdict the verdict wins anyway. For a bare soak there is no mark.
- Do not "fix" gfps to a float on this page. It is an integer in the log, and
  the frame rate is in the line spacing.
