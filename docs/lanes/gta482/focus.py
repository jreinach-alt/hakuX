#!/usr/bin/env python3
"""Does hakuX hold the input focus?  Reads `dumpsys input` on stdin.

    adb shell dumpsys input | focus.py      -> "in-front: <window>"  exit 0
                                               "miss: <why>"         exit 1

Key and gamepad events go to the focused window of FocusedDisplayId.  So:
read `FocusedDisplayId: N`, then the `FocusedWindows:` entry `displayId=N`,
and require N = 0 and that window to be com.jreinach.hakux*.  On the Thor the
bottom screen (display 4, SecondaryDisplayLauncher) always has a focused
window and is listed before display 0; a first-match read (the old
`dumpsys window | grep -m1 mCurrentFocus=`) sees the launcher every time,
which is what stopped sessions 2 and 3 (hostops, 09-27 12:45 PDT).

    focus.py --selftest   runs the fixtures next to this file
"""
import os
import re
import sys


def read_focus(text):
    disp = None
    wins = {}
    in_block = None
    for raw in text.replace('\r', '').split('\n'):
        m = re.match(r'^(\s*)FocusedDisplayId:\s*(-?\d+)', raw)
        if m and disp is None:
            disp = int(m.group(2))
            continue
        m = re.match(r'^(\s*)FocusedWindows:\s*(.*)$', raw)
        if m:
            in_block = len(m.group(1))
            if m.group(2).strip() == '<none>':
                in_block = None
            continue
        if in_block is not None:
            ind = len(raw) - len(raw.lstrip())
            if not raw.strip() or ind <= in_block:
                in_block = None
                continue
            m = re.match(r'^\s*displayId=(-?\d+),\s*name=\'(.*)\'', raw)
            if m:
                wins.setdefault(int(m.group(1)), m.group(2))
    return disp, wins


def verdict(text):
    disp, wins = read_focus(text)
    if disp is None:
        return 1, 'miss: no FocusedDisplayId line'
    if disp != 0:
        return 1, f'miss: FocusedDisplayId {disp} ({wins.get(disp, "no window")})'
    w = wins.get(0)
    if w is None:
        return 1, 'miss: display 0 has no focused window'
    if not re.search(r'\bcom\.jreinach\.hakux[\w.]*/', w):
        return 1, f'miss: display 0 focus is {w}'
    return 0, f'in-front: {w}'


def selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    cases = [('focus-fixture-thor-hakux.txt', 0),
             ('focus-fixture-thor-launcher.txt', 1),
             ('focus-fixture-thor-display4.txt', 1)]
    bad = 0
    for name, want in cases:
        rc, msg = verdict(open(os.path.join(here, name)).read())
        ok = rc == want
        bad += not ok
        print(f'{"ok  " if ok else "FAIL"} {name}: rc={rc} want={want} {msg}')
    # the empty read (adb failed) must be a miss, not in-front
    rc, msg = verdict('')
    bad += rc != 1
    print(f'{"ok  " if rc == 1 else "FAIL"} empty: rc={rc} {msg}')
    return 1 if bad else 0


if __name__ == '__main__':
    if sys.argv[1:] == ['--selftest']:
        sys.exit(selftest())
    rc, msg = verdict(sys.stdin.read())
    print(msg)
    sys.exit(rc)
