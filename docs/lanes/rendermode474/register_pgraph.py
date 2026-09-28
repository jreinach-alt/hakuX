#!/usr/bin/env python3
"""Register rendermode474-pgraph.json (run once, from the worktree root)."""
import subprocess
import sys

SUITES = ("3D_primitive Antialiasing_tests Attrib_float Blend_surface Blend_tests Clear "
          "Color_mask_blend Color_zeta_overlap Depth_buffer Fog_gen Image_blit "
          "Lighting_spotlight Specular Stencil Stencil_func Surface_clip Surface_format "
          "Surface_pitch Texture_CPU_Update Texture_DXT Texture_Framebuffer_Blit "
          "Texture_format Texture_render_target Texture_render_update_in_place "
          "Vertex_shader_rounding_tests Window_clip ZPass_pixel_count").split()

PREDICTION = (
    "#474: b_ref adds a per-title render mode. TU_DEBUG=sysmem is set only when the "
    "disc's default.xbe title ID is 4541000D (AUF) or 54430006 (DOA 1 Ultimate), or a "
    "per-game render_mode says so. A pgraph disc is neither and no per-game value is "
    "set, so B leaves TU_DEBUG unset like A, and every capture is byte-identical within "
    "the run-to-run band flip474 measured (Stencil REPLACE/ZERO, Blend spot_0_ADD, "
    "GeometrySuperscreen). ZPass_pixel_count discriminates: it prints 40960 under GMEM "
    "and 65536 under sysmem (flip474-sysmem-pgraph.json), so a B that engaged sysmem on "
    "a pgraph disc moves all 36 ZPass captures. Hand-read leg: B's logcat has one "
    "hakuX-build line 'render_mode: auto (default) title=<the disc's id> "
    "TU_DEBUG=(unset)'; KILL of that leg: 'sysmem' on the line, or no line.")

cmd = [sys.executable, "docs/testing/ab_compare.py",
       "--register", "docs/testing/predictions/rendermode474-pgraph.json",
       "--who", "lane.rendermode474", "--issue", "474",
       "--a-ref", "59d478911ec90f379efe789377b90963aef82a59",
       "--b-ref", "61e0edf87c6a95f555c6a000dfcfae2eec4b805e",
       "--disc-suites", ",".join(SUITES),
       "--disc-skip-tests", "Texture_render_target::RenderTextureLoop",
       "--prediction", PREDICTION]
for s in SUITES:
    cmd += ["--must-not-move", s + "/*"]
sys.exit(subprocess.call(cmd))
