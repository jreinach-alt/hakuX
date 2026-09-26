"""Print the shaderTessellationAndGeometryPointSize line from recent dispatch logcats."""
import glob
import os
import sys

d = os.environ.get("DISPATCH_DIR") or os.path.expanduser("~/hakux-work/dispatch")
print(d, os.path.isdir(d))
n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
res = sorted(glob.glob(os.path.join(d, "results", "*")), key=os.path.getmtime)[-n:]
for r in res:
    hit = None
    for f in glob.glob(os.path.join(r, "**", "*logcat*"), recursive=True):
        try:
            t = open(f, errors="replace").read()
        except OSError:
            continue
        for line in t.splitlines():
            if "shaderTessellationAndGeometryPointSize" in line:
                hit = line[-100:]
                break
        if hit:
            break
    drv = ""
    for f in glob.glob(os.path.join(r, "**", "*logcat*"), recursive=True):
        try:
            t = open(f, errors="replace").read()
        except OSError:
            continue
        for key in ("purple", "custom driver", "system driver", "adrenotools"):
            if key in t:
                drv += key + ";"
        break
    if hit:
        print(os.path.basename(r), "|", drv, "|", hit)
