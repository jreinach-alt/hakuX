# lane.stallmeasure569 -- #569: does the shipped shader pre-build remove first-play stalls?

Brief: `briefs/stallmeasure569.md`. Offline protocol in force (GitHub suspended). Base: origin/master
@ dbf2ebe915. No device time spent: every reading below comes from `dispatch/results/*` already on
disk, read with `docs/testing/hitch_report.py`'s own hitch finder (same `HITCH_MS`, same shader/
texture/both/unexplained classifier the owner's #433 finding defined) through a small wrapper,
`pair_hitch.py`, that splits a scored window at a fixed 120 s from its mark -- `hitch_report.py`'s
own `main()` only recognizes a `mark gameplay` line, and DOA's route marks `play`, so the wrapper
takes the mark label as an argument instead of hard-coding it.

## 1. What shipped, read from master (not re-derived)

- `shaderprebuild569` (folded `b1cea467c6`, 2026-09-30 20:44 PDT): a pool of 3 compile workers;
  per-title records of draw-path pipeline creates (`pipeline_keys/<title id>.bin`); a pre-build at
  renderer init that rebuilds a title's **already-recorded** pipelines before PFIFO draws need
  them; cache saves during play. Default on. **The mechanism only helps a REPLAY of a title this
  device has already recorded pipelines for.** It has nothing to build from on a title's first
  ever launch -- that is section 6 of its own NOTES ("item 6, shipped per-title sets... not built
  here"), not yet built.
- `uberspike569` (+ `-gpl`, folded as the GPL/uber ladder, default **off**, `HAKUX_GPL=0`): a
  separate first-draw mechanism (fast-linked interpreter stand-in while the real pipeline compiles)
  that this measurement task does not exercise, since every result read here ran at the default.
- `gpl569`: the pipeline-library infrastructure the ladder sits on.
- `litcompile569`: bit-exact cheap FF lighting helpers (#580, already folded); roughly halves
  pipeline-creation time and cuts GPU ms/frame 10-20%, independent of pre-build. Orthogonal to this
  question; cited in section 4.

**The tracker row for #569 is stale**, as the brief said: `blocked_on` still reads "litcompile569
is AT ITS ATTEMPT CAP (4/4)" (2026-09-30T00:42Z). `git log --all` shows `lane/litcompile569` folded
(`47bfcdc9b7`) and retired (`43902dab17`) the same day, and `uberspike569`/`shaderprebuild569`/
`gpl569` all folded or retired since. Not fixed here (no board edits from a lane); flagged in
OUTBOX for a board request.

## 2. Method

`pair_hitch.py <result-dir> <mark-label>` parses `logcat.txt` with `title_verdict.parse_logcat`,
finds the named `hakuX-route mark <label>` line and the last `soak end` (or last line) as the
window, and calls `hitch_report.find_hitches` + a local summarizer over two slices: `off_s < 120`
(first 120 s of play) and the whole window. A hitch is `shader`-aligned when the same
`[shd413]` window shows `dsm > 0` (a cache miss) or real `dpc_ms`/stage time, exactly
`hitch_report.classify`'s rule -- nothing here redefines what counts as a hitch or a stall.

Three families of pair, in order of how clean they are:

- **Kabuki, a fixed route** (same path every launch): the one clean same-content pair.
- **DOA, a blind route** (`titleplay` presses START/A through random menus): shaderprebuild569's
  own W1b leg already found this route meets a different opponent/stage each launch, so hitch
  counts across its launches are confounded by content, not just by pre-build. Read for direction,
  not as a verdict.
- **Today's first-ever plays** (ToeJam & Earl III, Tron 2.0): titles with no prior run on either
  device, all post-fold (pre-build default on, compiled in). They show what a true first play
  still costs today, on different content than DOA/Kabuki.

## 3. Kabuki: the clean pair (fixed route, `mark gameplay`)

| run | when | prebuild code | records at launch | whole-window hitches | first-120s hitches | worst stall | shader-aligned (whole) |
|---|---|---|---|---|---|---|---|
| cold ref, pre-shaderprebuild (`1-1790730670-uberspike569-2559946`) | 09-29 18:11 PDT | absent (base 2c59b7bbba) | n/a | 37 | 12 | 4,990 ms | 35/37 |
| L1, first play on this ref (`1790814605-shaderprebuild569-748505`) | 09-30 17:30 PDT | present, default on | 0 (apk change, dispatcher cleared) | 32 | 12 | 4,804 ms | 29/32 |
| L2, replay, same ref (`1790823465-shaderprebuild569-2896600`) | 09-30 19:57 PDT | present, default on | 810 records from L1 | 21 | 13 | 665 ms | 19/21 |

(`after-warmup` counts, `hitch_report.py`'s own convention: 30 / 27 / 12.)

- **L1 vs the cold-ref baseline is a near-match: 32 hitches / 4.80 s worst against 37 / 4.99 s.**
  A title's first play is not helped by pre-build being compiled in, because there is nothing
  recorded yet to pre-build. This is the design, not a bug (section 1).
- **L2 vs L1 is the real effect of a replay with records:** whole-window hitches down 34%
  (32 -> 21), and the worst single stall down 86% (4.80 s -> 0.665 s). Multi-second freezes become
  sub-second ones.
- **The first 120 s does not clear up on replay (12 vs 13 hitches).** What is left there is new
  content the title's one prior launch never met -- shaderprebuild569's own NOTES (section "Kabuki
  verdict", reading X) already found this: 83 of L2's creates after the mark were pipelines L1
  never made (the CPU's opponent and arena are randomised even though the route itself is fixed),
  and they cost as much per-create as a genuinely cold one (~173 ms). All of L2's remaining worst5
  hitches here are `class=shader` with real `dsm`/`dpc_ms`, i.e. real compiles, not scheduling
  noise.

## 4. DOA: confounded by route, read for direction only (`mark play`)

| run | when | prebuild | records | whole hitches | first-120s | worst stall |
|---|---|---|---|---|---|---|
| cold ref (`1-1790730667-uberspike569-2559714`) | 09-29 18:11 PDT | absent | n/a | 10 | 9 | 3,961 ms |
| L1 (`1790791301-shaderprebuild569-118449`) | 09-30 11:01 PDT | present | 0 | 29 | 17 | 4,393 ms |
| L2 (`1790791306-shaderprebuild569-118725`) | 09-30 11:01 PDT | present | 640 from L1 | 15 | 12 | 3,061 ms |

L1 shows *more* hitches than the pre-shaderprebuild cold ref, and L2 shows fewer than L1 but still
more than the cold ref. **Not evidence against the mechanism**: shaderprebuild569's own W1b leg
read the frames and found L1 and L2 fought different opponents on different stages (the route is
blind, pressing START/A into whatever the arcade AI picks), so none of L2's post-mark creates were
even in L1's 640 records. The direction (fewer hitches with records than without) is consistent
with Kabuki; the size is not comparable, because the content is not the same. Included so the
table in the brief has both titles; the plain answer in section 5 leans on Kabuki, the like-for-
like pair.

## 5. Today's first-ever plays (never run on either device before, post-fold, `mark gameplay`)

| title | result dir | whole hitches | first-120s | worst stall | shader-aligned (whole) |
|---|---|---|---|---|---|
| ToeJam & Earl III (`1790970734-lanelocal-1022425`, 10-02 12:52 PDT) | 9 | 9 | 435 ms | 8/9 |
| Tron 2.0 (`1790971658-lanelocal-1220020`, 10-02 13:07 PDT) | 10 | 3 | 1,883 ms | 8/10 |

Both are genuine first plays today, with pre-build compiled in and on by default, and both still
hitch on shader compiles in their first 120 s -- exactly what section 3's L1 predicts. Their worst
stalls (0.4-1.9 s) are much smaller than DOA/Kabuki's cold stalls (3.1-5.0 s); that is very likely
a difference in how many distinct draw-path pipelines each title's early minutes touch, not a
mechanism effect -- these are different titles, not a before/after pair, so size is not
comparable across this table and section 3's.

## 6. The plain answer

**No, pre-build does not remove a title's first-play compile stalls, and it was not designed to.**
A device that has never recorded a title's pipelines has nothing to pre-build, so a first launch
still pays full cold compile cost: Kabuki's L1 (32 hitches, 4.80 s worst) reads the same as the
pre-mechanism baseline (37 hitches, 4.99 s worst), and two titles never played before today
(ToeJam, Tron 2.0) still hitch on shader compiles in their first two minutes.

**Yes, pre-build removes most of the stall on a replay of a title already recorded**, by a wide
margin: Kabuki's second launch cut whole-window hitches 34% and its single worst stall 86% (4.80 s
-> 0.665 s). What is left on replay is pipelines the one prior launch never happened to meet
(randomised opponents/arenas inside a fixed route) -- new content, not engine overhead -- and it
shows up mostly in the first 120 s, where a fixed-route title's early minutes have the least chance
of having been met before.

**What still stalls, by cause, in order of what the data shows:**
1. **A title's genuine first play on this device**, every time, by design -- item 6 (shipped
   per-title sets, harvested from route soaks) is the only piece of the plan that would prebuild
   *before* any on-device play, and it is explicitly not built yet (shaderprebuild569 NOTES
   section 6).
2. **Content a prior play did not meet**, even on a replay of a title already recorded -- random
   fight/arena selection inside a fixed route, per Kabuki's remaining 19-21 hitches.
3. **Not observed here: uber-ladder fallback or link cost.** Every run read is at the shipped
   default, `HAKUX_GPL=0` -- the uber ladder is off by default and none of these logs exercise it.
   That path's own cost (interpreter stand-in while a specialised pipeline links) is a different,
   not-yet-shipped mechanism, covered in section 7.

## 7. The next ubershader step

`uberspike569/BUILD.md` section 12.4 already ranked four candidates from its own device legs
(E/N1-N3/G/K0-K3). Repeating its own ranking and evidence, then adding what today's pre-build
reading changes:

1. **Split link cost from interpreter cost (one Nova arm, `HAKUX_GPL=1` held vs `=0`).**
   uberspike569's own case: cheap (one arm, same instrument), and it decides which of two follow-on
   fixes to build -- optimise the interpreter, or LTO-link the uber pipeline on the worker.
   Probability of a useful answer: high. It is a diagnostic, not a stall fix by itself.
2. **Persist the uber combinations and pre-build them at boot** (uberspike569's own #2, explicitly
   **not built by decision**: "a cold soak clears caches, so a persisted list would make 'cold'
   warm", `BUILD.md` line 167-169). **This measurement task changes that call's confidence, not its
   concern.** The concern was real: without a way to still measure a true cold run, persisting
   combinations contaminates the one baseline the ladder's own legs depend on. But
   `shaderprebuild569` already shipped the exact pattern this needs (a worker pool, a per-title
   append-only record file, a boot-time resolve-and-build step) **and solved this same concern**
   with its W4 falsifier leg: run with the pipeline-cache file wiped but the records kept, so
   "cold" (no compiled cache) and "has records" are tested apart. Section 3 above is the first
   production evidence that the pattern works at the size this would need: 86% off the worst
   stall, 34% off the hitch count, on a real device log, not an estimate. Reusing shaderprebuild's
   pool/record/boot-prebuild code for the ladder's (family, GS, raster, formats) combinations
   (rather than monolithic draw-path pipelines) removes DOA's 14 cold combinations and Kabuki's
   fight entirely once a title has been played once, which is uberspike569's own stated win
   (BUILD.md line 523-527, OUTBOX line 40). **Ranked first here**, promoted from uberspike569's own
   #2, because the de-risking evidence is now a folded, proven mechanism rather than a plan.
3. **`NoContraction` on both paths, its own pixel arm, before any default flip.** No observed pop
   in the suites; Lavapipe shows 1-2 ulp on 22% of random programs (uberspike569 NOTES). A
   correctness prerequisite, not a stall fix.
4. **The default flip for mode 3, on the owner's decision.** The trade is a transient fps dip
   (0.79x median, recovering as swaps land) against the 26-133 s freezes it replaces. Not ranked
   as "next work" -- it is a decision, not a build step.

The successor brief for item 2 is in `OUTBOX.md` (`briefs/uberpersist569.md` candidate text),
for `lane.local` to dispatch.

## 8. Do not repeat

- `hitch_report.py`'s own `main()` only reads a `mark gameplay` line; it will print "no scored
  window" on a DOA log, which marks `play` instead. Pass the label, do not assume the function
  covers every route.
- The brief's "today's runs" line ("ToeJam... 1 hitch, worst 435 ms") is `hitch_report.py`'s
  `n_after_warmup` (hitches at or after `WARMUP_S`=60s), not the raw window count (9 here). Both
  are legitimate; say which one a number is before comparing it to another table.
- DOA's two-launch pair cannot be read as a clean pre/post pair for hitch *counts*: the route is
  blind and meets different content each launch (shaderprebuild569's own W1b finding, confirmed
  again here). Kabuki's fixed route is the only same-content natural experiment on disk right now.
