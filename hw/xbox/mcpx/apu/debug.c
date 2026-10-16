/*
 * QEMU MCPX Audio Processing Unit implementation
 *
 * Copyright (c) 2012 espes
 * Copyright (c) 2018-2019 Jannik Vogel
 * Copyright (c) 2019-2025 Matt Borgerson
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

#include "apu_int.h"

struct McpxApuDebug g_dbg, g_dbg_cache;
int g_dbg_voice_monitor = -1;
uint64_t g_dbg_muted_voices[4];

const struct McpxApuDebug *mcpx_apu_get_debug_info(void)
{
    return &g_dbg_cache;
}

void mcpx_debug_begin_frame(void)
{
    for (int i = 0; i < MCPX_HW_MAX_VOICES; i++) {
        g_dbg.vp.v[i].active = false;
        g_dbg.vp.v[i].multipass_dst_voice = 0xFFFF;
    }
}

/*
 * HAKUX_APU_MIXLOG=1 (#984, #938; off by default): every 7500 APU frames
 * (5 s of 48 kHz audio), one line per voice that was active and unpaused in
 * that window, under logcat tag hakuX-audio with the prefix "apumix":
 *
 *   apumix w=<window> v=<voice> n=<frames active> st=<stereo> mp=<multipass>
 *          bins=<bin>:<vol>,... (the voice's eight slots in order, vol in
 *          1/64 dB units of attenuation, 4095 = off; as last seen)
 *
 * The volumes are what vp.c read. MON_VP plays the voice at the smallest
 * of these attenuations; docs/lanes/audio1016/tools/mixlog_read.py adds the
 * per-side gains HAKUX_APU_MONVP_DOWNMIX would give. Nothing here is per
 * sample, so the cost when on is one pass over 256 voices a frame.
 */
#ifdef __ANDROID__
extern int __android_log_print(int prio, const char *tag, const char *fmt, ...);
#endif

#define MIXLOG_WINDOW_FRAMES 7500
static int mixlog_on = -1;
static uint32_t mixlog_frames[MCPX_HW_MAX_VOICES];
static struct McpxApuDebugVoice mixlog_last[MCPX_HW_MAX_VOICES];
static uint32_t mixlog_window_frames;
static uint32_t mixlog_window;

static void mixlog_frame(void)
{
    if (mixlog_on < 0) {
        const char *e = getenv("HAKUX_APU_MIXLOG");
        mixlog_on = e && e[0] == '1' && e[1] == '\0';
    }
    if (!mixlog_on) {
        return;
    }
    for (int i = 0; i < MCPX_HW_MAX_VOICES; i++) {
        if (g_dbg.vp.v[i].active && !g_dbg.vp.v[i].paused) {
            mixlog_frames[i]++;
            mixlog_last[i] = g_dbg.vp.v[i];
        }
    }
    if (++mixlog_window_frames < MIXLOG_WINDOW_FRAMES) {
        return;
    }
    for (int i = 0; i < MCPX_HW_MAX_VOICES; i++) {
        if (!mixlog_frames[i]) {
            continue;
        }
        const struct McpxApuDebugVoice *v = &mixlog_last[i];
        char bins[8 * 12];
        int len = 0;
        for (int b = 0; b < 8; b++) {
            len += snprintf(bins + len, sizeof(bins) - len, "%s%u:%u",
                            b ? "," : "", v->bin[b], v->vol[b] & 0xFFF);
        }
#ifdef __ANDROID__
        __android_log_print(4, "hakuX-audio",
                            "apumix w=%u v=%d n=%u st=%d mp=%d bins=%s",
                            mixlog_window, i, mixlog_frames[i], v->stereo,
                            v->multipass, bins);
#else
        fprintf(stderr, "apumix w=%u v=%d n=%u st=%d mp=%d bins=%s\n",
                mixlog_window, i, mixlog_frames[i], v->stereo, v->multipass,
                bins);
#endif
        mixlog_frames[i] = 0;
    }
    mixlog_window_frames = 0;
    mixlog_window++;
}

void mcpx_debug_end_frame(void)
{
    mixlog_frame();
    g_dbg_cache = g_dbg;
}

void mcpx_apu_debug_set_gp_realtime_enabled(bool run)
{
    g_state->gp.realtime = run;
}

void mcpx_apu_debug_set_ep_realtime_enabled(bool run)
{
    g_state->ep.realtime = run;
}

McpxApuDebugMonitorPoint mcpx_apu_debug_get_monitor(void)
{
    return g_state->monitor.point;
}

void mcpx_apu_debug_set_monitor(McpxApuDebugMonitorPoint monitor)
{
    g_state->monitor.point = monitor;
}

void mcpx_apu_debug_isolate_voice(uint16_t v)
{
    g_dbg_voice_monitor = v;
}

void mcpx_apu_debug_clear_isolations(void)
{
    g_dbg_voice_monitor = -1;
}

bool mcpx_apu_debug_is_muted(uint16_t v)
{
    assert(v < MCPX_HW_MAX_VOICES);
    return g_dbg_muted_voices[v / 64] & (1LL << (v % 64));
}

void mcpx_apu_debug_toggle_mute(uint16_t v)
{
    assert(v < MCPX_HW_MAX_VOICES);
    g_dbg_muted_voices[v / 64] ^= (1LL << (v % 64));
}
