#!/usr/bin/env python3
"""title_locations.py -- a tracked listing of which title is where, keyed by title_id (#433).

    title_locations.py build [--root W] [--out PATH] [--archive-limit N] [--no-nova]
    title_locations.py check [--root W] [--table PATH]        exit 0 fresh, 3 problems found
    title_locations.py show TID [--root W] [--table PATH]
    title_locations.py copies TID [--root W] [--table PATH]
    title_locations.py dcandidates [--root W] [--table PATH] [--queued PATH]
    title_locations.py selftest

W is the host work dir (default /home/justin/hakux-work). The table is W/pm/title-locations.tsv,
written beside W/pm/title-registry.tsv (title_registry.py's read_registry() reads that one; this
module is the sibling reader for WHERE a title is, joined to it by title_id). GENERATED: never
hand-edit; edit a source and rebuild.

WHY (owner 10-14, verbatim): "I'd feel a lot more confident if we aligned everything to title IDs,
and maintained a tracked listing of what titles are where. This vibes based name matching we're
doing is not working well at all for us." Confirmed on disk, not hypothetically: D:'s sports/ staging
dir holds MLB_SlugFest_2003.xiso.iso and MLB_SlugFest_2004.xiso.iso with no title id in either
filename -- a name-matcher that globs "MLB_SlugFest_2003*" against a request for 2004 (or the
reverse) finds nothing, or finds the wrong one if a future rename drops the trailing digit. See
also owner1004/Deathrow (USA).xiso.iso and owner1004/MechAssault.iso: no id, no digit to even
eyeball-check.

IDENTITY is the 4-byte hex title_id, read with this trust order (first that resolves wins):
  xbe-cert    the default.xbe certificate, read directly from the image (see read_xbe_cert below)
  name-prefix the "<TID>-" filename prefix convention this project's own tooling writes
  manifest    a pre-verified catalog row (xiso/manifest.csv, or titles/console-inventory-*.csv)
              that itself was built from an xbe-cert or equivalent read, by other code, earlier
  push-log    a push tool's own log of what it pushed, when nothing live can be re-read (the
              Thor, offline since 2026-10-13: hardware/titlepush/listing-thor.txt is the last
              word on what is there, and it cannot be confirmed right now)
A file whose id cannot be read by any of these is UNRESOLVED and is never matched by name to
anything -- that is the exact failure mode this file exists to replace.

LOCATIONS: console (the physical Xbox's F:/G:/D:, from titles/console-inventory-*.csv), d-archive
(D:\\Xbox, redump .7z/.iso, the owner's original names), d-xiso (/mnt/d/hakux-staging/xiso, the
stager's output), d-cache (shuffle-cache), d-other (the other D: staging dirs that hold individual
game images: ingest, kfc, owner1004, sports, staging, staging-linux, sweep, thor-copy,
nova-archive-1008), nova (a live adb listing), thor (offline: seeded from the last push log,
id_source=push-log, stale=thor-offline; never re-stated as live).
"""
import argparse
import csv
import datetime as dt
import glob
import hashlib
import os
import re
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = "/home/justin/hakux-work"
SEVENZ = "/mnt/c/Program Files/7-Zip/7z.exe"
NOVA_SERIAL = "ee317437"
NOVA_GAMES_DIR = "/storage/E6C6-D7AA/Games/XBox"
TID_RE = re.compile(r"^[0-9A-Fa-f]{8}$")
NAME_PREFIX_RE = re.compile(r"^([0-9A-Fa-f]{8})-")
XBE_CERT_READ_CAP = 300 * 1024 * 1024  # give up past this many bytes into an image (pathological case)

COLUMNS = ["title_id", "location", "path", "bytes", "sha256", "id_source", "seen_utc", "mtime", "stale"]
LOCATIONS = ("console", "d-archive", "d-xiso", "d-cache", "d-other", "nova", "thor")
TRUST = {"xbe-cert": 0, "name-prefix": 1, "manifest": 2, "push-log": 3}
GAME_EXTS = (".xiso.iso", ".iso")


def utcnow():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Paths:
    def __init__(self, root=DEFAULT_ROOT):
        self.root = root
        self.pm = os.path.join(root, "pm")
        self.table = os.path.join(self.pm, "title-locations.tsv")
        self.registry = os.path.join(self.pm, "title-registry.tsv")
        self.inventory = sorted(glob.glob(os.path.join(root, "titles", "console-inventory-*.csv")))
        self.d_archive = "/mnt/d/Xbox"
        self.d_xiso = "/mnt/d/hakux-staging/xiso"
        self.d_xiso_manifest = os.path.join(self.d_xiso, "manifest.csv")
        self.d_cache = "/mnt/d/hakux-staging/shuffle-cache"
        self.d_other = [os.path.join("/mnt/d/hakux-staging", d) for d in (
            "ingest", "kfc", "owner1004", "sports", "staging", "staging-linux", "sweep",
            "thor-copy", "nova-archive-1008")]
        self.listing_thor = os.path.join(root, "hardware", "titlepush", "listing-thor.txt")


# ---------------------------------------------------------------- table I/O

def read_table(path):
    """(header dict, [row dict]) or (None, []) if missing/unparseable."""
    if not os.path.isfile(path):
        return None, []
    with open(path, encoding="utf-8", errors="replace") as f:
        first = f.readline()
        if not first.startswith("# title-locations v1 "):
            return None, []
        hdr = dict(kv.split("=", 1) for kv in first[len("# title-locations v1 "):].split() if "=" in kv)
        rows = []
        cols = None
        for line in f:
            if line.startswith("#"):
                continue
            cells = line.rstrip("\n").split("\t")
            if cols is None:
                cols = cells
                continue
            rows.append(dict(zip(cols, cells)))
    return hdr, rows


def write_table(path, rows, out=None):
    out = out or path
    rows = sorted(rows, key=lambda r: (r.get("title_id", ""), r.get("location", ""), r.get("path", "")))
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# title-locations v1 generated_utc=%s rows=%d\n" % (utcnow(), len(rows)))
        f.write("# GENERATED by docs/testing/title_locations.py build -- never hand-edit; edit a source and rebuild\n")
        f.write("\t".join(COLUMNS) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "")) for c in COLUMNS) + "\n")
    os.replace(tmp, out)


def copies(tid, rows):
    """Every row recorded for this title_id, most-trusted id_source first."""
    tid = tid.upper()
    return sorted((r for r in rows if r["title_id"].upper() == tid),
                  key=lambda r: (TRUST.get(r.get("id_source"), 9), r.get("location", "")))


def copy_exists_elsewhere(title_id, location_to_delete, bytes_, rows, now=None, max_age_h=24):
    """The best other row backing a delete from location_to_delete, or None.

    Matches on title_id (never a name) AND (bytes equal OR sha256 equal to some row at
    location_to_delete with that title_id -- callers pass the bytes of the copy being deleted)
    AND the other row was seen within max_age_h hours. This is the gate: a caller about to
    delete a copy at `location_to_delete` must get a non-None answer first.
    """
    now = now or dt.datetime.now(dt.timezone.utc)
    title_id = title_id.upper()
    want_sha = None
    for r in rows:
        if r["title_id"].upper() == title_id and r["location"] == location_to_delete and str(r.get("bytes")) == str(bytes_):
            want_sha = r.get("sha256") or want_sha
    best = None
    for r in rows:
        if r["title_id"].upper() != title_id or r["location"] == location_to_delete:
            continue
        if r.get("stale"):
            continue
        same_bytes = str(r.get("bytes")) == str(bytes_)
        same_sha = bool(want_sha) and bool(r.get("sha256")) and r.get("sha256") == want_sha
        if not (same_bytes or same_sha):
            continue
        seen = parse_utc(r.get("seen_utc"))
        if seen is None or (now - seen).total_seconds() > max_age_h * 3600:
            continue
        if best is None or TRUST.get(r.get("id_source"), 9) < TRUST.get(best.get("id_source"), 9):
            best = r
    return best


def parse_utc(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def check_table(rows):
    """List of problem strings. Empty means check passes."""
    problems = []
    seen_keys = {}
    for r in rows:
        key = (r["title_id"], r["location"], r["path"])
        if key in seen_keys:
            problems.append("duplicate row: title_id=%s location=%s path=%s" % key)
        seen_keys[key] = True
        if r["title_id"] == "UNRESOLVED":
            problems.append("UNRESOLVED: location=%s path=%s" % (r["location"], r["path"]))
            continue
        if not TID_RE.match(r["title_id"]):
            problems.append("not an 8-hex title_id: %r at %s" % (r["title_id"], r["path"]))
        if r.get("path") and os.path.isfile(r["path"]):
            try:
                actual = os.path.getsize(r["path"])
            except OSError:
                continue
            if r.get("bytes") and str(actual) != str(r["bytes"]):
                problems.append("size mismatch: %s recorded %s, file is now %s bytes" % (r["path"], r["bytes"], actual))
    return problems


# ---------------------------------------------------------------- xbe-cert reading

class FileReader:
    """Wraps a real file; seek_forward may actually go anywhere (cheap on a local file)."""
    def __init__(self, fh):
        self.fh = fh

    def seek_forward(self, pos):
        self.fh.seek(pos)

    def read(self, n):
        b = self.fh.read(n)
        if len(b) < n:
            raise EOFError("short read: wanted %d, got %d" % (n, len(b)))
        return b


class PipeReader:
    """Wraps a subprocess stdout pipe. Forward-only: never writes the decompressed
    stream to disk, and gives up past XBE_CERT_READ_CAP bytes rather than draining
    an entire multi-GB image looking for a directory entry that isn't there."""
    def __init__(self, fh, cap=XBE_CERT_READ_CAP):
        self.fh = fh
        self.pos = 0
        self.cap = cap

    def seek_forward(self, pos):
        if pos < self.pos:
            raise ValueError("backward seek not supported (pos=%d < %d)" % (pos, self.pos))
        if pos > self.cap:
            raise ValueError("xbe-cert read exceeded %d byte cap seeking to %d" % (self.cap, pos))
        n = pos - self.pos
        while n > 0:
            chunk = self.fh.read(min(n, 1 << 20))
            if not chunk:
                raise EOFError("stream ended while skipping to %d" % pos)
            n -= len(chunk)
            self.pos += len(chunk)

    def read(self, n):
        if self.pos + n > self.cap:
            raise ValueError("xbe-cert read exceeded %d byte cap reading %d at %d" % (self.cap, n, self.pos))
        buf = b""
        while len(buf) < n:
            chunk = self.fh.read(n - len(buf))
            if not chunk:
                raise EOFError("stream ended after %d of %d bytes" % (len(buf), n))
            buf += chunk
        self.pos += len(buf)
        return buf


def read_xbe_cert(reader, bases=(0, 0x18300000)):
    """(title_id, name) from the default.xbe certificate inside an XDVDFS image, read through
    `reader` (FileReader or PipeReader). Tries each base in order; bases must be ascending so a
    forward-only PipeReader can still try more than one (base, not seek, is what varies here)."""
    last_err = None
    for base in bases:
        try:
            reader.seek_forward(base + 0x10000)
            h = reader.read(0x20)
            if h[:20] != b"MICROSOFT*XBOX*MEDIA":
                raise ValueError("no XDVDFS header at base 0x%X" % base)
            root_sec, root_size = struct.unpack_from("<II", h, 0x14)
            reader.seek_forward(base + root_sec * 2048)
            table = reader.read(root_size)

            def walk(off):
                if off * 4 + 14 > len(table):
                    return None
                left, right, sec, size, attr, nlen = struct.unpack_from("<HHIIBB", table, off * 4)
                if left == 0xFFFF:
                    return None
                if table[off * 4 + 14:off * 4 + 14 + nlen].lower() == b"default.xbe":
                    return sec, size
                for nxt in (left, right):
                    if nxt:
                        r = walk(nxt)
                        if r:
                            return r
                return None
            found = walk(0)
            if not found:
                raise ValueError("default.xbe not in the root directory (base 0x%X)" % base)
            sec, size = found
            reader.seek_forward(base + sec * 2048)
            x = reader.read(0x3000)
            if x[:4] != b"XBEH":
                raise ValueError("default.xbe is not an XBE")
            o = struct.unpack_from("<I", x, 0x118)[0] - struct.unpack_from("<I", x, 0x104)[0]
            tid = "%08X" % struct.unpack_from("<I", x, o + 8)[0]
            name = x[o + 0x0C:o + 0x0C + 0x50].decode("utf-16-le", "replace").split("\x00")[0]
            return tid, name
        except Exception as e:
            last_err = e
    raise last_err


def xbe_cert_from_file(path):
    with open(path, "rb") as fh:
        return read_xbe_cert(FileReader(fh))


def sevenz_iso_member(archive_winpath):
    """(member name, size) of the archive's .iso entry, or (None, None)."""
    out = subprocess.run([SEVENZ, "l", "-slt", archive_winpath], capture_output=True, text=True).stdout
    best = None
    path = size = None
    for line in out.splitlines():
        if line.startswith("Path = "):
            path = line[len("Path = "):]
        elif line.startswith("Size = "):
            size = line[len("Size = "):]
        elif not line.strip():
            if path and path.lower().endswith(".iso") and size:
                if best is None or int(size) > int(best[1]):
                    best = (path, size)
            path = size = None
    if path and path.lower().endswith(".iso") and size and (best is None or int(size) > int(best[1])):
        best = (path, size)
    return best or (None, None)


def xbe_cert_from_7z(archive_path):
    winpath = subprocess.run(["wslpath", "-w", archive_path], capture_output=True, text=True, check=True).stdout.strip()
    member, _ = sevenz_iso_member(winpath)
    if not member:
        raise ValueError("no .iso member in %s" % archive_path)
    proc = subprocess.Popen([SEVENZ, "x", "-so", winpath, member], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        return read_xbe_cert(PipeReader(proc.stdout), bases=(0, 0x18300000))
    finally:
        proc.stdout.close()
        proc.kill()
        proc.wait()


# ---------------------------------------------------------------- scanners

def row(title_id, location, path, bytes_, sha256_, id_source, seen_utc=None, mtime=None, stale=""):
    return {
        "title_id": title_id, "location": location, "path": path, "bytes": str(bytes_),
        "sha256": sha256_ or "", "id_source": id_source, "seen_utc": seen_utc or utcnow(),
        "mtime": str(int(mtime)) if mtime is not None else "", "stale": stale,
    }


def sha_sidecar(path):
    """Opportunistic sha256 from a '<path>.sha' sidecar or a SHA256SUMS file beside it. Never
    computed here (hashing multi-GB images on every build would be too slow); absent is fine,
    the deletion gate falls back to a bytes match."""
    sidecar = path + ".sha"
    if os.path.isfile(sidecar):
        try:
            h = open(sidecar).read().strip().split()[0]
            if re.fullmatch(r"[0-9a-fA-F]{64}", h):
                return h.lower()
        except (OSError, IndexError):
            pass
    sums = os.path.join(os.path.dirname(path), "SHA256SUMS")
    if os.path.isfile(sums):
        name = os.path.basename(path)
        for line in open(sums, errors="replace"):
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[1].strip() == name and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
                return parts[0].lower()
    return None


def scan_console(p):
    out = []
    for inv in p.inventory:
        with open(inv, newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                tid = (r.get("title_id") or "").upper()
                if not TID_RE.match(tid):
                    continue
                path = "%s:%s" % (r["drive"], r["path"])
                out.append(row(tid, "console", path, r.get("size_bytes") or 0, "", "manifest"))
    return out


def scan_d_xiso(p):
    out = []
    manifest = {}
    if os.path.isfile(p.d_xiso_manifest):
        with open(p.d_xiso_manifest, newline="", encoding="utf-8", errors="replace") as f:
            for r in csv.DictReader(f):
                manifest[r["title_id"].upper()] = r
    for path in sorted(glob.glob(os.path.join(p.d_xiso, "*.xiso.iso"))):
        fn = os.path.basename(path)
        m = NAME_PREFIX_RE.match(fn)
        if not m:
            out.append(row("UNRESOLVED", "d-xiso", path, os.path.getsize(path), "", "", stale=""))
            continue
        tid = m.group(1).upper()
        mr = manifest.get(tid)
        mtime = os.path.getmtime(path)
        if mr and mr.get("xiso_bytes") and str(mr["xiso_bytes"]) == str(os.path.getsize(path)):
            out.append(row(tid, "d-xiso", path, mr["xiso_bytes"], mr.get("sha256", ""), "manifest", mtime=mtime))
        else:
            out.append(row(tid, "d-xiso", path, os.path.getsize(path), sha_sidecar(path) or "", "name-prefix", mtime=mtime))
    return out


def scan_d_cache(p):
    out = []
    if not os.path.isdir(p.d_cache):
        return out
    for path in sorted(glob.glob(os.path.join(p.d_cache, "*.iso"))):
        fn = os.path.basename(path)
        m = NAME_PREFIX_RE.match(fn)
        tid = m.group(1).upper() if m else "UNRESOLVED"
        out.append(row(tid, "d-cache", path, os.path.getsize(path), sha_sidecar(path) or "",
                        "name-prefix" if m else "", mtime=os.path.getmtime(path)))
    return out


def scan_d_other(p, cache_rows=(), archive_limit=None):
    """cache_rows: previously-built rows for d-other, reused when (path, bytes, mtime) match so an
    xbe-cert read is not repeated on an unchanged file."""
    prior = {(r["path"], r.get("bytes"), r.get("mtime")): r for r in cache_rows}
    out, read_count = [], 0
    for d in p.d_other:
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith(GAME_EXTS):
                continue
            path = os.path.join(d, fn)
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            key = (path, str(size), str(int(mtime)))
            if key in prior:
                out.append(dict(prior[key], seen_utc=utcnow()))
                continue
            m = NAME_PREFIX_RE.match(fn)
            if m:
                out.append(row(m.group(1).upper(), "d-other", path, size, sha_sidecar(path) or "", "name-prefix", mtime=mtime))
                continue
            if archive_limit is not None and read_count >= archive_limit:
                out.append(row("UNRESOLVED", "d-other", path, size, "", "", mtime=mtime))
                continue
            read_count += 1
            try:
                tid, _name = xbe_cert_from_file(path)
                out.append(row(tid.upper(), "d-other", path, size, sha_sidecar(path) or "", "xbe-cert", mtime=mtime))
            except Exception as e:
                out.append(row("UNRESOLVED", "d-other", path, size, "", "", mtime=mtime, stale="xbe-cert failed: %s" % e))
    return out


def scan_d_archive(p, cache_rows=(), limit=None):
    prior = {(r["path"], r.get("bytes"), r.get("mtime")): r for r in cache_rows}
    out, read_count = [], 0
    if not os.path.isdir(p.d_archive):
        return out
    for fn in sorted(os.listdir(p.d_archive)):
        if not fn.lower().endswith((".7z", ".iso")):
            continue
        path = os.path.join(p.d_archive, fn)
        if not os.path.isfile(path):
            continue
        size = os.path.getsize(path)
        mtime = os.path.getmtime(path)
        key = (path, str(size), str(int(mtime)))
        if key in prior:
            out.append(dict(prior[key], seen_utc=utcnow()))
            continue
        m = NAME_PREFIX_RE.match(fn)
        if m:
            out.append(row(m.group(1).upper(), "d-archive", path, size, "", "name-prefix", mtime=mtime))
            continue
        if limit is not None and read_count >= limit:
            out.append(row("UNRESOLVED", "d-archive", path, size, "", "", mtime=mtime,
                            stale="not read this build: --archive-limit reached"))
            continue
        read_count += 1
        try:
            if fn.lower().endswith(".iso"):
                tid, _name = xbe_cert_from_file(path)
            else:
                tid, _name = xbe_cert_from_7z(path)
            out.append(row(tid.upper(), "d-archive", path, size, "", "xbe-cert", mtime=mtime))
        except Exception as e:
            out.append(row("UNRESOLVED", "d-archive", path, size, "", "", mtime=mtime, stale="xbe-cert failed: %s" % e))
    return out


def scan_nova(serial=NOVA_SERIAL, games_dir=NOVA_GAMES_DIR):
    out = []
    proc = subprocess.run(["adb", "-s", serial, "shell", "ls -l %s 2>&1 </dev/null" % games_dir],
                           capture_output=True, text=True, timeout=30)
    if proc.returncode != 0:
        return out
    for line in proc.stdout.splitlines():
        lm = re.match(r"^\S+\s+\d+\s+\S+\s+\S+\s+(\d+)\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+(.+)$", line.strip())
        if not lm:
            continue
        size, fn = lm.groups()
        m = NAME_PREFIX_RE.match(fn)
        tid = m.group(1).upper() if m else "UNRESOLVED"
        out.append(row(tid, "nova", "%s/%s" % (games_dir, fn), size, "",
                        "name-prefix" if m else ""))
    return out


def scan_thor(p):
    out = []
    if not os.path.isfile(p.listing_thor):
        return out
    seen_utc = utcnow()
    header_m = None
    with open(p.listing_thor) as f:
        first = f.readline()
        header_m = re.search(r"listed (\S+) by", first)
        for line in f:
            fn = line.strip()
            if not fn or fn.startswith("#"):
                continue
            m = NAME_PREFIX_RE.match(fn)
            tid = m.group(1).upper() if m else "UNRESOLVED"
            out.append(row(tid, "thor", "%s/%s" % (NOVA_GAMES_DIR, fn), 0, "", "push-log" if m else "",
                           seen_utc=(header_m.group(1) if header_m else seen_utc), stale="thor-offline"))
    return out


# ---------------------------------------------------------------- build / CLI

def build(root=DEFAULT_ROOT, out=None, archive_limit=None, no_nova=False, no_thor=False):
    p = Paths(root)
    _hdr, prior_rows = read_table(p.table)
    prior_by_loc = {}
    for r in prior_rows:
        prior_by_loc.setdefault(r["location"], []).append(r)
    rows = []
    rows += scan_console(p)
    rows += scan_d_xiso(p)
    rows += scan_d_cache(p)
    rows += scan_d_other(p, cache_rows=prior_by_loc.get("d-other", ()))
    rows += scan_d_archive(p, cache_rows=prior_by_loc.get("d-archive", ()), limit=archive_limit)
    if not no_nova:
        rows += scan_nova()
    else:
        rows += prior_by_loc.get("nova", ())
    if not no_thor:
        rows += scan_thor(p)
    write_table(p.table, rows, out=out or p.table)
    return rows


def cmd_build(args):
    rows = build(root=args.root, out=args.out, archive_limit=args.archive_limit,
                 no_nova=args.no_nova, no_thor=args.no_thor)
    by_loc = {}
    for r in rows:
        by_loc.setdefault(r["location"], [0, 0])
        by_loc[r["location"]][0] += 1
        if r["title_id"] == "UNRESOLVED":
            by_loc[r["location"]][1] += 1
    print("title-locations: %d rows" % len(rows))
    for loc in LOCATIONS:
        n, u = by_loc.get(loc, (0, 0))
        print("  %-10s %4d rows, %d UNRESOLVED" % (loc, n, u))
    unresolved = [r for r in rows if r["title_id"] == "UNRESOLVED"]
    if unresolved:
        print("\nUNRESOLVED:")
        for r in unresolved:
            print("  %-10s %s%s" % (r["location"], r["path"], (" (%s)" % r["stale"]) if r.get("stale") else ""))
    return 0


def cmd_check(args):
    p = Paths(args.root)
    hdr, rows = read_table(args.table or p.table)
    if hdr is None:
        print("title-locations: table %s missing or not a generated table" % (args.table or p.table))
        return 3
    problems = check_table(rows)
    if not problems:
        print("title-locations: check OK (%d rows)" % len(rows))
        return 0
    for pr in problems:
        print(pr)
    return 3


def cmd_show(args):
    p = Paths(args.root)
    _hdr, rows = read_table(args.table or p.table)
    for r in copies(args.title_id, rows):
        print("\t".join(r.get(c, "") for c in COLUMNS))
    return 0


def cmd_copies(args):
    return cmd_show(args)


def cmd_dcandidates(args):
    p = Paths(args.root)
    _hdr, rows = read_table(args.table or p.table)
    queued = set()
    if args.queued and os.path.isfile(args.queued):
        queued = {l.strip().upper() for l in open(args.queued) if re.match(r"[0-9A-Fa-f]{8}", l.strip())}
    d_locations = {"d-archive", "d-xiso", "d-cache", "d-other"}
    candidates = []
    for r in rows:
        if r["location"] not in d_locations or r["title_id"] == "UNRESOLVED":
            continue
        if r["title_id"].upper() in queued:
            continue
        other = copy_exists_elsewhere(r["title_id"], r["location"], r["bytes"], rows)
        if other and other["location"] in ("console", "d-archive") and other["location"] != r["location"]:
            candidates.append((r, other))
    for r, other in candidates:
        print("%s\t%s\t%s (verified on %s: %s)" % (r["title_id"], r["location"], r["path"], other["location"], other["path"]))
    print("\n%d candidate(s) -- printed only, nothing deleted" % len(candidates))
    return 0


def cmd_selftest(args):
    import selftest_title_locations
    return selftest_title_locations.run()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--root", default=DEFAULT_ROOT)
    b.add_argument("--out")
    b.add_argument("--archive-limit", type=int, default=None)
    b.add_argument("--no-nova", action="store_true")
    b.add_argument("--no-thor", action="store_true")
    b.set_defaults(func=cmd_build)

    c = sub.add_parser("check")
    c.add_argument("--root", default=DEFAULT_ROOT)
    c.add_argument("--table")
    c.set_defaults(func=cmd_check)

    s = sub.add_parser("show")
    s.add_argument("title_id")
    s.add_argument("--root", default=DEFAULT_ROOT)
    s.add_argument("--table")
    s.set_defaults(func=cmd_show)

    cp = sub.add_parser("copies")
    cp.add_argument("title_id")
    cp.add_argument("--root", default=DEFAULT_ROOT)
    cp.add_argument("--table")
    cp.set_defaults(func=cmd_copies)

    dc = sub.add_parser("dcandidates")
    dc.add_argument("--root", default=DEFAULT_ROOT)
    dc.add_argument("--table")
    dc.add_argument("--queued")
    dc.set_defaults(func=cmd_dcandidates)

    st = sub.add_parser("selftest")
    st.set_defaults(func=cmd_selftest)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
