#!/bin/bash
# Build the vsh-ff.c GLSL emitter (shadetie224's emit.c, extended with a
# position-only mode) against psh_differ's shims.  Output: vshemit/emit.
set -e
cd "$(dirname "$0")/../../../.."
D=docs/lanes/wparamcode223/vshemit
gcc -std=gnu11 -O0 -w -Idocs/testing/psh_differ/shim -Iinclude -I. \
    -Ihw/xbox/nv2a/pgraph/glsl $(pkg-config --cflags glib-2.0) \
    -o $D/emit $D/emit.c hw/xbox/nv2a/pgraph/glsl/vsh-ff.c \
    $(pkg-config --libs glib-2.0)
echo BUILD_OK
