#!/usr/bin/env python3
"""Move one title's saves between Xbox disk images, off the device.

A title keeps its profile and saves on the emulated Xbox disk, partition E:

    E:\\UDATA\\<TitleID>\\   saves: TitleMeta.xbx, TitleImage.xbx, SaveImage.xbx,
                          and one directory per save (<12 hex>\\SaveMeta.xbx + data)
    E:\\TDATA\\<TitleID>\\   the title's own persistent data (settings, rosters)

On Android that disk is `files/x1box/hdd.img`, a qcow2 file (virtual 8 GiB,
64 KiB clusters, refcount order 4, as qemu-img writes it). This reads such an
image with extract_results.py's qcow2 and FATX readers, and WRITES a new one
from scratch: it never edits an image in place, so it cannot damage a
device's disk, and it needs no qemu-img (the host has none).

    saves.py list  <image>                      titles on E:, with sizes
    saves.py pull  <image> <TitleID> <outdir>   one title's UDATA+TDATA, and
                                                save.json (sha256 per file,
                                                the raw FATX times)
    saves.py build <out.qcow2> [<savedir>...]   a freshly formatted disk holding
                                                exactly these saves on E:
    saves.py verify <image> <savedir>           the image holds the save, byte
                                                for byte (exit 1 if not)

A built image is small: the FATX structures plus the saves, a few hundred KiB.
The emulator grows it as the guest writes (the utility-drive caches X:, Y:,
Z: above all), and it opens it like any other: `hddPath` in x1box_prefs.xml
names the disk, so a title run can boot on a built image with the nxdk
results disk (`hdd.img`) left alone. See docs/lanes/titlestate/NOTES.md.

A save written by the title may be signed with the console's HDD key, which
lives in eeprom.bin, not on the disk. Such a save moved to a console with a
different eeprom.bin reads as damaged to the title. Whether a given title's
save survives a move is therefore a per-title observation, and titlestate.py
records it; nothing here can decide it.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import extract_results as er  # noqa: E402  (qcow2 + FATX readers)


def _load_mkhdd():
    path = os.path.join(HERE, "..", "..", "..", "tools", "make_xbox_hdd.py")
    spec = importlib.util.spec_from_file_location("make_xbox_hdd", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MK = _load_mkhdd()

ATTR_DIR = 0x10
DIRENT = 64
VIRTUAL_SIZE = 8 << 30          # what the device images carry (hdd-live.img)
QCOW_CLUSTER_BITS = 16
QCOW_CLUSTER = 1 << QCOW_CLUSTER_BITS
QCOW_COPIED = 1 << 63
TOPS = ("UDATA", "TDATA")


class SaveError(Exception):
    pass


# --------------------------------------------------------------- reading --

def open_e(image_path):
    image = er.open_image(image_path)
    off, size = er.PARTITIONS["E"]
    return er.Fatx(image, off, size)


def raw_listdir(fs, cluster):
    """(name, attrs, first_cluster, size, times) with the six raw FATX time
    words, so a pulled save can be written back with its own timestamps."""
    for chain_cluster in fs._chain(cluster):
        data = fs._cluster_bytes(chain_cluster)
        for pos in range(0, len(data), DIRENT):
            e = data[pos:pos + DIRENT]
            n = e[0]
            if n in (er.END_OF_DIR, er.END_OF_DIR2):
                return
            if n == er.DELETED_FILE or n > er.MAX_FILENAME_LEN:
                continue
            first, size = struct.unpack("<II", e[44:52])
            yield (e[2:2 + n].decode("latin-1"), e[1], first, size,
                   list(struct.unpack("<6H", e[52:64])))


def find(fs, cluster, name):
    for ent in raw_listdir(fs, cluster):
        if ent[0].lower() == name.lower():
            return ent
    return None


def walk(fs, cluster, prefix=""):
    """Yield (relpath, is_dir, size, times, first) depth-first."""
    for name, attrs, first, size, times in raw_listdir(fs, cluster):
        rel = prefix + name
        if attrs & ATTR_DIR:
            yield rel, True, 0, times, first
            yield from walk(fs, first, rel + "/")
        else:
            yield rel, False, size, times, first


def list_titles(fs):
    out = {}
    for top in TOPS:
        ent = find(fs, fs.root_cluster, top)
        if not ent:
            continue
        for name, attrs, first, _s, _t in raw_listdir(fs, ent[2]):
            if not attrs & ATTR_DIR:
                continue
            row = out.setdefault(name.upper(), {"UDATA": None, "TDATA": None})
            files = [w for w in walk(fs, first) if not w[1]]
            saves = [w[0] for w in walk(fs, first) if w[1] and "/" not in w[0]]
            row[top] = {"files": len(files), "bytes": sum(w[2] for w in files),
                        "saves": saves if top == "UDATA" else None}
    return out


def pull(image_path, title_id, outdir):
    fs = open_e(image_path)
    tid = title_id.upper()
    manifest = {"title_id": tid, "source": {
        "image": os.path.abspath(image_path),
        "image_bytes": os.path.getsize(image_path),
        "image_mtime_utc": time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(image_path)))},
        "entries": []}
    found = False
    for top in TOPS:
        ent = find(fs, fs.root_cluster, top)
        sub = find(fs, ent[2], tid) if ent else None
        if not sub or not sub[1] & ATTR_DIR:
            continue
        found = True
        base = f"{top}/{tid}"
        manifest["entries"].append({"path": base, "dir": True, "times": sub[4]})
        for rel, is_dir, size, times, first in walk(fs, sub[2]):
            path = f"{base}/{rel}"
            dest = os.path.join(outdir, *path.split("/"))
            if is_dir:
                os.makedirs(dest, exist_ok=True)
                manifest["entries"].append({"path": path, "dir": True, "times": times})
                continue
            data = fs.read_file(first, size) if size else b""
            if len(data) != size:
                raise SaveError(f"{path}: cluster chain ends at {len(data)} of {size} bytes")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as fh:
                fh.write(data)
            manifest["entries"].append({"path": path, "dir": False, "bytes": size,
                                        "sha256": hashlib.sha256(data).hexdigest(),
                                        "times": times})
    if not found:
        raise SaveError(f"{tid}: no E:/UDATA/{tid} or E:/TDATA/{tid} on {image_path}")
    manifest["save_id"] = save_id(manifest)
    with open(os.path.join(outdir, "save.json"), "w") as fh:
        json.dump(manifest, fh, indent=1, sort_keys=True)
    return manifest


def save_id(manifest):
    """Content id of a save: its paths and file hashes, not its times, so the
    same save pulled twice has one id."""
    h = hashlib.sha256()
    for e in sorted(manifest["entries"], key=lambda e: e["path"]):
        h.update(f"{e['path'].upper()}\0{e.get('sha256', 'dir')}\n".encode())
    return h.hexdigest()[:12]


# --------------------------------------------------------------- writing --

class SparseDisk:
    """A virtual disk as a dict of written 64 KiB blocks; the rest reads 0."""

    def __init__(self, size):
        self.size = size
        self.blocks = {}
        self.pos = 0

    def pwrite(self, offset, data):
        if offset + len(data) > self.size:
            raise SaveError("write past the end of the disk")
        while data:
            idx, within = divmod(offset, QCOW_CLUSTER)
            n = min(len(data), QCOW_CLUSTER - within)
            blk = self.blocks.get(idx)
            if blk is None:
                blk = self.blocks[idx] = bytearray(QCOW_CLUSTER)
            blk[within:within + n] = data[:n]
            data = data[n:]
            offset += n

    def read(self, offset, length):
        out = bytearray()
        while length > 0:
            idx, within = divmod(offset, QCOW_CLUSTER)
            n = min(length, QCOW_CLUSTER - within)
            blk = self.blocks.get(idx)
            out += blk[within:within + n] if blk is not None else bytes(n)
            offset += n
            length -= n
        return bytes(out)

    # enough of a file for make_xbox_hdd.write_partition
    def seek(self, offset):
        self.pos = offset

    def write(self, data):
        self.pwrite(self.pos, data)
        self.pos += len(data)


def fatx_now():
    t = time.localtime()
    d = (t.tm_mday & 0x1F) | ((t.tm_mon & 0x0F) << 5) | (((t.tm_year - 2000) & 0x7F) << 9)
    w = ((t.tm_hour & 0x1F) << 11) | ((t.tm_min & 0x3F) << 5) | ((t.tm_sec // 2) & 0x1F)
    return [w, d, w, d, w, d]


class FatxWriter:
    """Files and directories onto one freshly formatted FATX partition,
    allocated front to back. Mirrors what the kernel reads: 64-byte entries,
    0xFF end markers, a FAT chain per file, cluster N at
    cluster_offset + (N - 1) * bytes_per_cluster, the root at cluster 1."""

    def __init__(self, disk, plan):
        self.disk, self.p = disk, plan
        self.bpc = plan["bytes_per_cluster"]
        self.fat16 = plan["fat_is_16_bit"]
        self.nclusters = (plan["size"] - (plan["cluster_offset"] - plan["offset"])) // self.bpc
        self.next = 2
        self.fat = {}
        self.dirs = {1: []}          # dir cluster -> [raw entry bytes]
        self.index = {"": 1}         # upper-case path -> dir cluster

    def _alloc(self, n):
        if self.next + n > self.nclusters:
            raise SaveError("partition full")
        first = self.next
        self.next += n
        for c in range(first, first + n - 1):
            self.fat[c] = c + 1
        self.fat[first + n - 1] = 0xFFFF if self.fat16 else 0xFFFFFFFF
        return first

    def _addr(self, cluster):
        return self.p["cluster_offset"] + (cluster - 1) * self.bpc

    def _entry(self, name, attrs, first, size, times):
        raw = name.encode("latin-1")
        if not 0 < len(raw) <= er.MAX_FILENAME_LEN:
            raise SaveError(f"bad FATX name {name!r}")
        e = bytearray(b"\xFF" * DIRENT)
        e[0], e[1] = len(raw), attrs
        e[2:2 + len(raw)] = raw
        struct.pack_into("<II6H", e, 44, first, size, *times)
        return bytes(e)

    def mkdir(self, path, times=None):
        key = path.upper()
        if key in self.index:
            return self.index[key]
        parent, _, name = path.rpartition("/")
        pc = self.mkdir(parent) if parent else 1
        c = self._alloc(1)
        self.dirs[c] = []
        self.dirs[pc].append(self._entry(name, ATTR_DIR, c, 0, times or fatx_now()))
        self.index[key] = c
        return c

    def add_file(self, path, data, times=None):
        parent, _, name = path.rpartition("/")
        pc = self.mkdir(parent) if parent else 1
        first = 0
        if data:
            first = self._alloc(-(-len(data) // self.bpc))
            self.disk.pwrite(self._addr(first), data)
        self.dirs[pc].append(self._entry(name, 0, first, len(data), times or fatx_now()))

    def finish(self):
        per = self.bpc // DIRENT
        for c, entries in self.dirs.items():
            body = b"".join(entries)
            need = len(entries) // per + 1         # room for the end marker
            chain = [c]
            if need > 1:
                extra = self._alloc(need - 1)
                self.fat[c] = extra
                chain += list(range(extra, extra + need - 1))
            body += b"\xFF" * (need * self.bpc - len(body))
            for i, cl in enumerate(chain):
                self.disk.pwrite(self._addr(cl), body[i * self.bpc:(i + 1) * self.bpc])
        width = 2 if self.fat16 else 4
        fmt = "<H" if self.fat16 else "<I"
        for c, v in self.fat.items():
            self.disk.pwrite(self.p["offset"] + MK.FATX_FAT_OFFSET + c * width,
                             struct.pack(fmt, v))


def format_disk():
    disk = SparseDisk(VIRTUAL_SIZE)
    disk.pwrite(MK.REFURB_OFFSET, struct.pack("<I", MK.REFURB_SIGNATURE))
    spc = MK.FATX_RETAIL_CLUSTER_SIZE // MK.SECTOR_SIZE
    plans = {}
    for i, (letter, offset, size) in enumerate(MK.PARTITIONS):
        p = MK.plan_partition(i, letter, offset, size, spc)
        MK.write_partition(disk, p)
        plans[letter] = p
    return disk, plans


def write_qcow2(disk, path):
    """A qcow2 v3 image holding the disk's written blocks, laid out as
    qemu-img lays a fresh one out: header, refcount table, one refcount
    block, L1, then L2 tables and data."""
    used = sorted(i for i, b in disk.blocks.items() if any(b))
    l2_entries = QCOW_CLUSTER // 8
    l1_size = -(-disk.size // (QCOW_CLUSTER * l2_entries))
    l1_used = sorted({i // l2_entries for i in used})
    host = {}                               # guest block -> host cluster
    nxt = 4 + len(l1_used)
    for i in used:
        host[i] = nxt
        nxt += 1
    total = nxt
    if total > QCOW_CLUSTER // 2:
        raise SaveError("image too large for one refcount block")
    l2_host = {l1i: 4 + k for k, l1i in enumerate(l1_used)}

    hdr = bytearray(QCOW_CLUSTER)
    struct.pack_into(">IIQIIQIIQQIIQ", hdr, 0, 0x514649FB, 3, 0, 0,
                     QCOW_CLUSTER_BITS, disk.size, 0, l1_size, 3 * QCOW_CLUSTER,
                     1 * QCOW_CLUSTER, 1, 0, 0)
    struct.pack_into(">QQQII", hdr, 72, 0, 0, 0, 4, 104)   # refcount_order 4
    rct = bytearray(QCOW_CLUSTER)
    struct.pack_into(">Q", rct, 0, 2 * QCOW_CLUSTER)
    rcb = bytearray(QCOW_CLUSTER)
    for c in range(total):
        struct.pack_into(">H", rcb, c * 2, 1)
    l1 = bytearray(QCOW_CLUSTER)
    for l1i, hc in l2_host.items():
        struct.pack_into(">Q", l1, l1i * 8, (hc * QCOW_CLUSTER) | QCOW_COPIED)
    l2s = {l1i: bytearray(QCOW_CLUSTER) for l1i in l1_used}
    for i, hc in host.items():
        struct.pack_into(">Q", l2s[i // l2_entries], (i % l2_entries) * 8,
                         (hc * QCOW_CLUSTER) | QCOW_COPIED)
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        for blob in (hdr, rct, rcb, l1):
            fh.write(blob)
        for l1i in l1_used:
            fh.write(l2s[l1i])
        for i in used:
            fh.write(disk.blocks[i])
    os.replace(tmp, path)
    return total * QCOW_CLUSTER


def load_save(savedir):
    with open(os.path.join(savedir, "save.json")) as fh:
        m = json.load(fh)
    for e in m["entries"]:
        if e["dir"]:
            continue
        with open(os.path.join(savedir, *e["path"].split("/")), "rb") as fh:
            data = fh.read()
        if hashlib.sha256(data).hexdigest() != e["sha256"]:
            raise SaveError(f"{savedir}: {e['path']} does not match save.json")
        e["data"] = data
    return m


def build(out, savedirs):
    disk, plans = format_disk()
    w = FatxWriter(disk, plans["E"])
    seen = set()
    for sd in savedirs:
        m = load_save(sd)
        if m["title_id"] in seen:
            raise SaveError(f"two saves for {m['title_id']}")
        seen.add(m["title_id"])
        for e in sorted(m["entries"], key=lambda e: e["path"].count("/")):
            if e["dir"]:
                w.mkdir(e["path"], e["times"])
        for e in m["entries"]:
            if not e["dir"]:
                w.add_file(e["path"], e["data"], e["times"])
    w.finish()
    return write_qcow2(disk, out)


def verify(image_path, savedir):
    m = load_save(savedir)
    fs = open_e(image_path)
    bad = []
    for e in m["entries"]:
        cl, ent = fs.root_cluster, None
        for part in e["path"].split("/"):
            ent = find(fs, cl, part)
            if not ent:
                break
            cl = ent[2]
        if not ent:
            bad.append(f"missing {e['path']}")
        elif e["dir"] != bool(ent[1] & ATTR_DIR):
            bad.append(f"kind {e['path']}")
        elif not e["dir"]:
            data = fs.read_file(ent[2], ent[3]) if ent[3] else b""
            if data != e["data"]:
                bad.append(f"content {e['path']}")
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("list"); s.add_argument("image")
    s = sub.add_parser("pull"); s.add_argument("image"); s.add_argument("title_id"); s.add_argument("outdir")
    s = sub.add_parser("build"); s.add_argument("out"); s.add_argument("savedirs", nargs="*")
    s = sub.add_parser("verify"); s.add_argument("image"); s.add_argument("savedir")
    a = ap.parse_args(argv)
    t0 = time.monotonic()
    if a.cmd == "list":
        for tid, row in sorted(list_titles(open_e(a.image)).items()):
            u, t = row["UDATA"] or {}, row["TDATA"] or {}
            print(f"{tid}  UDATA {u.get('files', 0):3d} files {u.get('bytes', 0):9d} B"
                  f"  saves {','.join(u.get('saves') or []) or '-'}"
                  f"   TDATA {t.get('files', 0):3d} files {t.get('bytes', 0):9d} B")
    elif a.cmd == "pull":
        os.makedirs(a.outdir, exist_ok=True)
        m = pull(a.image, a.title_id, a.outdir)
        nfiles = sum(1 for e in m["entries"] if not e["dir"])
        print(f"pulled {m['title_id']} save {m['save_id']}: {nfiles} files, "
              f"{sum(e.get('bytes', 0) for e in m['entries'])} B, "
              f"{time.monotonic() - t0:.2f} s")
    elif a.cmd == "build":
        n = build(a.out, a.savedirs)
        print(f"built {a.out}: {n} B, {len(a.savedirs)} save(s), {time.monotonic() - t0:.2f} s")
    elif a.cmd == "verify":
        bad = verify(a.image, a.savedir)
        for b in bad:
            print("  " + b)
        print("verify: " + ("OK" if not bad else f"{len(bad)} mismatches"))
        return 1 if bad else 0
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (SaveError, er.ExtractError) as err:
        print(f"saves.py: {err}", file=sys.stderr)
        sys.exit(1)
