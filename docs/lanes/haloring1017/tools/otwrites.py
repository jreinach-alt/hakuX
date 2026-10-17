"""Which output registers each draw's vertex shader writes, in draw order (#939, R6).

usage: otwrites.py DUMP F

On hardware an output component a program does not write keeps what the
previous program left in it (#42 measured this for oFog; vsh.c:583). hakuX
starts every output at (0,0,0,1). For the ring draws this matters where
an unwritten component is read: PROJECT2D divides by oTn.w. This prints,
per draw of frame F, the shader, whether its vertex stage is a program or
fixed function, and the components of oD0/oD1/oFog/oT0..oT3 it writes.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "x1port1012", "tools"))
import gdread as g  # noqa: E402

OUTS = ("oD0", "oD1", "oB0", "oB1", "oFog", "oT0", "oT1", "oT2", "oT3")


def writes(vsh):
    """{out: set of components} from the generated GLSL's MOV/MUL/... (out,mask, ...) calls
    and plain `oX.y = ` / `oX = ` assignments after the initialisers."""
    w = {o: set() for o in OUTS}
    for m in re.finditer(r"\b[A-Z]{2,4}\((o[A-Za-z0-9]+),([xyzw]+),", vsh):
        if m.group(1) in w:
            w[m.group(1)] |= set(m.group(2))
    body = vsh.split("vec4 oT3 = vec4(0.0,0.0,0.0,1.0);", 1)[-1]
    for m in re.finditer(r"^\s*(o[A-Za-z0-9]+)(?:\.([xyzw]+))?\s*=[^=]", body, re.M):
        if m.group(1) in w:
            w[m.group(1)] |= set(m.group(2) or "xyzw")
    return w


session, draws, frames, skips, shaders = g.load(sys.argv[1])
F = int(sys.argv[2])
for d in draws:
    if int(d["f"]) != F:
        continue
    sh = shaders.get(d["shader"], {})
    vsh = sh.get("vsh", "")
    prog = "prog" if "MOV(" in vsh or "DP4(" in vsh or "DPH(" in vsh else "ff  "
    w = writes(vsh) if vsh else {}
    desc = " ".join(f"{o}.{''.join(c for c in 'xyzw' if c in w[o]) or '-'}" for o in OUTS) if w else "(no vsh)"
    print(f"n{int(d['n']):3d} {d['kind'][:13]:13s} {int(d['count']):5d} {d['shader'][:8]} {prog} "
          f"shaderprog {sh.get('shaderprog', '?')}  {desc}")
