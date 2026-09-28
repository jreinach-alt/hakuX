"""C2: every c[A0+n] read becomes c[n] (vsh-prog.c:342-344). Cost probe only."""
import sys
from _edit import edit

edit(sys.argv[1], "vsh-prog.c", [
    ('snprintf(tmp, sizeof(tmp), "%s[A0+%d]", c_file, reg_num);',
     'snprintf(tmp, sizeof(tmp), "%s[%d]", c_file, reg_num);'),
])
