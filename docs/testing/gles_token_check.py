#!/usr/bin/env python3
"""Catch desktop-only GL tokens reaching the GLES build, before CI does.

WHY THIS EXISTS

`pad_write_color_factor()` (#158) named `GL_SRC1_ALPHA` outside any
`__ANDROID__` guard. The function is dead code on Android -- the capability
flag is never set there -- but dead code still has to parse, and the GLES
headers spell that token `GL_SRC1_ALPHA_EXT`, so the arm64-v8a build failed to
compile. Audit pass 1 on PR #162 found it, H1.

The runtime exclusion had landed in two places and the compile-time one in
neither, and nothing local could tell: the desktop build was green, preflight
was green, and the only signal was a CI job. On a machine with no NDK -- which
is every cloud lane -- this script is the only pre-push check there is.

WHAT IT DOES, AND WHAT IT DOES NOT

It strips the branches a GLES build does not compile, handling `__ANDROID__`
conditionals only, and reports any curated desktop-only token left in code.
Comments are removed first, so prose about a token is not a finding.

It is NOT a preprocessor and NOT a compiler. A green result means "none of the
tokens in the list below survive the guards", not "this compiles on GLES". The
list is curated by hand rather than derived from a GLES header, because a
machine without an NDK has no GLES header to derive it from. Extend it when a
new one bites; a check that overstates its coverage is worse than none.

    usage: gles_token_check.py [path ...]      (default: the GL renderer)
    exit 0 clean, 1 finding, 2 bad usage
"""
import os
import re
import sys

# Tokens the desktop GL headers define and the GLES 3.x headers do not, or
# define only with an _EXT/_OES suffix behind an extension that is not core.
# Each entry says which extension provides it on GLES, so a future reader can
# judge whether guarding or suffixing is the right answer.
DESKTOP_ONLY = {
    'GL_SRC1_ALPHA':            'EXT_blend_func_extended (not core in GLES 3.0)',
    'GL_ONE_MINUS_SRC1_ALPHA':  'EXT_blend_func_extended (not core in GLES 3.0)',
    'GL_SRC1_COLOR':            'EXT_blend_func_extended (not core in GLES 3.0)',
    'GL_ONE_MINUS_SRC1_COLOR':  'EXT_blend_func_extended (not core in GLES 3.0)',
    'GL_FILL':                  'no polygon mode in GLES at all',
    'GL_LINE_SMOOTH':           'removed in GLES',
    'GL_POLYGON_SMOOTH':        'removed in GLES',
    'GL_CLAMP_TO_BORDER':       'EXT_texture_border_clamp (not core in GLES 3.0)',
    'GL_TEXTURE_BORDER_COLOR':  'EXT_texture_border_clamp (not core in GLES 3.0)',
    'GL_DEPTH_CLAMP':           'no GLES equivalent',
}

DEFAULT_PATHS = ('hw/xbox/nv2a/pgraph/gl',)


def decomment(text):
    """Blank out comments, preserving line numbering."""
    text = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'),
                  text, flags=re.S)
    text = re.sub(r'//[^\n]*', '', text)
    # A token inside a string literal is not a reference either.
    return re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', text)


ANDROID_IF = re.compile(r'#\s*(ifdef|ifndef)\s+__ANDROID__\b')
ANDROID_IF_DEFINED = re.compile(r'#\s*if\s+(!\s*)?defined\s*\(\s*__ANDROID__\s*\)\s*$')
ANY_IF = re.compile(r'#\s*if(def|ndef)?\b')
DEFINED_TOK = re.compile(r'defined\s*\(?\s*([A-Za-z_]\w*)')
IFDEF_TOK = re.compile(r'#\s*if(?:n)?def\s+([A-Za-z_]\w*)')


def gles_visible_lines(path):
    """The lines an arm64-v8a compile sees, as far as __ANDROID__ decides it.

    EVERY conditional goes on the stack, because only then do `#else` and
    `#endif` pair with the right one -- an earlier version tracked only the
    __ANDROID__ ones and let an inner `#ifdef GL_FOO ... #endif` pop the outer
    frame, which mis-reported six lines of constants.h as reachable. Non
    __ANDROID__ frames are treated as live, which is the conservative
    direction: it can report a line some other guard excludes, never hide one.

    Each frame also carries the tokens its condition TESTS FOR. A reference to
    a token inside `#ifdef <that token>` is the correct portability idiom, not
    a finding, so those are not reported.
    """
    stack, out = [], []
    for n, line in enumerate(decomment(open(path).read()).split('\n'), 1):
        s = line.strip()
        if ANY_IF.match(s):
            m = ANDROID_IF.match(s)
            if m:
                live = (m.group(1) == 'ifdef')
            elif ANDROID_IF_DEFINED.match(s):
                live = not ANDROID_IF_DEFINED.match(s).group(1)
            else:
                live = True                     # unknown condition: assume taken
            tested = set(DEFINED_TOK.findall(s)) | set(IFDEF_TOK.findall(s))
            stack.append({'live': live, 'tested': tested})
            continue
        if stack and re.match(r'#\s*elif\b', s):
            stack[-1]['live'] = True            # unknown arm: assume taken
            stack[-1]['tested'] |= set(DEFINED_TOK.findall(s))
            continue
        if stack and re.match(r'#\s*else\b', s):
            stack[-1]['live'] = not stack[-1]['live']
            continue
        if stack and re.match(r'#\s*endif\b', s):
            stack.pop()
            continue
        if all(f['live'] for f in stack):
            guarded = set().union(*(f['tested'] for f in stack)) if stack else set()
            out.append((n, line, guarded))
    return out


def sources(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        for root, _, names in os.walk(p):
            for name in sorted(names):
                if name.endswith(('.c', '.h')):
                    yield os.path.join(root, name)


def main(argv):
    paths = argv[1:] or list(DEFAULT_PATHS)
    missing = [p for p in paths if not os.path.exists(p)]
    if missing:
        sys.stderr.write('no such path: %s\n' % ', '.join(missing))
        sys.stderr.write('run from the repository root\n')
        return 2

    findings = []
    scanned = 0
    for path in sources(paths):
        scanned += 1
        for n, line, guarded in gles_visible_lines(path):
            for tok, why in DESKTOP_ONLY.items():
                if tok in guarded:
                    continue        # `#ifdef <tok>` around it is the right idiom
                if re.search(r'\b%s\b' % re.escape(tok), line):
                    findings.append((path, n, tok, why, line.strip()))

    for path, n, tok, why, text in findings:
        print('%s:%d: %s reaches the GLES build -- %s' % (path, n, tok, why))
        print('    %s' % text)
    print('%d file%s scanned, %d finding%s'
          % (scanned, '' if scanned == 1 else 's',
             len(findings), '' if len(findings) == 1 else 's'))
    if findings:
        print('guard the whole branch, not just the flag: a compile-time-false')
        print('condition still leaves the call inside it to be parsed.')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
