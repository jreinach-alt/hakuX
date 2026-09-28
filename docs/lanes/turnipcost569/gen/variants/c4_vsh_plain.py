"""C4: vsh-prog's NaN and zero-exact helpers become plain arithmetic
(vsh-prog.c:639-711: _PosNaN, _MUL's zero forcing, _DotZeroForced). Cost probe only."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-prog.c", [
    ('    "  return mix(v, vec4(uintBitsToFloat(0x7FC00000u)), isnan(v));\\n"\n',
     '    "  return v;\\n"\n'),
    ('    "  vec4 zero_components = sign(NaNToOne(src0)) * sign(NaNToOne(src1));\\n"\n',
     '    "  return src0 * src1;\\n"\n'),
    ('    "  if (!isnan(d)) { return d; }\\n"\n', '    "  return d;\\n"\n'),
])
