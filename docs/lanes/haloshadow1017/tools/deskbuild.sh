#!/bin/bash
# Desktop (lavapipe) build of this worktree, configured as x1port1012's build-linux was (#1038).
#   deskbuild.sh            configure if needed, then ninja; prints DESKBUILD_EXIT=<rc> last
set -u
WT=/home/justin/hakux-work/wt/haloshadow1017
B=$WT/build-linux
R=/home/justin/.local/nxdk-tools/root
export PATH=/home/justin/.local/nxdk-tools/bin:$PATH
export PKG_CONFIG_PATH=$R/usr/lib/x86_64-linux-gnu/pkgconfig:$R/usr/share/pkgconfig
export LD_LIBRARY_PATH=$R/usr/lib/x86_64-linux-gnu:$R/lib/x86_64-linux-gnu
INC=""
for d in usr/include usr/include/x86_64-linux-gnu usr/include/gtk-3.0 usr/include/pango-1.0 \
         usr/include/harfbuzz usr/include/cairo usr/include/gdk-pixbuf-2.0 usr/include/atk-1.0 \
         usr/include/at-spi2-atk/2.0 usr/include/at-spi-2.0 usr/include/dbus-1.0 \
         usr/include/freetype2 usr/include/libpng16 usr/include/pixman-1 usr/include/fribidi \
         usr/include/webp usr/include/gio-unix-2.0 usr/include/libmount usr/include/blkid \
         usr/include/slirp usr/include/SDL2 usr/include/libdrm usr/include/epoxy \
         usr/lib/x86_64-linux-gnu/dbus-1.0/include; do
  INC="$INC -idirafter $R/$d"
done
mkdir -p "$B"
if [ ! -f "$B/build.ninja" ]; then
  (cd "$B" && ../configure --target-list=i386-softmmu --disable-werror --disable-docs \
     --disable-guest-agent --disable-tools \
     "--extra-cflags=-DXBOX=1$INC" "--extra-cxxflags=-DXBOX=1$INC" \
     "--extra-ldflags=-L$R/usr/lib/x86_64-linux-gnu -Wl,-rpath,$R/usr/lib/x86_64-linux-gnu")
  rc=$?
  if [ $rc -ne 0 ]; then echo "DESKBUILD_EXIT=$rc (configure)"; exit $rc; fi
fi
ninja -C "$B" -j8 qemu-system-i386
rc=$?
echo "DESKBUILD_EXIT=$rc"
exit $rc
