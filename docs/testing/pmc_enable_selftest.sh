#!/usr/bin/env bash
#
# Check pmc_read's register table against what real NV2A silicon reads (#188),
# without building the emulator.
#
#   docs/testing/pmc_enable_selftest.sh
#
# Why this shape. An agent worktree cannot build the native side, and this is
# thirty lines of switch statement, so the alternative is no check at all.
# Extraction is by ANCHOR from hw/xbox/nv2a/pmc.c on every run rather than a
# pasted copy: a copy drifts from the original silently and then certifies
# code that is no longer in the tree. If the anchors stop matching, this fails
# loudly instead of testing nothing.
#
# The second half checks that pmc_write is still the no-op #188 found it as.
# That is not tidiness: writing 0 to NV_PMC_ENABLE HALTED THE PHYSICAL CONSOLE
# in the sweep that found this register, and #188 is explicit that the
# bit-field semantics are not established -- bits 20 and 24 are assigned by
# nothing in this tree, and the one state anyone has measured is an idle
# console. Modelling a write means modelling a halt on a guess. So the
# write path stays a silent no-op, and this says so in a way that a later edit
# has to notice.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/../../hw/xbox/nv2a/pmc.c"
REGS="$HERE/../../hw/xbox/nv2a/nv2a_regs.h"
[ -f "$SRC" ]  || { echo "cannot find $SRC" >&2; exit 2; }
[ -f "$REGS" ] || { echo "cannot find $REGS" >&2; exit 2; }

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# Each function runs from its signature to its own closing brace at column 0.
# Bounded on the brace, not on the next function's signature or on EOF: a
# helper interposed between the two would otherwise be compiled into the read
# extract against this file's stub set (reported as "pmc.c did not compile"),
# and a later function mentioning the constant would be refused as though
# pmc_write had changed. Both were reproduced in audit pass 1 (L1, L2).
START=$(grep -n '^uint64_t pmc_read(' "$SRC" | cut -d: -f1)
WSTART=$(grep -n '^void pmc_write(' "$SRC" | cut -d: -f1)
if [ -z "$START" ] || [ -z "$WSTART" ] || [ "$WSTART" -le "$START" ]; then
    echo "anchors not found in pmc.c -- the functions moved, were renamed," >&2
    echo "or pmc_write no longer follows pmc_read." >&2
    echo "  '^uint64_t pmc_read('  : ${START:-MISSING}" >&2
    echo "  '^void pmc_write('     : ${WSTART:-MISSING}" >&2
    exit 2
fi

# end_of_function <first line of the function> -> absolute line of its '^}'
end_of_function() {
    local first="$1" rel
    rel=$(sed -n "${first},\$p" "$SRC" | grep -n '^}' | head -1 | cut -d: -f1)
    [ -n "$rel" ] || return 1
    echo $((first + rel - 1))
}
END=$(end_of_function "$START")   || { echo "pmc_read has no closing brace at column 0" >&2; exit 2; }
WEND=$(end_of_function "$WSTART") || { echo "pmc_write has no closing brace at column 0" >&2; exit 2; }
if [ "$END" -ge "$WSTART" ]; then
    echo "pmc_read's closing brace ($END) is not before pmc_write ($WSTART):" >&2
    echo "brace-matching by column-0 '}' has stopped working on this file." >&2
    exit 2
fi
sed -n "${START},${END}p"   "$SRC" > "$TMP/pmc_read_extract.c"
sed -n "${WSTART},${WEND}p" "$SRC" > "$TMP/pmc_write_extract.c"

# A silent mis-extract compiles to something empty and "passes", so both
# halves are confirmed to contain what they are named for.
for want in 'uint64_t pmc_read' 'NV_PMC_BOOT_0' 'nv2a_reg_log_read'; do
    grep -q "$want" "$TMP/pmc_read_extract.c" || {
        echo "read extract is missing $want -- the anchors matched but the" >&2
        echo "block is wrong" >&2; exit 2; }
done
grep -q 'void pmc_write' "$TMP/pmc_write_extract.c" || {
    echo "write extract is missing pmc_write" >&2; exit 2; }

# --- the write path must still be the no-op #188 measured around ---
#
# Anchored on the CODE, not on prose: a comment mentioning NV_PMC_ENABLE in
# pmc_write is fine and in fact likely, so the check is for a case label and
# for the measured constant appearing on the write side.
#
# On the OFFSET as well as the macro. Audit pass 1 (M1) built the other
# spelling -- `case 0x200:` in pmc_write -- and this script reported 8 checks,
# 0 failures against a tree carrying a write model for the halting register.
# Every existing arm in pmc_write uses a macro, but the offset is what a
# future editor copies out of nv2a_regs.h (0x00000200) or a probe log
# (0xFD400200), so the guard has to know both. The `...` alternative catches
# the GCC range form, which is how #190's block (0x204-0x2FC) would arrive.
fail=0
if grep -qE \
    '^[[:space:]]*case[[:space:]]+(NV_PMC_ENABLE|0[xX]0*200|512)[[:space:]]*(\.\.\.|:)' \
        "$TMP/pmc_write_extract.c"; then
    echo "REFUSED: pmc_write has a case for NV_PMC_ENABLE (0x200)." >&2
    echo "  Writing 0 to this register halted the physical console, and #188" >&2
    echo "  does not establish which bits gate what. A write model needs the" >&2
    echo "  envytools cross-reference #188 asks for, not this lane." >&2
    fail=1
fi
if grep -qiE '0[xX]0*1110000' "$TMP/pmc_write_extract.c"; then
    echo "REFUSED: the measured read-back constant appears in pmc_write." >&2
    echo "  0x01110000 is what silicon READS. Nothing measured says what" >&2
    echo "  happens when it is written." >&2
    fail=1
fi
[ "$fail" -eq 0 ] || exit 1

CC="${CC:-gcc}"
"$CC" -std=gnu11 -Wall -Wextra -Wformat=2 -Werror \
      -I"$TMP" -I"$(dirname "$REGS")" -I"$HERE" \
      -o "$TMP/t" "$HERE/pmc_enable_selftest.c" || {
    echo "the extracted pmc_read did not compile cleanly" >&2; exit 1; }
"$TMP/t"
