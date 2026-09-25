# lane.cloud-189 -- does anything this campaign runs touch NV_PMC_BOOT_1 (0x004)?

Issue #189. Analysis only; no emulator file is edited.

## Answer

**No.** Nothing in the test-disc source this campaign builds against accesses
0x004. The one piece of guest code with no source, the retail kernel, leaves
0x004 at `0x00000000` on silicon. The emulator already returns that value,
because `pmc_read` falls through to `default:` and reads 0 there
(`hw/xbox/nv2a/pmc.c:104`).

The only way we could diverge from hardware is for a guest to *write* non-zero
bits to 0x004. We found no such write, and the byte-swapped access that would
follow makes no sense on an x86 guest. Modelling the endian switch, which would
add a check to every MMIO access, has no consumer here.

**Recommendation for the board (lanes do not edit the tracker):** move
`[issue.189]` in `nv2a_issues.toml` from `dispatch_state = "available"` to a
recorded reason such as `"no observed guest access: corpus grep 0 hits, silicon
post-boot value 0 == emulator default read (lane.cloud-189)"`. Reopen it only
if a title trace shows a write to PMC+0x004.

## What was searched

The trees the test XBE is built from, at the shas this campaign pins:

| tree | sha | why this sha |
|---|---|---|
| abaire/nxdk_pgraph_tests | `6743b6ab164e760e8b995e969c762d829af5d52e` | `docs/testing/nv2a_index.json` `provenance.tests_commit` |
| abaire/nxdk (submodule) | `73c95900965a16be3a3e34b8d4d5d41bc18498be` | the tests tree's `third_party/nxdk` gitlink. pbkit and hal live here, and they do the actual MMIO |
| abaire/pbkitplusplus | `f1491d1a05dbb44b48c1b388b86626659f6b3e3e` | the tests tree's `third_party/pbkitplusplus` gitlink |
| abaire/pbkitplusplus | `e91d509e4f75d6d815807d80443e4e56aab89772` | `PBKIT_SHA` in `.github/workflows/nv2a-index.yml` |

Fetch (depth 1, into any scratch dir):

    git init -q T && git -C T fetch -q --depth 1 https://github.com/abaire/<repo> <sha> && git -C T checkout -q FETCH_HEAD

### 1. Name search: 0 hits

    rg -i 'PMC_BOOT_1|BOOT_1\b|0x?fd000004|NV_PMC_ENDIAN|PMC_ENDIAN|BIG_ENDIAN_MODE|ENDIAN_MMIO|MMIO.*endian' <roots>
    -> No matches found

**Positive control:** the same search for `PMC|VIDEO_BASE|0xFD000000` does find
PMC accesses. pbkit reads `NV_PMC_INTR_0` (0x100) and writes `NV_PMC_INTR_EN_0`
(0x140) and `NV_PMC_ENABLE` (0x200), in `nxdk/lib/pbkit/pbkit.c:285, 528, 828,
2217, 2391-2401, 2584-2585`. So the search can see PMC accesses, and 0x004 is
not among them.

### 2. Offset resolution: 0 candidates

A name search misses a raw `VIDEOREG(4)` and any macro that expands to 4.
`mmio_offsets.py` (this directory) extracts the argument of every
`VIDEOREG/VIDEOREG8/VIDEOREG16(...)` and `VIDEO_BASE + ...` access. It also
extracts every `NV20_TCL_PRIMITIVE_3D_PARAMETER_A` push, because pbkit's
`PB_SETOUTER` interrupt routine does `VIDEOREG(paramA)=paramB`
(`pbkit.c:329`), so that path is an indirect MMIO write. Each argument is
resolved through every `#define` under the roots.

    python3 docs/lanes/cloud-189/mmio_offsets.py tests nxdk pbkpp pbkpp2
    files scanned: 536
    accesses with a constant offset: 464 (137 distinct)
      PMC-range (< 0x1000): 0x100 x8, 0x140 x9, 0x200 x13
    accesses with a runtime term, by constant base: 162
      lowest bases: 0x8900, 0x8908, 0x8910, 0x8918, 0x8920, 0x8928
    accesses with no constant term (check by hand): 16
    accesses that are or could be 0x004: 0

I checked all 16 no-constant-term accesses by hand:
- `ParamA`/`paramA`/`addr` (7) are the `PB_SETOUTER` body itself plus comments
  describing it. The pushes that feed it resolve to `NV_PRAMIN+…` (0x700000+),
  `NV_PGRAPH_DEBUG_5` and `NV_PGRAPH_UNKNOWN_400B80`.
- `NV_PVIDEO_UNKNOWN_88/8C` (4) are commented-out lines in
  `tests/src/tests/pvideo_tests.cpp:266-271` (0x8088/0x808C).
- `pb_FifoFCAddr`/`pb_FifoHTAddr` (5) are `baseaddr+NV_PRAMIN(+0x1000)`
  (`pbkit.c:2455, 2461`), which is 0x700000 or higher.

The test program itself never pushes `PARAMETER_A` or `FIRE_INTERRUPT`
(0 hits in `tests/`, `pbkpp*/`; the positive control `NV097_SET_ZSTENCIL|NV097_CLEAR_SURFACE`
hits `tests/src/tests/clear_tests.*`).

### 3. The guest code with no source: the kernel

Every disc also runs the retail kernel and the dashboard before the XBE. We
cannot grep those. Two measurements already on disk bound what they leave in
0x004:

- `tools/nv2a_probe/host/sweep_writable_bits.py:168` records that on silicon,
  after boot, **0x004 held `0x00000000`** before the sweep wrote it ("left
  0x000004 holding 0x01000001 instead of 0").
- In both probe runs, `docs/testing/nv2a-probe-pmc-findings.md:35` reads BOOT_0
  as `02A000A3` before 0x004 was written. That is not byte-swapped (swapped it
  would read `A300A002`), so the kernel hands over with MMIO in the default
  byte order.

`pmc_read` returns 0 for 0x004, so a guest reading the register after boot sees
the same value on silicon and here. This does **not** tell us whether the kernel
sets the bit and then clears it again *during* boot. The emulator boots the same
kernel without byte-swapping anything, and such a sequence would be pointless on
x86, but no measurement rules it out. If we ever need to, the evidence would be
the existing `nv2a_reg_write` trace point: `pmc_write` calls
`nv2a_reg_log_write(NV_PMC, …)` on every write. Run a desktop boot with
`--enable-trace-backends=log` (the `build.sh:165` debug configuration) and
`-trace nv2a_reg_write`, then grep for `PMC` writes at `0x4`. That trace is not
worth running until a title gives a reason to.

## What the next lane should not repeat

- Do not implement the endian switch on this evidence. It has no consumer.
- The issue's open question is why writing 0 did not restore normal byte order.
  It is still open, and nothing here depends on it.
  `sweep_writable_bits.py:168` records that after the `0xFFFFFFFF` write the
  register held `0x01000001`, so the writable bits are 0 and 24, which trade
  places under a byte swap. But `0x00000000` is the same value in either byte
  order, so a swapped bus alone cannot explain the failed restore. Settle it
  against envytools, as the issue asks, before anyone models the write side.
