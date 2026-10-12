#include <stdio.h>
#include <gccore.h>		/*** Wrapper to include common libogc headers ***/
#include <ogcsys.h>		/*** Needed for console support ***/
#include <ogc/color.h>
#include <ogc/dvdlow.h>
#include <ogc/exi.h>
#include <ogc/lwp.h>
#include <ogc/usbgecko.h>
#include <ogc/video_types.h>
#include <sdcard/card_cmn.h>
#include <ogc/machine/processor.h>
#include <stdio.h>
#include <ctype.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <malloc.h>
#include <sys/types.h>
#include <unistd.h>
#include <sdcard/gcsd.h>
#include "main.h"
#include "settings.h"
#include "swiss.h"
#include "bba.h"
#include "dvd.h"
#include "flippy.h"
#include "gcloader.h"
#include "wkf.h"
#include "exi.h"
#include "wiiload.h"
#include "config.h"
#include "sram.h"
#include "stub_bin.h"
#include "gui/FrameBufferMagic.h"
#include "gui/prism_pack_device.h"
#include "gui/prism_installed.h"
#include "gui/prism_enrich.h"
#include "gui/prism_layout.h"
#include "gui/prism_text.h"
#include "gui/prism_cover_cache.h"
#include "gui/IPLFontWrite.h"
#include "devices/deviceHandler.h"
#include "devices/fat/ata.h"
#include "aram/sidestep.h"
#include "devices/filemeta.h"

dvdcmdblk DVDCommandBlock;
dvdcmdblk DVDInquiryBlock;
dvdcmdblk DVDStopMotorBlock;
dvddrvinfo DVDDriveInfo[2] __attribute__((aligned(32)));
dvddiskid* DVDDiskID = (dvddiskid*)0x80000000;
SwissSettings swissSettings;

static const dvddiskid Swiss = {
	.gamename  = "GSWA",
	.company   = "GL",
	.magic     = DVD_MAGIC
};

static void driveInfoCallback(s32 result, dvdcmdblk *block) {
	dvddrvinfo* DVDDriveInfo = DVD_GetUserData(block);
	if(result == DVD_ERROR_CANCELED) {
		DVD_StopMotorAsync(block, NULL);
		return;
	}
	else if(result == DVD_ERROR_FATAL) {
		swissSettings.hasDVDDrive = 0;
		*DVDDeviceCode = 0x0001;
	}
	else if(result >= 0) {
		swissSettings.hasDVDDrive = 1;
		switch(DVDDriveInfo->rel_date) {
			default:
				*DVDDeviceCode = 0x8000 | DVDDriveInfo->dev_code;
				break;
			case 0:
				*DVDDeviceCode = 0x0001;
				break;
			case 0x20220420:
			case 0x20220426:
				syssramex* sramex = __SYS_LockSramEx();
				*DVDDeviceCode = sramex->dvddev_code;
				__SYS_UnlockSramEx(FALSE);
				return;
		}
	}
	syssramex* sramex = __SYS_LockSramEx();
	sramex->dvddev_code = *DVDDeviceCode;
	__SYS_UnlockSramEx(TRUE);
}

static void resetCoverCallback(s32 result) {
	syssramex* sramex = __SYS_LockSramEx();
	if(sramex->dvddev_code & 0x8000) {
		swissSettings.hasDVDDrive = 2;
		*DVDDeviceCode = sramex->dvddev_code;
		DVD_Pause();
		DVD_Reset(DVD_RESETSOFT);
	}
	__SYS_UnlockSramEx(FALSE);
}

/* Initialise Video, PAD, DVD, Font */
void Initialise(void)
{
	DVD_Init();
	DVD_LowSetResetCoverCallback(resetCoverCallback);
	DVD_Reset(DVD_RESETNONE);
	while(DVD_LowGetCoverStatus() == DVD_COVER_RESET);
	DVD_LowSetResetCoverCallback(NULL);
	refreshDeviceCode(false);

	// Disable IPL modchips to allow access to IPL ROM fonts
	ipl_set_config(6); 
	usleep(1000); //wait for modchip to disable (overkill)
	__SYS_ReadROM(IPLInfo,256,0);	// Read IPL tag

	if(!strncmp(IPLInfo, "(C) ", 4)) {
		if(!strncmp(&IPLInfo[0x55], "NTSC", 4) || (!IPLInfo[0x55] && (SYS_GetConsoleType() & SYS_CONSOLE_MASK) == SYS_CONSOLE_RETAIL))
			swissSettings.sramVideo = SYS_VIDEO_NTSC;
		else if(!strncmp(&IPLInfo[0x55], "PAL ", 4))
			swissSettings.sramVideo = SYS_VIDEO_PAL;
		else if(!strncmp(&IPLInfo[0x55], "MPAL", 4))
			swissSettings.sramVideo = SYS_VIDEO_MPAL;
		else if(!strncmp(&IPLInfo[0x55], "TDEV", 4) && (SYS_GetConsoleType() & SYS_CONSOLE_MASK) == SYS_CONSOLE_RETAIL) {
			*(u32*)0x8000002C += SYS_CONSOLE_TDEV_HW1 - SYS_CONSOLE_RETAIL_HW1;
			swissSettings.sramVideo = SYS_VIDEO_NTSC;
		}
	}

	*(u32*)0x800000CC = swissSettings.sramVideo;
	SYS_SetVideoMode(swissSettings.sramVideo);
	swissSettings.fontEncode = SYS_GetFontEncoding();

	if(swissSettings.sramLanguage == SYS_LANG_ENGLISH) {
		if(swissSettings.sramVideo == SYS_VIDEO_NTSC)
			swissSettings.sramLanguage = swissSettings.fontEncode == SYS_FONTENC_SJIS ? SYS_LANG_JAPANESE : SYS_LANG_ENGLISH_US;
		else if(swissSettings.sramVideo == SYS_VIDEO_MPAL)
			swissSettings.sramLanguage = SYS_LANG_ENGLISH_US;
	}

	GXRModeObj *vmode = getVideoMode();
	DrawInit(vmode, swissSettings.cubebootInvoked);
}

void __SYS_PreInit(void)
{
	u32 start = 0x80000000, end = 0x80003100;

	if (DVDDiskID->magic == DVD_MAGIC)
		start += sizeof(dvddiskid);

	DCZeroRange((void *)start, end - start);

	switch (((vu16 *)0xCC004000)[20] & 7) {
		case 0:
			*(u32 *)0x80000028 = 0x1000000;
			break;
		case 1: case 4:
			*(u32 *)0x80000028 = 0x2000000;
			break;
		case 2: case 6:
			*(u32 *)0x80000028 = 0x1800000;
			break;
		case 3: case 7:
			*(u32 *)0x80000028 = 0x3000000;
			break;
		case 5:
			*(u32 *)0x80000028 = 0x4000000;
			break;
	}

	if (((vu32 *)0xCC006000)[9] == 0xFF)
		*(u32 *)0x8000002C = SYS_CONSOLE_RETAIL_HW1;
	else
		*(u32 *)0x8000002C = SYS_CONSOLE_DEVELOPMENT_HW1;

	*(u32 *)0x8000002C += SYS_GetFlipperRevision();

	*(u32 *)0x800000F8 = SYS_GetBusFrequency();
	*(u32 *)0x800000FC = SYS_GetCoreFrequency();

	memcpy((void *)0x80001800, stub_bin, stub_bin_size);
	DCFlushRangeNoSync((void *)0x80001800, stub_bin_size); _sync();
	ICInvalidateRange((void *)0x80001800, stub_bin_size);

	*(u64 *)0x800030D8 = -__builtin_ppc_get_timebase();
	*(u16 *)0x800030E0 = 0x0006; // For backwards compatibility

	__PADFixBits = PAD_CHAN0_BIT | PAD_CHAN1_BIT | PAD_CHAN2_BIT | PAD_CHAN3_BIT;
}

uiDrawObj_t *configProgBar = NULL;
void config_migration(char* text, int state, int percent) {
	if(state) {
		if(percent < 0) {
			configProgBar = DrawPublish(DrawProgressBar(percent == -2, 0, text));
		}
		else {
			DrawUpdateProgressBar(configProgBar, percent);
		}
	}
	else {
		if(configProgBar) {
			DrawDispose(configProgBar);
		}
	}
}

/*
 * Prism dashboard bootstrap: temporary safe entry screen.
 * B/START or the Classic Swiss tile returns to the original menu.
 * Keep all Swiss initialization and game-launch code unchanged.
 * This bootstrap will be replaced by the actual cover library renderer.
 */
/* Disposing PRISM's opaque layer reveals the original Swiss frame. */
static uiDrawObj_t *prism_draw_panel(const char *subtitle)
{
    uiDrawObj_t *panel = DrawContainer();
    DrawAddChild(panel, DrawEmptyColouredBox(10, 10, 630, 470,
        (GXColor){9, 14, 27, 255}));
    DrawAddChild(panel, DrawEmptyColouredBox(PRISM_PANEL_X, PRISM_PANEL_Y,
        PRISM_PANEL_RIGHT, PRISM_PANEL_BOTTOM, (GXColor){18, 24, 42, 255}));
    DrawAddChild(panel, DrawStyledLabel(PRISM_LOGO_X, PRISM_LOGO_Y, "PRISM",
        1.5f, ALIGN_LEFT, (GXColor){225, 235, 255, 255}));
    DrawAddChild(panel, DrawStyledLabel(585, PRISM_LOGO_Y + 8,
        "Build " GIT_COMMIT, 0.65f, ALIGN_RIGHT, (GXColor){170, 194, 229, 255}));
    DrawAddChild(panel, DrawStyledLabel(PRISM_LOGO_X, PRISM_SUBTITLE_Y,
        subtitle, 0.8f, ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
    return panel;
}

typedef struct { int width; float scale; } PrismTextMeasure;

static int prism_text_fits(const char *text, void *context)
{
    PrismTextMeasure *measure = context;
    return GetTextScaleToFitInWidth(text, measure->width) >= measure->scale;
}

static void prism_draw_wrapped(uiDrawObj_t *panel, const char *text,
                                int x, int y, int width, float scale,
                                int rows, int line_height, GXColor colour)
{
    PrismTextMeasure measure = {width, scale};
    const char *cursor = text;
    char line[128];
    for (int row = 0; row < rows &&
         prism_text_next(&cursor, line, sizeof(line), prism_text_fits, &measure); ++row) {
        if (row + 1 == rows && *cursor)
            prism_text_elide(line, sizeof(line), prism_text_fits, &measure);
        DrawAddChild(panel, DrawStyledLabel(x, y + row * line_height, line,
            scale, ALIGN_LEFT, colour));
    }
}

/* A compact cover shelf: central selection stays prominent on a 4:3 TV. */
static void prism_draw_cover_card(uiDrawObj_t *panel, const PrismLibraryGame *game,
                                   GXTexObj *texture, int has_cover,
                                   int x, int y, int width, int height)
{
    if (!game) return;
    DrawAddChild(panel, DrawEmptyColouredBox(x, y, x + width, y + height,
        (GXColor){29, 42, 65, 255}));
    if (has_cover)
        DrawAddChild(panel, DrawTexObj(texture, x, y, width, height,
            0, 0.0f, 1.0f, 0.0f, 1.0f, 0));
    else {
        prism_draw_wrapped(panel, game->title, x + 8, y + 28, width - 16,
            0.65f, 4, 18, (GXColor){204, 218, 239, 255});
        DrawAddChild(panel, DrawStyledLabel(x + width / 2, y + height - 24,
            "NO COVER", 0.55f, ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
    }
}

static void prism_draw_coverflow(uiDrawObj_t *panel, const PrismLibrary *library,
                                  GXTexObj *texture, int has_cover,
                                  GXTexObj *side_textures[2], int side_covers[2],
                                  const char *title)
{
    prism_draw_cover_card(panel, prism_library_neighbor(library, -1),
        side_textures[0], side_covers[0], PRISM_FLOW_LEFT_X, PRISM_FLOW_SIDE_Y,
        PRISM_FLOW_SIDE_WIDTH, PRISM_FLOW_SIDE_HEIGHT);
    prism_draw_cover_card(panel, prism_library_neighbor(library, 1),
        side_textures[1], side_covers[1], PRISM_FLOW_RIGHT_X, PRISM_FLOW_SIDE_Y,
        PRISM_FLOW_SIDE_WIDTH, PRISM_FLOW_SIDE_HEIGHT);
    prism_draw_cover_card(panel, prism_library_selected(library),
        texture, has_cover, PRISM_FLOW_CENTER_X, PRISM_FLOW_CENTER_Y,
        PRISM_LAYOUT_COVER_WIDTH, PRISM_LAYOUT_COVER_HEIGHT);
    PrismTextMeasure measure = {500, 0.85f};
    const char *cursor = title;
    char label[128];
    if (prism_text_next(&cursor, label, sizeof(label), prism_text_fits, &measure)) {
        if (*cursor) prism_text_elide(label, sizeof(label), prism_text_fits, &measure);
        DrawAddChild(panel, DrawStyledLabel(320, PRISM_FLOW_TITLE_Y, label,
            0.85f, ALIGN_CENTER, (GXColor){225, 235, 255, 255}));
    }
}

static uiDrawObj_t *prism_draw_home(int selection)
{
    uiDrawObj_t *panel = prism_draw_panel("YOUR GAME LIBRARY");
    DrawAddChild(panel, DrawStyledLabel(58, 150,
        "Your installed games first. Full catalog is optional.", 0.78f,
        ALIGN_LEFT, (GXColor){204, 218, 239, 255}));
    DrawAddChild(panel, DrawSelectableButton(58, 196, 582, 234,
        "Browse installed games", selection == 0 ? B_SELECTED : B_NOSELECT));
    DrawAddChild(panel, DrawSelectableButton(58, 247, 582, 285,
        "Open Classic Swiss", selection == 1 ? B_SELECTED : B_NOSELECT));
    DrawAddChild(panel, DrawSelectableButton(58, 298, 582, 336,
        "Browse offline catalog", selection == 2 ? B_SELECTED : B_NOSELECT));
    DrawAddChild(panel, DrawSelectableButton(58, 349, 582, 387,
        "About PRISM", selection == 3 ? B_SELECTED : B_NOSELECT));
    DrawAddChild(panel, DrawStyledLabel(320, PRISM_FOOTER_LABELS_Y,
        "D-Pad: Select   A: Open   B/START: Classic Swiss", 0.72f, ALIGN_CENTER,
        (GXColor){185, 200, 225, 255}));
    return DrawPublish(panel);
}

/* Keep a visible checkpoint while Swiss initializes storage and settings. */
static uiDrawObj_t *prism_startup_stage(uiDrawObj_t *previous, const char *stage)
{
	uiDrawObj_t *panel = DrawContainer();
	DrawAddChild(panel, DrawEmptyColouredBox(55, 145, 585, 335,
		(GXColor){18, 24, 42, 255}));
	DrawAddChild(panel, DrawStyledLabel(320, 195,
		"PRISM STARTUP V3", 1.5f, ALIGN_CENTER,
		(GXColor){225, 235, 255, 255}));
	DrawAddChild(panel, DrawStyledLabel(320, 245, stage, 0.9f, ALIGN_CENTER,
		(GXColor){170, 194, 229, 255}));
	DrawAddChild(panel, DrawStyledLabel(320, 295,
		"Build " GIT_COMMIT, 0.8f, ALIGN_CENTER,
		(GXColor){170, 194, 229, 255}));
	return DrawRepublish(previous, panel);
}

/* Read-only catalog browser. Game launching stays in Classic Swiss. */
static void prism_catalog_browser(DEVICEHANDLER_INTERFACE *device, const char *path,
                                  u32 count)
{
    u32 position = 0;
    u32 last = BUTTON_B | BUTTON_START | BUTTON_LEFT | BUTTON_RIGHT;
    for (;;) {
        PrismPackEntry entry;
        char title[PRISM_PACK_TITLE_MAX + 1];
        char synopsis[PRISM_PACK_SYNOPSIS_MAX + 1];
        char heading[100];
        uiDrawObj_t *panel;
        u32 pressed, held;
        if (!prism_pack_device_entry(device, path, position, &entry,
                                     title, sizeof(title), synopsis, sizeof(synopsis))) {
            uiDrawObj_t *error = DrawPublish(DrawMessageBox(D_WARN,
                "Unable to read PRISM metadata entry.\nPress A/B to return."));
            while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
            while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
            DrawDispose(error);
            return;
        }
        snprintf(heading, sizeof(heading), "OFFLINE CATALOG  |  %lu / %lu",
            (unsigned long)(position + 1),
            (unsigned long)count);
        panel = prism_draw_panel(heading);
        DrawAddChild(panel, DrawStyledLabel(585, PRISM_SUBTITLE_Y,
            entry.id, 0.72f, ALIGN_RIGHT, (GXColor){170, 194, 229, 255}));
        DrawAddChild(panel, DrawEmptyColouredBox(PRISM_COVER_X, PRISM_COVER_Y,
            PRISM_COVER_X + PRISM_LAYOUT_COVER_WIDTH, PRISM_COVER_Y + PRISM_LAYOUT_COVER_HEIGHT,
            (GXColor){37, 52, 78, 255}));
            DrawAddChild(panel, DrawStyledLabel(PRISM_COVER_X + PRISM_LAYOUT_COVER_WIDTH / 2,
                PRISM_COVER_Y + PRISM_LAYOUT_COVER_HEIGHT / 2, "COVER PENDING", 0.72f,
                ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
        prism_draw_wrapped(panel, title, PRISM_TEXT_X, PRISM_TITLE_Y,
            PRISM_TEXT_WIDTH, 0.9f, 2, 25, (GXColor){225, 235, 255, 255});
        DrawAddChild(panel, DrawStyledLabel(PRISM_TEXT_X, PRISM_SYNOPSIS_HEADING_Y,
            "SYNOPSIS", 0.72f, ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
        prism_draw_wrapped(panel,
            synopsis[0] ? synopsis : "Metadata not available for this disc.",
            PRISM_TEXT_X, PRISM_SYNOPSIS_Y, PRISM_TEXT_WIDTH, 0.68f,
            6, 22, (GXColor){204, 218, 239, 255});
        DrawAddChild(panel, DrawStyledLabel(320, PRISM_FOOTER_LABELS_Y,
            "LEFT/RIGHT: Browse    B/START: Return", 0.75f, ALIGN_CENTER,
            (GXColor){185, 200, 225, 255}));
        panel = DrawPublish(panel);
        for (;;) {
            held = padsButtonsHeld();
            pressed = held & ~last;
            last = held;
            if (pressed & (BUTTON_B | BUTTON_START)) {
                DrawDispose(panel);
                return;
            }
            if (pressed & BUTTON_RIGHT) {
                position = (position + 1) % count;
                break;
            }
            if (pressed & BUTTON_LEFT) {
                position = (position + count - 1) % count;
                break;
            }
            VIDEO_WaitVSync();
        }
        DrawDispose(panel);
    }
}

/* Metadata policy is portable; pixels and GX objects remain stable while
 * their slot is pinned by either the displayed or incoming frame. */
typedef struct {
    PrismCoverCache policy;
    void *pixels[PRISM_COVER_CACHE_SLOTS];
    GXTexObj textures[PRISM_COVER_CACHE_SLOTS];
} PrismRuntimeCoverCache;

static int prism_cached_cover(PrismRuntimeCoverCache *cache,
                               DEVICEHANDLER_INTERFACE *device,
                               const char *path, const char *id, unsigned pinned)
{
    int load, slot;
    if (!cache || !device || !path) return -1;
    slot = prism_cover_cache_reserve(&cache->policy, id, pinned, &load);
    if (slot < 0 || !load) return slot;
    if (!cache->pixels[slot])
        cache->pixels[slot] = memalign(32, PRISM_COVER_TEXTURE_SIZE);
    /* Allocation failure remains pending so a later frame can retry. */
    if (!cache->pixels[slot]) return -1;
    int available = prism_pack_device_cover(device, path, id,
        cache->pixels[slot], PRISM_COVER_TEXTURE_SIZE);
    if (available) {
        DCFlushRange(cache->pixels[slot], PRISM_COVER_TEXTURE_SIZE);
        GX_InitTexObj(&cache->textures[slot], cache->pixels[slot], PRISM_COVER_WIDTH,
            PRISM_COVER_HEIGHT, GX_TF_RGB565, GX_CLAMP, GX_CLAMP, GX_FALSE);
        GX_InitTexObjLOD(&cache->textures[slot], GX_LINEAR, GX_LINEAR,
            0.0f, 0.0f, 0.0f, GX_FALSE, GX_FALSE, GX_ANISO_1);
    }
    prism_cover_cache_complete(&cache->policy, slot, available);
    return slot;
}

static void prism_free_cover_cache(PrismRuntimeCoverCache *cache)
{
    if (!cache) return;
    for (int i = 0; i < PRISM_COVER_CACHE_SLOTS; ++i) free(cache->pixels[i]);
    free(cache);
}

/* Raw GameCube images discovered via Swiss on /games.
 * Launch through Swiss's existing file preparation and game-info flow.
 */
static int prism_installed_browser(int quiet_if_empty)
{
    DEVICEHANDLER_INTERFACE *device = devices[DEVICE_CUR];
    DEVICEHANDLER_INTERFACE *metadata_device = devices[DEVICE_CONFIG];
    PrismLibrary *library;
    PrismInstalledPaths *paths;
    char folder[PATHNAME_MAX];
    char pack_path[PATHNAME_MAX];
    int has_pack = 0;
    PrismRuntimeCoverCache *covers = NULL;
    uiDrawObj_t *screen = NULL;
    unsigned displayed_slots = 0;
    int details = 0;
    u32 last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_LEFT | BUTTON_RIGHT |
               BUTTON_X | BUTTON_L | BUTTON_R;
    if (!device || !device->initial ||
        snprintf(folder, sizeof(folder), "%sgames", device->initial->name) >= (int)sizeof(folder)) {
        if (quiet_if_empty) return 0;
        uiDrawObj_t *info = DrawPublish(DrawMessageBox(D_INFO,
            "No active Swiss game storage. Use Classic Swiss."));
        while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
        while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
        DrawDispose(info);
        return 0;
    }
    library = malloc(sizeof(*library));
    if (!library) return 0;
    paths = malloc(sizeof(*paths));
    if (!paths) { free(library); return 0; }
    uiDrawObj_t *scan_progress = DrawPublish(DrawProgressBar(true, 0,
        "Scanning installed games"));
    int scanned = prism_installed_scan(device, folder, library, paths);
    DrawDispose(scan_progress);
    if (!scanned || !library->count) {
        if (quiet_if_empty) { free(paths); free(library); return 0; }
        uiDrawObj_t *info = DrawPublish(DrawMessageBox(D_INFO,
            "No ISO/GCM files found in /games\nor its game folders. Use Classic Swiss."));
        while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
        while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
        DrawDispose(info);
        free(paths);
        free(library);
        return 0;
    }
    if (metadata_device && metadata_device->initial &&
        snprintf(pack_path, sizeof(pack_path), "%sswiss/prism/library.prism",
                 metadata_device->initial->name) < (int)sizeof(pack_path)) {
        u32 count = 0;
        has_pack = prism_pack_device_count(metadata_device, pack_path, &count);
    }
    covers = calloc(1, sizeof(*covers));
    /* A failed cache allocation still permits title-only browsing/launching. */
    for (;;) {
        int has_cover = 0;
        int slots[3] = {-1, -1, -1};
        int side_covers[2] = {0, 0};
        GXTexObj *cover_texture = NULL;
        GXTexObj *side_textures[2] = {NULL, NULL};
        unsigned incoming_slots = 0;
        const PrismLibraryGame *game = prism_library_selected(library);
        char title[PRISM_PACK_TITLE_MAX + 1];
        char synopsis[PRISM_PACK_SYNOPSIS_MAX + 1];
        char heading[100];
        uiDrawObj_t *panel;
        u32 held, pressed;
        if (!game) break;
        if (!prism_enrich_installed(has_pack ? metadata_device : NULL,
                                    has_pack ? pack_path : NULL, game,
                                    title, sizeof(title), synopsis, sizeof(synopsis)))
            break;
        if (has_pack && covers) {
            for (int position = 0; position < 3; ++position) {
                if (details && position != 1) continue;
                const PrismLibraryGame *candidate = prism_library_neighbor(library, position - 1);
                if (!candidate) continue;
                slots[position] = prism_cached_cover(covers, metadata_device, pack_path,
                    candidate->id, displayed_slots | incoming_slots);
                if (slots[position] >= 0) incoming_slots |= 1u << slots[position];
            }
            if (slots[1] >= 0) {
                cover_texture = &covers->textures[slots[1]];
                has_cover = covers->policy.entries[slots[1]].state == PRISM_CACHE_READY;
            }
            for (int side = 0; side < 2; ++side) {
                int slot = slots[side ? 2 : 0];
                if (slot >= 0) {
                    side_textures[side] = &covers->textures[slot];
                    side_covers[side] = covers->policy.entries[slot].state == PRISM_CACHE_READY;
                }
            }
        }
        snprintf(heading, sizeof(heading), "INSTALLED GAMES  |  %lu / %lu",
            (unsigned long)(library->selected + 1),
            (unsigned long)library->count);
        panel = prism_draw_panel(heading);
        DrawAddChild(panel, DrawStyledLabel(585, PRISM_SUBTITLE_Y,
            game->id, 0.72f, ALIGN_RIGHT, (GXColor){170, 194, 229, 255}));
        if (!details) {
            prism_draw_coverflow(panel, library, cover_texture, has_cover,
                side_textures, side_covers, title);
        } else {
            DrawAddChild(panel, DrawEmptyColouredBox(PRISM_COVER_X, PRISM_COVER_Y,
                PRISM_COVER_X + PRISM_LAYOUT_COVER_WIDTH, PRISM_COVER_Y + PRISM_LAYOUT_COVER_HEIGHT,
                (GXColor){37, 52, 78, 255}));
            if (has_cover)
                DrawAddChild(panel, DrawTexObj(cover_texture,
                    PRISM_COVER_X, PRISM_COVER_Y, PRISM_LAYOUT_COVER_WIDTH, PRISM_LAYOUT_COVER_HEIGHT,
                    0, 0.0f, 1.0f, 0.0f, 1.0f, 0));
            else
                DrawAddChild(panel, DrawStyledLabel(PRISM_COVER_X + PRISM_LAYOUT_COVER_WIDTH / 2,
                    PRISM_COVER_Y + PRISM_LAYOUT_COVER_HEIGHT / 2, "NO COVER", 0.72f,
                    ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
            prism_draw_wrapped(panel, title, PRISM_TEXT_X, PRISM_TITLE_Y,
                PRISM_TEXT_WIDTH, 0.9f, 2, 25, (GXColor){225, 235, 255, 255});
            DrawAddChild(panel, DrawStyledLabel(PRISM_TEXT_X, PRISM_SYNOPSIS_HEADING_Y,
                "SYNOPSIS", 0.72f, ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
            prism_draw_wrapped(panel,
                synopsis[0] ? synopsis : "Metadata not available for this disc.",
                PRISM_TEXT_X, PRISM_SYNOPSIS_Y, PRISM_TEXT_WIDTH, 0.68f,
                6, 22, (GXColor){204, 218, 239, 255});
        }
        char scan_status[100];
        if (paths->truncated)
            snprintf(scan_status, sizeof(scan_status),
                "%u-game limit reached; scan stopped",
                (unsigned)PRISM_LIBRARY_MAX_GAMES);
        else if (paths->unreadable_folders)
            snprintf(scan_status, sizeof(scan_status),
                "Partial scan: %u game folders unreadable",
                paths->unreadable_folders);
        else
            snprintf(scan_status, sizeof(scan_status),
                "%s | /games + game folders", device->deviceName);
        float status_scale = GetTextScaleToFitInWidth(scan_status,
            details ? PRISM_STATUS_WIDTH : 500);
        if (status_scale > 0.6f) status_scale = 0.6f;
        DrawAddChild(panel, DrawStyledLabel(details ? PRISM_STATUS_X : 320,
            details ? PRISM_STATUS_Y : PRISM_FLOW_STATUS_Y, scan_status, status_scale,
            details ? ALIGN_LEFT : ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
        DrawAddChild(panel, DrawStyledLabel(320,
            details ? PRISM_FOOTER_LABELS_Y : PRISM_FLOW_FOOTER_Y,
            details ? "LEFT/RIGHT: Browse  L/R: 10  X: Covers  A: Game info  B: Return" :
                      "LEFT/RIGHT: Browse  L/R: 10  X: Details  A: Game info  B: Return",
            0.65f, ALIGN_CENTER, (GXColor){185, 200, 225, 255}));
        screen = DrawRepublish(screen, panel);
        panel = screen;
        displayed_slots = incoming_slots;
        for (;;) {
            held = padsButtonsHeld();
            pressed = held & ~last;
            last = held;
            if (pressed & (BUTTON_B | BUTTON_START)) {
                DrawDispose(panel);
                prism_free_cover_cache(covers);
                free(paths);
                free(library);
                return 1;
            }
            if (pressed & BUTTON_A) {
                char launch_path[PATHNAME_MAX];
                /* Recheck identity before entering Swiss, and require a fresh
                 * A press on its game-info screen (even with saved AutoBoot). */
                if (!prism_installed_resolve(device, paths, game,
                                              launch_path, sizeof(launch_path))) {
                    uiDrawObj_t *error = DrawPublish(DrawMessageBox(D_WARN,
                        "Game file changed or could not be read.\n"
                        "Press A/B to return."));
                    while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
                    while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
                    DrawDispose(error);
                    last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_X | BUTTON_L | BUTTON_R;
                    continue;
                }
                DrawDispose(screen);
                screen = NULL;
                displayed_slots = 0;
                panel = NULL;
                while (padsButtonsHeld() & BUTTON_A) VIDEO_WaitVSync();
                int auto_boot = swissSettings.autoBoot;
                swissSettings.autoBoot = 0;
                int result = find_existing_entry_exact(launch_path, true);
                swissSettings.autoBoot = auto_boot;
                if (result != 0) {
                    uiDrawObj_t *error = DrawPublish(DrawMessageBox(D_WARN,
                        "Swiss could not locate the selected game.\n"
                        "Press A/B to return."));
                    while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
                    while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
                    DrawDispose(error);
                }
                last = BUTTON_A | BUTTON_B | BUTTON_START;
                break; /* Cancellation/errors redraw the same PRISM selection. */
            }
            if (pressed & BUTTON_X) {
                details = !details;
                break;
            }
            if (pressed & (BUTTON_L | BUTTON_R)) {
                prism_library_step(library, (pressed & BUTTON_R) ? 10 : -10);
                break;
            }
            if (pressed & BUTTON_RIGHT) {
                prism_library_move(library, 1);
                break;
            }
            if (pressed & BUTTON_LEFT) {
                prism_library_move(library, -1);
                break;
            }
            VIDEO_WaitVSync();
        }
        /* Retain this frame during metadata/art reads for the next one. */
    }
    if (screen) DrawDispose(screen);
    prism_free_cover_cache(covers);
    free(paths);
    free(library);
    return 1;
}

/* Isolated boot UI: always allow direct access to Swiss's original menu.
 * No changes are made to Swiss's device or launch subsystems.
 */
static void prism_dashboard_bootstrap(void)
{
	/* Hardware isolation: render PRISM home first. Installed-game scanning
	 * remains available through the Games tile, after the UI is proven. */
	int selection = 0;
	u32 last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_UP | BUTTON_DOWN;
	uiDrawObj_t *screen = prism_draw_home(selection);
	/* Require a new button press after the diagnostic. Holding A/B/START
	 * while the dashboard first appears must not immediately exit it. */
	while (padsButtonsHeld() & (BUTTON_A | BUTTON_B | BUTTON_START))
		VIDEO_WaitVSync();
	for (;;) {
		u32 held = padsButtonsHeld();
		u32 pressed = held & ~last;
		last = held;
		if (pressed & (BUTTON_B | BUTTON_START)) break;
		if (pressed & (BUTTON_UP | BUTTON_DOWN)) {
			selection = (selection + ((pressed & BUTTON_DOWN) ? 1 : 3)) % 4;
			DrawDispose(screen);
			screen = prism_draw_home(selection);
		}
		if (pressed & BUTTON_A) {
			if (selection == 1) break;
			if (selection == 0) {
				DrawDispose(screen);
				prism_installed_browser(0);
				screen = prism_draw_home(selection);
				last = BUTTON_A | BUTTON_B | BUTTON_START;
				continue;
			}
			if (selection == 2) {
				DEVICEHANDLER_INTERFACE *device = devices[DEVICE_CONFIG];
				char path[PATHNAME_MAX];
				char result[192];
				u32 game_count = 0;
				int found = 0;
				if(device && device->initial &&
				   snprintf(path, sizeof(path), "%sswiss/prism/library.prism",
				            device->initial->name) < sizeof(path)) {
					found = prism_pack_device_count(device, path, &game_count);
				}
				if (found && game_count) {
					DrawDispose(screen);
					prism_catalog_browser(device, path, game_count);
					screen = prism_draw_home(selection);
					last = BUTTON_A | BUTTON_B | BUTTON_START;
					continue;
				}
				if (found)
					snprintf(result, sizeof(result),
					         "PRISM offline catalog is empty.\\nPress A/B to return.");
				else
					snprintf(result, sizeof(result),
					         "No readable PRISM pack on config storage.\\n"
					         "Expected: swiss/prism/library.prism\\nA/B: Return");
				uiDrawObj_t *info = DrawPublish(DrawMessageBox(D_INFO, result));
				while(padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
				while(!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
				DrawDispose(info);
				last = BUTTON_A | BUTTON_B;
				continue;
			}
			uiDrawObj_t *about = DrawPublish(DrawMessageBox(D_INFO,
				"PRISM Dashboard\n"
				"An original GameCube frontend built on Swiss.\n"
				"Press A or B to return."));
			/* Ignore the A press that opened this dialog. */
			while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
			while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
			DrawDispose(about);
			last = BUTTON_A | BUTTON_B;
		}
		VIDEO_WaitVSync();
	}
	DrawDispose(screen);
}

/****************************************************************************
* Main
****************************************************************************/
int main(int argc, char *argv[])
{
	// Setup defaults (if no config is found)
	memset(&swissSettings, 0 , sizeof(SwissSettings));
	strcpy(swissSettings.flattenDir, "*/games");

	// Register all devices supported (order matters for boot devices)
	int i = 0;
	for(i = 0; i < MAX_DEVICES; i++)
		allDevices[i] = NULL;
	i = 0;
	allDevices[i++] = &__device_flippy;
	allDevices[i++] = &__device_flippyflash;
	allDevices[i++] = &__device_wkf;
	allDevices[i++] = &__device_wode;
	allDevices[i++] = &__device_gcloader;
	allDevices[i++] = &__device_ata_c;
	allDevices[i++] = &__device_mcp_c;
	allDevices[i++] = &__device_sd_c;
	allDevices[i++] = &__device_sd_a;
	allDevices[i++] = &__device_sd_b;
	allDevices[i++] = &__device_mcp_a;
	allDevices[i++] = &__device_mcp_b;
	allDevices[i++] = &__device_dvd;
	allDevices[i++] = &__device_card_a;
	allDevices[i++] = &__device_card_b;
	allDevices[i++] = &__device_kunaigc;
	allDevices[i++] = &__device_qoob;
	allDevices[i++] = &__device_aram;
	allDevices[i++] = &__device_sys;
	allDevices[i++] = &__device_ata_a;
	allDevices[i++] = &__device_ata_b;
	allDevices[i++] = &__device_usbgecko;
	allDevices[i++] = &__device_smb;
	allDevices[i++] = &__device_ftp;
	allDevices[i++] = &__device_fsp;
	allDevices[i++] = NULL;
	
	// Set current devices
	devices[DEVICE_CUR] = NULL;
	devices[DEVICE_PREV] = NULL;
	devices[DEVICE_DEST] = NULL;
	devices[DEVICE_CHEATS] = NULL;
	devices[DEVICE_CONFIG] = NULL;
	devices[DEVICE_PATCHES] = NULL;
	
	// Sane defaults
	refreshSRAM(&swissSettings);
	swissSettings.enableUSBGecko = USBGECKO_OFF;
	swissSettings.exiSpeed = 1;		// 32MHz
	swissSettings.uiVMode = 0; 		// Auto UI mode
	swissSettings.gameVMode = 0;	// Auto video mode
	swissSettings.lastDTVStatus = getRawDTVStatus();
	swissSettings.configAudioBuffer = ENABLE_BYDISK;
	swissSettings.emulateAudioStream = 1;
	swissSettings.ftpPort = 21;
	swissSettings.fspPort = 21;
	swissSettings.fspPathMtu = 1500;
	swissSettings.bbaUseDhcp = 1;
	swissSettings.aveCompat = GCVIDEO_COMPAT;
	swissSettings.fileBrowserType = BROWSER_STANDARD;
	swissSettings.appsBrowserType = BROWSER_FULLWIDTH;
	swissSettings.gameBrowserType = BROWSER_FULLWIDTH;
	swissSettings.recentListLevel = 2;
	memset(&swissSettings.recent[0][0], 0, PATHNAME_MAX);
	config_init_environ();

	Initialise();
	/* Diagnostic before all Swiss device init, autoload and config paths. */
	/* Show an unmistakable first-frame diagnostic before any storage
	 * scan: distinguishes PRISM startup from the original Swiss menu. */
	uiDrawObj_t *boot_mark = DrawContainer();
	DrawAddChild(boot_mark, DrawEmptyColouredBox(55, 145, 585, 335,
		(GXColor){18, 24, 42, 255}));
	DrawAddChild(boot_mark, DrawStyledLabel(320, 200,
		"PRISM BOOT CHECK V3", 1.8f, ALIGN_CENTER,
		(GXColor){225, 235, 255, 255}));
	DrawAddChild(boot_mark, DrawStyledLabel(320, 265,
		swissSettings.cubebootInvoked ?
		"A: PRISM    X: Continue cubeboot" : "Press A to enter PRISM", 0.9f, ALIGN_CENTER,
		(GXColor){170, 194, 229, 255}));
	DrawAddChild(boot_mark, DrawStyledLabel(320, 310,
		"Build " GIT_COMMIT, 0.8f, ALIGN_CENTER,
		(GXColor){170, 194, 229, 255}));
	boot_mark = DrawPublish(boot_mark);
	/* A timed splash is too easy to miss on a display that resynchronizes
	 * video as a DOL starts. Require a fresh A press to proceed instead. */
	u32 boot_buttons = BUTTON_A | (swissSettings.cubebootInvoked ? BUTTON_X : 0);
	while (padsButtonsHeld() & boot_buttons) VIDEO_WaitVSync();
	u32 boot_pressed;
	while (!((boot_pressed = padsButtonsHeld()) & boot_buttons)) VIDEO_WaitVSync();
	/* A explicitly requests PRISM even if the launching loader supplied
	 * CUBEBOOT=1. X retains the special Swiss cubeboot path. */
	if (boot_pressed & BUTTON_A) {
		if (swissSettings.cubebootInvoked)
			DrawClassicUI();
		swissSettings.cubebootInvoked = 0;
		unsetenv("CUBEBOOT");
	}
	int prism_opened = !swissSettings.cubebootInvoked;
	DrawDispose(boot_mark);
	while (padsButtonsHeld() & boot_buttons) VIDEO_WaitVSync();
	uiDrawObj_t *startup = prism_opened ?
		prism_startup_stage(NULL, "1/4 Detecting boot storage") : NULL;
	/* Scan only after showing the marker. A missing device will return
	 * to the PRISM home menu rather than bypassing straight to Swiss. */
	needsDeviceChange = 1;
	needsRefresh = 1;
	
	//debugging stuff
	for(i = 0; i < EXI_CHANNEL_MAX; i++) {
		if(usb_isgeckoalive(i)) {
			swissSettings.enableUSBGecko = USBGECKO_MEMCARD_SLOT_A + i;
			init_wiiload_usb_thread(&swissSettings.enableUSBGecko);
			break;
		}
	}
	print_debug("Arena Size: %iKB\n",SYS_GetArenaSize()/1024);
	print_debug("DVD Drive Present? %s\n",swissSettings.hasDVDDrive?"Yes":"No");
	print_debug("GIT Commit: %s\n", GIT_COMMIT);
	print_debug("GIT Revision: %s\n", GIT_REVISION);
	
	// Go through all devices with FEAT_BOOT_DEVICE feature and set it as current if one is available
	for(i = 0; i < MAX_DEVICES; i++) {
		if(allDevices[i] != NULL && (allDevices[i]->features & FEAT_BOOT_DEVICE)) {
			print_debug("Testing device %s\n", allDevices[i]->deviceName);
			if(allDevices[i]->test()) {
				deviceHandler_setDeviceAvailable(allDevices[i], true);
				devices[DEVICE_CUR] = allDevices[i];
				break;
			}
		}
	}
	if(devices[DEVICE_CUR] != NULL) {
		print_debug("Detected %s\n", devices[DEVICE_CUR]->deviceName);
		if(!devices[DEVICE_CUR]->init(devices[DEVICE_CUR]->initial)) {
			/* PRISM owns normal startup: a boot-device autoload can
			 * chainload an older Swiss DOL before PRISM appears.
			 * Keep Swiss auto-DOL behavior for explicit cubeboot only. */
			if(swissSettings.cubebootInvoked &&
			   (devices[DEVICE_CUR]->features & FEAT_AUTOLOAD_DOL) &&
			   getenv("WIILOAD") == NULL) {
				load_auto_dol(argc, argv);
			}
			memcpy(&curDir, devices[DEVICE_CUR]->initial, sizeof(file_handle));
			needsDeviceChange = 0;
			DrawLoadBackdrop(devices[DEVICE_CUR]);
		}
	}

	// Scan here since some devices would already be initialised (faster)
	if (prism_opened)
		startup = prism_startup_stage(startup, "2/4 Detecting devices");
	populateDeviceAvailability();

	if (prism_opened)
		startup = prism_startup_stage(startup, "3/4 Reading Swiss settings");
	// Read Swiss settings
	if(!config_init(&config_migration)) {
		swissSettings.configDeviceId = DEVICE_ID_UNK;
	}
	else if(swissSettings.aveCompat != AVE_RVL_COMPAT && swissSettings.lastDTVStatus != getRawDTVStatus()) {
		show_settings(PAGE_GLOBAL, SET_AVE_COMPAT, NULL);
	}
	// If there's no default config device, set it to the first writable device available
	if(swissSettings.configDeviceId == DEVICE_ID_UNK) {
		for(i = 0; i < MAX_DEVICES; i++) {
			if(allDevices[i] != NULL && (allDevices[i]->features & FEAT_CONFIG_DEVICE) && deviceHandler_getDeviceAvailable(allDevices[i])) {
				swissSettings.configDeviceId = allDevices[i]->deviceUniqueId;
				print_debug("No default config device found, using [%s]\n", allDevices[i]->deviceName);
				if(!config_init(&config_migration)) {
					if(swissSettings.sramBoot != SYS_BOOT_PRODUCTION && !memcmp(DVDDiskID, &Swiss, sizeof(dvddiskid))) {
						uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_INFO, "You can set \223System Boot Mode\224 to Production\nto restore the GameCube logo screen."));
						wait_press_A();
						DrawDispose(msgBox);
					}
					show_settings(PAGE_GLOBAL, SET_CONFIG_DEV, NULL);
				}
				else if(swissSettings.aveCompat != AVE_RVL_COMPAT && swissSettings.lastDTVStatus != getRawDTVStatus()) {
					show_settings(PAGE_GLOBAL, SET_AVE_COMPAT, NULL);
				}
				break;
			}
		}
	}
	config_parse_args(argc, argv);
	config_update_environ();
	
	if (prism_opened)
		startup = prism_startup_stage(startup, "4/4 Applying video settings");
	// Swiss video mode force
	GXRModeObj *forcedMode = getVideoModeFromSwissSetting(swissSettings.uiVMode);
	DrawVideoMode(forcedMode);
	
	// Save settings to SRAM
	swissSettings.sram60Hz = getTVFormat() == VI_EURGB60;
	swissSettings.sramProgressive = getScanMode() == VI_PROGRESSIVE;
	if(in_range(swissSettings.aveCompat, GCDIGITAL_COMPAT, GCVIDEO_COMPAT)) {
		swissSettings.sramHOffset &= ~1;
	}
	VIDEO_SetAdjustingValues(swissSettings.sramHOffset, 0);
	updateSRAM(&swissSettings, true);
	
	if(swissSettings.initNetworkAtStart |= bba_requires_init()) {
		// Start up the BBA if it exists
		init_network_async();
	}
	
	DEVICEHANDLER_INTERFACE *device = getDeviceByLocation(LOC_DVD_CONNECTOR);
	if(device == &__device_dvd) {
		if(swissSettings.initDVDDriveAtStart) {
			DVD_Reset(DVD_RESETNONE);
			DVD_Resume();
		}
		// DVD Motor off setting
		if(swissSettings.stopMotor && DVD_GetDriveStatus() != DVD_STATE_PAUSING) {
			DVD_StopMotorAsync(&DVDStopMotorBlock, NULL);
		}
	}
	else if(device == &__device_flippy) {
		flippyversion *version = (flippyversion*)DVDDriveInfo->pad;
		u32 flippy_version = FLIPPY_VERSION(version->major, version->minor, version->build);
		if(flippy_version < FLIPPY_VERSION(FLIPPY_MINVER_MAJOR, FLIPPY_MINVER_MINOR, FLIPPY_MINVER_BUILD)) {
			uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_WARN, "A firmware update is required.\nflippydrive.com/updates"));
			wait_press_A();
			DrawDispose(msgBox);
		}
		else if(flippy_version < FLIPPY_VERSION(1,4,2) && (SYS_GetConsoleType() & SYS_CONSOLE_MASK) == SYS_CONSOLE_RETAIL) {
			uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_INFO, "A firmware update is available.\nflippydrive.com/updates"));
			wait_press_A();
			DrawDispose(msgBox);
		}
	}
	else if(device == &__device_gcloader) {
		if(gcloaderVersionStr != NULL) {
			if(strverscmp(swissSettings.gcloaderTopVersion, gcloaderVersionStr) < 0 || swissSettings.gcloaderHwVersion != gcloaderHwVersion) {
				strlcpy(swissSettings.gcloaderTopVersion, gcloaderVersionStr, sizeof(swissSettings.gcloaderTopVersion));
				swissSettings.gcloaderHwVersion = gcloaderHwVersion;
			}
			switch(gcloaderHwVersion) {
				case 1:
					if(!prism_opened && strverscmp(swissSettings.gcloaderTopVersion, "2.0.1") < 0) {
						find_existing_entry("gcldr:/GCLoader_Updater_2.0.1*.dol", true);
						uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_INFO, "A firmware update is available.\ngc-loader.com/firmware-updates"));
						wait_press_A();
						DrawDispose(msgBox);
					}
					break;
				case 2:
					if(!prism_opened && strverscmp(swissSettings.gcloaderTopVersion, "1.0.1") < 0) {
						find_existing_entry("gcldr:/GC_LOADER_HW2_UPDATER_1.0.1.dol", true);
						find_existing_entry("gcldr:/GC_LOADER_HW2_UPDATER_1.1.0*.dol", true);
						uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_INFO, "A firmware update is available.\ngc-loader.com/firmware-updates-hw2"));
						wait_press_A();
						DrawDispose(msgBox);
					}
					break;
			}
		}
	}
	
	/* PRISM takes priority over Swiss's automatic game/DOL launch.
	 * Otherwise a configured autoload can chainload away before the
	 * PRISM menu is ever reached. Classic Swiss continues afterward. */
	if (prism_opened) {
		DrawDispose(startup);
		prism_dashboard_bootstrap();
	}

	/* Leaving PRISM for Classic Swiss must show its menu, not launch
	 * a saved automatic DOL/game. Original autoload is retained for
	 * the special cubeboot path where PRISM does not open. */
	if(!prism_opened && swissSettings.autoload[0]) {
		// Check that the path in the autoload entry points at a device that has been detected
		print_debug("Autoload entry detected [%s]\n", swissSettings.autoload);
		find_existing_entry(&swissSettings.autoload[0], true);
	}
	else if(!prism_opened && swissSettings.recent[0][0] && swissSettings.recentListLevel > 1) {
		find_existing_entry(&swissSettings.recent[0][0], false);
	}

	if(swissSettings.cubebootInvoked) {
		return 0;
	}
	while(1) {
		menu_loop();
	}
	return 0;
}


// Checks if devices are available, prints name of device being detected for slow init devices
void populateDeviceAvailability() {
	uiDrawObj_t *msgBox = DrawPublish(DrawProgressBar(true, 0, "Detecting devices\205\nThis can be skipped by holding B next time"));
	while(DVD_GetCmdBlockStatus(&DVDInquiryBlock) == DVD_STATE_BUSY) {
		if(DVD_LowGetCoverStatus() == DVD_COVER_OPEN) {
			break;
		}
		if(padsButtonsHeld() & BUTTON_B) {
			DVD_CancelAsync(&DVDInquiryBlock, NULL);
			break;
		}
	}
	int i;
	for(i = 0; i < MAX_DEVICES; i++) {
		if(allDevices[i] != NULL && !deviceHandler_getDeviceAvailable(allDevices[i])) {
			print_debug("Checking device availability for device %s\n", allDevices[i]->deviceName);
			deviceHandler_setDeviceAvailable(allDevices[i], allDevices[i]->test());
		}
		if(allDevices[i] == &__device_sd_a && allDevices[i]->location == LOC_MEMCARD_SLOT_A && !CARD_Probe(CARD_SLOTB) && deviceHandler_getDeviceAvailable(allDevices[i])) {
			sprintf(txtbuffer, "Please move %s to Slot B", allDevices[i]->deviceName);
			uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_INFO, txtbuffer));
			wait_press_A();
			DrawDispose(msgBox);
			deviceHandler_setDeviceAvailable(allDevices[i], allDevices[i]->test());
			needsDeviceChange = !deviceHandler_getDeviceAvailable(devices[DEVICE_CUR]);
		}
	}
	DrawDispose(msgBox);
}

void refreshDeviceCode(bool subdevice) {
	switch(DVD_GetCmdBlockStatus(&DVDInquiryBlock)) {
		case DVD_STATE_END:
		case DVD_STATE_FATAL_ERROR:
		case DVD_STATE_CANCELED:
			DVD_SetUserData(&DVDInquiryBlock, &DVDDriveInfo[subdevice]);
			DVD_InquiryAsync(&DVDInquiryBlock, &DVDDriveInfo[subdevice], driveInfoCallback);
			break;
	}
}





