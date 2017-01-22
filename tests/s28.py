# Test for S28 output creation
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 22. Jan 2017
# This version: 22. Jan 2017

# Compare result of this output with the result of 
# srec_cat tink.bin -binary -offset 0x6000 -o tink.s28 -address-length=3
# -execution-start-address=0x6000

import string
import sys

from binascii import hexlify, unhexlify


with open('tink.bin', 'rb') as f:
    raw = bytearray(f.read())


### Definitions ### 


def crc(s):
    """Create an 8-bit checksum of a S-Record hexstring. Adapted from
    https://github.com/eerimoq/bincopy/blob/master/bincopy.py
    Returns result as string
    """

    # Make sure we really got a hex string
    if not all(c in string.hexdigits for c in s):
        print('Error: Got malformed hexstring {0}'.format(s))

    cs = unhexlify(s)
    cs = sum(bytearray(cs)) 
    cs ^= 0xff
    cs &= 0xff
    cs = '{0:02x}'.format(cs)

    return cs


def make_s0(s): 
    """Given a string for the S0 header line, return a correctly formated 
    S-Record line
    """

    if not s:
        print('Error: No string for S0 provided')
        sys.exit(1)

    s = s.strip()
    h_len = '{0:02x}'.format(len(s)+3)
    h_address = '0000'
    h_data = ''

    for c in s:
        h_data = h_data+'{0:02x}'.format(ord(c))

    h_crc = crc(h_len+h_address+h_data)
    h_all = ('S0'+h_len+h_address+h_data+h_crc).upper()

    return h_all


def make_s2(s, n):
    """Given up to 64 characters of data as a string and an address,
    return a complete S2 record as a string
    """

    if (not n) or (not s):
        print('Error: No address for S8 provided')
        sys.exit(1)

    h_data = s
    h_len = '{0:02x}'.format(len(s)//2+4)
    h_address = '{0:06x}'.format(n)
    h_crc = crc(h_len+h_address+h_data)
    h_all = ('S2'+h_len+h_address+h_data+h_crc).upper()

    return h_all


def make_s8(n):
    """Given the address to pass control to, return the S8 record
    as a string
    """

    if not n:
        print('Error: No address for S8 provided')
        sys.exit(1)

    h_len = '04'        # Always a length of four
    h_address = '{0:06x}'.format(n)
    h_crc = crc(h_len+h_address)

    h_all = ('S8'+h_len+h_address+h_crc).upper()

    return h_all
    
    

### Main routine ###

h_string = 'https://github.com/scotws/tinkasm'
start_address = 0x6000
control_address = 0x6000

# Test S0 line with srec_cat: 'http://srecord.sourceforge.net/' must return 
# S0220000687474703A2F2F737265636F72642E736F75726365666F7267652E6E65742F1D

s0_line = make_s0(h_string)
print(s0_line)

# The S2 line may have a data field with up to 64 characters -> max 32 bytes of
# data. Test S0 lines with the 'hexdump -C <BIN_FILE>'

h_data = ''
for c in raw:
    h_data = h_data+'{0:02x}'.format(c)

t = h_data
a = start_address
while t:
    print(make_s2(t[:64], a))
    t = t[64:]
    a += 32


# Test S8 line with srec_cat: Control address '006000' must return
# S8040060009B

s8_line = make_s8(control_address)
print(s8_line) 


