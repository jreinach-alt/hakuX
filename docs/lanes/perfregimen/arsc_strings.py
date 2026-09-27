#!/usr/bin/env python3
"""Print an APK's resource entries whose name matches a regex, with values.

A minimal resources.arsc reader (string pool + type chunks, default config
and every other config) -- enough to read string/array/integer resources
without aapt.  arsc_strings.py <apk> <name-regex>
"""
import re, struct, sys, zipfile


def pool(buf, off):
    _, hsz, size, n, nstyle, flags, sstart, _ = struct.unpack_from("<HHIIIIII", buf, off)
    utf8 = flags & 0x100
    offs = struct.unpack_from("<%dI" % n, buf, off + hsz)
    out = []
    for o in offs:
        p = off + sstart + o
        if utf8:
            l = buf[p]; p += 2 if l & 0x80 else 1
            l = buf[p]
            if l & 0x80:
                l = ((l & 0x7f) << 8) | buf[p + 1]; p += 2
            else:
                p += 1
            out.append(buf[p:p + l].decode("utf8", "replace"))
        else:
            l = struct.unpack_from("<H", buf, p)[0]; p += 2
            if l & 0x8000:
                l = ((l & 0x7fff) << 16) | struct.unpack_from("<H", buf, p)[0]; p += 2
            out.append(buf[p:p + 2 * l].decode("utf16", "replace"))
    return out, off + size


def main():
    apk, rx = sys.argv[1], re.compile(sys.argv[2])
    buf = zipfile.ZipFile(apk).read("resources.arsc")
    _, hsz, size, npkg = struct.unpack_from("<HHII", buf, 0)
    gstr, off = pool(buf, hsz)
    byid, hits = {}, []
    while off < size:
        typ, phsz, psize = struct.unpack_from("<HHI", buf, off)
        if typ != 0x200:
            off += psize; continue
        types_off, _, keys_off = struct.unpack_from("<III", buf, off + 268)[0], 0, struct.unpack_from("<I", buf, off + 276)[0]
        tnames, _ = pool(buf, off + types_off)
        knames, _ = pool(buf, off + keys_off)
        c = off + phsz
        end = off + psize
        while c < end:
            ctyp, chsz, csize = struct.unpack_from("<HHI", buf, c)
            if ctyp == 0x201:  # type chunk
                tid, _, _, n, estart = struct.unpack_from("<BBHII", buf, c + 8)
                cfg_size = struct.unpack_from("<I", buf, c + 20)[0]
                cfg = buf[c + 20:c + 20 + cfg_size]
                lang = cfg[8:10].rstrip(b"\0").decode("ascii", "replace")
                eoffs = struct.unpack_from("<%dI" % n, buf, c + chsz)
                tname = tnames[tid - 1]
                for i, eo in enumerate(eoffs):
                    if eo == 0xFFFFFFFF:
                        continue
                    e = c + estart + eo
                    esz, eflags, kidx = struct.unpack_from("<HHI", buf, e)
                    name = "%s/%s" % (tname, knames[kidx])
                    resid = (0x7f << 24) | (tid << 16) | i
                    if not (eflags & 1) and lang in ("", "en"):
                        _, _, dt, d = struct.unpack_from("<HBBI", buf, e + esz)
                        if dt == 3:
                            byid[resid] = gstr[d]
                    if not rx.search(name):
                        continue
                    vals = []
                    if eflags & 1:  # complex (array/style)
                        parent, cnt = struct.unpack_from("<II", buf, e + 8)
                        q = e + esz
                        for _ in range(cnt):
                            _, _, _, dt, d = struct.unpack_from("<IHBBI", buf, q)
                            vals.append(gstr[d] if dt == 3 else "0x%x:%d" % (dt, d))
                            q += 12
                    else:
                        _, _, dt, d = struct.unpack_from("<HBBI", buf, e + esz)
                        vals.append(gstr[d] if dt == 3 else "0x%x:%d" % (dt, d))
                    if lang in ("", "en"):
                        hits.append((name, lang or "-", vals))
            c += csize
        off += psize
    for name, lang, vals in hits:
        vals = [byid.get(int(v[4:]), v) if v.startswith("0x1:") else v for v in vals]
        print("%-55s [%s] %s" % (name, lang, vals))


main()
