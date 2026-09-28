"""j_per_frame per soak (#548): title_verdict.py on a copy of each result dir
(it may write into the dir), printing the power lines. Usage: jpf.py RDIR..."""
import os, shutil, subprocess, sys, tempfile

here = os.path.dirname(os.path.abspath(__file__))
tv = os.path.join(here, '..', '..', 'testing', 'title_verdict.py')
tmp = tempfile.mkdtemp(prefix='dirtytlb-tv-')
for r in sys.argv[1:]:
    dst = os.path.join(tmp, os.path.basename(r.rstrip('/')))
    shutil.copytree(r, dst)
    out = subprocess.run([sys.executable, tv, dst], capture_output=True, text=True)
    print('==', os.path.basename(dst))
    for line in (out.stdout + out.stderr).splitlines():
        if any(k in line.lower() for k in ('j_per_frame', 'j/frame', 'joule', 'power', 'watt')):
            print('  ', line)
