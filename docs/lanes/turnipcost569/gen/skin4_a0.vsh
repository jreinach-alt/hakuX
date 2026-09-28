; A D3D8-style 4-bone palette skinning program, the shape Xbox titles ship:
; per-vertex bone indices address a matrix palette through A0, so every
; palette read is c[A0+n]. Not from a title; written for this lane to exercise
; vsh-prog.c's dynamic-index path (decode_opcode_input, :342-344).
;   v0 position, v1 weights, v2 indices (pre-scaled by 3), v3 normal,
;   v4 diffuse, v9 texcoord0
;   c[0..3] view-projection, c[4] light dir, c[5] (0,1,0.5,255),
;   c[6] light colour, c[10..] the palette, 3 rows per bone

MOV R6, v2
ARL A0, R6.x
DP4 R0.x, v0, c[A0+10]
DP4 R0.y, v0, c[A0+11]
DP4 R0.z, v0, c[A0+12]
DP3 R1.x, v3, c[A0+10]
DP3 R1.y, v3, c[A0+11]
DP3 R1.z, v3, c[A0+12]
MUL R2.xyz, R0.xyz, v1.x
MUL R3.xyz, R1.xyz, v1.x

ARL A0, R6.y
DP4 R0.x, v0, c[A0+10]
DP4 R0.y, v0, c[A0+11]
DP4 R0.z, v0, c[A0+12]
DP3 R1.x, v3, c[A0+10]
DP3 R1.y, v3, c[A0+11]
DP3 R1.z, v3, c[A0+12]
MAD R2.xyz, R0.xyz, v1.y, R2.xyz
MAD R3.xyz, R1.xyz, v1.y, R3.xyz

ARL A0, R6.z
DP4 R0.x, v0, c[A0+10]
DP4 R0.y, v0, c[A0+11]
DP4 R0.z, v0, c[A0+12]
DP3 R1.x, v3, c[A0+10]
DP3 R1.y, v3, c[A0+11]
DP3 R1.z, v3, c[A0+12]
MAD R2.xyz, R0.xyz, v1.z, R2.xyz
MAD R3.xyz, R1.xyz, v1.z, R3.xyz

ARL A0, R6.w
DP4 R0.x, v0, c[A0+10]
DP4 R0.y, v0, c[A0+11]
DP4 R0.z, v0, c[A0+12]
DP3 R1.x, v3, c[A0+10]
DP3 R1.y, v3, c[A0+11]
DP3 R1.z, v3, c[A0+12]
MAD R2.xyz, R0.xyz, v1.w, R2.xyz
MAD R3.xyz, R1.xyz, v1.w, R3.xyz

MOV R2.w, c[5].y
DP4 oPos.x, R2, c[0]
DP4 oPos.y, R2, c[1]
DP4 oPos.z, R2, c[2]
DP4 oPos.w, R2, c[3]

DP3 R4.w, R3.xyz, R3.xyz
RSQ R4.w, R4.w
MUL R3.xyz, R3.xyz, R4.w
DP3 R5.x, R3.xyz, -c[4].xyz
MAX R5.x, R5.x, c[5].x
MUL R5.xyz, c[6].xyz, R5.x
MUL oD0.xyz, v4.xyz, R5.xyz
MOV oD0.w, v4.w
MOV oT0, v9
