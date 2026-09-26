# lane.dmasurf277 -- #277 xemuReadFromFileIntoSurface

## Result

**Mechanism:** a device DMA write that goes through a direct RAM mapping never
reaches the surface watch. The surface's stale copy is then downloaded over it
on the guest's next CPU read.

**Hunk:** `system/physmem.c`, `address_space_map()`, direct-RAM branch (commit
`c49955975b`). For a write mapping, call
`mem_check_access_callback_ramaddr(qemu_get_cpu(0), ram_addr + xlat, *plen, BP_MEM_WRITE)`
before returning the host pointer. That is what `flatview_write_continue()`
already does for every non-mapped write, including the bounce-buffer path of
this same function.

**Holder:** none. No `territory.toml` row and no open PR names
`system/physmem.c`, so I have filed a board request for it. It is **not**
`vk/surface.c` (the issue's guess, lane.remote's #109) and not `vk/draw.c`.

**Arm:** `docs/testing/predictions/dmasurf277-dmamap.json`, a=`7f6b5e3473`
b=`c49955975b`.

## The test (nxdk_pgraph_tests `dma_corruption_around_surface_tests.cpp`)

1. The CPU memsets 640x480x4 of texture memory to `0x22`.
2. A colour surface is bound at that address (A8R8G8B8, 640x480) and a no-op
   (degenerate) triangle is drawn. This creates the SurfaceBinding (uploaded
   0x22, `draw_dirty` set, CPU watch registered).
3. `NtReadFile(FILE_NO_INTERMEDIATE_BUFFERING)` reads 64 KiB of `0xFF` from
   `Z:\opaque_white.raw` into the first 64 KiB of that surface. This is IDE
   bus-master DMA.
4. The guest prints the first dword ("Read"), rebinds the framebuffer and draws
   that memory as a 128x128 A8R8G8B8 texture, then prints the first dword again
   ("Surf flush").

The target is a bound surface's backing memory, not a texture. The sibling
`xemuReadFromFileIntoTexture` does the same read into memory that no surface
occupies, and it passes.

## The trace

- IDE DMA uses `dma_blk_read` -> `dma_memory_map` -> `address_space_map`. For
  RAM, `memory_access_is_direct()` is true and it returns a host pointer. The
  block layer writes into that pointer, and `address_space_unmap` then only
  calls `invalidate_and_set_dirty`. That sets the NV2A/NV2A_TEX/VGA dirty bits,
  which is why the texture sibling passes, but it never calls the access
  callbacks.
- The surface watch (`surface_access_callback`, vk/surface.c:1877 and
  gl/surface.c:1612) is reached from two places: TCG TLB watch flags for CPU
  accesses, and `flatview_write_continue` / `flatview_read_continue` (physmem.c)
  for `address_space_rw`. The direct map path is the one guest-RAM write path
  that reaches neither.
- So after step 3 the surface still has `draw_dirty` from the no-op draw and
  `upload_pending` false. The CPU read in step 4 trips the watch, which sees a
  dirty surface and downloads the whole surface. That writes 0x22 back over the
  file's white. **The capture shows it: `Read 0x22222222`**, where the console
  shows `0xFFFFFFFF` (hardware/runs/2026-09-19-calib).
- This path is shared by both renderers. That matches lane.remote's desktop
  measurement on #277, where GL and Vulkan both fail with 90,912 px.

With the hunk, the map-time callback downloads the surface first. It is still
0x22, so nothing is lost; the callback then retires `draw_dirty` and sets
`upload_pending`. The DMA lands white, and the CPU read finds nothing to
download. On the texture side, VK disables surface-to-texture when
`upload_pending` is set (vk/texture.c:1797) and reads VRAM; GL re-uploads
(gl/texture.c:804). Either way the texture reads white.

## Scores on disk (region = the golden's white pixels minus the text block, 91,311 px)

| date | run | wrong px in region | scorer |
|---|---|---:|---|
| 09-09..09-14 | res_full0907, fullrun4/5, z-sweep/after/tip, z-6762a54c82, z-c866527e03 (+repeat) | 87,405 each | -- |
| 09-25 | 1790359589-xbox-full6743-dry3 | 87,405 | -- |
| 09-25 | 0-a-now-8e683b3a26 (thor, apk 423469eb5d42) | 87,405 | 90,912 px, status `white-content` (not `unreadable`) |
| 09-19 | console calib run1 | 0 | golden |

Every run from 09-09 to today gives the same figure on both devices, so this is
not a stale capture. The scorer's 90,912 also counts the "Read"/"Surf flush"
text glyphs.

## Arm legs

- must_move: `DMA_corruption_around_surfaces/xemuReadFromFileIntoSurface` goes
  from 90,912 to 0.
- must_not_move, with the change that would move each:
  - `DMAOverlap` and `xemuReadFromFileIntoTexture` are exact today. A move means
    the new call matched a range it should not (the mapping's ram_addr
    disagreeing with the watch's).
  - `Surface_format/*` and `Clear/*` do no DMA into
    a bound surface. A move means a test-host file read overlapped a still-dirty
    watched surface. Moving toward the golden would be a real extra fix; moving
    away, or a hung run, refutes the hunk.

## Risks the arm checks, and the next lane should not re-derive

- **Deadlock.** The callback waits on `downloads_complete` from the pfifo
  thread, and IDE DMA completion runs with the BQL held. The pfifo thread takes
  the BQL only for the context-switch and error interrupts (pgraph.c:1062,
  2263). `flatview_write_continue` already calls the same callback from
  BQL-holding device writers, so this adds no new class of risk. It is still
  the thing to look for if the arm hangs.
- **Not done: the read leg.** A device reading RAM through a direct map (for
  example, DMA-out of a rendered surface) also skips the watch, so it would read
  stale RAM. The symmetric `BP_MEM_READ` call at map time would fix that. I left
  it out because no capture here needs it and it adds a finish per overlapping
  DMA read.
- Do not look in `vk/surface.c:3406-3422` (the upload check) for this bug. The
  upload never gets the chance: the download destroys the data first.

## Remediation 1 (job.cloud, 2026-09-25, pass-2 MEDIUM-1)

- The arms job refused the arm twice: `Surface_as_vertex_array/*` has no PNG in
  the golden set that `request.sh` checks keys against, although the suite is in
  the nv2a index. Re-registered with `--force` before any arm ran. The refs are
  unchanged and there has been no rebase. That leg and its disc suite are
  dropped. The other four legs each bind to a golden PNG (checked against
  `goldens/results`, not the index).
- The pass-1 LOW-1 BQL wait is not filed as an issue yet. The hunk adds no new
  class of wait, and the arm's hung-run leg is the measurement for it. The PR
  comment explains this.
