#!/usr/bin/env python3
"""Set or clear runtime_override_gpu_driver in an x1box_prefs.xml, in place.

Only that one key. The file also holds the MCPX, flash and HDD paths and the
setup_complete flag, and deleting it drops the app into its setup wizard with
no way back except re-running the wizard -- which is what happened when an
earlier version of driver_ab.sh cleared the key with rm.
"""
import re
import sys

KEY = "runtime_override_gpu_driver"
path, want = sys.argv[1], sys.argv[2]
s = open(path).read()
s = re.sub(r'\n?[ \t]*<string name="%s">[^<]*</string>' % KEY, "", s)
if want == "system":
    s = s.replace("</map>", '    <string name="%s">system</string>\n</map>' % KEY)
if "</map>" not in s:
    sys.exit("prefs file has no </map>; refusing to write")
open(path, "w").write(s)
