import json, os, datetime

D = '/home/justin/hakux-work/dispatch/fleet'
now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

rows = {
    'blitsafe': (['88', '91', '92', '89'],
        '#92 instrumented run FIRST (framebuffer_dirty across TestSwap SET_CONTEXT_DMA_COLOR), '
        'then #89 narrow the clear format to surface_shape not drawn_format, then #88 before #91. '
        'Register the prediction, do not queue the arm.'),
    'swizzle87': (['85', '87'],
        '#87 NOW IMPLEMENT on both backends (vk/texture.c + gl/surface.c, granted); falsify the '
        'layout model offline against the 16/32/64/80 px run lengths before building. #85 second, '
        'separate commit.'),
    'tier81fix': (['81', '90'],
        '#81 = audit M2, dedup on (pc, cs_base, flags) plus reset-or-latch exec_count; NOT '
        'unmasking CF_INVALID. #90 separately, and agree the #ifndef __ANDROID__ intent in writing '
        'first. Diff the per-pc request multiset, not the total.'),
    'toolsmith': (['94', '95'],
        '#94 request.sh repeated --only-tests silently clobbers -- urgent, it produced a confident '
        'pre-registered wrong answer on disc89-H-pre8. #95 add composition to the prediction '
        'schema, grandfathering 106 of 107.'),
    'blit83': (['83'],
        'ANALYSIS ONLY, files=[]. Name the one-low SRCCOPY mechanism and its line; FIRST settle '
        'whether the eight are still a sound must-not-move control for #84 arm, which is in fold now.'),
    'stencil99': (['99'],
        'ANALYSIS ONLY, files=[]. #99 is a title with an empty body: separate the three captures '
        'from #79 nondeterministic nine, date the goldens and the captures, only then read the sha '
        'range. Write the tracker entry the issue never got.'),
}

for lane, pair in rows.items():
    issues, asked = pair
    rec = {
        'lane': lane,
        'agent': 'hakux-lane-' + lane + '.service',
        'issues': issues,
        'asked': asked,
        'dispatched_utc': now,
        'state': 'running',
        'waiting_on': '',
        'worktree': '/home/justin/hakux-work/wt/' + lane,
        'brief': 'briefs/' + lane + '.md on the board branch (a8fde2ee51)',
    }
    p = os.path.join(D, lane + '.json')
    with open(p, 'w') as fh:
        json.dump(rec, fh, indent=2)
    json.load(open(p))
    print('wrote ' + p)
