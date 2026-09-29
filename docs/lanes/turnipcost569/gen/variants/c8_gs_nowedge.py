"""C8: the filled-triangle geometry stage without #223's negative-w wedge
(geom.c:436-449): three emits, max_vertices 3. Cost probe only."""
import sys
from _edit import edit

edit(sys.argv[1], "geom.c", [
    ("            need_wedge = true;\n"
     '            layout_out = "layout(triangle_strip, max_vertices = 8) out;\\n";\n',
     "            need_wedge = false;\n"
     '            layout_out = "layout(triangle_strip, max_vertices = 3) out;\\n";\n'),
    ('                   "  if (emit_wedge(pz)) { return; }\\n"\n', ""),
])
