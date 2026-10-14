#include "../cube/swiss/source/gui/prism_emulator_launch.h"
#include <assert.h>
int main(void) {
    PrismEmulatorLaunch args;
    const char *systems[]={"n64", "nes", "snes", "gb", "gbc", "gba", "megadrive"};
    for (unsigned i=0;i<7;++i) {
        char dol[128];snprintf(dol,sizeof(dol),"sdc:/swiss/prism/emulators/%s.dol",systems[i]);
        assert(prism_emulator_arguments(dol,"sdc:/roms/Game [1] with spaces.bin",&args));
        assert(args.argv[args.argc]==NULL);
        if (i==0) {assert(args.argc==2 && !strcmp(args.argv[1],"sd:/roms/Game [1] with spaces.bin"));}
        else {
            assert(args.argc==3 && !strcmp(args.argv[2],"Game [1] with spaces.bin"));
            assert(!strcmp(args.argv[1],i==6 ? "sd:/roms/" : "port2:/roms/"));
        }
    }
    const char *bad[]={"sdb:/roms/test.nes","sdc:/../test.nes","sdc:/roms//test.nes",
        "sdc:/roms/./test.nes","sdc:/roms/../test.nes","sdc:/roms/", "sdc:/roms/a\\b.nes",
        "sdc:/roms/a\n.nes","sdc:/roms/sd:/x.nes"};
    for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);++i)
        assert(!prism_emulator_arguments("sdc:/nes.dol",bad[i],&args));
    assert(!prism_emulator_arguments("sdc:/unknown.dol","sdc:/a.nes",&args));
    char longpath[600]="sdc:/";memset(longpath+5,'x',500);longpath[505]=0;
    assert(!prism_emulator_arguments("sdc:/n64.dol",longpath,&args));
    assert(!prism_emulator_arguments("sdc:/megadrive.dol",longpath,&args));
    return 0;
}
