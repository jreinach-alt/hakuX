/*
 * Stand-in for hw/xbox/nv2a/pgraph/pgraph.h.
 *
 * psh.c wants two things from the real header: the NV2A register and method
 * constants, and the PGRAPHState type. The constants come from nv2a_regs.h,
 * which is a flat list of #defines with no includes of its own, so it is used
 * verbatim -- the values under test are the real ones.
 *
 * PGRAPHState stays opaque. The three functions in psh.c that read it
 * (set_psh_state, set_psh_uniform_values, get_color_key_mask_for_texture) are
 * removed by carve.py before this file is compiled, so nothing here needs its
 * layout. If a new function starts reading emulator state, carve.py says so.
 */

#ifndef PSH_DIFFER_PGRAPH_H
#define PSH_DIFFER_PGRAPH_H

#include "qemu/osdep.h"
#include "hw/xbox/nv2a/nv2a_regs.h"

typedef struct PGRAPHState PGRAPHState;

#endif
