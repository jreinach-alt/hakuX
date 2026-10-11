# profileconv1011: gta-sa and amped2 measure on their golden profiles (#433)

Lane: profileconv1011          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 6d8947bb47
State: draft -- gta-sa CONFIRMED; amped2 re-run queued, waiting on the Nova (see OUTBOX.md)
Files: docs/testing/titles/routes/gta-sa.route, docs/testing/titles/routes/amped2.route, docs/lanes/profileconv1011/**
Prediction: none: analysis-only (route-header change verified by compose()/resolve_route() reads, not a perf arm; proof is the device runs' frames, judged by eye against the last good first-run run)
Needs device: yes (Nova only, queued)    Needs NDK: no
Release note: none (test infrastructure/route-state change, no player-visible effect)

## What changed

`compose()` (titlestate.py) strips a title's own golden from its disk when
its route declares `# state: first-run` -- the one case that matters, since
every OTHER title's golden still composes. Both `gta-sa` and `amped2` declare
`first-run`, so each run's golden (title data only, no save directory,
promoted 2026-10-03) was being stripped even though both were confirmed on
exactly this golden shape.

Per `SETTINGS_ONLY_FIX` in titlestate.py: a golden confirmed on as-is heads
its route `# state: any`, which loads the golden unchanged (`any` reaches
neither the `first-run` pop nor the `returning` `NoGolden` checks). Both
routes are re-headed `any`; no step lines changed. `docs/lanes/profileconv1011/NOTES.md`
section 4 has the pre-run prediction (no visible change expected; neither
golden has a save-slot subdirectory, so neither game's own save/continue
logic should find anything).

## Confirming device runs

- **gta-sa: CONFIRMED.** Run `1-1791746513-profileconv1011-1034280`.
  `hdd.json`: `loaded: golden, save: 7da19befd45b`. Every shot (boot, skA,
  menu, load, cut1-cut3, moved, gameplay) matches the last good first-run
  run frame for frame, modulo loading-time jitter the route's own header
  already documents. Detail: NOTES.md section 6.
- **amped2: in progress.** Attempt 1 (`1-1791746520-profileconv1011-1034452`)
  hit a device/WSL adb flake at 536s of 900s; `hdd.json` confirmed
  `loaded: golden, save: f90786b6e0f5` and every frame captured before the
  flake matched the baseline (NOTES.md section 7). A clean re-run,
  `1-1791749881-profileconv1011-1652106`, is queued on the Nova behind a long
  backlog; see `OUTBOX.md` for what resolves it.
