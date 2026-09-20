# Emulator versus hardware, at the register level

The first comparison of PGRAPH register state between this emulator and the
console. One test, identical configuration on both sides.

Cross-reference: #112, #38. Console: `xbox-console-provenance.md` (calibrated
3,374/3,379). Programme: `nv2a-mapping-programme.md`.

## What was run

`Blend tests::#spot_0_ADD`, alone, with `enable_pgraph_region_diff` and
`enable_progress_log`. A suite containing exactly one test means the harness's
`Initialize()`/`Deinitialize()` capture brackets that test, so no source change
was needed. Both sides ran the same ISO built by `make_test_iso.py` from the
same stock image, and both logged `Starting [1/1]`.

## The result

| | |
|---|---:|
| PGRAPH registers moved on **hardware** | **299** |
| PGRAPH registers moved on the **emulator** | **24** |
| moved by both | 24 |
| moved by the emulator only | **0** |
| moved by hardware only | 275 (63 of them known noise) |
| moved by both, **different end value** | **3** |

**The emulator never invents state.** Its 24 are a strict subset of hardware's
299, and that is worth saying plainly: there is no register the emulator
touches that silicon leaves alone.

## The three that disagree

| register | hardware | emulator | differing bits |
|---|---|---|---|
| `NV_PGRAPH_SURFACE` | `30100001` → `30200001` | `30100000` → `30200000` | **bit 0** |
| `NV_PGRAPH_TEXFMT0` | `089104B8` → `08813AB8` | `0AA1068A` → `08813A88` | **bits 4, 5** |
| `NV_PGRAPH_TEXFMT1` | `000105B8` → `09913AB8` | `0881198A` → `09913A88` | **bits 4, 5** |

All three differ in bits `nv2a_regs.h` does not name.

`NV_PGRAPH_SURFACE`'s declared fields are `WRITE_3D` (`0x00700000`),
`READ_3D` (`0x07000000`) and `MODULO_3D` (`0x70000000`). Bit 0 is not among
them, and hardware holds it **set** in both the before and after snapshot while
we hold it clear throughout — so this is not a transition we get wrong, it is a
bit we never set at all.

`NV_PGRAPH_TEXFMT0`'s declared fields run `CONTEXT_DMA` (bit 1),
`CUBEMAPENABLE` (bit 2), `BORDER_SOURCE` (bit 3), then jump to
`DIMENSIONALITY` (bits 6-7). **Bits 4 and 5 are a gap in the header**, and both
texture format registers end with them set on hardware and clear here.

## Why this is worth more than the pixel score

The same run's capture differs from the golden by **5,412 pixels with a maximum
delta of 1** — textbook #38 "one-step colour difference" territory, the kind of
residual that gets attributed to rounding and parked.

At the register level the same run shows two texture-format registers ending in
a different state, in bits nobody has named. Whether those cause the one-step
difference is a hypothesis this measurement does not settle. What it does is
give the hypothesis somewhere to point, which a pixel count never will.

This is the case the register comparison was built for: **state that differs
structurally while the picture looks almost right.**

## The 275

Most of the gap is not a defect list. `pgraph.c` models the NV2A at the
*method* level — `methods.h.inc` dispatches 209 entries — and maintains its own
`pg->regs_[0x2000]`, which is not obliged to mirror silicon's internal state.
275 registers moving on hardware and not here is a measure of how much of that
state the abstraction does not represent, not 275 bugs.

Only five of the 275 are named at all, and four of those are on the harness's
own noise blacklist. The fifth is `NV_PGRAPH_CSV1_A`
(`00000000` → `00010000`), which the emulator leaves untouched.

## Reproducing it, including what the existing recipe gets wrong

`desktop-runs.md` is accurate except in three places that cost time here.

- **`xvfb-run` does not work on this host.** `/tmp/.X11-unix` is mode `0777`
  rather than `1777`, so Xvfb refuses to create its listener, and `xkbcomp` is
  absent. **WSLg already provides an X server on `:0`** — using `DISPLAY=:0`
  and no Xvfb at all is simpler and works.
- **An MCPX boot ROM is required in practice.** `xbox.c:147` guards on the
  `bootrom` property, so it is optional in code, and the machine starts without
  one — it then spins without ever reaching the disc. With
  `mcpx_1.0.bin` (512 bytes) configured, the same run exits 0 and writes
  results.
- **A missing flash ROM is not fatal and that is the trap.** `xbox_flash_init`
  prints `Failed to load BIOS` and fills the region with `0xff`, so the
  emulator comes up and runs, looking healthy, doing nothing.

The build needs `cmake`, which was avoidable for the probe and is not avoidable
here. On a host without `sudo`, `apt-get download` plus `dpkg -x` into a prefix
works for the whole dependency closure — `apt-cache depends --recurse` gives
the list, and `PKG_CONFIG_PATH` with `PKG_CONFIG_SYSROOT_DIR` wires it up. Use
`-idirafter`, not `-I`, for the extracted include tree: `-I` puts the extracted
libc headers ahead of the system ones and the build dies in `osdep.h`.

## What to do next with it

Widen. This is one test. The same procedure over a suite, or over the tests
behind a specific issue, costs one emulator run and one console run each and
produces a named-register difference list rather than a pixel count.

The capture point is still `Initialize`/`Deinitialize`, so a suite with more
than one test gives per-suite residual state rather than per-test. Single-test
discs avoid that entirely at the cost of one run per test.
