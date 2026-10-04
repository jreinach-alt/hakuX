"""Per-title frame-time bands from decompose.py row TSVs (lane.vcpu60, #507).

Usage: python3 docs/lanes/vcpu60/bands.py TITLE=ROWS.tsv:RUN [...] > decompose4.tsv

ROWS.tsv is the `--tsv` output of docs/lanes/fps20786/decompose.py on one
run; RUN is a label. Prints medians of the 2-s rows per frame-time band,
in ms per guest frame.
"""
import csv
import statistics
import sys

COLS = ('fps F v_run v_blk v_rq gidle Ri rcpu rblk lockw '
        'ph_GPU ph_Draw ph_Fin ph_Idle ph_Tot BE').split()
BANDS = [(0, 999, 'all'), (0, 22.2, '<22.2'), (22.2, 26, '22.2-26'),
         (26, 31, '26-31'), (31, 36, '31-36'), (36, 999, '>=36')]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main(args):
    print('# medians of 2-s rows after the gameplay mark, ms per guest frame;'
          ' rows from docs/lanes/fps20786/decompose.py --tsv')
    print('\t'.join(['title', 'run', 'band_F_ms', 'n'] + COLS))
    for a in args:
        title, rest = a.split('=', 1)
        path, run = rest.split(':', 1)
        rows = list(csv.DictReader(open(path), delimiter='\t'))
        for lo, hi, name in BANDS:
            rs = [r for r in rows if lo <= num(r['F']) < hi]
            if not rs:
                continue
            vals = []
            for k in COLS:
                v = [num(r.get(k)) for r in rs if num(r.get(k)) is not None]
                vals.append('%.2f' % statistics.median(v) if v else '')
            print('\t'.join([title, run, name, str(len(rs))] + vals))


if __name__ == '__main__':
    main(sys.argv[1:])
