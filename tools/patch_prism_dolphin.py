#!/usr/bin/env python3
"""Pinned Dolphin 2609a compatibility fix; never edits the tested PRISM DOL.

GCController returns 0 for the optional 0x1d GameID packet. SI.cpp interprets
0 as pending and repeatedly schedules the device's zero TransferInterval(),
preventing guest time and the debugger from advancing. Real standard controllers
ignore this accessory notification. Return -1 (no response) so SI completes it.
"""
import argparse
from pathlib import Path

BEFORE = '''case EBufferCommands::CMD_SET_GAME_ID:
  {
    return 0;
  }'''
AFTER = '''case EBufferCommands::CMD_SET_GAME_ID:
  {
    // PRISM CI: ignored accessory notification completes with no response.
    // Zero means pending in SI.cpp; standard controllers have zero retry delay.
    return -1;
  }'''


def patch(source):
    if source.count(BEFORE) != 1:
        raise ValueError('Expected exactly one pinned GameID handler; refusing an unrecognized source')
    return source.replace(BEFORE, AFTER, 1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    args.source.write_text(patch(args.source.read_text()))
    print('Applied Dolphin controller GameID no-response fix; PRISM DOL unchanged')
