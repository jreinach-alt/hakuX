#version 450
layout(triangles) in;
layout(points, max_vertices = 3) out;
void main() {
  for (int i = 0; i < 3; i++) {
    gl_Position = gl_in[i].gl_Position;
    gl_PointSize = gl_in[i].gl_PointSize;
    EmitVertex(); EndPrimitive();
  }
}
