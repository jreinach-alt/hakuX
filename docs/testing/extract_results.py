#!/usr/bin/env python3
"""Pull nxdk_pgraph_tests results out of an Android ``hdd.img``.

The suite writes its captured framebuffers to ``e:\\nxdk_pgraph_tests`` on the
emulated Xbox hard disk.  On Android that disk is a qcow2 file inside the app's
private storage, so the results are reachable only by reading the image
host-side: the emulator's own FATX code is compiled into the app and shaped for
dashboard import, and Settings' "export HDD" is a byte-for-byte copy that
performs no conversion or extraction.

This reads the qcow2 directly (no qemu-img needed), walks the FATX filesystem
on the E: partition, and writes the files out.  The layout constants and the
on-disk structures are taken from the in-tree implementation in
``android/app/src/main/cpp/xemu_fatx_import.c`` rather than re-derived.

    python3 docs/testing/extract_results.py hdd.img -o ./ftpdump

The output is flat, matching what the FTP upload path produces, so
``collect_results.py`` can consume it unchanged.
"""

import argparse
import datetime
import os
import struct
import sys

SECTOR_SIZE = 512
SUPERBLOCK_SIZE = 4096
FAT_OFFSET = SUPERBLOCK_SIZE
FAT_RESERVED_ENTRIES = 1
FATX_SIGNATURE = 0x58544146  # 'FATX'
MAX_FILENAME_LEN = 42
END_OF_DIR = 0xFF
END_OF_DIR2 = 0x00
DELETED_FILE = 0xE5
ATTR_DIRECTORY = 1 << 4

# android/app/src/main/cpp/xemu_hdd_tools_jni.c:88
PARTITIONS = {
    "X": (0x00080000, 0x02EE00000),
    "Y": (0x2EE80000, 0x02EE00000),
    "Z": (0x5DC80000, 0x02EE00000),
    "C": (0x8CA80000, 0x01F400000),
    "E": (0xABE80000, 0x1312D6000),
}



def _fatx_time(date_word, time_word):
    """Decode a FATX timestamp to a naive datetime (epoch 2000)."""
    year = 2000 + ((date_word >> 9) & 0x7F)
    month = (date_word >> 5) & 0x0F
    day = date_word & 0x1F
    hour = (time_word >> 11) & 0x1F
    minute = (time_word >> 5) & 0x3F
    second = (time_word & 0x1F) * 2
    try:
        return datetime.datetime(year, max(month, 1), max(day, 1), hour, minute,
                                 min(second, 59))
    except ValueError:
        return None


class ExtractError(Exception):
    pass


class Qcow2:
    """Minimal read-only qcow2 v2/v3 reader.

    Only what is needed here: a single image with no backing file and no
    compression or encryption.  Unallocated clusters read as zeroes, which is
    what the FATX layer expects of untouched areas of the disk.
    """

    def __init__(self, path):
        self.f = open(path, "rb")
        magic, version = struct.unpack(">II", self._read_at(0, 8))
        if magic != 0x514649FB:
            raise ExtractError(f"{path} is not a qcow2 image")
        if version not in (2, 3):
            raise ExtractError(f"unsupported qcow2 version {version}")
        header = self._read_at(0, 72)
        (backing_offset, backing_size, cluster_bits, self.size,
         crypt_method, l1_size, l1_offset) = struct.unpack(
            ">QIIQIIQ", header[8:48])
        if backing_offset:
            raise ExtractError("backing files are not supported")
        if crypt_method:
            raise ExtractError("encrypted images are not supported")
        self.cluster_bits = cluster_bits
        self.cluster_size = 1 << cluster_bits
        self.l2_bits = cluster_bits - 3
        self.l2_size = 1 << self.l2_bits
        self.l1 = struct.unpack(
            f">{l1_size}Q", self._read_at(l1_offset, l1_size * 8)) if l1_size else ()
        self._l2_cache = {}

    def _read_at(self, offset, length):
        self.f.seek(offset)
        data = self.f.read(length)
        if len(data) != length:
            raise ExtractError(f"short read at 0x{offset:x}")
        return data

    def _l2_table(self, l2_offset):
        if l2_offset not in self._l2_cache:
            raw = self._read_at(l2_offset, self.l2_size * 8)
            self._l2_cache[l2_offset] = struct.unpack(f">{self.l2_size}Q", raw)
        return self._l2_cache[l2_offset]

    def _cluster(self, index):
        """Host offset of guest cluster `index`, or None if unallocated."""
        l1_index = index >> self.l2_bits
        if l1_index >= len(self.l1):
            return None
        l2_offset = self.l1[l1_index] & 0x00FFFFFFFFFFFE00
        if not l2_offset:
            return None
        entry = self._l2_table(l2_offset)[index & (self.l2_size - 1)]
        if entry & (1 << 62):
            raise ExtractError("compressed clusters are not supported")
        offset = entry & 0x00FFFFFFFFFFFE00
        return offset or None

    def read(self, offset, length):
        out = bytearray()
        while length > 0:
            index = offset >> self.cluster_bits
            within = offset & (self.cluster_size - 1)
            chunk = min(length, self.cluster_size - within)
            host = self._cluster(index)
            out += (self._read_at(host + within, chunk) if host
                    else b"\0" * chunk)
            offset += chunk
            length -= chunk
        return bytes(out)


class Fatx:
    def __init__(self, image, part_offset, part_size):
        self.image = image
        self.offset = part_offset
        sb = image.read(part_offset, 18)
        signature, volume_id, sectors_per_cluster, root_cluster = \
            struct.unpack("<IIII", sb[:16])
        if signature != FATX_SIGNATURE:
            raise ExtractError(
                f"partition at 0x{part_offset:x} is not formatted as FATX")
        self.bytes_per_cluster = sectors_per_cluster * SECTOR_SIZE
        if not self.bytes_per_cluster or sectors_per_cluster > 1024:
            raise ExtractError("invalid FATX cluster size")

        fat_entries = part_size // self.bytes_per_cluster + FAT_RESERVED_ENTRIES
        self.fat_type = 16 if fat_entries < 0xFFF0 else 32
        fat_size = fat_entries * (2 if self.fat_type == 16 else 4)
        if fat_size % SUPERBLOCK_SIZE:
            fat_size += SUPERBLOCK_SIZE - (fat_size % SUPERBLOCK_SIZE)

        self.fat_entry_count = fat_entries
        self.fat_offset = part_offset + FAT_OFFSET
        self.cluster_offset = self.fat_offset + fat_size
        self.root_cluster = root_cluster
        if not (FAT_RESERVED_ENTRIES <= root_cluster < fat_entries):
            raise ExtractError("invalid FATX root cluster")
        self._fat = None

    def _fat_entry(self, index):
        if self._fat is None:
            width = 2 if self.fat_type == 16 else 4
            raw = self.image.read(self.fat_offset, self.fat_entry_count * width)
            fmt = "<%d%s" % (self.fat_entry_count, "H" if width == 2 else "I")
            self._fat = struct.unpack(fmt, raw[:self.fat_entry_count * width])
        return self._fat[index]

    def _is_end(self, entry):
        return entry >= (0xFFF8 if self.fat_type == 16 else 0xFFFFFFF8)

    def _chain(self, cluster):
        seen = set()
        while cluster and not self._is_end(cluster):
            if cluster in seen or cluster >= self.fat_entry_count:
                raise ExtractError("corrupt FATX cluster chain")
            seen.add(cluster)
            yield cluster
            cluster = self._fat_entry(cluster)

    def _cluster_bytes(self, cluster):
        start = self.cluster_offset + (cluster - 1) * self.bytes_per_cluster
        return self.image.read(start, self.bytes_per_cluster)

    def listdir(self, cluster):
        """Yield (name, attributes, first_cluster, size, mtime) for one directory."""
        for chain_cluster in self._chain(cluster):
            data = self._cluster_bytes(chain_cluster)
            for pos in range(0, len(data), 64):
                entry = data[pos:pos + 64]
                if len(entry) < 64:
                    return
                name_len = entry[0]
                if name_len in (END_OF_DIR, END_OF_DIR2):
                    return
                if name_len == DELETED_FILE or name_len > MAX_FILENAME_LEN:
                    continue
                attributes = entry[1]
                name = entry[2:2 + name_len].decode("latin-1")
                first_cluster, size = struct.unpack("<II", entry[44:52])
                mtime, mdate = struct.unpack("<HH", entry[52:56])
                yield name, attributes, first_cluster, size, _fatx_time(mdate, mtime)

    def read_file(self, first_cluster, size):
        out = bytearray()
        for cluster in self._chain(first_cluster):
            out += self._cluster_bytes(cluster)
            if len(out) >= size:
                break
        return bytes(out[:size])

    def resolve(self, path):
        """Resolve a '/'-separated path to (attributes, cluster, size)."""
        cluster, attributes, size = self.root_cluster, ATTR_DIRECTORY, 0
        for part in [p for p in path.split("/") if p]:
            if not attributes & ATTR_DIRECTORY:
                raise ExtractError(f"{path}: {part} is not inside a directory")
            for name, attrs, first, sz, _mt in self.listdir(cluster):
                if name.lower() == part.lower():
                    cluster, attributes, size = first, attrs, sz
                    break
            else:
                raise ExtractError(f"{path}: {part} not found")
        return attributes, cluster, size


def extract(fs, cluster, out_dir, prefix="", newer_than=None):
    count = total = 0
    os.makedirs(out_dir, exist_ok=True)
    for name, attributes, first, size, mtime in fs.listdir(cluster):
        if attributes & ATTR_DIRECTORY:
            sub, subtotal = extract(fs, first, out_dir, prefix + name + "::",
                                    newer_than)
            count += sub
            total += subtotal
            continue
        if not size:
            print(f"  skipping empty {prefix}{name}")
            continue
        if newer_than is not None and (mtime is None or mtime < newer_than):
            continue
        data = fs.read_file(first, size)
        with open(os.path.join(out_dir, prefix + name), "wb") as handle:
            handle.write(data)
        count += 1
        total += len(data)
    return count, total


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image", help="hdd.img (qcow2 or raw)")
    parser.add_argument("-o", "--output", default="./results",
                        help="directory to write files into (default: %(default)s)")
    parser.add_argument("-p", "--partition", default="E", choices=sorted(PARTITIONS),
                        help="partition to read (default: %(default)s)")
    parser.add_argument("-d", "--dir", default="nxdk_pgraph_tests",
                        help="directory on that partition (default: %(default)s)")
    parser.add_argument("--newer-than", metavar="ISO8601",
                        help="only extract files modified at or after this "
                             "time, e.g. 2026-09-07T18:30 . The results "
                             "directory accumulates across runs, so this is "
                             "how a single run's output is isolated.")
    parser.add_argument("--list", action="store_true",
                        help="list the directory instead of extracting")
    args = parser.parse_args(argv)

    offset, size = PARTITIONS[args.partition]
    image = Qcow2(args.image)
    fs = Fatx(image, offset, size)
    print(f"{args.partition}: FATX, {fs.bytes_per_cluster} B/cluster, "
          f"FAT{fs.fat_type}, root cluster {fs.root_cluster}")

    attributes, cluster, _size = fs.resolve(args.dir)
    if not attributes & ATTR_DIRECTORY:
        raise ExtractError(f"{args.dir} is not a directory")

    if args.list:
        for name, attrs, _first, sz, _mt in fs.listdir(cluster):
            kind = "dir " if attrs & ATTR_DIRECTORY else "file"
            print(f"  {kind} {sz:>10}  {_mt}  {name}")
        return 0

    cutoff = (datetime.datetime.fromisoformat(args.newer_than)
              if args.newer_than else None)
    count, total = extract(fs, cluster, args.output, newer_than=cutoff)
    print(f"extracted {count} files ({total / (1 << 20):.1f} MiB) to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ExtractError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
