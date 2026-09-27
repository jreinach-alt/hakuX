#!/usr/bin/env python3
"""Register docs/testing/predictions/notify488-pgraph.json with ab_compare.py.
Run once, before any device run."""
import subprocess
import sys

SUITES = ["3D_primitive", "Attrib_float", "Blend_tests", "Depth_buffer",
          "Fog_gen", "Lighting_spotlight", "Specular", "Surface_clip",
          "Texture_CPU_Update", "Texture_DXT", "Texture_format",
          "Vertex_shader_rounding_tests", "ZPass_pixel_count"]
PRED = (
    "#488: the whole lane change against a master-equivalent A on the pgraph "
    "suite, Nova (Vulkan). A = dffb7a8a66 (master db8cc66396 plus a "
    "perflog-only counter, compiled out here, and the NV097_NOTIFY define). "
    "B = 9f80bc887a adds the NV097 NOTIFY handler and the semaphore release "
    "that records queued draws instead of downloading the bound surfaces "
    "(under TCG on Vulkan, and not after a GET_REPORT). Every capture is "
    "identical. Why: pbkit and the harness never send NV097 NOTIFY, and only "
    "Texture_CPU_Update and ZPass_pixel_count send "
    "BACK_END_WRITE_SEMAPHORE_RELEASE; captures are read back by a CPU "
    "memcpy (hakuX has no M2MF, so gpu_m2m falls back), which goes through "
    "the surface watch that B now relies on. ZPass_pixel_count exercises the "
    "GET_REPORT guard: without it the reports would be read before the "
    "finish writes them, and its captures would move. What this cannot see: "
    "a guest that reads a surface shelved while dirty after a release (no "
    "suite test does), and the notifier contents (the timing arm reads "
    "those). The other eleven suites are lane.flip474's readback-heavy set; "
    "they carry no semaphore and show the change leaves the common path "
    "alone.")

cmd = [sys.executable, 'docs/testing/ab_compare.py',
       '--register', 'docs/testing/predictions/notify488-pgraph.json',
       '--who', 'lane.notify488', '--issue', '488',
       '--a-ref', 'dffb7a8a660e1fc367dbb27ee0c30a17b1f8269b',
       '--b-ref', '9f80bc887aee554dec249e2c3978853faec3f44d',
       '--disc-suites', ','.join(SUITES), '--prediction', PRED]
for s in SUITES:
    cmd += ['--must-not-move', s + '/*']
sys.exit(subprocess.call(cmd))
