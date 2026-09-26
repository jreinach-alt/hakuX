/*
 * Stand-in for ui/xemu-settings.h.
 *
 * psh.c reads g_config.display.renderer in three places, all of them inside
 * pgraph_glsl_set_psh_state, which carve.py removes. The declaration is here
 * so the include resolves; the definition lives in the differ, defaulting to
 * the renderer the run is generating for.
 */

#ifndef PSH_DIFFER_XEMU_SETTINGS_H
#define PSH_DIFFER_XEMU_SETTINGS_H

#include "qemu/osdep.h"

enum {
    CONFIG_DISPLAY_RENDERER_NULL,
    CONFIG_DISPLAY_RENDERER_OPENGL,
    CONFIG_DISPLAY_RENDERER_VULKAN,
};

typedef struct {
    struct {
        int renderer;
    } display;
} PshDifferConfig;

extern PshDifferConfig g_config;

#endif
