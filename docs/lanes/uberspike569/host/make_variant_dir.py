#!/usr/bin/env python3
"""Build a render_check input dir whose ubershaders are a variant's rewrite.

    make_variant_dir.py SHADER_DIR OUT_DIR v1|v3
"""
import os
import shutil
import subprocess
import sys

src, dst, var = sys.argv[1:4]
here = os.path.dirname(os.path.abspath(__file__))
os.makedirs(dst, exist_ok=True)
for f in sorted(os.listdir(src)):
    p = os.path.join(src, f)
    if f.startswith("uber_") and f.endswith(".frag"):
        subprocess.run([sys.executable, os.path.join(here, "variant_%s.py" % var),
                        p, os.path.join(dst, f)], check=True)
    elif f.startswith(("spec_", "comb_")) or f == "manifest.txt":
        shutil.copy(p, os.path.join(dst, f))
