#!/usr/bin/env python3
"""Package a linked GameCube DOL with complete 32-byte loader read blocks.

No header, address, code or existing payload byte is changed. Some elf2dol
outputs end exactly at an unaligned last section; Dolphin/apploaders round
section reads up to 32 bytes and reject that short final block.
"""
import argparse
import struct
from pathlib import Path

HEADER_BYTES = 256
MEM1_START, MEM1_END = 0x80003100, 0x81800000


def padded_dol(raw):
    if len(raw) < HEADER_BYTES or len(raw) > 32*1024*1024:
        raise ValueError('Invalid PRISM DOL size')
    words = struct.unpack('>64I', raw[:HEADER_BYTES])
    needed = len(raw)
    entry = words[56]
    entry_in_text = False
    sections = 0
    for start, address_start, size_start, count in [(0,18,36,7), (7,25,43,11)]:
        for index in range(count):
            offset, address, size = words[start+index], words[address_start+index], words[size_start+index]
            if not size:
                continue
            sections += 1
            if offset < HEADER_BYTES or offset+size > len(raw):
                raise ValueError('DOL section outside linked file')
            aligned_size = (size+31) & ~31
            if address < MEM1_START or address+aligned_size > MEM1_END:
                raise ValueError('DOL section outside GameCube MEM1')
            if start == 0 and address <= entry < address+size:
                entry_in_text = True
            needed = max(needed, offset+aligned_size)
    if not sections or not entry_in_text:
        raise ValueError('DOL has no executable entry in a text section')
    extra = needed-len(raw)
    if extra > 31:
        raise ValueError('Unexpected DOL loader padding requirement')
    result = raw + bytes(extra)
    assert result[:len(raw)] == raw and result[:HEADER_BYTES] == raw[:HEADER_BYTES]
    return result


def package(source, destination):
    raw = Path(source).read_bytes()
    result = padded_dol(raw)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(result)
    assert destination.read_bytes() == result
    print(f'{destination.name}: preserved {len(raw)} linked bytes, added {len(result)-len(raw)} zero padding bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args = parser.parse_args()
    package(args.source,args.destination)
