# lane.cloud-190 -- model the 0x160 / 0x204-0x2FC PMC read-1 region

Issue: #190
Base: master @ 7ec5f8e42d747b6bdcf2679f34db4d7228a937d5
Files: hw/xbox/nv2a/pmc.c

## What's already measured

PR #191's read-only PMC survey (tools/nv2a_probe), two independent runs with
a reboot between them, 1,024/1,024 identical, no writes issued: 0x000160 and
0x000204-0x0002FC (63 consecutive dwords) read 0x00000001 on silicon; pmc.c
returns 0 for anything it does not name. 0x200 in that range is
NV_PMC_ENABLE, filed separately as #188 -- do not fold that register into
this one; keep the two changes disjoint.

## What is NOT established, and is out of scope for this lane

Whether this is 64 distinct live registers or one aliased/unimplemented-read
pattern is UNTESTED. Distinguishing them needs a write into the region, and
that region sits directly beside the register that already halted the
console once (#188's NV_PMC_ENABLE). Do not attempt a write to silicon, and
do not register a falsifier that implies one. Severity is filed as low: an
undocumented-register read is an unusual guest access pattern.

## Goal

Model the read side only: pmc_read returns 0x00000001 for 0x160 and for each
dword in 0x204-0x2FC (excluding 0x200/NV_PMC_ENABLE, which #188 owns), and
0 elsewhere unless another named register claims that offset. Writes to
these offsets should behave as they do today (dropped/no special case) --
this lane does not model write semantics for the region, only fixes the
read default.

## Falsifier

A read-only desktop-build test: pmc_read at 0x160 and at every dword offset
in [0x204, 0x2FC] except 0x200 returns 0x00000001; pmc_read(0x200) is
untouched by this change (still #188's row). No write-path assertion.

## Done when

pmc.c returns the measured 1s for the named offsets, the desktop build
passes, and #190 gets a short note confirming #188's register was left
alone.
