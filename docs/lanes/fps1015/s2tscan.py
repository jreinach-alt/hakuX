#!/usr/bin/env python3
"""Render-to-texture reads in a frame dump (framedump_*.jsonl, schema 8):
which textures sample a surface the same frame drew into, and whether the
surface was bound directly (s2t=1) or refused, which costs a download of the
surface into VRAM and a CPU decode of it.

A read counts once per (frame, texture offset, surface draw generation): the
first enabled stage that reads the address after a draw into it. The refusal
reason is re-derived from check_surface_to_texture_compatiblity()'s order
(vk/texture.c): dim, levels/cube, pitch, swz, cvt, bpp. Usage:

    s2tscan.py FRAMEDUMP.jsonl [--frames N]
"""
import argparse
import collections
import json
import sys

# pgraph_texture_format_is_converted() (pgraph/texture.c), plus the 5551/565
# formats #59 widened to RGBA8 on the host
CONVERTED = {0x02, 0x03, 0x05, 0x10, 0x11, 0x1C,
             0x0B, 0x0C, 0x0E, 0x0F, 0x24, 0x25, 0x27}
# kelvin_color_format_info_map's linear column
LINEAR = {0x10, 0x11, 0x12, 0x13, 0x17, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20,
          0x24, 0x25, 0x2E, 0x2F, 0x30, 0x31, 0x35, 0x36, 0x3F, 0x40, 0x41}
TEXNAME = {0x02: 'SZ_A1R5G5B5', 0x03: 'SZ_X1R5G5B5', 0x05: 'SZ_R5G6B5',
           0x06: 'SZ_A8R8G8B8', 0x07: 'SZ_X8R8G8B8', 0x10: 'LU_A1R5G5B5',
           0x11: 'LU_R5G6B5', 0x12: 'LU_A8R8G8B8', 0x1C: 'LU_X1R5G5B5',
           0x1E: 'LU_X8R8G8B8', 0x2E: 'LU_DEPTH_X8_Y24_FIXED',
           0x2A: 'SZ_DEPTH_X8_Y24_FIXED', 0x30: 'LU_DEPTH_Y16_FIXED',
           0x2C: 'SZ_DEPTH_Y16_FIXED'}
SURFNAME = {1: 'X1R5G5B5_Z', 2: 'X1R5G5B5_O', 3: 'R5G6B5', 4: 'X8R8G8B8_Z',
            5: 'X8R8G8B8_O', 6: 'X1A7R8G8B8_Z', 7: 'X1A7R8G8B8_O',
            8: 'A8R8G8B8', 9: 'B8', 10: 'G8B8'}


def why(srf, tfmt_reg, ctl1):
    cfmt = (tfmt_reg >> 8) & 0xFF
    levels = (tfmt_reg >> 16) & 0xF
    cube = (tfmt_reg >> 2) & 1
    if cfmt in LINEAR:
        pitch = ctl1 >> 16
        tw = th = None
    else:
        pitch = None
        tw = 1 << ((tfmt_reg >> 20) & 0xF)
        th = 1 << ((tfmt_reg >> 24) & 0xF)
    if levels > 1:
        return 'levels'
    if tw is not None and (srf['w'], srf['h']) != (tw, th):
        return 'dim'
    if cube:
        return 'cube'
    if not srf.get('color', 1):
        return 'zeta'
    if not srf['swizzle'] and pitch is not None and srf['pitch'] != pitch:
        return 'pitch'
    if bool(srf['swizzle']) == (cfmt in LINEAR):
        return 'swz'
    if cfmt in CONVERTED:
        return 'cvt'
    return 'bpp/other'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dump')
    a = ap.parse_args()

    frames = set()
    per = collections.Counter()      # (s2t, why, srf fmt, tex fmt, wxh)
    per_frame = collections.Counter()
    drawn_gen = {}                    # color addr -> draw index of last draw
    read_gen = {}                     # (tex off) -> drawn gen last counted
    draws = 0
    with open(a.dump, errors='replace') as f:
        for line in f:
            try:
                o = json.loads(line)
            except ValueError:
                continue
            if o.get('t') != 'draw':
                continue
            draws += 1
            fr = o['f']
            frames.add(fr)
            for s in o.get('tex', []):
                if not s.get('en') or s.get('srf') is None:
                    continue
                off = int(s['off'], 16)
                g = drawn_gen.get(off)
                if g is None or read_gen.get(off) == g:
                    continue
                read_gen[off] = g
                srf = s['srf']
                reg = int(s['fmt'], 16)
                cfmt = (reg >> 8) & 0xFF
                w = 'ok' if s['s2t'] else why(srf, reg, int(s['ctl1'], 16))
                key = (s['s2t'], w, SURFNAME.get(srf['fmt'], srf['fmt']),
                       TEXNAME.get(cfmt, '0x%02x' % cfmt),
                       '%dx%d' % (srf['w'], srf['h']))
                per[key] += 1
                per_frame[(fr, s['s2t'])] += 1
            c = o.get('color')
            if c and c.get('addr'):
                drawn_gen[int(c['addr'], 16)] = draws

    nf = len(frames) or 1
    print('%d frames, %d draws' % (len(frames), draws))
    print('render-to-texture reads per frame: bound %.2f, refused %.2f'
          % (sum(v for (fr, b), v in per_frame.items() if b) / nf,
             sum(v for (fr, b), v in per_frame.items() if not b) / nf))
    print('%8s %4s %-9s %-13s %-22s %s' % ('per_frame', 's2t', 'why',
                                            'surface', 'texture', 'size'))
    for k, v in sorted(per.items(), key=lambda kv: -kv[1]):
        print('%8.2f %4d %-9s %-13s %-22s %s' % ((v / nf,) + k))


if __name__ == '__main__':
    sys.exit(main())
