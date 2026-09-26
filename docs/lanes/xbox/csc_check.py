# Exact integer check: is silicon's YUV Bump-map output the TEX1 checker texel
# passed through the NV2A YCbCr->RGB converter (hakuX util.h, fitted on the
# texture-format goldens)?
def clip(x): return 0 if x < 0 else 255 if x > 255 else x
def csc(Y, Cb, Cr, kr=127):
    c, d, e = Y - 16, Cb - 128, Cr - 128
    luma = (298 * c - 96) >> 8
    r = clip(luma + 2 * ((409 * e + kr) >> 9))
    g = clip(luma + 2 * ((-50 * d + 254) >> 8) + 2 * ((-104 * e + 248) >> 8) + 1)
    b = clip(luma + ((516 * d) >> 8))
    return r, g, b
def blend(rgb, a, clear=(32, 32, 32), clear_a=254):
    # hardware integer blend, SRC_ALPHA / ONE_MINUS_SRC_ALPHA; the Bump_map
    # goldens round half-alpha to nearest (bump_oracle.py gate 1)
    f = a / 255.0
    return tuple(int(round(s * f + d * (1 - f))) for s, d in zip(rgb, clear)) + (int(round(a * f + clear_a * (1 - f))),)
# checker texels, ARGB words 0xFF0000FE / 0x7F202122 -> (R,G,B,A)
tex = {"red": (0xFE, 0x00, 0x00, 0xFF), "grey": (0x22, 0x21, 0x20, 0x7F)}
gold = {"red": (72, 255, 18, 255), "grey": (16, 84, 16, 191)}
for kr in (127, 128):
    for order in ("Cb=G,Cr=B", "Cb=B,Cr=G"):
        out = {}
        for k, (R, G, B, A) in tex.items():
            cb, cr = (G, B) if order.startswith("Cb=G") else (B, G)
            rgb = csc(R, cb, cr, kr)
            out[k] = (rgb, blend(rgb, A))
        ok = all(out[k][1] == gold[k] for k in tex)
        print("kr=%d %s  red->%s %s  grey->%s %s  %s" % (kr, order, out["red"][0], out["red"][1], out["grey"][0], out["grey"][1], "MATCH" if ok else "no"))
# where do kr=127 and kr=128 differ? Compare the red term itself, unclipped:
# a clipped channel would hide the difference.
diff = [cr for cr in range(256) if (409 * (cr - 128) + 127) >> 9 != (409 * (cr - 128) + 128) >> 9]
print("Cr values where the red term differs between kr 127 and 128:", diff)
# alternative: Y from A, or from other bytes
for name, (Y, cb, cr) in {"Y=A(255)": (255, 0, 0), "Y=R(254)": (254, 0, 0)}.items():
    print(name, [csc(Y, cb, cr, k) for k in (127, 128)])
