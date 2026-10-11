#include "../cube/swiss/source/gui/prism_text.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static int fits(const char *text, void *context)
{
    return strlen(text) <= *(size_t *)context;
}
int main(void)
{
    size_t width = 10;
    char line[32];
    const char *text = "  Metroid Prime\n A title with words  ";
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "Metroid"));
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "Prime"));
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "A title"));
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "with words"));
    assert(!prism_text_next(&text, line, sizeof(line), fits, &width));
    text = "ABCDEFGHIJKLMNO";
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "ABCDEFGHIJ"));
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "KLMNO"));
    text = "a\tb\r\nc";
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "a b"));
    assert(prism_text_next(&text, line, sizeof(line), fits, &width));
    assert(!strcmp(line, "c"));
    struct { char tiny[4]; char sentinel; } bounded = {{0}, 'X'};
    text = "abcdef";
    assert(prism_text_next(&text, bounded.tiny, sizeof(bounded.tiny), fits, &width));
    assert(!strcmp(bounded.tiny, "abc") && bounded.sentinel == 'X');
    strcpy(line, "1234567890");
    prism_text_elide(line, sizeof(line), fits, &width);
    assert(!strcmp(line, "1234567..."));
    width = 2;
    prism_text_elide(line, sizeof(line), fits, &width);
    assert(line[0] == 0);
    text = "\n \t\r";
    assert(!prism_text_next(&text, line, sizeof(line), fits, &width) && !*text);
    assert(!prism_text_next(NULL, line, sizeof(line), fits, &width));
    puts("PRISM measured text: wrapping, newlines, long words, bounds and ellipsis passed");
    return 0;
}
