#!/usr/bin/env python3
"""lane.pmucounters (#433): name the function at an offset in an ELF file.

  elfsyms.py LIB.so OFF [OFF...]      hex offsets from the library's load base
                                      (smph's off=), one "OFF func+0xN" line each
  elfsyms.py --apk APK.apk LIBNAME OFF...   the same, the .so read out of an APK

The [pmu433] smph lines give an offset from dladdr's dli_fbase. For a shared
object whose first PT_LOAD is at vaddr 0 (every NDK .so), a .symtab st_value
is the same offset. The APK's .so keeps its .symtab (build.gradle.kts:
jniLibs.keepDebugSymbols), so static functions are named too, which dladdr's
hint (dynamic symbols only) cannot do. Pure stdlib: no pyelftools, no binutils.
"""
import bisect
import io
import struct
import sys
import zipfile


def functions(data):
    """Sorted [(start, size, name)] of STT_FUNC symbols in .symtab/.dynsym."""
    if data[:4] != b"\x7fELF" or data[4] != 2:
        raise SystemExit("not a 64-bit ELF")
    end = "<" if data[5] == 1 else ">"
    shoff, = struct.unpack_from(end + "Q", data, 0x28)
    shentsize, shnum, shstrndx = struct.unpack_from(end + "HHH", data, 0x3a)
    secs = []
    for i in range(shnum):
        name, typ, flags, addr, off, size, link, info, align, entsize = \
            struct.unpack_from(end + "IIQQQQIIQQ", data, shoff + i * shentsize)
        secs.append((typ, off, size, link, entsize))
    out = {}
    for typ, off, size, link, entsize in secs:
        if typ not in (2, 11):          # SHT_SYMTAB, SHT_DYNSYM
            continue
        stroff = secs[link][1]
        for j in range(size // entsize):
            st_name, st_info, st_other, st_shndx, st_value, st_size = \
                struct.unpack_from(end + "IBBHQQ", data, off + j * entsize)
            if st_info & 0xf != 2 or not st_value:   # STT_FUNC
                continue
            e = data.index(b"\0", stroff + st_name)
            name = data[stroff + st_name:e].decode(errors="replace")
            if st_value not in out or typ == 2:
                out[st_value] = (st_value, st_size, name)
    return sorted(out.values())


def name_at(funcs, starts, off):
    i = bisect.bisect_right(starts, off) - 1
    if i < 0:
        return "?"
    start, size, name = funcs[i]
    if size and off >= start + size:
        return "?(after %s)" % name
    return "%s+0x%x" % (name, off - start)


def main(argv):
    if argv[1] == "--apk":
        z = zipfile.ZipFile(argv[2])
        member = [n for n in z.namelist() if n.endswith("/" + argv[3])
                  and "arm64" in n]
        if not member:
            raise SystemExit("no arm64 %s in %s" % (argv[3], argv[2]))
        data, offs = z.read(member[0]), argv[4:]
    else:
        data, offs = open(argv[1], "rb").read(), argv[2:]
    funcs = functions(data)
    starts = [f[0] for f in funcs]
    for o in offs:
        print("%s %s" % (o, name_at(funcs, starts, int(o, 16))))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
