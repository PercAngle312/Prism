#include <stdio.h>
#include <gccore.h>		/*** Wrapper to include common libogc headers ***/
#include <ogcsys.h>		/*** Needed for console support ***/
#include <ogc/color.h>
#include <ogc/dvdlow.h>
#include <ogc/exi.h>
#include <ogc/lwp.h>
#include <ogc/lwp_watchdog.h>
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
#include "gui/prism_theme.h"
#include "gui/prism_autoscroll.h"
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

/* PRISM's opaque composition uses exact bounds; disposing it reveals Swiss. */
static uiDrawObj_t *prism_draw_panel_background(const char *subtitle, GXTexObj *background)
{
    uiDrawObj_t *panel = DrawContainer();
    DrawAddChild(panel, DrawSolidBox(0, 0, 640, 480, (GXColor){17, 24, 43, 255}));
    static u16 theme_pixels[PRISM_THEME_SIZE * PRISM_THEME_SIZE] __attribute__((aligned(32)));
    static GXTexObj theme_texture;
    static int theme_ready;
    if (!theme_ready) {
        prism_theme_fill(theme_pixels);
        DCFlushRange(theme_pixels, sizeof(theme_pixels));
        GX_InitTexObj(&theme_texture, theme_pixels, PRISM_THEME_SIZE, PRISM_THEME_SIZE,
            GX_TF_RGB565, GX_CLAMP, GX_CLAMP, GX_FALSE);
        GX_InitTexObjLOD(&theme_texture, GX_LINEAR, GX_LINEAR, 0, 0, 0, GX_FALSE, GX_FALSE, GX_ANISO_1);
        theme_ready = 1;
    }
    DrawAddChild(panel, DrawTexObj(&theme_texture, 0, 0, 640, 480, 0, 0, 1, 0, 1, 0));
    if (background) DrawAddChild(panel, DrawTexObj(background, 0, 0, 640, 480, 0, 0, 1, 0, 1, 0));
    DrawAddChild(panel, DrawSolidBox(0, 0, 640, 116, (GXColor){42, 47, 76, 255}));
    DrawAddChild(panel, DrawSolidBox(0, PRISM_FOOTER_LINE_Y, 640, 480, (GXColor){42, 78, 112, 255}));
    DrawAddChild(panel, DrawSolidBox(0, PRISM_FOOTER_LINE_Y, 640, PRISM_FOOTER_LINE_Y + 2, (GXColor){115, 176, 212, 255}));
    DrawAddChild(panel, DrawStyledLabel(PRISM_LOGO_X, PRISM_LOGO_Y, "PRISM",
        0.85f, ALIGN_LEFT, (GXColor){233, 241, 247, 255}));
    DrawAddChild(panel, DrawStyledLabel(585, PRISM_LOGO_Y + 8,
        "Build " GIT_COMMIT, 0.45f, ALIGN_RIGHT, (GXColor){143, 162, 183, 255}));
    DrawAddChild(panel, DrawStyledLabel(PRISM_LOGO_X, PRISM_SUBTITLE_Y,
        subtitle, 0.72f, ALIGN_LEFT, (GXColor){143, 162, 183, 255}));
    return panel;
}

static uiDrawObj_t *prism_draw_panel(const char *subtitle)
{
    return prism_draw_panel_background(subtitle, NULL);
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

static int prism_draw_synopsis(uiDrawObj_t *panel, const char *text, int *scroll)
{
    PrismTextMeasure measure = {PRISM_TEXT_WIDTH, 0.68f};
    const char *cursor = text;
    char line[128];
    int lines = 0;
    while (prism_text_next(&cursor, line, sizeof(line), prism_text_fits, &measure)) ++lines;
    int maximum = lines > 6 ? lines - 6 : 0;
    if (*scroll > maximum) *scroll = maximum;
    cursor = text;
    for (int skipped = 0; skipped < *scroll; ++skipped)
        prism_text_next(&cursor, line, sizeof(line), prism_text_fits, &measure);
    for (int row = 0; row < 6 && prism_text_next(&cursor, line, sizeof(line), prism_text_fits, &measure); ++row)
        DrawAddChild(panel, DrawStyledLabel(PRISM_TEXT_X, PRISM_SYNOPSIS_Y + row * 22,
            line, 0.68f, ALIGN_LEFT, (GXColor){231, 226, 242, 255}));
    return maximum;
}

/* Each hint owns a bounded cell, so long labels cannot collide on a CRT. */
static void prism_draw_hint(uiDrawObj_t *panel, int x, int y, int width,
                             const char *text, GXColor colour)
{
    float scale = GetTextScaleToFitInWidth(text, width - 8);
    if (scale > 0.62f) scale = 0.62f;
    DrawAddChild(panel, DrawStyledLabel(x + width / 2, y, text,
        scale, ALIGN_CENTER, colour));
}

static void prism_draw_library_hints(uiDrawObj_t *panel, int y, int details)
{
    if (details) {
        prism_draw_hint(panel, 24, y, 112, "UP/DN: Read", (GXColor){190, 181, 218, 255});
        prism_draw_hint(panel, 138, y, 110, "A: Start", (GXColor){165, 229, 204, 255});
        prism_draw_hint(panel, 250, y, 112, "X: Cheats", (GXColor){190, 210, 218, 255});
        prism_draw_hint(panel, 364, y, 122, "Y: Settings", (GXColor){190, 210, 218, 255});
        prism_draw_hint(panel, 488, y, 118, "B: Games", (GXColor){233, 180, 204, 255});
    } else {
        prism_draw_hint(panel, 44, y, 184, "LEFT/RIGHT: Browse", (GXColor){190, 210, 218, 255});
        prism_draw_hint(panel, 228, y, 110, "A: Open", (GXColor){165, 229, 204, 255});
        prism_draw_hint(panel, 338, y, 120, "Z: Systems", (GXColor){190, 210, 218, 255});
        prism_draw_hint(panel, 458, y, 138, "START: Settings", (GXColor){233, 180, 204, 255});
    }

}

static uiDrawObj_t *prism_draw_notice(const char *title, const char *body,
                                      const char *footer)
{
    uiDrawObj_t *panel = prism_draw_panel(title);
    DrawAddChild(panel, DrawSolidBox(54, 150, 586, 370, (GXColor){22, 33, 48, 255}));
    DrawAddChild(panel, DrawSolidBox(54, 150, 58, 370, (GXColor){77, 219, 201, 255}));
    prism_draw_wrapped(panel, title, 78, 176, 484, 0.95f, 1, 25, (GXColor){233, 241, 247, 255});
    prism_draw_wrapped(panel, body, 78, 220, 484, 0.75f, 5, 25, (GXColor){185, 200, 225, 255});
    prism_draw_hint(panel, 54, PRISM_FOOTER_LABELS_Y, 532, footer, (GXColor){113, 223, 181, 255});
    return panel;
}

static void prism_show_notice(const char *title, const char *body)
{
    const u32 dismiss = BUTTON_A | BUTTON_B | BUTTON_START;
    uiDrawObj_t *panel = DrawPublish(prism_draw_notice(title, body, "A/B/START: Return"));
    /* Opening and closing both require a released button. */
    while (padsButtonsHeld() & dismiss) VIDEO_WaitVSync();
    while (!(padsButtonsHeld() & dismiss)) VIDEO_WaitVSync();
    while (padsButtonsHeld() & dismiss) VIDEO_WaitVSync();
    DrawDispose(panel);
}

/* A compact cover shelf: central selection stays prominent on a 4:3 TV. */
static void prism_draw_cover_card(uiDrawObj_t *panel, const PrismLibraryGame *game,
                                   GXTexObj *texture, int has_cover,
                                   int x, int y, int width, int height)
{
    if (!game) return;
    DrawAddChild(panel, DrawSolidBox(x, y, x + width, y + height,
        (GXColor){28, 41, 58, 255}));
    if (has_cover) {
        DrawAddChild(panel, DrawTexObj(texture, x, y, width, height,
            0, 0.0f, 1.0f, 0.0f, 1.0f, 0));
        /* Reuse the pinned cover pixels. Reflect only the bottom of the
         * artwork, and fade it before the footer without allocating textures. */
        int reflection_y = y + height + 2;
        int reflection_height = 40;
        if (reflection_y + reflection_height > PRISM_FOOTER_LINE_Y - 8)
            reflection_height = PRISM_FOOTER_LINE_Y - 8 - reflection_y;
        if (reflection_height > 0) {
            DrawAddChild(panel, DrawTexObj(texture, x, reflection_y, width, reflection_height,
                0, 0.0f, 1.0f, 1.0f, 1.0f - reflection_height / (float)height, 0));
            for (int band = 0; band < 4; ++band) {
                int alpha = 190 + band * 20;
                /* Swiss uses premultiplied alpha for these solid fills. */
                for (int column = 0; column < 2; ++column) {
                    int sample_x = x + (column * 2 + 1) * width / 4;
                    if (sample_x < 0) sample_x = 0;
                    if (sample_x > 639) sample_x = 639;
                    int sample_y = reflection_y + (band * 2 + 1) * reflection_height / 8;
                    u16 theme = prism_theme_pixel(sample_x * 63 / 639, sample_y * 63 / 479);
                    GXColor fade = {(theme >> 11) * 255 / 31 * alpha / 255,
                        ((theme >> 5) & 63) * 255 / 63 * alpha / 255,
                        (theme & 31) * 255 / 31 * alpha / 255, alpha};
                    DrawAddChild(panel, DrawSolidBox(x + column * width / 2, reflection_y + band * reflection_height / 4,
                        x + (column + 1) * width / 2, reflection_y + (band + 1) * reflection_height / 4, fade));
                }
            }
        }
    }
    else {
        prism_draw_wrapped(panel, game->title, x + 8, y + 28, width - 16,
            0.65f, 4, 18, (GXColor){204, 218, 239, 255});
        DrawAddChild(panel, DrawStyledLabel(x + width / 2, y + height - 24,
            "NO COVER", 0.55f, ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
    }
}

static void prism_draw_coverflow(uiDrawObj_t *panel, const PrismLibrary *library,
                                  GXTexObj *textures[5], int available[5])
{
    /* Aurora-style continuous shelf: five covers, clipped edge cards and a
     * prominent centre. Draw the selected card last without adding frames. */
    const int side_x[] = {PRISM_FLOW_LEFT_X - PRISM_FLOW_SIDE_WIDTH - 4,
        PRISM_FLOW_LEFT_X, PRISM_FLOW_RIGHT_X,
        PRISM_FLOW_RIGHT_X + PRISM_FLOW_SIDE_WIDTH + 4};
    const int positions[] = {0, 1, 3, 4};
    for (int side = 0; side < 4; ++side) {
        int position = positions[side];
        prism_draw_cover_card(panel, prism_library_neighbor(library, position - 2),
            textures[position], available[position], side_x[side], PRISM_FLOW_SIDE_Y,
            PRISM_FLOW_SIDE_WIDTH, PRISM_FLOW_SIDE_HEIGHT);
    }
    prism_draw_cover_card(panel, prism_library_selected(library), textures[2], available[2],
        PRISM_FLOW_CENTER_X, PRISM_FLOW_CENTER_Y,
        PRISM_LAYOUT_COVER_WIDTH, PRISM_LAYOUT_COVER_HEIGHT);
}

static uiDrawObj_t *prism_draw_home(uiDrawObj_t *previous, int selection)
{
    static const char *titles[] = {"Return to games", "Classic Swiss", "Offline catalog", "About PRISM"};
    static const char *descriptions[] = {
        "Browse your games. View details and launch through Swiss.",
        "Open Swiss for devices, settings, cheats and advanced options.",
        "Explore the games and artwork in your offline library pack.",
        "An original GameCube dashboard. Built on Swiss."
    };
    uiDrawObj_t *panel = prism_draw_panel("SETTINGS");
    for (int tile = 0; tile < 4; ++tile) {
        int x = PRISM_HOME_X + (tile % 2) * PRISM_HOME_STRIDE_X;
        int y = PRISM_HOME_Y + (tile / 2) * PRISM_HOME_STRIDE_Y;
        int focused = tile == selection;
        DrawAddChild(panel, DrawSolidBox(x - 2, y - 2,
            x + PRISM_HOME_WIDTH + 2, y + PRISM_HOME_HEIGHT + 2,
            focused ? (GXColor){77, 219, 201, 255} : (GXColor){39, 53, 70, 255}));
        DrawAddChild(panel, DrawSolidBox(x, y, x + PRISM_HOME_WIDTH, y + PRISM_HOME_HEIGHT,
            focused ? (GXColor){30, 56, 65, 255} : (GXColor){22, 33, 48, 255}));
        DrawAddChild(panel, DrawStyledLabel(x + 16, y + 16, titles[tile], 0.88f,
            ALIGN_LEFT, (GXColor){233, 241, 247, 255}));
        prism_draw_wrapped(panel, descriptions[tile], x + 16, y + 47,
            PRISM_HOME_WIDTH - 32, 0.62f, 3, 18, (GXColor){170, 189, 203, 255});
    }
    prism_draw_hint(panel, 44, PRISM_FOOTER_LABELS_Y, 136, "D-Pad: Select", (GXColor){185, 200, 225, 255});
    prism_draw_hint(panel, 180, PRISM_FOOTER_LABELS_Y, 92, "A: Open", (GXColor){113, 223, 181, 255});
    prism_draw_hint(panel, 272, PRISM_FOOTER_LABELS_Y, 114, "Z: Systems", (GXColor){134, 184, 245, 255});
    prism_draw_hint(panel, 386, PRISM_FOOTER_LABELS_Y, 210, "B/START: Games", (GXColor){239, 154, 157, 255});
    return DrawRepublish(previous, panel);
}

/* Keep a visible checkpoint while Swiss initializes storage and settings. */
static uiDrawObj_t *prism_startup_stage(uiDrawObj_t *previous, const char *stage)
{
	uiDrawObj_t *panel = DrawContainer();
	DrawAddChild(panel, DrawEmptyColouredBox(55, 145, 585, 335,
		(GXColor){18, 24, 42, 255}));
	DrawAddChild(panel, DrawStyledLabel(320, 195,
		"PRISM", 1.5f, ALIGN_CENTER,
		(GXColor){225, 235, 255, 255}));
	DrawAddChild(panel, DrawStyledLabel(320, 245, stage, 0.9f, ALIGN_CENTER,
		(GXColor){170, 194, 229, 255}));
	DrawAddChild(panel, DrawStyledLabel(320, 295,
		"Build " GIT_COMMIT, 0.8f, ALIGN_CENTER,
		(GXColor){170, 194, 229, 255}));
	return DrawRepublish(previous, panel);
}

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
 * Launch through Swiss's existing file preparation with direct game startup.
 */
static void prism_system_libraries(void);
static int prism_settings_menu(void);

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
    void *background_pixels = NULL;
    GXTexObj background_texture;
    char background_id[7] = "";
    int has_background = 0;
    uiDrawObj_t *screen = NULL;
    unsigned displayed_slots = 0;
    int details = 0, systems_selected = 0, synopsis_scroll = 0, synopsis_maximum = 0;
    PrismAutoScroll synopsis_auto = {0};
    u32 last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_LEFT | BUTTON_RIGHT |
               BUTTON_X | BUTTON_Y | BUTTON_L | BUTTON_R | BUTTON_Z | BUTTON_UP | BUTTON_DOWN;
    if (!device || !device->initial ||
        snprintf(folder, sizeof(folder), "%sgames", device->initial->name) >= (int)sizeof(folder)) {
        if (quiet_if_empty) return 0;
        prism_show_notice("No game storage", "No active game storage was found. Open Classic Swiss to check your device connection and storage.");
        return 0;
    }
    library = malloc(sizeof(*library));
    if (!library) { prism_show_notice("Library unavailable", "There is not enough free memory to open the game library."); return 0; }
    paths = malloc(sizeof(*paths));
    if (!paths) { free(library); prism_show_notice("Library unavailable", "There is not enough free memory to scan game folders."); return 0; }
    uiDrawObj_t *scan_progress = DrawPublish(prism_draw_notice("Scanning games",
        "Looking for ISO/GCM files in /games and its game folders.", "Please wait"));
    int scanned = prism_installed_scan(device, folder, library, paths);
    DrawDispose(scan_progress);
    if (!scanned || !library->count) {
        if (quiet_if_empty) { free(paths); free(library); return 0; }
        prism_show_notice("No installed games", "No ISO/GCM files were found in /games or its game folders. Use Classic Swiss to check your game storage.");
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
    char storage_info[96] = "Storage information unavailable";
    device_info *storage = device->info ? device->info(device->initial) : NULL;
    if (storage && storage->totalSpace)
        snprintf(storage_info, sizeof(storage_info), "%.1f GiB total  /  %.1f GiB free",
            (double)storage->totalSpace / 1073741824.0, (double)storage->freeSpace / 1073741824.0);
    /* A failed cache allocation still permits title-only browsing/launching. */
    for (;;) {
        int has_cover = 0;
        int slots[5] = {-1, -1, -1, -1, -1};
        int shelf_covers[5] = {0, 0, 0, 0, 0};
        GXTexObj *cover_texture = NULL;
        GXTexObj *shelf_textures[5] = {NULL, NULL, NULL, NULL, NULL};
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
            for (int position = 0; position < 5; ++position) {
                if (details && position != 2) continue;
                const PrismLibraryGame *candidate = prism_library_neighbor(library, position - 2);
                if (!candidate) continue;
                slots[position] = prism_cached_cover(covers, metadata_device, pack_path,
                    candidate->id, displayed_slots | incoming_slots);
                if (slots[position] >= 0) incoming_slots |= 1u << slots[position];
            }
            for (int position = 0; position < 5; ++position) {
                int slot = slots[position];
                if (slot >= 0) {
                    shelf_textures[position] = &covers->textures[slot];
                    shelf_covers[position] = covers->policy.entries[slot].state == PRISM_CACHE_READY;
                }
            }
            cover_texture = shelf_textures[2];
            has_cover = shelf_covers[2];
        }

        snprintf(heading, sizeof(heading), "GAMES  |  %lu / %lu",
            (unsigned long)(library->selected + 1),
            (unsigned long)library->count);
        if (details && strcmp(background_id, game->id)) {
            /* Details can only be entered from the shelf, whose frame does
             * not reference this buffer. Keep it alive until frame disposal. */
            if (!background_pixels) background_pixels = memalign(32, PRISM_BACKGROUND_BYTES);
            has_background = background_pixels && prism_pack_device_background(metadata_device, game->id,
                background_pixels, PRISM_BACKGROUND_BYTES);
            strlcpy(background_id, game->id, sizeof(background_id));
            if (has_background) {
                DCFlushRange(background_pixels, PRISM_BACKGROUND_BYTES);
                GX_InitTexObj(&background_texture, background_pixels, PRISM_BACKGROUND_WIDTH, PRISM_BACKGROUND_HEIGHT,
                    GX_TF_RGB565, GX_CLAMP, GX_CLAMP, GX_FALSE);
                GX_InitTexObjLOD(&background_texture, GX_LINEAR, GX_LINEAR, 0, 0, 0, GX_FALSE, GX_FALSE, GX_ANISO_1);
            }
        }
        panel = prism_draw_panel_background(heading, details && has_background ? &background_texture : NULL);
        DrawAddChild(panel, DrawStyledLabel(585, PRISM_SUBTITLE_Y, storage_info,
            0.48f, ALIGN_RIGHT, (GXColor){192, 181, 219, 255}));
        if (systems_selected) {
            DrawAddChild(panel, DrawSolidBox(232, 146, 408, 352, (GXColor){62, 46, 103, 255}));
            DrawAddChild(panel, DrawStyledLabel(320, 226, "SYSTEMS", 1.0f, ALIGN_CENTER, (GXColor){239, 232, 255, 255}));
            DrawAddChild(panel, DrawStyledLabel(320, 272, "A: Browse platforms", 0.6f, ALIGN_CENTER, (GXColor){202, 190, 226, 255}));
        } else if (!details) {
            prism_draw_coverflow(panel, library, shelf_textures, shelf_covers);
        } else {
            DrawAddChild(panel, DrawSolidBox(PRISM_COVER_X, PRISM_COVER_Y,
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
            synopsis_maximum = prism_draw_synopsis(panel, synopsis[0] ? synopsis : "Description not available for this game.", &synopsis_scroll);
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
            scan_status[0] = '\0';
        float status_scale = GetTextScaleToFitInWidth(scan_status,
            details ? PRISM_STATUS_WIDTH : 500);
        if (status_scale > 0.6f) status_scale = 0.6f;
        if (scan_status[0]) DrawAddChild(panel, DrawStyledLabel(details ? PRISM_STATUS_X : 320,
            details ? PRISM_STATUS_Y : PRISM_FLOW_STATUS_Y, scan_status, status_scale,
            details ? ALIGN_LEFT : ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
        prism_draw_library_hints(panel, PRISM_FOOTER_LABELS_Y, details);
        screen = DrawRepublish(screen, panel);
        panel = screen;
        displayed_slots = incoming_slots;
        for (;;) {
            held = padsButtonsHeld();
            pressed = held & ~last;
            last = held;
            if (pressed & BUTTON_B) {
                if (details) { details = 0; synopsis_scroll = 0; break; }
            }
            if (!details && (pressed & BUTTON_Z)) {
                DrawDispose(screen); screen = NULL; displayed_slots = 0;
                prism_system_libraries();
                last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_Z;
                break;
            }
            if (!details && (pressed & BUTTON_START)) {
                DrawDispose(screen); screen = NULL; displayed_slots = 0;
                if (!prism_settings_menu()) {
                    last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_Z;
                    break;
                }
                prism_free_cover_cache(covers);
                free(background_pixels);
                free(paths);
                free(library);
                return 2;
            }
            if (details && (pressed & (BUTTON_X | BUTTON_Y))) {
                /* Enter the existing Swiss per-game menu without autoboot.
                 * Swiss owns cheat and individual game settings management;
                 * PRISM does not alter cheat/config files directly. */
                char options_path[PATHNAME_MAX];
                if (!prism_installed_resolve(device, paths, game,
                                              options_path, sizeof(options_path))) {
                    prism_show_notice("Game changed", "The selected game is no longer available. Check your storage.");
                    last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_X | BUTTON_Y;
                    continue;
                }
                DrawDispose(screen); screen = NULL; displayed_slots = 0;
                while (padsButtonsHeld() & (BUTTON_X | BUTTON_Y)) VIDEO_WaitVSync();
                int saved_auto_boot = swissSettings.autoBoot;
                swissSettings.autoBoot = 0;
                int options_result = find_existing_entry_exact(options_path, true);
                swissSettings.autoBoot = saved_auto_boot;
                if (options_result)
                    prism_show_notice("Game options unavailable", "Swiss could not open this game's options.");
                last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_X | BUTTON_Y;
                break;
            }
            if (pressed & BUTTON_A) {
                if (systems_selected) {
                    DrawDispose(screen); screen = NULL; displayed_slots = 0;
                    prism_system_libraries();
                    last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_Z;
                    break;
                }
                if (!details) {
                    details = 1; synopsis_scroll = 0;
                    prism_scroll_begin(&synopsis_auto, ticks_to_millisecs(gettime()));
                    break;
                }
                char launch_path[PATHNAME_MAX];
                /* Recheck identity before direct native Swiss launch. */
                if (!prism_installed_resolve(device, paths, game,
                                              launch_path, sizeof(launch_path))) {
                    prism_show_notice("Game changed", "The game file changed or could not be read. Check your game storage before trying again.");
                    last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_X | BUTTON_L | BUTTON_R;
                    continue;
                }
                DrawDispose(screen);
                screen = NULL;
                displayed_slots = 0;
                panel = NULL;
                while (padsButtonsHeld() & BUTTON_A) VIDEO_WaitVSync();
                int auto_boot = swissSettings.autoBoot;
                swissSettings.autoBoot = 1;
                int result = find_existing_entry_exact(launch_path, true);
                swissSettings.autoBoot = auto_boot;
                if (result != 0) {
                    prism_show_notice("Game unavailable", "Swiss could not locate the selected game. Check your game storage before trying again.");
                }
                last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START;
                break; /* Cancellation/errors redraw the same PRISM selection. */
            }
            if (details) {
                if (pressed & BUTTON_DOWN) {
                    if (synopsis_scroll < synopsis_maximum) ++synopsis_scroll;
                    prism_scroll_manual(&synopsis_auto, ticks_to_millisecs(gettime()));
                    break;
                }
                if (pressed & BUTTON_UP) {
                    if (synopsis_scroll) --synopsis_scroll;
                    prism_scroll_manual(&synopsis_auto, ticks_to_millisecs(gettime()));
                    break;
                }
                if (!(held & (BUTTON_UP | BUTTON_DOWN)) &&
                    prism_scroll_tick(&synopsis_auto, ticks_to_millisecs(gettime()),
                                      synopsis_maximum, &synopsis_scroll)) break;
                VIDEO_WaitVSync();
                continue;
            }
            if (pressed & (BUTTON_L | BUTTON_R)) {
                systems_selected = 0;
                prism_library_step(library, (pressed & BUTTON_R) ? 10 : -10);
                break;
            }
            if (pressed & BUTTON_RIGHT) {
                if (systems_selected) { systems_selected = 0; library->selected = 0; }
                else if (library->selected + 1 == library->count) systems_selected = 1;
                else prism_library_move(library, 1);
                break;
            }
            if (pressed & BUTTON_LEFT) {
                if (systems_selected) { systems_selected = 0; library->selected = library->count - 1; }
                else if (!library->selected) systems_selected = 1;
                else prism_library_move(library, -1);
                break;
            }
            VIDEO_WaitVSync();
        }
        /* Retain this frame during metadata/art reads for the next one. */
    }
    if (screen) DrawDispose(screen);
    prism_free_cover_cache(covers);
    free(background_pixels);
    free(paths);
    free(library);
    return 1;
}

/* Catalog metadata never implies that a game is installed. Emulator packs
 * can open their configured DOL, with ROM selection in the emulator itself. */
static void prism_catalog_browser(DEVICEHANDLER_INTERFACE *device, const char *path,
                                  u32 count, const char *system_name, const char *emulator_path)
{
    u32 position = 0;
    u32 last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_LEFT | BUTTON_RIGHT | BUTTON_L | BUTTON_R;
    uiDrawObj_t *screen = NULL;
    PrismRuntimeCoverCache *covers = calloc(1, sizeof(*covers));
    unsigned displayed_slots = 0;
    if (!count) { prism_free_cover_cache(covers); return; }
    for (;;) {
        PrismPackEntry entry;
        char title[PRISM_PACK_TITLE_MAX + 1];
        char synopsis[PRISM_PACK_SYNOPSIS_MAX + 1];
        char heading[100];
        u32 pressed, held;
        if (!prism_pack_device_entry(device, path, position, &entry,
                                     title, sizeof(title), synopsis, sizeof(synopsis))) {
            prism_show_notice("Catalog unavailable", "The library pack could not be read. Check library.prism on your config storage.");
            break;
        }
        int slot = covers ? prism_cached_cover(covers, device, path, entry.id, displayed_slots) : -1;
        int has_cover = slot >= 0 && covers->policy.entries[slot].state == PRISM_CACHE_READY;
        snprintf(heading, sizeof(heading), "%s  |  %lu / %lu", system_name ? system_name : "OFFLINE CATALOG",
            (unsigned long)(position + 1), (unsigned long)count);
        uiDrawObj_t *panel = prism_draw_panel(heading);
        DrawAddChild(panel, DrawStyledLabel(585, PRISM_SUBTITLE_Y,
            entry.id, 0.72f, ALIGN_RIGHT, (GXColor){170, 194, 229, 255}));
        DrawAddChild(panel, DrawSolidBox(PRISM_COVER_X, PRISM_COVER_Y,
            PRISM_COVER_X + PRISM_LAYOUT_COVER_WIDTH, PRISM_COVER_Y + PRISM_LAYOUT_COVER_HEIGHT,
            (GXColor){28, 41, 58, 255}));
        if (has_cover)
            DrawAddChild(panel, DrawTexObj(&covers->textures[slot], PRISM_COVER_X, PRISM_COVER_Y,
                PRISM_LAYOUT_COVER_WIDTH, PRISM_LAYOUT_COVER_HEIGHT, 0, 0, 1, 0, 1, 0));
        else
            DrawAddChild(panel, DrawStyledLabel(PRISM_COVER_X + PRISM_LAYOUT_COVER_WIDTH / 2,
                PRISM_COVER_Y + PRISM_LAYOUT_COVER_HEIGHT / 2, "NO COVER", 0.72f,
                ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
        prism_draw_wrapped(panel, title, PRISM_TEXT_X, PRISM_TITLE_Y,
            PRISM_TEXT_WIDTH, 0.9f, 2, 25, (GXColor){225, 235, 255, 255});
        DrawAddChild(panel, DrawStyledLabel(PRISM_TEXT_X, PRISM_SYNOPSIS_HEADING_Y,
            "SYNOPSIS", 0.72f, ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
        prism_draw_wrapped(panel, synopsis[0] ? synopsis : "Description not available for this game.",
            PRISM_TEXT_X, PRISM_SYNOPSIS_Y, PRISM_TEXT_WIDTH, 0.68f,
            6, 22, (GXColor){204, 218, 239, 255});
        int rom_status = emulator_path ? prism_pack_device_rom_status(device, path, entry.id) : -1;
        DrawAddChild(panel, DrawStyledLabel(PRISM_STATUS_X, PRISM_STATUS_Y,
            emulator_path ? (rom_status > 0 ? "ROM file found / choose inside the emulator" :
                rom_status == 0 ? "Mapped ROM missing on config storage" : "No ROM mapping / choose inside the emulator") :
                "Catalog entry / not an installed-game check", 0.55f,
            ALIGN_LEFT, (GXColor){143, 162, 183, 255}));
        prism_draw_hint(panel, 44, PRISM_FOOTER_LABELS_Y, 340, "LEFT/RIGHT: Browse", (GXColor){185, 200, 225, 255});
        if (emulator_path) {
            prism_draw_hint(panel, 384, PRISM_FOOTER_LABELS_Y, 120, "A: Emulator", (GXColor){113, 223, 181, 255});
            prism_draw_hint(panel, 504, PRISM_FOOTER_LABELS_Y, 92, "B: Return", (GXColor){239, 154, 157, 255});
        } else
            prism_draw_hint(panel, 384, PRISM_FOOTER_LABELS_Y, 212, "B/START: Return", (GXColor){239, 154, 157, 255});
        screen = DrawRepublish(screen, panel);
        displayed_slots = slot >= 0 ? 1u << slot : 0;
        for (;;) {
            held = padsButtonsHeld();
            pressed = held & ~last;
            last = held;
            if (pressed & (BUTTON_B | BUTTON_START)) goto done;
            if (emulator_path && (pressed & BUTTON_A)) {
                /* Native Swiss owns DOL validation and chainloading. These
                 * entries deliberately open its menu, never fake ROM autoboot. */
                char target[PATHNAME_MAX];
                strlcpy(target, emulator_path, sizeof(target));
                DrawDispose(screen); screen = NULL;
                prism_free_cover_cache(covers); covers = NULL;
                displayed_slots = 0;
                int saved_auto_boot = swissSettings.autoBoot;
                swissSettings.autoBoot = 0;
                int error = find_existing_entry_exact(target, true);
                swissSettings.autoBoot = saved_auto_boot;
                if (error)
                    prism_show_notice("Emulator unavailable", "Copy the GameCube emulator DOL to the matching system name in /swiss/prism/emulators/ on your config storage.");
                covers = calloc(1, sizeof(*covers));
                last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START;
                break;
            }
            if (pressed & (BUTTON_L | BUTTON_R)) {
                if (pressed & BUTTON_R) position = count - position > 10 ? position + 10 : count - 1;
                else position = position > 10 ? position - 10 : 0;
                break;
            }
            if (pressed & BUTTON_RIGHT) { position = (position + 1) % count; break; }
            if (pressed & BUTTON_LEFT) { position = (position + count - 1) % count; break; }
            VIDEO_WaitVSync();
        }
    }
done:
    if (screen) DrawDispose(screen);
    prism_free_cover_cache(covers);
}

/* Separate packs retain the existing indexed cover/synopsis format. A
 * system catalog is curated metadata, not proof that its ROMs are installed. */
static void prism_system_libraries(void)
{
    static const char *names[] = {"Nintendo 64", "NES", "Super Nintendo", "Game Boy", "Game Boy Advance", "Mega Drive"};
    static const char *keys[] = {"n64", "nes", "snes", "gb", "gba", "megadrive"};
    int selection = 0;
    u32 last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_Z;
    uiDrawObj_t *screen = NULL;
    for (;;) {
        uiDrawObj_t *panel = prism_draw_panel("EMULATOR LIBRARIES");
        for (int i = 0; i < 6; ++i) {
            int x = 54 + (i % 2) * 278, y = 140 + (i / 2) * 84;
            GXColor fill = i == selection ? (GXColor){32, 78, 83, 255} : (GXColor){22, 33, 48, 255};
            DrawAddChild(panel, DrawSolidBox(x, y, x + 254, y + 66, fill));
            if (i == selection)
                DrawAddChild(panel, DrawSolidBox(x, y, x + 4, y + 66, (GXColor){77, 219, 201, 255}));
            prism_draw_wrapped(panel, names[i], x + 14, y + 23, 228, 0.85f, 1, 22, (GXColor){233, 241, 247, 255});
        }
        prism_draw_hint(panel, 44, PRISM_FOOTER_LABELS_Y, 180, "D-Pad: System", (GXColor){185, 200, 225, 255});
        prism_draw_hint(panel, 224, PRISM_FOOTER_LABELS_Y, 180, "A: Library", (GXColor){113, 223, 181, 255});
        prism_draw_hint(panel, 404, PRISM_FOOTER_LABELS_Y, 192, "B/START: Return", (GXColor){239, 154, 157, 255});
        screen = DrawRepublish(screen, panel);
        for (;;) {
            u32 held = padsButtonsHeld(), pressed = held & ~last;
            last = held;
            if (pressed & (BUTTON_B | BUTTON_START)) goto finished;
            if (pressed & (BUTTON_LEFT | BUTTON_RIGHT)) { selection ^= 1; break; }
            if (pressed & BUTTON_UP) { selection = (selection + 4) % 6; break; }
            if (pressed & BUTTON_DOWN) { selection = (selection + 2) % 6; break; }
            if (pressed & BUTTON_A) {
                DEVICEHANDLER_INTERFACE *device = devices[DEVICE_CONFIG];
                char pack[PATHNAME_MAX], emulator[PATHNAME_MAX], body[192];
                u32 count = 0;
                if (device && device->initial &&
                    snprintf(pack, sizeof(pack), "%sswiss/prism/emulators/%s.prism", device->initial->name, keys[selection]) < sizeof(pack) &&
                    snprintf(emulator, sizeof(emulator), "%sswiss/prism/emulators/%s.dol", device->initial->name, keys[selection]) < sizeof(emulator) &&
                    prism_pack_device_count(device, pack, &count) && count) {
                    DrawDispose(screen); screen = NULL;
                    prism_catalog_browser(device, pack, count, names[selection], emulator);
                } else {
                    snprintf(body, sizeof(body), "Export your %s project from PRISM Studio as %s.prism. Copy it to /swiss/prism/emulators/ on your config storage.", names[selection], keys[selection]);
                    prism_show_notice("System library not found", body);
                }
                last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START;
                break;
            }
            VIDEO_WaitVSync();
        }
    }
finished:
    if (screen) DrawDispose(screen);
}

/* Isolated boot UI: always allow direct access to Swiss's original menu.
 * No changes are made to Swiss's device or launch subsystems.
 */
static int prism_settings_menu(void)
{
	/* Hardware isolation: render PRISM home first. Installed-game scanning
	 * remains available through the Games tile, after the UI is proven. */
	int selection = 0, classic = 0;
	u32 last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_UP | BUTTON_DOWN | BUTTON_LEFT | BUTTON_RIGHT | BUTTON_Z;
	uiDrawObj_t *screen = prism_draw_home(NULL, selection);
	/* Require a new button press after the diagnostic. Holding A/B/START
	 * while the dashboard first appears must not immediately exit it. */
	while (padsButtonsHeld() & (BUTTON_A | BUTTON_B | BUTTON_START))
		VIDEO_WaitVSync();
	for (;;) {
		u32 held = padsButtonsHeld();
		u32 pressed = held & ~last;
		last = held;
		if (pressed & (BUTTON_B | BUTTON_START)) break;
        if (pressed & BUTTON_Z) {
            DrawDispose(screen); screen = NULL;
            prism_system_libraries();
            screen = prism_draw_home(NULL, selection);
            last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_Z;
            continue;
        }
		if (pressed & (BUTTON_UP | BUTTON_DOWN | BUTTON_LEFT | BUTTON_RIGHT)) {
			if (pressed & (BUTTON_UP | BUTTON_DOWN)) selection ^= 2;
			else selection ^= 1;
			screen = prism_draw_home(screen, selection);
		}
		if (pressed & BUTTON_A) {
			if (selection == 1) { classic = 1; break; }
			if (selection == 0) break;
			if (selection == 2) {
				DEVICEHANDLER_INTERFACE *device = devices[DEVICE_CONFIG];
				char path[PATHNAME_MAX];
				const char *result;
				u32 game_count = 0;
				int found = 0;
				if(device && device->initial &&
				   snprintf(path, sizeof(path), "%sswiss/prism/library.prism",
				            device->initial->name) < sizeof(path)) {
					found = prism_pack_device_count(device, path, &game_count);
				}
				if (found && game_count) {
					DrawDispose(screen);
					prism_catalog_browser(device, path, game_count, NULL, NULL);
					screen = prism_draw_home(NULL, selection);
					last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START;
					continue;
				}
				result = found ? "Your offline catalog is empty. Add games in PRISM Studio, then export library.prism." :
				    "No readable offline pack was found. Copy library.prism to /swiss/prism/ on your config storage.";
				prism_show_notice(found ? "Catalog empty" : "Catalog not found", result);
				last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START;
				continue;
			}
			prism_show_notice("About PRISM", "Your GameCube library, with offline covers and descriptions. Open Classic Swiss for devices, settings and advanced options.");
			last = padsButtonsHeld() | BUTTON_A | BUTTON_B | BUTTON_START;
		}
		VIDEO_WaitVSync();
	}
	DrawDispose(screen);
	return classic;
}

static void prism_dashboard_bootstrap(void)
{
    for (;;) {
        int result = prism_installed_browser(1);
        if (result == 2) return;
        if (!result && prism_settings_menu()) return;
    }
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
    if (swissSettings.cubebootInvoked) DrawClassicUI();
    swissSettings.cubebootInvoked = 0;
    unsetenv("CUBEBOOT");
    int prism_opened = 1;
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





