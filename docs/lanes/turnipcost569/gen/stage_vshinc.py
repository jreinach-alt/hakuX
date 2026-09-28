#!/usr/bin/env python3
"""Collect the vertex programs the catalogue uses into one directory.

    stage_vshinc.py <dest>

Four come from the nxdk test suites' own builds (the programs the pgraph and
vsh test discs load); skin4_a0 is assembled here from gen/skin4_a0.vsh.
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
dest = Path(sys.argv[1])
dest.mkdir(parents=True, exist_ok=True)
SRC = {
    "passthrough.vshinc": "/home/justin/nxdk_pgraph_tests/build-xbe/src/shaders",
    "projection_vertex_shader_no_lighting.vshinc": "/home/justin/nxdk_pgraph_tests/build-xbe/src/shaders",
    "fixed_function_approximation_shader.vshinc": "/home/justin/nxdk_pgraph_tests/build-xbe/src/shaders",
    "americas_army_shader.vshinc": "/home/justin/nxdk_vsh_tests/build-xbe/src/shaders",
}
for name, d in SRC.items():
    shutil.copy(Path(d) / name, dest / name)
subprocess.run([sys.executable, str(HERE / "assemble.py"), str(HERE / "skin4_a0.vsh"),
                str(dest / "skin4_a0.vshinc")], check=True)
for p in sorted(dest.iterdir()):
    print(p.name, p.stat().st_size)
