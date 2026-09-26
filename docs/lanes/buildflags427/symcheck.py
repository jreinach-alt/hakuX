#!/usr/bin/env python3
"""Count the three host-runtime mechanisms of #427 in a libxemu.so.

usage: symcheck.py <libxemu.so | app.apk> [...]

For each library prints:
  emutls_calls     direct calls to __emutls_get_address
  emutls_vars      __emutls_v.* control variables (one per emulated TLS var)
  tls_segment      whether the library has a PT_TLS segment (native ELF TLS)
  outline_calls    direct calls to __aarch64_{cas,swp,ldadd,ldset,ldclr,ldeor}*
  outline_defs     __aarch64_* outline-atomic helpers defined in the library
  lse_insns        inline LSE instructions (cas/swp/ld{add,set,clr,eor}*)
  plt_total        JUMP_SLOT relocations (= PLT entries)
  plt_internal     PLT entries whose symbol the library itself defines --
                   the intra-library calls that go through a stub

Reads with the NDK's llvm tools; nothing is run on a device.
"""
import os
import re
import subprocess
import sys
import tempfile
import zipfile

NDK = os.path.expanduser('~/Android/Sdk/ndk/29.0.14206865/toolchains/llvm/prebuilt/linux-x86_64/bin')
READELF = os.path.join(NDK, 'llvm-readelf')
OBJDUMP = os.path.join(NDK, 'llvm-objdump')

OUTLINE = re.compile(r'\bbl\s+0x[0-9a-f]+\s+<(__aarch64_(?:cas|swp|ldadd|ldset|ldclr|ldeor)\w*)')
EMUTLS = re.compile(r'\bbl\s+0x[0-9a-f]+\s+<__emutls_get_address')
LSE = re.compile(r'\t(?:cas|casp|swp|ldadd|ldset|ldclr|ldeor|stadd|stset|stclr|steor)(?:a|al|l)?(?:b|h)?\t')


def run(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def check(path):
    syms = run(READELF, '-W', '--dyn-syms', path)
    defined = set()
    for line in syms.splitlines():
        f = line.split()
        if len(f) >= 8 and f[0].rstrip(':').isdigit() and f[6] != 'UND':
            defined.add(f[7].split('@')[0])
    relocs = run(READELF, '-W', '-r', path)
    slots = [line.split()[4].split('@')[0] for line in relocs.splitlines()
             if 'R_AARCH64_JUMP_SLOT' in line and len(line.split()) >= 5]
    phdrs = run(READELF, '-W', '-l', path)
    allsyms = run(READELF, '-W', '-s', path)
    emutls_vars = sum(1 for l in allsyms.splitlines() if '__emutls_v.' in l)
    outline_defs = len(set(m.group(0) for m in re.finditer(
        r'__aarch64_(?:cas|swp|ldadd|ldset|ldclr|ldeor)\w+', allsyms)))

    emutls_calls = outline_calls = lse = 0
    outline_by = {}
    proc = subprocess.Popen([OBJDUMP, '-d', '--no-show-raw-insn', path],
                            stdout=subprocess.PIPE, text=True)
    for line in proc.stdout:
        if EMUTLS.search(line):
            emutls_calls += 1
        m = OUTLINE.search(line)
        if m:
            outline_calls += 1
            outline_by[m.group(1)] = outline_by.get(m.group(1), 0) + 1
        if LSE.search(line):
            lse += 1
    proc.wait()

    return {
        'emutls_calls': emutls_calls,
        'emutls_vars': emutls_vars,
        'tls_segment': ' TLS ' in phdrs,
        'outline_calls': outline_calls,
        'outline_defs': outline_defs,
        'lse_insns': lse,
        'plt_total': len(slots),
        'plt_internal': sum(1 for s in slots if s in defined),
        'plt_internal_examples': sorted(s for s in slots if s in defined)[:8],
        'outline_top': sorted(outline_by.items(), key=lambda kv: -kv[1])[:5],
    }


def main():
    for arg in sys.argv[1:]:
        if arg.endswith('.apk'):
            with zipfile.ZipFile(arg) as z, tempfile.TemporaryDirectory() as t:
                p = os.path.join(t, 'libxemu.so')
                with open(p, 'wb') as f:
                    f.write(z.read('lib/arm64-v8a/libxemu.so'))
                r = check(p)
        else:
            r = check(arg)
        print(arg)
        for k, v in r.items():
            print(f'  {k:22s} {v}')


if __name__ == '__main__':
    main()
