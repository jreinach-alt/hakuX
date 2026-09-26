#!/bin/bash
# Registers lane.tiecode282's prediction.  Run from the repository root.
set -e
cd "$(git rev-parse --show-toplevel)"

A=7a2036020d   # master, the lane's base
B=18dc4f11e2   # the rule + the PROJECT3D bias

read -r -d '' PRED <<'EOT' || true
#282 / #283: silicon's v-tie direction, on the one configuration it was measured on (fixed function, smooth, Vulkan; triangle UL, UR, LR of an axis-aligned right triangle; equal w; v constant along v0-v1 and rising to v2): down iff l2 <= 1/2 and not (l0 in (1/4,1/2] and l2 in (1/4,1/2]); every other draw keeps today's up. PROJECT3D on a 3D texture also takes the bias (u up, v per the rule).

MUST MOVE (exact): Volume_texture/Y16 = 0. vol283r's pixel-exact model with this rule reproduces the golden Y16 frame with 0 of 75,840 quad px differing; every one of Y16's 2,605 differing px is an exact v tie. The PROJECT3D bias alone (always up) predicts 2,070, and the rule reaching nothing predicts 2,605, so this leg fails if the rule is inert on the 3D path. Texture_render_target/TexFmt_A8R8G8B8 = 0: its residual on the full-disc run 1790359589 was 71 px, max_rgb 1, which is row 240's columns 392-462 exactly (tie282c: silicon down there, we up). It fails if the rule is inert on the 2D path, or if the composition (RenderTextureLoop skipped) does not reproduce that baseline.

MUST NOT REGRESS (improvement expected, not asserted per capture): the nine checkerboard suites (FF captures improve; the VS-drawn ones, Lighting_control VS_* and the Specular *VS* tests, are outside the gate and should not move), all of Texture_render_target (the other full-gradient TexFmt_* captures should go to 0 as A8R8G8B8 does; the 5/6-bit ones observe no column and should not move) and all of Volume_texture (Y16 and R16B16 go down by at least 535 and 275, the PROJECT3D bias's share; the others toward 0; R5G6B5 and X1R5G5B5 stay 0).

MUST NOT MOVE: Texture_BRDF, Texture_format, Texture_DXT, Texture_signed_component_tests, Texture_Matrix, Texture_perspective, Texture_palette, Texture_3D_as_2D, Texture_2D_as_cubemap, Pixel_shader, Point_params, Bump_env_lum and Texture_border/3D_BorderTex_SZ_* (VS draws, which vol283r measured all up; the PROJECT3D bias must leave them at 0). A must-not-move capture that moves, either way, means the configuration test reaches a draw the evidence does not cover: that refutes the scoping, not the rule, and the hunk gets narrowed, not the leg.

Open and not tested by this arm: vertex roles other than (UL, UR, LR), projective interpolation, VS draws with the same vertices, and the GL renderer. One known miss inside the configuration: checkerboard row 240, x = 480 (l0 = 1/4, l2 = 1/2 exactly) is up on silicon and down by the rule, 3 px over 3 captures; the rule is implemented as published, not patched for that point.
EOT

python3 docs/testing/ab_compare.py --register docs/testing/predictions/tiecode282-binade.json \
    --who lane.tiecode282 --issue 282 --a-ref "$A" --b-ref "$B" \
    --prediction "$PRED" \
    --expect-value 'Volume_texture/Y16=0' \
    --expect-value 'Texture_render_target/TexFmt_A8R8G8B8=0' \
    --must-not-move 'Texture_BRDF/*' \
    --must-not-move 'Texture_format/*' \
    --must-not-move 'Texture_DXT/*' \
    --must-not-move 'Texture_signed_component_tests/*' \
    --must-not-move 'Texture_Matrix/*' \
    --must-not-move 'Texture_perspective/*' \
    --must-not-move 'Texture_palette/*' \
    --must-not-move 'Texture_3D_as_2D/*' \
    --must-not-move 'Texture_2D_as_cubemap/*' \
    --must-not-move 'Pixel_shader/*' \
    --must-not-move 'Point_params/*' \
    --must-not-move 'Bump_env_lum/*' \
    --must-not-move 'Texture_border/3D_BorderTex_SZ_*' \
    --disc-suites 'Lighting spotlight,Lighting accumulation,Material color source,Lighting control,Specular,Specular back,Texture border color,Combiner,Lighting range,Texture render target,Volume texture,Texture BRDF,Texture border,Texture format,Texture DXT,Texture signed component tests,Texture Matrix,Texture perspective,Texture palette,Texture 3D as 2D,Texture 2D as cubemap,Pixel shader,Point params,Bump env lum' \
    --disc-skip-tests 'Texture render target::RenderTextureLoop' \
    "$@"

# must_not_regress has no command-line flag; add it to the file just written,
# parsed and checked in memory before it is written back.
python3 - <<'EOP'
import json
p = "docs/testing/predictions/tiecode282-binade.json"
exp = json.load(open(p))
exp["must_not_regress"] = [
    "Lighting_spotlight/*", "Lighting_accumulation/*",
    "Material_color_source/*", "Lighting_control/*", "Specular/*",
    "Specular_back/*", "Texture_border_color/*", "Combiner/*",
    "Lighting_range/*", "Texture_render_target/*", "Volume_texture/*",
]
text = json.dumps(exp, indent=2) + "\n"
assert json.loads(text) == exp
open(p, "w").write(text)
print("must_not_regress:", len(exp["must_not_regress"]), "globs")
EOP
