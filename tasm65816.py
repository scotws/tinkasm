# #!/usr/bin/env python3
# A Typist's Assembler for the 65816 in Forth 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 27. Oct 2015

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


"""(DOCMENTATION STRING DUMMY)"""

# TODO make sure this is python 3


### SETUP ### 

import argparse
import sys
import time
import timeit

import special     # dictionary of special routines special.opc 
from opcodes import opcode_table


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


### OUTPUT FUNCTIONS ###

def dump(l):
    """At each assembly stage, print the complete stage as a list. Produces
    an enormous amount of output, probably only interesting for debugging."""
    if args.dump:
        for line in l:
            print('{0:5d}: {1}'.format(line[0], repr(line[1])))
        print()

def verbose(s):
    """Print information string given if --verbose flag was set. Later 
    expand this by the option of priting to a log file instead."""
    if args.verbose:
        print(s)

def warning(s):
    """If program called with -w or --warnings, print a warning string"""
    if args.warnigns:
        print('WARNING: ', s) 


### CONSTANTS ###

ASSIGN = "="        # Change this to " equ " or whatever 
COMMENT = ';'       # Change this for a different comment marker 
ST_WIDTH = 16       # Number of chars of symbol in Symbol Table printed

title_string = "A Typist's Assembler for the 65816 in Python\n"


### GENERATE TABLES ###

# Generate mnemonic list 
# TODO remove special NOP handling once opcode table is complete: Remove if
# portion of next line and assigment to nop

mnemonics =\
    { opcode_table[n][1]:n for n, e in enumerate(opcode_table) if opcode_table[n][1] != 'nop'}

mnemonics['nop'] = 0xea

verbose('Generated mnemonics list')



### HELPER FUNCTIONS ###

# TODO see if this should be a formal error with RAISE and all of that
def fatal(l,s): 
    """Abort program because of fatal error during assembly"""
    print('FATAL ERROR in line', l, ":", s)
    sys.exit(1) 

# TODO Make this work with various formats, currently assumes hex
def number2int(s):
    """Convert a number string provided by the user in one of various 
    formats to an integer we can use internally. See Manual for details on
    supported formats."""
    return int(s, 16)


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


# --- Step ORIGIN: Find ORIGIN directive, initialize location counter ---

sc_origin = []
LC = 0 

# ORIGIN line should be in first line now 
originline = sc_lower[0][1].strip().split() 

if originline[0] != "origin":
    l = sc_lower[0][0]
    fatal(l, 'No ORIGIN directive found') 

LC = number2int(originline[1]) 
sc_origin = sc_lower[1:]

verbose('STEP ORIGIN: Found ORIGIN directive, setting LC to {0}'.format(originline[1]))
dump(sc_origin) 


# --- Step END: Make sure we have an END directive --- 

endline = sc_origin[-1][1].strip().split() 

if endline[0] != "end":
    fatal(sc_origin[0][0], 'No END directive found') 

sc_end = sc_origin[:-1]

verbose('STEP END: Found END directive in last line') 
dump(sc_end) 


# --- Step ASSIGN: Handle the clear assignment lines ---

verbose('Initializing symbol table') 

symbol_table = {}

sc_assign = []

for n, l in sc_end:
    if ASSIGN in l: 
        s, v = l.split(ASSIGN)
        symbol = s.split()[-1] 
        value = number2int(v.split()[0])
        symbol_table[symbol] = value  
    else: 
        sc_assign.append((n, l))

verbose('STEP ASSIGN: Assigned {0} symbols to symbol table'.\
        format(len(sc_end)-len(sc_assign))) 

if args.verbose:
    print() 
    print('Symbol Table:')

    for v in sorted(symbol_table):
        print('{0} : {1:x}'.format(v.rjust(ST_WIDTH), symbol_table[v]))
    print()


# --- Step PASS1: Create Intermediate File ---

# Life is easier if we define the entry types down here. See "Although
# practicality beats purity", https://www.python.org/dev/peps/pep-0020/

# Entry types TODO use ENUMERATE once we're done 
OPCODE_DONE = 0     # Contains completely assembled instruction 

pass1_entry_types = {0: 'OPCODE_DONE'}


sc_pass1 = []       # Immediate file

for n, l in sc_assign:

    # - Substep MNEMONIC: See if we have a correct mnemonic - 
    m = l.strip() 

    try: 
        oc = mnemonics[m]
    except KeyError:
        pass
    else:
        sc_pass1.append((n, OPCODE_DONE, oc))
        continue

verbose('STEP PASS1: Created intermediate file')

# Easier to handle the intermediate file formationg separately
if args.dump:

    for l, t, c in sc_pass1:
        print('{0:5d}: {1} {2:x}'.format(l, pass1_entry_types[t], c))
    print()



# --- Step PASS2: Create binary file --- 

# TODO unwind multi-byte instructions
sc_pass2 = [b[2] for b in sc_pass1 if b[1] == OPCODE_DONE]

verbose('STEP PASS2: Generated binary object code') 

if args.dump:
    print(repr(sc_pass2))
    print()

object_code = bytes(sc_pass2) 
code_size = len(object_code)


# Save binary file 
with open(args.output, 'wb') as f:
    f.write(object_code)

verbose('Saved {0} bytes of object code as {1}'.\
        format(code_size, args.output))


# --- Step LIST: Create listing file ---

with open(args.listing, 'w') as f:
    f.write(title_string)
    f.write('Code listing file {0} in 65816 assembler\n'.format(args.listing))
    f.write('Generated at {0}\n\n'.format(time.asctime()))

verbose('STEP LIST: Created listing as {0}'.\
        format(args.listing))



# --- Step SYMBOLS: Create symbol file ---

verbose('STEP SYMBOLS: Created symbol table listing as {0} (DUMMY)'\
        .format(args.symbols))

# TODO save symbol table file 


# TODO HIER HIER TODO 



### END ###

time_end = timeit.default_timer() 
verbose('All steps complete in {0} seconds.'.format(time_end - time_start))
verbose('Enjoy the cake.')
sys.exit(0) 


