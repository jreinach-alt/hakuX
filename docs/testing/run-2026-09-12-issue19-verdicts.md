# Issue #19: what the accused tests do when run alone

Company arm APK: `f9b5a5df2776`

## Group `g0` — 54 accused

| test | renders instead | in company | alone | verdict |
|---|---|---|---:|---|
| `Texture_signed_component_tests::txt_A8R8G8B8_SADD` | `txt_A8R8G8B8_ADD` | 83.03 | 83.03 | **missing-state** — as wrong alone |
| `Fog_gen::FogGen_VS-linear-radial` | `FogGen_VS-linear-planar` | 91.64 | 91.64 | **missing-state** — as wrong alone |
| `Fog_gen::FogGen_VS-linear_abs-radial` | `FogGen_VS-linear_abs-planar` | 89.54 | 89.54 | **missing-state** — as wrong alone |
| `Fog_gen::FogGen_VS-exp2-radial` | `FogGen_VS-exp2-planar` | 73.15 | 73.15 | **missing-state** — as wrong alone |
| `Fog_gen::FogGen_VS-exp2_abs-radial` | `FogGen_VS-exp2_abs-planar` | 73.15 | 73.15 | **missing-state** — as wrong alone |
| `Fog_gen::FogGen_VS-exp-radial` | `FogGen_VS-exp-planar` | 70.95 | 70.95 | **missing-state** — as wrong alone |
| `Blend_surface::DstAlpha_X_ORGB8` | `DstAlpha_ARGB8` | 65.49 | 65.49 | **missing-state** — as wrong alone |
| `Blend_surface::1-DstAlpha_X_ORGB8` | `1-DstAlpha_ARGB8` | 50.61 | 50.61 | **missing-state** — as wrong alone |
| `Fog_gen::FogGen_VS-exp_abs-radial` | `FogGen_VS-exp_abs-planar` | 62.56 | 62.56 | **missing-state** — as wrong alone |
| `Blend_surface::1-DstAlpha_X_ZRGB8` | `1-DstAlpha_ARGB8` | 32.48 | 32.48 | **missing-state** — as wrong alone |
| `Blend_surface::DstAlpha_X_ZRGB8` | `DstAlpha_ARGB8` | 32.00 | 32.00 | **missing-state** — as wrong alone |
| `Image_blit::ImgBlt_Clip_320_240_0_0` | `ImgBlt_Clip_0_0_640_480` | 5.58 | 5.58 | **missing-state** — as wrong alone |
| `W_param::prog_w_zero_inf__bitri_w-0.00` | `ff_w_zero_inf__quad_w-inf` | 86.29 | 86.29 | **missing-state** — as wrong alone |
| `Image_blit::ImgBlt_Clip_320_240_1_1` | `ImgBlt_Clip_0_0_640_480` | 5.58 | 5.58 | **missing-state** — as wrong alone |
| `Specular::ControlFlagsNoLight_VS` | `ControlFlagsLightDisable_VS` | 16.97 | 16.97 | **missing-state** — as wrong alone |
| `Blend_surface::1-DstAlpha_XA_O1A7RGB8` | `1-DstAlpha_ARGB8` | 9.87 | 9.87 | **missing-state** — as wrong alone |
| `Fog_exceptional_value::INF-FogExc-exp-abs_planar` | `NaN-FogExc-exp-abs_planar` | 4.06 | 4.06 | **missing-state** — as wrong alone |
| `Fog_exceptional_value::INF-FogExc-exp-fog_x` | `NaN-FogExc-exp-fog_x` | 4.06 | 4.06 | **missing-state** — as wrong alone |
| `Fog_exceptional_value::INF-FogExc-exp-planar` | `NaN-FogExc-exp-planar` | 4.06 | 4.06 | **missing-state** — as wrong alone |
| `Fog_exceptional_value::INF-FogExc-exp-spec_alpha` | `NaN-FogExc-exp-spec_alpha` | 4.06 | 4.06 | **missing-state** — as wrong alone |
| `Image_blit::ImgBlt_Clip_320_240_0_10` | `ImgBlt_Clip_0_0_640_480` | 5.58 | 5.58 | **missing-state** — as wrong alone |
| `Specular::ControlFlags_VS` | `ControlFlagsLightDisable_VS` | 19.45 | 19.45 | **missing-state** — as wrong alone |
| `Blend_surface::DstAlpha_XA_O1A7RGB8` | `DstAlpha_ARGB8` | 7.89 | 7.89 | **missing-state** — as wrong alone |
| `Image_blit::ImgBlt_Clip_300_200_16_24` | `ImgBlt_Clip_0_0_640_480` | 5.40 | 5.40 | **missing-state** — as wrong alone |
| `Image_blit::ImgBlt_Clip_320_240_64_40` | `ImgBlt_Clip_0_0_640_480` | 4.59 | 4.59 | **missing-state** — as wrong alone |
| `ZMinMaxControl::CtrlFixed_WBuf_NEARFAR_ZCLAMP` | `CtrlFixed_WBuf_ZCLAMP_IgnW` | 7.24 | 7.24 | **missing-state** — as wrong alone |
| `ZMinMaxControl::CtrlFixed_NEARFAR_ZCLAMP` | `CtrlFixed_WBuf_ZCLAMP_IgnW` | 7.26 | 7.26 | **missing-state** — as wrong alone |
| `ZMinMaxControl::Ctrl_NEARFAR_ZCLAMP` | `Ctrl_ZCLAMP_IgnW` | 6.89 | 6.89 | **missing-state** — as wrong alone |
| `ZMinMaxControl::Ctrl_WBuf_NEARFAR_ZCLAMP` | `Ctrl_WBuf_ZCLAMP_IgnW` | 6.89 | 6.89 | **missing-state** — as wrong alone |
| `Surface_format::Fmt_X8R8G8B8_Z8R8G8B8` | `Fmt_A8R8G8B8` | 8.23 | 8.23 | **missing-state** — as wrong alone |
| `Image_blit::ImgBlt_Clip_320_240_640_480` | `ImgBlt_Clip_0_0_640_480` | 4.13 | 4.13 | **missing-state** — as wrong alone |
| `ZMinMaxControl::CtrlFixed_NEARFAR_ZCLAMP_IgnW` | `CtrlFixed_WBuf_ZCLAMP_IgnW` | 7.24 | 7.24 | **missing-state** — as wrong alone |
| `Bump_map::BumpMap_Y16_L` | `BumpMap_AY8_L` | 6.92 | 6.92 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_winf` | `ff_w_zero_inf__quad_w-inf` | 12.22 | 12.22 | **missing-state** — as wrong alone |
| `Bump_map::BumpMap_Y16` | `BumpMap_AY8_L` | 6.92 | 6.92 | **missing-state** — as wrong alone |
| `ZMinMaxControl::Ctrl_NEARFAR_ZCLAMP_IgnW` | `Ctrl_WBuf_ZCLAMP_IgnW` | 6.89 | 6.89 | **missing-state** — as wrong alone |
| `ZMinMaxControl::CtrlFixed_WBuf_NEARFAR_ZCLAMP_IgnW` | `CtrlFixed_WBuf_ZCLAMP_IgnW` | 7.23 | 7.23 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_w-1.50e-36` | `ff_w_zero_inf__quad_w-inf` | 18.73 | 18.73 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_w-1.88e-37` | `ff_w_zero_inf__quad_w-inf` | 18.73 | 18.73 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_w-7.52e-37` | `ff_w_zero_inf__quad_w-inf` | 18.73 | 18.73 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_w-3.76e-37` | `ff_w_zero_inf__quad_w-inf` | 18.73 | 18.73 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_w-0.00` | `ff_w_zero_inf__quad_w-inf` | 18.73 | 18.73 | **missing-state** — as wrong alone |
| `ZMinMaxControl::Ctrl_WBuf_NEARFAR_ZCLAMP_IgnW` | `Ctrl_WBuf_ZCLAMP_IgnW` | 6.89 | 6.89 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__quad_w0.00` | `ff_w_zero_inf__quad_w-inf` | 17.09 | 17.09 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__bitri_w-inf` | `ff_w_zero_inf__bitri_winf` | 27.18 | 27.18 | **missing-state** — as wrong alone |
| `Blend_surface::DstAlpha_X_O1RGB5` | `DstAlpha_XA_Z1A7RGB8` | 63.47 | 63.47 | **missing-state** — as wrong alone |
| `Bump_map::BumpMap_UYVY_L` | `BumpMap_G8B8` | 34.01 | 34.01 | **missing-state** — as wrong alone |
| `Bump_map::BumpMap_YUY2_L` | `BumpMap_G8B8_L` | 34.01 | 34.01 | **missing-state** — as wrong alone |
| `Surface_format::Fmt_X1A7R8G8B8_Z1A7R8G8B8` | `Fmt_X1A7R8G8B8_O1A7R8G8B8` | 4.13 | 4.13 | **missing-state** — as wrong alone |
| `Blend_surface::1-DstAlpha_X_O1RGB5` | `1-DstAlpha_XA_Z1A7RGB8` | 45.33 | 45.33 | **missing-state** — as wrong alone |
| `Texture_render_target::TexFmt_A8_L` | `TexFmt_DXT1` | 67.42 | 0.00 | **contamination** — exact alone |
| `Texture_render_target::TexFmt_A8` | `TexFmt_DXT1` | 67.42 | 0.00 | **contamination** — exact alone |
| `W_param::ff_w_zero_inf__bitri_w0.00` | `ff_w_zero_inf__quad_w0.25` | 48.52 | 48.52 | **missing-state** — as wrong alone |
| `W_param::ff_w_zero_inf__bitri_w-0.00` | `ff_w_zero_inf__quad_w0.25` | 48.47 | 48.47 | **missing-state** — as wrong alone |

## Group `g1` — 0 accused

Nothing accused; every failing capture in this group fits its own golden better than any other in the suite.

## Group `g2` — 30 accused

| test | renders instead | in company | alone | verdict |
|---|---|---|---:|---|
| `Blend_tests::#spot_1_SREVSUB` | `#spot_1_REVSUB` | 13.79 | 13.79 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_srcAsat_SREVSUB` | `#spot_srcAsat_REVSUB` | 13.79 | 13.79 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_dstA_SREVSUB` | `#spot_dstA_REVSUB` | 13.82 | 13.82 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_dstRGB_SREVSUB` | `#spot_dstRGB_REVSUB` | 13.82 | 13.82 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-cA_SREVSUB` | `#spot_1-cA_REVSUB` | 13.74 | 13.74 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-cRGB_SREVSUB` | `#spot_1-cRGB_REVSUB` | 13.74 | 13.74 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_srcA_SREVSUB` | `#spot_srcA_REVSUB` | 13.78 | 13.78 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_srcRGB_SREVSUB` | `#spot_srcRGB_REVSUB` | 13.78 | 13.78 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_cA_SREVSUB` | `#spot_cA_REVSUB` | 13.39 | 13.39 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_cRGB_SREVSUB` | `#spot_cRGB_REVSUB` | 13.39 | 13.39 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-srcA_SREVSUB` | `#spot_1-srcA_REVSUB` | 13.05 | 13.05 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-srcRGB_SREVSUB` | `#spot_1-srcRGB_REVSUB` | 12.79 | 12.79 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-dstRGB_SREVSUB` | `#spot_1-dstRGB_REVSUB` | 12.43 | 12.43 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-dstA_SREVSUB` | `#spot_1-dstA_REVSUB` | 12.43 | 12.43 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_0_SREVSUB` | `#spot_0_REVSUB` | 11.40 | 11.40 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_0_SADD` | `#spot_0_ADD` | 8.41 | 8.41 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-dstRGB_SADD` | `#spot_1-dstRGB_ADD` | 27.34 | 27.34 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_srcRGB_SADD` | `#spot_srcRGB_ADD` | 31.17 | 31.17 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_srcA_SADD` | `#spot_srcA_ADD` | 29.95 | 29.95 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_dstA_SADD` | `#spot_dstA_ADD` | 21.48 | 21.48 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1_SADD` | `#spot_1_ADD` | 33.85 | 33.85 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_cA_SADD` | `#spot_cA_ADD` | 13.66 | 13.66 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_cRGB_SADD` | `#spot_cRGB_ADD` | 13.66 | 13.66 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-cA_SADD` | `#spot_1-cA_ADD` | 23.45 | 23.45 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-cRGB_SADD` | `#spot_1-cRGB_ADD` | 23.45 | 23.45 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-dstA_SADD` | `#spot_1-dstA_ADD` | 17.25 | 17.25 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-srcA_SADD` | `#spot_1-srcA_ADD` | 9.35 | 9.35 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_1-srcRGB_SADD` | `#spot_1-srcRGB_ADD` | 8.55 | 8.55 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_srcAsat_SADD` | `#spot_srcAsat_ADD` | 18.94 | 18.94 | **missing-state** — as wrong alone |
| `Blend_tests::#spot_dstRGB_SADD` | `#spot_dstRGB_ADD` | 8.35 | 8.35 | **missing-state** — as wrong alone |

## Blend tests, against silicon's blend model

`g2`, 105 #spot_ captures:

```
quantiser fits (ours against the model):
  blend round / blit round:  16409 hit,   1591 miss
  blend round / blit floor:  10267 hit,   7733 miss
  blend floor / blit round:  14282 hit,   3718 miss
  blend floor / blit floor:   9060 hit,   8940 miss
  best fit: blend round / blit round (silicon-s own)

|delta| against silicon, 18000 samples:
     0: 16409
     6: 16
     9: 34
    10: 1
    11: 1
    15: 36
    16: 1
    17: 1
    20: 2
    21: 2
    24: 1
    25: 44
    26: 7
    29: 30
    30: 56
    36: 42
    38: 20
    44: 288
    45: 4
    59: 4
    65: 4
    68: 2
    73: 14
    74: 77
    88: 2
   103: 6
   109: 2
   112: 6
   118: 6
   133: 13
   139: 7
   141: 6
   142: 5
   147: 51
   148: 48
   153: 1
   156: 3
   162: 8
   168: 6
   171: 3
   176: 9
   177: 272
   183: 7
   185: 13
   186: 3
   191: 9
   192: 41
   206: 6
   207: 2
   212: 6
   213: 2
   215: 4
   221: 357
  within one or two steps: 0  <- no precision floor here

channels wrong: R=1529, G=1529, B=1197

exact as captured         : 16409
exact once R and B swapped: 0
wrong either way          : 1591
```

## Totals

- **contamination**: 2
- **partial**: 0
- **missing-state**: 82
- **no-run**: 0
- **mismatched-binary**: 0

### Missing-state tests, which name a feature rather than an ordering bug

- `Texture_signed_component_tests::txt_A8R8G8B8_SADD`
- `Fog_gen::FogGen_VS-linear-radial`
- `Fog_gen::FogGen_VS-linear_abs-radial`
- `Fog_gen::FogGen_VS-exp2-radial`
- `Fog_gen::FogGen_VS-exp2_abs-radial`
- `Fog_gen::FogGen_VS-exp-radial`
- `Blend_surface::DstAlpha_X_ORGB8`
- `Blend_surface::1-DstAlpha_X_ORGB8`
- `Fog_gen::FogGen_VS-exp_abs-radial`
- `Blend_surface::1-DstAlpha_X_ZRGB8`
- `Blend_surface::DstAlpha_X_ZRGB8`
- `Image_blit::ImgBlt_Clip_320_240_0_0`
- `W_param::prog_w_zero_inf__bitri_w-0.00`
- `Image_blit::ImgBlt_Clip_320_240_1_1`
- `Specular::ControlFlagsNoLight_VS`
- `Blend_surface::1-DstAlpha_XA_O1A7RGB8`
- `Fog_exceptional_value::INF-FogExc-exp-abs_planar`
- `Fog_exceptional_value::INF-FogExc-exp-fog_x`
- `Fog_exceptional_value::INF-FogExc-exp-planar`
- `Fog_exceptional_value::INF-FogExc-exp-spec_alpha`
- `Image_blit::ImgBlt_Clip_320_240_0_10`
- `Specular::ControlFlags_VS`
- `Blend_surface::DstAlpha_XA_O1A7RGB8`
- `Image_blit::ImgBlt_Clip_300_200_16_24`
- `Image_blit::ImgBlt_Clip_320_240_64_40`
- `ZMinMaxControl::CtrlFixed_WBuf_NEARFAR_ZCLAMP`
- `ZMinMaxControl::CtrlFixed_NEARFAR_ZCLAMP`
- `ZMinMaxControl::Ctrl_NEARFAR_ZCLAMP`
- `ZMinMaxControl::Ctrl_WBuf_NEARFAR_ZCLAMP`
- `Surface_format::Fmt_X8R8G8B8_Z8R8G8B8`
- `Image_blit::ImgBlt_Clip_320_240_640_480`
- `ZMinMaxControl::CtrlFixed_NEARFAR_ZCLAMP_IgnW`
- `Bump_map::BumpMap_Y16_L`
- `W_param::ff_w_zero_inf__quad_winf`
- `Bump_map::BumpMap_Y16`
- `ZMinMaxControl::Ctrl_NEARFAR_ZCLAMP_IgnW`
- `ZMinMaxControl::CtrlFixed_WBuf_NEARFAR_ZCLAMP_IgnW`
- `W_param::ff_w_zero_inf__quad_w-1.50e-36`
- `W_param::ff_w_zero_inf__quad_w-1.88e-37`
- `W_param::ff_w_zero_inf__quad_w-7.52e-37`
- `W_param::ff_w_zero_inf__quad_w-3.76e-37`
- `W_param::ff_w_zero_inf__quad_w-0.00`
- `ZMinMaxControl::Ctrl_WBuf_NEARFAR_ZCLAMP_IgnW`
- `W_param::ff_w_zero_inf__quad_w0.00`
- `W_param::ff_w_zero_inf__bitri_w-inf`
- `Blend_surface::DstAlpha_X_O1RGB5`
- `Bump_map::BumpMap_UYVY_L`
- `Bump_map::BumpMap_YUY2_L`
- `Surface_format::Fmt_X1A7R8G8B8_Z1A7R8G8B8`
- `Blend_surface::1-DstAlpha_X_O1RGB5`
- `W_param::ff_w_zero_inf__bitri_w0.00`
- `W_param::ff_w_zero_inf__bitri_w-0.00`
- `Blend_tests::#spot_1_SREVSUB`
- `Blend_tests::#spot_srcAsat_SREVSUB`
- `Blend_tests::#spot_dstA_SREVSUB`
- `Blend_tests::#spot_dstRGB_SREVSUB`
- `Blend_tests::#spot_1-cA_SREVSUB`
- `Blend_tests::#spot_1-cRGB_SREVSUB`
- `Blend_tests::#spot_srcA_SREVSUB`
- `Blend_tests::#spot_srcRGB_SREVSUB`
- `Blend_tests::#spot_cA_SREVSUB`
- `Blend_tests::#spot_cRGB_SREVSUB`
- `Blend_tests::#spot_1-srcA_SREVSUB`
- `Blend_tests::#spot_1-srcRGB_SREVSUB`
- `Blend_tests::#spot_1-dstRGB_SREVSUB`
- `Blend_tests::#spot_1-dstA_SREVSUB`
- `Blend_tests::#spot_0_SREVSUB`
- `Blend_tests::#spot_0_SADD`
- `Blend_tests::#spot_1-dstRGB_SADD`
- `Blend_tests::#spot_srcRGB_SADD`
- `Blend_tests::#spot_srcA_SADD`
- `Blend_tests::#spot_dstA_SADD`
- `Blend_tests::#spot_1_SADD`
- `Blend_tests::#spot_cA_SADD`
- `Blend_tests::#spot_cRGB_SADD`
- `Blend_tests::#spot_1-cA_SADD`
- `Blend_tests::#spot_1-cRGB_SADD`
- `Blend_tests::#spot_1-dstA_SADD`
- `Blend_tests::#spot_1-srcA_SADD`
- `Blend_tests::#spot_1-srcRGB_SADD`
- `Blend_tests::#spot_srcAsat_SADD`
- `Blend_tests::#spot_dstRGB_SADD`
