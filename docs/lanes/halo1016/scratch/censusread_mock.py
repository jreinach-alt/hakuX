#!/usr/bin/env python3
"""Exercise censusread.py on an older perflog result (the 10-03 Halo soak,
1-1791064684-lanelocal-4097992, mark gameplay; its slow pre-gameplay
stretch is mark-82..mark-31).

usage: censusread_mock.py <mock A dir> [<mock B dir> --legs]

With one dir it runs as is, and the verdict voids on [s2tcvt] and
[ovl1018], which that build did not have. With --legs, to reach the leg
code, the B dir is taken as the S2T_CVT arm, [evict372]'s ticks stand in for
[ovl1018]'s, and V's ms/f floor is 0 (a temporary expect file).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import cineread  # noqa: E402
import censusread  # noqa: E402

cineread.MARK[0] = 'gameplay'
censusread.SPAN = (-82.0, -31.0)
censusread.VIEW = (-120.0, 20.0)
a = sys.argv[1]
b = sys.argv[2] if len(sys.argv) > 2 else a
argv = ['censusread.py', a, b]
if '--legs' in sys.argv:
    orig = censusread.Census.read_log

    def read_log(self, path):
        orig(self, path)
        self.ovl = self.ev
        self.s2tcvt = os.path.normpath(self.d) == os.path.normpath(b)
    censusread.Census.read_log = read_log
    ex = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False,
                                     dir='/tmp/claude-1000')
    json.dump({'expect': {'V_a_span_msf_min': 0}}, ex)
    ex.close()
    argv += ['--expect', ex.name]
sys.argv = argv
sys.exit(censusread.main())
