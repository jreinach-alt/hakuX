/*
 * The frontend's side of save states (#433): the folder, the settings, and
 * the calls the pause menu, the quit path and the auto-load toast make.
 *
 * A folder picked through the Storage Access Framework is reached through
 * com.rfandango.haku_x.SaveStateStore, which hands back file descriptors.
 * Its calls come from the save state threads, which SDL attaches to the VM.
 */
#include "savestate/hxs_jni.h"

#include <android/log.h>
#include <SDL_system.h>

#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "savestate/hxs.h"

#define HXS_JLOG(...) \
    __android_log_print(ANDROID_LOG_INFO, "hakuX-lane", __VA_ARGS__)

namespace {

jclass g_store_cls;
jobject g_ctx;
jstring g_tree;
jmethodID m_open, m_rename, m_unlink, m_mkdir, m_list;

JNIEnv *Env()
{
    return static_cast<JNIEnv *>(SDL_AndroidGetJNIEnv());
}

bool Failed(JNIEnv *env, const char *what)
{
    if (!env->ExceptionCheck()) {
        return false;
    }
    env->ExceptionDescribe();
    env->ExceptionClear();
    HXS_JLOG("[savestate] store %s threw", what);
    return true;
}

int StoreOpen(const char *rel, bool write)
{
    JNIEnv *env = Env();
    if (!env || env->PushLocalFrame(8) < 0) {
        return -EIO;
    }
    jstring jrel = env->NewStringUTF(rel);
    jint fd = env->CallStaticIntMethod(g_store_cls, m_open, g_ctx, g_tree,
                                       jrel, (jboolean)write);
    if (Failed(env, "open")) {
        fd = -EIO;
    }
    env->PopLocalFrame(nullptr);
    return fd;
}

int StoreTwo(jmethodID m, const char *what, const char *a, const char *b)
{
    JNIEnv *env = Env();
    if (!env || env->PushLocalFrame(8) < 0) {
        return -EIO;
    }
    jstring ja = env->NewStringUTF(a);
    jint r;
    if (b) {
        jstring jb = env->NewStringUTF(b);
        r = env->CallStaticIntMethod(g_store_cls, m, g_ctx, g_tree, ja, jb);
    } else {
        r = env->CallStaticIntMethod(g_store_cls, m, g_ctx, g_tree, ja);
    }
    if (Failed(env, what)) {
        r = -EIO;
    }
    env->PopLocalFrame(nullptr);
    return r;
}

int StoreRename(const char *from, const char *to)
{
    return StoreTwo(m_rename, "rename", from, to);
}

int StoreUnlink(const char *rel)
{
    return StoreTwo(m_unlink, "unlink", rel, nullptr);
}

int StoreMkdir(const char *rel)
{
    return StoreTwo(m_mkdir, "mkdir", rel, nullptr);
}

char *StoreList(const char *rel)
{
    JNIEnv *env = Env();
    if (!env || env->PushLocalFrame(8) < 0) {
        return nullptr;
    }
    jstring jrel = env->NewStringUTF(rel);
    auto s = static_cast<jstring>(
        env->CallStaticObjectMethod(g_store_cls, m_list, g_ctx, g_tree, jrel));
    char *out = nullptr;
    if (!Failed(env, "list") && s) {
        const char *utf = env->GetStringUTFChars(s, nullptr);
        if (utf) {
            out = strdup(utf);
            env->ReleaseStringUTFChars(s, utf);
        }
    }
    env->PopLocalFrame(nullptr);
    return out;
}

/* Binds SaveStateStore through the app's class loader. */
bool BindStore(JNIEnv *env, jobject activity, const char *tree_uri)
{
    jclass act = env->GetObjectClass(activity);
    jmethodID get_cl =
        env->GetMethodID(act, "getClassLoader", "()Ljava/lang/ClassLoader;");
    jmethodID get_app = env->GetMethodID(act, "getApplicationContext",
                                         "()Landroid/content/Context;");
    jobject loader = env->CallObjectMethod(activity, get_cl);
    jobject app = env->CallObjectMethod(activity, get_app);
    if (Failed(env, "bind") || !loader || !app) {
        return false;
    }
    jclass cl_cls = env->FindClass("java/lang/ClassLoader");
    jmethodID load = env->GetMethodID(cl_cls, "loadClass",
                                      "(Ljava/lang/String;)Ljava/lang/Class;");
    jstring name = env->NewStringUTF("com.rfandango.haku_x.SaveStateStore");
    auto cls = static_cast<jclass>(env->CallObjectMethod(loader, load, name));
    env->DeleteLocalRef(name);
    if (Failed(env, "loadClass") || !cls) {
        return false;
    }
    const char *ctx = "(Landroid/content/Context;Ljava/lang/String;";
    std::string s_open = std::string(ctx) + "Ljava/lang/String;Z)I";
    std::string s_two = std::string(ctx) + "Ljava/lang/String;Ljava/lang/String;)I";
    std::string s_one = std::string(ctx) + "Ljava/lang/String;)I";
    std::string s_list = std::string(ctx) + "Ljava/lang/String;)Ljava/lang/String;";
    m_open = env->GetStaticMethodID(cls, "open", s_open.c_str());
    m_rename = env->GetStaticMethodID(cls, "rename", s_two.c_str());
    m_unlink = env->GetStaticMethodID(cls, "unlink", s_one.c_str());
    m_mkdir = env->GetStaticMethodID(cls, "mkdir", s_one.c_str());
    m_list = env->GetStaticMethodID(cls, "list", s_list.c_str());
    if (Failed(env, "methods") || !m_open || !m_rename || !m_unlink ||
        !m_mkdir || !m_list) {
        return false;
    }
    g_store_cls = static_cast<jclass>(env->NewGlobalRef(cls));
    g_ctx = env->NewGlobalRef(app);
    jstring tree = env->NewStringUTF(tree_uri);
    g_tree = static_cast<jstring>(env->NewGlobalRef(tree));
    env->DeleteLocalRef(tree);
    env->DeleteLocalRef(cls);
    env->DeleteLocalRef(loader);
    env->DeleteLocalRef(app);
    return true;
}

const char *CodecName(int c)
{
    switch (c) {
    case HXS_CODEC_NONE:
        return "none";
    case HXS_CODEC_LZ4:
        return "lz4";
    case HXS_CODEC_ZSTD:
        return "zstd";
    default:
        return "-";
    }
}

/* key=value fields separated by tabs, for the Kotlin side. */
jstring Result(JNIEnv *env, const HxsStats &st)
{
    char buf[512];
    std::string err = st.error;
    for (char &c : err) {
        if (c == '\t' || c == '\n') {
            c = ' ';
        }
    }
    snprintf(buf, sizeof(buf),
             "ok=%d\treason=%s\tslot=%d\tpause_ms=%.0f\ttotal_ms=%.0f\t"
             "changed=%d\tcodec=%s\tbytes=%llu\terror=%s",
             st.ok, st.reason, st.slot, st.pause_us / 1000.0,
             st.total_us / 1000.0, st.goto_us > 0,
             CodecName(st.ok && st.file_codec < 0 ? st.codec : st.file_codec),
             (unsigned long long)st.file_bytes, err.c_str());
    return env->NewStringUTF(buf);
}

}  // namespace

void hxs_android_configure(JNIEnv *env, jobject activity, const char *base_dir,
                           const char *tree_uri, bool compression,
                           bool auto_load, uint32_t title_id)
{
    bool saf = false;
    if (tree_uri && *tree_uri) {
        saf = BindStore(env, activity, tree_uri);
        if (saf) {
            static const HxsStoreOps ops = { StoreOpen, StoreRename,
                                             StoreUnlink, StoreMkdir,
                                             StoreList };
            hxs_set_store(&ops, tree_uri);
        } else {
            HXS_JLOG("[savestate] folder %s unusable; using the default",
                     tree_uri);
        }
    }
    if (!saf) {
        std::string root = std::string(base_dir) + "/states";
        hxs_set_root(root.c_str());
    }
    hxs_set_compression(compression);
    hxs_set_auto_load(auto_load);
    if (title_id) {
        char t[9];
        snprintf(t, sizeof(t), "%08x", title_id);
        hxs_set_boot_title(t);
    }
    HXS_JLOG("[savestate] configure root=%s saf=%d compression=%d "
             "auto_load=%d title=%08x",
             hxs_root_label(), saf, compression, auto_load, title_id);
}

extern "C" {

JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateSave(JNIEnv *env,
                                                            jobject,
                                                            jint slot)
{
    HxsStats st;
    hxs_save_default(slot, false, &st);
    return Result(env, st);
}

JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateLoad(JNIEnv *env,
                                                            jobject,
                                                            jint slot)
{
    HxsStats st;
    hxs_load(slot, &st);
    return Result(env, st);
}

JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateUndoLoad(JNIEnv *env,
                                                                jobject)
{
    HxsStats st;
    hxs_undo_load(&st);
    return Result(env, st);
}

JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateUndoSave(JNIEnv *env,
                                                                jobject)
{
    HxsStats st;
    hxs_undo_save(&st);
    return Result(env, st);
}

JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateAutoQuit(JNIEnv *env,
                                                                jobject)
{
    HxsStats st;
    hxs_save_auto_quit(&st);
    return Result(env, st);
}

JNIEXPORT jboolean JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateDelete(JNIEnv *,
                                                              jobject,
                                                              jint slot)
{
    return hxs_delete(slot) == 0 ? JNI_TRUE : JNI_FALSE;
}

/* Bit 0: a load can be undone; bit 1: a save can be undone. */
JNIEXPORT jint JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateCanUndo(JNIEnv *,
                                                               jobject)
{
    return (hxs_can_undo_load() ? 1 : 0) | (hxs_can_undo_save() ? 2 : 0);
}

/*
 * One line per slot (0-9, then auto):
 * slot, exists, loadable, reason, saved_at, bytes, codec, other_title_since.
 * Null when there is no running title or folder.
 */
JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateList(JNIEnv *env,
                                                            jobject)
{
    HxsSlotInfo all[HXS_SLOT_COUNT];
    if (hxs_slot_list(all) < 0) {
        return nullptr;
    }
    std::string out;
    for (int s = 0; s <= HXS_SLOT_AUTO; s++) {
        char line[200];
        snprintf(line, sizeof(line), "%d\t%d\t%d\t%s\t%lld\t%llu\t%s\t%d\n",
                 s, all[s].exists, all[s].loadable,
                 all[s].reason[0] ? all[s].reason : "-",
                 (long long)all[s].saved_at,
                 (unsigned long long)all[s].file_bytes, CodecName(all[s].codec),
                 all[s].other_title_since);
        out += line;
    }
    return env->NewStringUTF(out.c_str());
}

/* "ok\t<slot>\t<saved_at>\t<ms>", "refused\t<slot>\t<reason>", "none", "off". */
JNIEXPORT jstring JNICALL
Java_com_rfandango_haku_1x_MainActivity_nativeSaveStateAutoLoadMessage(
    JNIEnv *env, jobject)
{
    const char *m = hxs_auto_load_message();
    return m ? env->NewStringUTF(m) : nullptr;
}

}  // extern "C"
