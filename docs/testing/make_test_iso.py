#!/usr/bin/env python3
"""Write a runtime config into a stock nxdk_pgraph_tests disc image.

The test suite reads ``d:\\nxdk_pgraph_tests_config.json`` from the disc it
booted from, and the released disc image does not carry one.  Without it the
suite runs every test with its defaults: results are written to the emulated
Xbox hard disk and nothing else, which on Android means they are sealed inside
``hdd.img``.

This adds that file to a copy of the image, so a run can be pointed at an FTP
server, sharded, or trimmed to a few suites.  Nothing already on the disc is
moved: the new file and a rebuilt root directory table are appended, and the
volume descriptor is repointed at the new table.

See pgraph-harness.md for how the resulting image is used.
"""

import argparse
import json
import struct
import sys

SECTOR = 2048
MAGIC = b"MICROSOFT*XBOX*MEDIA"
HEADER_SECTOR = 32  # 0x10000
CONFIG_NAME = "nxdk_pgraph_tests_config.json"
ATTR_DIRECTORY = 0x10
ATTR_ARCHIVE = 0x20


class XisoError(Exception):
    pass


def _entry_size(name):
    """Size on disc of one directory entry, padded to a 4-byte boundary."""
    return (14 + len(name) + 3) & ~3


def _name_key(name):
    """The order the Xbox kernel expects directory entries in.

    Uppercase ASCII byte comparison, with a shorter name sorting first when it
    is a prefix of a longer one.  Confirmed against the in-order traversal of
    the released image rather than assumed.  Only a-z is folded: the kernel
    does not do Unicode case mapping, and Python's str.upper() would change
    the length of some latin-1 names.
    """
    encoded = bytearray(name.encode("latin-1"))
    for index, byte in enumerate(encoded):
        if 0x61 <= byte <= 0x7A:
            encoded[index] = byte - 0x20
    return bytes(encoded)


def read_header(data):
    off = HEADER_SECTOR * SECTOR
    if data[off:off + 20] != MAGIC:
        raise XisoError(
            "no 'MICROSOFT*XBOX*MEDIA' signature at 0x%X. Only plain XISO images "
            "are supported; redump-style images with a 0x18300000 offset are not." % off)
    root_sector, root_size = struct.unpack_from("<II", data, off + 20)
    return root_sector, root_size


def read_directory(data, sector, size):
    """Return the entries of one directory table, in tree order."""
    base = sector * SECTOR
    table = data[base:base + size]
    entries = []

    def walk(offset):
        pos = offset * 4
        if pos + 14 > len(table):
            raise XisoError("directory entry at offset %d runs past the table" % pos)
        left, right, start, length, attributes = struct.unpack_from("<HHIIB", table, pos)
        name_length = table[pos + 13]
        name = table[pos + 14:pos + 14 + name_length].decode("latin-1")
        if left:
            walk(left)
        entries.append((name, start, length, attributes))
        if right:
            walk(right)

    if size:
        walk(0)
    return entries


def build_directory(entries):
    """Lay out a directory table as a binary search tree.

    Entries are linked into a balanced tree over the sorted names, then written
    out in pre-order, which puts the tree's root at offset 0 where the kernel
    looks for it.  The shape does not have to match what extract-xiso would
    produce -- the kernel descends the tree comparing names, so any correctly
    ordered tree resolves the same lookups -- but the ordering does.

    An entry is never allowed to straddle a sector boundary; the gap is filled
    with 0xFF, which is what extract-xiso emits.
    """
    entries = sorted(entries, key=lambda e: _name_key(e[0]))
    for name, _start, _length, _attributes in entries:
        if len(name.encode("latin-1")) > 255:
            raise XisoError("%r is too long for a directory entry" % name)

    children = [(None, None)] * len(entries)

    def shape(low, high):
        if low >= high:
            return None
        mid = (low + high) // 2
        children[mid] = (shape(low, mid), shape(mid + 1, high))
        return mid

    root = shape(0, len(entries))
    if root is None:
        raise XisoError("refusing to write an empty directory")

    offsets = [0] * len(entries)
    cursor = 0

    def place(index):
        nonlocal cursor
        size = _entry_size(entries[index][0])
        if (cursor % SECTOR) + size > SECTOR:
            cursor += SECTOR - (cursor % SECTOR)
        offsets[index] = cursor
        cursor += size
        for child in children[index]:
            if child is not None:
                place(child)

    place(root)
    if offsets[root] != 0:
        raise XisoError("root entry did not land at offset 0")
    total = cursor

    table = bytearray(b"\xff" * total)
    for index, (name, start, length, attributes) in enumerate(entries):
        left, right = children[index]
        encoded = name.encode("latin-1")
        struct.pack_into("<HHIIBB", table, offsets[index],
                         0 if left is None else offsets[left] // 4,
                         0 if right is None else offsets[right] // 4,
                         start, length, attributes, len(encoded))
        table[offsets[index] + 14:offsets[index] + 14 + len(encoded)] = encoded
    return bytes(table), total


def default_config(args):
    return {
        "settings": {
            "enable_progress_log": args.progress_log,
            "disable_autorun": not args.autorun,
            "enable_autorun_immediately": args.autorun and args.autorun_immediately,
            "enable_shutdown_on_completion": args.shutdown_on_completion,
            "enable_pgraph_region_diff": False,
            "skip_tests_by_default": bool(args.suite),
            "delay_milliseconds_between_tests": args.delay_between_tests,
            "delay_milliseconds_before_exit": args.delay_before_exit,
            "network": {
                "enable": bool(args.ftp_host),
                "config_automatic": False,
                "config_dhcp": bool(args.ftp_host),
                "static_ip": "",
                "static_netmask": "",
                "static_gateway": "",
                "static_dns_1": "",
                "static_dns_2": "",
                "ftp": {
                    "ftp_ip": args.ftp_host or "",
                    "ftp_port": args.ftp_port,
                    "ftp_user": args.ftp_user,
                    "ftp_password": args.ftp_password,
                    "ftp_timeout_milliseconds": args.ftp_timeout,
                },
            },
            "sharding": {"index": args.shard_index, "count": args.shard_count},
            "output_directory_path": args.output_dir,
        },
        # Naming a suite switches the disc to opt-in: skip_tests_by_default
        # above flips, and only these run. The value must be {"skipped": False}
        # -- a per-test dict looks reasonable and silently runs nothing, which
        # cost a device round trip to notice.
        "test_suites": {name: {"skipped": False} for name in args.suite},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iso", help="stock nxdk_pgraph_tests_xiso.iso")
    parser.add_argument("-o", "--output", required=True, help="image to write")
    parser.add_argument("--config", metavar="FILE",
                        help="use this JSON verbatim instead of generating one "
                             "(start from the sample-config.json on the disc to "
                             "skip individual suites or tests)")

    ftp = parser.add_argument_group("FTP upload")
    ftp.add_argument("--ftp-host", metavar="IP",
                     help="IPv4 address of an FTP server to upload results to. "
                          "Enables guest networking; without it results only "
                          "reach the emulated hard disk.")
    ftp.add_argument("--ftp-port", type=int, default=21)
    ftp.add_argument("--ftp-user", default="xbox")
    ftp.add_argument("--ftp-password", default="xbox")
    ftp.add_argument("--ftp-timeout", type=int, default=10000,
                     metavar="MS", help="default: 10000")

    run = parser.add_argument_group("run behaviour")
    run.add_argument("--suite", action="append", default=[], metavar="NAME",
                     help="run only this suite, repeatable. Names use spaces, "
                          "not underscores (\"Bump map\", not \"Bump_map\") -- "
                          "the underscored form is the results directory. "
                          "Without this the disc runs everything.")
    run.add_argument("--output-dir", default="e:/nxdk_pgraph_tests",
                     help="where the suite writes results on the guest "
                          "(default: %(default)s). Must be on a writable drive.")
    run.add_argument("--no-autorun", dest="autorun", action="store_false",
                     help="stop at the menu instead of running every test")
    run.add_argument("--no-autorun-immediately", dest="autorun_immediately",
                     action="store_false",
                     help="wait out the menu countdown before starting")
    run.add_argument("--shutdown-on-completion", action="store_true",
                     help="power off when finished instead of rebooting")
    run.add_argument("--progress-log", action="store_true",
                     help="write a progress log next to the results")
    run.add_argument("--delay-between-tests", type=int, default=0, metavar="MS")
    run.add_argument("--delay-before-exit", type=int, default=4000, metavar="MS")
    run.add_argument("--shard-index", type=int, default=0)
    run.add_argument("--shard-count", type=int, default=0,
                     help="split the run across N discs (0 disables sharding)")

    args = parser.parse_args(argv)

    if args.shard_count and args.shard_index >= args.shard_count:
        parser.error("--shard-index must be less than --shard-count")

    if args.config:
        with open(args.config, "r", encoding="utf-8") as handle:
            config = json.load(handle)
    else:
        config = default_config(args)
    payload = json.dumps(config, indent=2).encode("utf-8")

    with open(args.iso, "rb") as handle:
        data = bytearray(handle.read())

    root_sector, root_size = read_header(data)
    entries = read_directory(data, root_sector, root_size)
    names = {name.lower(): name for name, _s, _l, _a in entries}
    if CONFIG_NAME.lower() in names:
        entries = [e for e in entries if e[0].lower() != CONFIG_NAME.lower()]
        print("replacing the existing %s" % names[CONFIG_NAME.lower()])

    # Append the payload, then the rebuilt root table, on fresh sectors.
    if len(data) % SECTOR:
        data.extend(b"\x00" * (SECTOR - len(data) % SECTOR))
    payload_sector = len(data) // SECTOR
    data.extend(payload)
    if len(data) % SECTOR:
        data.extend(b"\x00" * (SECTOR - len(data) % SECTOR))

    entries.append((CONFIG_NAME, payload_sector, len(payload), ATTR_ARCHIVE))
    table, table_size = build_directory(entries)

    table_sector = len(data) // SECTOR
    data.extend(table)
    if len(data) % SECTOR:
        data.extend(b"\x00" * (SECTOR - len(data) % SECTOR))

    struct.pack_into("<II", data, HEADER_SECTOR * SECTOR + 20, table_sector, table_size)

    with open(args.output, "wb") as handle:
        handle.write(data)

    verify(args.output, payload)
    print("wrote %s (%.1f MiB), %s is %d bytes"
          % (args.output, len(data) / (1 << 20), CONFIG_NAME, len(payload)))
    return 0


def lookup(data, sector, size, name):
    """Resolve a name the way the kernel does: a descent of the entry tree.

    Listing the directory in order only proves the entries are sorted.  This
    proves the file is actually reachable, which is what a boot depends on.
    """
    base = sector * SECTOR
    table = data[base:base + size]
    target = _name_key(name)
    offset = 0
    while True:
        pos = offset * 4
        left, right, start, length, attributes = struct.unpack_from("<HHIIB", table, pos)
        entry = table[pos + 14:pos + 14 + table[pos + 13]].decode("latin-1")
        key = _name_key(entry)
        if target == key:
            return start, length, attributes
        offset = left if target < key else right
        if not offset:
            return None


def verify(path, expected_payload):
    """Re-read the image we just wrote and check it round-trips."""
    with open(path, "rb") as handle:
        data = handle.read()
    root_sector, root_size = read_header(data)
    entries = read_directory(data, root_sector, root_size)

    names = [name for name, _s, _l, _a in entries]
    if names != sorted(names, key=_name_key):
        raise XisoError("rebuilt root directory is not in tree order: %r" % names)

    for name, start, length, _attributes in entries:
        found = lookup(data, root_sector, root_size, name)
        if found is None:
            raise XisoError("%r is in the table but a tree descent cannot find it" % name)
        if found[:2] != (start, length):
            raise XisoError("%r resolves to the wrong extent" % name)

    found = lookup(data, root_sector, root_size, CONFIG_NAME)
    start, length, _attributes = found
    written = data[start * SECTOR:start * SECTOR + length]
    if written != expected_payload:
        raise XisoError("%s did not round-trip" % CONFIG_NAME)
    json.loads(written)  # catches truncation; the guest parser is stricter


if __name__ == "__main__":
    try:
        sys.exit(main())
    except XisoError as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
