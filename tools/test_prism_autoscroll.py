"""Exercise native timing without tying reading speed to PAL/NTSC frame rate."""
from pathlib import Path
import subprocess, tempfile
program = r'''
#include <assert.h>
#include "prism_autoscroll.h"
int main(void) {
    PrismAutoScroll state; int line = 0;
    prism_scroll_begin(&state, 100);
    assert(!prism_scroll_tick(&state, 5099, 2, &line) && line == 0);
    assert(prism_scroll_tick(&state, 5100, 2, &line) && line == 1);
    assert(!prism_scroll_tick(&state, 7599, 2, &line));
    assert(prism_scroll_tick(&state, 7600, 2, &line) && line == 2);
    assert(!prism_scroll_tick(&state, 15599, 2, &line));
    assert(prism_scroll_tick(&state, 15600, 2, &line) && line == 0);
    assert(!prism_scroll_tick(&state, 20599, 2, &line));
    prism_scroll_manual(&state, 20000);
    assert(!prism_scroll_tick(&state, 29999, 2, &line));
    assert(prism_scroll_tick(&state, 30000, 2, &line) && line == 1);
    assert(prism_scroll_tick(&state, 100000, 2, &line) && line == 2);
    assert(!prism_scroll_tick(&state, 100000, 2, &line));
    line = 0;prism_scroll_begin(&state, 0);
    assert(!prism_scroll_tick(&state, 100000, 0, &line) && line == 0);
    uint64_t long_uptime = UINT64_C(4294967295);
    prism_scroll_begin(&state, long_uptime);
    assert(!prism_scroll_tick(&state, long_uptime + 4999, 1, &line));
    assert(prism_scroll_tick(&state, long_uptime + 5000, 1, &line) && line == 1);
    return 0;
}
'''
repo = Path(__file__).resolve().parent.parent
with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary);source = root/'scroll.c';source.write_text(program)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pedantic',
                    '-fsanitize=undefined','-I',str(repo/'cube/swiss/source/gui'),
                    str(source),'-o',str(root/'scroll')],check=True)
    subprocess.run([str(root/'scroll')],check=True)
print('Native auto-scroll: start/end pauses, manual override, short text, delayed frames and long uptime passed')
