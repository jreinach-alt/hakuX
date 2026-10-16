#!/usr/bin/env python3
"""Classify long frames in a hakuX logcat by what else happened in their window.

Each `hakuX-pace` line closes a 60-flip window and carries `max=` (the
window's longest frame, ms). For every window whose longest frame is at
least --min ms, this prints the window's pipeline and shader compile
counters, storage latency and audio starvation, so a stall can be named by
the one that rises with it.

Columns (all over the window):
  win_s      window length, s; max_ms its longest frame
  dpm        pipeline misses created inline (sync) on the recording thread
  kd         sync draw misses by key class, summed ([shd413] kd=)
  dpn/dpc_ms graphics pipeline creates and the wall ms inside them, sync,
             worker and clear alike ([shd413]); dsm shader module misses
  mod_ms     GLSL -> shader module ms ([shd413] dsmod_ms)
  gpl_new    new pipeline-library parts ([gpl569] new=, delta of the 4 parts)
  gpl_ms     library compile ms ([gpl569] lib_ms=, delta of the 4 parts)
  ub_cold    ubershader cold links ([uber569] cold=, delta)
  ub_ms      ubershader library ms ([uber569] lib_ms=, delta)
  ub_next_ms ubershader background specialisation ms ([uber569] next_ms=, delta)
  plc_ms     pipeline cache saves ([plc569] ms=)
  ide_dev_ms longest single IDE device operation ([ide425d] dev_us_max)
  starve     audio output zero-filled, % ([hakuX-audiocap] starve, max)
  tq, ri     the window's gfps line

Usage: stallscan.py LOGCAT [--min MS]
"""
import argparse
import re

LINE = re.compile(r'^\d\d-\d\d (\d\d:\d\d:\d\d\.\d+)\s+\w/([\w-]+)\s*\(\s*\d+\):\s*(.*)$')
KV = re.compile(r'(\w+)=(-?\d+(?:\.\d+)?)(?![\d.])')
COLS = ('dpm', 'kd', 'dpn', 'dpc_ms', 'dsm', 'mod_ms', 'gpl_new', 'gpl_ms', 'ub_cold', 'ub_ms',
        'ub_next_ms', 'plc_ms', 'ide_dev_ms', 'starve', 'tq', 'ri')


def kv(text):
    return {k: float(v) for k, v in KV.findall(text)}


def secs(t):
    h, m, s = t.split(':')
    return int(h) * 3600 + int(m) * 60 + float(s)


def slash_sum(msg, key):
    m = re.search(r'\b%s=([\d./]+)' % key, msg)
    return sum(float(x) for x in m.group(1).split('/')) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('logcat')
    ap.add_argument('--min', type=float, default=300.0)
    a = ap.parse_args()

    print(' '.join('%10s' % h for h in ('end', 'win_s', 'max_ms') + COLS))

    def reset():
        w = dict.fromkeys(COLS, 0.0)
        w['tq'] = w['ri'] = float('nan')
        return w

    def emit(w):
        if w and w['_max'] >= a.min:
            row = [w['_t'][:8], '%.1f' % w['_ws'], '%.0f' % w['_max']] + ['%.0f' % w[k] for k in COLS]
            print(' '.join('%10s' % x for x in row))

    # Running totals of the cumulative counters; a window gets their deltas.
    last = {}

    def delta(key, value, w, col):
        if value is None:
            return
        if key in last:
            w[col] += value - last[key]
        last[key] = value

    win = reset()
    pending = None
    for line in open(a.logcat, errors='replace'):
        m = LINE.match(line)
        if not m:
            continue
        t, tag, msg = m.groups()
        if msg.startswith('[gpl569] mode='):
            delta('gpl_new', slash_sum(msg, 'new'), win, 'gpl_new')
            delta('gpl_ms', slash_sum(msg, 'lib_ms'), win, 'gpl_ms')
        elif msg.startswith('[uber569] mode='):
            d = kv(msg)
            delta('ub_cold', d.get('cold'), win, 'ub_cold')
            delta('ub_ms', d.get('lib_ms'), win, 'ub_ms')
            delta('ub_next_ms', d.get('next_ms'), win, 'ub_next_ms')
        elif msg.startswith('[plc569]'):
            win['plc_ms'] += kv(msg).get('ms', 0.0)
        elif msg.startswith('[shd413]'):
            # Logged right after the pace line of the window it counts.
            d = kv(msg)
            dst = pending if pending and secs(t) - secs(pending['_t']) < 0.5 else win
            dst['dpm'] += d.get('dpm', 0.0)
            dst['kd'] += slash_sum(msg, 'kd') or 0.0
            dst['dpn'] += d.get('dpn', 0.0)
            dst['dpc_ms'] += d.get('dpc_ms', 0.0)
            dst['dsm'] += d.get('dsm', 0.0)
            dst['mod_ms'] += d.get('dsmod_ms', 0.0)
        elif msg.startswith('[ide425d]'):
            win['ide_dev_ms'] = max(win['ide_dev_ms'], kv(msg).get('dev_us_max', 0.0) / 1000)
        elif tag == 'hakuX-audiocap' and msg.startswith('starve'):
            s = re.search(r'= ([\d.]+)% of output', msg)
            if s:
                win['starve'] = max(win['starve'], float(s.group(1)))
        elif msg.startswith('gfps='):
            tq = re.search(r'Tq:([\d.]+)', msg)
            ri = re.search(r'Ri:([\d.]+)', msg)
            win['tq'] = float(tq.group(1)) if tq else float('nan')
            win['ri'] = float(ri.group(1)) if ri else float('nan')
        elif tag == 'hakuX-pace' and msg.startswith('f='):
            d = kv(msg)
            emit(pending)
            win.update(_t=t, _max=d.get('max', 0.0), _ws=d.get('ms', 0.0) / 1000)
            pending = win
            win = reset()
    emit(pending)


if __name__ == '__main__':
    main()
