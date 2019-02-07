# Common Routines for Tinkasm
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 07. Feb 2019
# This version: 07. Feb 2019
"""Collection of helper routines for tinkasm"""

import re

def convert_number(s):
    """Convert a number string provided by the user in one of various
    formats to an integer we can use internally. Returns a tuple of a
    bool and an int, or a bool and a string. By default, numbers are
    decimal. We encourage modern use of '0x' for hex numbers but
    accept the traditional '$' without warning.
    """

    SEPARATORS = '[.:]'
    s1 = re.sub(SEPARATORS, '', s)

    if s1.startswith('0x'):
        BASE = 16
        s2 = s1[2:]
    elif s1.startswith('$'):
        BASE = 16
        s2 = s1[1:]
    elif s1.startswith('%'):
        BASE = 2
        s2 = s1[1:]
    else:
        BASE = 10 # Default numbers are hex, not decimal
        s2 = s1

    # If we can convert this to a number, it's a number, otherweise we claim
    # it's a symbol. The default is to convert to a number.
    try:
        r = int(s2, BASE)
        f = True
    except ValueError:
        r = s
        f = False

    return f, r
