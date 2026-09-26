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

**Result (soak `0-0-y-1790433000-1790432905-blinx372d-2396550`, ref
9540a21f79, Thor, 240 s; the last print, cumulative since boot):**

    m08:993/0 m10:14/0 m40:993/0 overflow=0
    pair4 n=993 m40 Z f130 ln p2560 640x480 b4 -> Z f130 ln p2560 320x240 b4
    pair5 n=993 m08 Z f130 ln p2560 320x240 b4 -> Z f130 ln p2560 640x480 b4

The demo's two evictions are **one zeta surface at one address changing
size**: D24S8 (vk 130), linear, pitch 2560, 4 bytes per pixel, 640x480 <->
320x240. The role, format, pitch and swizzle are the same. Only the size
differs, and each direction is one of the two waits. The `m10` rows (6+6+1+1,
swizzle only) are boot-movie pairs, 14 in total, and not the demo. Both A/B
arms print the same two pairs (A: n=710, B: n=866).

So the demo's branch is **size-only at equal pitch**. The hunk in sec 2
handles identical geometry only, and it declines this case by design (see the
correction below and sec 5).

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

**Results.**

Demo A/B, `abread.py` over 135-265 s. A is
`0-0-y-1790433000-1790433606-blinx372d-2480701` (9540a21f79) and B is
`-1790433607-blinx372d-2481219` (0f9735049c), back to back on the Thor:

| arm | stall lines | sd/frame | Tot | Sub | GPU | fps | handoffs/frame |
|---|---|---|---|---|---|---|---|
| A | 23 | 1.04 | 56.6 | 25.6 | 31.4 | 12.98 | (not printed) |
| B | 23 | 1.28 | 62.9 | 31.6 | 40.5 | 12.25 | **0.0** |

Verdict **VOID**, and the hunk is **inert on the demo**. B logged
`handoffs=0 fallbacks=0` because every demo eviction is the size flip from
sec 1, and `surface_handoff_partner()` declines geometry changes before it
counts a fallback. The two arms therefore ran the same path. Their
differences in fps (0.943), sd/frame and the ms columns are run-to-run noise
on one path, not an effect. Two reader notes:
- `M1/A_evict372_live` FAILs because abread's line regex wants the
  `handoffs=` field, and 9540a21f79 does not print it. That leg is a reader
  limit, not a dead counter: the counter soak above is the same ref and
  printed.
- sd/frame came in at 1.0-1.3 here, not the brief's 2.0. The window catches
  some non-demo frames.

Must-not-move arm, `blinx372d-mnm.json`, pair
`0-0-x-1790434483-arms-blinx372d-base-2755805` / `-fix-2755972`: **PASS, not
inert.**
- All 102 rows are byte-identical in `differing`, `max_rgb`, `max_a`,
  `pixels` and `off_by_one`.
- B's logcat reads `handoffs=2 fallbacks=0`, so the handoff ran in these
  suites and changed no byte.
- Two rows, `Depth_buffer_fixed_function/z16_Cn_FZy_M00ffff` and
  `z16_Cy_FZy_M00ffff`, are `white-content` (unreadable) in both arms, with
  identical values. They are not passes, and the Z16 flips are declined anyway
  (bpp differs).

### Why attempt 1 did not finish

It ended correctly, on a `waiting:` comment. The three Thor soaks were about
22 requests deep in the queue, and the `[job.arms]` pair had not run.
`jobs/handback.sh` resumed this lane once all of them were DONE (19:15Z).
Nothing failed.

### Attempt 2 (2026-09-26, 12:20-12:40 PDT)

- Read the four results above.
- Merged origin/master 9f5a3dfc98 into the lane with no rebase, as
  790dc14730. It was a clean merge: master's vk changes since a5b5b628f2 are
  all in `draw.c`. `cc_surface.py` rc=0.
- Re-registered the must-not-move arm on the merged refs as
  `blinx372d-mnm2.json`: A 9f5a3dfc98 (plain master), B 790dc14730. The arms
  job queues it.
- Did not re-register the demo A/B. On the demo this PR's code runs the same
  path as master, and a second hand-read soak pair would measure noise.

## 5. The demo's case: a same-pitch size flip (next lane, not this PR)

Not implemented here. The resume brief said not to extend this PR, and #303
is waiting for `vk/surface.c`. What the counter says the next hunk must do:

Pixel (x, y) sits at `y*2560 + x*4` in both bindings, so the 320x240 binding
is exactly the top-left quadrant of the 640x480 one in VRAM. A GPU region
copy (`vkCmdCopyImage`, same format D24S8, depth and stencil aspects) of the
quadrant is exact **for the quadrant**. The part that is hard is the rest of
the big binding:
- **Small -> big (X=320x240 evicted, P=640x480 unshelved).** The old path
  downloads X and then re-uploads all of P from VRAM. The quadrant copy X ->
  P is exact if P's own image outside the quadrant still equals VRAM there.
  That holds when P was written back on its own eviction, as it is today. It
  fails if the guest CPU wrote that range while P sat shelved. `vram_newer`
  (`surface_vram_written`, surface.c:848) is set only when a *download* is
  recorded over a shelved binding, never on a guest CPU write. A clean
  shelved binding sheds its watch
  (`unregister_cpu_access_callback_if_clean`), so nothing sees that write.
  Master's same-format rebind (`shelf_stale = surface->vram_newer`) already
  has this exposure. A quadrant handoff would widen it from same-format
  rebinds to size flips. Measure or close it first.
- **Big -> small (X=640x480 evicted, P=320x240).** Copying the quadrant to P
  is exact. But X still owes the other three quadrants to VRAM, and a
  shelved binding's owed download is not guarded by the watch (sec 3). Keep
  this direction on the old path, or make X's download deferred but not
  waited on: record it, complete it at the next natural finish, and have the
  watch answer a shelved binding with a pending download. The second option
  is a watch change, and it is PR #387's territory.

A first step that is safe by this reading is **small -> big only** (one wait
per frame, sd/frame about 1 fewer). It needs the CPU-write gap above closed or
measured first. It
bounds the gain at about half of the Sub the two waits cost. That is a
bound, and it has not been measured. The must-not-move set to add is every
capture that binds zeta at two sizes at one address. Grep the nxdk tests for
`set_surface_clip` with a changed size between draws, and name them before
registering.

### Waiting (2026-09-26 07:50 PDT, attempt 1; resolved)

The session ended waiting on the three Thor soaks above. About 22 Thor-pinned
requests (hotfix041 and titleplay, priority 0-0-y) were ahead of them, roughly
2.5-3 h. It is also waiting on the arms job's `[job.arms]` verdict for
`blinx372d-mnm.json`. On resume:
1. Read `[evict372]` in `1790432905`'s logcat over 135-265 s, and record the
   mask and top pair in sec 1.
2. Run `abread.py` on A/B: `--spec-a`/`--spec-b` from each result.json and
   `--prediction` the demo JSON. Look at B's frames by eye.
3. Read B's `handoffs=` in the must-not-move arm's logcat before calling its
   pass anything but inert.
4. Merge master (no rebase), re-register on the new refs, re-run the arm, and
   mark ready.

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
