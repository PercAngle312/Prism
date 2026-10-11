#!/usr/bin/env python3
"""Exercise Swiss's actual entry helper with mocked directory/device services."""
from pathlib import Path
import subprocess
import tempfile

source = Path('cube/swiss/source/util.c').read_text()
helper = source[source.index('static int find_entry('):source.index('bool deleteFileOrDir(')]
stub = r'''
#define _GNU_SOURCE
#include <assert.h>
#include <stdbool.h>
#include <string.h>
#include <fnmatch.h>
#define DEVICE_CUR 0
#define DEVICE_PREV 1
#define IS_FILE 1
#define IS_DIR 2
#define ON_FILLIST 1
#define RECENT_ERR_ENT_MISSING 1
#define RECENT_ERR_DEV_MISSING 2
typedef struct { char name[1024]; int fileType; } file_handle;
typedef struct device { const char *deviceName; file_handle *initial;
    int (*init)(file_handle *); int (*deinit)(file_handle *); } DEVICEHANDLER_INTERFACE;
static file_handle root = {"sdc:/", IS_DIR};
static int init_device(file_handle *file) { (void)file; return 0; }
static DEVICEHANDLER_INTERFACE device = {"SD2SP2", &root, init_device, init_device};
static DEVICEHANDLER_INTERFACE *devices[2] = {&device, NULL};
static file_handle curDir, curFile;
static struct { char flattenDir[32]; } swissSettings = {"*/games"};
static int curMenuLocation, curMenuSelection, curSelection, needsDeviceChange, needsRefresh;
static file_handle entries[] = {
    {"sdc:/games/Game 1.iso", IS_FILE}, {"sdc:/games/Game [1].iso", IS_FILE}
};
static char loaded[1024];
static int load_count;
static DEVICEHANDLER_INTERFACE *getDeviceFromPath(char *path) {
    return !strncmp(path, "sdc:/", 5) ? &device : NULL;
}
#define print_debug(...) ((void)0)
static void freeFiles(void) {}
static void getParentPath(char *path, char *out) {
    char temp[1024]; strcpy(temp, path);
    char *slash = strrchr(temp, '/'); assert(slash); slash[0] = 0; strcpy(out, temp);
}
static bool endsWith(char *text, const char *suffix) {
    size_t a = strlen(text), b = strlen(suffix);
    return a >= b && !strcmp(text + a - b, suffix);
}
static void scanFiles(void) {}
static file_handle *getCurrentDirEntries(void) { return entries; }
static int getCurrentDirEntryCount(void) { return 2; }
static void populate_meta(file_handle *file) { (void)file; }
static int getSortedDirEntryIndex(file_handle *file) { return (int)(file - entries); }
static void load_file(void) { strcpy(loaded, curFile.name); ++load_count; }
'''
test = r'''
int main(void) {
    char literal[] = "sdc:/games/Game [1].iso";
    assert(find_existing_entry_exact(literal, true) == 0);
    assert(!strcmp(loaded, literal) && curSelection == 1 && load_count == 1);
    /* Legacy caller retains its documented wildcard behavior. */
    assert(find_existing_entry(literal, true) == 0);
    assert(!strcmp(loaded, entries[0].name) && load_count == 2);
    char missing[] = "sdc:/games/Missing.iso";
    assert(find_existing_entry_exact(missing, true) == RECENT_ERR_ENT_MISSING);
    assert(load_count == 2);
    char wrong_device[] = "sdb:/games/Game.iso";
    assert(find_existing_entry_exact(wrong_device, true) == RECENT_ERR_DEV_MISSING);
    assert(load_count == 2);
    assert(find_existing_entry_exact(literal, false) == 0 && load_count == 2);
    return 0;
}
'''
with tempfile.TemporaryDirectory() as folder:
    path = Path(folder)
    (path / 'test.c').write_text(stub + helper + test)
    subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-pedantic',
                    '-fsanitize=undefined', str(path / 'test.c'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
main = Path('cube/swiss/source/main.c').read_text()
browser = main[main.index('static int prism_installed_browser'):main.index('static void prism_dashboard_bootstrap')]
assert 'u32 last = BUTTON_A | BUTTON_B' in browser
assert browser.index('prism_installed_resolve(') < browser.index('find_existing_entry_exact(')
assert browser.index('swissSettings.autoBoot = 0;') < browser.index('find_existing_entry_exact(')
assert browser.index('swissSettings.autoBoot = auto_boot;') > browser.index('find_existing_entry_exact(')
print('Swiss exact-path launch, legacy glob behavior and PRISM entry guards passed')
