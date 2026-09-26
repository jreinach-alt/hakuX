"""#315: replicate texture_brdf_tests.cpp's fixed-function transform on the CPU.

The PerspectiveVertexShader has no program code, so the draw runs in FIXED mode
(TestSuite::SetupTest set SetVertexShaderProgram(nullptr)); position =
v * MV * P with MV = LookAtLH(eye) * model (row vectors, so the model
rotate/translate is applied AFTER the view), P = PerspectiveFOVLH * D3D
viewport (24-bit zeta), and the XDK default viewport offset 0.53125.
"""
import numpy as np

W, H = 640.0, 480.0
OFF = 0.53125


def ident():
    return np.eye(4, dtype=np.float64)


def lookat_lh(eye, at, up):
    z = at - eye
    z /= np.linalg.norm(z)
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    y /= np.linalg.norm(y)
    m = np.zeros((4, 4))
    m[:3, 0], m[:3, 1], m[:3, 2] = x, y, z
    m[3, :3] = [-x @ eye, -y @ eye, -z @ eye]
    m[3, 3] = 1
    return m


def rotate(mat, r):
    rx, ry, rz = r
    t = ident()
    t[0, 0], t[0, 1], t[1, 0], t[1, 1] = np.cos(rz), np.sin(rz), -np.sin(rz), np.cos(rz)
    ret = mat @ t
    t = ident()
    t[0, 0], t[0, 2], t[2, 0], t[2, 2] = np.cos(ry), -np.sin(ry), np.sin(ry), np.cos(ry)
    ret = ret @ t
    t = ident()
    t[1, 1], t[1, 2], t[2, 1], t[2, 2] = np.cos(rx), np.sin(rx), -np.sin(rx), np.cos(rx)
    return ret @ t


def translate(mat, tr):
    t = ident()
    t[3, :3] = tr
    return mat @ t


def projection_viewport(zmax=float(0xFFFFFF)):
    ys = 1 / np.tan(np.pi * 0.25 / 2)
    xs = ys / (W / H)
    zf, zn = 200.0, 1.0
    za = zf / (zf - zn)
    p = ident()
    p[0, 0], p[1, 1], p[2, 2], p[2, 3], p[3, 2], p[3, 3] = xs, ys, za, 1, -zn * za, 0
    v = ident()
    v[0, 0], v[3, 0], v[3, 1], v[1, 1], v[2, 2], v[3, 2] = W / 2, W / 2, H / 2, -H / 2, zmax, 0
    return p @ v


K = 1.0
PTS = np.array([[-K, -K, -K], [-K, -K, K], [K, -K, K], [K, -K, -K],
                [-K, K, -K], [-K, K, K], [K, K, K], [K, K, -K]])
FACES = [("right", [3, 7, 6, 2]), ("left", [1, 5, 4, 0]), ("top", [4, 5, 6, 7]),
         ("bottom", [1, 0, 3, 2]), ("back", [2, 6, 5, 1]), ("front", [0, 4, 7, 3])]
FRONT = {0, 4, 7, 3}
DRAWS = [(-1.5, 0.0, 2.0, np.pi * 0.25, np.pi * 0.25, 0.0),
         (1.5, 0.0, 2.0, np.pi * 1.25, np.pi * 0.25, 0.0)]


def mv_for(d):
    x, y, z, rx, ry, rz = d
    view = lookat_lh(np.array([0, 0, -7.0]), np.array([0, 0, 0.0]), np.array([0, 1.0, 0]))
    model = translate(rotate(ident(), (rx, ry, rz)), (x, y, z))
    return view @ model


def clip_positions(d):
    comp = mv_for(d) @ projection_viewport()
    return np.c_[PTS, np.ones(8)] @ comp


if __name__ == "__main__":
    for di, d in enumerate(DRAWS):
        c = clip_positions(d)
        print(f"draw {di} {d[:3]}")
        for i, v in enumerate(c):
            w = v[3]
            print(f"  v{i} w={w:9.4f} screen=({v[0] / w + OFF:10.2f},{v[1] / w + OFF:10.2f})")
