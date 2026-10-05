#!/usr/bin/env python3
"""frametrace selftest (#433).

    python3 docs/lanes/frametrace/selftest.py [--cc cc] [--keep]

Builds ft_selftest.c against hw/xbox/nv2a/pgraph/profile.h on the host and
runs it: the attribution rule on synthetic frames, the holder test on live
threads (a lock holder in a GPU fence, running, or changing state), a wait
split across flips, the hitch trigger and the off path.

Then it builds the same harness against MUTATED copies of the header, each
removing one mechanism, and requires the check named for that mechanism to
FAIL. A mutant that passes means the check cannot see the thing it is named
for, and the selftest fails.

Exit 0 only if every check passes on the real header and every mutant is
caught. Needs a C compiler with pthreads; no numpy, no device.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
HDR = 'hw/xbox/nv2a/pgraph/profile.h'

# (name, old, new, the check that must FAIL)
MUTANTS = [
    ('holder spans not read',
     '            if (e <= a) {\n                break;',
     '            if (1) {\n                break;',
     'live.fence_holder_books_gpu'),
    ('holder wait in progress not read',
     'if (wt0 && wt0 < b && wr < HAKUX_FT_NW) {',
     'if (0) {',
     'live.split_wait_keeps_holder_class'),
    ('holder time outside its waits not booked RUN',
     'part[HAKUX_FT_H_RUN] += tot - used;',
     'part[HAKUX_FT_H_GPU] += tot - used;',
     'live.changing_holder_split_by_overlap'),
    ('guest work over the deadline not tested',
     '} else if (work > D) {',
     '} else if (0) {',
     'rule.work_over_deadline_is_run'),
    ('guest idle not taken out of on-CPU time',
     'uint32_t gidle_on = hakux_ft_sub0(gidle, halt);',
     'uint32_t gidle_on = 0;',
     'rule.gidle_with_gpu_saturated_is_gpu'),
    ('in-progress waits not split at the flip',
     'if (wt0 && now > wt0 && wreason < HAKUX_FT_NW) {',
     'if (0) {',
     'live.wait_split_at_flips'),
    ('hitch floor of 50 ms removed',
     'if (thr < FT_HITCH_MIN_NS / 1000) {',
     'if (0) {',
     'hitch.45ms_in_60fps_is_not'),
    ('holder class taken from the lock wait, not the holder',
     '    charge[HAKUX_FT_C_BLK_GPU] = fr->vh[HAKUX_FT_H_GPU] +',
     '    charge[HAKUX_FT_C_BLK_GPU] = fr->vh[HAKUX_FT_H_GPU] + '
     'fr->vh[HAKUX_FT_H_RUN] +',
     'rule.running_holder_is_block'),
    ('off path records',
     '    if (hakux_ft_enabled()) {\n        hakux_ft_wait_begin_slow',
     '    if (1) {\n        hakux_ft_wait_begin_slow',
     'off.records_nothing'),
    ('duty: no baseline after an off span',
     'if (__atomic_exchange_n(&ft_resync, 0, __ATOMIC_ACQ_REL)) {',
     'if (0) {',
     'duty.first_flip_after_off_is_a_baseline'),
    ('duty: slack read across an off span',
     'if (prev && fr->t - (int64_t)fr->P * 1000 > prev->t + 1000000) {',
     'if (0) {',
     'duty.no_slack_across_off_span'),
    ('duty: switch never turns the instrument off',
     '    __atomic_store_n(&hakux_ft_on, d->on, __ATOMIC_RELEASE);',
     '',
     'duty.switches_off_then_on'),
    ('mmio: nested dispatch booked twice',
     'if (ft_self != HAKUX_FT_VCPU || ft_mmio_depth) {',
     'if (ft_self != HAKUX_FT_VCPU) {',
     'mmio.outermost_vcpu_dispatch_booked_once'),
    ('mmio: any thread booked as the vCPU',
     'if (ft_self != HAKUX_FT_VCPU || ft_mmio_depth) {',
     'if (ft_mmio_depth) {',
     'mmio.outermost_vcpu_dispatch_booked_once'),
    ('mmio: every region booked to one slot',
     '    for (i = 0; i < n && ft_mmio_key[i] != key; i++) {',
     '    for (i = 0; i < n; i++) {\n        break;',
     'mmio.slots_by_region'),
]


def build_and_run(cc, inc, out, keep):
    exe = os.path.join(out, 'ft_selftest')
    cmd = [cc, '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
           '-Wno-unused-parameter', '-pthread', '-I', inc,
           os.path.join(HERE, 'ft_selftest.c'), '-o', exe]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        return None, 'compile failed:\n' + r.stderr
    r = subprocess.run([exe], capture_output=True, text=True, timeout=120)
    res = {}
    for line in r.stdout.splitlines():
        if line.startswith('PASS '):
            res[line[5:].strip()] = True
        elif line.startswith('FAIL '):
            res[line[5:].split(':')[0].strip()] = False
    return res, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cc', default=os.environ.get('CC', 'cc'))
    ap.add_argument('--keep', action='store_true')
    ap.add_argument('-v', action='store_true')
    a = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix='ftself')
    ok = True
    try:
        res, text = build_and_run(a.cc, ROOT, tmp, a.keep)
        if res is None:
            print(text)
            return 2
        if a.v:
            print(text)
        fails = [k for k, v in res.items() if not v]
        print('real header: %d checks, %d failed' % (len(res), len(fails)))
        for k in fails:
            print('  FAIL', k)
            for line in text.splitlines():
                if line.startswith('FAIL ' + k):
                    print('   ', line)
        ok = not fails and len(res) >= 25

        src = open(os.path.join(ROOT, HDR)).read()
        for name, old, new, must_fail in MUTANTS:
            if src.count(old) != 1:
                print('MUTANT %-50s NOT APPLIED (pattern count %d)'
                      % (name, src.count(old)))
                ok = False
                continue
            mroot = os.path.join(tmp, 'm')
            shutil.rmtree(mroot, ignore_errors=True)
            os.makedirs(os.path.join(mroot, os.path.dirname(HDR)))
            open(os.path.join(mroot, HDR), 'w').write(src.replace(old, new))
            mres, mtext = build_and_run(a.cc, mroot, tmp, a.keep)
            if mres is None:
                print('MUTANT %-50s does not compile' % name)
                print(mtext)
                ok = False
                continue
            caught = mres.get(must_fail) is False
            print('MUTANT %-50s %s (%s)' % (name, 'caught' if caught
                                            else 'NOT CAUGHT', must_fail))
            ok = ok and caught
    finally:
        if not a.keep:
            shutil.rmtree(tmp, ignore_errors=True)
    print('SELFTEST', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
