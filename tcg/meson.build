if not have_tcg
   subdir_done()
endif

tcg_ss = ss.source_set()

tcg_ss.add(files(
  # Fork addition. The Android build globs sources (CMakeLists.txt
  # file(GLOB_RECURSE)), so new files compile there automatically and
  # were never listed here - the meson build referenced their symbols
  # and never built them.
  'tier1-opt.c',
  'optimize.c',
  'region.c',
  'tcg.c',
  'tcg-common.c',
  'tcg-op.c',
  'tcg-op-ldst.c',
  'tcg-op-gvec.c',
  'tcg-op-vec.c',
  'tcg-op-fp.c',
))

if get_option('tcg_interpreter')
  libffi = dependency('libffi', version: '>=3.0', required: true,
                      method: 'pkg-config')
  tcg_ss.add(libffi)
  tcg_ss.add(files('tci.c'))
endif

tcg_ss.add(when: libdw, if_true: files('debuginfo.c'))
if host_os == 'linux'
  tcg_ss.add(files('perf.c'))
endif

user_ss.add_all(tcg_ss)
system_ss.add_all(tcg_ss)
