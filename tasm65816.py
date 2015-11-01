#!/usr/bin/env python3
# A Typist's Assembler for the 65816 in Forth 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 1. Nov 2015 

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""(TODO DOCUMENTATION STRING DUMMY)"""


### SETUP ### 

import argparse
import re
import sys
import time
import timeit

import special     # dictionary of special routines special.opc 
from opcodes import opcode_table

# Check for correct version of Python

if sys.version_info.major != 3:
    print("FATAL: Python 3 required. Aborting.")
    sys.exit(1) 

# Initialize various counts

n_warnings = 0



### ARGUMENTS ###

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True, 
        help='Assembler source code file (required)')
parser.add_argument('-o', '--output', dest='output', 
        help='Binary output file (default TASM.BIN)', default='tasm.bin')
parser.add_argument('-l', '--listing', dest='listing', 
        help='Name of listing file (default TASM.LST)', default='tasm.lst')
parser.add_argument('-v', '--verbose', 
        help='Display additional information', action='store_true')
parser.add_argument('-s', '--symbols', dest='symbols', 
        help='Name of symbol table file (default TASM.SYM)', default='tasm.sym')
parser.add_argument('-d', '--dump', 
        help='Print intermediate steps as (long) lists', action='store_true')
parser.add_argument('-w', '--warnings', 
        help='Print all warnings', action='store_true')
args = parser.parse_args()



### BASIC OUTPUT FUNCTIONS ###

def verbose(s):
    """Print information string given if --verbose flag was set. Later 
    expand this by the option of priting to a log file instead."""
    if args.verbose:
        print(s)

def warning(s):
    """If program called with -w or --warnings, print a warning string"""
    if args.warnings:
        print('WARNING:', s) 
        


### CONSTANTS ###

ASSIGN = "="        # Used instead of ".equ" or such
COMMENT = ';'       # Change this for a different comment marker 
CURRENT = '*'       # Marks current location counter
SEPARATORS = '[.:]' # Legal separators in number strings in RE format

HEX_PREFIX = '$'           # Prefix for hexadecimal numbers
BIN_PREFIX = '%'        # Prefix for binary numbers
DEC_PREFIX = '&'       # Prefix for decimal numbers (SUBJECT TO CHANGE)

ST_WIDTH = 16       # Number of chars of symbol from Symbol Table printed

title_string = "A Typist's Assembler for the 65816 in Python\n"

LC0 = 0             # Start address of code ("location counter") 
LCi = 0             # Index to where we are in code

symbol_table = {}


### GENERATE TABLES ###

# Generate mnemonic list 
# TODO remove special NOP handling once opcode table is complete: Remove if
# portion of next line and assigment to nop

mnemonics =\
    { opcode_table[n][1]:n for n, e in enumerate(opcode_table) if opcode_table[n][1] != 'nop'}

mnemonics['nop'] = 0xea

verbose('Generated mnemonics list')



### HELPER FUNCTIONS ###

def lsb(n):
    """Return Least Significant Byte of a number"""
    return n & 0xff

def msb(n):
    """Return Most Significant Byte of a number"""
    return (n & 0xff00) >> 8  

def bank(n):
    """Return Bank Byte of a number"""
    return (n & 0xff0000) >> 16

def little_endian_16(n): 
    """Given a number, return a list with two bytes in correct format"""
    return [lsb(n), msb(n)]

def little_endian_24(n):
    """Given a number, return a list with three bytes in correct format"""
    return [lsb(n), msb(n), bank(n)]

def string2bytes(s):
    """Given a string with quotation marks, isolate what is between them
    and return the number of characters and a list of the ASCII values of
    the characters in that string. Assumes that there is one and only one
    string in the line that is delimited by quotation marks"""

    s1 = l.split('"')[1] 
    return len(s1), [ord(a) for a in s1]


# TODO see if this should be a formal error with RAISE and all of that
def fatal(l,s): 
    """Abort program because of fatal error during assembly"""
    print('FATAL ERROR in line', l, ":", s)
    sys.exit(1) 

def convert_number(s): 
    """Convert a number string provided by the user in one of various 
    formats to an integer we can use internally. See Manual for details on
    supported formats."""
    
    # Remove separator markings
    s1 = re.sub(SEPARATORS, '', s)

    # By default, all numbers are hexadecimal. See if we were given a different
    # number
    c = s1[0]

    if c == DEC_PREFIX:
        BASE = 10
        s2 = s1[1:]
    elif c == BIN_PREFIX:
        BASE = 2
        s2 = s1[1:]
    else: 
        BASE = 16 
        s2 = s1
    
    # If we can convert this to a number, it's a number, otherweise we claim its
    # a symbol. Note that this means that a symbol such as "faced" will be
    # converted to a number, so such numbers should always be prefixed with a 0 
    
    try: 
        r = int(s2, BASE)
        f = True
    except ValueError:
        f = False
        r = s

    return f, r


def dump(l):
    """At each assembly stage, print the complete stage as a list. Produces
    an enormous amount of output, probably only interesting for debugging."""
    if args.dump:
        for line in l:
            print('{0:5d}: {1}'.format(line[0], repr(line[1])))
        print()

def dump_symbol_table(d=symbol_table, s=""):
    print('Symbol Table', s)

    if len(symbol_table) > 0: 

        for v in sorted(symbol_table):
            print('{0} : {1:x}'.format(v.rjust(ST_WIDTH), symbol_table[v]))
        print()

    else:
        print('    (empty)\n')



### PASSES ###

# The assembler works by connecting as many little steps as possible (see the 
# Manual for details). Each step is given a title such as RAW, and all
# requirements for that step are kept close to the actual processing. 

# Note we don't process lists of code, but lists of tuples which consist of
# the original line number and a line of code as a string. That way, we can
# always reference the original line number at each stage. 


# --- Step ZERO: Set up timing, print banner ---

verbose(title_string)

# TODO print banner

time_start = timeit.default_timer() 


# --- Step RAW: Import original code and add line numbers ---

# Line numbers start with 1 because this is for humans

with open(args.source, "r") as f:
    sc_raw = list(enumerate(f.readlines(),1))

verbose('STEP RAW: Read {0} lines from {1}'.format (len(sc_raw), args.source))
dump(sc_raw) 


# --- Step EMPTY: Remove empty lines ---
# TODO keep empty lines in separate list to reconstruct listing file

sc_empty = []

for l in sc_raw:
    if l[1].strip():
        sc_empty.append(l) 

verbose('STEP EMPTY: Removed {0} empty lines'.format(len(sc_raw)-len(sc_empty)))
dump(sc_empty) 


# --- Step COMMENTS: Remove comments that span whole lines ---
# TODO keep comment lines in separate list to reconstruct listing file

sc_comments = []

for l in sc_empty:
    if l[1].strip()[0] != COMMENT :
        sc_comments.append(l) 

verbose('STEP COMMENTS: Removed {0} full-line comments'.format(len(sc_empty)-len(sc_comments)))
dump(sc_comments) 


# -- Step INLINES: Remove comments that are inline ---
# TODO keep inline comments in a separate list to reconstruct file listing

def remove_inlines(l): 
    """Remove any inlines, defined by COMMENT char. Note we only strip the 
    right side because we might need the whitespace on the left later."""
    return l.split(COMMENT)[0].rstrip() 

sc_inlines = []

for n, l in sc_comments:
    sc_inlines.append((n, remove_inlines(l)))

verbose('STEP INLINES: Removed all inline comments') 
dump(sc_inlines) 

    
# --- Step MACROS: Define macros ---
# TODO code this 

verbose('STEP MACROS: Defined 0 macros (DUMMY, not coded yet)')
# TODO add dump 


# --- STEP EXPAND: Expand macros in source code --- 
# TODO code this 

sc_expand = sc_inlines

verbose('STEP EXPAND: Expanded 0 macros (DUMMY, not coded yet)')
dump(sc_expand) 


# --- Step LOWER: Convert everything to lower case ---

sc_lower = [(n, l.lower()) for n, l in sc_expand] 
verbose('STEP LOWER: Converted all remaining code to lower case')
dump(sc_lower) 


# --- Step ORIGIN: Find .ORIGIN directive, initialize location counter ---

sc_origin = []

# ORIGIN line should be in first line now 
originline = sc_lower[0][1].strip().split() 

if originline[0] != ".origin":
    l = sc_lower[0][0]
    fatal(l, 'No ORIGIN directive found') 

_, LC0 = convert_number(originline[1])  # ORIGIN may not take a symbol (yet)
sc_origin = sc_lower[1:]

verbose('STEP ORIGIN: Found ORIGIN directive, setting LC to {0:6x}'.\
        format(LC0))
dump(sc_origin) 


# --- Step END: Make sure we have an .END directive --- 

endline = sc_origin[-1][1].strip().split() 

if endline[0] != ".end":
    fatal(sc_origin[0][0], 'No END directive found') 

sc_end = sc_origin[:-1]

verbose('STEP END: Found END directive in last line') 
dump(sc_end) 


# --- Step ASSIGN: Handle assignment lines ---

verbose('Initializing symbol table') 

sc_assign = []

for n, l in sc_end:
    if ASSIGN in l: 
        s, v = l.split(ASSIGN)
        symbol = s.split()[-1] 
        _, value = convert_number(v.split()[0])  # Can't do symbol to symbol
        symbol_table[symbol] = value  
    else: 
        sc_assign.append((n, l))

verbose('STEP ASSIGN: Assigned {0} symbols to symbol table'.\
        format(len(sc_end)-len(sc_assign))) 
dump(sc_assign)

if args.verbose:
    dump_symbol_table(symbol_table, "after ASSIGN (all numbers in hex)")


# --- Step PASS1: Create Intermediate File ---

# Life is easier if we define the entry types down here. See "Although
# practicality beats purity", https://www.python.org/dev/peps/pep-0020/

cpu_mode = "emulated"
a_mode = 8 
xy_mode = 8 


# Intermediate file Entry types 
# TODO use ENUMERATE construct once we have sorted this all out 

DONE = 0           # Contains completely assembled binary data
MODE_EMULATED = 1  # Tell Pass 2 the following is emulated
MODE_NATIVE = 2    # Tell Pass 2 the following is native
OPC_SYMBOL = 3     # Opcode with unresolved symbol

A16 = 10
A8 = 11
XY16 = 12
XY8 = 13
AXY16 = 14
AXY8 = 15

pass1_entry_types = {
        0: 'DONE',
        1: 'MODE_EMULATE',
        2: 'MODE_NATIVE',
        3: 'OPC_SYMBOL',
       10: 'A16',
       11: 'A8',
       12: 'XY16',
       13: 'XY8',
       14: 'AXY16',
       15: 'AXY8'
        }

# Intermediate file is a list of entries, each a list, with three elements: The
# original line number, the entry type code (see above), and a "payload" list
# with parameters that are unpacked depending on the type 

# Elements of the intermediate file. These are indexes to the entries of the
# lines in each entry

IMF_LINE = 0
IMF_STATUS = 1 
IMF_PAYLOAD = 2

sc_pass1 = []       # Immediate file

# Loop through all lines 

for n, l in sc_assign:

    w = l.split()
    w0 = w[0].strip() 


    # -- Substep LABEL: See if we were given a label --
    
    if w0 == '->':

        # Warn if symbol name is missing, a non-fatal error
        
        try:
            w1 = w[1].strip()
        except IndexError:  
            warning('Directive "->" found without label name in {0}, deleting'.\
                    format(n))
            n_warnings += 1
            continue

        # Make sure we haven't defined this symbol before. That is fatal. 
        # Unknown symbol table entries must be initialized with None so we can
        # know if we're trying to reference to address 0
        
        # TODO see if we need to do this differenty once we add forward
        # references
        
        # TODO This sucks, rewrite once we know how this will work

        if w1 not in symbol_table.keys():
            verbose('Label {0} found in line {1}, address is {2:06x}'.\
                    format(w1, n, LC0 + LCi))
            symbol_table[w1] = LC0 + LCi
        elif symbol_table[w1]: 
            print('FATAL: Attempt to redefine symbol {0} in line {1}'.\
                        format(w1, l))
            sys.exit(1)
        else:
            symbol_table[w1] = LC0 + LCi
            

        # Some people put the label in the same line as another directive or an
        # instruction, so even we think that's crude, we have to allow for it
        w = w[2:]  

        try:
            w0 = w[0].strip()
        except IndexError:
            # That was all that was in the line
            continue


    # -- Substep MNEMONIC: See if we have a mnemonic --
    
    # TODO This currently only works with single-byte instructions
    
    try: 
        oc = mnemonics[w0]
    except KeyError:
        pass
    else:
        sc_pass1.append((n, DONE, [oc]))
        LCi += 1
        continue


    # --- Substep BYTE: See if we have a .BYTE directive
    
    if w0 == '.byte' or w0 == '.b':

        bs = [convert_number(b)[1] for b in w[1:]]
        sc_pass1.append((n, DONE, bs))
        LCi += len(w[1:])
        continue 


    # --- Substep WORD: See if we have a .WORD directive

    if w0 == '.word' or w0 == '.w':

        bl = []
        for b in w[1:]:
            bl.extend(little_endian_16(convert_number(b)[1])) 

        sc_pass1.append((n, DONE, bl))
        LCi += len(w[1:]) * 2 
        continue 
   

    # --- Substep LONG: See if we have a .LONG directive

    if w0 == '.long' or w0 == '.l':

        bl = []
        for b in w[1:]:
            bl.extend(little_endian_24(convert_number(b)[1])) 
            print(bl)

        sc_pass1.append((n, DONE, bl))
        LCi += len(w[1:]) * 3
        continue 


    # --- Substep STRING: See if we have a .STRING directive
    # TODO see if we want to combine all string directives

    if w0 == '.string' or w0 == '.str':

        sn, sl = string2bytes(l) 
        sc_pass1.append((n, DONE, sl))
        LCi += sn
        continue 


    # --- Substep STRING_ZERO: See if we have a .STRING0 directive

    if w0 == '.string0' or w0 == '.str0':

        sn, sl = string2bytes(l) 
        sl.append(00) 
        sn += 1

        sc_pass1.append((n, DONE, sl))
        LCi += sn
        continue 


    # --- Substep STRING_LF: See if we have a .STRINGLF directive

    if w0 == '.stringlf' or w0 == '.strlf':

        sn, sl = string2bytes(l) 
        sl.append(0x0a) 
        sn += 1

        sc_pass1.append((n, DONE, sl))
        LCi += sn
        continue 


    # -- Substep CPU_MODE: See if we have native or emulated directive
    
    # This must come after label directive
    # TODO 00 is a dummy value in MODE_ , see if needed
    # TODO see if we want to save LC0+LCi with DONE (probably)

    if w0 == '.native':
        sc_pass1.append((n, DONE, [0x18])) # clc
        sc_pass1.append((n, DONE, [0xfb])) # xce
        sc_pass1.append((n, MODE_NATIVE, [])) # Payload is dummy
        cpu_mode = 'native'
        continue

    if w0 == '.emulated':
        sc_pass1.append((n, DONE, [0x38])) # sec
        sc_pass1.append((n, DONE, [0xfb])) # xce
        sc_pass1.append((n, MODE_EMULATED, [])) # Payload is dummy
        cpu_mode = 'emulated'
        continue
    
    

verbose('STEP PASS1: Created intermediate file')

# TODO open up list
if args.dump:

    for l, t, bl in sc_pass1:
        print('{0:5d}: {1} {2}'.format(l, pass1_entry_types[t], bl))
    print()



# --- Step PASS2: Create binary file --- 

# TODO use bytearray because it is faster (http://www.dotnetperls.com/bytes)
sc_pass2 = []

def p2_done(l): 
    """Handle lines that are completely done"""
    sc_pass2.extend(l[IMF_PAYLOAD])

pass2_routines = {
        DONE: p2_done, }

for l in sc_pass1:
    
    try:
        pass2_routines[l[IMF_STATUS]](l)
    except:
        # TODO change this to real error code
        print("DUMMY Intermediate File, entry not found.")

object_code = bytes(sc_pass2) 
code_size = len(object_code)

verbose('STEP PASS2: Generated binary object code') 

# TODO make this a real hexdump
if args.dump:
    bl = [hex(b)[2:] for b in sc_pass2]
    print('{0}\n'.format(bl))


# --- Step BIN: Save binary file --- 

with open(args.output, 'wb') as f:
    f.write(object_code)

verbose('STEP BIN: Saved {0} bytes of object code as {1}'.\
        format(code_size, args.output))

if n_warnings != 0 and args.warnings:
    print('Generated {0} warning(s).'.format(n_warnings))


# --- Step LIST: Create listing file ---

with open(args.listing, 'w') as f:
    f.write(title_string)
    f.write('Code listing file {0} generated on {1}\n'\
            .format(args.listing, time.asctime()))
    if n_warnings != 0:
        f.write('Generated {0} warnings.\n'.format(n_warnings))
    f.write('Code origin is {0:06x},'.format(LC0))
    f.write(' {0:x} bytes of machine code generated\n'.format(code_size))

verbose('STEP LIST: Created listing as {0}\n'.\
        format(args.listing))



# --- Step SYMBOLS: Create symbol file ---

# TODO save symbol table file 

verbose('STEP SYM_TABLE: Created symbol table listing as {0} (DUMMY)\n'\
        .format(args.symbols))

if args.verbose:
    dump_symbol_table(symbol_table, "at end of run (all numbers in hex)")



### END ###

time_end = timeit.default_timer() 
verbose('All steps completed in {0:.5f} seconds.'.format(time_end - time_start))
verbose('Enjoy the cake.')
sys.exit(0) 


