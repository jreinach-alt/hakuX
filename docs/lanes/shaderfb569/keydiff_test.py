#!/usr/bin/env python3
"""Build and run keydiff_test.c with the desktop build's flags for profile.c.

    keydiff_test.py [<desktop compile_commands.json>] [<its source tree>]

The emulator symbols profile.c references stay unresolved; the test calls
only nv2a_profile_shader_keydiff().
"""
import json
import os
import shlex
import subprocess
import sys
import tempfile

HERE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def main():
    cc = sys.argv[1] if len(sys.argv) > 1 else "/home/justin/hakuX/build-desktop/compile_commands.json"
    src = sys.argv[2] if len(sys.argv) > 2 else "/home/justin/hakuX"
    e = [x for x in json.load(open(cc)) if x["file"].endswith("pgraph/profile.c")][0]
    args = e.get("arguments") or shlex.split(e["command"])
    out, skip = [], False
    for a in args:
        if skip:
            skip = False
            continue
        if a in ("-o", "-MF", "-MQ", "-MT", "-c"):
            skip = a != "-c"
            continue
        if a == "-MD" or a.endswith("profile.c"):
            continue
        pre = "-I" if a.startswith("-I") else ""
        path = a[len(pre):]
        if pre and not path.startswith("/"):
            path = os.path.normpath(os.path.join(e["directory"], path))
            a = pre + path
        if (path == src or path.startswith(src + "/")) and not any(
                path.startswith(src + x) for x in ("/subprojects", "/build")):
            a = pre + HERE + path[len(src):]
        out.append(a)
    tmp = tempfile.mkdtemp(prefix="keydiff")
    exe = os.path.join(tmp, "t")
    prof = open(os.path.join(HERE, "hw/xbox/nv2a/pgraph/profile.c")).read()
    a0 = prof.index("enum {\n    SHADER_KEYDIFF_VP")
    a1 = prof.index("\n}\n", prof.index("void nv2a_profile_shader_keydiff(const ShaderState *prev,\n                                 const ShaderState *cur)\n{")) + 3
    open(os.path.join(tmp, "keydiff_fn.inc"), "w").write(prof[a0:a1])
    out += ["-I" + tmp]
    test = os.path.join(HERE, "docs/lanes/shaderfb569/keydiff_test.c")
    glib = subprocess.run(["pkg-config", "--libs", "glib-2.0"], capture_output=True,
                          text=True).stdout.split() or ["-lglib-2.0"]
    cmd = out + ["-Wno-missing-prototypes", test, "-o", exe,
                 ] + glib
    r = subprocess.run(cmd, cwd=e["directory"], capture_output=True, text=True)
    if r.returncode:
        print(r.stderr[-4000:])
        return 1
    print("built", exe, flush=True)
    return subprocess.run([exe]).returncode


if __name__ == "__main__":
    sys.exit(main())
