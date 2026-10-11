"""Share of unique frames with the passing car's body drawn, over the pass window.
Window: first..last unique frame whose red-livery share > NEAR (the car near the camera).
Present: red share > PRESENT. Absent frames inside the window are listed."""
import sys
NEAR, PRESENT = 0.015, 0.003
for path in sys.argv[1:]:
    rows = [l.split('\t') for l in open(path).read().split('\n') if l]
    rows = [(r[0], r[1], float(r[2]), float(r[3])) for r in rows]
    near = [i for i, r in enumerate(rows) if r[3] > NEAR]
    w = rows[near[0]:near[-1] + 1]
    absent = [r for r in w if r[3] <= PRESENT]
    print('%-22s window %s..%s (video frames %s..%s) unique=%d present=%d absent=%d share=%.1f%%  absent: %s' % (
        path, w[0][0], w[-1][0], w[0][1], w[-1][1], len(w), len(w) - len(absent), len(absent),
        100.0 * (len(w) - len(absent)) / len(w), ' '.join('%s(%.4f)' % (r[0], r[3]) for r in absent)))
