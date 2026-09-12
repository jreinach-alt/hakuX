#!/usr/bin/env python3
"""Fail if an Android-only symbol is used outside `#ifdef __ANDROID__`.

Why this exists
---------------

The Android build and the desktop build compile the same core sources. A call
to an Android-only symbol therefore compiles fine and links fine on Android,
and fails at *link* on the desktop -- which no amount of Android-side
verification can catch. That happened on 2026-09-12: an
`__android_log_print` added for audio instrumentation passed the Android build,
was verified present in the APK, and broke the desktop link with `undefined
reference`. Every other call in the tree is wrapped in `#ifdef __ANDROID__`;
that one was not.

This is not a substitute for building both targets. It is a cheap gate for the
one failure class that has actually occurred, runnable with no toolchain, no
system packages and no CI minutes -- CI on this project is a finite monthly
budget and must not be used as a self-check.

The nesting has to be tracked properly rather than scanned backwards for the
nearest `#ifdef`: a naive version of this check reported 13 false positives on
a clean tree, including a *comment* that mentioned the guard.

Usage
-----

    check_android_guards.py [paths...]      # defaults to hw/ ui/ include/

Exit status is 1 if any unguarded use is found, so it can gate a push.
"""
import os
import re
import sys

# Symbols that resolve only when linking against Android's liblog/NDK.
ANDROID_ONLY = (
    "__android_log_print",
    "__android_log_write",
    "__android_log_assert",
    "AAssetManager",
    "AAsset_",
    "ANativeWindow_",
    "AAudioStream",
    "AAudioStreamBuilder",
)

GUARD_OPEN = re.compile(r"^\s*#\s*if(?:def)?\s+(.*)$")
GUARD_ELIF = re.compile(r"^\s*#\s*elif\b(.*)$")
GUARD_ELSE = re.compile(r"^\s*#\s*else\b")
GUARD_END = re.compile(r"^\s*#\s*endif\b")

ANDROID_COND = re.compile(r"\b__ANDROID__\b")

# Match each symbol only at an identifier boundary. Plain substring matching
# reported 35 false positives on a clean tree, every one of them QEMU's own
# `HDAAudioStream` containing `AAudioStream`.
ANDROID_RE = [(s, re.compile(r"(?<![A-Za-z0-9_])" + re.escape(s)))
              for s in ANDROID_ONLY]


def strip_comments(src):
    """Blank out comment and string bodies, preserving line structure.

    Line count must survive so reported line numbers stay usable, and the text
    inside comments and string literals must not be scanned -- the false
    positives that motivated this were a comment naming the guard and a log
    format string naming the function.
    """
    out = []
    i, n = 0, len(src)
    state = None  # None | 'line' | 'block' | 'str' | 'chr'
    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state is None:
            if c == "/" and nxt == "/":
                state = "line"; out.append("  "); i += 2; continue
            if c == "/" and nxt == "*":
                state = "block"; out.append("  "); i += 2; continue
            if c == '"':
                state = "str"; out.append(" "); i += 1; continue
            if c == "'":
                state = "chr"; out.append(" "); i += 1; continue
            out.append(c); i += 1; continue
        if state == "line":
            if c == "\n":
                state = None; out.append("\n")
            else:
                out.append(" ")
            i += 1; continue
        if state == "block":
            if c == "*" and nxt == "/":
                state = None; out.append("  "); i += 2; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
        if state in ("str", "chr"):
            if c == "\\":
                out.append("  "); i += 2; continue
            if (state == "str" and c == '"') or (state == "chr" and c == "'"):
                state = None; out.append(" "); i += 1; continue
            out.append("\n" if c == "\n" else " "); i += 1; continue
    return "".join(out)


def unguarded_uses(path):
    """Yield (line_no, symbol, line_text) for uses outside an __ANDROID__ guard."""
    raw = open(path, errors="replace").read()
    code = strip_comments(raw).split("\n")
    rawlines = raw.split("\n")

    # stack of bools: is this conditional level known to require __ANDROID__?
    stack = []
    findings = []
    for idx, line in enumerate(code):
        if GUARD_END.match(line):
            if stack:
                stack.pop()
            continue
        m = GUARD_OPEN.match(line)
        if m:
            stack.append(bool(ANDROID_COND.search(m.group(1))))
            continue
        if GUARD_ELIF.match(line) or GUARD_ELSE.match(line):
            # The #else of an __ANDROID__ guard is explicitly NOT Android, and
            # an #elif changes the condition, so either way this branch no
            # longer counts as guarded.
            if stack:
                stack[-1] = False
            continue
        if any(stack):
            continue
        for sym, rx in ANDROID_RE:
            if rx.search(line):
                findings.append((idx + 1, sym, rawlines[idx].strip()))
                break
    return findings


def main(argv):
    roots = argv[1:] or ["hw", "ui", "include"]
    bad = []
    scanned = 0
    for root in roots:
        if os.path.isfile(root):
            files = [root]
        else:
            files = []
            for dirpath, _dirnames, filenames in os.walk(root):
                for f in filenames:
                    if f.endswith((".c", ".h", ".cpp", ".cc")):
                        files.append(os.path.join(dirpath, f))
        for f in sorted(files):
            scanned += 1
            for line_no, sym, text in unguarded_uses(f):
                bad.append((f, line_no, sym, text))

    if not bad:
        print(f"android guards ok ({scanned} files scanned)")
        return 0

    print(f"UNGUARDED ANDROID-ONLY SYMBOLS ({len(bad)} in {scanned} files)")
    print("These compile and link on Android and fail the desktop link.")
    print("Wrap each in #ifdef __ANDROID__ / #endif.\n")
    for f, line_no, sym, text in bad:
        print(f"  {f}:{line_no}: {sym}")
        print(f"      {text[:100]}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
