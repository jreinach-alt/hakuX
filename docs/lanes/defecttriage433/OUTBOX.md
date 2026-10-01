## #433 -- 2026-09-30 11:40 PDT

lane.defecttriage433: classified and ranked the title-specific defects
blocking otherwise-good titles (analysis only, no device runs). Full table
and evidence in `docs/lanes/defecttriage433/NOTES.md` (PR: see
`docs/lanes/defecttriage433/PR.md`, offline protocol).

**Ranked, unowned causes (titles unblocked x probability):**

1. **Sustained fps collapse -- Blood Wake + Battlefield 2: Modern Combat (2
   titles), Thor.** Both collapse from a workable frame rate to ~2-6 fps for
   minutes at a stretch, starting 40-90 s into the scored gameplay window
   (Blood Wake 29.5% share at 28.5+, Battlefield 2: MC 0%). Ruled out: the
   `ubo_ring_grow` log lines both titles print are the already-fixed,
   bounded growth from lane.aufire412's `1b557ff6a4` (confirmed an ancestor
   of both runs' refs) -- not a new bug; neither title shows a
   pipeline-create stall (`[shd413]`/`vkCreateGraphicsPipelines` absent from
   both logs). No perflog capture exists for either yet. Proposing
   lane.thorcollapse: a `--perflog` soak of Blood Wake's route (simpler
   pattern) read with lane.aufire412's `timeline.py`/`splitread.py`, the
   method that already found Agent Under Fire's real bottleneck once.

2. **D&D Heroes flat fps dip (1 title), Thor.** A sustained, essentially
   unvarying ~14-15 fps ceiling for the whole scored window (0% share at
   28.5+), no hang, no audio shortfall, no crash -- `late_per_100=100.0` for
   every pace line on record. Proposing lane.dndfps: one `--perflog` soak,
   same read method as above; simpler than #1 since there's no collapse to
   isolate, the whole run reads the same.

3. **Bruce Lee: Quest of the Dragon, single 21.2 s hang (1 title), Thor.**
   Only one full-window run exists (81.3% share otherwise, the closest of
   the six to the bar). Per the single-run-flake rule, this needs a rerun
   before it's treated as a real defect -- if it doesn't repeat, Bruce Lee
   may already be within reach of a passing confirmation on its own.

**Lower priority, already has an owner or a clear next step, no new
dispatch:**

- **Crimson Skies** (85-97% across several short runs, best single reading
  94.1%): owned indirectly by lane.ibcache, whose `HAKUX_IBC=0` control
  build is what produced the 94.1% read. Needs a full 1200 s confirmation
  once ibcache's three remaining Crimson Nova runs are read.
- **DOA Ultimate** (91.4%, audio 0.136% over the 0.1% bar): its survey route
  ends on the User Profiles menu, not in a fight -- needs its own route
  (route-authoring work, not a code defect).
- **Kabuki Warriors, 007: Agent Under Fire, Forza**: already owned
  (uberspike569/shaderprebuild569 + lane.kabukistall; done via #530;
  forzadecay414) -- no new work from this lane.

**Unsettled, not yet a diagnosed defect:**

- **25 to Life**: two generic `survey`-route samples disagree (53.9% share
  at 28.5+ on the earlier build vs 83.0% on a later one that merges #442),
  neither from a dedicated route. Needs its own route and one clean sample
  before it can be classified at all -- the "54%" figure does not survive
  being checked against its own later run.

Dispatch-ready brief sketches for the top three (question, evidence, files,
first step) are written out in NOTES.md.
