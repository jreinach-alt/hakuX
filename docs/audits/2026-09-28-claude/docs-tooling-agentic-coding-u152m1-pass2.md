# Audit pass 2: PR #560 (lane.remote, #557 thermal governor core)

Head verified: `8727eaaae2`. Pass 1 audited `8a0d7a34b7`. The only change since then is the pass-1 audit file (`git diff --stat 8a0d7a34b7 8727eaaae2`), so the code is byte-identical to what pass 1 read. Pass 1: `docs/audits/2026-09-28-claude/docs-tooling-agentic-coding-u152m1-pass1.md`.

**Verdict: clean. Fold-ready.** Pass 1 raised no HIGH or MEDIUM, so no blocking scenario is left that could fire. All five LOWs are still present and are deferred below, each with its reason. The PR is MERGEABLE and both `build` checks pass on this head.

Nothing calls the core yet. A grep for `thermal_governor_tick` and `thermal_governor.h` outside the two governor files finds no caller in `android/app/src/main/cpp` or `ui/`. So no LOW can occur in a shipped build until the hook PR lands.

## Scenarios from pass 1

| pass-1 finding | still occurs? | where |
|---|---|---|
| LOW-1: the `off:` line is emitted before the first gfps line | yes, unchanged | `thermal_governor.c:616`, emitted on the first tick |
| LOW-2: one unreadable cooling device blocks every step up | yes, unchanged | `count_set()` at `:515-527` returns -1 on any failed `pread_long`, and `cool` at `:341` requires `s->pause == 0` |
| LOW-3: a pause with xo-therm unread is dropped | yes, unchanged | early return in `thermal_governor_feed()` (`:295`) |
| LOW-4: CLOCK_MONOTONIC does not advance across suspend | yes, unchanged | `:584` |
| LOW-5: unregistering an engaged rung strands it | narrowed, not closed | `thermal_governor.h:159` already says "register each rung once", which implies no re-registration. It does not name NULL |

## Decisions logged

All five are deferred to the hook PR, which is the first change that makes any of them reachable. The rule for the hook PR: **LOW-1 and LOW-2 must be fixed or re-justified before its device run.**

- **LOW-1:** hold the `off:` line until `status_every_s`, the way the config line is held. Without that, the first opt-in run on an enforcing ROM shifts every `phase_read_split.py --window` origin.
- **LOW-2:** count the readable devices and report the unreadable count as a separate field on the `state` line. Without that, one bad device silently pins the governor at its lowest rung for the rest of the session.
- **LOW-3, LOW-4:** these are bounded by `gap_reset_s` and by the 60 s window against the 300 s up-dwell, as pass 1 showed. They can wait until a device trace shows either one.
- **LOW-5:** add "never with NULL" to the sentence at `thermal_governor.h:159` when the hook PR adds the first real registrant.
