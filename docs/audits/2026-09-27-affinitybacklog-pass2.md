# Audit pass 2: PR #503, lane/affinitybacklog

Pass 2 checks that each pass-1 scenario can no longer occur. Head read:
`0b56db7a8c` ("affinity: a load pin ranks below a sibling that has landed").
The pass-1 findings are in `2026-09-27-affinitybacklog-pass1.md`.

**Verdict: clean. H1 no longer occurs. The three LOWs are carried forward
and do not block.**

## H1. A load pin outranks rule 2, so a hold on the pinned device splits the pair: CLOSED

`decide()` no longer returns a live load pin at the first line. A hand pin
(`_is_load_pin` false) still returns at once (rule 1). A live load pin is
kept in `load_pin`. The order is now: a running sibling on a live owner,
then a queued sibling (only if there is no live load pin), then a result
sibling on a live device, then the load pin, then rule 3. A dead load pin
falls through as before and writes its split note. With no `expect` key,
the function returns `load_pin`, so a keyless arms request keeps its pin.

I replayed the pass-1 sequence against the head's `affinity.py` with a
scratch dispatch dir. This was an independent script, not the selftest.
Both arms were `device: thor`, requester `arms-g-*`, same `expect`:

```
both live, base: 'thor' fix: 'thor'
thor held, base: ''
thor held, fix (base running on nova): 'nova'
H1: hold lifted, fix (base running on nova): 'nova'      <- was 'thor' at ac1c8a3f07
H1b: base finished on nova, fix: 'nova'
hand pin with nova result: 'thor'                          (rule 1 unchanged)
```

Pass 1 recorded step 5 answering `thor`. It now answers `nova`, and it still
answers `nova` once the base arm has finished and only a result remains.

Other cases the new ordering could have broken, all checked:

- **Normal, no hold.** Both arms are queued with a live thor pin and nothing
  has landed. Both answer `thor`, so a nova worker skips both. This is the
  PR's intended behaviour.
- **Queued sibling vs load pin.** A queued sibling no longer outranks a live
  load pin. At `ac1c8a3f07`, the explicit device already returned first, so
  nothing changes for the queued case. For an arms-job pair the two values
  are the same anyway.
- **Re-run of a prediction with old results.** A result sibling on a live
  device now outranks CHOOSE's pick. Both arms read the same results, so
  both follow the result and the pair stays together. This can cost some
  balancing but never splits a pair.
- **The dispatcher has no second copy of the rule.** `dispatcher.sh:651`
  asks `affinity.py` per request.

The selftest adds a replay of the sequence (the fix arm must answer `nova`).
It also adds a mutant that restores the early return and must answer
`thor`, and a control showing that a live load pin still decides when
nothing has landed. The mutant wraps `decide` and returns a live explicit
device first, which is the pass-1 ordering, so the check is not blind.

## LOWs, carried forward (not addressed at this head; none blocks)

- **L1.** `fleet.py` `queue_stall()` still treats every `device` as
  absolute. It can misreport a stall alongside a real outage.
- **L2.** Deploy skew. arms.sh's `affinity.py` comes from the repo, while
  the workers' copy comes from the `$DISPATCH_DIR/bin` snapshot. The
  dispatcher update window has to follow the fold, or a hold on a pinned
  device stalls a pair for up to the hold's length until it does.
- **L3.** `backlog()` is quadratic in the epoch-tier queue. This is harmless
  at today's queue depths.

## Selftest

CI run 36354972587 ("jobs selftest") passed at `0b56db7a8c`. That covers
2213 `ok` lines, including all three new checks:

```
ok   after a hold lifts, the fix arm follows its base arm running on the nova, not its own load pin
ok   MUTANT: a load pin that outranks a running sibling answers thor, and so fails the check above
ok   with no sibling landed, a live load pin is still where the arm goes
```

Android and Desktop build also passed on that sha, and the PR is mergeable.
A local full run hit its 900 s budget before it reached this fragment, so
CI is the record here.
