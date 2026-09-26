#!/usr/bin/env python3
"""Read-only: list a title folder on the console and fetch the head of its videos.

    ftpvideo.py list <dir>                 recursive LIST, video-looking files only
    ftpvideo.py head <path> <bytes> <out>  RETR the first <bytes> of one file, then ABOR

Same access as titles/bin/stage_xiso.py (FTP CWD / LIST / RETR, nothing written
on the console). Check that no staging batch is running first: the stager's
PAUSE/STOP files live in /mnt/d/hakux-staging/xiso/.
"""
import ftplib
import sys

HOST = "192.168.50.1"
VIDEO = (".bik", ".sfd", ".xmv", ".wmv", ".m2v", ".mpg", ".vid", ".avi", ".usm", ".pss")


def conn():
    f = ftplib.FTP(encoding="latin-1")
    f.connect(HOST, 21, timeout=30)
    f.login("xbox", "xbox")
    f.set_pasv(True)
    return f


def walk(f, d, out):
    f.cwd(d)
    lines = []
    f.retrlines("LIST", lines.append)
    for ln in lines:
        parts = ln.split(None, 8)
        if len(parts) < 9 or parts[8] in (".", ".."):
            continue
        name = parts[8]
        path = d.rstrip("/") + "/" + name
        if ln.startswith("d"):
            walk(f, path, out)
        else:
            out.append((path, int(parts[4])))


cmd = sys.argv[1]
f = conn()
if cmd == "list":
    files = []
    walk(f, sys.argv[2], files)
    exts = {}
    for p, n in files:
        e = p[p.rfind("."):].lower() if "." in p else ""
        exts[e] = exts.get(e, 0) + 1
    print("files %d; by extension: %s" % (len(files), sorted(exts.items(), key=lambda x: -x[1])))
    for p, n in files:
        if p.lower().endswith(VIDEO) or n > 20_000_000:
            print("%12d %s" % (n, p))
elif cmd == "head":
    want = int(sys.argv[3])
    buf = bytearray()
    sock = f.transfercmd("RETR " + sys.argv[2])
    while len(buf) < want:
        b = sock.recv(min(65536, want - len(buf)))
        if not b:
            break
        buf += b
    sock.close()
    try:
        f.abort()
    except ftplib.all_errors:
        pass
    open(sys.argv[4], "wb").write(bytes(buf))
    print("read %d bytes of %s" % (len(buf), sys.argv[2]))
try:
    f.quit()
except ftplib.all_errors:
    pass
