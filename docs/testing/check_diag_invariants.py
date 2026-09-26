#!/usr/bin/env python3
"""Check cross-field invariants over a diagnostic capture session.

A per-field measurement could not find Galleon's flashing surfaces, because
every field was individually stable. So the acceptance test for any fix is not
a frame someone looks at; it is a relationship between fields, checked over a
capture:

    check_diag_invariants.py <diag_session.json> [more.json ...]

Exits non-zero if any invariant fails, so it can gate a change.

THE FIRST VERSION OF THIS FILE CHECKED A FITTED CONSTANT, and it is kept
described here because the failure is instructive and the number is quoted in
`docs/investigations/galleon-flashing-deck.md`.

It checked `stage1 matrix u-scale * stage1 texture width == 2048`, "detail
texels across the surface", and reported 166 of 167 draws passing with one
violation -- session 4122, frame 4122, draw 92, scale 8 with a 128-wide
texture. That violation was published as the defect found in the act.

2048 rests on two observed pairings, 8 with a 256-wide texture and 16 with a
128-wide one. Draw 92 is the ONLY draw in the corpus whose stage-0 base
texture is 128 wide rather than 256 -- every other one of the 167 has a
256x256 BC1 base. So draw 92 is the only observation in the corpus capable of
distinguishing 2048 from a rule expressed relative to the base texture, and it
distinguishes them against 2048:

    scale * stage1_width                     2048 on 166, 1024 on 1
    scale * stage1_width / stage0_width         8 on 167, no exception

Stage 0 carries `matrix_enable = false` and row 0 `[1, ...]` on all 167 draws,
so stage-0 coordinates are the mesh's own UVs: `stage0_width` base texels and
`scale * stage1_width` detail texels span the same UV unit, and their ratio is
detail texels per base texel. It is 8.000 on every draw including draw 92,
which is what a detail texture holding a fixed density RELATIVE TO THE BASE
MAP looks like. 2048 is that same rule specialised to the 256-wide base the
other 166 draws happen to use.

Which of the two the game intends is not decidable from 167 draws. But a gate
must not fail on the only draw that separates them, so the gate is the rule
with no exception, and the fitted one is reported alongside it as an
observation.
"""
import json
import sys

# Detail texels per base texel: (stage-1 u-scale * stage-1 width) / stage-0
# width. Observed at exactly 8 on 167 of 167 stage-1 draws across four
# sessions, with no exception. This is the gate.
STAGE1_DETAIL_PER_BASE = 8.0

# Detail texels across the surface: stage-1 u-scale * stage-1 width. Observed
# at 2048 on 166 of 167, with draw 92 at 1024 -- and draw 92 is the only draw
# whose base texture is not 256 wide. Reported, never gated on.
STAGE1_DETAIL_TEXELS = 2048


def check(path):
    with open(path) as fh:
        session = json.load(fh)

    checked = 0
    failures = []
    fitted_exceptions = []
    for frame in session.get("frames", []):
        for draw in (frame.get("draw_calls") or []):
            stages = {t.get("stage"): t for t in draw.get("textures", [])}
            tex = stages.get(1)
            base = stages.get(0)
            if tex is None or base is None:
                continue
            if not (tex.get("enabled") and tex.get("matrix_enable")):
                continue
            if not base.get("enabled"):
                continue
            scale = tex["matrix"][0]
            detail = scale * tex["width"]
            ratio = detail / base["width"]
            checked += 1
            row = (frame["frame_number"], draw["draw_index"], scale,
                   tex["width"], base["width"], detail, ratio,
                   draw.get("color_image"))
            if abs(ratio - STAGE1_DETAIL_PER_BASE) > 0.01:
                failures.append(row)
            if abs(detail - STAGE1_DETAIL_TEXELS) > 1:
                fitted_exceptions.append(row)
    return checked, failures, fitted_exceptions


def show(rows, label):
    for fnum, didx, scale, w1, w0, detail, ratio, image in rows:
        print(f"  {label} frame {fnum} draw {didx}: scale {scale} with a "
              f"{w1}-wide detail texture over a {w0}-wide base = "
              f"{detail:.0f} detail texels, {ratio:.3f} per base texel")
        if image:
            print(f"      framebuffer after that draw: {image}")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    total = 0
    bad = []
    fitted = []
    for path in sys.argv[1:]:
        checked, failures, exceptions = check(path)
        total += checked
        bad += [(path,) + f for f in failures]
        fitted += [(path,) + f for f in exceptions]
        print(f"{path}: {checked} stage-1 draws checked, "
              f"{len(failures)} failed")

    print(f"\n{total} draws checked, {len(bad)} violating "
          f"detail-per-base-texel == {STAGE1_DETAIL_PER_BASE}")
    show([r[1:] for r in bad], "FAIL")

    print(f"\nobservation only, NOT a gate: {len(fitted)} of {total} draws "
          f"depart from the fitted {STAGE1_DETAIL_TEXELS}-detail-texel rule")
    show([r[1:] for r in fitted], "fitted-rule exception")
    if fitted and not bad:
        print("  -- every one of these has a base texture that is not 256 "
              "wide, which is what the fitted rule assumed. Not a defect.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
