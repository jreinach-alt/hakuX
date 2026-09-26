#!/usr/bin/env bash
#
# Check pmc_read's register table against what real NV2A silicon reads
# (#188 NV_PMC_ENABLE, #190 the 0x160 / 0x204-0x2FC read-1 region), without
# building the emulator.
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
# NV_PMC_ENABLE's write side is modelled as STORAGE AND NOTHING ELSE (#188,
# after #203 measured the implemented bits): pmc_write and pmc_reset are
# extracted as well and driven by the C half, which checks the stored value
# and that a write to it touches no other state. Which engine each bit gates
# is unmeasured, so gating is what the C half refuses.
#
# #190's region (0x160, 0x204-0x2FC) is still read-side only, and the grep
# guards below still refuse a write arm there: it begins one dword after the
# register whose write of 0 halted the physical console, and nothing measured
# says what a write into it does.
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
RSTART=$(grep -n '^void pmc_reset(' "$SRC" | cut -d: -f1)
if [ -z "$START" ] || [ -z "$WSTART" ] || [ -z "$RSTART" ] \
   || [ "$WSTART" -le "$START" ]; then
    echo "anchors not found in pmc.c -- the functions moved, were renamed," >&2
    echo "or pmc_write no longer follows pmc_read." >&2
    echo "  '^uint64_t pmc_read('  : ${START:-MISSING}" >&2
    echo "  '^void pmc_write('     : ${WSTART:-MISSING}" >&2
    echo "  '^void pmc_reset('     : ${RSTART:-MISSING}" >&2
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
REND=$(end_of_function "$RSTART") || { echo "pmc_reset has no closing brace at column 0" >&2; exit 2; }
if [ "$END" -ge "$WSTART" ]; then
    echo "pmc_read's closing brace ($END) is not before pmc_write ($WSTART):" >&2
    echo "brace-matching by column-0 '}' has stopped working on this file." >&2
    exit 2
fi
sed -n "${START},${END}p"   "$SRC" > "$TMP/pmc_read_extract.c"
sed -n "${WSTART},${WEND}p" "$SRC" > "$TMP/pmc_write_extract.c"
sed -n "${RSTART},${REND}p" "$SRC" > "$TMP/pmc_reset_extract.c"

# A silent mis-extract compiles to something empty and "passes", so both
# halves are confirmed to contain what they are named for.
for want in 'uint64_t pmc_read' 'NV_PMC_BOOT_0' 'nv2a_reg_log_read'; do
    grep -q "$want" "$TMP/pmc_read_extract.c" || {
        echo "read extract is missing $want -- the anchors matched but the" >&2
        echo "block is wrong" >&2; exit 2; }
done
grep -q 'void pmc_write' "$TMP/pmc_write_extract.c" || {
    echo "write extract is missing pmc_write" >&2; exit 2; }
grep -q 'void pmc_reset' "$TMP/pmc_reset_extract.c" || {
    echo "reset extract is missing pmc_reset" >&2; exit 2; }

# --- #190's region must still have no write model ---
#
# Anchored on the CODE, not on prose: the check is for a case label, so a
# comment mentioning an offset is fine.
fail=0
# Any 0x2xx offset but 0x200 itself is refused wholesale rather than the
# measured 63: the reason is the neighbouring register that halted the
# console, and that reason does not stop at 0x2FC. 0x160 is named separately.
# 0x200 is excluded because NV_PMC_ENABLE now HAS a write arm (#188), and
# `case 0x200:` is a spelling of it rather than of #190's region; until #188
# the guard that refused it lived here too (pmc188/mutants.py M1-M1c).
#
# Two patterns, because a range has two ends. The first catches an arm that
# BEGINS in the region; the second catches one that ENDS in it, which is the
# hole pass 2 of #188's audit measured and named (P2: `case 0x1FC ... 0x2FC:`
# passed both guards, 8 checks 0 failures). That shape was contrived while the
# region was unmodelled; now that pmc_read answers 0x204-0x2FC, it is the
# shape a write model would actually arrive in.
#
# THE REACH, written down rather than left in the regex -- the thing pass 2
# asked for. Caught: any case label or range endpoint spelled in hex as 0x160
# or 0x2xx other than 0x200, and 0x160 in decimal. NOT caught here: a range
# whose BOTH endpoints lie outside the region while spanning it
# (`case 0x100 ... 0x400:`), and decimal 516-764. Since #188 gave 0x200 a
# write arm, a spanning range that includes 0x200 is refused by gcc as a
# duplicate case instead (cloud190's K1 now goes red; see
# docs/lanes/cloud-188/NOTES.md). Grep cannot evaluate an interval; closing that properly
# means parsing the case labels and comparing numbers, which is the write
# lane's job to build if it wants the guard to be airtight. Both holes are
# mutants in docs/lanes/cloud190/mutants.py (K1, K2), expected GREEN, so the
# limit is a measurement someone can re-run rather than a sentence to trust.
if grep -qE \
    '^[[:space:]]*case[[:space:]]+(0[xX]0*(160|2(0[1-9A-Fa-f]|[1-9A-Fa-f][0-9A-Fa-f]))|352)[[:space:]]*(\.\.\.|:)' \
        "$TMP/pmc_write_extract.c" \
   || grep -qE \
    '^[[:space:]]*case[[:space:]]+.*\.\.\.[[:space:]]*(0[xX]0*(160|2(0[1-9A-Fa-f]|[1-9A-Fa-f][0-9A-Fa-f]))|352)[[:space:]]*:' \
        "$TMP/pmc_write_extract.c"; then
    echo "REFUSED: pmc_write has a case in #190's read-1 region." >&2
    echo "  0x160 and 0x204-0x2FC read 0x00000001 on silicon. Nothing" >&2
    echo "  measured says what a WRITE there does, and the region begins" >&2
    echo "  one dword after the register whose write halted the console." >&2
    echo "  Whether the region is 63 live registers, an alias or a fixed" >&2
    echo "  unimplemented-read pattern is also untested -- see #190." >&2
    fail=1
fi
[ "$fail" -eq 0 ] || exit 1

CC="${CC:-gcc}"
"$CC" -std=gnu11 -Wall -Wextra -Wformat=2 -Werror \
      -I"$TMP" -I"$(dirname "$REGS")" -I"$HERE" \
      -o "$TMP/t" "$HERE/pmc_enable_selftest.c" || {
    echo "the extracted pmc_read/pmc_write/pmc_reset did not compile" >&2
    echo "cleanly against the stubs -- a new call in one of them (an engine" >&2
    echo "reset on an NV_PMC_ENABLE write, say) lands here first" >&2
    exit 1; }
"$TMP/t"
