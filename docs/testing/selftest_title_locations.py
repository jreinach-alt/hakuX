#!/usr/bin/env python3
"""Selftest for title_locations.py (#433). Hermetic: builds tiny synthetic XDVDFS/XBE images in a
temp dir rather than depending on /mnt/d being mounted. Falsifier pairs (names that collide or
nearly collide, but must never resolve to the same title_id): Max Payne / Max Payne 2, GTA III /
Vice City / San Andreas, MLB SlugFest 2003 / 2004, Legends of Wrestling / II -- these are confirmed
for real on disk too (see PR.md), but the selftest does not require the mount to exist.

    selftest_title_locations.py            run all tests, exit 0 pass / 1 fail
"""
import os
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import title_locations as tl  # noqa: E402

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        print("ok   %s" % name)
    else:
        print("FAIL %s %s" % (name, detail))
        FAILURES.append(name)


# ---------------------------------------------------------------- fixture builder

def build_fake_image(title_id, name, root_sec=40, xbe_sec=50, cert_off=0x180):
    """A minimal XDVDFS image: header at 0x10000, a one-entry root directory naming
    default.xbe, and an XBE whose certificate carries title_id/name. Small (fits in memory)."""
    xbe = bytearray(0x3000)
    xbe[0:4] = b"XBEH"
    struct.pack_into("<I", xbe, 0x104, 0)              # base address
    struct.pack_into("<I", xbe, 0x118, cert_off)        # cert address (base=0, so == file offset)
    struct.pack_into("<I", xbe, cert_off + 8, int(title_id, 16))
    nb = name.encode("utf-16-le")[:0x50]
    xbe[cert_off + 0x0C:cert_off + 0x0C + len(nb)] = nb

    table = struct.pack("<HHIIBB", 0, 0, xbe_sec, len(xbe), 0, len(b"DEFAULT.XBE")) + b"DEFAULT.XBE"
    header = b"MICROSOFT*XBOX*MEDIA" + struct.pack("<II", root_sec, len(table))
    header += b"\x00" * (0x20 - len(header))

    image = bytearray(xbe_sec * 2048 + len(xbe) + 2048)
    image[0x10000:0x10000 + len(header)] = header
    image[root_sec * 2048:root_sec * 2048 + len(table)] = table
    image[xbe_sec * 2048:xbe_sec * 2048 + len(xbe)] = bytes(xbe)
    return bytes(image)


def write_fake_iso(tmpdir, filename, title_id, name):
    path = os.path.join(tmpdir, filename)
    with open(path, "wb") as f:
        f.write(build_fake_image(title_id, name))
    return path


# ---------------------------------------------------------------- tests

def test_xbe_cert_roundtrip(tmpdir):
    path = write_fake_iso(tmpdir, "fake1.iso", "4D570008", "Slugfest")
    tid, name = tl.xbe_cert_from_file(path)
    check("xbe_cert_from_file reads back the title_id", tid == "4D570008", "got %r" % tid)
    check("xbe_cert_from_file reads back the name", name == "Slugfest", "got %r" % name)


def test_falsifier_pairs_resolve_distinct(tmpdir):
    pairs = [
        ("54540003", "Max Payne", "maxpayne1.iso"),
        ("5454000C", "Max Payne 2", "maxpayne2.iso"),
        ("41430002", "Grand Theft Auto III", "gta3.iso"),
        ("45560029", "Grand Theft Auto Vice City", "gtavc.iso"),
        ("54540082", "GTA San Andreas", "gtasa.iso"),
        ("4D570008", "Slugfest", "mlb2003.iso"),
        ("4D570009", "Slugfest2004", "mlb2004.iso"),
        ("41430003", "Legends of Wrestling", "low1.iso"),
        ("4143000F", "Legends of Wrestling 2", "low2.iso"),
    ]
    seen = {}
    for tid, name, fn in pairs:
        path = write_fake_iso(tmpdir, fn, tid, name)
        got_tid, got_name = tl.xbe_cert_from_file(path)
        check("falsifier %s resolves to its own id" % name, got_tid == tid, "got %r wanted %r" % (got_tid, tid))
        seen.setdefault(got_tid, []).append(name)
    dupes = {t: ns for t, ns in seen.items() if len(ns) > 1}
    check("no two falsifier titles share a resolved id", not dupes, "collided: %r" % dupes)


def test_name_prefix_and_table_roundtrip(tmpdir):
    rows = [
        tl.row("4D570008", "d-xiso", "/mnt/d/hakux-staging/xiso/4D570008-Slugfest.xiso.iso", 123, "aa", "name-prefix"),
        tl.row("UNRESOLVED", "d-other", "/mnt/d/hakux-staging/sports/Mystery.xiso.iso", 456, "", ""),
    ]
    out = os.path.join(tmpdir, "table.tsv")
    tl.write_table(out, rows)
    hdr, back = tl.read_table(out)
    check("write_table/read_table header parses", hdr is not None and "generated_utc" in hdr)
    check("write_table/read_table round-trips row count", len(back) == 2, "got %d" % len(back))
    check("round-tripped row keeps its title_id", {r["title_id"] for r in back} == {"4D570008", "UNRESOLVED"})


def test_check_table_catches_problems(tmpdir):
    f = os.path.join(tmpdir, "sized.iso")
    open(f, "wb").write(b"\x00" * 1000)
    rows = [
        tl.row("4D570008", "d-other", f, 999, "", "xbe-cert"),          # size mismatch (recorded 999, actual 1000)
        tl.row("UNRESOLVED", "d-other", "/no/such/file.iso", 1, "", ""),  # UNRESOLVED
        tl.row("4D570009", "d-xiso", "/a/b.iso", 1, "", "name-prefix"),
        tl.row("4D570009", "d-xiso", "/a/b.iso", 1, "", "name-prefix"),  # exact duplicate key
    ]
    problems = tl.check_table(rows)
    check("check_table flags the size mismatch", any("size mismatch" in p for p in problems), problems)
    check("check_table flags UNRESOLVED", any("UNRESOLVED" in p for p in problems), problems)
    check("check_table flags the duplicate row", any("duplicate row" in p for p in problems), problems)


def test_copies_sorts_by_trust():
    rows = [
        tl.row("4D570008", "nova", "/nova/a.iso", 1, "", "name-prefix"),
        tl.row("4D570008", "d-archive", "/d/a.7z", 1, "", "xbe-cert"),
        tl.row("4D570008", "console", "/console/a", 1, "", "manifest"),
    ]
    cs = tl.copies("4d570008", rows)  # lowercase input must still match
    check("copies() is case-insensitive on title_id", len(cs) == 3, "got %d" % len(cs))
    check("copies() ranks xbe-cert first", cs[0]["id_source"] == "xbe-cert", cs[0])
    check("copies() ranks manifest last of these three", cs[-1]["id_source"] == "manifest", cs[-1])


def test_copy_exists_elsewhere_gate():
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    fresh = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    stale_time = (now - dt.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ")

    rows = [
        tl.row("4D570008", "nova", "/nova/a.iso", 1000, "", "name-prefix", seen_utc=fresh),
        tl.row("4D570008", "d-archive", "/d/a.7z", 1000, "", "xbe-cert", seen_utc=fresh),
    ]
    other = tl.copy_exists_elsewhere("4D570008", "nova", 1000, rows, now=now)
    check("copy_exists_elsewhere finds the d-archive copy before deleting from nova",
          other is not None and other["location"] == "d-archive", other)

    wrong_size = [dict(r) for r in rows]
    wrong_size[1]["bytes"] = "999"
    none1 = tl.copy_exists_elsewhere("4D570008", "nova", 1000, wrong_size, now=now)
    check("copy_exists_elsewhere refuses a size mismatch with no matching sha256", none1 is None, none1)

    old = [dict(r) for r in rows]
    old[1]["seen_utc"] = stale_time
    none2 = tl.copy_exists_elsewhere("4D570008", "nova", 1000, old, now=now)
    check("copy_exists_elsewhere refuses a copy last seen 48h ago (default 24h window)", none2 is None, none2)

    marked_stale = [dict(r) for r in rows]
    marked_stale[1]["stale"] = "thor-offline"
    none3 = tl.copy_exists_elsewhere("4D570008", "nova", 1000, marked_stale, now=now)
    check("copy_exists_elsewhere refuses a row marked stale even if recently seen_utc", none3 is None, none3)

    different_title = [dict(r) for r in rows]
    different_title[1]["title_id"] = "41430003"
    none4 = tl.copy_exists_elsewhere("4D570008", "nova", 1000, different_title, now=now)
    check("copy_exists_elsewhere never matches a different title_id", none4 is None, none4)


def _mutant_name_gate(name_prefix, location_to_delete, rows):
    """A deliberately BAD gate, matching by filename prefix instead of title_id -- the exact
    'vibes based name matching' the owner's brief calls out. Exists only in this selftest, to
    prove the falsifier pairs break a name-based rule while the real gate stays correct. Mirrors
    copy_exists_elsewhere's own shape: look for a backing copy at some OTHER location."""
    for r in rows:
        if r["location"] != location_to_delete and os.path.basename(r["path"]).startswith(name_prefix):
            return r
    return None


def test_mutant_name_gate_passes_falsifier_pair_wrongly():
    rows = [
        tl.row("4D570008", "d-archive", "MLB_SlugFest_2003.xiso.iso", 100, "", "xbe-cert"),
        tl.row("4D570009", "d-other", "MLB_SlugFest_2004.xiso.iso", 100, "", "xbe-cert"),
    ]
    bad = _mutant_name_gate("MLB_SlugFest_200", "d-archive", rows)
    check("mutant: a name-prefix gate wrongly matches the 2004 copy for a 2003 request",
          bad is not None and bad["title_id"] == "4D570009", bad)
    real = tl.copy_exists_elsewhere("4D570008", "d-archive", 100, rows)
    check("the real title_id-keyed gate refuses that same wrong match",
          real is None, real)

    rows2 = [
        tl.row("54540003", "d-archive", "Max Payne (USA).7z", 50, "", "xbe-cert"),
        tl.row("5454000C", "d-other", "Max Payne 2 - The Fall of Max Payne (USA).iso", 50, "", "xbe-cert"),
    ]
    bad2 = _mutant_name_gate("Max Payne", "d-archive", rows2)
    check("mutant: a name-prefix gate also wrongly matches Max Payne against Max Payne 2",
          bad2 is not None and bad2["title_id"] == "5454000C", bad2)
    real2 = tl.copy_exists_elsewhere("54540003", "d-archive", 50, rows2)
    check("the real gate refuses the Max Payne / Max Payne 2 collision too", real2 is None, real2)


def run():
    with tempfile.TemporaryDirectory(prefix="title-locations-selftest-") as tmpdir:
        test_xbe_cert_roundtrip(tmpdir)
        test_falsifier_pairs_resolve_distinct(tmpdir)
        test_name_prefix_and_table_roundtrip(tmpdir)
        test_check_table_catches_problems(tmpdir)
        test_copies_sorts_by_trust()
        test_copy_exists_elsewhere_gate()
        test_mutant_name_gate_passes_falsifier_pair_wrongly()
    if FAILURES:
        print("\n%d FAILURE(S): %s" % (len(FAILURES), ", ".join(FAILURES)))
        return 1
    print("\nall selftests passed")
    return 0


if __name__ == "__main__":
    sys.exit(run())
