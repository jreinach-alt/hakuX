# lane.blinx372d: remove the two synchronous surface downloads in Blinx's attract demo (#372)

Base master a5b5b628f2 (includes PR #387, surfwatch382's watch suspension).
One source file: `hw/xbox/nv2a/pgraph/vk/surface.c`. PR #396.
Predecessor: lane.blinx372c (`docs/lanes/blinx372c/NOTES.md`), which found the site.

| commit | what |
|---|---|
| 9540a21f79 | `[evict372]` counter only: which compatibility field an incompatible eviction fails, and the most-repeated held -> target pairs. No behaviour change. |
| 0f9735049c | The GPU handoff (sec 2). The counter also prints `handoffs=` and `fallbacks=`. |
| c1704ee1f0 | Both predictions registered (sec 4). |

## 1. The counter (step 1 of the brief)

`[evict372]` prints beside `[surfwatch382]` every 5 s (tag `hakuX`, cumulative
since boot):

    [evict372] dirty/clean by mask (1role 2fmt 4pitch 8small 10swz 20ovl 40zdim): m03:N/M ... overflow= handoffs= fallbacks=
    [evict372] pairN n= mXX C f<vk> ln p<pitch> WxH b<bpp> -> Z f<vk> ln p<pitch> WxH b<bpp>

Each mask bit is tested on its own, so a mask with several bits means several
fields differ; it is not a "first failure". `dirty` counts evictions that took
the download (the Sd wait), and `clean` the ones that did not. The pair table
keeps 8 entries. When full it replaces the least-counted one, so boot-movie
pairs give way to the demo's.

**Result: pending.** Soak `1790432905-blinx372d-2396550` (ref 9540a21f79) is
queued on the Thor. Arm A of the A/B below carries the same counter.

### A correction to the brief's framing

"A pitch-only or size-only mismatch is a plain `vkCmdCopyImage`" is not so.
The old path moves the pixels *through VRAM*. The partner reads byte
`y * pitch_P + x * bpp` where the evicted binding wrote `y * pitch_X + x * bpp`.
So a pitch change re-maps pixels across rows, and it is not an image copy. A
size change also leaves the partner's pixels outside the evicted binding's
area coming from whatever VRAM held, and that need not be the partner's own
image. The cheap and exact case is **identical geometry**: same width, height,
pitch, swizzle and bytes per pixel, differing only in host format or role. The
download's staging bytes are then byte for byte what the upload would stage.
VRAM adds only the pitch padding (never read back) and the swizzle (the upload
undoes it). A role swap (colour and zeta) costs no more than a format change
in that case. The existing pack and unpack compute passes already do the
conversion, and the handoff reuses them. The hunk handles only this case, and
declines every other one to the old path.

## 2. The hunk (0f9735049c)

`update_surface_part`, incompatible branch. `surface_handoff_partner()` decides
at the eviction. `surface_handoff_record()` records the copy once the partner is
off the shelf:

    X image -> COMPUTE_DST (the download's regions)
      [X depth-stencil: pack COMPUTE_DST -> COMPUTE_SRC, the download's pass]
      [P depth-stencil: (copy to COMPUTE_DST) unpack -> COMPUTE_SRC, the upload's pass]
    -> P image (the upload's regions)

It uses global transfer/compute memory barriers between steps and no host
finish. There is no scratch image: at scale 1 the upload's scratch-to-image
step is a plain copy.

**Declined** (falls back to the unchanged download) when any of these holds:
surface scale is not 1; TCG is off (no watch exists); `mem_dirty`; the held
binding is not draw-dirty, or has `upload_pending` or `download_pending` (the
CPU asked for it); the geometry differs; a side's staged bytes are not its guest
bytes (colour host bpp != guest bpp, or depth-stencil with guest bpp != 4); the
held binding is the display pre-download's surface; the held binding itself
matches `get_shelved_surface`'s predicate (it would be the one taken back); no
shelved partner exists; another active binding overlaps the range; or a
draw-dirty shelved binding at another address overlaps it (`surface_put` would
write it back into VRAM before the old path's upload read it).

**Bookkeeping after a handoff:**
- The partner P is now the active binding. It gets `upload_pending = false`,
  and after `surface_put` a `draw_generation++` and
  `pgraph_vk_surface_watch_mark_dirty`. So it **owes the download**, and its
  watch is live.
- The evicted X is shelved with `draw_dirty = shelved_dirty = false`,
  `download_generation = draw_generation`, `vram_newer = true`, and its watch
  unregistered. It owes nothing, and it is stale. Whenever it is next wanted it
  is either handed P's pixels the same way, or re-uploaded from VRAM after P's
  download.

## 3. How the handoff interacts with surfwatch382's watch

The brief proposed "leave the shelved binding draw-dirty so the CPU copy happens
only if the CPU touches the memory". **The watch does not guard that.**
`surface_access_callback` walks only `r->surfaces` (active bindings) to set
`download_pending`. For shelved and invalid bindings it acts only on a *write*,
and it cancels their writeback (the bump-map fix). A guest *read* of a range
whose newest pixels sit in a shelved draw-dirty binding is not answered, so the
guest reads stale VRAM. Only the texture and overlap lookups
(`pgraph_vk_download_surfaces_in_range_if_dirty`, `invalidate_overlapping_surfaces`)
write back shelved-dirty bindings.

So the hunk moves the obligation to the **active** partner instead. P holds X's
bytes exactly, so P's download writes to VRAM what X's download would have
written. P is active and draw-dirty, so a guest CPU read or write traps and
downloads it first, the same as any drawn surface. The only difference from the
old path is *when* VRAM gets the bytes. Every exit of an active draw-dirty
binding writes it back:
- eviction: handoff or download;
- overlap invalidation: deferred download;
- expiry: download;
- texture range lookup: download;
- display pre-download: download.

Where it depends on surfwatch382:
- **Suspension.** A suspended watch is never on a draw-dirty surface, because
  `pgraph_vk_surface_watch_mark_dirty` re-arms it under `surface_watch_lock`.
  The handoff marks P dirty through that same call, not by setting the flag,
  so the invariant "the watch is live whenever a download is owed" holds for P.
  P's watch was freshly registered by `surface_put` a line earlier, so no
  re-arm or gap check fires in practice.
- **Gap check.** If a gap check from an earlier re-arm of P's address runs
  later, it finds `draw_dirty` and only counts `lost_writes`, as it does for a
  drawn surface.
- **Without TCG** there is no watch, so the handoff is declined.

Tested by: PR #387's own must-not-move suites (Texture_CPU_Update and
Texture_render_update_in_place) in the registered arm (sec 4), and by B's
`[surfwatch382] lost_writes=` in the demo soak.

## 4. Price (offline, a bound) and arms

**Price.** The handoff removes these per switch:
- one host finish (the Sd wait, in `Sub`);
- the host memcpy of the download;
- the host memcpy of the upload;
- two buffer copies: COMPUTE_SRC -> STAGING_DST and STAGING_SRC -> COMPUTE_DST;
- the scratch-to-image copy.

It adds nothing the old path's GPU did not already do: the same image-to-buffer
copy, the same pack and unpack passes, and one buffer-to-image copy. From
blinx372c's two master soaks, re-read by `abread.py`:

| run | Tot | Sub | GPU | gfps |
|---|---|---|---|---|
| 1790424874-blinx372c-754046 | 65.9 | 33.5 | 44.0 | 12.56 |
| 1790425369-blinx372c-1062368 | 71.1 | 35.2 | 46.0 | 12.36 |

With the waits gone the frame is GPU-bound at about 44-46 ms: 22-23 fps by Tot,
and about 18-19 by gfps (gfps runs at about 0.83 of 1000/Tot in A). That is a
ceiling, not a value.

**Arms (registered 14:39Z, before any device run of 0f9735049c):**
- `docs/testing/predictions/blinx372d-demo-ab.json`: the same-session Thor soak
  A/B, judged by `abread.py`. A `1790433606-blinx372d-2480701` (9540a21f79) and
  B `1790433607-blinx372d-2481219` (0f9735049c), frames every 30 s, queued back
  to back.
- `docs/testing/predictions/blinx372d-mnm.json`: the must-not-move arm, byte
  identity over Depth_buffer_fixed_function, Color_zeta_overlap,
  Surface_format, Texture_CPU_Update and Texture_render_update_in_place.
  Queued by the arms job. A pass with zero `handoffs=` across all five suites
  is inert, not a pass.

**Results: pending.**

## Tools

- `cc_surface.py`: syntax-checks `vk/surface.c` from this worktree with the
  desktop build's flags and `-Werror`, using
  `/home/justin/hakux-work/desktop/tree/build-linux/compile_commands.json`. A
  planted error returns rc=1. It is not a link, and not an Android build.
- `abread.py`: the A/B judge. It imports `blinx372c/stallread.py`, so both
  lanes read the demo the same way. `--selftest` passes. A dry run on
  blinx372c's two master soaks gives fps 12.56 against 12.36 (ratio 1.016).
  SURF92_LOG's plain `hakuX` tag is padded (`I/hakuX   (`), and stallread's
  timestamp regex does not match it. So abread keeps stallread's time zero and
  parses bodies with a regex that accepts the padding.

## Do not repeat

- Do not leave an owed download on a shelved binding and count on the watch to
  catch a CPU read. It catches reads only on active bindings (sec 3).
- Do not treat a pitch or size mismatch as an image copy (sec 1).
- `buffer.c` gives STAGING_DST only TRANSFER_DST and STAGING_SRC only
  TRANSFER_SRC. A GPU copy from the download's staging to the upload's staging
  is not allowed, which is why the handoff runs through the COMPUTE buffers.
