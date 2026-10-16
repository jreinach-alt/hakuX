#!/usr/bin/env python3
"""Every APU voice in a save state: format, routing, gains and source level.

  hxs_voices.py STREAM [--all] [--dump-dir DIR]

STREAM is the raw migration stream hxs_unpack.py writes. The tool parses the
"ram" section into guest RAM, finds the mcpx-apu device section (regs[],
hrtf_submix, submix_headroom, SSL state), walks the 2D, 3D and multipass voice
lists from TVL2D/TVL3D/TVLMP, and for each voice prints what voice_process()
in hw/xbox/mcpx/apu/vp/vp.c would read: stereo, container/sample size,
buffer or stream, pitch as a sample rate, envelope state and level, the eight
bins with their volumes in dB, the monitor-path gain (max over bins times the
amplitude envelope), the filter mode and cutoff, and the HRTF handle.

Then it reads the voice's source samples out of RAM (the whole buffer for a
buffer voice; every filled SSL segment for a stream voice) and prints their
AC RMS and peak in dBFS, the level the voice feeds the mixer before any gain.
--dump-dir writes those samples as s16le (mono or stereo) per voice.

Units: dB is 20*log10 of an amplitude ratio; dBFS is relative to int16 full
scale (32768); vol is the 12-bit register in 1/64 dB of attenuation, which is
how attenuate() in vp.c reads it.
"""
import math
import os
import struct
import sys

PAGE = 4096
RAM_FLAGS = dict(ZERO=0x02, MEM_SIZE=0x04, PAGE=0x08, EOS=0x10,
                 CONTINUE=0x20, XBZRLE=0x40, HOOK=0x80)

# apu_regs.h
VPVADDR, VPSGEADDR, VPSSLADDR = 0x202C, 0x2030, 0x2034
TVL2D, TVL3D, TVLMP = 0x2054, 0x2060, 0x206C
PAVS_SIZE = 0x80
TAIL = 4 + 4 + 256 * 18 + 4 + 4 + 1 + 32 + 32   # vmstate fields after regs[]
REGS_BYTES = 0x20000 * 4

EG = ["off", "delay", "attack", "hold", "decay", "sustain", "release",
      "force-release"]
CS = ["B8", "B16", "ADPCM", "B32"]
SS = ["U8", "S16", "S24", "S32"]


class Stream:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos

    def u8(self):
        v = self.d[self.p]
        self.p += 1
        return v

    def be32(self):
        v, = struct.unpack_from(">I", self.d, self.p)
        self.p += 4
        return v

    def be64(self):
        v, = struct.unpack_from(">Q", self.d, self.p)
        self.p += 8
        return v

    def name(self):
        n = self.u8()
        s = self.d[self.p:self.p + n].decode("latin-1")
        self.p += n
        return s

    def take(self, n):
        b = self.d[self.p:self.p + n]
        self.p += n
        return b


def ram_load(s, blocks):
    """One ram section's data, up to RAM_SAVE_FLAG_EOS."""
    cur = None
    pages = 0
    while True:
        v = s.be64()
        flags = v & (PAGE - 1)
        addr = v & ~(PAGE - 1)
        if flags & RAM_FLAGS["MEM_SIZE"]:
            total = addr
            seen = 0
            while seen < total:
                name = s.name()
                length = s.be64()
                blocks.setdefault(name, bytearray(length))
                seen += length
            continue
        if flags & RAM_FLAGS["EOS"]:
            return pages
        if flags & (RAM_FLAGS["ZERO"] | RAM_FLAGS["PAGE"]):
            if not flags & RAM_FLAGS["CONTINUE"]:
                cur = s.name()
            blk = blocks[cur]
            if flags & RAM_FLAGS["ZERO"]:
                ch = s.u8()
                blk[addr:addr + PAGE] = bytes([ch]) * PAGE
            else:
                blk[addr:addr + PAGE] = s.take(PAGE)
            pages += 1
            continue
        if flags & 0x200:       # MULTIFD_FLUSH: no payload
            continue
        raise SystemExit(f"ram: unhandled flags {flags:#x} at {s.p - 8}")


def parse(data):
    q = data.find(b"QEVM")
    if q < 0:
        raise SystemExit("no QEVM magic")
    s = Stream(data, q + 8)
    blocks = {}
    ram_sid = None
    footers = False
    while True:
        t = s.u8()
        if t == 0x07:                       # CONFIGURATION
            n = s.be32()
            s.take(n)
            continue
        if t in (0x01, 0x04):               # START, FULL
            sid = s.be32()
            idstr = s.name()
            s.be32()
            s.be32()
            if idstr != "ram":
                return blocks, s.p, footers
            ram_sid = sid
            ram_load(s, blocks)
        elif t in (0x02, 0x03):             # PART, END
            sid = s.be32()
            if sid != ram_sid:
                return blocks, s.p, footers
            ram_load(s, blocks)
        elif t == 0x00:
            return blocks, s.p, footers
        else:
            return blocks, s.p, footers
        if s.d[s.p] == 0x7E:
            footers = True
            s.p += 5


def find_apu(data, start):
    """(sid, data_start, regs_offset, tail_offset) of the mcpx-apu section."""
    pos = start
    while True:
        i = data.find(b"mcpx-apu", pos)
        if i < 0:
            raise SystemExit("no mcpx-apu section")
        pos = i + 1
        for q in range(i - 1, max(i - 80, 0), -1):
            if data[q] != 0x04:
                continue
            n = data[q + 5]
            idstr = data[q + 6:q + 6 + n]
            if idstr.endswith(b"mcpx-apu") and q + 6 + n == i + 8:
                sid, = struct.unpack_from(">I", data, q + 1)
                body = q + 6 + n + 8
                foot = struct.pack(">BI", 0x7E, sid)
                f = data.find(foot, body + 0x100000)
                while f >= 0:
                    regs = f - TAIL - REGS_BYTES
                    vpv, = struct.unpack_from(">I", data, regs + VPVADDR * 4)
                    if vpv and vpv % 0x80 == 0 and vpv < 0x08000000:
                        return sid, body, regs, f - TAIL
                    f = data.find(foot, f + 1)
                raise SystemExit("mcpx-apu footer not found")


class Apu:
    def __init__(self, data, regs_off, tail_off):
        self.regs_raw = data[regs_off:regs_off + REGS_BYTES]
        t = tail_off + 8
        self.ssl = []
        for _ in range(256):
            b0, b1, c0, c1, idx, seg = struct.unpack_from(">IIBBii", data, t)
            self.ssl.append(((b0, b1), (c0, c1), idx, seg))
            t += 18
        t += 4
        self.hrtf_submix = list(data[t:t + 4])
        self.hrtf_headroom = data[t + 4]
        self.submix_headroom = list(data[t + 5:t + 37])

    def reg(self, a):
        return struct.unpack_from(">I", self.regs_raw, a * 4)[0]


class Ram:
    def __init__(self, blk):
        self.b = blk

    def u32(self, a):
        return struct.unpack_from("<I", self.b, a)[0]

    def bytes(self, a, n):
        return bytes(self.b[a:a + n])


def field(w, mask):
    sh = (mask & -mask).bit_length() - 1
    return (w & mask) >> sh


def att_db(vol):
    vol &= 0xFFF
    return None if vol == 0xFFF else -vol / 64.0


IMA_STEP = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34,
            37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143,
            157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494,
            544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552,
            1707, 1878, 2066, 2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428,
            4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487,
            12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086,
            29794, 32767]
IMA_IDX = [-1, -1, -1, -1, 2, 4, 6, 8]


def ima_block(blk, channels):
    """One Xbox ADPCM block (36 bytes per channel) to 65 frames."""
    out = [[0] * 65 for _ in range(channels)]
    pred = []
    idx = []
    for c in range(channels):
        p, i = struct.unpack_from("<hB", blk, 4 * c)
        pred.append(p)
        idx.append(min(max(i, 0), 88))
        out[c][0] = p
    pos = 4 * channels
    n = [1] * channels
    for _ in range(8):
        for c in range(channels):
            word = blk[pos:pos + 4]
            pos += 4
            for byte in word:
                for nib in (byte & 0xF, byte >> 4):
                    step = IMA_STEP[idx[c]]
                    diff = step >> 3
                    if nib & 1:
                        diff += step >> 2
                    if nib & 2:
                        diff += step >> 1
                    if nib & 4:
                        diff += step
                    if nib & 8:
                        pred[c] -= diff
                    else:
                        pred[c] += diff
                    pred[c] = min(max(pred[c], -32768), 32767)
                    idx[c] = min(max(idx[c] + IMA_IDX[nib & 7], 0), 88)
                    out[c][n[c]] = pred[c]
                    n[c] += 1
    return out


def decode(raw, cs, ss, channels):
    """Bytes in the voice's format to per-channel int16-scaled floats."""
    import numpy as np
    if cs == 2:
        bs = 36 * channels
        chans = [[] for _ in range(channels)]
        for o in range(0, len(raw) - bs + 1, bs):
            frames = ima_block(raw[o:o + bs], channels)
            for c in range(channels):
                chans[c].extend(frames[c])
        return [np.array(c, dtype=np.float64) for c in chans]
    width = [1, 2, 0, 4][cs]
    a = np.frombuffer(raw[: len(raw) // (width * channels) * width * channels],
                      dtype={1: "u1", 2: "<i2", 4: "<i4"}[width])
    a = a.astype(np.float64)
    if ss == 0:
        a = (a - 128.0) * 256.0
    elif ss == 2:
        a = a / 256.0           # s24 in a 32-bit container, low byte padding
    elif ss == 3:
        a = a / 65536.0
    a = a.reshape(-1, channels)
    return [a[:, c] for c in range(channels)]


def level(x):
    import numpy as np
    if len(x) == 0:
        return float("nan"), float("nan")
    rms = math.sqrt(float(np.mean((x - x.mean()) ** 2)))
    pk = float(np.abs(x).max())
    f = lambda v: 20 * math.log10(v / 32768.0) if v > 0 else float("-inf")
    return f(rms), f(pk)


def voice_lists(apu, ram, vpv):
    lists = {}
    for name, reg in (("2D", TVL2D), ("3D", TVL3D), ("MP", TVLMP)):
        h = apu.reg(reg) & 0xFFFF
        seen = 0
        while h != 0xFFFF and h < 256 and seen < 256:
            lists[h] = name
            w = ram.u32(vpv + h * PAVS_SIZE + 0x7C)
            h = w & 0xFFFF
            seen += 1
    return lists


def main():
    path = sys.argv[1]
    show_all = "--all" in sys.argv
    dump = None
    if "--dump-dir" in sys.argv:
        dump = sys.argv[sys.argv.index("--dump-dir") + 1]
        os.makedirs(dump, exist_ok=True)
    data = open(path, "rb").read()
    blocks, dev_pos, footers = parse(data)
    print("ram blocks: " + ", ".join(
        f"{k} {len(v):#x}" for k, v in blocks.items()) +
        f"; device sections from {dev_pos}; footers {footers}")
    sid, body, regs_off, tail_off = find_apu(data, dev_pos - 64)
    apu = Apu(data, regs_off, tail_off)
    vpv, sge, sslb = apu.reg(VPVADDR), apu.reg(VPSGEADDR), apu.reg(VPSSLADDR)
    print(f"mcpx-apu section {sid}: VPVADDR {vpv:#x} VPSGEADDR {sge:#x} "
          f"VPSSLADDR {sslb:#x} TVL2D {apu.reg(TVL2D):#x} "
          f"TVL3D {apu.reg(TVL3D):#x} TVLMP {apu.reg(TVLMP):#x}")
    print(f"hrtf_submix {apu.hrtf_submix} hrtf_headroom {apu.hrtf_headroom} "
          f"submix_headroom {apu.submix_headroom}")
    # Guest RAM is the block whose voice table has ACTIVE bits and sane links.
    best = None
    for name, blk in blocks.items():
        if len(blk) < vpv + 256 * PAVS_SIZE:
            continue
        r = Ram(blk)
        n = sum(1 for v in range(256)
                if field(r.u32(vpv + v * PAVS_SIZE + 0x54), 1 << 21))
        if best is None or n > best[0]:
            best = (n, name)
    print(f"guest RAM: {best[1]} ({best[0]} voices with ACTIVE set)")
    ram = Ram(blocks[best[1]])
    lists = voice_lists(apu, ram, vpv)

    print()
    hdr = ("v   list st fmt      spb  type   Hz      eg/lvl        "
           "bins:vol(dB)                                   mon_g  fm fc     "
           "hrtf  src_rms/pk dBFS (frames)")
    print(hdr)
    for v in range(256):
        base = vpv + v * PAVS_SIZE
        w = [ram.u32(base + o) for o in range(0, PAVS_SIZE, 4)]
        state = w[0x54 // 4]
        active = bool(state & (1 << 21))
        if not active and not show_all:
            continue
        paused = bool(state & (1 << 18))
        vbin, fmt = w[0], w[1]
        stereo = bool(fmt & (1 << 27))
        ch = 2 if stereo else 1
        ss = field(fmt, 0x3 << 28)
        cs = field(fmt, 0x3 << 30)
        spb = 1 + field(fmt, 0x1F << 16)
        stream = bool(fmt & (1 << 24))
        loop = bool(fmt & (1 << 25))
        mp = bool(fmt & (1 << 21))
        pitch = field(w[0x7C // 4], 0xFFFF0000)
        if pitch >= 0x8000:
            pitch -= 0x10000
        hz = 48000.0 * 2 ** (pitch / 4096.0)
        bins = [field(vbin, 0x1F), field(vbin, 0x1F << 5),
                field(vbin, 0x1F << 10), field(vbin, 0x1F << 16),
                field(vbin, 0x1F << 21), field(vbin, 0x1F << 26),
                field(fmt, 0x1F), field(fmt, 0x1F << 5)]
        if v < 64:
            bins[:4] = apu.hrtf_submix
        va, vb, vc = w[0x60 // 4], w[0x64 // 4], w[0x68 // 4]
        vol = [field(va, 0xFFF0), field(va, 0xFFF00000),
               field(vb, 0xFFF0), field(vb, 0xFFF00000),
               field(vc, 0xFFF0), field(vc, 0xFFF00000),
               (field(vc, 0xF) << 8) | (field(vb, 0xF) << 4) | field(va, 0xF),
               (field(vc, 0xF0000) << 8) | (field(vb, 0xF0000) << 4) |
               field(va, 0xF0000)]
        eacur = field(state, 0xF << 28)
        ealvl = field(w[0x58 // 4], 0xFF000000)
        sustain = field(w[0x0C // 4], 0xFF << 24)
        if eacur == 0:
            ea = 1.0
        elif eacur == 5:
            ea = sustain / 255.0
        else:
            ea = ealvl / 255.0
        lin = [10 ** (a / 20) for a in (att_db(x) for x in vol) if a is not None]
        mon = max(lin) * ea if lin else 0.0
        mon_db = 20 * math.log10(mon) if mon > 0 else float("-inf")
        fmode = field(w[0x18 // 4], 3 << 16)
        fca = w[0x74 // 4]
        fc = fca & 0xFFFF
        if fc >= 0x8000:
            fc -= 0x10000
        if v < 64:
            lpf = fmode == 1
        else:
            lpf = (fmode == 1) if stereo else bool(fmode & 1)
        fc_s = f"{min(max(2 ** (fc / 4096.0), 0.003906), 1.0):.3f}" if lpf else "-"
        hrtf = w[0x1C // 4] & 0xFFFF
        binvol = " ".join(
            f"{b}:{'off' if att_db(x) is None else '%.1f' % att_db(x)}"
            for b, x in zip(bins, vol))
        eg = f"{EG[eacur]}/{ealvl}" + (f" s{sustain}" if eacur == 5 else "")

        # Source samples.
        raw = b""
        src = ""
        if stream:
            (b0, b1), (c0, c1), idx, seg = apu.ssl[v]
            segs = []
            for bi, cnt in ((b0, c0), (b1, c1)):
                for k in range(cnt):
                    e = sslb + (bi + k) * 8
                    off, ln = ram.u32(e), ram.u32(e + 4)
                    n = ln & 0xFFFF
                    if off == 0 or n == 0:
                        continue
                    seg_cs = (ln >> 16) & 3
                    bs = 36 * ch if seg_cs == 2 else [1, 2, 0, 4][seg_cs] * ch
                    nbytes = (n >> 6) * bs if seg_cs == 2 else n * bs
                    segs.append(ram.bytes(off, nbytes))
            raw = b"".join(segs)
            src = f"ssl A{c0}@{b0} B{c1}@{b1} idx{idx} seg{seg}"
        elif not mp:
            ba = w[0x20 // 4] & 0xFFFFFF
            ebo = w[0x5C // 4] & 0xFFFFFF
            if cs == 2:
                nbytes = ((ebo + 1 + 64) // 65) * 36 * ch
            else:
                nbytes = (ebo + 1) * [1, 2, 0, 4][cs] * ch
            nbytes = min(nbytes, 16 << 20)
            parts = []
            a = ba
            end = ba + nbytes
            while a < end:
                ent = a // PAGE
                prd = ram.u32(sge + ent * 8)
                take = min(PAGE - a % PAGE, end - a)
                parts.append(ram.bytes(prd + a % PAGE, take))
                a += take
            raw = b"".join(parts)
            src = f"buf ba{ba:#x} ebo{ebo}"
        lv = ""
        if raw:
            chans = decode(raw, cs, ss, ch)
            frames = len(chans[0])
            lv = " ".join("%.1f/%.1f" % level(c) for c in chans) + f" ({frames})"
            if dump:
                import numpy as np
                inter = np.stack(chans, axis=1).clip(-32768, 32767)
                inter.astype("<i2").tofile(
                    os.path.join(dump, f"v{v:03d}.{ch}ch.{int(round(hz))}.s16le"))
        typ = ("strm" if stream else "loop" if loop else "buf") + \
              ("+mp" if mp else "") + ("+P" if paused else "")
        print(f"{v:<3d} {lists.get(v, '-'):4s} {'S' if stereo else 'M'}  "
              f"{CS[cs]}/{SS[ss]:3s} {spb:3d}  {typ:6s} {hz:7.0f} {eg:13s} "
              f"{binvol:46s} {mon_db:6.1f} {fmode}  {fc_s:6s} "
              f"{'-' if hrtf == 0xFFFF else '%#x' % hrtf:5s} {lv}  [{src}]")


if __name__ == "__main__":
    main()
