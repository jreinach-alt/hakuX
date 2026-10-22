# p5swz1022: a swizzle-only #372 handoff is HAKUX_SWZKEEP's end state, already measured; no code change (#433)

State: draft

Lane: p5swz1022            Issue: #433 (0.5)
Base: master @ b944110629
Files: docs/lanes/p5swz1022/PR.md
Prediction: none: no code change. The proposed change (fps30 plan item P5: accept `held->swizzle !=
  target->swizzle` in `surface_handoff_partner`, carry `draw_dirty` and the generation over, schedule no download)
  leaves the binding, its VkImage, VRAM and the owed download in exactly the state `HAKUX_SWZKEEP=1` leaves them
  (sec 3). That state was measured on Blinx 2 (batch `bx2`, two off and two on arms, one APK): Surf 10.1/11.6 ->
  1.1/0.9 ms, `surfupd` fence lines 37 -> 0, fps +1.0 against +3.2 predicted, and the character-and-shadow region
  6.7/6.9 against an off-vs-off floor of 2.7, with an extra long shadow streak on both on arms
  (docs/lanes/fpsnext1019/NOTES.md 799-862). The P5 prediction (Surf 15-42 -> ~3 ms/flip, `[evict372] pair0` -> 0) is
  that measured P1 leg; the legs it does not predict are the two that failed.
Needs device: no
Needs NDK: no

## 1. Already tried

| commit | change | result | bearing on a swizzle-only handoff |
|---|---|---|---|
| bbbcf13845, e8cb544c98 | shelve evicted surfaces; keep the VkImage for a same-format rebind | on master | the shelf the eviction uses; `get_shelved_surface` (surface.c:3991-4008) compares address, VkFormat, role, width, height, pitch, not swizzle |
| 0c014f8fe8 | read back shelved surfaces before texture use | on master | a shelved draw-dirty surface still owes VRAM its pixels |
| 0b0e037f5e | upload an unshelved surface again when a download landed under it | on master | `vram_newer` (`surface_vram_written`, surface.c:1645-1656, excepts the downloading surface); `shelve_surface` resets it (surface.c:3980) |
| 9540a21f79 | `[evict372]` field census | on master | Blinx 2 gameplay: one pair, `m10 Z f130 ln p1024 256x256 b4 -> Z f130 sz p1024 256x256 b4`, 120 per 60 flips |
| 0f9735049c | #372 GPU handoff to a *different* shelved partner (`surface_handoff_partner` + `surface_handoff_record`) | on master | requires equal swizzle (surface.c:5418) and refuses a held binding the shelf would hand straight back (`surface_shelf_matches`, surface.c:5432); declines the Blinx 2 twin on both counts (docs/lanes/forza414/NOTES.md 489) |
| eedeeb3a81, c5dc70c577, 489394939f (merges d979c58234, 99bb40a200) | #372 zeta size flip 640x480 <-> 320x240 by image copy, quadrant copy, watch handover | on master | geometry changes, same swizzle; not this pair |
| 214445e90e | `[ovl1018]` overlap-eviction pair census | on master | overlap class, not twins |
| bb7c3bcbc3 | `HAKUX_SWZKEEP=1`: a swizzle-only re-mark under strict compatibility, TCG, no `mem_dirty`, no pending upload or download stays bound and draw-dirty; no eviction download | on master, opt-in (`swzkeep_on`, surface.c:3571-3581; rescue surface.c:5767-5772). Blinx 2 `bx2`: P1 mechanism holds, P2 fps +1.0 of +3.2, P3 pixels 6.7/6.9 vs floor 2.7, extra shadow streak; "does not ship" | the same end state as the proposed handoff (sec 3) |

## 2. Premise: swizzle is applied only between the VkImage and VRAM

Holds. The image always holds the unswizzled texel grid; `swizzle` selects the VRAM codec and nothing else.

- Synchronous download (`download_surface_to_buffer`): the GPU readback lands in a linear buffer at
  `guest_pitch = swizzle_linear_pitch(width, bpp)` when swizzled (surface.c:2779-2784), then `swizzle_rect` writes
  VRAM (surface.c:2786-2791). The compute path swizzles on the way out of the image the same way
  (`use_compute_to_swizzle`, surface.c:2334-2336, 2672); the CPU path's buffer is set up at surface.c:2391-2395.
- Deferred download: `download_surface_deferred` captures `dl->swizzle = surface->swizzle` when it records
  (surface.c:1568); completion applies it to the staging bytes (surface.c:1761-1774).
- Upload: `unswizzle_rect` reads VRAM into a linear buffer at `swizzle_linear_pitch` (surface.c:4712-4722), or the
  compute unswizzle does it on the GPU (`use_compute_to_unswizzle`, surface.c:4699-4701, 4950-5004), before the
  copy into the image.
- The implied pitch of a swizzled surface is `width * bpp` (`swizzle_linear_pitch`, surface.c:407-411). The Blinx 2
  pair has pitch 1024 = 256 x 4, so a pitch clause as specified would accept it.

## 3. Why the proposed handoff is not a different lever

The proposal rests on `HAKUX_SWZKEEP` having kept "two live surfaces for one range". In code it kept one, and so
does the baseline:

- **Baseline.** The eviction records the old binding's download in the linear layout and shelves it
  (surface.c:5876-5888); `shelve_surface` inserts at the shelf head and resets `vram_newer` (surface.c:3980-3981).
  The create path's `get_shelved_surface` (surface.c:5901) returns that same struct, `migrate_surface_image` moves
  its image into the target (surface.c:5904, 4339-4367), and `*surface = target` reuses the struct
  (surface.c:5960). `shelf_stale` is false and `mem_dirty` is false under TCG, so nothing uploads
  (surface.c:5991-6000; measured `evict[dl:120 unshelve:120 stale:0]`, `[edl] dl=120 upload=0 other=120`,
  docs/lanes/fpsnext1019/NOTES.md 620-641). One struct, one image, the target's swizzle, clean.
- **`HAKUX_SWZKEEP`.** The compatible-hit path keeps the bound struct (surface.c:5767-5772, 5799-5855,
  `should_create = false`), and `pgraph_vk_surface_update` stamps the target's swizzle on it after the upload step
  (surface.c:6371, 6385). One struct, one image, the target's swizzle, draw-dirty, VRAM not written, the download
  owed in the swizzled layout.
- **The proposed handoff.** One struct (old retired), one image (migrated), the target's swizzle, `draw_dirty` and
  generation carried, no download, no upload. Every field that decides pixels or VRAM matches `HAKUX_SWZKEEP`. What
  differs is struct identity, the texture-view retirement inside `migrate_surface_image` (surface.c:4343) and a
  `surface_list_gen` bump; none of them changes what a texture, a CPU access or a later download reads.

"Double shadow" in docs/lanes/fpsnext1019/NOTES.md 846-849 is the on-screen artifact (a second, elongated shadow
streak), not a second binding.

**What the image and VRAM hold.** Pixels drawn while the guest declares the range linear are, on hardware, in
VRAM in linear order. The baseline's eviction download writes exactly those bytes (the layout is captured at record
time, surface.c:1568). Both `HAKUX_SWZKEEP` and the proposed handoff skip it, so VRAM keeps the older bytes until
something takes the owed download, and that download writes the same pixels in swizzled order: a Morton
permutation of what hardware holds. A texture over the range that cannot take the image goes through
`pgraph_vk_surface_download_if_dirty` (texture.c:4093) and reads the permuted bytes. That is the reader the
`bx2` pixel leg points at; any lever that removes the linear-order download inherits it.

**Where the per-flip cost is.** Not an upload (above). `surface_update_may_defer_downloads` returns false whenever
the recorded batch has been submitted (`deferred_downloads_frame >= 0`, surface.c:6198-6201), so
`pgraph_vk_surface_update` completes it at the frame fence (surface.c:6333-6349; `download_surface_complete_deferred_at` reaches
`wait_frame_fence` at surface.c:2199-2203; `surfupd=fence61/dl120`, `dfF` 20.8-23.4 ms). A lever distinct from `HAKUX_SWZKEEP` keeps the
linear-order download and moves its completion off that wait (#474's fence path); it is outside this item.

## 4. Checks

- No source file changes, so no compile check applies (`git diff --stat b944110629` lists this file only).
- Selftest fragments naming the area (`grep -l -E "surface\.c|surface_handoff_partner|evict372|shelve"
  docs/testing/jobs/selftest.d/*.sh`): 65-status-objective.sh, 71-cloud-territory.sh, 86-nightly-notes.sh. All
  three use `surface.c` as a path string in board and notes fixtures; none exercises its code, and none reads
  this file. Not run.

## 5. Risks

- The equivalence in sec 3 is from code and from the `bx2` logs, not from a run of the proposed handoff. The two
  paths' struct identity and view retirement differ; a reader keyed on the struct pointer or on a texture slot's
  view would see the difference. None was found in surface.c or texture.c.
- The reader of the permuted bytes in Blinx 2's shadow pass is inferred from the mechanism, not identified by a
  capture.
