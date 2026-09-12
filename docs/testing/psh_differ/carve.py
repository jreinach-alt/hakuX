#!/usr/bin/env python3
"""Produce a copy of psh.c with the emulator-state functions removed.

psh.c holds two separable halves. One half turns a PshState into GLSL and
reads nothing else; the other half fills a PshState in from a live PGRAPHState.
The differ only exercises the first, but a C file compiles whole, and the
second half needs the real PGRAPHState -- which needs the real pgraph.h, which
needs a configured QEMU tree.

So the second half is cut out. Each removed line becomes a blank line, so
every line that survives keeps its original number and compiler diagnostics
point at the real psh.c.

This is a build step, not an edit: psh.c on disk is untouched. If a signature
below stops matching, or a new function starts reading PGRAPHState, this exits
non-zero and names it rather than carving something unexpected.
"""

import argparse
import re
import sys
from pathlib import Path

# Functions that read emulator state, per source file. Each entry is matched
# against the start of a line.
CARVE = {
    "psh.c": (
        "static uint32_t get_color_key_mask_for_texture(PGRAPHState *pg, int i)",
        "bool pgraph_glsl_polygon_stipple_enabled(PGRAPHState *pg)",
        "int pgraph_glsl_window_clip_count(PGRAPHState *pg)",
        "void pgraph_glsl_set_psh_state(PGRAPHState *pg, PshState *state)",
        "void pgraph_glsl_set_psh_uniform_values(PGRAPHState *pg,",
    ),
    "common.c": (
        "void pgraph_glsl_set_clip_range_uniform_value(PGRAPHState *pg, float clipRange[4])",
    ),
}


def find_body_end(text: str, start: int) -> int:
    """Index just past the closing brace of the block opening at/after start.

    Skips braces inside string and character literals and inside comments --
    psh.c is mostly GLSL held in C strings, and that GLSL is full of braces.
    """
    i = text.index("{", start)
    depth = 0
    while i < len(text):
        c = text[i]
        if c == "/" and text[i + 1 : i + 2] == "/":
            i = text.find("\n", i)
            if i < 0:
                break
            continue
        if c == "/" and text[i + 1 : i + 2] == "*":
            end = text.find("*/", i + 2)
            if end < 0:
                break
            i = end + 2
            continue
        if c in "\"'":
            quote = c
            i += 1
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    break
                i += 1
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise SystemExit("carve.py: unterminated function body from offset %d" % start)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    if args.source.name not in CARVE:
        raise SystemExit(
            "carve.py: nothing known about %s. Add it to CARVE with the "
            "functions that read PGRAPHState." % args.source.name
        )
    signatures = CARVE[args.source.name]

    text = args.source.read_text()
    lines = text.splitlines(keepends=True)
    # Byte offset of the start of each line, for mapping matches to lines.
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)

    def line_of(offset: int) -> int:
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if offsets[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo

    blank = set()
    for sig in signatures:
        idx = text.find("\n" + sig)
        if idx < 0:
            raise SystemExit(
                "carve.py: no line starts with:\n  %s\n"
                "psh.c changed. Update CARVE in %s to match, and check whether "
                "the generator still reads nothing but PshState." % (sig, __file__)
            )
        start = idx + 1
        end = find_body_end(text, start)
        blank.update(range(line_of(start), line_of(end - 1) + 1))

    # Anything else taking a PGRAPHState would not compile against the opaque
    # type in the shim. Catch it here, where the message can say why.
    for n, line in enumerate(lines):
        if n in blank or not re.match(r"^[A-Za-z_].*PGRAPHState", line):
            continue
        raise SystemExit(
            "carve.py: %s:%d reads emulator state and is not carved:\n  %s"
            "Add it to CARVE if it belongs to the state half, or split it out "
            "of psh.c if the generator now depends on it."
            % (args.source, n + 1, line)
        )

    out = ['#line 1 "%s"\n' % args.source]
    out += ["\n" if n in blank else line for n, line in enumerate(lines)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(out))
    print(
        "carve.py: %s -> %s (%d of %d lines removed)"
        % (args.source, args.output, len(blank), len(lines)),
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
