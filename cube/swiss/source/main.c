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
 * The original Swiss menu is reached with A/START/B.
 * Keep all Swiss initialization and game-launch code unchanged.
 * This bootstrap will be replaced by the actual cover library renderer.
 */
static uiDrawObj_t *prism_draw_home(int selection)
{
	uiDrawObj_t *panel = DrawContainer();
	DrawAddChild(panel, DrawEmptyColouredBox(38, 78, 602, 430,
		(GXColor){18, 24, 42, 242}));
	DrawAddChild(panel, DrawStyledLabel(65, 116, "PRISM", 1.9f, ALIGN_LEFT,
		(GXColor){225, 235, 255, 255}));
	DrawAddChild(panel, DrawStyledLabel(65, 151, "GameCube dashboard | Swiss-CA", 0.85f, ALIGN_LEFT,
		(GXColor){170, 194, 229, 255}));
	DrawAddChild(panel, DrawStyledLabel(65, 199, "Game library", 1.2f, ALIGN_LEFT,
		(GXColor){225, 235, 255, 255}));
	DrawAddChild(panel, DrawStyledLabel(65, 229,
		"Your installed games first. Full catalog is optional.", 0.8f, ALIGN_LEFT,
		(GXColor){170, 194, 229, 255}));
	DrawAddChild(panel, DrawSelectableButton(70, 257, 563, 292,
		"Browse installed games", selection == 0 ? B_SELECTED : B_NOSELECT));
	DrawAddChild(panel, DrawSelectableButton(70, 298, 563, 333,
		"Open Classic Swiss", selection == 1 ? B_SELECTED : B_NOSELECT));
	DrawAddChild(panel, DrawSelectableButton(70, 339, 563, 374,
		"Browse offline catalog", selection == 2 ? B_SELECTED : B_NOSELECT));
	DrawAddChild(panel, DrawSelectableButton(70, 380, 563, 415,
		"About PRISM", selection == 3 ? B_SELECTED : B_NOSELECT));
	DrawAddChild(panel, DrawStyledLabel(320, 423,
		"D-Pad: Select   A: Open   B/START: Classic Swiss", 0.8f, ALIGN_CENTER,
		(GXColor){185, 200, 225, 255}));
	return DrawPublish(panel);
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
        char line[48];
        const char *cursor;
        uiDrawObj_t *panel;
        u32 pressed, held;
        int y, i;
        if (!prism_pack_device_entry(device, path, position, &entry,
                                     title, sizeof(title), synopsis, sizeof(synopsis))) {
            uiDrawObj_t *error = DrawPublish(DrawMessageBox(D_WARN,
                "Unable to read PRISM metadata entry.\nPress A/B to return."));
            while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
            while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
            DrawDispose(error);
            return;
        }
        panel = DrawContainer();
        DrawAddChild(panel, DrawEmptyColouredBox(38, 78, 602, 430,
            (GXColor){18, 24, 42, 242}));
        DrawAddChild(panel, DrawStyledLabel(65, 115, "PRISM  /  OFFLINE CATALOG",
            1.15f, ALIGN_LEFT, (GXColor){225, 235, 255, 255}));
        snprintf(heading, sizeof(heading), "%s  |  %lu / %lu", entry.id,
                 (unsigned long)(position + 1), (unsigned long)count);
        DrawAddChild(panel, DrawStyledLabel(65, 151, heading, 0.85f,
            ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
        DrawAddChild(panel, DrawEmptyColouredBox(65, 175, 225, 358,
            (GXColor){37, 52, 78, 255}));
        DrawAddChild(panel, DrawStyledLabel(145, 265, "COVER PENDING", 0.72f,
            ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
        if (strlen(title) > 42) title[42] = 0;
        DrawAddChild(panel, DrawStyledLabel(246, 190, title, 0.92f,
            ALIGN_LEFT, (GXColor){225, 235, 255, 255}));
        DrawAddChild(panel, DrawStyledLabel(246, 224, "SYNOPSIS", 0.75f,
            ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
        cursor = synopsis;
        y = 251;
        for (i = 0; i < 5 && *cursor; ++i) {
            size_t n = strlen(cursor);
            if (n > 43) {
                size_t cut = 43;
                while (cut > 15 && cursor[cut] != ' ') --cut;
                n = cut > 15 ? cut : 43;
            }
            memcpy(line, cursor, n);
            line[n] = 0;
            DrawAddChild(panel, DrawStyledLabel(246, y, line, 0.68f,
                ALIGN_LEFT, (GXColor){204, 218, 239, 255}));
            cursor += n;
            while (*cursor == ' ') ++cursor;
            y += 22;
        }
        DrawAddChild(panel, DrawStyledLabel(320, 404,
            "LEFT/RIGHT: Browse    B/START: Return", 0.8f, ALIGN_CENTER,
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

/* Read-only view of raw GameCube images discovered via Swiss on /games.
 * The original Swiss menu remains the only launch path.
 */
static int prism_installed_browser(int quiet_if_empty)
{
    DEVICEHANDLER_INTERFACE *device = devices[DEVICE_CUR];
    DEVICEHANDLER_INTERFACE *metadata_device = devices[DEVICE_CONFIG];
    PrismLibrary *library;
    char folder[PATHNAME_MAX];
    char pack_path[PATHNAME_MAX];
    int has_pack = 0;
    void *cover_buffer = NULL;
    GXTexObj cover_texture;
    u32 last = BUTTON_B | BUTTON_START | BUTTON_LEFT | BUTTON_RIGHT;
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
    if (!prism_installed_scan(device, folder, library) || !library->count) {
        if (quiet_if_empty) { free(library); return 0; }
        uiDrawObj_t *info = DrawPublish(DrawMessageBox(D_INFO,
            "No raw ISO/GCM files found in /games.\nUse Classic Swiss."));
        while (padsButtonsHeld() & (BUTTON_A | BUTTON_B)) VIDEO_WaitVSync();
        while (!(padsButtonsHeld() & (BUTTON_A | BUTTON_B))) VIDEO_WaitVSync();
        DrawDispose(info);
        free(library);
        return 0;
    }
    if (metadata_device && metadata_device->initial &&
        snprintf(pack_path, sizeof(pack_path), "%sswiss/prism/library.prism",
                 metadata_device->initial->name) < (int)sizeof(pack_path)) {
        u32 count = 0;
        has_pack = prism_pack_device_count(metadata_device, pack_path, &count);
    }
    /* GX textures need 32-byte aligned memory; reuse one cover buffer.
     * Do not tie image storage to temporary directory-entry buffers. */
    cover_buffer = memalign(32, PRISM_COVER_TEXTURE_SIZE);
    for (;;) {
        int has_cover = 0;
        const PrismLibraryGame *game = prism_library_selected(library);
        char title[PRISM_PACK_TITLE_MAX + 1];
        char synopsis[PRISM_PACK_SYNOPSIS_MAX + 1];
        char heading[100];
        char line[48];
        const char *cursor;
        uiDrawObj_t *panel;
        u32 held, pressed;
        int y, i;
        if (!game) break;
        if (!prism_enrich_installed(has_pack ? metadata_device : NULL,
                                    has_pack ? pack_path : NULL, game,
                                    title, sizeof(title), synopsis, sizeof(synopsis)))
            break;
        if (cover_buffer && has_pack &&
            prism_pack_device_cover(metadata_device, pack_path, game->id,
                                    cover_buffer, PRISM_COVER_TEXTURE_SIZE)) {
            DCFlushRange(cover_buffer, PRISM_COVER_TEXTURE_SIZE);
            GX_InitTexObj(&cover_texture, cover_buffer, PRISM_COVER_WIDTH,
                          PRISM_COVER_HEIGHT, GX_TF_RGB565,
                          GX_CLAMP, GX_CLAMP, GX_FALSE);
            GX_InitTexObjLOD(&cover_texture, GX_LINEAR, GX_LINEAR,
                             0.0f, 0.0f, 0.0f, GX_FALSE, GX_FALSE,
                             GX_ANISO_1);
            has_cover = 1;
        }
        panel = DrawContainer();
        DrawAddChild(panel, DrawEmptyColouredBox(38, 78, 602, 430,
            (GXColor){18, 24, 42, 242}));
        DrawAddChild(panel, DrawStyledLabel(65, 115, "PRISM  /  INSTALLED GAMES",
            1.15f, ALIGN_LEFT, (GXColor){225, 235, 255, 255}));
        snprintf(heading, sizeof(heading), "%s  |  %lu / %lu",
            game->id, (unsigned long)(library->selected + 1),
            (unsigned long)library->count);
        DrawAddChild(panel, DrawStyledLabel(65, 151, heading, 0.85f,
            ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
        DrawAddChild(panel, DrawEmptyColouredBox(65, 175, 225, 358,
            (GXColor){37, 52, 78, 255}));
        if (has_cover)
            DrawAddChild(panel, DrawTexObj(&cover_texture, 78, 175, 134, 183,
                                          0, 0.0f, 1.0f, 0.0f, 1.0f, 0));
        else
            DrawAddChild(panel, DrawStyledLabel(145, 265, "NO COVER", 0.72f,
                ALIGN_CENTER, (GXColor){170, 194, 229, 255}));
        if (strlen(title) > 42) title[42] = 0;
        DrawAddChild(panel, DrawStyledLabel(246, 190, title, 0.92f,
            ALIGN_LEFT, (GXColor){225, 235, 255, 255}));
        DrawAddChild(panel, DrawStyledLabel(246, 224, "SYNOPSIS", 0.75f,
            ALIGN_LEFT, (GXColor){170, 194, 229, 255}));
        cursor = synopsis[0] ? synopsis : "Metadata not available for this disc.";
        y = 251;
        for (i = 0; i < 5 && *cursor; ++i) {
            size_t n = strlen(cursor);
            if (n > 43) {
                size_t cut = 43;
                while (cut > 15 && cursor[cut] != ' ') --cut;
                n = cut > 15 ? cut : 43;
            }
            memcpy(line, cursor, n);
            line[n] = 0;
            DrawAddChild(panel, DrawStyledLabel(246, y, line, 0.68f,
                ALIGN_LEFT, (GXColor){204, 218, 239, 255}));
            cursor += n;
            while (*cursor == ' ') ++cursor;
            y += 22;
        }
        DrawAddChild(panel, DrawStyledLabel(320, 404,
            "LEFT/RIGHT: Browse   B/START: Return", 0.8f,
            ALIGN_CENTER, (GXColor){185, 200, 225, 255}));
        panel = DrawPublish(panel);
        for (;;) {
            held = padsButtonsHeld();
            pressed = held & ~last;
            last = held;
            if (pressed & (BUTTON_B | BUTTON_START)) {
                DrawDispose(panel);
                free(cover_buffer);
                free(library);
                return 1;
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
        DrawDispose(panel);
    }
    free(cover_buffer);
    free(library);
    return 1;
}

/* Isolated boot UI: always allow direct access to Swiss's original menu.
 * No changes are made to Swiss's device or launch subsystems.
 */
static void prism_dashboard_bootstrap(void)
{
	/* Launch straight into installed games when the active Swiss storage
	 * contains supported raw images. Missing/unavailable storage falls back
	 * to the home screen without a blocking boot-time dialog. */
	prism_installed_browser(1);
	int selection = 0;
	u32 last = BUTTON_A | BUTTON_B | BUTTON_START | BUTTON_UP | BUTTON_DOWN;
	uiDrawObj_t *screen = prism_draw_home(selection);
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
			if((devices[DEVICE_CUR]->features & FEAT_AUTOLOAD_DOL) && getenv("WIILOAD") == NULL) {
				load_auto_dol(argc, argv);
			}
			memcpy(&curDir, devices[DEVICE_CUR]->initial, sizeof(file_handle));
			needsDeviceChange = 0;
			DrawLoadBackdrop(devices[DEVICE_CUR]);
		}
	}

	// Scan here since some devices would already be initialised (faster)
	populateDeviceAvailability();

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
					if(strverscmp(swissSettings.gcloaderTopVersion, "2.0.1") < 0) {
						find_existing_entry("gcldr:/GCLoader_Updater_2.0.1*.dol", true);
						uiDrawObj_t *msgBox = DrawPublish(DrawMessageBox(D_INFO, "A firmware update is available.\ngc-loader.com/firmware-updates"));
						wait_press_A();
						DrawDispose(msgBox);
					}
					break;
				case 2:
					if(strverscmp(swissSettings.gcloaderTopVersion, "1.0.1") < 0) {
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
	
	// Check for autoload entry
	if(swissSettings.autoload[0]) {
		// Check that the path in the autoload entry points at a device that has been detected
		print_debug("Autoload entry detected [%s]\n", swissSettings.autoload);
		find_existing_entry(&swissSettings.autoload[0], true);
	}
	else if(swissSettings.recent[0][0] && swissSettings.recentListLevel > 1) {
		find_existing_entry(&swissSettings.recent[0][0], false);
	}

	if(swissSettings.cubebootInvoked) {
		return 0;
	}
	/* Prism is the first interactive screen; Classic Swiss remains available. */
	prism_dashboard_bootstrap();
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
