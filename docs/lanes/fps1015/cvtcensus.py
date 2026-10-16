#!/usr/bin/env python3
"""Which titles take `cvt` render-to-texture downloads, from every perflog
soak on disk.

A perflog build prints, once per stats window, `hakuX-stall` lines
`txr[... dl<n>/<K> ... s2tc<n> ...] txdl[lv dim cube pitch swz cvt<n> bpp upl oth]`
(vk/draw.c). `cvt` counts textures create_texture() downloaded because
check_surface_to_texture_compatiblity() refused a 5551/565 texture over a
16-bit surface (#59's guard), the downloads HAKUX_S2T_CVT replaces. The
window's own `fps`/frame count is not on that line, so the rate is per
window; the window length is the stats period, the same in every run.

    cvtcensus.py [RESULTS_DIR] > census.tsv

One row per result directory whose logcat has txdl[] lines: title, windows,
windows with cvt > 0, median and max cvt per window, median dl per window.
"""
import glob
import json
import os
import re
import statistics
import subprocess
import sys

RES = sys.argv[1] if len(sys.argv) > 1 else '/home/justin/hakux-work/dispatch/results'
TXDL = re.compile(r'txr\[ct\d+ bt\d+/\d+ dl(\d+)/\d+K .*?\] txdl\[lv\d+ dim\d+ cube\d+ '
                  r'pitch\d+ swz\d+ cvt(\d+) ')

print('\t'.join(['result', 'title', 'ref', 'windows', 'cvt_windows', 'cvt_med', 'cvt_max', 'dl_med']))
for d in sorted(glob.glob(os.path.join(RES, '*'))):
    logs = sorted(glob.glob(os.path.join(d, 'logcat*.txt')))
    if not logs:
        continue
    p = subprocess.run(['grep', '-h', '-o', '-E', r'txr\[ct[^]]*\] txdl\[[^]]*\]'] + logs,
                       capture_output=True, text=True)
    rows = [TXDL.search(l) for l in p.stdout.splitlines()]
    rows = [(int(m.group(1)), int(m.group(2))) for m in rows if m]
    if not rows:
        continue
    try:
        req = json.load(open(os.path.join(d, 'request.json')))
    except (OSError, ValueError):
        req = {}
    title = req.get('title') or (','.join(req.get('suites') or []) if isinstance(req.get('suites'), list)
                                 else str(req.get('suites') or '?'))
    cvt = [c for _, c in rows]
    dl = [x for x, _ in rows]
    print('\t'.join([os.path.basename(d), str(title)[:60], str(req.get('ref', '?'))[:10],
                     str(len(rows)), str(sum(1 for c in cvt if c)),
                     str(statistics.median(cvt)), str(max(cvt)), str(statistics.median(dl))]))
