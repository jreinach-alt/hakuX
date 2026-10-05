/* cc_check.py --android: enough of <android/log.h> to type-check the
 * __ANDROID__ branches of vk/ on the desktop compiler. */
#ifndef ASYNC794_SHIM_ANDROID_LOG_H
#define ASYNC794_SHIM_ANDROID_LOG_H
enum { ANDROID_LOG_DEBUG = 3, ANDROID_LOG_INFO = 4, ANDROID_LOG_WARN = 5,
       ANDROID_LOG_ERROR = 6 };
int __android_log_print(int prio, const char *tag, const char *fmt, ...)
    __attribute__((format(printf, 3, 4)));
#endif
