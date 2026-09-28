#!/bin/bash
# Registers docs/testing/predictions/dirtytlb-counter-signed.json (#548): the
# discriminator for dirtytlb-counter-pixels.json's one moved capture,
# Texture_signed_component_tests/txt_A8R8G8B8_ADD (A 168,960 label-differs,
# B 153,427 white-content, one run each). Three runs per arm on that suite.
# A = master 01e62d8d1c, B = the counter merged onto it, 0794c79011.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
out=docs/testing/predictions/dirtytlb-counter-signed.json
python3 docs/testing/ab_compare.py --register "$out" \
  --who lane.dirtytlb --issue 548 \
  --a-ref 01e62d8d1c --b-ref 0794c79011 \
  --disc-suites "Texture signed component tests" \
  --must-not-move 'Texture_signed_component_tests/*' \
  --prediction "#548 counter arm, the discriminator. dirtytlb-counter-pixels.json FAILED as registered on one capture: Texture_signed_component_tests/txt_A8R8G8B8_ADD read 168,960 px in A (9d777502fa) and 153,427 in B (111c7fea74), one run each, and the B image shows the header's red gradient and blue stripes in the upper quads (a stale texture sampled). The counter makes every walk and clears every bit A does (read in system/physmem.c: the tags wrap the same tlb_reset_dirty_range_all() calls); what it adds on the render thread is time: relaxed atomic adds per walk and one __android_log_print per 60+ flips. So the claim: the move is this capture's own run-to-run variance (it moved 12,544 px under an unrelated change in tiecode282's arm, and varies run to run on lavapipe), not the counter. PREDICTED: with three runs per arm, every capture's B runs fall inside A's measured band, and txt_A8R8G8B8_ADD varies inside at least one arm. REFUTED, in either of two worlds: (1) A's three runs of txt_A8R8G8B8_ADD are byte-identical to each other and B's three all differ from them -- the counter's timing reliably exposes a texture-upload race, and it does not land as it stands; (2) any other capture of the suite moves outside A's band."
python3 - "$out" <<'EOF'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["runs_per_arm"] = 3
json.dump(d, open(p, "w"), indent=2)
open(p, "a").write("\n")
EOF
sha256sum "$out"
