Lane: idlehaltspin          Issue: #525
Base: master @ 23416ffb77

# Fix the broken spin-variant prediction, then judge it

lane.idlehalt (PR #528, merged, retired) shipped the idle-halt vCPU sleep
(`HAKUX_IDLE_HALT`) opt-in, default OFF: H/C/F/heat/J-per-frame all held but
the L leg (p99 push-buffer-callback raise-to-run < 50 us) failed on both AUF
(14.2%) and Blinx (3.7%). It also landed a latency-mitigation variant,
`HAKUX_IDLE_HALT_SPIN_US` (a bounded spin before the condvar sleep, default
0, sha 40fabbaacc, `target/i386/tcg/translate.c`), and registered
`docs/testing/predictions/idlehalt-spin-{auf,blinx}.json` for arms.sh to
judge "on its own" before the lane ran out of turns.

arms.sh SKIPPED both (2026-09-28T17:21Z, issue #525 comment): `a_ref ==
b_ref, nothing to compare`. The registration is structurally broken -- both
refs resolved to the same merged commit, because the on/off distinction is
an env var, not two commits, and arms.sh compares refs. Nothing will
measure this on its own; that comment says so explicitly ("nothing to
delete on the host... until the registration itself changes").

Separately, lane.sustain507's PR #547 (folded, results on issue #507 and in
the PR body) measured idle-halt ON vs OFF **at the device defaults**, not
the spin variant, and found it is not a thermal lever there (cuts 0.13-0.58
W, falsifier's 1.5 W not met). That result stands; it does not touch L.

## Goal

Get a real A/B measurement of the spin variant against leg L. Two shas that
actually differ (e.g. base = 40fabbaacc with SPIN_US=0 vs a fix commit that
turns it on by default at a value taken from `docs/lanes/idlehalt/NOTES.md`
section 6, or whatever the retired lane's notes recommend) so arms.sh has a
real a_ref/b_ref pair. Re-register `idlehalt-spin-{auf,blinx}.json` bound to
that pair. Run the AUF (Nova) and Blinx (Thor) pairs.

## Falsifier

L fails again (p99 raise-to-run >= 50 us on either title) at every SPIN_US
tried up to some reasonable bound (start from the pilot's own suggestion,
else sweep 50/100/200 us) -- report that as a refutation and say so on
#525; do not keep tuning past a bound you can justify in NOTES.md. H/C/F
must still hold (they already do at SPIN_US=0; re-check they still hold
with spin on, since spin changes latency to sleep, not the sleep itself).

## Files

`target/i386/tcg/translate.c` (from [free]), `docs/lanes/idlehaltspin/**`,
`docs/testing/predictions/idlehaltspin-*.json`.

## Done when

Either L passes at some SPIN_US and the PR proposes flipping the default,
or every SPIN_US tried still fails L and the PR (or a #525 comment, if no
code changes) says the mechanism is exhausted and idle-halt stays opt-in
for good. Either way, delete or fix the two structurally-broken
`idlehalt-spin-*.json` files so arms.sh stops needing to skip them.
