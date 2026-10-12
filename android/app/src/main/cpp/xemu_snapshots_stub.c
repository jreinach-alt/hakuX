/*
 * Stand-ins for ui/xemu-thumbnail.cc, which the Android build leaves out:
 * it renders snapshot thumbnails with desktop GL. ui/xemu-snapshots.c itself
 * is built (#433); on Android it writes and reads no thumbnail.
 */
#include "ui/xemu-snapshots.h"

void xemu_snapshots_set_framebuffer_texture(GLuint tex, bool flip)
{
    (void)tex;
    (void)flip;
}

bool xemu_snapshots_load_png_to_texture(GLuint tex, void *buf, size_t size)
{
    (void)tex;
    (void)buf;
    (void)size;
    return false;
}

void *xemu_snapshots_create_framebuffer_thumbnail_png(size_t *size)
{
    if (size) {
        *size = 0;
    }
    return NULL;
}
