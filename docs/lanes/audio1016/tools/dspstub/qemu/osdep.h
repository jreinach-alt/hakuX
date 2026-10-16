/* Stand-in for QEMU's osdep.h so hw/xbox/mcpx/apu/dsp builds outside QEMU
 * for dsp_harness.c. Only what dsp.c, dsp_cpu.c and dsp_dma.c use. */
#ifndef DSPSTUB_OSDEP_H
#define DSPSTUB_OSDEP_H
#include <assert.h>
#include <inttypes.h>
#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define likely(x) __builtin_expect(!!(x), 1)
#define unlikely(x) __builtin_expect(!!(x), 0)
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#ifndef MIN
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#endif
#ifndef MAX
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#endif
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))
#define QEMU_FALLTHROUGH __attribute__((fallthrough))
#define G_GNUC_UNUSED __attribute__((unused))

static inline uint32_t ldl_le_p(const void *p)
{
    uint32_t v;
    memcpy(&v, p, 4);
    return v;
}

static inline void stl_le_p(void *p, uint32_t v)
{
    memcpy(p, &v, 4);
}
#endif
