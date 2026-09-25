"""Predicted post-fix `differing` for every DBFF _ZB capture, two ways.

pure:  the fixed vertex z is exact RTZ and psh.c's floor is exact, so the
       new capture IS the silicon-model replay wherever the replay draws or
       clears; nothing else in a _ZB capture (no label in the zeta buffer).
delta: our capture plus (model - our-model), the conservative transfer.
"""
import os
import struct
import sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import price  # noqa: E402
import price_f16  # noqa: E402

run = sys.argv[1] if len(sys.argv) > 1 else "0-a-now-8e683b3a26-023-Depth_buffer_fixed_function"
names = sorted(f[:-4] for f in os.listdir(price.GOLD) if f.endswith("_ZB.png"))
for name in names:
    z16 = name.startswith("z16")
    fz = "_FZy_" in name
    cutoff = int(name.split("_M")[1].split("_")[0], 16)
    g = price.word(os.path.join(price.GOLD, name + ".png"), z16)
    o = price.word(os.path.join(price.RES, run, "captures1",
                                "Depth_buffer_fixed_function::%s.png" % name), z16)
    if fz and not z16:
        # z24 float: only the near-plane edge is drawn on silicon (stored 0);
        # the model's near z is exactly 0, so the edge draws 0; rest stays M.
        new = o.copy()
        new[53, 502:510] = 0
        new[56:72, 136] = 0
        zo_match = None
    elif fz:
        vp = struct.unpack("f", struct.pack("I", 0x43FFF800))[0]
        c22, c32 = price.consts(vp)
        zo = price_f16.render_f16(price.make_vz(c22, c32, False), cutoff)
        zs = price_f16.render_f16(price.make_vz(c22, c32, True), cutoff)
        new = zs
        zo_match = int((zo == o).sum())
    else:
        c22, c32 = price.consts(65535.0 if z16 else 16777215.0)
        zo, _ = price.render(price.make_vz(c22, c32, False), cutoff)
        zs, _ = price.render(price.make_vz(c22, c32, True), cutoff)
        new = zs
        zo_match = int((zo == o).sum())
        delta = o + (zs - zo)
    now = int((o != g).sum())
    pure = int((new != g).sum())
    dl = int((delta != g).sum()) if (not fz) else pure
    print("%-24s now %7d  after(pure) %7d  after(delta) %7d  replay-ours==capture %s" % (
        name, now, pure, dl, zo_match))
