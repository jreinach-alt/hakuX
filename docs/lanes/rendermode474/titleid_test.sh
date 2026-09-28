#!/bin/bash
# Host test of ReadDiscTitleId (xemu_android.cpp, #474).
#
# Cuts ReadLe32 .. ReadDiscTitleId out of the source as it is (so the test
# follows the code), compiles it with g++, and runs it on:
#   - synthetic images: an xiso, the same content at the redump partition
#     start (sparse), a tree whose default.xbe is only reachable to the right,
#     no magic, and no default.xbe;
#   - any real images given as arguments, printing each title ID, so they
#     can be checked against the staging manifest.
# Exit 0 only if every synthetic case reads what it should.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
SRC="$HERE/../../../android/app/src/main/cpp/xemu_android.cpp"
T=$(mktemp -d "$HERE/.titleid.XXXX")
trap 'rm -rf "$T"' EXIT

{
  printf '#include <cerrno>\n#include <cstdint>\n#include <cstdio>\n#include <cstdlib>\n#include <cstring>\n'
  printf '#include <fcntl.h>\n#include <strings.h>\n#include <unistd.h>\n#include <vector>\n'
  awk '/^static uint32_t ReadLe32/{on=1} on{print} on&&/^}/&&seen{exit} /^static uint32_t ReadDiscTitleId/{seen=1}' "$SRC"
  cat <<'EOF'
int main(int argc, char** argv) {
  int bad = 0;
  for (int i = 1; i < argc; i++) {
    const char* want = strchr(argv[i], '=');
    std::string path = want ? std::string(argv[i], want - argv[i]) : argv[i];
    int fd = open(path.c_str(), O_RDONLY);
    uint32_t tid = fd >= 0 ? ReadDiscTitleId(fd) : 0;
    if (fd >= 0) close(fd);
    char got[16];
    snprintf(got, sizeof(got), "%08X", tid);
    if (want) {
      bool ok = strcmp(got, want + 1) == 0;
      bad += !ok;
      printf("%s %s want=%s got=%s\n", ok ? "ok " : "BAD", path.c_str(), want + 1, got);
    } else {
      printf("    %s title=%s\n", path.c_str(), got);
    }
  }
  return bad ? 1 : 0;
}
EOF
} > "$T/t.cc"
sed -i '1i #include <string>' "$T/t.cc"
g++ -std=c++17 -O1 -Wall -o "$T/t" "$T/t.cc" || { echo "BAD: does not compile"; exit 1; }

# mkimg OUT BASE TID LAYOUT: a minimal XDVDFS image, partition at BASE.
#   LAYOUT=root   default.xbe is the root node
#   LAYOUT=right  root is "a.txt", default.xbe its right child
#   LAYOUT=none   only "a.txt"
#   LAYOUT=nomagic  as root, with the second magic missing
python3 - "$T" <<'EOF'
import struct, sys, os
T = sys.argv[1]
def entry(left, right, sector, size, name):
    b = struct.pack('<HHIIBB', left, right, sector, size, 0x20, len(name)) + name
    return b + b'\xff' * (-len(b) % 4)
def mkimg(out, base, tid, layout):
    S = 2048
    with open(out, 'wb') as f:
        vd = bytearray(S)
        vd[0:20] = b'MICROSOFT*XBOX*MEDIA'
        vd[0x14:0x18] = struct.pack('<I', 40)
        vd[0x18:0x1c] = struct.pack('<I', S)
        if layout != 'nomagic':
            vd[0x7EC:0x7EC + 20] = b'MICROSOFT*XBOX*MEDIA'
        f.seek(base + 32 * S); f.write(vd)
        if layout in ('root', 'nomagic'):
            d = entry(0, 0, 50, 0x1000, b'default.xbe')
        elif layout == 'right':
            first = entry(0, 0, 60, 16, b'a.txt')
            d = entry(0, len(first) // 4, 60, 16, b'a.txt')
            d = d + entry(0, 0, 50, 0x1000, b'DEFAULT.XBE')
        else:
            d = entry(0, 0, 60, 16, b'a.txt')
        f.seek(base + 40 * S); f.write(d + b'\xff' * (S - len(d)))
        x = bytearray(0x1000)
        x[0:4] = b'XBEH'
        x[0x104:0x108] = struct.pack('<I', 0x10000)
        x[0x118:0x11c] = struct.pack('<I', 0x10000 + 0x200)
        x[0x208:0x20c] = struct.pack('<I', tid)
        f.seek(base + 50 * S); f.write(x)
mkimg(f'{T}/xiso.iso', 0, 0x54430006, 'root')
mkimg(f'{T}/redump.iso', 0x18300000, 0x4541000D, 'root')
mkimg(f'{T}/right.iso', 0, 0x4541000D, 'right')
mkimg(f'{T}/none.iso', 0, 0x4541000D, 'none')
mkimg(f'{T}/nomagic.iso', 0, 0x4541000D, 'nomagic')
EOF

"$T/t" "$T/xiso.iso=54430006" "$T/redump.iso=4541000D" "$T/right.iso=4541000D" \
       "$T/none.iso=00000000" "$T/nomagic.iso=00000000"
rc=$?
[ $# -gt 0 ] && "$T/t" "$@"
exit $rc
