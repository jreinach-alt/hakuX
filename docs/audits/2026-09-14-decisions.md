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
