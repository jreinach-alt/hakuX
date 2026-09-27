#!/usr/bin/env python3
"""Write one stage of the #488 change into the worktree from the final
pgraph.c (docs/lanes/notify488/.final.c): `counter`, `notify` or `final`.
Used once to build the lane's three commits so each arm ref is one change."""
import subprocess
import sys

WT = subprocess.check_output(['git', 'rev-parse', '--show-toplevel'],
                             text=True).strip()
FINAL = open(WT + '/docs/lanes/notify488/.final.c').read()
BASE = subprocess.check_output(
    ['git', 'show', '5d0cbfeae65d:hw/xbox/nv2a/pgraph/pgraph.c'], text=True)
stage = sys.argv[1]

SEM_OLD = '''#ifdef CONFIG_VULKAN
    if (tcg_enabled() &&
        pg->renderer->type == CONFIG_DISPLAY_RENDERER_VULKAN) {
        pgraph_vk_flush_reorder_window(d);
        pgraph_vk_flush_draw_queue(d);
    } else
#endif
    {
        d->pgraph.renderer->ops.surface_update(d, false, true, true);
    }
'''
SEM_BASE = '    d->pgraph.renderer->ops.surface_update(d, false, true, true);\n'


def strip_sem(s):
    start = s.index('/*\n * #488: the release used to download')
    end = s.index('DEF_METHOD(NV097, BACK_END_WRITE_SEMAPHORE_RELEASE)\n{\n')
    s = s[:start] + s[end:]
    assert s.count(SEM_OLD) == 1
    s = s.replace(SEM_OLD, SEM_BASE)
    return s.replace('#include "system/tcg.h"\n', '', 1)


def strip_notify(s):
    start = s.index('/*\n * #488: NOTIFY writes a 16-byte notification')
    end = s.index('DEF_METHOD(NV097, WAIT_FOR_IDLE)')
    return s[:start] + s[end:]


if stage == 'final':
    out = FINAL
elif stage == 'notify':
    out = strip_sem(FINAL)
elif stage == 'counter':
    out = strip_notify(strip_sem(FINAL))
else:
    sys.exit('stage?')
open(WT + '/hw/xbox/nv2a/pgraph/pgraph.c', 'w').write(out)
