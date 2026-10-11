#include <assert.h>
#include <string.h>
#include "../cube/swiss/source/gui/prism_metadata.h"

int main(void)
{
    const char record[] = "GM8E01\tExplore Tallon IV.\r\n";
    const char manifest[] = "# Offline PRISM metadata\n"
        "GZLE01\tSail the Great Sea.\n"
        "GM8E01\tExplore Tallon IV.\n";
    PrismMetadata meta;
    assert(prism_metadata_parse_line(record, sizeof(record)-1, &meta));
    assert(!strcmp(meta.id, "GM8E01"));
    assert(!strcmp(meta.synopsis, "Explore Tallon IV."));
    assert(!prism_metadata_parse_line("BAD\tNo", 6, &meta));
    assert(!prism_metadata_parse_line("GM8E01\t", 7, &meta));
    assert(!prism_metadata_parse_line("# comment", 9, &meta));
    assert(!prism_metadata_parse_line("GM8E01\tBad\tField", 16, &meta));
    assert(prism_metadata_find(manifest, sizeof(manifest)-1, "GZLE01", &meta));
    assert(!strcmp(meta.synopsis, "Sail the Great Sea."));
    assert(prism_metadata_find(manifest, sizeof(manifest)-1, "GM8E01", &meta));
    assert(!prism_metadata_find(manifest, sizeof(manifest)-1, "GALE01", &meta));
    assert(!prism_metadata_find(manifest, sizeof(manifest)-1, "SHORT", &meta));
    return 0;
}
