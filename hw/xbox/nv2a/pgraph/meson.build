specific_ss.add(files(
	'prim_rewrite.c',
	'pgraph.c',
	'profile.c',
	'rdi.c',
	's3tc.c',
	'swizzle.c',
	'texture.c',
	'vertex.c',
	))
if have_renderdoc
	specific_ss.add(files('debug_renderdoc.c'))
endif
subdir('thirdparty')
subdir('null')
subdir('gl')
subdir('glsl')
subdir('vk')
specific_ss.add(nv2a_vsh_cpu)
# pgraph.h includes nv2a_vsh_emulator.h, so anything including pgraph.h
# needs this dependency's include directory - including ui/xemu.c, which
# is built into the target-agnostic system sourceset.
system_ss.add(nv2a_vsh_cpu)
