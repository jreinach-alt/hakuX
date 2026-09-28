# lane.memfast (#507)

The vCPU's memory path: a VA==PA census of the XBOX load fast path (phase 0),
removing its dead preamble and per-load test (phase 1), and a fastmem design
(phase 2). Brief: `briefs/memfast.md`; plan: lane.vcpuplan, PR #589,
`docs/lanes/vcpuplan/NOTES.md` items 0, 1 and 3.

## Refs

| ref | what |
|---|---|
| `31515f9751` | phase 0: the `[mf0]` census (instrumentation only); a_ref |
| `82e0ef1fa9` | phase 1: the fast path, its preamble and the X26/X27 reservations removed; b_ref |

## The code as found (master be05285c44)

- `tcg_out_tb_start` (`tcg/aarch64/tcg-target.c.inc`) opened every TB with
  `ldr w16,[x27,#8]; cbz; ldr w16,[x27,#12]; cbnz; ldr x26,[x27]; b; mov x26,#0`.
  That is `xbox_ram_fp.active`, then `cb_count`, then `host_base` cached in X26,
  or 0.
- `prepare_host_addr` opened every guest **load** with `cbz x26, tlb`, then:
  - `tst addr, #~(ram_size-1)`: if the address is in range, host = X26 + addr,
    with no TLB lookup;
  - otherwise, the same test against `vram_pci_base` (NV2A BAR1):
    host = X26 + addr - vram_base.
  - Only then the softmmu compare.
- `active` is set once, at the first flip (`pgraph/vk/renderer.c:2485`).
  `cb_count` counts live `mem_access_callback`s, which are the NV2A surface
  watches (`system/physmem.c`).
- X26 and X27 were reserved, taking two callee-saved registers from the
  allocator.
- **The fast path indexes guest-physical RAM with the guest-virtual address.**
  Nothing checks that the page is identity-mapped, present, readable, not
  MMIO, or that the access does not straddle the window's end.

## Phase 1 decision: drop it, do not make it live

The brief asks: drop the path, or make it correct and live. **Drop it.** The
census does not change this, for three reasons:

1. **A correct version needs a per-page lookup.** Whether VA maps to the same
   RAM offset is a property of each page. Knowing it per access *is* a TLB
   lookup, which is what the softmmu compare already does.
2. **The hoist cannot make it correct.** The plan's hoist (one global, with a
   `tb_flush` on change) removes the per-TB test, but it does not make a
   non-identity page read the right bytes.
3. **Phase 2 is the correct form.** Direct access with no compare is fastmem:
   the host MMU holds the per-page translation. It replaces this path.

What the census decides is different: whether the removal is *also a
correctness fix*. That needs both:

- the armed share (`act=1` with `cb=0`) above 0 on some title;
- non-identity (`ln`) or device (`lo`) installs on that title.

The census also sizes phase 2: the distinct mappings in the windows. If a
title has both, the fix gets its own line on #507, and the release note
names it.

### What the removal can and cannot move

- **Pixels.** They can move only where the path was armed during a pgraph
  test and read a different page than the TLB would. Such a move is a fix.
  The pixel prediction (`memfast-drop-pixels.json`) says no capture moves.
- **Speed.** Every TB loses up to 7 instructions and every load loses 1-12.
  The allocator gains X26/X27 (callee-saved, already saved and restored by the
  prologue).
- **Unchanged.** The softmmu compare, the slow path and store codegen.

## Phase 0: the `[mf0]` census

- **Where.** `tlb_set_page_full` (`accel/tcg/cputlb.c`) classes every install
  in the fast path's two windows. The test compares the TLB's own host pointer
  for the page with the one the fast path computes:
  - `id`: the same pointer;
  - `nid`: another RAM page;
  - `io`: not RAM.
- **What else it records:**
  - distinct `nid` pages, in a bitmap;
  - the first 8 with their VA and PA (`[mf0] first`);
  - the exact wall time with `cb_count == 0`, booked on the 0<->1 transitions
    under a lock in `physmem.c`.
- **Output.** One line every 2 s, at the `[tlb68]` cadence, tag `hakuX` at W:
  `[mf0] w dt act cb cb0ms up dn li ln lo vi vn vo lnd vnd vb`.
  - `cb0ms=-1` on the first window (no baseline).
  - A run with no line is VOID.
- **Reader:** `docs/lanes/memfast/mf0_read.py <result dir>`.
- **The b_ref keeps the counter.** There, the "armed" share still counts
  `cb=0` time, but nothing reads it.

## Predictions

- `docs/testing/predictions/memfast-drop-pixels.json`: all 100 golden suites
  bit-identical per capture, skipping `RenderTextureLoop` as the full sweep
  does. The arms job queues it.
- `docs/testing/predictions/memfast-drop-soak.json`, hand-read:
  - J/frame and fps pairs on GTA (Thor) and Nightfire (Nova);
  - gameplay reach on GTA, Nightfire and Crimson;
  - the census on the A runs, plus AUF;
  - the jitmix vCPU-share leg (needs a held simpleperf window: board request).

## Log

- 2026-09-28: branch, both commits, a type check against the NDK compile
  database (`compile_commands.json` from the main tree's Release `.cxx`; no
  new warnings in `physmem.c`, `cputlb.c` or `tcg.c`, which includes the
  backend). Predictions registered. Both devices were held at the start
  (Nova battery 14%, Thor host maintenance).
