#!/usr/bin/env python3
"""Assemble a .vsh with nv2avsh (the nv2a-venv tool nxdk's build uses) into a
.vshinc token list, the same format nxdk_pgraph_tests' build writes."""
import subprocess
import sys

NV2AVSH = "/home/justin/.local/nv2a-venv/bin/nv2avsh"
src, out = sys.argv[1], sys.argv[2]
r = subprocess.run([NV2AVSH, src, out], capture_output=True, text=True)
sys.stdout.write(r.stdout)
sys.stderr.write(r.stderr)
sys.exit(r.returncode)
