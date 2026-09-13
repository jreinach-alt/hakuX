#ifndef ACI_HARNESS_PCI_H
#define ACI_HARNESS_PCI_H
#include "qemu/osdep.h"

/* PCI config space is the one thing the pre-fix field list DID migrate, so
 * the harness models it -- that is what makes the legacy arm's "0 of N AC'97
 * bytes, all 256 config bytes" result readable rather than vacuous. */
typedef struct PCIDevice { uint8_t config[256]; } PCIDevice;

#define VMSTATE_PCI_DEVICE(_field, _state) \
    VMSTATE_BUFFER(_field.config, _state)

#endif
