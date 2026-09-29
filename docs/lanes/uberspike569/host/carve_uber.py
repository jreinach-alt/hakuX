#!/usr/bin/env python3
"""psh_differ's carve.py, taught psh-uber.c: cut the one function that reads
PGRAPHState (the uniform staging), keep the generator."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "../../../testing/psh_differ"))
import carve  # noqa: E402

carve.CARVE["psh-uber.c"] = (
    "void pgraph_glsl_psh_uber_comb_values(PGRAPHState *pg,",
)
sys.exit(carve.main())
