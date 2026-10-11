# profileconv1011: gta-sa and amped2 measure on their golden profiles (#433)

Lane: profileconv1011          Issue: none (dispatched directly by lane.local, #433 umbrella)
Base: master @ 6d8947bb47
State: draft until both confirming device runs show gameplay with the HUD, matching the last good first-run frames
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

Confirming device runs pending (see NOTES.md for ids once queued).
