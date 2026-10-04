# lane.verdict10min -- the 10-minute confirmation (#433)

PR: see `docs/lanes/verdict10min/PR.md` (offline protocol: GitHub is
suspended). Base master @ 2ba1a6e9a2.

## The brief

The owner (2026-09-30 ~12:05 PDT) agreed to move `confirmation_s` from
1200 s to 600 s, on lane.local's 09-30 evidence: every full-length
confirmation re-scored as if cut at 300 s and 600 s reached the same verdict
at 5 and 10 minutes as at 20 on the Nova (6/6 runs; it plateaus near 49 C and
never pauses); on the Thor, Azurik read 99.6% at 10 minutes and failed at
15.6 minutes on the heat pause. So 20 minutes is kept only where it earns its
cost: a title flagged for slow-building defects, or a run whose window was
still heating when it ended.

## What changed

`docs/testing/titles/targets.toml`:
- `[defaults] confirmation_s` 1200 -> 600, with the decision and date in a
  comment.
- Forza Motorsport (4D53006E) and Kabuki Warriors (43560001) each carry
  their own `confirmation_s = 1200` (the brief's two starting flags:
  Forza's invalid-list decay and memory growth, #517; Kabuki's random
  stalls).

`docs/testing/title_verdict.py`:
- `need["confirmation"]` now reads a title's own `confirmation_s` from
  targets.toml (via `find_title`'s existing lookup), falling back to
  `[defaults]`, instead of only ever reading the default.
- STILL HEATING: a new check, run once `mark_t`/`end_t` and the thermal
  samples are known (same place the existing thermal-pause void logic
  lives). True when either a thermal pause overlapped the scored window at
  all (`hit`, already computed there), or a new `heating_rate()` helper
  finds xo-therm or the battery zone climbing faster than 1.0 C/min over the
  window's last 180 s. When true, and the confirmation figure in force was
  under 1200 s (i.e. no title flag already demanded it), it is bumped to
  1200 s and the run's duration failure reads "confirmation: 1200 s needed
  -- the device was still heating at the end" instead of the generic
  "duration: ... s < ... s confirmation" -- so a flag-driven 1200 s demand
  (Forza, Kabuki) and a heat-driven one read as different reasons, which
  matters for anyone triaging why a title needs the long form.
- `thermal.still_heating` and `confirmation_need_s` are recorded in
  verdict.json for visibility (the existing pattern for other computed
  bars, e.g. `fps_bar`, `target_fps`).
- Screening is untouched: `screening_s` was already 600 and stays a flat
  600 regardless of title or heat.
- `--require` still decides which bar (screening/confirmation) a run is
  judged against; a caller doing an actual confirmation check passes
  `--require confirmation` explicitly (as `docs/lanes/defecttriage433/
  judge_copy.py`, adapted from lane.verdict433's own judge_copy.py, already
  does). The auto-detect path (`--require` omitted) picks screening for a
  run short of ITS OWN (pre-heating-bump) confirmation figure, unchanged
  from before -- the heating bump only ever tightens a confirmation-level
  check, it does not reclassify which bar a short run is judged against.

`docs/testing/jobs/selftest.d/99-verdict-10min.sh`: four fixtures (flat
600 s pass, the same with a heating tail that needs 1200 s, a flagged-title
600 s run that needs 1200 s on the generic duration message instead, and an
existing-shape 1200 s pass), each read with `--require confirmation`
against the REAL `targets.toml` (so a future edit to either file is what
this test catches, not a copy), plus two mutants (drop the per-title
override; never apply the heating bump) that must turn the forza/heating
legs red respectively.

## What was NOT done (process, not code)

The audit -- "lane.verdict433 re-runs every 5th 600-s pass at the full
1200 s" -- is a dispatch/process step, not something to implement here. Its
existence is recorded in the rule's own comment in both
`docs/testing/titles/targets.toml` and `title_verdict.py`'s module doc, as
the brief asked.

Existing verdicts are not re-judged: nothing here touches a result dir that
already has a `verdict.json`, and a pass already recorded at 1200 s stands
regardless of the new default.

## Verification

`SELFTEST_ONLY="99-verdict-10min 89-title-verdict 99-thermal-pause
99-default-regimen 99-power-per-frame 99-display-covered 66-status-titles
99-status-fullwindow" bash docs/testing/jobs/selftest.sh` -- 172 passed, 0
failed (the touched file's own fragment plus every other fragment that
exercises title_verdict.py or thermal_state.py). Full `selftest.sh` was not
run end to end (18-25 min, unrelated fragments); these are every fragment
whose fixtures import or invoke the two files this lane changed.

## For the next lane

- `heating_rate()` and the `HEATING_*` constants live in `title_verdict.py`,
  not `thermal_state.py`, on purpose: the brief's Files: line does not
  include `thermal_state.py`, and the check only ever needs `zone_c` and
  `dev_ts`, both already public there.
- If a third slow-building title is flagged later, it is one
  `confirmation_s = 1200` line in `targets.toml`'s title entry -- no code
  change.
