#!/bin/bash
# Step 0 search for lane.bootstatic1017: commit-message and pickaxe searches for every mechanism
# the lane may touch. Output: one section per query, "<sha> <date> <subject>".
# Usage: step0_search.sh <repo> > out.txt
R=${1:-/home/justin/hakux-work/wt/bootstatic1017}
P="hw/xbox ui android"

grep_q() {
  echo "=== --grep -i '$1' (--all)"
  git -C "$R" log --all -i --grep="$1" --format='%h %ad %s' --date=short | head -60
}
pick_q() {
  echo "=== -S '$1' (--all, -- $P)"
  git -C "$R" log --all -S"$1" --format='%h %ad %s' --date=short -- $P | head -60
}

# commit messages: the looks and the moment
for q in 'garbage' 'static' 'green' 'flash' 'noise' 'uninitiali' 'first frame' 'first present' \
         'black screen' 'boot anim' 'skip.*boot' 'splash' 'flicker' 'corrupt' 'stale frame' \
         'swapchain' 'present' 'display texture' 'clear.*display' 'video mode' 'pcrtc' 'start address' \
         'pvideo' 'overlay' 'yuv' 'SDLSurface' 'surfaceCreated' 'surfaceChanged' 'eglSwap' \
         'title start' 'launch' 'startup' 'boot'; do
  grep_q "$q"
done

# pickaxe: code that does or touches each mechanism
for s in 'NV_PCRTC_START' 'pcrtc_start' 'NV_PRAMDAC_GENERAL_CONTROL' 'vga_framebuffer' \
         'display.image' 'display.draw_time' 'pgraph_vk_render_display' 'render_display' \
         'VK_IMAGE_LAYOUT_UNDEFINED' 'vkCmdClearColorImage' 'glClear' 'xemu_hud' \
         'SDL_GL_SwapWindow' 'eglSwapBuffers' 'surfaceCreated' 'surfaceChanged' 'setZOrderOnTop' \
         'pvideo' 'NV_PVIDEO' 'boot_anim' 'skip_boot_anim' 'fast boot' 'display_ready' \
         'first_frame' 'frame_count' 'tex_id' 'nv2a_get_framebuffer_surface'; do
  pick_q "$s"
done
