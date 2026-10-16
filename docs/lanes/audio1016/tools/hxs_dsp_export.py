#!/usr/bin/env python3
"""Export the APU's GP and EP DSP state from a save state for dsp_harness.

  hxs_dsp_export.py STREAM OUTDIR

STREAM is the raw migration stream hxs_unpack.py writes. Writes, all
little-endian u32 arrays:

  gp_core.bin, ep_core.bin   one DSPState each, flattened (layout below)
  gp_regs.bin, ep_regs.bin   gp.regs[0x10000], ep.regs[0x10000]
  apu_regs.bin               regs[0x20000]
  ram.bin                    guest RAM (the block that holds the voice table)

Core layout, in u32 words: pc, registers[64], stack[2][16], xram[4096],
yram[2048], pram[4096], mixbuffer[1024], periph[128], loop_rep, pc_on_rep,
instr_cycle, interrupt_state, interrupt_instr_fetch, interrupt_save_pc,
interrupt_counter, interrupt_ipl_to_raise, interrupt_pipeline_count,
interrupt_ipl[12], interrupt_is_pending[12], num_inst, cur_inst_len,
cur_inst, dma.configuration, dma.control, dma.start_block, dma.next_block,
dma.error, dma.eol, save_cycles, interrupts.

The mcpx-apu vmstate is in apu.c (vmstate_mcpx_apu, vmstate_vp_dsp_state);
the DSPState blob is 46337 bytes and the regs[] offset from the section body
is 276 (PCI) + 2 * (46337 + 0x40000). That offset is checked against the
footer-derived one hxs_voices.find_apu() uses.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hxs_voices as hv  # noqa: E402

PCI_BYTES = 276
DSP_BYTES = 46337
UNIT_REGS = 0x10000 * 4


def be(fmt, data, off):
    return struct.unpack_from(">" + fmt, data, off)


def flatten_dsp(blob):
    """The DSPState vmstate blob as the flat u32 list the harness reads."""
    o = 0
    out = []
    instr_cycle, = be("H", blob, o); o += 2
    pc, = be("I", blob, o); o += 4
    out.append(pc)
    for n in (64, 32, 4096, 2048, 4096, 1024, 128):
        out.extend(be(f"{n}I", blob, o)); o += 4 * n
    loop_rep, pc_on_rep = be("II", blob, o); o += 8
    out += [loop_rep, pc_on_rep, instr_cycle]
    out.extend(be("6H", blob, o)); o += 12
    out.extend(v & 0xFFFFFFFF for v in be("12h", blob, o)); o += 24
    out.extend(be("12H", blob, o)); o += 24
    out.extend(be("III", blob, o)); o += 12      # num_inst, cur_inst_len, cur_inst
    o += 1                                       # VMSTATE_UNUSED(1)
    o += 4 + 1 + 4 + 1 + 4 + 2 + 256             # disassembler fields
    assert o == 46311, o
    out.extend(be("IIII", blob, o)); o += 16     # dma words
    out += list(be("BB", blob, o)); o += 2       # dma.error, dma.eol
    save_cycles, interrupts = be("iI", blob, o); o += 8
    out += [save_cycles & 0xFFFFFFFF, interrupts]
    assert o == DSP_BYTES, o
    return out


def be_words_to_le(raw):
    n = len(raw) // 4
    return struct.pack(f"<{n}I", *struct.unpack(f">{n}I", raw))


def main():
    path, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    data = open(path, "rb").read()
    blocks, dev_pos, _ = hv.parse(data)
    sid, body, regs_off, tail_off = hv.find_apu(data, dev_pos - 64)
    gp_off = body + PCI_BYTES
    gp_regs_off = gp_off + DSP_BYTES
    ep_off = gp_regs_off + UNIT_REGS
    ep_regs_off = ep_off + DSP_BYTES
    pred_regs = ep_regs_off + UNIT_REGS
    print(f"mcpx-apu body {body}; regs by footer {regs_off}, by layout "
          f"{pred_regs} ({'agree' if pred_regs == regs_off else 'DISAGREE'})")
    if pred_regs != regs_off:
        raise SystemExit("layout does not match the stream; not exporting")
    for name, off in (("gp", gp_off), ("ep", ep_off)):
        words = flatten_dsp(data[off:off + DSP_BYTES])
        open(os.path.join(outdir, f"{name}_core.bin"), "wb").write(
            struct.pack(f"<{len(words)}I", *words))
        print(f"{name}: pc {words[0]:#x} words {len(words)}")
    for name, off, n in (("gp_regs", gp_regs_off, UNIT_REGS),
                         ("ep_regs", ep_regs_off, UNIT_REGS),
                         ("apu_regs", regs_off, hv.REGS_BYTES)):
        open(os.path.join(outdir, f"{name}.bin"), "wb").write(
            be_words_to_le(data[off:off + n]))
    apu = hv.Apu(data, regs_off, tail_off)
    vpv = apu.reg(hv.VPVADDR)
    best = None
    for name, blk in blocks.items():
        if len(blk) < vpv + 256 * hv.PAVS_SIZE:
            continue
        r = hv.Ram(blk)
        n = sum(1 for v in range(256)
                if hv.field(r.u32(vpv + v * hv.PAVS_SIZE + 0x54), 1 << 21))
        if best is None or n > best[0]:
            best = (n, name)
    open(os.path.join(outdir, "ram.bin"), "wb").write(blocks[best[1]])
    gpr = lambda a: struct.unpack_from(">I", data, gp_regs_off + a * 4)[0]
    epr = lambda a: struct.unpack_from(">I", data, ep_regs_off + a * 4)[0]
    print(f"ram: {best[1]} {len(blocks[best[1]]):#x} bytes")
    print(f"GPRST {gpr(0xFFFC):#x} EPRST {epr(0xFFFC):#x}")
    for nm, a in (("GPSADDR", 0x2040), ("GPFADDR", 0x2044),
                  ("EPSADDR", 0x2048), ("EPFADDR", 0x204C),
                  ("GPSMAXSGE", 0x20D4), ("GPFMAXSGE", 0x20D8),
                  ("EPSMAXSGE", 0x20DC), ("EPFMAXSGE", 0x20E0)):
        print(f"{nm} {apu.reg(a):#x}", end="  ")
    print()
    for unit, base in (("GP", 0x3000), ("EP", 0x4000)):
        for kind, o in (("OF", 0x24), ("IF", 0x64)):
            cnt = 4 if kind == "OF" else 2
            for i in range(cnt):
                b = apu.reg(base + o + 0x10 * i)
                e = apu.reg(base + o + 4 + 0x10 * i)
                c = apu.reg(base + o + 8 + 0x10 * i)
                if b or e or c:
                    print(f"{unit}{kind}{i}: base {b:#x} end {e:#x} cur {c:#x}")


if __name__ == "__main__":
    main()
