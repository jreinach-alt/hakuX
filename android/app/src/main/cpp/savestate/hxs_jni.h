/*
 * The frontend's side of save states (#433). xemu_android.cpp reads the
 * preferences and hands them over here before the machine is built.
 */
#ifndef HAKUX_SAVESTATE_HXS_JNI_H
#define HAKUX_SAVESTATE_HXS_JNI_H

#include <jni.h>
#include <stdbool.h>
#include <stdint.h>

/*
 * base_dir: the app's external files folder (x1box); the default root is
 * <base_dir>/states. tree_uri: a folder picked through the Storage Access
 * Framework, or empty for the default. title_id: the disc's title, 0 if
 * unknown.
 */
void hxs_android_configure(JNIEnv *env, jobject activity, const char *base_dir,
                           const char *tree_uri, bool compression,
                           bool auto_load, uint32_t title_id);

#endif
