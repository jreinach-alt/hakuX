# Audit pass 2: PR #528 (lane/idlehalt)

PR: #528, "lane.idlehalt: halt the vCPU in the guest idle loop (#525)"
Head verified: 968159ae26 (pass 1 audited cee0e5f3cb; the only change since
is the pass-1 audit file, so the code is byte-identical to what pass 1 read).
Pass 1: `docs/audits/2026-09-28-idlehalt-pass1.md`.

Verdict: **clean. No HIGH or MEDIUM scenario exists to fire; fold-ready.**

## Scenarios from pass 1

Pass 1 raised no HIGH and no MEDIUM, so there is no blocking failure
scenario to re-test. The four LOWs were re-read against the head. None was
addressed, and NOTES.md does not record a deferral for any of them. All four
still stand as described:

| pass-1 finding | still occurs? | where |
|---|---|---|
| LOW 1: stale `ih_on` bounds a real `hlt` | yes, same narrow race, opt-in only | `system/cpus.c:741` takes the bounded path on `ih_on` alone; `ih_on` is cleared only at `:783` and in `ih_wake` via `:794` |
| LOW 2: idiom match reads bytes outside the TB | yes | `hakux_idle_idiom` in `target/i386/tcg/translate.c`, unchanged |
| LOW 3: `slept_us` includes spin time | yes | `ih_t0` precedes the spin (`:752`); `:714` and `:782` add `now - ih_t0` |
| LOW 4: unguarded `wk` offset in `ih_tick` | yes, unreachable in practice | unchanged |

Each of them sits behind `HAKUX_IDLE_HALT=1` (LOWs 1-3) or is unreachable
(LOW 4). With the halt default off, `hakux_idle_halt_wait` is exactly
`qemu_cond_wait(cond, &bql)` (`:741-743`), so no LOW changes behaviour on
the default path. They do not block the fold.

## Carried forward

If the halt is ever turned on by default, fix LOW 1 first: clear `ih_on`
whenever `cpu->halted` is found 0 in `hakux_idle_halt_after_wait`. Also
subtract `spin_ns` from `slept_us` (LOW 3) before anyone compares the
`slept%` of the spin arms.
