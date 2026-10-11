#ifndef PRISM_TEST_DEVICE_HANDLER_H
#define PRISM_TEST_DEVICE_HANDLER_H
#include <stdint.h>
typedef int32_t s32;
typedef int64_t s64;
typedef uint32_t u32;
#define PATHNAME_MAX 1024
#define ATTRIB_DIRECTORY 0x10
#define FEAT_READ 1
#define DEVICE_HANDLER_SEEK_SET 0
typedef struct DEVICEHANDLER_STRUCT DEVICEHANDLER_INTERFACE;
typedef struct {
    char name[PATHNAME_MAX];
    u32 size;
    unsigned char fileAttrib;
    DEVICEHANDLER_INTERFACE *device;
} file_handle;
struct DEVICEHANDLER_STRUCT {
    u32 features;
    s32 (*readDir)(file_handle *, file_handle **, u32);
    s32 (*readFile)(file_handle *, void *, u32);
    s64 (*seekFile)(file_handle *, s64, u32);
    s32 (*closeFile)(file_handle *);
};
#endif
