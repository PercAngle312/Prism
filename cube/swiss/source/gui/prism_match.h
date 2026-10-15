#ifndef SWISS_CA_PRISM_MATCH_H
#define SWISS_CA_PRISM_MATCH_H
#include "prism_library.h"

/* Find metadata by the actual disc ID discovered from a game's header.
 * Never infer the ID from filenames or titles. Returns NULL on no match.
 */
const PrismLibraryGame *prism_match_id(const PrismLibrary *library, const char *id);
#endif
