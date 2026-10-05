#!/bin/bash
# lane.pmucounters (#433): build pmuprobe (aarch64, Android API 30) with the
# NDK. -Wall -Werror so the hook it includes is held to the tree's bar.
set -eu
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NDK=${NDK:-/home/justin/Android/Sdk/ndk/29.0.14206865}
CC=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/aarch64-linux-android30-clang
OUT=${1:-$HERE/pmuprobe}
"$CC" -O2 -Wall -Wextra -Wno-unused-parameter -Werror \
    -o "$OUT" "$HERE/pmuprobe.c"
echo "built $OUT"
# DIS=1: also write the disassembly next to it (check the control kernels:
# alu1 must be 64 dependent adds, ind* a `br` through the table).
if [ "${DIS:-0}" = 1 ]; then
    "$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-objdump" -d \
        --no-show-raw-insn "$OUT" > "$OUT.dis"
    echo "disassembly $OUT.dis"
fi
