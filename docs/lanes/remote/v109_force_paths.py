#!/usr/bin/env python3
"""Force swizzled surface transfers through vk/surface.c's CPU paths (#109).

    v109_force_paths.py            # apply to hw/xbox/nv2a/pgraph/vk/surface.c
    git checkout -- hw/xbox/nv2a/pgraph/vk/surface.c   # take it out again

NOT FOR COMMIT INTO THE EMULATOR. This edits a working tree so the forced arms
of #109's Vulkan half can be re-run; build, run, then revert and rebuild.

No disc in the corpus takes an undersized-pitch swizzled surface through the
three CPU sites that #109's Vulkan fix changes (the deferred download's
completion, and the synchronous download's and the upload's CPU branches):
Surface_pitch::Swizzle's target 3, the only such surface, is 4-byte and takes
the compute paths. The edits add a V109_FORCE switch that is inert unless set:

  V109_FORCE=sync    the synchronous download swizzles on the CPU
  V109_FORCE=upload  the upload unswizzles on the CPU
  V109_FORCE=defer   the download goes through the deferred recorder and is
                     completed at once

Each forced transfer of an undersized-pitch surface logs a [v109f] line on
stderr. The replacements are exact-string, so they apply to master and to the
fix alike, and fail loudly once the code they anchor on changes.

Used on #109 (lane.remote, 2026-09-25): on master, disc109, Swizzle's q3 read
4,032 / 6,144 / 4,034 under sync / upload / defer (0 unforced), and 0 in every
mode with the fix (predictions/remote-109-vk-forced-*.json).
"""
p = "hw/xbox/nv2a/pgraph/vk/surface.c"
t = open(p).read()
anchor = "static bool check_surface_overlaps_range(const SurfaceBinding *surface,"
helper = """/* v109 LOCAL FORCING -- NOT FOR COMMIT: route swizzled transfers through
 * the CPU paths so #109's stride defect can be seen on a real capture. */
static bool v109_force(const char *mode, const SurfaceBinding *s, const char *site)
{
    const char *e = getenv("V109_FORCE");
    bool on = e && !strcmp(e, mode) && s->swizzle;
    if (on && s->pitch < s->width * s->fmt.bytes_per_pixel) {
        fprintf(stderr, "[v109f] %s addr=%08x w=%u h=%u pitch=%u bpp=%u\\n", site,
                (unsigned)s->vram_addr, s->width, s->height, s->pitch,
                s->fmt.bytes_per_pixel);
    }
    return on;
}

"""
assert t.count(anchor) == 1
t = t.replace(anchor, helper + anchor)
old1 = """    bool use_compute_to_swizzle = surface->swizzle &&
                                   surface->fmt.bytes_per_pixel == 4 &&
                                   !use_compute_to_convert_depth_stencil_format;"""
new1 = """    bool use_compute_to_swizzle = surface->swizzle &&
                                   surface->fmt.bytes_per_pixel == 4 &&
                                   !use_compute_to_convert_depth_stencil_format &&
                                   !v109_force("sync", surface, "sync-cpu-download");"""
assert t.count(old1) == 1; t = t.replace(old1, new1)
old2 = """    bool use_compute_to_unswizzle = surface->swizzle &&
                                     surface->fmt.bytes_per_pixel == 4 &&
                                     !use_compute_to_convert_depth_stencil_format;"""
new2 = """    bool use_compute_to_unswizzle = surface->swizzle &&
                                     surface->fmt.bytes_per_pixel == 4 &&
                                     !use_compute_to_convert_depth_stencil_format &&
                                     !v109_force("upload", surface, "cpu-upload");"""
assert t.count(old2) == 1; t = t.replace(old2, new2)
old3 = """    bool was_partial = surface->download_row_count > 0 &&
                       surface->download_row_count < surface->height;

    download_surface_to_buffer(d, surface, d->vram_ptr + surface->vram_addr);
"""
new3 = """    bool was_partial = surface->download_row_count > 0 &&
                       surface->download_row_count < surface->height;

    if (v109_force("defer", surface, "deferred-download") &&
        download_surface_record_deferred(d, surface,
                                         d->vram_ptr + surface->vram_addr)) {
        pgraph_vk_download_surface_complete_deferred(d); /* v109 LOCAL FORCING */
        return;
    }

    download_surface_to_buffer(d, surface, d->vram_ptr + surface->vram_addr);
"""
assert t.count(old3) == 1; t = t.replace(old3, new3)
open(p, "w").write(t)
print("forcing applied")
