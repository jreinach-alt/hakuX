# Desktop experiment: make the x86_64 JIT truncate FIST like aarch64's FCVTZS

Local only, never committed as code. Apply with `git apply` after extracting the block. `HAKUX_FIST_TRUNC=1` switches `cvt32f`/`cvt64f` from CVTSS2SI/CVTSD2SI (MXCSR.RC) to CVTTSS2SI/CVTTSD2SI (truncate). Used for dg3 in NOTES.md "(b) root cause".

```diff
diff --git a/tcg/i386/tcg-target.c.inc b/tcg/i386/tcg-target.c.inc
index 44119bf2ff..901ea8ce72 100644
--- a/tcg/i386/tcg-target.c.inc
+++ b/tcg/i386/tcg-target.c.inc
@@ -3116,7 +3116,8 @@ static inline void tcg_out_op(TCGContext *s, TCGOpcode opc, TCGType type,
         tcg_out_modrm(s, OPC_CVTSS2SD, a0, a1);
         break;
     OP_32_64(cvt32f):
-        tcg_out_modrm(s, OPC_CVTSS2SI + rexw, a0, a1);
+        /* LOCAL NEVER-COMMIT x1port1012: HAKUX_FIST_TRUNC mimics aarch64 FCVTZS */
+        tcg_out_modrm(s, (getenv("HAKUX_FIST_TRUNC") ? (0x2c | P_EXT | P_SIMDF3) : OPC_CVTSS2SI) + rexw, a0, a1);
         break;
     OP_f32_f64(cvt32i):
         tcg_out_modrm(s, OPC_PXOR, a0, a0);
@@ -3126,7 +3127,8 @@ static inline void tcg_out_op(TCGContext *s, TCGOpcode opc, TCGType type,
         tcg_out_modrm(s, OPC_CVTSD2SS, a0, a1);
         break;
     OP_32_64(cvt64f):
-        tcg_out_modrm(s, OPC_CVTSD2SI + rexw, a0, a1);
+        /* LOCAL NEVER-COMMIT x1port1012: HAKUX_FIST_TRUNC mimics aarch64 FCVTZS */
+        tcg_out_modrm(s, (getenv("HAKUX_FIST_TRUNC") ? (0x2c | P_EXT | P_SIMDF2) : OPC_CVTSD2SI) + rexw, a0, a1);
         break;
     OP_f32_f64(cvt64i):
         tcg_out_modrm(s, OPC_PXOR, a0, a0);
```
