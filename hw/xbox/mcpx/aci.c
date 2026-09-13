/*
 * QEMU MCPX Audio Codec Interface implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2020-2021 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "qemu/osdep.h"
#include "hw/hw.h"
#include "hw/i386/pc.h"
#include "hw/pci/pci.h"
#include "hw/audio/ac97_int.h"
#include "migration/vmstate.h"

typedef struct MCPXACIState {
    PCIDevice dev;

    AC97LinkState ac97;

    MemoryRegion io_nam, io_nabm;

    MemoryRegion mmio;
    MemoryRegion nam_mmio, nabm_mmio;
} MCPXACIState;

#define MCPX_ACI_DEVICE(obj) \
    OBJECT_CHECK(MCPXACIState, (obj), "mcpx-aci")

static void mcpx_aci_realize(PCIDevice *dev, Error **errp)
{
    MCPXACIState *d = MCPX_ACI_DEVICE(dev);

    dev->config[PCI_INTERRUPT_PIN] = 0x01;

    memory_region_init(&d->mmio, OBJECT(dev), "mcpx-aci-mmio", 0x1000);

    memory_region_init_io(&d->io_nam, OBJECT(dev), &ac97_io_nam_ops, &d->ac97,
                          "mcpx-aci-nam", 0x100);
    memory_region_init_io(&d->io_nabm, OBJECT(dev), &ac97_io_nabm_ops, &d->ac97,
                          "mcpx-aci-nabm", 0x80);

    /*pci_register_bar(&d->dev, 0, PCI_BASE_ADDRESS_SPACE_IO, &d->io_nam);
    pci_register_bar(&d->dev, 1, PCI_BASE_ADDRESS_SPACE_IO, &d->io_nabm);

    memory_region_init_alias(&d->nam_mmio, NULL, &d->io_nam, 0, 0x100);
    memory_region_add_subregion(&d->mmio, 0x0, &d->nam_mmio);

    memory_region_init_alias(&d->nabm_mmio, NULL, &d->io_nabm, 0, 0x80);
    memory_region_add_subregion(&d->mmio, 0x100, &d->nabm_mmio);*/

    memory_region_add_subregion(&d->mmio, 0x0, &d->io_nam);
    memory_region_add_subregion(&d->mmio, 0x100, &d->io_nabm);

    pci_register_bar(&d->dev, 2, PCI_BASE_ADDRESS_SPACE_MEMORY, &d->mmio);
    ac97_common_init(&d->ac97, &d->dev, pci_get_address_space(&d->dev));
}

/* ------------------------------------------------------------------------
 * Issue #75: migrate the AC'97 codec, not just the PCI config space.
 *
 * What was here was VMSTATE_PCI_DEVICE and a bare `// FIXME`, so a save/load
 * round trip restored the BARs and the config header and left the embedded
 * AC97LinkState holding whatever mcpx_aci_realize/ac97_common_init had put
 * there at boot. Every guest-visible codec register -- the 256-byte mixer
 * page, the global control and status words, the codec access semaphore, and
 * all eight bus-master descriptor engines with their BD cache -- came back at
 * reset values, and the load reported success. That silence is the severe
 * half: a load that refuses is a bug report, a load that succeeds with the
 * wrong state is a bug report filed months later against something else.
 *
 * The field list below is the same state upstream's own AC97 device migrates
 * (hw/audio/ac97.c, vmstate_ac97), reached through a nested struct because the
 * ACI embeds AC97LinkState directly rather than via AC97DeviceState. Reached
 * that way the nested post_load also gets the right opaque, which the
 * device-level one in ac97.c does not -- see the note there.
 *
 * SCOPE, stated so this is not over-sold: the ACI is not in the audible path
 * on this platform. ep_sink_samples() returns false for MCPX_APU_DEBUG_MON_AC97
 * (apu/dsp/gp_ep.c) and the APU opens its own output device, so a corrupted
 * AC'97 cannot make the emulator quiet and this is not a loudness fix. It is a
 * savestate-correctness fix.
 *
 * VERSION 2, minimum 2, DELIBERATELY REFUSING VERSION 1. A v1 stream contains
 * no codec bytes at all, so there is nothing to load and no way to reconstruct
 * them; the only two options are to refuse the stream or to succeed while
 * silently restoring reset values, which is the defect itself. Refusing is a
 * real cost -- existing savestates of this branch will not load -- and it is
 * paid where it is cheapest: xemu's snapshot UI lives in ui/xui/, which
 * android/app/src/main/cpp/CMakeLists.txt:473 excludes from the Android build
 * outright, and nothing in the android/ tree calls savevm or loadvm, so no handheld
 * user has a savestate to lose.
 * ------------------------------------------------------------------------ */

static int mcpx_aci_post_load(void *opaque, int version_id)
{
    AC97LinkState *s = opaque;

    ac97_link_post_load(s);
    return 0;
}

static const VMStateDescription vmstate_mcpx_aci_bm_regs = {
    .name = "mcpx-aci/ac97-bm-regs",
    .version_id = 1,
    .minimum_version_id = 1,
    .fields = (const VMStateField[]) {
        VMSTATE_UINT32(bdbar, AC97BusMasterRegs),
        VMSTATE_UINT8(civ, AC97BusMasterRegs),
        VMSTATE_UINT8(lvi, AC97BusMasterRegs),
        VMSTATE_UINT16(sr, AC97BusMasterRegs),
        VMSTATE_UINT16(picb, AC97BusMasterRegs),
        VMSTATE_UINT8(piv, AC97BusMasterRegs),
        VMSTATE_UINT8(cr, AC97BusMasterRegs),
        VMSTATE_UINT32(bd_valid, AC97BusMasterRegs),
        VMSTATE_UINT32(bd.addr, AC97BusMasterRegs),
        VMSTATE_UINT32(bd.ctl_len, AC97BusMasterRegs),
        VMSTATE_END_OF_LIST()
    },
};

static const VMStateDescription vmstate_mcpx_aci_ac97 = {
    .name = "mcpx-aci/ac97",
    .version_id = 1,
    .minimum_version_id = 1,
    .post_load = mcpx_aci_post_load,
    .fields = (const VMStateField[]) {
        VMSTATE_UINT32(glob_cnt, AC97LinkState),
        VMSTATE_UINT32(glob_sta, AC97LinkState),
        VMSTATE_UINT32(cas, AC97LinkState),
        VMSTATE_STRUCT_ARRAY(bm_regs, AC97LinkState, LAST_INDEX, 1,
                             vmstate_mcpx_aci_bm_regs, AC97BusMasterRegs),
        VMSTATE_BUFFER(mixer_data, AC97LinkState),
        VMSTATE_END_OF_LIST()
    },
};

static const VMStateDescription vmstate_mcpx_aci = {
    .name = "mcpx-aci",
    .version_id = 2,
    .minimum_version_id = 2,
    .fields = (VMStateField[]) {
        VMSTATE_PCI_DEVICE(dev, MCPXACIState),
        VMSTATE_STRUCT(ac97, MCPXACIState, 1, vmstate_mcpx_aci_ac97,
                       AC97LinkState),
        VMSTATE_END_OF_LIST()
    },
};

static void mcpx_aci_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    PCIDeviceClass *k = PCI_DEVICE_CLASS(klass);

    k->vendor_id = PCI_VENDOR_ID_NVIDIA;
    k->device_id = PCI_DEVICE_ID_NVIDIA_MCPX_ACI;
    k->revision = 177;
    k->class_id = PCI_CLASS_MULTIMEDIA_AUDIO;
    k->realize = mcpx_aci_realize;

    dc->desc = "MCPX Audio Codec Interface";
    dc->vmsd = &vmstate_mcpx_aci;
}

static const TypeInfo mcpx_aci_info = {
    .name          = "mcpx-aci",
    .parent        = TYPE_PCI_DEVICE,
    .instance_size = sizeof(MCPXACIState),
    .class_init    = mcpx_aci_class_init,
    .interfaces = (InterfaceInfo[]) {
        { INTERFACE_CONVENTIONAL_PCI_DEVICE },
        { },
    },
};

static void mcpx_aci_register(void)
{
    type_register_static(&mcpx_aci_info);
}

type_init(mcpx_aci_register);

#ifdef __ANDROID__
void xemu_android_force_mcpx_aci_link(void)
{
}
#endif
