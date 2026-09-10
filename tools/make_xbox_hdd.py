#!/usr/bin/env python3
"""Create a blank, FATX-formatted Xbox hard disk image.

The Android app can already do this - Settings has a "recreate HDD" button
wired to XboxHddFormatter.kt and, under it,
android/app/src/main/cpp/xemu_hdd_tools_jni.c. Nothing equivalent existed off
the device, which meant a desktop or CI run had no way to produce the one
asset the BIOS refuses to boot without. (It does refuse: with no disk the
console POSTs to the multilingual "Your Xbox requires service" screen and
never looks at the DVD.)

This is a direct port of android_xbox_hdd_format_partition() and the
functions it calls. It writes only the FATX structures - a superblock, the
first two FAT entries and an empty root directory per partition - so the
result contains no Microsoft code or data of any kind, and can be generated
freely by anyone.

The image is created sparse. A retail layout is 7.45 GiB nominal but costs a
few hundred KiB on disk until something writes to it.

    tools/make_xbox_hdd.py hdd.img

Cross-check against the device path in xemu_hdd_tools_jni.c if you change
anything here; the two must agree or an image made on one will confuse the
other.
"""

import argparse
import os
import random
import struct
import sys

SECTOR_SIZE = 512
FATX_SIGNATURE = 0x58544146           # "FATX"
FATX_SUPERBLOCK_SIZE = 4096
FATX_FAT_OFFSET = FATX_SUPERBLOCK_SIZE
FATX_RESERVED_ENTRY_COUNT = 1
FATX_RETAIL_CLUSTER_SIZE = 16 * 1024
FATX_END_OF_DIR_MARKER = 0xFF
FATX_CLUSTER_MEDIA_16, FATX_CLUSTER_END_16 = 0xFFF8, 0xFFFF
FATX_CLUSTER_MEDIA_32, FATX_CLUSTER_END_32 = 0xFFFFFFF8, 0xFFFFFFFF
REFURB_OFFSET = 0x600
REFURB_SIGNATURE = 0x42524652
MINIMUM_RETAIL_DISK_BYTES = 0x1DD156000

# letter, offset, size - the fixed retail layout. The Xbox kernel hardcodes
# these; there is no partition table on the disk to read them from.
PARTITIONS = [
    ("X", 0x00080000, 0x02EE00000),
    ("Y", 0x2EE80000, 0x02EE00000),
    ("Z", 0x5DC80000, 0x02EE00000),
    ("C", 0x8CA80000, 0x01F400000),
    ("E", 0xABE80000, 0x1312D6000),
]


def plan_partition(index, letter, offset, size, sectors_per_cluster):
    bytes_per_cluster = sectors_per_cluster * SECTOR_SIZE
    fat_entries = size // bytes_per_cluster + FATX_RESERVED_ENTRY_COUNT
    fat_is_16_bit = fat_entries < 0xFFF0
    fat_length = fat_entries * (2 if fat_is_16_bit else 4)
    if fat_length % FATX_SUPERBLOCK_SIZE:
        fat_length += FATX_SUPERBLOCK_SIZE - (fat_length % FATX_SUPERBLOCK_SIZE)
    if FATX_FAT_OFFSET + fat_length + bytes_per_cluster > size:
        sys.exit("partition %s is too small for the selected layout" % letter)
    return {
        "letter": letter,
        "offset": offset,
        "size": size,
        "volume_id": random.getrandbits(32) ^ index ^ ord(letter),
        "sectors_per_cluster": sectors_per_cluster,
        "bytes_per_cluster": bytes_per_cluster,
        "fat_is_16_bit": fat_is_16_bit,
        "fat_length": fat_length,
        "cluster_offset": offset + FATX_FAT_OFFSET + fat_length,
    }


def write_partition(fh, p):
    # Superblock: 0xFF-filled, then the header fields.
    sb = bytearray(b"\xFF" * FATX_SUPERBLOCK_SIZE)
    struct.pack_into("<I", sb, 0, FATX_SIGNATURE)
    struct.pack_into("<I", sb, 4, p["volume_id"])
    struct.pack_into("<I", sb, 8, p["sectors_per_cluster"])
    struct.pack_into("<I", sb, 12, 1)          # root directory cluster
    struct.pack_into("<H", sb, 16, 0)
    fh.seek(p["offset"])
    fh.write(sb)

    # The first two FAT entries. Everything after them stays zero, which a
    # sparse file gives for free.
    if p["fat_is_16_bit"]:
        entries = struct.pack("<HH", FATX_CLUSTER_MEDIA_16, FATX_CLUSTER_END_16)
    else:
        entries = struct.pack("<II", FATX_CLUSTER_MEDIA_32, FATX_CLUSTER_END_32)
    fh.seek(p["offset"] + FATX_FAT_OFFSET)
    fh.write(entries)

    # An empty root directory is one cluster of end-of-directory markers.
    fh.seek(p["cluster_offset"])
    fh.write(bytes([FATX_END_OF_DIR_MARKER]) * p["bytes_per_cluster"])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", help="image file to create")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing file")
    args = ap.parse_args()

    if os.path.exists(args.path) and not args.force:
        sys.exit("%s exists; pass --force to overwrite" % args.path)

    total = MINIMUM_RETAIL_DISK_BYTES
    spc = FATX_RETAIL_CLUSTER_SIZE // SECTOR_SIZE

    with open(args.path, "wb") as fh:
        fh.truncate(total)                     # sparse
        # Refurb info, which the kernel looks for near the head of the disk.
        fh.seek(REFURB_OFFSET)
        fh.write(struct.pack("<I", REFURB_SIGNATURE))
        for i, (letter, offset, size) in enumerate(PARTITIONS):
            p = plan_partition(i, letter, offset, size, spc)
            write_partition(fh, p)
            print("  %s: offset 0x%09X  %6.2f GiB  %d-bit FAT  cluster %d B"
                  % (letter, offset, size / 2**30,
                     16 if p["fat_is_16_bit"] else 32, p["bytes_per_cluster"]))

    st = os.stat(args.path)
    print("wrote %s" % args.path)
    print("  nominal %.2f GiB, actually %d KiB on disk"
          % (total / 2**30, st.st_blocks * 512 // 1024))


if __name__ == "__main__":
    main()
