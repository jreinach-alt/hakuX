"""C3: no per-invocation copy of the 192-entry constant file (vsh-prog.c:866-875).
Constant writes land in a scratch vec4 and reads use the UBO. Cost probe only."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-prog.c", [
    ("            c_file = VSH_CONST_FILE_RW;\n", "            /* C3: no copy */\n"),
    ('                "  vec4 " VSH_CONST_FILE_RW "[" stringify(\n'
     '                    NV2A_VERTEXSHADER_CONSTANTS) "] = " VSH_CONST_FILE ";\\n"\n', ""),
    ('mstring_append_fmt(ret, VSH_CONST_FILE_RW "[%d]", c_reg);',
     'mstring_append(ret, VSH_CONST_FILE_RW_OOB);'),
    ('"  " VSH_CONST_FILE_RW "[%d].%s = "',
     '"  /* %d */ " VSH_CONST_FILE_RW_OOB ".%s = "'),
])
