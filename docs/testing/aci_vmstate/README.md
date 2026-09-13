# `aci-vmstate` — does a save/load round trip reproduce the AC'97 codec?

Three seconds, no ROMs, no device, and **no configured QEMU build** — which
matters, because the desktop build does not currently configure on this machine
(`subprojects/curl-8.12.1/meson.build:532`, `Dependency "openssl" not found`,
see `docs/orchestration.md`). This is issue **#75**'s oracle.

```sh
cd docs/testing/aci_vmstate && make run
```

## Why this exists

Audio has no golden reference, so most claims on this stream have to be
anchored to a register's own arithmetic or to a repeat measurement. #75 is the
exception: **a save/load round trip must reproduce the device state**, and that
is checkable from source with nothing else present. Before the fix,
`vmstate_mcpx_aci` was `VMSTATE_PCI_DEVICE` and a bare `// FIXME`, so a load
restored 256 bytes of PCI config space and left every guest-visible AC'97
register at its reset value — and reported success.

## What it checks

1. **Byte coverage.** Walk the field list over `AC97LinkState` and record which
   bytes it touches. Every member classified `GUEST` must be fully covered;
   every `HOST`, `DERIVED` or `TRANSIENT` member must not be covered at all.
2. **The round trip.** Fill the whole struct and PCI config space with a
   pattern (no reset value anywhere), save through the field list, `memset` the
   device to fresh, load back. Every `GUEST` member must return byte for byte;
   every other member must still read as a fresh device, since anything else
   could only have come out of the stream.
3. **The post-load hook's opaque.** `post_load` must run exactly once and be
   handed `&state->ac97`. This is not decoration: the device-level
   `ac97_post_load` in `hw/audio/ac97.c` was handed `AC97DeviceState *` and
   cast it to `AC97LinkState *` from `7aa5985eba` (2018) until this campaign,
   and a nested `VMSTATE_STRUCT` is what makes the ACI immune to the same
   mistake.
4. **The drift gate.** The member list is *generated* from
   `hw/audio/ac97_int.h` by `carve.py`, and every member needs a row in
   `body.c.inc`'s classification table. Add a field to `AC97LinkState` and this
   fails until someone decides whether it is guest state. Verified by adding a
   dummy member: the run reports
   `AC97LinkState.newly_added_thing has no classification`.

## Why it can fail

A check that can only pass is not a check. The run therefore includes a second
arm using the **pre-fix, PCI-only field list**, and *requires* it to report
`guest state reproduced: 0 of 460 bytes`. Current output:

| arm | stream | guest state reproduced |
|---|---:|---:|
| `aci.c` as it stands | 716 B | **460 of 460** |
| PCI-only (control) | 256 B | **0 of 460** |

## What it does NOT prove

- **Not `post_load`'s re-derivation.** `ac97_link_post_load` is stubbed here;
  the harness proves the hook is reached with the right pointer, not that
  `reset_voices`/`set_volume` recompute correctly. That needs a running
  emulator.
- **Not QEMU's own walker.** `body.c.inc` implements a minimal
  save/load walk and its own `vmstate_info_uint8/16/32/buffer`. It reads the
  *real* `VMStateField` arrays through the *real* `migration/vmstate.h` macros,
  so offsets, sizes and types are the genuine ones (a member/type mismatch is
  a compile error via `type_check`), but a defect inside
  `migration/vmstate.c` itself would not show up.
  It refuses rather than skips anything beyond fixed scalars, fixed arrays,
  fixed buffers and nested structs — a skipped field would read as covered.
- **Not struct sizes.** `PCIDevice` and `MemoryRegion` are stubs in `shim/`, so
  `sizeof(MCPXACIState)` here is not the emulator's. Irrelevant: every offset
  is computed by `offsetof` against whatever this harness compiles, so the test
  is layout-independent.
- **Nothing about loudness.** The ACI is not in the audible path on this
  platform (`ep_sink_samples` returns false for `MCPX_APU_DEBUG_MON_AC97`).

## Layout

| file | what |
|---|---|
| `carve.py` | lifts the field list out of `hw/xbox/mcpx/aci.c` and the member list out of `hw/audio/ac97_int.h` |
| `harness.h` | the real `vmstate.h` and `ac97_int.h`, via `shim/` |
| `body.c.inc` | the walker, the `VMStateInfo`s, the classification table, the arms |
| `shim/` | opaque stand-ins for the QEMU headers those two reach |
