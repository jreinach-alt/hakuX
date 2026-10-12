#!/usr/bin/env python3
"""Turnip's GMEM tile choice for one hakuX render pass on the Nova (Adreno 740),
re-done in Python from the fork the app ships (mesa-turnipfork):

  vulkan/tu_pass.cc  tu_render_pass_calc_gmem_pixels: one GMEM allocation per
                     attachment, a second cpp-1 one for D32_SFLOAT_S8_UINT's
                     separate stencil, and a cpp-1 allocation doubles
                     tile_align_w (96 -> 192) and halves the block alignment.
  vulkan/tu_util.cc  tu_tiling_config_update_tile_layout: walk every tile width
                     in steps of tile_align_w, keep the fewest tiles.
                     tu_tiling_config_update_binning: binning_useful only when
                     tiles > 2. With 2 tiles and no binning, each tile replays
                     the whole draw stream.
  common/fd6_gmem_cache.h, common/freedreno_devices.py: A740 = a7xx_gen2,
                     num_ccu 6, tile_align 96x32, 3 MiB GMEM, gmem CCU
                     fractions 1/8 (colour 64 KiB/CCU, depth 256 KiB/CCU).

hakuX's scene pass has at most two attachments (vk/draw.c create_render_pass):
colour (B8G8R8A8 / R5G6B5 ...) and zeta. Z24S8 maps to D32_SFLOAT_S8_UINT when
supported (vk/surface.c), else D24_UNORM_S8_UINT.

    python3 tilesim.py            # the table in NOTES.md section 5
    python3 tilesim.py 720 480 4 d32s8
"""
import sys

GMEM = 3 * 1024 * 1024
NUM_CCU = 6
TILE_ALIGN_W, TILE_ALIGN_H = 96, 32
TILE_MAX_W, TILE_MAX_H = 2016, 2032
COLOR_CCU_GMEM = NUM_CCU * 64 * 1024 // 8
DEPTH_CCU_GMEM = NUM_CCU * 256 * 1024 // 8

ZETA = {  # name -> list of (cpp, is_separate_stencil_plane)
    "d32s8": [4, 1],   # D32_SFLOAT_S8_UINT: att->cpp = 4, plus a cpp-1 stencil plane
    "d24s8": [4],      # D24_UNORM_S8_UINT: one cpp-4 plane
    "d16": [2],
    "none": [],
}


def gmem_pixels(colour_cpp, zeta, layout):
    """tu_render_pass_calc_gmem_pixels for one layout (FULL or AVOID_CCU)."""
    block_align_shift = 3
    tile_align_w = TILE_ALIGN_W
    allocs = []
    cpps = ([colour_cpp] if colour_cpp else []) + ZETA[zeta]
    for cpp in cpps:
        allocs.append(cpp)
        if cpp == 1 and tile_align_w % 64 != 0:
            tile_align_w *= 2
            block_align_shift -= 1
    gmem_align = (1 << block_align_shift) * tile_align_w * TILE_ALIGN_H
    size = GMEM
    if layout == "avoid_ccu":
        size = min(size, GMEM - COLOR_CCU_GMEM)
    blocks = size // gmem_align
    total = sum(allocs)
    pixels = None
    for cpp in allocs:
        align = max(1, cpp >> block_align_shift)
        nb = max((blocks * cpp // total) & ~(align - 1), align)
        if nb > blocks:
            return 0, tile_align_w
        blocks -= nb
        total -= cpp
        p = nb * gmem_align // cpp
        pixels = p if pixels is None else min(pixels, p)
    return pixels, tile_align_w


def align_npot(x, a):
    return (x + a - 1) // a * a


def tiles(w, h, colour_cpp, zeta, layout="full"):
    px, taw = gmem_pixels(colour_cpp, zeta, layout)
    if not px:
        return None
    best = None
    max_w = min(TILE_MAX_W, align_npot(w, taw))
    max_h = min(TILE_MAX_H, align_npot(h, TILE_ALIGN_H))
    tw = taw
    while tw <= max_w:
        th = min(px // tw, max_h)
        th -= th % TILE_ALIGN_H
        if th:
            cw = -(-w // tw)
            ch = -(-h // th)
            th2 = align_npot(-(-h // ch), TILE_ALIGN_H)
            n = cw * ch
            if best is None or n < best[0] or (n == best[0] and abs(tw - th2) < abs(best[1] - best[2])):
                best = (n, tw, th2, cw, ch)
        tw += taw
    n, tw, th, cw, ch = best
    return {"tiles": n, "tile": f"{tw}x{th}", "grid": f"{cw}x{ch}", "align_w": taw,
            "gmem_pixels": px, "binning": n > 2}


def main():
    if len(sys.argv) == 5:
        w, h, c, z = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
        for lay in ("full", "avoid_ccu"):
            print(lay, tiles(w, h, c, z, lay))
        return
    print("| pass (colour cpp) | zeta | layout | align_w | gmem px | tiles | grid | HW binning | per-tile work |")
    print("|---|---|---|---|---|---|---|---|---|")
    for (w, h) in ((640, 480), (720, 480), (1280, 720)):
        for c in (4, 2):
            for z in ("d32s8", "d24s8"):
                for lay in ("full", "avoid_ccu"):
                    t = tiles(w, h, c, z, lay)
                    work = "whole stream" if t["tiles"] == 1 else \
                        ("whole stream, x%d" % t["tiles"] if not t["binning"] else "binned")
                    print(f"| {w}x{h} ({c}) | {z} | {lay} | {t['align_w']} | {t['gmem_pixels']} | "
                          f"{t['tiles']} | {t['grid']} | {'yes' if t['binning'] else 'no'} | {work} |")


if __name__ == "__main__":
    main()
