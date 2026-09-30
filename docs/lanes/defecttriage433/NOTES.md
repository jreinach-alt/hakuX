# lane.defecttriage433 notes

#433 (0.5: 50 Playable): which title-specific defects block an otherwise-good
title, classified and ranked. Analysis only, no device runs (brief: "the
Nova's battery goes to confirmations").

## Method

- Source 1: `lane.verdict433`'s NOTES.md (branch `lane/verdict433`, not yet
  folded), which already ran `judge_copy.py` (a copy of `title_verdict.py`'s
  inputs, never the live dir) over every tier A/B title's newest route soak,
  plus a later Nova sweep (`sweep.py`) over 11 titles / 124 runs since
  2026-09-28 ~19:00 PDT. I read it rather than re-deriving it.
- Source 2: my own `judge_copy.py` (this dir, adapted from lane.verdict433's;
  same copy-then-judge shape) against `$DISPATCH_DIR/results` for "25 to
  Life", which verdict433's sweep never covered (it has no `titleroutes`
  entry yet, only two generic `survey`-route benchmarks). Copies were judged
  in a scratch dir and deleted after the citations below were pulled out —
  not committed, since raw logcat copies (100s of KB to several MB each)
  do not belong in a docs-only PR.
- All timestamps are device-log local time (America/Los_Angeles, matching
  the run), taken straight from `logcat.txt`.

## The table

| Title | Device | Run (id) | Gameplay s | Share @28.5+ | Class | Evidence | Owner / proposal |
|---|---|---|---|---|---|---|---|
| Bruce Lee: Quest of the Dragon | thor | `1-1790487611-titleroutes-261841` | 288.7 | 81.3% | **hang**, single episode | `logcat.txt`: last `hakuX-perf` line before the gap at 23:32:17.728 PDT 09-26, next at 23:32:38.911 -- 21.2 s with no `hakuX-perf` line (< 60 flips). Nothing else in the window: no `ubo_ring_grow` past n16, no `[shd413]`/`vkCreateGraphicsPipelines`. | **Unowned.** Only one full-window run exists; a single-run oddity needs a rerun before any conclusion ([[device-run-flakes]]). See brief sketch A. |
| Blood Wake | thor | `1-1790508532-titleroutes-1074940` | 286.6 | 29.5% | **sustained fps collapse** (not a clean single hang) | `logcat.txt`: mark gameplay 04:34:50.025 PDT 09-27. From ~04:36:21 to soak end (04:39:36.642) the run is a near-continuous chain of ~20 windows at 9.1-11.7 s per 60 flips (about 5-6 fps), of which 3 individually clear title_verdict's 10 s hang bar (10.6, 10.3, 11.7 s) -- the tool reports "hang" but the shape is a sustained collapse, not a discrete freeze. `ubo_ring_grow: n256 pools15 sets62464` fires at 04:35:33.507 (43 s after mark), just before the collapse starts, but `pools` stays at 15, under the 16-pool cap lane.aufire412's `1b557ff6a4` put in (confirmed an ancestor of this run's ref `7e38a5628d` by `git merge-base --is-ancestor`) -- that fix already landed, so the growth log line is the normal "every 256th grow" print, not a new unbounded-growth bug. No `[shd413]`/`vkCreateGraphicsPipelines`. No `thermal.jsonl` (unmeasured). | **Unowned.** See brief sketch B (paired with Battlefield 2: MC below -- same shape). |
| Battlefield 2: Modern Combat | thor | `1-1790517591-titleroutes-1523259` | 270.3 | 0.0% | **sustained fps collapse** (same shape as Blood Wake) | `logcat.txt`: mark gameplay 08:13:40.865 PDT 09-27. From 08:15:19.242 to 08:17:58.898 (soak end 08:18:11.156) the run is a near-continuous chain of 10+ windows at 12.7-16.5 s per 60 flips (2-4 fps) -- essentially the whole back half of the scored window. `ubo_ring_grow: n256 pools15 sets62464` fires at 08:14:21.198, 41 s after mark, just before the collapse starts -- same bounded-growth, already-fixed pattern as Blood Wake (fix `1b557ff6a4` is an ancestor of this run's ref `3ea9cd9a34`). No `[shd413]`/`vkCreateGraphicsPipelines`. No `thermal.jsonl`. | **Unowned.** See brief sketch B. |
| Dungeons & Dragons Heroes | thor | `1-1790560999-titleroutes-2862610` | 302.3 | 0.0% | **fps dip**, flat and sustained (no hang, no dip-and-recover) | `logcat.txt`: last `hakuX-pace` line `f=9300 v0=0 v1=0 v2=0 v3=0 v4=60 vb=254 max=86.7 ms=4258.2` -- every one of the last 60 flips took 4+ VBLANKs (target is 2, i.e. 30 fps); `late_per_100` is 100.0 for the whole pace history. `fps_window_median` 14.5, `fps_window_min` 14.0 -- a near-flat ~14-15 fps ceiling the entire window, not stalls. No hang, no audio short (0.0%), no crash. | **Unowned.** See brief sketch C. |
| 25 to Life | thor | `0-0-y-1790433159-titleplay-p1-25tolife` (ref `a5b5b628f2`) vs `1790467152-titlebench-2601473` (ref `d0e30924f8`, `d0e` merges PR #442 lane.titlestate after `a5b`) | 90.8 vs 184.4 | **53.9%** vs 83.0% | **unsettled** -- two generic `survey`-route benchmarks disagree by 29 points, on different refs, both far short of the 600 s screening bar | This is the brief's cited "54% at 30+"; the later, longer run at 83.0% contradicts it. Neither is a dedicated `titleroutes` run (title has none yet), so both are noisy first-look samples (menu path varies run to run) rather than a repeatable read. `logcat.txt` pace on the worse run: `late_per_100=62.03`, `worst_stall=5621.4` ms. | **Not yet a diagnosed defect.** Needs a dedicated route (like `bf2mc`/`blood-wake`) and one clean full-window run before classifying. Lowest priority of the six -- it may resolve to "fine" once measured properly. |
| Crimson Skies: High Road to Revenge | nova + thor | several, all <310 s | 129-308 (every run short of 600 s) | 85.0-97.0%, best single reading 94.1% (251 s, ibcache's `HAKUX_IBC=0` control build `c8e95ed539`, i.e. master's own code path) | **fps dip, marginal** -- consistently near but under the 90% bar | verdict433 NOTES, sessions 4 and 9 (Nova sweep and the ibcache read): "paced at 30.0, 96.6% only on unmerged ibcache builds; the `HAKUX_IBC=0` control read 94.1% ... a thin margin over 20 min." | **Owned indirectly by lane.ibcache** (its IBC change visibly moves Crimson's share). Needs a full 1200 s confirmation once ibcache's three remaining Crimson Nova runs (`-1378207`, `-1378332`, `-1378456`) are read. No new dispatch needed. |
| DOA Ultimate | nova | 38 runs (Nova sweep) | -- | 91.4% at 28.5+, audio 0.136% short (bar 0.1%) | **route/menu**, not gameplay: the survey route ends on the User Profiles menu | verdict433 NOTES session 9: "The survey route ends on the User Profiles menu ('There is no profile to import'), not in a fight (frame `092146-play.png`)." | Needs its own route to a fight (a `doax.route` exists for DOA Xtreme, not this title). Route-authoring work, unowned, but not a code defect -- lower priority than the fps-collapse/dip work below. |
| Kabuki Warriors | nova | 14 runs (Nova sweep) | -- | 22.4-99% (highly variable) | **pipeline-create stall** (early runs) now largely fixed; residual hang in pacing/idlehalt/energymap runs (21-59%) | verdict433 NOTES: gmem474's fix reads 96-99% clean; "The pacing, idlehaltdefault and energymap runs hang (3 of the 5 most recent)." | Owned: **uberspike569 / shaderprebuild569** (the stall), **lane.kabukistall** (residual hang, `-194847` queued). No new work from this lane. |
| 007: Agent Under Fire | nova | 25 runs (Nova sweep) | -- | 0% pre-#530 -> 100% post-#530 | per-title sysmem exhaustion, **fixed** | verdict433 NOTES: "Every run before #530 (per-title sysmem, folded 09-28 11:50) reads 0%. Both normal builds after #530 read 100%." | **Done.** Confirmation already queued by lane.verdict433. |
| Forza | nova | 11 runs (Nova sweep) | -- | 52.4% | invalid-list decay | brief's own framing; verdict433 NOTES "waits on #583 (still an open draft)" | Owned: **forzadecay414**, `[watch311] invalid=` per [[forza-invalid-list-since-517]]. No new work from this lane. |

## Ruled out, so the next lane does not re-walk it

- **`ubo_ring_grow: nNNN` is not evidence of a new bug** in Blood Wake or
  Battlefield 2: MC. `shaders.c`'s `make_room_in_ubo_ring()` (lane.aufire412,
  `1b557ff6a4`) logs the first 16 grows and then every 256th, and both
  titles' `pools` field stays at 15 -- under the 16-pool cap that commit
  added. `git merge-base --is-ancestor 1b557ff6a4 <ref>` confirms the fix
  predates both runs' refs (`7e38a5628d`, `3ea9cd9a34`). aufire412's own
  A/B soak (its NOTES section 6) already showed this same hunk moves GPU
  time but not fps for Agent Under Fire, so it is very unlikely to be the
  lever for these two either; do not re-open it as a hypothesis without new
  evidence.
- **Not a pipeline-create stall.** `grep -rc "shd413\|vkCreateGraphicsPipelines"`
  over all six full-window logcats above (Bruce Lee, Blood Wake,
  Battlefield 2: MC, D&D Heroes, and both 25-to-Life runs) found nothing.
  uberspike569/shaderprebuild569's fix does not apply here.
- **Not thermal.** None of the four `titleroutes` runs captured
  `thermal.jsonl`; regimen is unmeasured for these particular benchmark
  requests (they predate the addendum's full-fan Thor confirmations), so
  thermal is neither confirmed nor a live hypothesis here -- a future soak
  of any of these should carry `--env PERF_REGIMEN=...` and read
  `thermal.jsonl` so this stops being a blind spot.

## Ranking (titles unblocked x probability, per roles/lane.md)

1. **Sustained fps collapse, Blood Wake + Battlefield 2: MC (2 titles).**
   Same shape (near-continuous 9-16 s/60-flip windows starting 40-90 s into
   gameplay, lasting to the end of the window), same device, same
   already-ruled-out causes. This is the "hard tech work" call: neither
   title has a perflog capture, so nobody has split Surf/Draw/Fin/GPU time
   the way aufire412 did for Agent Under Fire. That method is proven (it
   found AUF's true bottleneck was outside the renderer) and fits the
   evidence here directly -- open with it rather than guessing at a
   one-line fix. Ranked first because it is the largest win (2 titles) with
   a concrete, previously-successful method ready to point at it.
2. **D&D Heroes flat fps dip (1 title).** Simpler than #1: no collapse to
   isolate, no partial-good stretch to compare against -- the whole window
   reads the same ~14-15 fps. A single perflog soak read with aufire412's
   `timeline.py`/`splitread.py` should say what the guest or renderer is
   bound on. Ranked second: one title, but a clean, well-characterized
   signal with the least ambiguity to resolve first.
3. **Bruce Lee isolated hang (1 title).** Only one run exists. Per
   [[device-run-flakes]], a single-run anomaly is confirmed or dismissed by
   a rerun before any investigation is opened -- that is the cheap step
   that decides something here (is this a repeating defect or noise),
   not a substitute for the harder work above. If it repeats, it joins the
   investigation queue; if not, Bruce Lee (already at 81.3%) may be close
   to a passing confirmation on its own. Ranked third: smallest guaranteed
   win, and the first action is a measurement, not a fix.
4. Crimson Skies and DOA Ultimate are lower priority: both already have an
   owner or a clear procedural next step (more ibcache runs; a new route)
   rather than an open causal question.
5. 25 to Life is unranked pending a dedicated route and a clean sample --
   its current "54%" reading does not survive being checked against its
   own later run.

## Dispatch-ready brief sketches (top 2-3 unowned causes)

### A. Blood Wake / Battlefield 2: MC -- sustained fps collapse (proposed: lane.thorcollapse)

- **Question:** what causes Blood Wake and Battlefield 2: MC to collapse
  from a workable frame rate to ~2-6 fps for minutes at a stretch, starting
  40-90 s into the scored gameplay window, on the Thor?
- **Evidence:** this file's table rows for both titles, with exact
  timestamps; the "ruled out" section above (not the UBO ring fix, not a
  pipeline stall, thermal unmeasured -- carry a regimen env and
  `thermal.jsonl` this time to close that gap).
- **Files:** `hw/xbox/nv2a/pgraph/vk/*` (renderer, perflog phase lines);
  `docs/lanes/aufire412/` for the proven method (`splitread.py`,
  `timeline.py`) and its phase-line vocabulary (Surf, Tex, Shd, Draw
  sub-phases, Fin(Sub, Fen), GPU(R, X, RP)); the titles' own routes
  (`blood-wake`, `bf2mc`, both authored by lane.titleroutes 2026-09-27).
- **First step:** a `--perflog` soak of Blood Wake's route (shorter,
  simpler pattern than bf2mc's) over 300-480 s after the mark, with
  `--env PERF_REGIMEN=default` and a `thermal.jsonl` capture, read with a
  copy of aufire412's `timeline.py` across the pre-collapse and collapse
  windows to see which phase (Surf/Draw/Fin/GPU/vCPU) grows.

### B. Dungeons & Dragons Heroes -- flat fps dip (proposed: lane.dndfps)

- **Question:** what limits D&D Heroes to a sustained, essentially
  unvarying ~14-15 fps (half the 30 fps bar) for its whole scored window,
  with no hangs, no audio shortfall, and no crash?
- **Evidence:** this file's table row; `pace` line `late_per_100=100.0`,
  `fps_window_median=14.5`, `fps_window_min=14.0` from
  `1-1790560999-titleroutes-2862610`.
- **Files:** same renderer directories as sketch A; the title's own route
  (`titleroutes-2862610`'s route, authored by lane.titleroutes).
- **First step:** a single `--perflog` soak (400-600 s after mark, no need
  to isolate a collapse window since the whole run reads the same),
  read with aufire412's `timeline.py` for the phase breakdown.

### C. Bruce Lee -- confirm before investigating (proposed: fold into whichever lane runs next)

- **Question:** does Bruce Lee's single 21.2 s hang
  (`1-1790487611-titleroutes-261841`, 23:32:17.7-23:32:38.9 PDT 2026-09-26)
  repeat on a second run, or was it a one-off?
- **Evidence:** only one full-window run exists for this title; the rest of
  that run reads 81.3% at 28.5+, the closest of the six to the bar.
- **Files:** the title's route (`titleroutes-261841`'s route).
- **First step:** queue one more full-window (or confirmation-length) Thor
  run. If the hang repeats, open a perflog investigation same as sketches A
  and B; if it doesn't, re-attempt Bruce Lee's confirmation directly --
  it may already be within reach.

## For the next lane

- Don't re-derive the tier A/B table; read `lane/verdict433`'s NOTES.md
  first (`git show lane/verdict433:docs/lanes/verdict433/NOTES.md`, it is
  not yet folded to master).
- `judge_copy.py` here works the same as verdict433's: point it at a
  scratch OUTDIR and a list of `$DISPATCH_DIR/results` ids, and it writes a
  `verdict.json` per id without touching the live results. Delete the
  scratch copies afterward -- they are large (100s of KB to several MB of
  logcat per run) and do not belong in a docs-only PR.
- `git merge-base --is-ancestor <fix-sha> <run-ref>` is the fast way to
  check whether a log line you're suspicious of predates or postdates a
  landed fix, before spending time on it as a live hypothesis.
