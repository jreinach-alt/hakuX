"""Replicate the Viewport test's fixed-function vertex round trip.

nxdk_pgraph_tests' Viewport test builds each quad corner by unprojecting a
screen point through the inverse composite matrix (pbkitplusplus
NV2AState::UnprojectPoint -> xbox_math3d UnprojectPoint) and lets the
fixed-function pipeline project it back. This script repeats that arithmetic
in strict fp32, exactly as the C++ evaluates it one rounding per operation,
then evaluates the forward composite transform of each fixed-function quad
vertex (a) exactly in rational arithmetic and (b) under a few fp32 operation
orders, and prints where each lands relative to n + 9/16 in fp32 ULPs.

The point of the exercise is in docs/investigations/edge-defect.md: under
this model the vertices land 150-1,400 ULP off the boundary, and the signs at
x = 120 and 220 contradict both hardware and lavapipe, so the Xbox build
evaluates the chain with more precision than this and the true vertices are
within a few ULP of the boundary.

Usage: viewport_ff_roundtrip.py [TAN_ULP_SHIFT]   (0, +1 or -1: perturb tanf)
Needs numpy only.
"""
import numpy as np, math
from fractions import Fraction as Fr
f=np.float32
def F(x): return f(x)
def fadd(a,b): return f(f(a)+f(b))
def fmul(a,b): return f(f(a)*f(b))
def fdiv(a,b): return f(f(a)/f(b))
def fsub(a,b): return f(f(a)-f(b))
Z=lambda: [[F(0)]*4 for _ in range(4)]
def ident():
    m=Z()
    for i in range(4): m[i][i]=F(1)
    return m
def matmul(a,b):
    r=Z()
    for i in range(4):
        for j in range(4):
            s=fmul(a[i][0],b[0][j])
            for k in (1,2,3): s=fadd(s,fmul(a[i][k],b[k][j]))
            r[i][j]=s
    return r
def vecmul(v,a):  # VectorMultMatrix(b=v, a=matrix): ret[j]=a[0][j]*b0 + a[1][j]*b1 + a[2][j]*b2 + a[3][j]*b3
    r=[None]*4
    for j in range(4):
        s=fmul(a[0][j],v[0])
        for i in (1,2,3): s=fadd(s,fmul(a[i][j],v[i]))
        r[j]=s
    return r
# --- model view: LookAtLH eye(0,0,-7) at(0,0,0) up(0,1,0)
def normalize(v):
    l=f(np.sqrt(f(fadd(fadd(fmul(v[0],v[0]),fmul(v[1],v[1])),fmul(v[2],v[2])))))
    inv=fdiv(1,l)
    return [fmul(v[0],inv),fmul(v[1],inv),fmul(v[2],inv),F(1)]
def cross(a,b): return [fsub(fmul(a[1],b[2]),fmul(a[2],b[1])), fsub(fmul(a[2],b[0]),fmul(a[0],b[2])), fsub(fmul(a[0],b[1]),fmul(a[1],b[0])), F(1)]
def dot3(a,b): return fadd(fadd(fmul(a[0],b[0]),fmul(a[1],b[1])),fmul(a[2],b[2]))
eye=[F(0),F(0),F(-7),F(1)]; at=[F(0),F(0),F(0),F(1)]; up=[F(0),F(1),F(0),F(1)]
z_axis=normalize([fsub(at[0],eye[0]),fsub(at[1],eye[1]),fsub(at[2],eye[2]),F(1)])
x_axis=normalize(cross(up,z_axis)); y_axis=normalize(cross(z_axis,x_axis))
mv=Z()
for r,ax in enumerate((x_axis,y_axis,z_axis)):
    pass
mv=[[x_axis[0],y_axis[0],z_axis[0],F(0)],[x_axis[1],y_axis[1],z_axis[1],F(0)],[x_axis[2],y_axis[2],z_axis[2],F(0)],
    [fmul(-1,dot3(x_axis,eye)),fmul(-1,dot3(y_axis,eye)),fmul(-1,dot3(z_axis,eye)),F(1)]]
# --- projection FOV LH: fov=(float)(M_PI*0.25), aspect=640/480, near=1, far=200
def build(tan_ulp_shift=0):
    fov=F(math.pi*0.25)
    half=fmul(fov,F(0.5))
    t=F(math.tan(float(half)))
    if tan_ulp_shift: t=np.nextafter(t,f(np.inf) if tan_ulp_shift>0 else f(-np.inf))
    y_scale=fdiv(1,t); aspect=fdiv(640,480); x_scale=fdiv(y_scale,aspect)
    zn,zf=F(1),F(200); z_adj=fdiv(zf,fsub(zf,zn))
    proj=ident(); proj[0][0]=x_scale; proj[1][1]=y_scale; proj[2][2]=z_adj; proj[2][3]=F(1); proj[3][2]=fmul(fmul(-1,zn),z_adj); proj[3][3]=F(0)
    vp=ident(); vp[0][0]=fmul(640,F(0.5)); vp[3][0]=vp[0][0]; vp[3][1]=fmul(480,F(0.5)); vp[1][1]=fmul(-1,vp[3][1]); vp[2][2]=fmul(F(0x00FFFFFF),fsub(1,0)); vp[3][2]=fmul(F(0x00FFFFFF),F(0))
    pv=matmul(proj,vp)
    comp=matmul(mv,pv)
    return comp
def det3(m):
    a,b,c=map(float,m[0]); d,e,g=map(float,m[1]); h,i_,j=map(float,m[2])
    return a*(e*j-g*i_)-b*(d*j-g*h)+c*(d*i_-e*h)
def det4(mat):
    a,b,c,d=map(float,mat[0]); e,f_,g,h=map(float,mat[1]); i_,j,k,l=map(float,mat[2]); m,n,o,p=map(float,mat[3])
    in_=i_*n; io=i_*o; ip=i_*p; jm=j*m; jo=j*o; jp=j*p; km=k*m; kn=k*n; kp=k*p; lm=l*m; ln=l*n; lo=l*o
    return a*(f_*(kp-lo)-g*(jp-ln)+h*(jo-kn)) - b*(e*(kp-lo)-g*(ip-lm)+h*(io-km)) + c*(e*(jp-ln)-f_*(ip-lm)+h*(in_-jm)) - d*(e*(jo-kn)-f_*(io-km)+g*(in_-jm))
def invert(a):
    det=det4(a)
    ret=Z(); sign=1.0
    for r in range(4):
        for c in range(4):
            sub=[[a[rr][cc] for cc in range(4) if cc!=c] for rr in range(4) if rr!=r]
            ret[c][r]=F(sign*det3(sub))
            sign*=-1.0
        sign*=-1.0
    scalar=F(1.0/det)  # 1.0f/double -> double -> float param
    for r in range(4):
        for c in range(4): ret[r][c]=fmul(ret[r][c],scalar)
    return ret
def euclid(v): return [fdiv(v[0],v[3]),fdiv(v[1],v[3]),fdiv(v[2],v[3]),F(1)]
def unproject(sp,inv,world_z):
    near=euclid(vecmul([sp[0],sp[1],F(0),F(1)],inv)); far=euclid(vecmul([sp[0],sp[1],F(64000),F(1)],inv))
    t=fdiv(fsub(world_z,near[2]),fsub(far[2],near[2]))
    return [fadd(near[0],fmul(fsub(far[0],near[0]),t)), fadd(near[1],fmul(fsub(far[1],near[1]),t)), F(world_z), F(1)]
def ulp(x): return 2.0**(math.floor(math.log2(abs(x)))-23)
import sys
shift=int(sys.argv[1]) if len(sys.argv)>1 else 0
comp=build(shift); inv=invert(comp)
print('composite (row-major, CPU convention):'); [print(['%.9g'%float(v) for v in row]) for row in comp]
quads={1:(220,320,140,240),3:(420,520,140,240),4:(120,220,240,340),6:(320,420,240,340)}
hw_sign={120:'>=',220:'>=',320:'<',420:'<',520:'<'}; hw_y={140:'<',240:'<',340:'<'}
print('\nvertex          exact x_s-320.. (ulps)   fp32seq   fp32pair   x*rcp(w)   | exact y (ulps)  fp32seq | hw x  hw y')
for qi,(l,r,t,b) in quads.items():
    for (x,y,z) in ((l,t,10.0),(r,t,10.0),(r,b,0.0),(l,b,0.0)):
        w=unproject([F(x),F(y),F(z),F(1)],inv,F(z))
        v=[w[0],w[1],F(z),F(1)]
        # exact
        C=[[Fr(float(c)) for c in row] for row in comp]; V=[Fr(float(c)) for c in v]
        X=[sum(V[i]*C[i][j] for i in range(4)) for j in range(4)]
        ex=X[0]/X[3]; ey=X[1]/X[3]
        dx=float(ex-x); dy=float(ey-y)
        # fp32 sequential (our GLSL dot order assumed sequential), then divide
        Xs=vecmul(v,comp); xs=fdiv(Xs[0],Xs[3]); ys=fdiv(Xs[1],Xs[3])
        # pairwise
        def pair(j):
            p=[fmul(v[i],comp[i][j]) for i in range(4)]; return fadd(fadd(p[0],p[1]),fadd(p[2],p[3]))
        Xp=[pair(j) for j in range(4)]; xp=fdiv(Xp[0],Xp[3])
        # x * rcp(w)
        rc=fdiv(1,Xs[3]); xr=fmul(Xs[0],rc)
        def rel(val,target):
            d=float(val)-target
            return '=' if d==0 else ('+%.1f'%(d/ulp(target)) if d>0 else '%.1f'%(d/ulp(target)))
        print(f'q{qi} ({x:3d},{y:3d},{z:4.1f})  {dx/ulp(x):+7.2f}            {rel(xs,x):>6s}   {rel(xp,x):>6s}    {rel(xr,x):>6s}    | {dy/ulp(y):+7.2f}      {rel(ys,y):>6s}  | {hw_sign[x]:>2s}   {hw_y[y]}')
