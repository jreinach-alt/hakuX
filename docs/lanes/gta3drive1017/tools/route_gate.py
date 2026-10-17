#!/usr/bin/env python3
"""Calibrate the driving route's gate crop against every frame on hand (#433).

The first draft gated the car entry on gta-3.route's `fist-hud` crop. Both
pilots matched it at once on a screen that was not the mission start (a
damaged Kuruma already in Chinatown at a 05:xx clock, then a restart into
the "Give Me Liberty" cutscene), so the single Y press landed on the wrong
screen. The fist icon is up on every in-game screen; it cannot say "Claude
is on foot next to the car".

The tutorial box "Enter or exit a vehicle: Y" can: GTA III shows it only
while Claude is on foot at the start of the first mission, with the Kuruma
marked. This scores that region of every frame in the given result dirs
against a reference cut from one of them, so the threshold sits between the
frames that show the box and those that do not (including the same box
with other text, "Brake or reverse ...: Left Trigger").

Usage: route_gate.py <ref out.png> <source frame> <x,y,w,h> <result dir>...
"""
import glob
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', 'testing', 'titles'))
from waitfor_match import region_score  # noqa: E402


def main():
    ref, src, region = sys.argv[1], sys.argv[2], sys.argv[3]
    x, y, w, h = (int(v) for v in region.split(','))
    Image.open(src).convert('RGB').crop((x, y, x + w, y + h)).save(ref)
    print('# ref %s <- %s %s' % (ref, src, region))
    for rdir in sys.argv[4:]:
        for f in sorted(glob.glob(os.path.join(rdir, 'route-frames', '*.png'))):
            print('%7.2f\t%s/%s' % (region_score(f, ref, (x, y, w, h)),
                                    os.path.basename(rdir.rstrip('/')),
                                    os.path.basename(f)))


if __name__ == '__main__':
    main()
