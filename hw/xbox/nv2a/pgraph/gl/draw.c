/*
 * Geforce NV2A PGRAPH OpenGL Renderer
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2015 Jannik Vogel
 * Copyright (c) 2018-2024 Matt Borgerson
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, see <http://www.gnu.org/licenses/>.
 */

#include "qemu/fast-hash.h"
#include "hw/xbox/nv2a/nv2a_int.h"
#include "hw/xbox/nv2a/pgraph/prim_rewrite.h"
#include "debug.h"
#include "renderer.h"

#ifdef __ANDROID__
#include <android/log.h>

static void android_log_gl_errors(const char *ctx)
{
    GLenum err;

    while ((err = glGetError()) != GL_NO_ERROR) {
        __android_log_print(ANDROID_LOG_WARN, "hakuX",
                            "GL error 0x%X at %s", err, ctx);
    }
}
#else
static inline void android_log_gl_errors(const char *ctx)
{
    (void)ctx;
}
#endif

/*
 * A clear writes the surface the way a draw does, and the surface-to-texture
 * path has to be told: it only refreshes a texture bound straight from a
 * surface when that surface's draw time has moved on. A surface that is
 * cleared and not otherwise drawn to keeps the draw time it had, so a texture
 * sampled from it afterwards still shows what was there before the clear.
 */
/*
 * glLineWidth raises GL_INVALID_VALUE for width <= 0 and then does nothing.
 * The guest can legitimately ask for line width 0 -- Line_width and 2D_Lines
 * both do -- and the MIN clamps above only bound the TOP of the supported
 * range, so that reached the driver as glLineWidth(0.0f) and left an error
 * pending. Nothing consumed it, and gl/shaders.c:413 asserts glGetError() ==
 * GL_NO_ERROR on entry, so the whole process aborted: iso_line produced ZERO
 * captures on desktop GL, and seven suites could not be measured at all.
 * Android never saw it because that same function drains errors in a loop
 * rather than asserting.
 *
 * Skipping the call is BEHAVIOUR-IDENTICAL: a call GL rejects is a no-op, so
 * the line width GL uses is the same either way. The only difference is that
 * no error is raised.
 *
 * What the hardware actually draws at line width 0 is NOT settled here, and
 * this deliberately does not decide it -- clamping up to the minimum supported
 * width would be a visible answer to a question nothing has measured. This
 * changes a crash into the behaviour we already had.
 */
static void set_line_width(float width)
{
    if (width > 0.0f) {
        glLineWidth(width);
    }
}

static void mark_clear_drawn(PGRAPHState *pg, bool write_color, bool write_zeta)
{
    PGRAPHGLState *r = pg->gl_renderer_state;

    pg->draw_time++;
    if (r->color_binding && write_color) {
        r->color_binding->draw_time = pg->draw_time;
    }
    if (r->zeta_binding && write_zeta) {
        r->zeta_binding->draw_time = pg->draw_time;
    }
}

/*
 * True when the colour surface format stores no alpha bits at all, so the
 * blend unit has no destination alpha to read and substitutes 1.0.
 *
 * Measured on Blend surface's DstAlpha/1-DstAlpha pairs (issue #48): on both
 * X8R8G8B8 variants and both X1R5G5B5 variants, the golden is 255 everywhere
 * for DST_ALPHA and 0 everywhere for ONE_MINUS_DST_ALPHA, which pins Ad = 1.0
 * from two complementary directions. R5G6B5, which already lands on a host
 * format with no alpha component, is bit-exact and is the control. The `Z`
 * variants do not read their pad bits as zero here; that distinction belongs to
 * the texture unit, not the blend unit. See the Vulkan renderer's copy of this
 * comment for the full derivation.
 *
 * X1A7R8G8B8 is excluded: its seven alpha bits are real data.
 */
static bool surface_color_format_dst_alpha_is_one(unsigned int color_format)
{
    switch (color_format) {
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_Z1R5G5B5:
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_X1R5G5B5_O1R5G5B5:
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_R5G6B5:
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_Z8R8G8B8:
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_X8R8G8B8_O8R8G8B8:
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_B8:
    case NV097_SET_SURFACE_FORMAT_COLOR_LE_G8B8:
        return true;
    default:
        return false;
    }
}

/*
 * #158/#59's GL half. psh.c stamps the format's pad constant into the
 * fragment's alpha, so GL_SRC_ALPHA -- which is output index 0's alpha --
 * stops being the combiner's alpha and becomes the constant. Index 1 carries
 * the combiner's alpha unchanged (psh.c copies it after the alpha test and
 * after #43's fold, so it is exactly the value the blend unit would have
 * consumed), and GL_SRC1_ALPHA reads it.
 *
 * The substitution is therefore a NO-OP IN INTENT: a draw that does not stamp
 * is untouched, and a draw that does gets the same colour it would have got
 * before the stamp existed. This mirrors pad_write_color_factor() in
 * vk/draw.c, which the Vulkan side measured at eight Blend_surface Add_SrcA
 * captures, four of them from bit-exact, with no exceptions to the rule
 * `moved = {format has pad bits} AND {colour factor is SRC_ALPHA}`.
 *
 * COLOUR ONLY: the alpha half is forced to ONE/ZERO/ADD by the caller so that
 * result.a is the stamp itself, which is the whole point of stamping.
 *
 * GL_SRC_ALPHA_SATURATE is left alone, as it is on the Vulkan side, and the
 * reason is a derivation rather than an observation about the corpus: that
 * factor is min(As, 1 - Ad), which is 0 for BOTH pad variants once the stamp
 * lands -- _Z because As is the stamped 0, _O because Ad is folded to 1 by
 * surface_color_format_dst_alpha_is_one(). So there is nothing to substitute
 * whatever a disc contains, and the absence of a GL_SRC1_ALPHA_SATURATE token
 * costs nothing. (That no capture on this fleet reaches it on a stamping
 * format is true, and is the secondary note, not the argument: vk/draw.c's own
 * pass-1 audit retired the argument-from-absence here as finding L2, because a
 * wrong comment on right code is believed.)
 *
 * NOT COMPILED ON GLES. GL_SRC1_ALPHA and GL_ONE_MINUS_SRC1_ALPHA are
 * EXT_blend_func_extended tokens there, spelled with an _EXT suffix, and the
 * extension is not core in GLES 3.0 -- so the GLES headers do not define these
 * names and the function does not parse, dead code or not. The exclusion is
 * the same one gl/renderer.c makes for the capability flag and psh.c makes for
 * the two shader gates; this is the third site, and the one whose omission
 * broke the arm64-v8a build (audit pass 1, H1). Do not "fix" a future
 * recurrence by defining the tokens locally: that would compile a blend path
 * against a shader that has no index-1 output.
 */
#ifndef __ANDROID__
static GLenum pad_write_color_factor(GLenum factor)
{
    switch (factor) {
    case GL_SRC_ALPHA:
        return GL_SRC1_ALPHA;
    case GL_ONE_MINUS_SRC_ALPHA:
        return GL_ONE_MINUS_SRC1_ALPHA;
    default:
        return factor;
    }
}
#endif

/*
 * Fold a known Ad = 1.0 into a blend factor. SRC_ALPHA_SATURATE is min(As,
 * 1 - Ad) and so is also 0 here, but is left alone: no capture exercises it on
 * an alpha-less surface, and changing it would be unmeasured.
 */
static uint32_t blend_factor_with_dst_alpha_one(uint32_t factor)
{
    switch (factor) {
    case NV_PGRAPH_BLEND_SFACTOR_DST_ALPHA:
        return NV_PGRAPH_BLEND_SFACTOR_ONE;
    case NV_PGRAPH_BLEND_SFACTOR_ONE_MINUS_DST_ALPHA:
        return NV_PGRAPH_BLEND_SFACTOR_ZERO;
    default:
        return factor;
    }
}

/*
 * The two signed blend equations (issue #43). Silicon computes
 *
 *     signed(S) = S - 256 if S >= 128 else S
 *     FUNC_ADD_SIGNED              = clamp(signed(S) + D, 0, 255)
 *     FUNC_REVERSE_SUBTRACT_SIGNED = clamp(D - signed(S), 0, 255)
 *
 * with BOTH FACTORS IGNORED -- a measurement, at 176,160,768 of 176,160,768
 * channels over the 448 signed captures of the retired `BlendTests::
 * TestDetailed` oracle. Only the factor half is implemented, here and in the
 * Vulkan renderer; see that copy for why the signed fold of S cannot be
 * expressed in fixed-function blend state at all (silicon's output is
 * discontinuous in the source at S = 128, and every blend op is continuous),
 * and for the three places it could go instead.
 */
static bool blend_equation_is_signed(uint32_t equation)
{
    return equation == NV_PGRAPH_BLEND_EQN_FUNC_ADD_SIGNED ||
           equation == NV_PGRAPH_BLEND_EQN_FUNC_REVERSE_SUBTRACT_SIGNED;
}

#ifndef __ANDROID__
/*
 * #164/#59: the CLEAR half of the surface pad-bit write side, the counterpart
 * of the raster half pgraph_gl_draw_begin() gained in #158.
 *
 * The shared pgraph_get_clear_color()'s alpha switch (pgraph.c) has no case
 * for the four pad formats and falls through to `default: *a = 1.0f`. That is
 * the _O constant by coincidence -- which is why the _O twins have been
 * bit-exact all along -- and the wrong constant for _Z. So without this a _Z
 * surface holds alpha 1 where CLEAR_SURFACE wrote and, since #158, alpha 0
 * where the raster drew: one surface, two answers, where hardware gives 0 for
 * both. pgraph_vk_get_clear_color() has had this since #59.
 *
 * READ FROM THE SAME EXPRESSION the raster half reads
 * (pgraph_glsl_surface_pad_alpha_mode of surface_shape.color_format), not a
 * second per-format table: two independent derivations of one per-format fact
 * is how #48's clear and sampler halves came apart (audit M3/P4).
 *
 * GATED ON THE CAPABILITY FLAG, which the Vulkan copy does not need to be.
 * Ungated, a GL part without GL_ARB_blend_func_extended would clear to the pad
 * constant while drawing without it -- the same internal inconsistency this
 * fixes, with the operands swapped. The flag ties the two halves together, so
 * a part that cannot stamp also does not clear to the stamp, which is bit-for
 * -bit this renderer's behaviour before #158.
 *
 * NOT COMPILED ON GLES, for the reason the blend path is not (audit pass 1,
 * H1): the flag is never set there, so this would be dead code -- but the
 * three sites' exclusions disagreeing about HOW GLES is excluded is exactly
 * what H1 was about, and this is the fourth site. Note the consequence for
 * anyone measuring this: on a GLES build the change is a guaranteed no-op by
 * construction, so an arm that means to observe it must run desktop OpenGL,
 * which is where #158's own 236-capture arm ran.
 */
static void pgraph_gl_get_clear_color(PGRAPHState *pg, float rgba[4])
{
    pgraph_get_clear_color(pg, rgba);

    if (!pgraph_glsl_dual_src_pad_supported()) {
        return;
    }

    switch (pgraph_glsl_surface_pad_alpha_mode(pg->surface_shape.color_format)) {
    case PSH_PAD_ALPHA_ZERO: rgba[3] = 0.0f; break;
    case PSH_PAD_ALPHA_ONE:  rgba[3] = 1.0f; break;
    default: break;
    }
}
#endif

void pgraph_gl_clear_surface(NV2AState *d, uint32_t parameter)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHGLState *r = pg->gl_renderer_state;

    NV2A_DPRINTF("---------PRE CLEAR ------\n");
    pg->clearing = true;

    GLbitfield gl_mask = 0;

    bool write_color = (parameter & NV097_CLEAR_SURFACE_COLOR);
    bool write_zeta =
        (parameter & (NV097_CLEAR_SURFACE_Z | NV097_CLEAR_SURFACE_STENCIL));

    if (write_zeta) {
        GLint gl_clear_stencil;
        GLfloat gl_clear_depth;
        pgraph_get_clear_depth_stencil_value(pg, &gl_clear_depth,
                                             &gl_clear_stencil);

        if (parameter & NV097_CLEAR_SURFACE_Z) {
            gl_mask |= GL_DEPTH_BUFFER_BIT;
            glDepthMask(GL_TRUE);
            glClearDepth(gl_clear_depth);
        }
        if (parameter & NV097_CLEAR_SURFACE_STENCIL) {
            gl_mask |= GL_STENCIL_BUFFER_BIT;
            glStencilMask(0xff);
            glClearStencil(gl_clear_stencil);
        }
    }
    if (write_color) {
        gl_mask |= GL_COLOR_BUFFER_BIT;
        glColorMask((parameter & NV097_CLEAR_SURFACE_R)
                         ? GL_TRUE : GL_FALSE,
                    (parameter & NV097_CLEAR_SURFACE_G)
                         ? GL_TRUE : GL_FALSE,
                    (parameter & NV097_CLEAR_SURFACE_B)
                         ? GL_TRUE : GL_FALSE,
                    (parameter & NV097_CLEAR_SURFACE_A)
                         ? GL_TRUE : GL_FALSE);

        GLfloat rgba[4];
#ifdef __ANDROID__
        pgraph_get_clear_color(pg, rgba);
#else
        pgraph_gl_get_clear_color(pg, rgba);
#endif
        glClearColor(rgba[0], rgba[1], rgba[2], rgba[3]);
    }

    pgraph_gl_surface_update(d, true, write_color, write_zeta);

    /* FIXME: Needs confirmation */
    unsigned int xmin =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CLEARRECTX), NV_PGRAPH_CLEARRECTX_XMIN);
    unsigned int xmax =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CLEARRECTX), NV_PGRAPH_CLEARRECTX_XMAX);
    unsigned int ymin =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CLEARRECTY), NV_PGRAPH_CLEARRECTY_YMIN);
    unsigned int ymax =
        GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CLEARRECTY), NV_PGRAPH_CLEARRECTY_YMAX);

    NV2A_DPRINTF(
        "------------------CLEAR 0x%x %d,%d - %d,%d  %x---------------\n",
        parameter, xmin, ymin, xmax, ymax,
        d->pgraph.regs_[NV_PGRAPH_COLORCLEARVALUE]);

    /*
     * The surface clip rectangle bounds a clear as it bounds a draw: the
     * memory outside it is left alone whatever the clear rect says. pbkit
     * paints its debug text with clears, and Surface clip's
     * DebugTextShouldClip expects the lines above a tiny clip to stay
     * invisible; its rt_ tests fill the memory around the clip from the CPU
     * and expect a full-surface clear to leave that fill alone. A zero clip
     * size is not a hardware case that has been measured -- the suite sends
     * the surface size instead -- so it bounds nothing here.
     *
     * vk/draw.c has done this since the Vulkan renderer was fixed for these
     * same captures; this is that change, ported.
     */
    {
        unsigned int cx = pg->surface_shape.clip_x;
        unsigned int cy = pg->surface_shape.clip_y;
        unsigned int cw = pg->surface_shape.clip_width;
        unsigned int ch = pg->surface_shape.clip_height;
        if (cw) {
            xmin = MAX(xmin, cx);
            xmax = MIN(xmax, cx + cw - 1);
        }
        if (ch) {
            ymin = MAX(ymin, cy);
            ymax = MIN(ymax, cy + ch - 1);
        }
        if (xmin > xmax || ymin > ymax) {
            /* Entirely outside the clip: nothing is written. */
            pg->clearing = false;
            return;
        }
    }

    unsigned int scissor_width = xmax - xmin + 1,
                 scissor_height = ymax - ymin + 1;
    pgraph_apply_anti_aliasing_factor(pg, &xmin, &ymin);
    pgraph_apply_anti_aliasing_factor(pg, &scissor_width, &scissor_height);

    NV2A_DPRINTF("Translated clear rect to %d,%d - %d,%d\n", xmin, ymin,
                 xmin + scissor_width - 1, ymin + scissor_height - 1);

    bool full_clear = !xmin && !ymin &&
                      scissor_width >= pg->surface_binding_dim.width &&
                      scissor_height >= pg->surface_binding_dim.height;

    pgraph_apply_scaling_factor(pg, &xmin, &ymin);
    pgraph_apply_scaling_factor(pg, &scissor_width, &scissor_height);

    /* FIXME: Respect window clip?!?! */
    glEnable(GL_SCISSOR_TEST);
    glScissor(xmin, ymin, scissor_width, scissor_height);

    /* Dither */
    /* FIXME: Maybe also disable it here? + GL implementation dependent */
    if (pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) & NV_PGRAPH_CONTROL_0_DITHERENABLE) {
        glEnable(GL_DITHER);
    } else {
        glDisable(GL_DITHER);
    }

    glClear(gl_mask);

    glDisable(GL_SCISSOR_TEST);

    pgraph_gl_set_surface_dirty(pg, write_color, write_zeta);
    mark_clear_drawn(pg, write_color, write_zeta);

    if (r->color_binding) {
        r->color_binding->cleared = full_clear && write_color;
    }
    if (r->zeta_binding) {
        r->zeta_binding->cleared = full_clear && write_zeta;
    }
    
    pg->clearing = false;
}

void pgraph_gl_draw_begin(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHGLState *r = pg->gl_renderer_state;

    NV2A_GL_DGROUP_BEGIN("NV097_SET_BEGIN_END: 0x%x", pg->primitive_mode);

    uint32_t control_0 = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0);
    bool mask_alpha = control_0 & NV_PGRAPH_CONTROL_0_ALPHA_WRITE_ENABLE;
    bool mask_red = control_0 & NV_PGRAPH_CONTROL_0_RED_WRITE_ENABLE;
    bool mask_green = control_0 & NV_PGRAPH_CONTROL_0_GREEN_WRITE_ENABLE;
    bool mask_blue = control_0 & NV_PGRAPH_CONTROL_0_BLUE_WRITE_ENABLE;
    bool color_write = mask_alpha || mask_red || mask_green || mask_blue;
    bool depth_test = control_0 & NV_PGRAPH_CONTROL_0_ZENABLE;
    bool stencil_test =
        pgraph_reg_r(pg, NV_PGRAPH_CONTROL_1) & NV_PGRAPH_CONTROL_1_STENCIL_TEST_ENABLE;
    bool is_nop_draw = !(color_write || depth_test || stencil_test) ||
                       pgraph_draw_is_empty_line(pg);

    pgraph_gl_surface_update(d, true, true, depth_test || stencil_test);

    if (is_nop_draw) {
        return;
    }

    assert(r->color_binding || r->zeta_binding);

    pgraph_gl_bind_textures(d);

    glColorMask(mask_red, mask_green, mask_blue, mask_alpha);
    glDepthMask(!!(control_0 & NV_PGRAPH_CONTROL_0_ZWRITEENABLE));
    glStencilMask(GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_1),
                           NV_PGRAPH_CONTROL_1_STENCIL_MASK_WRITE));

    if (pgraph_reg_r(pg, NV_PGRAPH_BLEND) & NV_PGRAPH_BLEND_EN) {
        glEnable(GL_BLEND);
        uint32_t sfactor = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_BLEND),
                                    NV_PGRAPH_BLEND_SFACTOR);
        uint32_t dfactor = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_BLEND),
                                    NV_PGRAPH_BLEND_DFACTOR);
        /*
         * The guest-declared format, not r->color_binding->shape.color_format:
         * surface compatibility is decided on the host format, and the several
         * guest formats that share one are matched across a colour-format
         * change without the binding's shape being refreshed.  See the Vulkan
         * renderer's pgraph_vk_effective_blend_reg() for what that cost.
         */
        if (surface_color_format_dst_alpha_is_one(
                pg->surface_shape.color_format)) {
            sfactor = blend_factor_with_dst_alpha_one(sfactor);
            dfactor = blend_factor_with_dst_alpha_one(dfactor);
        }

        uint32_t equation = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_BLEND),
                                     NV_PGRAPH_BLEND_EQN);
        /* The signed equations consult neither factor; this overrides the
         * destination-alpha fold above on purpose, since ONE/ONE reads no Ad
         * either way. */
        if (blend_equation_is_signed(equation)) {
            sfactor = NV_PGRAPH_BLEND_SFACTOR_ONE;
            dfactor = NV_PGRAPH_BLEND_DFACTOR_ONE;
        }

        assert(sfactor < ARRAY_SIZE(pgraph_blend_factor_gl_map));
        assert(dfactor < ARRAY_SIZE(pgraph_blend_factor_gl_map));
        assert(equation < ARRAY_SIZE(pgraph_blend_equation_gl_map));

        GLenum gl_sfactor = pgraph_blend_factor_gl_map[sfactor];
        GLenum gl_dfactor = pgraph_blend_factor_gl_map[dfactor];

        /*
         * #158: when psh.c stamps this surface's pad constant into the
         * fragment alpha, the colour factors read the combiner's alpha from
         * index 1 instead, and the alpha half is forced so the stamp is what
         * lands in memory. Read from the same expression psh.c stages its
         * uniform from -- one derivation read twice rather than two
         * derivations of one per-format fact, which is how #48's clear and
         * sampler halves came apart (audit M3/P4).
         *
         * The Ad = 1.0 fold above STAYS, and that is not an oversight. It is
         * about what the blend unit substitutes for a missing destination
         * alpha, which #48 measured as one for BOTH suffixes; the stamp is
         * about what the texture unit reads back, which is zero for _Z and
         * one for _O. Different questions about the same bits -- see the
         * comment on surface_color_format_dst_alpha_is_one() above. Once the
         * stamp lands, memory holds the pad constant, so without this fold a
         * _Z surface's DST_ALPHA would read zero where hardware reads one.
         */
        /*
         * The GLES term mirrors psh.c's two gates, which read
         * `g_dual_src_pad_supported && !ps->opts.gles`. Today it cannot
         * diverge -- gl/shaders.c makes `gles` true exactly when __ANDROID__
         * is defined, and gl/renderer.c only sets the flag when it is not --
         * but the three sites disagreeing on HOW GLES is excluded is what
         * produced H1, and this is the site that would silently name a SRC1
         * factor against a shader with no index-1 output if the exclusion ever
         * became a run-time decision (a GLES-capable desktop build, ANGLE).
         * The GL spec leaves that undefined rather than erroring, so it would
         * arrive as corrupted colour and not as a diagnostic. Expressed as a
         * preprocessor guard rather than an `opts.gles` term because the
         * tokens themselves are absent on GLES, not merely unwanted.
         */
#ifdef __ANDROID__
        /*
         * Whole branch, not just the flag: making pad_stamped a compile-time
         * false would still leave the call to pad_write_color_factor() to be
         * parsed, and that function does not exist here.
         */
        glBlendFunc(gl_sfactor, gl_dfactor);
        glBlendEquation(pgraph_blend_equation_gl_map[equation]);
#else
        const bool pad_stamped =
            pgraph_glsl_dual_src_pad_supported() &&
            pgraph_glsl_surface_pad_alpha_mode(
                pg->surface_shape.color_format) != PSH_PAD_ALPHA_NONE;

        if (pad_stamped) {
            glBlendFuncSeparate(pad_write_color_factor(gl_sfactor),
                                pad_write_color_factor(gl_dfactor),
                                GL_ONE, GL_ZERO);
            glBlendEquationSeparate(pgraph_blend_equation_gl_map[equation],
                                    GL_FUNC_ADD);
        } else {
            glBlendFunc(gl_sfactor, gl_dfactor);
            glBlendEquation(pgraph_blend_equation_gl_map[equation]);
        }
#endif

        uint32_t blend_color = pgraph_reg_r(pg, NV_PGRAPH_BLENDCOLOR);
        float gl_blend_color[4];
        pgraph_argb_pack32_to_rgba_float(blend_color, gl_blend_color);
        glBlendColor(gl_blend_color[0], gl_blend_color[1], gl_blend_color[2],
                     gl_blend_color[3]);
    } else {
        glDisable(GL_BLEND);
    }

    /* Face culling */
    if (pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER)
            & NV_PGRAPH_SETUPRASTER_CULLENABLE) {
        uint32_t cull_face = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER),
                                      NV_PGRAPH_SETUPRASTER_CULLCTRL);
        assert(cull_face < ARRAY_SIZE(pgraph_cull_face_gl_map));
        glCullFace(pgraph_cull_face_gl_map[cull_face]);
        glEnable(GL_CULL_FACE);
    } else {
        glDisable(GL_CULL_FACE);
    }

    /* Front-face select */
    /* Winding is reverse here because clip-space y-coordinates are inverted */
    glFrontFace(pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER)
                    & NV_PGRAPH_SETUPRASTER_FRONTFACE
                        ? GL_CW : GL_CCW);

    /* Polygon offset is handled in geometry and fragment shaders explicitly */
    glDisable(GL_POLYGON_OFFSET_FILL);
#ifndef __ANDROID__ /* GL_POLYGON_OFFSET_LINE/POINT not valid in GLES 3.x */
    glDisable(GL_POLYGON_OFFSET_LINE);
    glDisable(GL_POLYGON_OFFSET_POINT);
#endif

    /* Depth testing */
    if (depth_test) {
        glEnable(GL_DEPTH_TEST);

        uint32_t depth_func = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0),
                                       NV_PGRAPH_CONTROL_0_ZFUNC);
        assert(depth_func < ARRAY_SIZE(pgraph_depth_func_gl_map));
        glDepthFunc(pgraph_depth_func_gl_map[depth_func]);
    } else {
        glDisable(GL_DEPTH_TEST);
    }

#ifndef __ANDROID__
    glEnable(GL_DEPTH_CLAMP);
#endif

#ifndef __ANDROID__ /* glProvokingVertex not available in GLES 3.x */
    /* Set first vertex convention to match Vulkan default */
    glProvokingVertex(GL_FIRST_VERTEX_CONVENTION);
#endif

    if (stencil_test) {
        glEnable(GL_STENCIL_TEST);

        uint32_t stencil_func = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_1),
                                    NV_PGRAPH_CONTROL_1_STENCIL_FUNC);
        uint32_t stencil_ref = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_1),
                                    NV_PGRAPH_CONTROL_1_STENCIL_REF);
        uint32_t func_mask = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_1),
                                NV_PGRAPH_CONTROL_1_STENCIL_MASK_READ);
        uint32_t op_fail = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_2),
                                NV_PGRAPH_CONTROL_2_STENCIL_OP_FAIL);
        uint32_t op_zfail = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_2),
                                NV_PGRAPH_CONTROL_2_STENCIL_OP_ZFAIL);
        uint32_t op_zpass = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_2),
                                NV_PGRAPH_CONTROL_2_STENCIL_OP_ZPASS);

        assert(stencil_func < ARRAY_SIZE(pgraph_stencil_func_gl_map));
        assert(op_fail < ARRAY_SIZE(pgraph_stencil_op_gl_map));
        assert(op_zfail < ARRAY_SIZE(pgraph_stencil_op_gl_map));
        assert(op_zpass < ARRAY_SIZE(pgraph_stencil_op_gl_map));

        glStencilFunc(
            pgraph_stencil_func_gl_map[stencil_func],
            stencil_ref,
            func_mask);

        glStencilOp(
            pgraph_stencil_op_gl_map[op_fail],
            pgraph_stencil_op_gl_map[op_zfail],
            pgraph_stencil_op_gl_map[op_zpass]);

    } else {
        glDisable(GL_STENCIL_TEST);
    }

    /* Dither */
    /* FIXME: GL implementation dependent */
    if (pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0) &
            NV_PGRAPH_CONTROL_0_DITHERENABLE) {
        glEnable(GL_DITHER);
    } else {
        glDisable(GL_DITHER);
    }

#ifndef __ANDROID__
    /* GL_PROGRAM_POINT_SIZE is not a valid enum in GLES 3.x;
     * point size from gl_PointSize is always enabled in GLES. */
    glEnable(GL_PROGRAM_POINT_SIZE);
#endif

    bool anti_aliasing = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_ANTIALIASING), NV_PGRAPH_ANTIALIASING_ENABLE);

    /*
     * Edge Antialiasing.
     *
     * The GL_LINE_SMOOTH / GL_POLYGON_SMOOTH half below is desktop-GL only:
     * GLES 3.x has neither enum, so on Android this compiles down to the line
     * width alone and both smoothing bits are ignored, exactly as in the
     * Vulkan backend. The device sweeps therefore measure nothing from it --
     * see the measurement and the cost of doing this properly in vk/draw.c
     * and docs/investigations/line-polygon-smoothing.md (#36).
     *
     * Worth a cheap check before anyone builds on the desktop path: both
     * branches gate smoothing on !anti_aliasing, and the nxdk -ls/-ps tests
     * are reported to redirect the colour surface with AA_CENTER_CORNER_2. If
     * NV_PGRAPH_ANTIALIASING_ENABLE is in fact set while those tests draw,
     * this gate suppresses smoothing on the very captures that are supposed
     * to exercise it, and desktop GL would be silently unsmoothed too. That
     * the hardware goldens plainly do carry coverage antialiasing says the
     * gate and the register state cannot both be what they look like.
     */
#ifdef __ANDROID__
    set_line_width(MIN(r->supported_aliased_line_width_range[1],
                       (pg->line_width / 8.0f) * pg->surface_scale_factor));
#else
    if (!anti_aliasing && pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER) &
                              NV_PGRAPH_SETUPRASTER_LINESMOOTHENABLE) {
        glEnable(GL_LINE_SMOOTH);
        set_line_width(MIN(r->supported_smooth_line_width_range[1],
                           (pg->line_width / 8.0f) * pg->surface_scale_factor));
    } else {
        glDisable(GL_LINE_SMOOTH);
        set_line_width(MIN(r->supported_aliased_line_width_range[1],
                           (pg->line_width / 8.0f) * pg->surface_scale_factor));
    }
    if (!anti_aliasing && pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER) &
                              NV_PGRAPH_SETUPRASTER_POLYSMOOTHENABLE) {
        glEnable(GL_POLYGON_SMOOTH);
    } else {
        glDisable(GL_POLYGON_SMOOTH);
    }
#endif

    unsigned int vp_width = pg->surface_binding_dim.width,
                 vp_height = pg->surface_binding_dim.height;
    pgraph_apply_scaling_factor(pg, &vp_width, &vp_height);
    glViewport(0, 0, vp_width, vp_height);

    /* Surface clip */
    /* FIXME: Consider moving to PSH w/ window clip */
    unsigned int xmin = pg->surface_shape.clip_x,
                 ymin = pg->surface_shape.clip_y;

    unsigned int scissor_width = pg->surface_shape.clip_width,
                 scissor_height = pg->surface_shape.clip_height;

    pgraph_apply_anti_aliasing_factor(pg, &xmin, &ymin);
    pgraph_apply_anti_aliasing_factor(pg, &scissor_width, &scissor_height);
    pgraph_apply_scaling_factor(pg, &xmin, &ymin);
    pgraph_apply_scaling_factor(pg, &scissor_width, &scissor_height);

    glEnable(GL_SCISSOR_TEST);
    glScissor(xmin, ymin, scissor_width, scissor_height);

    /* Visibility testing */
    bool zpass_query_enabled = pg->zpass_pixel_count_enable;
#ifdef __ANDROID__
    zpass_query_enabled = zpass_query_enabled &&
                          r->supported_extensions.occlusion_query_boolean;
#endif
    if (zpass_query_enabled) {
        r->gl_zpass_pixel_count_query_count++;
        r->gl_zpass_pixel_count_queries = (GLuint*)g_realloc(
            r->gl_zpass_pixel_count_queries,
            sizeof(GLuint) * r->gl_zpass_pixel_count_query_count);

        GLuint gl_query;
        glGenQueries(1, &gl_query);
        r->gl_zpass_pixel_count_queries[
            r->gl_zpass_pixel_count_query_count - 1] = gl_query;
        glBeginQuery(NV2A_GL_ZPASS_QUERY_TARGET, gl_query);
    }

    android_log_gl_errors("pgraph_gl_draw_begin");
}

void pgraph_gl_draw_end(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHGLState *r = pg->gl_renderer_state;

    uint32_t control_0 = pgraph_reg_r(pg, NV_PGRAPH_CONTROL_0);
    bool mask_alpha = control_0 & NV_PGRAPH_CONTROL_0_ALPHA_WRITE_ENABLE;
    bool mask_red = control_0 & NV_PGRAPH_CONTROL_0_RED_WRITE_ENABLE;
    bool mask_green = control_0 & NV_PGRAPH_CONTROL_0_GREEN_WRITE_ENABLE;
    bool mask_blue = control_0 & NV_PGRAPH_CONTROL_0_BLUE_WRITE_ENABLE;
    bool color_write = mask_alpha || mask_red || mask_green || mask_blue;
    bool depth_test = control_0 & NV_PGRAPH_CONTROL_0_ZENABLE;
    bool stencil_test =
        pgraph_reg_r(pg, NV_PGRAPH_CONTROL_1) & NV_PGRAPH_CONTROL_1_STENCIL_TEST_ENABLE;
    bool is_nop_draw = !(color_write || depth_test || stencil_test) ||
                       pgraph_draw_is_empty_line(pg);

    if (is_nop_draw) {
        // FIXME: Check PGRAPH register 0x880.
        // HW uses bit 11 in 0x880 to enable or disable a color/zeta limit
        // check that will raise an exception in the case that a draw should
        // modify the color and/or zeta buffer but the target(s) are masked
        // off. This check only seems to trigger during the fragment
        // processing, it is legal to attempt a draw that is entirely
        // clipped regardless of 0x880. See xemu#635 for context.
        NV2A_GL_DGROUP_END();
        return;
    }

    pgraph_gl_flush_draw(d);

    /* End of visibility testing */
    bool zpass_query_enabled = pg->zpass_pixel_count_enable;
#ifdef __ANDROID__
    zpass_query_enabled = zpass_query_enabled &&
                          r->supported_extensions.occlusion_query_boolean;
#endif
    if (zpass_query_enabled) {
        nv2a_profile_inc_counter(NV2A_PROF_QUERY);
        glEndQuery(NV2A_GL_ZPASS_QUERY_TARGET);
    }

    pg->draw_time++;
#ifdef __ANDROID__
#endif
    if (r->color_binding && pgraph_color_write_enabled(pg)) {
        r->color_binding->draw_time = pg->draw_time;
    }
    if (r->zeta_binding && pgraph_zeta_write_enabled(pg)) {
        r->zeta_binding->draw_time = pg->draw_time;
    }

    pgraph_gl_set_surface_dirty(pg, color_write, depth_test || stencil_test);
    NV2A_GL_DGROUP_END();
}

/* Whether gl/shaders.c attaches a geometry stage: always on desktop GL, and
 * on GLES only with GL_EXT/OES_geometry_shader (see generate_shaders()). */
static bool gl_geometry_stage_available(PGRAPHGLState *r)
{
#ifdef __ANDROID__
    return r->geometry_shaders_supported;
#else
    return true;
#endif
}

/*
 * The binding's mode, except that adjacency topology needs a geometry stage
 * to consume it.  Without one the rewrite is told `no_adjacency` and emits
 * plain triangles, so draw them as such.
 */
static GLenum gl_draw_mode(PGRAPHGLState *r)
{
    GLenum mode = r->shader_binding->gl_primitive_mode;
    if (mode == GL_TRIANGLES_ADJACENCY && !gl_geometry_stage_available(r)) {
        return GL_TRIANGLES;
    }
    return mode;
}

void pgraph_gl_flush_draw(NV2AState *d)
{
    PGRAPHState *pg = &d->pgraph;
    PGRAPHGLState *r = pg->gl_renderer_state;

    if (!(r->color_binding || r->zeta_binding)) {
        return;
    }

    PrimAssemblyState assembly = {
        .primitive_mode = pg->primitive_mode,
        .polygon_mode = (enum ShaderPolygonMode)GET_MASK(
            pgraph_reg_r(pg, NV_PGRAPH_SETUPRASTER),
            NV_PGRAPH_SETUPRASTER_FRONTFACEMODE),
        .last_provoking = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3),
                                   NV_PGRAPH_CONTROL_3_PROVOKING_VERTEX) ==
                          NV_PGRAPH_CONTROL_3_PROVOKING_VERTEX_LAST,
        .flat_shading = GET_MASK(pgraph_reg_r(pg, NV_PGRAPH_CONTROL_3),
                                 NV_PGRAPH_CONTROL_3_SHADEMODE) ==
                        NV_PGRAPH_CONTROL_3_SHADEMODE_FLAT,
        .no_adjacency = !gl_geometry_stage_available(r),
    };

    if (pg->draw_arrays_length) {
        NV2A_GL_DPRINTF(false, "Draw Arrays");
        nv2a_profile_inc_counter(NV2A_PROF_DRAW_ARRAYS);
        assert(pg->inline_elements_length == 0);
        assert(pg->inline_buffer_length == 0);
        assert(pg->inline_array_length == 0);

        pgraph_gl_bind_vertex_attributes(d, pg->draw_arrays_min_start,
                                      pg->draw_arrays_max_count - 1,
                                      false, 0,
                                      pg->draw_arrays_max_count - 1);
        pgraph_gl_bind_shaders(pg);

        PrimRewrite prim_rw = pgraph_prim_rewrite_ranges(
            &r->prim_rewrite_buf, assembly, pg->draw_arrays_start,
            pg->draw_arrays_count, pg->draw_arrays_length);

        if (prim_rw.num_indices > 0) {
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, r->gl_prim_rewrite_buffer);
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                         prim_rw.num_indices * sizeof(uint32_t),
                         prim_rw.indices, GL_STREAM_DRAW);
            glDrawElements(gl_draw_mode(r),
                           prim_rw.num_indices, GL_UNSIGNED_INT, (void *)0);
        } else {
            glMultiDrawArrays(gl_draw_mode(r),
                              pg->draw_arrays_start, pg->draw_arrays_count,
                              pg->draw_arrays_length);
        }
        android_log_gl_errors("pgraph_gl_flush_draw: draw_arrays");
    } else if (pg->inline_elements_length) {
        NV2A_GL_DPRINTF(false, "Inline Elements");
        nv2a_profile_inc_counter(NV2A_PROF_INLINE_ELEMENTS);
        assert(pg->inline_buffer_length == 0);
        assert(pg->inline_array_length == 0);

        uint32_t *draw_indices = pg->inline_elements;
        unsigned int draw_index_count = pg->inline_elements_length;
        PrimRewrite prim_rw = pgraph_prim_rewrite_indexed(
            &r->prim_rewrite_buf, assembly, pg->inline_elements,
            pg->inline_elements_length);
        if (prim_rw.num_indices > 0) {
            draw_indices = prim_rw.indices;
            draw_index_count = prim_rw.num_indices;
        }

        uint32_t min_element = (uint32_t)-1;
        uint32_t max_element = 0;
        for (unsigned int i = 0; i < draw_index_count; i++) {
            max_element = MAX(draw_indices[i], max_element);
            min_element = MIN(draw_indices[i], min_element);
        }

        pgraph_gl_bind_vertex_attributes(
                d, min_element, max_element, false, 0,
                draw_indices[draw_index_count - 1]);
        pgraph_gl_bind_shaders(pg);

        if (prim_rw.num_indices > 0) {
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, r->gl_prim_rewrite_buffer);
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                         draw_index_count * sizeof(uint32_t), draw_indices,
                         GL_STREAM_DRAW);
            glDrawElements(gl_draw_mode(r),
                           draw_index_count, GL_UNSIGNED_INT, (void *)0);
        } else {
            VertexKey k;
            memset(&k, 0, sizeof(VertexKey));
            k.count = pg->inline_elements_length;
            k.gl_type = GL_UNSIGNED_INT;
            k.gl_normalize = GL_FALSE;
            k.stride = sizeof(uint32_t);
            uint64_t h = fast_hash((uint8_t*)pg->inline_elements,
                                   pg->inline_elements_length * 4);

            LruNode *node = lru_lookup(&r->element_cache, h, &k);
            VertexLruNode *found = container_of(node, VertexLruNode, node);
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, found->gl_buffer);
            if (!found->initialized) {
                nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_4);
                glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                             pg->inline_elements_length * 4,
                             pg->inline_elements, GL_STATIC_DRAW);
                found->initialized = true;
            } else {
                nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_4_NOTDIRTY);
            }
            glDrawElements(gl_draw_mode(r),
                           pg->inline_elements_length, GL_UNSIGNED_INT,
                           (void *)0);
        }
        android_log_gl_errors("pgraph_gl_flush_draw: inline_elements");
    } else if (pg->inline_buffer_length) {
        NV2A_GL_DPRINTF(false, "Inline Buffer");
        nv2a_profile_inc_counter(NV2A_PROF_INLINE_BUFFERS);
        assert(pg->inline_array_length == 0);

        if (pg->compressed_attrs || pg->swizzle_attrs || pg->uniform_attrs) {
            pg->compressed_attrs = 0;
            pg->uniform_attrs = 0;
            pg->swizzle_attrs = 0;
        }
        pgraph_gl_bind_shaders(pg);

        for (int i = 0; i < NV2A_VERTEXSHADER_ATTRIBUTES; i++) {
            VertexAttribute *attr = &pg->vertex_attributes[i];
            if (attr->inline_buffer_populated) {
                nv2a_profile_inc_counter(NV2A_PROF_GEOM_BUFFER_UPDATE_3);
                glBindBuffer(GL_ARRAY_BUFFER, r->gl_inline_buffer[i]);
                glBufferData(GL_ARRAY_BUFFER,
                             pg->inline_buffer_length * sizeof(float) * 4,
                             attr->inline_buffer, GL_STREAM_DRAW);
                glVertexAttribPointer(i, 4, GL_FLOAT, GL_FALSE, 0, 0);
                glEnableVertexAttribArray(i);
                attr->inline_buffer_populated = false;
                memcpy(attr->inline_value,
                       attr->inline_buffer + (pg->inline_buffer_length - 1) * 4,
                       sizeof(attr->inline_value));
            } else {
                glDisableVertexAttribArray(i);
                glVertexAttrib4fv(i, attr->inline_value);
            }
        }

        PrimRewrite prim_rw = pgraph_prim_rewrite_sequential(
            &r->prim_rewrite_buf, assembly, 0, pg->inline_buffer_length);

        if (prim_rw.num_indices > 0) {
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, r->gl_prim_rewrite_buffer);
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                         prim_rw.num_indices * sizeof(uint32_t),
                         prim_rw.indices, GL_STREAM_DRAW);
            glDrawElements(gl_draw_mode(r),
                           prim_rw.num_indices, GL_UNSIGNED_INT, (void *)0);
        } else {
            glDrawArrays(gl_draw_mode(r),
                         0, pg->inline_buffer_length);
        }
        android_log_gl_errors("pgraph_gl_flush_draw: inline_buffer");
    } else if (pg->inline_array_length) {
        NV2A_GL_DPRINTF(false, "Inline Array");
        nv2a_profile_inc_counter(NV2A_PROF_INLINE_ARRAYS);

        unsigned int index_count = pgraph_gl_bind_inline_array(d);
        pgraph_gl_bind_shaders(pg);

        PrimRewrite prim_rw = pgraph_prim_rewrite_sequential(
            &r->prim_rewrite_buf, assembly, 0, index_count);

        if (prim_rw.num_indices > 0) {
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, r->gl_prim_rewrite_buffer);
            glBufferData(GL_ELEMENT_ARRAY_BUFFER,
                         prim_rw.num_indices * sizeof(uint32_t),
                         prim_rw.indices, GL_STREAM_DRAW);
            glDrawElements(gl_draw_mode(r),
                           prim_rw.num_indices, GL_UNSIGNED_INT, (void *)0);
        } else {
            glDrawArrays(gl_draw_mode(r),
                         0, index_count);
        }
        android_log_gl_errors("pgraph_gl_flush_draw: inline_array");
    } else {
        NV2A_GL_DPRINTF(true, "EMPTY NV097_SET_BEGIN_END");
        NV2A_UNCONFIRMED("EMPTY NV097_SET_BEGIN_END");
    }
}
