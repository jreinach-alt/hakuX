/* Stand-in for hw/hw.h plus the QOM declaration macro ac97_int.h uses. */
#ifndef ACI_HARNESS_HW_H
#define ACI_HARNESS_HW_H
#include "qemu/osdep.h"

/* Real expansion declares the type and its class checkers; only the typedef
 * matters for a struct-layout round trip. */
#define OBJECT_DECLARE_SIMPLE_TYPE(InstanceType, LOWERCASE) \
    typedef struct InstanceType InstanceType;
#define OBJECT_CHECK(type, obj, name) ((type *)(obj))

typedef struct MemoryRegionOps MemoryRegionOps;

/* Size is irrelevant to the test: every member of AC97LinkState that the
 * field list touches is a scalar or an array of scalars, and the macros
 * compute offsets with offsetof against whatever this harness compiles. */
typedef struct MemoryRegion { void *opaque; } MemoryRegion;

#endif
