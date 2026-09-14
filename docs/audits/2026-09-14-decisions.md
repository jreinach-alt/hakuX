# Logged decisions on audit pass 1 findings not remediated

The protocol requires that a finding left unfixed carries a decision rather
than silence. These are the orchestrator's, made on `lane.remediate1`'s board
request. LOW decisions are `lane.audit2`'s and are not here.

## M5's third facility: the TCG counters — REVIEWED, NOT FIXED

`accel/tcg/tb-maint.c` (`hakux_inval_events`, `hakux_inval_tbs_overlap`,
`hakux_inval_tbs_spared`, `hakux_inval_emptied`, `hakux_inval_would_survive`,
`hakux_tlb_protect_calls`) and the `#ifdef XBOX` additions in
`translate-all.c`. `XBOX` is always defined in this fork, so that is not a
flag: they are unconditional, and they do violate AGENTS.md's rule that
instrumentation belongs behind one.

**Decision: leave them unflagged for now, and record the removal condition
that was actually missing.**

The reasoning, and the part I am least sure of is stated first. The flag rule
exists to stop instrumentation costing something in a shipped build. These sit
on TB invalidation rather than a per-draw path, so the cost argument that
justified flagging the #54 VRAM probe is genuinely weaker here — but *weaker*
is not *measured*, and I have not measured it. If someone does and it is not
free, this decision should be revisited rather than defended.

What made them worth keeping: #69 closed tonight on the strength of these
counters, and closed with a residual — moving them past their early returns so
they count generations and discards directly rather than calls and visits is
upstream-shaped and was explicitly left. So the counters are not leftovers
from a finished measurement; they are the current, corrected instrument for a
question that is still open.

**The real gap was never the flag.** It was that they had no recorded removal
condition, so nobody could tell a live instrument from an abandoned one —
which is exactly how the #54 probe came to run on Galleon three times with
nobody reading its output. Recorded now: **these retire when the direct
generation/discard counters land, or when #68's block-extent question is
closed.** Whichever comes first.

## M2 and M4 — ROUTED, NOT DEFERRED

`target/i386/tcg/fpu_helper.c` (M2) and `hw/xbox/nv2a/pgraph/gl/texture.c`
(M4) are `lane.remote`'s territory. Routed there rather than remediated by
`lane.remediate1`, which correctly refused to edit outside its claim.

They are **not** closed and must not read as closed. M2 in particular is the
sibling of the fix that made it visible: FRNDINT now honours the guest RC
field and FIST/FISTP still do not, so `helper_fistl_ST0`'s out-of-range guard
is unreachable. That is #74, which is already open and already routed.

## `glsl/psh.c:180-186` — ROUTED

The stale comment that misled pass 1's M3. In `[free]`, held by nobody, and it
is the third copy of a fact whose other two copies (`constants.h:449`,
`renderer.h:1628`) are correct. Route to whichever lane next holds
`glsl/psh.c`; it is a comment correction, not a behaviour change.

Worth noting for its own sake: **a stale comment cost an audit a finding's
accuracy.** Pass 1 quoted it as authority and overstated M3's blast radius on
the strength of it. The remediation caught it. That is the two-pass loop
working, and it is an argument for correcting stale comments that is stronger
than tidiness.

## The nv2a index: who regenerates it — DECIDED, fold-time, and the gate must stop punishing lanes

`lane.lows` measured the problem rather than asserting it: the committed index
was already stale at its base by **396 entries, all `vk/draw.c`, none of them
its own**. It arrived at a lane whose preflight then failed on drift the lane
did not cause, and fixing it would have swept another lane's churn into its
commit.

With three lanes running concurrently, three regenerated 829 KB JSONs conflict
at the next fold.

**Decision: fold-time regeneration is the rule, and the orchestrator owns it.**

That is already what happens in practice — `c58ce95249` is my own commit
titled "my own merge moved 68 sites" — but it was practice, not policy, so
nobody could rely on it and every lane paid for the gap.

Why this way round rather than making lanes regenerate on every `hw/xbox`
commit: the index is derived from the **whole tree**, so a lane regenerating it
necessarily commits other lanes' churn. That is not a lane's to own, and asking
three lanes to each produce an 829 KB JSON guarantees the conflict. One writer
at the merge point is the only arrangement where the file has a single author
per revision.

**What must change, and it is not mine to write:** `preflight.sh`'s `nv2a
index` gate should compare against the **fold base** rather than the tip, so a
lane fails only on drift it introduced. Until that lands, a lane that hits this
gate should regenerate, say so in its report, and expect the orchestrator to
take its version — which is what `lane.lows` did, correctly. Routed to
`lane.toolsmith`, which holds `preflight.sh`.

**Separately, a false positive worth its own note.** `nv2a_index.py` scores
"may not be" as a HEDGE gap, and it tripped on a *precise* sentence — "a
surface that may not be the current target". The lane reworded rather than
admit a false gap, which is the right call in the moment and the wrong one as a
pattern: a prose-scoring gap list has a false-positive rate, and that rate is
paid by whoever reads the list next. It belongs in `papercuts.toml`.

## M5 (`cpu-exec.c:605`, inv_htable eviction) — FOLDED UNREMEDIATED, deliberately

**This is an exception to "every HIGH and MEDIUM is remediated before the code
folds in", and it is recorded as one rather than quietly taken.**

**The audit's remediation is refuted.** It proposed evicting on insert, on the
grounds that a superseded entry "can never be recycled again". `lane.tcgfix`
showed that is false: `ihash` is over **guest bytes**, so alternating overlays
(A→B→A) make the older entry recyclable — and that is precisely the workload
#73 and #68 exist for. Evicting on insert destroys exactly the hit the cache is
there to get.

So following the remediation would have been worse than the finding. That is
the second time in this audit chain that a proposed fix was wrong and the
remediating lane caught it: pass 2 found the first HIGH's assert unfireable,
and `lane.lows` refused to write an unfireable one for L10.

**Why fold anyway.** M5 is **pre-existing** — it is how the recycle cache was
built, not something this remediation introduced — so folding does not make it
worse. Holding H1 for it would leave **undefined behaviour with two page
spinlocks held** in the tree, reachable from the DMA thread by the overlay load
#73 names as its own payoff. Trading a live UB fix for an unfixed pre-existing
cost is the wrong way round.

**What the protocol actually protects** is that a MEDIUM must not ship
*silently*. This one ships with a refutation of its proposed fix, this decision,
and its own dispatch. The chain-growth cost is real and unmeasured: the fix
needs a bound that keeps the most recent N, plus a counter that does not exist
today.

**Open, and it needs its own lane.** Not #81, not #73, not #68.
