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

``--program vsh`` does the same for nxdk_vsh_tests, whose config is not JSON:
``d:\\vsh_tests.cnf``, one suite name per line. That program ASSERTs and waits
forever when the file is missing (debug_output.cpp PrintAssertAndWaitForever),
and runs EVERY suite when the file names none it knows -- so a vsh disc is
written only with a cnf naming known suites, never with the pgraph JSON, and
``--inspect`` says whether an image will run to completion before anything is
queued for it.
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

# nxdk_vsh_tests. The suite names are the program's own Name() strings, as its
# DUMP_CONFIG_FILE build writes them and as the 2026-09-25 console cnfs used
# them (main.cpp register_suites, hakux/completion-marker @ c3dde45). The list
# is closed on purpose: process_config() keeps only suites it recognises and,
# when that leaves none, runs ALL of them -- a typo is a full-program run
# filed as the one suite that was asked for.
VSH_CNF_NAME = "vsh_tests.cnf"
VSH_SUITES = (
    "AmericasArmyShader",
    "CPU Shader Tests",
    "Exceptional Float",
    "ILU RCP Tests",
    "MAC Add Tests",
    "MAC mov",
    "Paired ILU Tests",
    "SpyVsSpy",
    "Vertex Data Array Format Tests",
)
# Strings in default.xbe that say which program a disc carries and how it ends.
# RUNTIME_CONFIG_PATH is compiled in as a literal, so each program names its
# own config file. The reboot message exists only in a build without
# ENABLE_SHUTDOWN (main.cpp's #else branch), and on hakuX a guest reboot boots
# the same disc again: the program reruns until the run's timeout, the way a
# pgraph disc without --shutdown-on-completion did (overnight-2026-09-12-log.md).
XBE_VSH_MARK = b"d:\\vsh_tests.cnf"
XBE_PGRAPH_MARK = CONFIG_NAME.encode()
XBE_VSH_REBOOTS = b"Rebooting in 4 seconds"


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
        # cost a device round trip to notice. A per-test skip is therefore
        # {"skipped": False, "<Test>": {"skipped": True}}: the suite-level
        # False must stay, or the whole suite goes quiet.
        "test_suites": _suites_with_skips(args),
    }


def _suites_with_skips(args):
    """Build ``test_suites``, honouring ``--skip-test "Suite::Test"``.

    One test in a suite can poison every test that runs after it, so a disc
    that cannot express "this suite, without that test" cannot measure such a
    suite at all. `Texture render target` is the standing case: its
    `RenderTextureLoop` ends with ``texture_stage.SetEnabled(false)`` and
    ``SetShaderStageProgram(STAGE_NONE)``, the 40 `TexFmt_*` tests rely on the
    suite's `Initialize()` rather than setting the stage themselves, and
    `RunAll` walks a `std::map` alphabetically so the loop goes first. Every
    later test then renders its quad with no texture stage -- flat black over
    the whole 285x285 quad, 81,225 px each.

    That is not a rendering defect and it is not run-to-run noise; it is the
    disc composition. Measured 2026-09-12 against the same goldens and the
    same build, the gap between the two discs is 9.9x:

        loop included   41 captures, 1 exact, 3,209,634 px
        loop skipped    40 captures, 5 exact,   324,349 px

    so a suite request that cannot skip the loop reports an order of magnitude
    that is entirely an artefact of its own disc.
    """
    suites = {name: {"skipped": False} for name in args.suite}

    # --only-test is the ALLOW-LIST, and its shape is the inverse of a skip:
    # the suite goes to {"skipped": True} and each named test to
    # {"skipped": False}. That is not a guess. runtime_config.cpp resolves it
    # in ApplyConfig: `default_skip_test_case` starts at
    # `skip_tests_by_default_`, a suite-level entry overrides it, and then a
    # per-test explicit entry overrides THAT --
    #
    #     skip_test_case = explicit_config->second == SkipConfiguration::SKIPPED
    #
    # so a per-test False beats a suite-level True. `ParseTestCases` reads the
    # literal key "skipped" as the suite's own setting and every other key as a
    # test name whose value must be an object. And `ApplyConfig` drops a suite
    # with no enabled tests entirely, which is why naming only tests that do
    # not exist yields an empty disc rather than a full one.
    #
    # It is written this way round because the obvious spelling silently runs
    # NOTHING, which the comment above records having already cost a device
    # round trip once.
    only = {}
    for spec in args.only_test:
        suite, _, test = spec.partition("::")
        if not test:
            raise SystemExit("--only-test wants \"Suite::Test\", got %r" % spec)
        suite = suite.replace("_", " ")
        if suite not in suites:
            raise SystemExit(
                "--only-test names %r, which is not among the --suite names: %s"
                % (suite, ", ".join(sorted(suites)) or "(none)"))
        only.setdefault(suite, []).append(test)
    for suite, tests in only.items():
        # Refuse the combination rather than pick a winner. Both flags resolve
        # through the same per-test map, so "only A, skipping A" is a request
        # with no meaning and "only A, skipping B" is a longer way of writing
        # "only A" -- either way the requester believes something the disc does
        # not do.
        if any(sp.partition("::")[0].replace("_", " ") == suite
               for sp in args.skip_test):
            raise SystemExit(
                "--only-test and --skip-test both name %r; they resolve through "
                "the same per-test map, so combining them cannot mean what it "
                "looks like. Use one." % suite)
        suites[suite] = {"skipped": True}
        for test in tests:
            suites[suite][test] = {"skipped": False}

    for spec in args.skip_test:
        suite, _, test = spec.partition("::")
        if not test:
            raise SystemExit("--skip-test wants \"Suite::Test\", got %r" % spec)
        # Underscores are the results-directory spelling; the disc wants
        # spaces, the same rule --suite documents.
        suite = suite.replace("_", " ")
        if suite not in suites:
            raise SystemExit(
                "--skip-test names %r, which is not among the --suite names: %s"
                % (suite, ", ".join(sorted(suites)) or "(none)"))
        suites[suite][test] = {"skipped": True}
    return suites


def vsh_cnf(args):
    """The vsh_tests.cnf payload for ``--program vsh``, or SystemExit.

    One suite per line, in the order given; process_config() skips '#' lines.
    """
    if args.only_test or args.skip_test:
        raise SystemExit(
            "--only-test/--skip-test are pgraph-disc options. nxdk_vsh_tests "
            "has its own '-Test' syntax, and nothing here writes it yet.")
    if args.config:
        raise SystemExit("--config is the pgraph JSON; a vsh disc is written "
                         "from --suite only")
    if not args.suite:
        raise SystemExit(
            "--program vsh needs at least one --suite. Without %s the program "
            "ASSERTs and waits forever." % VSH_CNF_NAME)
    unknown = [s for s in args.suite if s not in VSH_SUITES]
    if unknown:
        raise SystemExit(
            "not an nxdk_vsh_tests suite: %s. The program ignores unknown names "
            "and, left with none, runs every suite. Known: %s"
            % (", ".join(repr(s) for s in unknown), ", ".join(VSH_SUITES)))
    lines = ["# written by hakuX make_test_iso.py --program vsh"] + list(args.suite)
    return ("\n".join(lines) + "\n").encode("ascii")


def _root(data):
    root_sector, root_size = read_header(data)
    return root_sector, root_size


def _read_named(data, name):
    """Bytes of one root-directory file, or None."""
    root_sector, root_size = _root(data)
    found = lookup(data, root_sector, root_size, name)
    if found is None:
        return None
    start, length, _attributes = found
    return bytes(data[start * SECTOR:start * SECTOR + length])


def inspect_image(data):
    """What an image will do when booted, read off the image itself.

    program:  "vsh" / "pgraph" by the config path compiled into default.xbe,
              "unknown" when neither is there.
    reboots:  a vsh build that reboots at completion (no ENABLE_SHUTDOWN).
    cnf:      the suite lines of vsh_tests.cnf, or None when the file is absent.
    problems: every reason this disc would not run to completion; empty is good.
    """
    xbe = _read_named(data, "default.xbe") or b""
    if XBE_VSH_MARK in xbe:
        program = "vsh"
    elif XBE_PGRAPH_MARK in xbe:
        program = "pgraph"
    else:
        program = "unknown"
    out = {"program": program, "reboots": False, "cnf": None,
           "pgraph_config": _read_named(data, CONFIG_NAME) is not None,
           "problems": []}
    if program != "vsh":
        return out
    out["reboots"] = XBE_VSH_REBOOTS in xbe
    raw = _read_named(data, VSH_CNF_NAME)
    if raw is not None:
        out["cnf"] = [ln.strip() for ln in raw.decode("latin-1").splitlines()
                      if ln.strip() and not ln.startswith(("#", "-"))]
    if out["cnf"] is None:
        out["problems"].append(
            "no %s on the disc: nxdk_vsh_tests ASSERTs and waits forever, and "
            "the run burns its whole timeout with the device awake" % VSH_CNF_NAME)
    else:
        known = [s for s in out["cnf"] if s in VSH_SUITES]
        if not known:
            out["problems"].append(
                "%s names no known suite (%s): the program falls back to running "
                "EVERY suite" % (VSH_CNF_NAME, ", ".join(out["cnf"]) or "empty"))
    if out["reboots"]:
        out["problems"].append(
            "default.xbe is a rebooting build (no ENABLE_SHUTDOWN): on hakuX the "
            "reboot boots the same disc again and the program reruns until the "
            "timeout. Build with -DCMAKE_CXX_FLAGS=...-DENABLE_SHUTDOWN")
    if out["pgraph_config"]:
        out["problems"].append(
            "a vsh disc carries %s, which only the pgraph program reads: this "
            "disc was built as the wrong program" % CONFIG_NAME)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iso", help="stock nxdk_pgraph_tests_xiso.iso, or an "
                                    "nxdk_vsh_tests image with --program vsh")
    parser.add_argument("-o", "--output", help="image to write")
    parser.add_argument("--program", choices=("pgraph", "vsh"), default="pgraph",
                        help="which test program the base image carries "
                             "(default: %(default)s). Refused when the image's "
                             "default.xbe says otherwise.")
    parser.add_argument("--inspect", action="store_true",
                        help="write nothing: print what ISO will do as JSON, "
                             "exit 1 if it would not run to completion, or if "
                             "it is not the --program named")
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
    run.add_argument("--only-test", action="append", default=[],
                     metavar="SUITE::TEST",
                     help="run ONLY these tests from their --suite; repeatable. "
                          "The inverse of --skip-test, and mutually exclusive "
                          "with it per suite.")
    run.add_argument("--skip-test", action="append", default=[],
                     metavar="SUITE::TEST",
                     help="skip one test within a --suite, repeatable. Needed "
                          "when a test leaves state that poisons the tests "
                          "after it: \"Texture render target::RenderTextureLoop\" "
                          "disables the texture stage, and without this the "
                          "other 40 tests render flat black and the suite "
                          "measures 9.9x its real residual.")
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

    with open(args.iso, "rb") as handle:
        data = bytearray(handle.read())

    base = inspect_image(data)
    if args.inspect:
        # The image AS IT STANDS, which is what a pre-built disc will boot.
        print(json.dumps(base, indent=2))
        problems = list(base["problems"])
        if base["program"] != args.program:
            problems.insert(0, "%s is a %s disc, not --program %s"
                            % (args.iso, base["program"], args.program))
        for problem in problems:
            print("refused: %s" % problem, file=sys.stderr)
        return 1 if problems else 0

    if not args.output:
        parser.error("-o/--output is required unless --inspect")
    if args.shard_count and args.shard_index >= args.shard_count:
        parser.error("--shard-index must be less than --shard-count")

    # THE PROGRAM IS READ OFF THE IMAGE, NOT TRUSTED FROM THE CALLER. A vsh
    # image given the pgraph treatment gets nxdk_pgraph_tests_config.json,
    # which it never reads, and no vsh_tests.cnf, on which it hangs.
    # "unknown" still builds as pgraph, as every image did before the program
    # was read at all: a pgraph XBE that does not carry the literal is not a
    # reason to refuse a disc that has always worked.
    if base["program"] != args.program and not (
            args.program == "pgraph" and base["program"] == "unknown"):
        raise XisoError("%s carries the %s program, not --program %s"
                        % (args.iso, base["program"], args.program))

    if args.program == "vsh":
        if base["reboots"]:
            raise XisoError(next(p for p in base["problems"] if "reboot" in p))
        config_name = VSH_CNF_NAME
        payload = vsh_cnf(args)
    else:
        config_name = CONFIG_NAME
        if args.config:
            with open(args.config, "r", encoding="utf-8") as handle:
                config = json.load(handle)
        else:
            config = default_config(args)
        payload = json.dumps(config, indent=2).encode("utf-8")

    root_sector, root_size = read_header(data)
    entries = read_directory(data, root_sector, root_size)
    names = {name.lower(): name for name, _s, _l, _a in entries}
    if config_name.lower() in names:
        entries = [e for e in entries if e[0].lower() != config_name.lower()]
        print("replacing the existing %s" % names[config_name.lower()])

    # Append the payload, then the rebuilt root table, on fresh sectors.
    if len(data) % SECTOR:
        data.extend(b"\x00" * (SECTOR - len(data) % SECTOR))
    payload_sector = len(data) // SECTOR
    data.extend(payload)
    if len(data) % SECTOR:
        data.extend(b"\x00" * (SECTOR - len(data) % SECTOR))

    entries.append((config_name, payload_sector, len(payload), ATTR_ARCHIVE))
    table, table_size = build_directory(entries)

    table_sector = len(data) // SECTOR
    data.extend(table)
    if len(data) % SECTOR:
        data.extend(b"\x00" * (SECTOR - len(data) % SECTOR))

    struct.pack_into("<II", data, HEADER_SECTOR * SECTOR + 20, table_sector, table_size)

    with open(args.output, "wb") as handle:
        handle.write(data)

    verify(args.output, payload, config_name)
    if args.program == "vsh":
        with open(args.output, "rb") as handle:
            written = inspect_image(handle.read())
        if written["problems"]:
            raise XisoError("wrote %s but it would not run: %s"
                            % (args.output, "; ".join(written["problems"])))
    print("wrote %s (%.1f MiB), %s is %d bytes"
          % (args.output, len(data) / (1 << 20), config_name, len(payload)))
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


def verify(path, expected_payload, config_name=CONFIG_NAME):
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

    found = lookup(data, root_sector, root_size, config_name)
    start, length, _attributes = found
    written = data[start * SECTOR:start * SECTOR + length]
    if written != expected_payload:
        raise XisoError("%s did not round-trip" % config_name)
    if config_name == CONFIG_NAME:
        json.loads(written)  # catches truncation; the guest parser is stricter


if __name__ == "__main__":
    try:
        sys.exit(main())
    except XisoError as error:
        print("error: %s" % error, file=sys.stderr)
        sys.exit(1)
