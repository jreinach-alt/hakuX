#!/usr/bin/env python3
"""Write hooks-g9.diff (system/memory.c: the vCPU's time in MMIO dispatch)
and scratch_g9/memory.c, the patched file, for a type-check:

    make_hooks_g9.py
    cp system/memory-internal.h system/trace.h docs/lanes/frametrace/scratch_g9/
    typecheck.py <wt> docs/lanes/frametrace/scratch_g9/memory.c=system/memory.c

(memory.c includes both headers from its own directory.) scratch_g9/ is not
committed; the patch is the product."""
import difflib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
src = open(os.path.join(WT, 'system', 'memory.c')).read()
s = src


def rep(old, new):
    global s
    assert s.count(old) == 1, old
    s = s.replace(old, new)


rep('#include "memory-internal.h"\n',
    '#include "memory-internal.h"\n'
    '#ifdef XBOX\n'
    '#include "hw/xbox/nv2a/pgraph/profile.h"   /* #433 frametrace G9 */\n'
    '#endif\n')

rep('''    r = memory_region_dispatch_read1(mr, addr, pval, size, attrs);
    adjust_endianness(mr, pval, op);
    return r;''', '''#ifdef XBOX
    {
        /* #433 frametrace (G9): the vCPU's time in MMIO dispatch; off, one
         * load and a branch. */
        HakuxFtMmio ftm;
        hakux_ft_mmio_begin(&ftm);
        r = memory_region_dispatch_read1(mr, addr, pval, size, attrs);
        hakux_ft_mmio_end(&ftm, mr, mr->name);
    }
#else
    r = memory_region_dispatch_read1(mr, addr, pval, size, attrs);
#endif
    adjust_endianness(mr, pval, op);
    return r;''')

W_OLD = '''    if (mr->ops->write) {
        return access_with_adjusted_size(addr, &data, size,
                                         mr->ops->impl.min_access_size,
                                         mr->ops->impl.max_access_size,
                                         memory_region_write_accessor, mr,
                                         attrs);
    } else {
        return
            access_with_adjusted_size(addr, &data, size,
                                      mr->ops->impl.min_access_size,
                                      mr->ops->impl.max_access_size,
                                      memory_region_write_with_attrs_accessor,
                                      mr, attrs);
    }
}'''
W_NEW = '''#ifdef XBOX
    {
        /* #433 frametrace (G9): the vCPU's time in MMIO dispatch. */
        HakuxFtMmio ftm;
        MemTxResult r;

        hakux_ft_mmio_begin(&ftm);
        if (mr->ops->write) {
            r = access_with_adjusted_size(addr, &data, size,
                                          mr->ops->impl.min_access_size,
                                          mr->ops->impl.max_access_size,
                                          memory_region_write_accessor, mr,
                                          attrs);
        } else {
            r = access_with_adjusted_size(addr, &data, size,
                                          mr->ops->impl.min_access_size,
                                          mr->ops->impl.max_access_size,
                                          memory_region_write_with_attrs_accessor,
                                          mr, attrs);
        }
        hakux_ft_mmio_end(&ftm, mr, mr->name);
        return r;
    }
#else
''' + W_OLD[:-2] + '''
#endif
}'''
rep(W_OLD, W_NEW)

os.makedirs(os.path.join(HERE, 'scratch_g9'), exist_ok=True)
open(os.path.join(HERE, 'scratch_g9', 'memory.c'), 'w').write(s)
d = difflib.unified_diff(src.splitlines(True), s.splitlines(True),
                         'a/system/memory.c', 'b/system/memory.c')
open(os.path.join(HERE, 'hooks-g9.diff'), 'w').writelines(d)
print('ok')
