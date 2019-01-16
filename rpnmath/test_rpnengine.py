# Tests for the Math Engine of Tinkasm 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 13. Jan 2019
# This version: 13. Jan 2019

# From this directory, run "python3 -m unittest"

import unittest

from mathengine import engine

class TestHelpers(unittest.TestCase):

    def test_operations(self):
        self.assertEqual(engine('1 1 +'), (2, True))
        self.assertEqual(engine('4 2 -'), (2, True))
        self.assertEqual(engine('2 2 *'), (4, True))
        self.assertEqual(engine('6 2 /'), (3, True))

    def test_masking(self):
        self.assertEqual(engine('10255 .lsb'), (255, True))
        self.assertEqual(engine(f'{str(0xFF0A)} .msb'), (255, True))
        self.assertEqual(engine(f'{str(0xFFEEDD)} .bank'), (255, True))

    def test_logic(self):
        self.assertEqual(engine('3 1 .and'), (1, True))
        self.assertEqual(engine('3 1 .or'), (3, True))
        self.assertEqual(engine('3 1 .xor'), (2, True))

    def test_bit_twiddle(self):
        self.assertEqual(engine('2 1 .lshift'), (4, True))
        self.assertEqual(engine('4 1 .rshift'), (2, True))
        self.assertEqual(engine('2 .inv'), (-3, True))

    def test_directives(self):
        self.assertEqual(engine('1 2 .drop'), (1, True))
        self.assertEqual(engine('1 .dup +'), (2, True))
        self.assertEqual(engine('2 12 .over / +'), (8, True))
        self.assertEqual(engine('3 12 .swap /'), (4, True))

    def test_misc(self):
        self.assertEqual(engine('.rand .dup -'), (0, True)) # Well, whatever

    def test_pathological(self):
        self.assertEqual(engine(''), (0, False))
        self.assertEqual(engine('2 2'), (2, False))


if __name__ == '__main__':
    unittest.main()


 
