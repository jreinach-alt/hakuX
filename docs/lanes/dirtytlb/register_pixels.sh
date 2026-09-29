#!/bin/bash
# Registers docs/testing/predictions/dirtytlb-counter-pixels.json (#548):
# the counter arm moves no pgraph pixel. Usage: register_pixels.sh A_REF B_REF
set -e
cd "$(dirname "$0")/../../.."
A=$1; B=$2
python3 docs/testing/ab_compare.py --register docs/testing/predictions/dirtytlb-counter-pixels.json \
  --who lane.dirtytlb --issue 548 --a-ref "$A" --b-ref "$B" \
  --must-not-move 'Texture_CPU_Update/*' \
  --must-not-move 'Texture_3D_as_2D/*' \
  --must-not-move 'Texture_signed_component_tests/*' \
  --must-not-move 'Texture_render_update_in_place/*' \
  --must-not-move 'Texture_format/*' \
  --must-not-move 'High_vertex_count/*' \
  --must-not-move 'SetVertexData/*' \
  --must-not-move 'Zero_stride/*' \
  --must-not-move 'Attrib_carryover/*' \
  --must-not-move 'DMA_corruption_around_surfaces/*' \
  --must-not-move 'Inline_array_size_mismatch/*' \
  --must-not-move '3D_primitive/*' \
  --prediction "#548 counter arm: B adds the [rdc] per-caller count of off-vCPU tlb_reset_dirty walks (system/physmem.c, accel/tcg/cputlb.c, include/system/ram_addr.h) and changes nothing else. Every dirty bit is cleared, and every TLB walk made, exactly as in A: the counter reads thread-locals the walk already computed and adds to its own statics, so no guest-visible state can differ. The suites are the ones whose draws go through the two paths it sits on -- the vertex RAM sync (vertex data the guest writes between draws) and check_texture_dirty (textures the guest rewrites) -- so every capture in them is identical between arms. A moved capture refutes 'counter only', and the counter does not land until the move is explained. Read scores1.tsv for unreadable rows and run1.log for UtilAcceptVsock before trusting a same."
