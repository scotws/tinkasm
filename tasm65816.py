#!/usr/bin/env python3
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


"""(TODO DOCUMENTATION STRING DUMMY)"""


### SETUP ### 

import argparse
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

ASSIGN = "="        # Change this to " equ " or whatever 
COMMENT = ';'       # Change this for a different comment marker 
ST_WIDTH = 16       # Number of chars of symbol in Symbol Table printed

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


# --- Step ORIGIN: Find ORIGIN directive, initialize location counter ---

sc_origin = []

# ORIGIN line should be in first line now 
originline = sc_lower[0][1].strip().split() 

if originline[0] != "origin":
    l = sc_lower[0][0]
    fatal(l, 'No ORIGIN directive found') 

LC0 = number2int(originline[1]) 
sc_origin = sc_lower[1:]

verbose('STEP ORIGIN: Found ORIGIN directive, setting LC to {0:6x}'.\
        format(LC0))
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
dump(sc_assign)

if args.verbose:
    dump_symbol_table(symbol_table, "after ASSIGN")


# --- Step PASS1: Create Intermediate File ---

# Life is easier if we define the entry types down here. See "Although
# practicality beats purity", https://www.python.org/dev/peps/pep-0020/

cpu_mode = "emulated"
a_mode = 8 
xy_mode = 8 


# Intermediate file Entry types 
# TODO use ENUMERATE construct once we're done 
OPCODE_DONE = 0     # Contains completely assembled instruction 
MODE_EMULATED = 1    # Tell Pass 2 this part is emulated
MODE_NATIVE = 2     # Tell Pass 2 this part is native
A16 = 3
A8 = 4
XY16 = 5
XY8 = 6

pass1_entry_types = {0: 'OPCODE_DONE',
        1: 'MODE_EMULATE',
        2: 'MODE_NATIVE',
        3: 'A16',
        4: 'A8',
        5: 'XY16',
        6: 'XY8'
        }

sc_pass1 = []       # Immediate file

for n, l in sc_assign:

    w = l.split()
    w0 = w[0].strip() 


    # -- Substep LABEL: See if we were given a label --
    
    if w0 == '->':

        # Warn if symbol name is missing. That is not fatal 
        
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
        
        # TODO This construct sucks, rewrite once we know how this will work

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
        # instruction, so we have to allow for that
        w = w[2:]  

        try:
            w0 = w[0].strip()
        except IndexError:
            # That was all that was in the line
            continue


    # -- Substep MNEMONIC: See if we have a correct mnemonic --
    
    try: 
        oc = mnemonics[w0]
    except KeyError:
        pass
    else:
        sc_pass1.append((n, OPCODE_DONE, oc))
        LCi += 1
        continue


    # -- Substep CPU_MODE: See if we have native or emulated directive
    # This must come after label directive
    # TODO 00 is a dummy value in MODE_ , see if needed
    # TODO see if we want to save LC0+LCi with OPCODE_DONE (probably)

    if w0 == 'native':
        sc_pass1.append((n, OPCODE_DONE, 0x18)) # clc
        sc_pass1.append((n, OPCODE_DONE, 0xfb)) # xce
        sc_pass1.append((n, MODE_NATIVE, 00)) 
        cpu_mode = 'native'
        continue

    if w0 == 'emulated':
        sc_pass1.append((n, OPCODE_DONE, 0x38)) # sec
        sc_pass1.append((n, OPCODE_DONE, 0xfb)) # xce
        sc_pass1.append((n, MODE_EMULATED, 00)) 
        cpu_mode = 'emulated'
        continue
    
    

verbose('STEP PASS1: Created intermediate file')

if args.dump:

    for l, t, c in sc_pass1:
        print('{0:5d}: {1} {2:x}'.format(l, pass1_entry_types[t], c))
    print()



# --- Step PASS2: Create binary file --- 

# TODO unwind multi-byte instructions
# TODO use bytearray because it is faster (http://www.dotnetperls.com/bytes)
sc_pass2 = [b[2] for b in sc_pass1 if b[1] == OPCODE_DONE]

verbose('STEP PASS2: Generated binary object code') 

# TODO make this a real hexdump
if args.dump:
    bl = [hex(b)[2:] for b in sc_pass2]
    print('{0}\n'.format(bl))

object_code = bytes(sc_pass2) 
code_size = len(object_code)


# Save binary file 
with open(args.output, 'wb') as f:
    f.write(object_code)

verbose('Saved {0} bytes of object code as {1}'.\
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
    dump_symbol_table(symbol_table, "at end of run")



### END ###

time_end = timeit.default_timer() 
verbose('All steps completed in {0:.5f} seconds.'.format(time_end - time_start))
verbose('Enjoy the cake.')
sys.exit(0) 


