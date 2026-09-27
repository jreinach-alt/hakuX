#!/usr/bin/env python3
"""What the PFIFO thread's draw dispatch (SET_BEGIN_END) spends, from one capture.

    drawcost.py <perf.data> <tid> --ms-per-flip M [--top N]

The #474 ask (lane.flip474's [cblat], 2026-09-27): break the PFIFO thread's
SET_BEGIN_END time into vertex fetch and conversion, state and pipeline lookup,
uniforms, descriptors, the Vulkan driver, uploads and the lock.

A sample is "in draw dispatch" when its chain holds any ENTRY frame. The
handler itself is often missing: `--call-graph dwarf,8192` copies 8 KB of
stack, and a draw's chain runs deeper than that, so the unwinder stops inside
`flush_draw_one_pass` before it reaches the method handler. The ENTRY list is
therefore the functions only draw_end reaches (the flush and queue paths).

Each draw sample goes to one bucket: walking the chain from the draw entry
towards the leaf, the INNERMOST frame that names a bucket wins. So
`apply_uniform_updates -> memcpy_opt` is "uniforms", and a `tu_*` frame under
descriptor code is "vulkan driver".

cpu-clock samples are 1 ms each (-f 1000). In a `--trace-offcpu` capture the
sched_switch samples are charged the time to the thread's next switch-in (as
offcpu.py does) and printed as a separate off-CPU table; switch-outs the
sampler dropped cannot be placed and are counted as unsampled.

ms/frame = thread-ms / record span x ms per flip (the flip period is
profwin.py's, over the same window).
"""
import argparse
import bisect
import collections
import glob
import os
import subprocess

NDK = sorted(glob.glob(os.path.expanduser("~/Android/Sdk/ndk/*")))[-1]
SP = NDK + "/simpleperf/bin/linux/x86_64/simpleperf"

#
# The flush functions are not enough either: `flush_draw_one_pass` keeps a
# ~35 KB RenderCommandSnapshot on its stack (the #ifndef NDEBUG block, live on
# Android, which builds with -UNDEBUG), so a leaf a few frames under
# `begin_pre_draw_inner` or the uniform upload has its chain cut before the
# flush. The second group are functions only the draw path (and CLEAR_SURFACE,
# which [cblat] prices at 0.07 ms/frame) calls: create_pipeline,
# begin_pre_draw_inner and upload_draw_uniforms are the uniform upload's only
# callers (grep, 76cba82fd2).
ENTRY = ("pgraph_NV097_SET_BEGIN_END_handler", "pgraph_vk_draw_end", "pgraph_vk_draw_begin",
         "pgraph_vk_flush_draw", "flush_draw_one_pass", "flush_draw_queue_internal",
         "flush_reorder_window_internal", "pgraph_vk_flush_draw_queue",
         "begin_pre_draw_inner", "begin_pre_draw", "begin_draw", "pgraph_vk_bind_shaders",
         "pgraph_vk_update_shader_uniforms", "apply_uniform_updates", "upload_draw_uniforms",
         "pgraph_vk_snapshot_state", "sync_vertex_ram_buffer", "pgraph_vk_bind_vertex_attributes")

# (bucket, frame names or prefixes). Order does not matter: the innermost hit wins.
BUCKETS = [
    ("debug snapshot (NDEBUG undefined)", ["pgraph_vk_snapshot_state"]),
    ("uniforms: hash, compare, upload", ["pgraph_vk_update_shader_uniforms", "apply_uniform_updates",
                                         "pgraph_glsl_set_vsh_uniform_values",
                                         "pgraph_glsl_set_psh_uniform_values", "pgraph_glsl_vsh_fog_write",
                                         "fast_hash", "pgraph_vsh_writeback_constants"]),
    ("shader/pipeline lookup", ["pgraph_vk_bind_shaders", "pgraph_glsl_compare_shader_state",
                                "vsh_get_field", "pgraph_vk_create_pipeline", "create_pipeline",
                                "lookup_pipeline", "pipeline_cache", "shader_cache"]),
    ("pre-draw state (begin_pre_draw)", ["begin_pre_draw_inner", "begin_pre_draw"]),
    ("vertex: RAM sync, dirty pages", ["sync_vertex_ram_buffer", "has_dirty_vertex_pages",
                                       "vertex_range_gpu_stale", "tlb_reset_dirty",
                                       "tlb_reset_dirty_range_all", "physical_memory_test_and_clear_dirty",
                                       "cpu_physical_memory"]),
    ("vertex: attributes, remap, index rewrite", ["pgraph_vk_bind_vertex_attributes",
                                                  "remap_unaligned_attributes",
                                                  "copy_remapped_attributes_to_inline_buffer",
                                                  "rewrite_indices", "pgraph_prim_rewrite_ranges",
                                                  "pgraph_vk_append_to_buffer", "ensure_buffer_space",
                                                  "bind_vertex_buffer"]),
    ("surface update/dirty", ["pgraph_vk_surface_update", "pgraph_vk_set_surface_dirty",
                              "pgraph_vk_surface_watch_mark_dirty", "update_surface_part",
                              "prune_invalid_surfaces", "populate_surface_binding_target_sized",
                              "pgraph_vk_download_surface"]),
    ("textures", ["pgraph_vk_bind_textures", "pgraph_vk_poll_bound_textures", "texture_"]),
    ("descriptors", ["pgraph_vk_update_descriptor_sets", "bind_descriptor_sets"]),
    ("render pass / command buffer", ["begin_draw", "pgraph_vk_begin_render_pass", "begin_render_pass",
                                      "pgraph_vk_end_render_pass"]),
    ("finish / pending reports", ["pgraph_vk_finish", "pgraph_vk_process_pending_reports",
                                  "pgraph_vk_process_pending"]),
    ("vulkan driver (tu_*, vk_common_*)", ["tu_", "void tu_", "unsigned int tu_", "VkResult tu_",
                                           "vk_common_", "vk_cmd_"]),
    ("lock (mutex)", ["pthread_mutex_lock", "pthread_mutex_unlock", "qemu_mutex_lock_impl",
                      "qemu_mutex_unlock_impl", "qemu_rec_mutex_lock_impl", "qemu_rec_mutex_unlock_impl",
                      "NonPI::Mutex", "__aarch64_swp", "__aarch64_cas"]),
    ("logging (__android_log)", ["__android_log", "LogdWrite", "write_to_log"]),
]


def bucket_of(frame):
    for name, keys in BUCKETS:
        for k in keys:
            if frame == k or frame.startswith(k):
                return name
    return None


def classify(chain):
    """chain[0] is the leaf. Returns (in_draw, bucket, leaf-most unbucketed frame below the entry)."""
    ent = None
    for i, f in enumerate(chain):
        if f in ENTRY:
            ent = i  # keep going: the outermost entry
    if ent is None:
        return False, None, None
    for f in chain[:ent]:  # leaf first: the innermost bucketed frame wins
        b = bucket_of(f)
        if b:
            return True, b, None
    below = chain[ent - 1] if ent > 0 else chain[ent] + " (self)"
    return True, "other", below


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data")
    ap.add_argument("tid")
    ap.add_argument("--ms-per-flip", type=float, required=True)
    ap.add_argument("--top", type=int, default=12)
    ap.add_argument("--near", type=float, default=2.0)
    a = ap.parse_args()
    p = subprocess.Popen([SP, "report-sample", "--show-callchain", "-i", a.data],
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    on = collections.Counter()
    other_on = collections.Counter()
    rest = collections.Counter()
    leaf_on = collections.Counter()
    n_on = 0
    ons, outs, cs, oncs = [], [], [], []
    tmin = tmax = None
    kind, rec, chain = None, {}, []

    def flush():
        nonlocal n_on, tmin, tmax
        if not rec:
            return
        t = rec.get("time")
        if t is not None:
            tmin = t if tmin is None else min(tmin, t)
            tmax = t if tmax is None else max(tmax, t)
        if rec.get("tid") != a.tid:
            return
        if kind == "cs":
            cs.append((t, bool(rec.get("on"))))
            if rec.get("on"):
                ons.append(t)
        elif rec.get("ev", "cpu-clock") == "cpu-clock":
            n_on += 1
            oncs.append((t, list(chain)))
            ind, b, below = classify(chain)
            if not ind:
                if "pgraph_vk_surface_update" in chain:
                    # SET_BEGIN_END(begin) -> pgraph_vk_draw_begin tail-calls it, so its
                    # draw share has no draw frame; the flip and surface methods call it too
                    rest["surface_update, no draw frame (draw_begin's or another method's)"] += 1
                elif "pfifo_thread" not in chain:
                    rest["truncated: reaches neither a draw frame nor pfifo_thread"] += 1
                else:
                    rest["outside draw dispatch"] += 1
            if ind:
                on[b] += 1
                leaf_on[chain[0] if chain else "?"] += 1
                if below:
                    other_on[below] += 1
        elif rec.get("ev") == "sched:sched_switch":
            outs.append((t, list(chain)))

    for line in p.stdout:
        s = line.strip()
        if s in ("sample:", "context_switch:"):
            flush()
            kind = "sample" if s == "sample:" else "cs"
            rec, chain = {}, []
        elif s.startswith("switch_on:"):
            rec["on"] = s.endswith("true")
        elif s.startswith("time:"):
            rec["time"] = int(s.split(":", 1)[1])
        elif s.startswith("thread_id:"):
            rec["tid"] = s.split(":", 1)[1].strip()
        elif s.startswith("event_type:") and kind == "sample" and "ev" not in rec:
            rec["ev"] = s.split(":", 1)[1].strip()
        elif s.startswith("symbol:") and kind == "sample":
            chain.append(s.split(":", 1)[1].strip())
    flush()

    span = (tmax - tmin) / 1e6
    per = a.ms_per_flip / span  # thread-ms -> ms/frame
    tot = sum(on.values())
    print("%s tid %s: span %.0f ms = %.0f frames at %.1f ms/flip; on-CPU %d ms (%.1f ms/frame); "
          "in draw dispatch %d ms = %.1f%% of on-CPU = %.2f ms/frame" % (
              a.data, a.tid, span, span / a.ms_per_flip, a.ms_per_flip, n_on, n_on * per,
              tot, 100.0 * tot / max(n_on, 1), tot * per))
    print("on-CPU not in draw dispatch:")
    for k, v in rest.most_common():
        print("  %7d %5.1f%% of on-CPU %9.2f ms/frame  %s" % (v, 100.0 * v / max(n_on, 1), v * per, k))
    print("\non-CPU in draw dispatch, by bucket (innermost bucketed frame):")
    print("  %7s %6s %9s  %s" % ("ms", "draw%", "ms/frame", "bucket"))
    for b, k in on.most_common():
        print("  %7d %5.1f%% %9.2f  %s" % (k, 100.0 * k / max(tot, 1), k * per, b))
    if other_on:
        print("\n'other': the frame just below the draw entry")
        for f, k in other_on.most_common(a.top):
            print("  %7d %9.2f  %s" % (k, k * per, f))
    print("\nleaf symbols of the draw-dispatch samples")
    for f, k in leaf_on.most_common(a.top):
        print("  %7d %5.1f%% %9.2f  %s" % (k, 100.0 * k / max(tot, 1), k * per, f))

    if not cs:
        print("\nno context-switch records: on-CPU only")
        return
    cs.sort()
    ons.sort()
    oncs.sort(key=lambda x: x[0])
    stimes = [t for t, _ in outs]
    off = collections.Counter()
    off_total = 0.0
    for (t0, on0), (t1, _) in zip(cs, cs[1:]):
        if on0:
            continue
        dt = (t1 - t0) / 1e6
        off_total += dt
        i = bisect.bisect_right(stimes, t0) - 1
        if i >= 0 and t0 - stimes[i] <= 200000:
            ind, b, below = classify(outs[i][1])
            off[(b if ind else "not in draw dispatch") + ("" if not below else ": " + below)] += dt
        else:
            off["(unsampled switch-out)"] += dt
    print("\noff-CPU %.0f ms (%.1f ms/frame), each interval charged to its switch-out sample:" % (
        off_total, off_total * per))
    for k, v in off.most_common(a.top):
        print("  %8.0f ms %5.1f%% %9.2f ms/frame  %s" % (v, 100.0 * v / max(off_total, 1), v * per, k))

    # The unsampled intervals, charged instead to the thread's last cpu-clock
    # sample before the switch-out (within --near ms): what it was running when
    # it went off. The DOA GPU-wait reading used the same match (median 0.9 ms).
    near = a.near * 1e6
    otimes = [t for t, _ in oncs]
    by_last = collections.Counter()
    hist = collections.Counter()
    for (t0, on0), (t1, _) in zip(cs, cs[1:]):
        if on0:
            continue
        i = bisect.bisect_right(stimes, t0) - 1
        if i >= 0 and t0 - stimes[i] <= 200000:
            continue
        dt = (t1 - t0) / 1e6
        hist["<0.1" if dt < 0.1 else "<1" if dt < 1 else "<5" if dt < 5 else "<20" if dt < 20 else ">=20"] += dt
        j = bisect.bisect_right(otimes, t0) - 1
        if j < 0 or t0 - otimes[j] > near:
            by_last["(no on-CPU sample within %.0f ms)" % a.near] += dt
            continue
        ind, b, below = classify(oncs[j][1])
        by_last[(b if ind else "not in draw dispatch: " + " <- ".join(
            f for f in oncs[j][1][:3])) + ("" if not below else ": " + below)] += dt
    # The driver's GPU waits (Turnip/KGSL `wait_timestamp_safe`): their chain
    # stops in the vendor driver, so each is charged to the thread's last
    # on-CPU sample before it, by the emulator frames of that sample.
    drv = collections.Counter()
    drv_gap = []
    for (t0, on0), (t1, _) in zip(cs, cs[1:]):
        if on0:
            continue
        i = bisect.bisect_right(stimes, t0) - 1
        if not (i >= 0 and t0 - stimes[i] <= 200000):
            continue
        if not any(f.startswith("wait_timestamp_safe") for f in outs[i][1]):
            continue
        dt = (t1 - t0) / 1e6
        j = bisect.bisect_right(otimes, t0) - 1
        if j < 0 or t0 - otimes[j] > near:
            drv["(no on-CPU sample within %.0f ms)" % a.near] += dt
            continue
        drv_gap.append((t0 - otimes[j]) / 1e6)
        emu = [f for f in oncs[j][1] if not f.startswith(("*", "[", "__", "tu_", "void tu_", "VkResult tu_",
                                                           "unsigned int tu_", "vk_common", "kgsl",
                                                           "pthread", "memcpy", "memset", "@plt"))]
        drv[" <- ".join(emu[:4]) or "(no emulator frame)"] += dt
    if drv:
        tot_d = sum(drv.values())
        drv_gap.sort()
        print("\nsampled driver GPU waits %.0f ms (%.2f ms/frame); last on-CPU sample median %.2f ms before:" % (
            tot_d, tot_d * per, drv_gap[len(drv_gap) // 2] if drv_gap else float("nan")))
        for k, v in drv.most_common(a.top):
            print("  %8.0f ms %5.1f%% %9.2f ms/frame  %s" % (v, 100.0 * v / max(tot_d, 1), v * per, k))
    if by_last:
        u = sum(by_last.values())
        print("\nunsampled off-CPU %.0f ms (%.1f ms/frame), by interval length (ms): %s" % (
            u, u * per, ", ".join("%s %.0f" % (k, hist[k]) for k in ("<0.1", "<1", "<5", "<20", ">=20"))))
        print("charged to the last on-CPU sample within %.0f ms before the switch-out:" % a.near)
        for k, v in by_last.most_common(a.top):
            print("  %8.0f ms %5.1f%% %9.2f ms/frame  %s" % (v, 100.0 * v / max(u, 1), v * per, k))


if __name__ == "__main__":
    main()
