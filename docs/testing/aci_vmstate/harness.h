/* Harness scaffolding: the REAL migration/vmstate.h and the REAL
 * hw/audio/ac97_int.h, reached through the thin shims in shim/.
 * See README.md. */
#ifndef ACI_VMSTATE_HARNESS_H
#define ACI_VMSTATE_HARNESS_H

#include "qemu/osdep.h"
#include <assert.h>
#include <stdarg.h>

#include "migration/vmstate.h"
#include "hw/audio/ac97_int.h"

#define ARRAY_SIZE_LOCAL(a) (sizeof(a) / sizeof((a)[0]))

typedef struct HarnessMember {
    const char *name;
    size_t offset;
    size_t size;
} HarnessMember;

#endif
