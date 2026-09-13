/* Minimal stand-in for qemu/osdep.h, enough for the real
 * include/migration/vmstate.h and the real include/hw/audio/ac97_int.h.
 * See README.md for why this harness exists and what it does not prove. */
#ifndef ACI_HARNESS_OSDEP_H
#define ACI_HARNESS_OSDEP_H

#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* The real definition is an annotation for the coroutine checker. */
#define coroutine_mixed_fn

/* Real macros: typeof_field, type_check, QEMU_BUILD_BUG_ON_ZERO, stringify.
 * compiler.h has no includes of its own, so this is the genuine article
 * rather than a copy that could drift. */
#include "qemu/compiler.h"

typedef struct QEMUFile QEMUFile;
typedef struct VMStateDescription VMStateDescription;
typedef struct DeviceState DeviceState;
struct MemoryRegion;
typedef struct JSONWriter JSONWriter;
typedef struct Error Error;

typedef uint64_t hwaddr;

#endif
