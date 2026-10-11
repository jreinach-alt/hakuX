import os, json, collections, sys
R = '/home/justin/hakux-work/dispatch/results/'
keys = {('Stencil', 'Stencil_REPLACE'),
        ('Vertex_shader_rounding_tests', 'GeometrySuperscreen_0.5624'),
        ('Vertex_shader_rounding_tests', 'GeometrySuperscreen_0.9990'),
        ('Vertex_shader_rounding_tests', 'GeometrySuperscreen_0.5000'),
        ('Antialiasing_tests', 'FramebufferNotModifiedBySurfaceState'),
        ('ZPass_pixel_count', 'ZPassLineWidth-0x0000'),
        ('ZPass_pixel_count', 'ZPass')}
rows = collections.defaultdict(list)
for r in sorted(os.listdir(R)):
    p = R + r
    if not os.path.isfile(p + '/scores1.tsv') or not os.path.isfile(p + '/result.json'):
        continue
    try:
        j = json.load(open(p + '/result.json'))
    except Exception:
        continue
    dev = j.get('device_label')
    vals = {}
    for l in open(p + '/scores1.tsv'):
        f = l.rstrip('\n').split('\t')
        if len(f) > 4 and (f[0], f[1]) in keys:
            vals[f[1]] = f[4]
    if vals:
        rows[dev].append((r, j.get('ref'), vals))
verbose = len(sys.argv) > 1
for dev, lst in rows.items():
    print('##', dev, len(lst))
    c = collections.defaultdict(collections.Counter)
    for r, ref, v in lst:
        for k, x in v.items():
            c[k][x] += 1
    for k in sorted(c):
        print('  ', k, c[k].most_common(10))
    if verbose and dev == 'nova':
        for r, ref, v in lst[-40:]:
            print('   ', r, ref, v.get('Stencil_REPLACE'), v.get('ZPass'), v.get('GeometrySuperscreen_0.5000'), v.get('GeometrySuperscreen_0.5624'))
