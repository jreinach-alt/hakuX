#!/usr/bin/env python3
"""Desktop build setup for lane.bootstatic1017 (bindpose1017's recipe, bp/setup_desk.py).

Copies the meson subproject sources bp1017desk already fetched into this worktree, and
writes build-linux/cfg.py (the x1port1012 configure/build wrapper, nxdk-tools prefix).
Run `python3 build-linux/cfg.py` to configure, `python3 build-linux/cfg.py build` to build.
"""
import os
import shutil

SRC = "/home/justin/hakux-work/wt/bp1017desk"
DST = "/home/justin/hakux-work/wt/bootstatic1017"

sp_src, sp_dst = os.path.join(SRC, "subprojects"), os.path.join(DST, "subprojects")
for name in sorted(os.listdir(sp_src)):
    s, d = os.path.join(sp_src, name), os.path.join(sp_dst, name)
    if os.path.isdir(s) and not os.path.exists(d):
        shutil.copytree(s, d, symlinks=True)
        print("copied", name)
    elif os.path.isdir(s):
        for sub in os.listdir(s):
            ss, dd = os.path.join(s, sub), os.path.join(d, sub)
            if not os.path.exists(dd):
                if os.path.isdir(ss):
                    shutil.copytree(ss, dd, symlinks=True)
                else:
                    shutil.copy2(ss, dd)
                print("copied", name + "/" + sub)
os.makedirs(os.path.join(DST, "build-linux"), exist_ok=True)
shutil.copy2(os.path.join(SRC, "build-linux", "cfg.py"), os.path.join(DST, "build-linux", "cfg.py"))
print("cfg.py in place")
