# Audit pass 2: PR #554, lane/sustain507-fan (#507 Part D.2)

Head verified: `15350970ad`. Pass 1 audited `e406cafa7b`, and the only change
since then is the pass-1 audit file, so the code is byte-identical to what
pass 1 read. Pass 1: `docs/audits/2026-09-28-sustain507-fan-pass1.md`.

**Verdict: clean. Pass 1 raised no HIGH or MEDIUM, so no blocking scenario is left to fire. Fold-ready.**

## Scenarios from pass 1

| pass-1 finding | still occurs? | where |
|---|---|---|
| LOW-1: the run.log fan range includes the cool-down samples | yes, unchanged | `docs/testing/thermal_state.py:369` still calls `fan_range(ok)` over every readable sample. The battery figure at `:364` is limited to `t0` onwards; the fan figure is not |

Selftest re-run on this head: `SELFTEST_ONLY=99-thermal-pause`, 16 passed,
0 failed, `fan` included.

## Decision logged for LOW-1

Not fixed in this PR. The reason: the defect is confined to one line of run.log
text that nothing parses (`title_verdict.py` reads no `fan` key). Each
thermal.jsonl sample carries its own correct `fan` object and a `cool`/run
label, so any Part D analysis that reads the samples is unaffected. Only
someone reading the `THERMAL:` line by eye can be misled.

Carried forward: fix this before Part D quotes the run.log fan range as the
run's duty. The fix is `fan_range([r for r in ok if dev_ts(r) >= t0])`, plus a
fixture `cool` sample whose duty is above the run's, so that the leg fails if
cool-down duty leaks into the range.
