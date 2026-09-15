#!/usr/bin/env python3
"""Check cross-field invariants over a diagnostic capture session.

A per-field measurement could not find Galleon's flashing surfaces, because
every field was individually stable. The defect was in the *relationship*
between two of them: stage 1's detail-texture matrix scale is paired with that
texture's width to hold detail density constant, and one draw in 167 had the
scale for a 256-wide texture while a 128-wide one was bound. Brighter, coarser
stone, for one frame.

So the acceptance test for any fix is not a frame someone looks at. It is this,
run over a capture: does every draw satisfy the pairing?

    check_diag_invariants.py <diag_session.json> [more.json ...]

Exits non-zero if any invariant fails, so it can gate a change.
"""
import json
import sys

# Product of stage-1 matrix u-scale and texture width, i.e. detail texels
# across the surface. Observed at 2048 on 166 of 167 draws.
STAGE1_DETAIL_TEXELS = 2048


def check(path):
    with open(path) as fh:
        session = json.load(fh)

    checked = 0
    failures = []
    for frame in session.get("frames", []):
        for draw in (frame.get("draw_calls") or []):
            for tex in draw.get("textures", []):
                if tex.get("stage") != 1:
                    continue
                if not (tex.get("enabled") and tex.get("matrix_enable")):
                    continue
                scale = tex["matrix"][0]
                product = scale * tex["width"]
                checked += 1
                if abs(product - STAGE1_DETAIL_TEXELS) > 1:
                    failures.append(
                        (frame["frame_number"], draw["draw_index"], scale,
                         tex["width"], product, draw.get("color_image")))
    return checked, failures


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    total = 0
    bad = []
    for path in sys.argv[1:]:
        checked, failures = check(path)
        total += checked
        bad += [(path,) + f for f in failures]
        print(f"{path}: {checked} stage-1 draws checked, {len(failures)} failed")

    print(f"\n{total} draws checked, {len(bad)} violating the pairing")
    for path, fnum, didx, scale, width, product, image in bad:
        print(f"  {path} frame {fnum} draw {didx}: "
              f"scale {scale} with a {width}-wide texture = {product:.0f} "
              f"detail texels, expected {STAGE1_DETAIL_TEXELS}")
        if image:
            print(f"      framebuffer after that draw: {image}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
