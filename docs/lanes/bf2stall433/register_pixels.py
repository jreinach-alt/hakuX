#!/usr/bin/env python3
"""Register bf2stall433's two pixel predictions with ab_compare.py (#433).

    register_pixels.py [--force]

The full golden sweep less the two suites that flip between runs of one
binary (lane.ibcache, docs/lanes/ibcache/NOTES.md "Do not repeat"), at one
run per arm; and those two as a band at three runs per arm. Suites are every
suite with goldens.
"""
import json, os, subprocess, sys

A_REF = 'b71f92a12a'
B_REF = '57fe561924'
GOLDENS = '/home/justin/goldens/results'
BAND = ['Stencil', 'Vertex_shader_rounding_tests']
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
PRED = os.path.join(ROOT, 'docs', 'testing', 'predictions')

COMMON = (
    "lane.bf2stall433 (#433), commit 57fe561924 on master b71f92a12a: draws "
    "fetch vertex RAM from a device-local mirror instead of the per-frame "
    "host copies. The mirror is filled in the aux command buffer at each "
    "finish with exactly what was written into the current host copy since "
    "the last finish (every sync_vertex_ram_buffer upload; a whole flush "
    "range when another writer did a full refresh). The draws of a command "
    "buffer therefore read the bytes the host copy held at that finish, "
    "which is what they read before: a frame's host copy is not written "
    "again until that frame is current again, after its fence. B differs "
    "from A in hw/ by vk/draw.c only. So every capture is byte-identical "
    "between arms. A moved capture means a write reached the host copy "
    "without reaching the mirror (a writer the list does not see, or a "
    "range the catch-up skip dropped), and draws read stale vertices: the "
    "change is wrong, whatever it does for frame rate. ")

suites = sorted(s for s in os.listdir(GOLDENS)
                if os.path.isdir(os.path.join(GOLDENS, s)))
full = [s for s in suites if s not in BAND]


def register(name, suite_list, text, runs):
    path = os.path.join(PRED, name)
    cmd = [sys.executable, os.path.join(ROOT, 'docs', 'testing', 'ab_compare.py'),
           '--register', path, '--a-ref', A_REF, '--b-ref', B_REF,
           '--who', 'lane.bf2stall433', '--issue', '433', '--prediction', text,
           '--disc-suites', ','.join(suite_list),
           '--expect-count', 'better=0', '--expect-count', 'worse=0']
    for s in suite_list:
        cmd += ['--must-not-move', s + '/*']
    if '--force' in sys.argv:
        cmd.append('--force')
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    sys.stdout.write(r.stdout[-600:])
    sys.stderr.write(r.stderr)
    if r.returncode:
        sys.exit(r.returncode)
    if runs > 1:
        with open(path) as f:
            exp = json.load(f)
        exp['runs_per_arm'] = runs
        with open(path, 'w') as f:
            json.dump(exp, f, indent=2)
            f.write('\n')


register('bf2stall433-pixels.json', full,
         COMMON + "THIS FILE: the full golden sweep (%d suites) less %s, one "
         "run per arm; those two flip between runs of one binary and are "
         "bf2stall433-band.json." % (len(full), ' and '.join(BAND)), 1)
register('bf2stall433-band.json', BAND,
         COMMON + "THIS FILE: the flip band, %s, at three runs per arm. A "
         "capture self-identical within each arm and different between them "
         "kills the change; a capture that flips inside an arm is band "
         "(docs/lanes/ibcache/bandread.py reads it)." % ' and '.join(BAND), 3)
print('registered: %d suites full, %d band' % (len(full), len(BAND)))
