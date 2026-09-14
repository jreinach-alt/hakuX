# #68's arm ran and is VOID by its own instrument

Six soaks, three per ref, Crimson Skies, 90 s each. Arm A at `117203fe9b`,
arm B at the held commit `937848c9e7`. Judged with `docs/testing/perf/tcg_pages.py`
against `docs/testing/predictions/tcg-range-test-restored.json`, registered by
`lane.tcginval` before any of them ran.

## Arm A is coherent and every control passes

```
xx = 0 over 21 windows              every visited block was live-and-discarded
                                    or already-invalid-and-not
sp + ov == di in every window       the live population agrees between the
                                    overlap split and the discard counter
visits 280,384 = discards 40,880 + already-invalid 239,504   residual 0
waste 11.69 discards per generation (40,880 / 3,497)
ws/em = 38,177 / 38,177 = 100.0%
```

**85% of visits are dead blocks.** The page lists carry already-invalidated TBs
that `do_tb_phys_invalidate`'s early return refuses to unlink, so every later
store re-visits them — which is #73's defect, measured from the other side.

## Arm B's counters are incoherent, and the tool says so

```
VOID: sp + ov != di in 21 of 21 windows
visits 160,838,266 = discards 1,307 + already-invalid 0   residual 160,836,959
visited 720,554 / 8,479,446 / 13,983,030   against arm A's 280,384
em 0 / 0 / 6                                against arm A's 38,177
```

`sp + ov` and `di` are **two separate counts of the same live population on one
log line**. They must agree exactly. They do not, in every window. And
`visited` is up by ~573×, with a residual of 160 million.

That is not a behavioural result. **It is the counters measuring a different
thing after the change**, which is precisely what audit pass 1's M1 warned
about from the other direction: the #73 fix silently altered what `ws` counts,
because the identity it relied on (`em` implies `seen == live`) was true only
by accident.

## What this establishes, and what it does not

- **The arm is void.** No verdict on whether restoring the range test is a win.
  `em` falling from 38,177 to ~0 is the shape the prediction expected, but it
  cannot be read off an instrument whose own consistency check fails in every
  window.
- **`937848c9e7` must not fold.** It has been held since it was written, on
  `lane.tcginval`'s own recommendation that it must not fold on an Android
  build alone. That recommendation is now vindicated by measurement rather than
  by caution.
- **The next step is the instrument, not the device.** More soaks cannot fix a
  counter that disagrees with itself. Whatever `937848c9e7` changes about the
  populations these counters are taken over has to be reconciled first — and
  `lane.tcgfix`'s M1 work is the precedent for how: it found that a proposed
  remediation was wrong because the auditor had not read this commit.

## Not established

Whether the range-test restoration is correct, beneficial, or costly. Whether
`visited`'s 573× jump is a counter placed inside a loop it should be outside,
a population change, or an overflow. Whether arm A's own 100.0% spared figure
survives — it carries the tool's standing caution that a page list clogged with
dead TBs reports 100% spared while saying nothing about live ones.
