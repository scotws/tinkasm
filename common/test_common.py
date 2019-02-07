# Test routines for tinkasm common routines
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 07. Feb 2019
# This version: 07. Feb 2019

# From this directory, run "python3 -m unittest"

import unittest

from common import convert_number

class TestHelpers(unittest.TestCase):

    def test_convert_number(self):
        self.assertEqual(convert_number('0'), (True, 0))
        self.assertEqual(convert_number('100'), (True, 100))
        self.assertEqual(convert_number('0x0'), (True, 0))
        self.assertEqual(convert_number('0x100'), (True, 256))
        self.assertEqual(convert_number('$0'), (True, 0))
        self.assertEqual(convert_number('$100'), (True, 256))
        self.assertEqual(convert_number('%0'), (True, 0))
        self.assertEqual(convert_number('%100'), (True, 4))
        self.assertEqual(convert_number('%0000100'), (True, 4))

        self.assertEqual(convert_number('&100'), (False, '&100'))

        self.assertEqual(convert_number('$'), (False, '$'))
        self.assertEqual(convert_number('%'), (False, '%'))
        self.assertEqual(convert_number('0x'), (False, '0x'))

if __name__ == '__main__':
    unittest.main()


 

 
