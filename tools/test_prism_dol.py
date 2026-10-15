"""Regression for Dolphin's rounded section reads rejecting unpadded elf2dol output."""
import struct
import unittest
from prism_dol import padded_dol


def linked(data_size):
    words = [0]*64
    words[0], words[18], words[36] = 256, 0x80003100, 32
    words[7], words[25], words[43] = 288, 0x80003120, data_size
    words[56] = 0x80003100
    return struct.pack('>64I',*words)+b'X'*32+b'Y'*data_size


def dolphin_section_bounds(raw):
    words = struct.unpack('>64I',raw[:256])
    return all(not words[size+i] or words[offset+i]+((words[size+i]+31)&~31)<=len(raw)
               for offset,size,count in [(0,36,7),(7,43,11)] for i in range(count))


class DOLTests(unittest.TestCase):
    def test_every_final_block_remainder_and_unchanged_payload(self):
        for remainder in range(32):
            with self.subTest(remainder=remainder):
                raw = linked(32+remainder)
                result = padded_dol(raw)
                self.assertEqual(result[:len(raw)],raw)
                self.assertEqual(result[len(raw):],bytes((-remainder)%32))
                self.assertTrue(dolphin_section_bounds(result))
                self.assertEqual(dolphin_section_bounds(raw),remainder==0)
                self.assertEqual(padded_dol(result),result)

    def test_existing_tail_and_aligned_output_untouched(self):
        raw = linked(64)
        self.assertEqual(padded_dol(raw),raw)
        with_tail = linked(33)+b'original trailer'*3
        self.assertEqual(padded_dol(with_tail),with_tail)

    def test_bad_header_entry_ranges_and_truncation_rejected(self):
        for raw in [b'bad',bytes(256),linked(33)[:-1]]:
            with self.assertRaises(ValueError):
                padded_dol(raw)
        for position,value in [(0,0),(18,0x90000000),(56,0x81000000),(43,0xffffffff)]:
            raw = bytearray(linked(33))
            struct.pack_into('>I',raw,position*4,value)
            with self.subTest(position=position), self.assertRaises(ValueError):
                padded_dol(bytes(raw))


if __name__ == '__main__':
    unittest.main()
