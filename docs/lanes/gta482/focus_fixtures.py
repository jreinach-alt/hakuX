#!/usr/bin/env python3
"""Writes focus.py's fixtures: `dumpsys input` of the dual-screen Thor, shaped
on hostops's 12:43 PDT launch-only read (FocusedDisplayId 0; FocusedWindows
display 0 = hakuX GameLibraryActivity, display 4 = SecondaryDisplayLauncher).
Display 4 is listed FIRST in every block, so a first-match read fails."""
import os

HEAD = """INPUT MANAGER (dumpsys input)

Input Manager Service (Java) State:
  Pointer Capture: false
Input Dispatcher State:
  DispatchEnabled: true
  DispatchFrozen: false
  InputFilterEnabled: false
  FocusedDisplayId: {fd}
  FocusedApplications:
    displayId=4, name='ActivityRecord{{5b2c1e u0 com.android.launcher3/.secondarydisplay.SecondaryDisplayLauncher t2}}', dispatchingTimeout=5000ms
    displayId=0, name='ActivityRecord{{8c1f2a u0 {app0} t41}}', dispatchingTimeout=5000ms
  FocusedWindows:
    displayId=4, name='3e1a2b0 com.android.launcher3/com.android.launcher3.secondarydisplay.SecondaryDisplayLauncher'
    displayId=0, name='9c1d0f7 {app0}'
  FocusRequests:
    displayId=4, name='3e1a2b0 com.android.launcher3/com.android.launcher3.secondarydisplay.SecondaryDisplayLauncher' result='OK'
    displayId=0, name='9c1d0f7 {app0}' result='OK'
  Pointer Capture Requested: false
"""
HX = 'com.jreinach.hakux.debug/com.rfandango.haku_x.GameLibraryActivity'
DJ = 'com.magneticchen.daijishou/com.magneticchen.daijishou.app.HomeActivity'
here = os.path.dirname(os.path.abspath(__file__))
for name, fd, app in [('hakux', 0, HX), ('launcher', 0, DJ), ('display4', 4, HX)]:
    with open(os.path.join(here, f'focus-fixture-thor-{name}.txt'), 'w', newline='') as f:
        f.write(HEAD.format(fd=fd, app0=app).replace('\n', '\r\n'))
