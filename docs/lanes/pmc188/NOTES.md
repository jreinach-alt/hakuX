# lane.pmc188 -- #188: NV_PMC_ENABLE reads 0, silicon reads 0x01110000

Status: in progress.

## The brief

`hw/xbox/nv2a/pmc.c:pmc_read` has no `case NV_PMC_ENABLE` (0x200); the read
falls to `default: r = 0`. Two independent read-only sweeps on real NV2A
silicon, with a reboot between them and 1,024/1,024 dwords reproducible, read
`0x01110000` there. Scope is the read only.

Explicitly out of scope, from #188 itself: the bit-field semantics. The header
puts `_PFIFO` at bit 8 and `_PGRAPH` at bit 12; the measured value has bits 16,
20 and 24 set. Those header positions are the generic NVIDIA ones and may not
be NV2A's, and a different bit-position claim from this same sweep has already
been retracted as an endian artefact. Writing 0 to this register halted the
physical console. So: no write side, no engine-disable side effects, no new
bit-field macros.
