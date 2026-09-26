#!/usr/bin/env python3
"""How much of each thread's CPU time is inside the Vulkan driver.

    driver_share.py <perf.data> <driver.so> [--ndk DIR]

Reads a simpleperf `record --call-graph dwarf` capture taken with an
adrenotools driver installed, and prints, per thread, the samples whose leaf
frame is in the driver (self), the samples with the driver anywhere on the
stack (inclusive), how many of those inclusive samples are kernel time under a
driver frame (KGSL ioctls), and how many run through the shader compiler.

The driver must be the same binary that was recorded: its GNU build-id is
checked against the capture's build_id feature, and a mismatch is refused,
because symbols from another build would attribute samples to the wrong
functions without any error. T30 ships unstripped, so its symbols resolve
directly.

Why this exists: the 09-11 Crimson Skies profile was reported as unable to
attribute driver time. It could, and nobody had symbolized it
(docs/investigations/adreno-driver-feasibility.md, section (e)).
"""
import argparse
import collections
import os
import re
import subprocess
import sys
import tempfile

COMPILE = re.compile(r'^(ir3_|nir_|tu_shader|tu_compile|tu_pipeline_builder|'
                     r'tu_CreateGraphicsPipelines|vk_pipeline|ra_|isa_|'
                     r'spirv_to_nir|vtn_)')


def elf_build_id(path):
    data = open(path, 'rb').read(1 << 16)
    i = data.find(b'GNU\x00')
    if i < 0:
        sys.exit('%s: no GNU build-id note in the first 64 KiB' % path)
    return data[i + 4:i + 24].hex()


def recorded_driver(sp, perf):
    """(device path, build-id) of the adrenotools driver in the capture."""
    out = subprocess.run([sp, 'dump', '-i', perf, '--dump-feature', 'build_id'],
                         capture_output=True, text=True).stdout.splitlines()
    for i, line in enumerate(out):
        if 'gpu_driver/' in line and 'filename' in line:
            path = line.split('filename', 1)[1].strip()
            for back in out[max(0, i - 3):i][::-1]:
                if 'build_id' in back and '0x' in back:
                    return path, back.split('0x', 1)[1].strip()[:40]
    sys.exit('no gpu_driver/ mapping in %s: was a custom driver loaded?' % perf)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('perf_data')
    ap.add_argument('driver_so')
    ap.add_argument('--ndk', default='/home/justin/Android/Sdk/ndk/29.0.14206865')
    ap.add_argument('--top', type=int, default=8)
    a = ap.parse_args()

    spdir = os.path.join(a.ndk, 'simpleperf')
    sp = os.path.join(spdir, 'bin/linux/x86_64/simpleperf')
    dev_path, rec_id = recorded_driver(sp, a.perf_data)
    have = elf_build_id(a.driver_so)
    if not rec_id.startswith(have[:32]):
        sys.exit('build-id mismatch: capture has %s, %s is %s' % (rec_id, a.driver_so, have))
    print('driver %s build-id %s matches the capture' % (dev_path, have))

    symfs = tempfile.mkdtemp(prefix='driver_share_')
    dst = symfs + os.path.dirname(dev_path)
    os.makedirs(dst)
    os.symlink(os.path.abspath(a.driver_so), symfs + dev_path)

    sys.path.insert(0, spdir)
    from simpleperf_report_lib import ReportLib
    lib = ReportLib()
    lib.SetRecordFile(a.perf_data)
    lib.SetSymfs(symfs)

    drv = 'gpu_driver/'
    tot, dself, dincl, dkern, dcomp = (collections.Counter() for _ in range(5))
    ours = collections.defaultdict(collections.Counter)
    dsyms = collections.defaultdict(collections.Counter)
    while True:
        s = lib.GetNextSample()
        if s is None:
            break
        t = s.thread_comm
        tot[t] += 1
        sym = lib.GetSymbolOfCurrentSample()
        cc = lib.GetCallChainOfCurrentSample()
        frames = [(sym.dso_name, sym.symbol_name)] + [
            (cc.entries[i].symbol.dso_name, cc.entries[i].symbol.symbol_name)
            for i in range(cc.nr)]
        in_drv = [f for f in frames if drv in f[0]]
        if drv in frames[0][0]:
            dself[t] += 1
            dsyms[t][frames[0][1]] += 1
        if in_drv:
            dincl[t] += 1
            if 'kernel' in frames[0][0]:
                dkern[t] += 1
            if any(COMPILE.match(f[1]) for f in in_drv):
                dcomp[t] += 1
        elif 'libxemu' in frames[0][0]:
            ours[t][frames[0][1]] += 1

    n = sum(tot.values())
    print('samples %d' % n)
    print('%-30s %8s %8s %8s %9s %8s' % ('thread', 'total', 'drv self', 'drv incl',
                                         'kern<drv', 'compile'))
    for t, c in tot.most_common(10):
        print('%-30s %8d %8d %8d %9d %8d   incl %.1f%%' % (
            t, c, dself[t], dincl[t], dkern[t], dcomp[t], 100.0 * dincl[t] / c))
    for t, _ in tot.most_common(3):
        print('\n%s: top libxemu self' % t)
        for k, v in ours[t].most_common(a.top):
            print('  %6d %s' % (v, k[:100]))
        print('%s: top driver self' % t)
        for k, v in dsyms[t].most_common(a.top):
            print('  %6d %s' % (v, k[:100]))


if __name__ == '__main__':
    main()
