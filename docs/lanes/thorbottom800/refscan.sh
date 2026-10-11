#!/bin/bash
# For each ref: does it carry the 640x480 shrink, the drawable-sized Android
# blit, and which default startup size?  Reading only, no build.
for r in "$@"; do
  echo "== $r $(git log -1 --format='%h %ad %s' --date=short "$r" | cut -c1-90)"
  git show "$r:ui/xemu.c" | grep -n "disp_mode.w < window_width\|SDL_GL_GetDrawableSize(m_window\|SDL_SetWindowSize(m_window"
  git show "$r:config_spec.yml" | grep -A3 "startup_size:" | grep default
done
