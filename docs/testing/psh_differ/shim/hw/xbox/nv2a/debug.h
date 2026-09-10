/*
 * Stand-in for hw/xbox/nv2a/debug.h.
 *
 * The real header pulls qemu/timer.h on non-ARM64 hosts, which reaches most of
 * QEMU. The generator only wants the warning macros.
 *
 * Deliberate difference from the real header: NV2A_UNIMPLEMENTED is always
 * live here (upstream compiles it out unless DEBUG_NV2A_FEATURES) and it
 * records the message instead of printing it. That is the point -- a state bit
 * whose only effect is to trip an "unimplemented" warning produces no change
 * in the emitted GLSL, and the differ needs to tell that known gap apart from
 * a bit nothing looks at.
 */

#ifndef PSH_DIFFER_NV2A_DEBUG_H
#define PSH_DIFFER_NV2A_DEBUG_H

#include <stdint.h>
#include <stdio.h>

/* Defined by the differ; see unimpl.c. */
void psh_differ_record_unimpl(const char *fmt, ...);

#define NV2A_UNIMPLEMENTED(format, ...) \
    psh_differ_record_unimpl(format, ##__VA_ARGS__)
#define NV2A_UNCONFIRMED(format, ...) \
    psh_differ_record_unimpl(format, ##__VA_ARGS__)

#define NV2A_XPRINTF(x, ...) do { } while (0)
#define NV2A_DPRINTF(...)    do { } while (0)
#define NV2A_GL_DPRINTF(...) do { } while (0)
#define NV2A_VK_DPRINTF(...) do { } while (0)

#endif
