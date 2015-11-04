#!/usr/bin/env python3
# A Tinkerer's Assembler for the 65816 in Forth 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 04. Nov 2015 

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
import string
import sys
import time
import timeit

# dictionary of special routines special.opc 
# TODO do this differently 
import special     

# Check for correct version of Python
if sys.version_info.major != 3:
    print("FATAL: Python 3 required. Aborting.")
    sys.exit(1) 

# Initialize various counts
n_invocations = 0
n_warnings = 0


### ARGUMENTS ###

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True, 
        help='Assembler source code file (required)')
parser.add_argument('-o', '--output', dest='output', 
        help='Binary output file (default TINK.BIN)', default='tink.bin')
parser.add_argument('-l', '--listing', dest='listing', 
        help='Name of listing file (default TINK.LST)', default='tink.lst')
parser.add_argument('-m', '--mpu', dest='mpu', help='Type of MPU', 
        choices=['6502', '65c02', '65816'], default='65816')
parser.add_argument('-v', '--verbose', 
        help='Display additional information', action='store_true')
parser.add_argument('-d', '--dump', 
        help='Print intermediate steps as (long) lists', action='store_true')
parser.add_argument('-x', '--hexdump', 
        help='Create ASCII file TINK.HEX with hexdump of program',
        action='store_true')
parser.add_argument('-w', '--warnings', default=True,
        help='Disable warnings (default: print them)', action='store_false')
args = parser.parse_args()


### BASIC OUTPUT FUNCTIONS ###

def fatal(l,s): 
    """Abort program because of fatal error during assembly"""
    print('FATAL ERROR in line', l, ":", s)
    sys.exit(1) 

def verbose(s):
    """Print information string given if --verbose flag was set. Later 
    expand this by the option of priting to a log file instead."""
    if args.verbose:
        print(s)

def warning(s):
    """If program called with -w or --warnings, print a warning string"""
    if args.warnings:
        print('WARNING:', s) 
        
def hexdump(listing, addr65 = 0):
    """Print hexdump of listing to screen"""

    print('{0:06x}'.format(addr65), end=': ')
    c = 0 

    for e in listing:
        print('{0:02x}'.format(e), end=' ')
        c += 1
        if c % 16 == 0:
            print()
            addr65 += 16
            print('{0:06x}'.format(addr65), end=': ')
    print('\n') 


### IMPORT OPCODE TABLE ### 

MPU = args.mpu.lower() 

if MPU == '6502':
    from opcodes6502 import opcode_table
elif MPU == '65c02':
    from opcodes65c02 import opcode_table
elif MPU == '65816':
    from opcodes65816 import opcode_table
else:
    # Paranoid, this should be caught by argparse routines automatically
    print('FATAL: Unknown MPU type {0} given'.format(args.mpu))
    sys.exit(1)

verbose('Loading opcodes for {0}'.format(MPU))


### CONSTANTS ###

ASSIGN = "="        # Used instead of ".equ" or such
COMMENT = ';'       # Change this for a different comment marker 
CURRENT = '*'       # Marks current location counter
SEPARATORS = '[.:]' # Legal separators in number strings in RE format

HEX_PREFIX = '$'    # Prefix for hexadecimal numbers
BIN_PREFIX = '%'    # Prefix for binary numbers
DEC_PREFIX = '&'    # Prefix for decimal numbers (SUBJECT TO CHANGE)

ST_WIDTH = 10       # Number of chars of symbol from Symbol Table printed
INDENT = ' '*12     # Indent in whitespace for inserted instructions

LC0 = 0             # Start address of code ("location counter") 
LCi = 0             # Index to where we are in code

symbol_table = {}

# Positions in the opcode tables

OT_OPCODE = 0 
OT_MNEMONIC = 1 
OT_N_BYTES = 2
OT_N_OPERANDS = 3 

title_string = "A Tinkerer's Assembler for the 65816 in Python\n"
verbose(title_string)


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

def convert_number(s): 
    # TODO We need to handle CURRENT marker as well
    # TODO Rename this to "analyze_operand" and return code for type
    #      This will let us use the routine to find math routines
    """Convert a number string provided by the user in one of various 
    formats to an integer we can use internally. See Manual for details 
    on supported formats."""
    
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
    """Print Symbol Tabel to screen"""
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


# -------------------------------------------------------------------
# STEP ZERO: Set up timing, print banner 

# TODO print banner

time_start = timeit.default_timer() 

verbose('Beginning assembly. Timer started.')


# -------------------------------------------------------------------
# STEP RAW: Import original code and add line numbers

# Line numbers start with 1 because this is for humans

with open(args.source, "r") as f:
    sc_raw = list(enumerate(f.readlines(),1))

verbose('STEP RAW: Read {0} lines from {1}'.format (len(sc_raw), args.source))
dump(sc_raw) 


# -------------------------------------------------------------------
# Step EMPTY: Remove empty lines
# TODO keep empty lines in separate list to reconstruct listing file

sc_empty = []

for l in sc_raw:
    if l[1].strip():
        sc_empty.append(l) 

verbose('STEP EMPTY: Removed {0} empty lines'.format(len(sc_raw)-len(sc_empty)))
dump(sc_empty) 


# -------------------------------------------------------------------
# STEP COMMENTS: Remove comments that span whole lines
# TODO keep comment lines in separate list to reconstruct listing file

sc_comments = []

for l in sc_empty:
    if l[1].strip()[0] != COMMENT :
        sc_comments.append(l) 

verbose('STEP COMMENTS: Removed {0} full-line comments'.format(len(sc_empty)-len(sc_comments)))
dump(sc_comments) 


# -------------------------------------------------------------------
# STEP INLINES: Remove comments that are inline
# TODO keep inline comments in a separate list to reconstruct file listing

def remove_inlines(l): 
    """Remove any inlines, defined by COMMENT char. Note we only strip the 
    right side because we might need the whitespace on the left later."""
    return l.split(COMMENT)[0].rstrip() 

sc_inlines = []

for n, l in sc_comments:
    sc_inlines.append((n, remove_inlines(l)))

verbose('STEP INLINES: Removed all inline comments and terminating linefeeds') 
dump(sc_inlines) 


# -------------------------------------------------------------------
# STEP MPU: Make sure we have the correct MPU listed

sc_mpu = []

# MPU line should be in first line now 
ml = sc_inlines[0][1].strip().split() 
n = sc_inlines[0][0]

if ml[0].lower() != '.mpu': 
    fatal('No ".mpu" directive found at beginning of source file')

if ml[1] != MPU:
    fatal(n, 'MPU mismatch: {0} given, {1} in source file'.\
            format(MPU, ml[1]))

sc_mpu = sc_inlines[1:]

verbose('STEP MPU: Found .mpu directive, "{0}", agrees with MPU given'.\
        format(MPU))
dump(sc_mpu)


# -------------------------------------------------------------------
# STEP LOWER: Convert everything to lower case

sc_lower = [(n, l.lower()) for n, l in sc_mpu] 

verbose('STEP LOWER: Converted all lines to lower case')
dump(sc_lower) 


# -------------------------------------------------------------------
# STEP BREAKUP: Split labels into their own lines

# It's legal to have a label and either an opcode or a directive in the same
# line. To make life easier for the following routines, we make sure each label
# has it's own line. Since we have gotten rid of the full-line comments,
# anything that is in the first column and is not whitespace is considered
# a label. We don't distinguish between global and local labels at this point

# It is tempting to start filling the symbol table at this point because we're
# touching all the labels and that would be far more efficient. However, we keep
# these steps separate for ideological reasons. 

sc_breakup = []

for n, l in sc_lower:

    # Most of the stuff will be whitespace
    if l[0] in string.whitespace:
        sc_breakup.append((n, l))
        continue 

    # We know now we have a label, we just don't know if it is alone in its
    # line. 
    w = l.split() 

    # If we're alone in the line we're done 
    if len(w) == 1:
        sc_breakup.append((n, l))
        continue 

    # Nope, there is some other stuff there
    sc_breakup.append((n, w[0]))
    rest = l.replace(w[0], '')  # Delete word from string
    sc_breakup.append((n, (len(w[0])*' ')+rest))

verbose('STEP BREAKUP: All labels have a line to themselves')
dump(sc_breakup)


# -------------------------------------------------------------------
# STEP MACROS: Define macros 
# TODO add parameters 

sc_macros = []
macros = {}
are_defining = False 
macro_name = ''

for mn, ml in enumerate(sc_breakup): 

    w = ml[1].split() 

    if are_defining:

        if w[0] != ".endmacro": 
            macros[macro_name].append((ml[0], ml[1]))
        else: 
            are_defining = False 
            continue 
    else:
        # .MACRO must be first in the line, no labels allowed 
        if w[0] != '.macro':    
            sc_macros.append((ml[0], ml[1]))
            continue 
        else: 
            verbose('Found macro {0} in line {1}'.format(w[1], ml[0]))

            macro_name = w[1]
            macros[macro_name] = []
            are_defining = True 

verbose('STEP MACROS: Defined {0} macros'.format(len(macros)))

if args.dump: 

    for m in macros.keys(): 
        print('Macro {0}:'.format(m))

        for ml in macros[m]:
            print('    {0}'.format(ml)) 

    print() 


# -------------------------------------------------------------------
# STEP ORIGIN: Find .ORIGIN directive

sc_origin = []

# ORIGIN line should be in first line now 
originline = sc_macros[0][1].strip().split() 

# TODO rewrite so this works with ".org" as well
if originline[0] != ".origin":
    l = sc_macros[0][0]
    fatal(l, 'No ORIGIN directive found, must be first line after macros') 

_, LC0 = convert_number(originline[1])  # ORIGIN may not take a symbol (yet)
sc_origin = sc_macros[1:]

verbose('STEP ORIGIN: Found ORIGIN directive, starting at {0:06x}'.\
        format(LC0))
dump(sc_origin) 


# -------------------------------------------------------------------
# STEP END: Find .END directive 

endline = sc_origin[-1][1].strip().split() 

if endline[0] != ".end":
    fatal(sc_origin[0][0], 'No END directive found, must be in last line') 

sc_end = sc_origin[:-1]

verbose('STEP END: Found END directive in last line') 
dump(sc_end) 


# -------------------------------------------------------------------
# STEP ASSIGN: Handle assignments

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


# -------------------------------------------------------------------
# STEP INVOKE: Insert macro definitions

# Macros must be expanded before we touch the .NATIVE and .AXY directives
# because those might be in the macros

sc_invoke = []
pre_len = len(sc_assign)

for n, l in sc_assign: 
    
    if '.invoke' not in l:
        sc_invoke.append((n, l)) 
    else:
        print('DUMMY: Expanding Macro in line {0}'.\
                format(n))

# HIER HIER 

post_len = len(sc_invoke)
verbose('STEP INVOKE: Expanded {0} macros, adding {1} lines'.\
        format(n_invocations, post_len - pre_len))

dump(sc_invoke)

# -------------------------------------------------------------------
# STEP MODES: Handle '.native' and '.emulated' directives

# .NATIVE and .EMULATED can either be alone in their line, or with a label or
# a local label, because people do that. If the line contains one word, it will
# be the directive, if there are two or three, it will be the last one and we
# need to conserve the other two.

sc_modes = []

for n, l in sc_invoke:

    if '.native' in l:
        rest = l.replace('.native', '')  # Delete substring
        
        if rest.strip() != '':  
            sc_modes.append((n, rest)) 

        # We need the spaces so we don't screw up label detection later
        sc_modes.append((n, INDENT+'clc'))
        sc_modes.append((n, INDENT+'xce'))

    elif '.emulated' in l: 
        rest = l.replace('.emulated', '')  # Delete substring
        
        if rest.strip() != '':  
            sc_modes.append((n, rest)) 

        # We need leading spaces so we don't screw up label detection later
        sc_modes.append((n, INDENT+'sec'))
        sc_modes.append((n, INDENT+'xce'))

    else:
        sc_modes.append((n, l))
 
verbose('STEP MODES: Handled mode switches')
dump(sc_modes) 


# -------------------------------------------------------------------
# STEP AXY: Handle register size switches

# We add the actual REP/SEP instructions as well as internal directives for the
# following steps 

sc_axy = []

# We need leading spaces so we don't screw up label detection later
axy_ins = {
'.a8':    ((INDENT+'sep 20'), (INDENT+'.a->8')),
'.a16':   ((INDENT+'rep 20'), (INDENT+'.a->16')), 
'.xy8':   ((INDENT+'sep 10'), (INDENT+'.xy->8')) ,
'.xy16':  ((INDENT+'rep 10'), (INDENT+'.xy->16')), 
'.axy8':  ((INDENT+'sep 30'), (INDENT+'.a->8'), (INDENT+'.xy->8')),
'.axy16': ((INDENT+'rep 30'), (INDENT+'.a->16'), (INDENT+'.xy->16')) } 

for n, l in sc_modes:
    have_found = False

    for a in axy_ins: 

        if a in l:

            for e in axy_ins[a]:
                sc_axy.append((n, e))
                have_found = True

            rest = l.replace(a, '')  
        
            # Some people put label markers in the same line as these
            # directives, so we have to let them by copying the rest of the line
            # back to the beginning of the next
            if rest.strip() != '':  
                sc_axy.append((n, rest)) 

    if not have_found:
        sc_axy.append((n, l)) 

verbose('STEP AXY: Handled register size switches (8/16 bit for A, X, and Y)')
dump(sc_axy) 


# -------------------------------------------------------------------
# STEP PASS1: Create Intermediate File

# Life is easier if we define the entry types down here. See "Although
# practicality beats purity", https://www.python.org/dev/peps/pep-0020/

cpu_mode = "emulated"
a_mode = 8 
xy_mode = 8 






# Intermediate file Entry types 
# TODO use ENUMERATE construct once we have sorted this all out 

OPC_DONE = 0       # Contains completely assembled binary data from opcode
DATA_DONE = 1      # Contains completely assembled binary data from data
OPC_SYMBOL = 2     # Opcode with unresolved symbol
ADV_SYMBOL = 3     # .ADVANCE directive with unresolved symbol
MODE_EMULATED = 4  # Tell Pass 2 the following is emulated
MODE_NATIVE = 5    # Tell Pass 2 the following is native

# See if these are required
A16 = 10
A8 = 11
XY16 = 12
XY8 = 13
AXY16 = 14
AXY8 = 15

pass1_entry_types = {
        0: 'OPC_DONE',
        1: 'DATA_DONE',
        2: 'OPC_SYMBOL',
        3: 'ADV_SYMBOL',
        4: 'MODE_EMULATE',
        5: 'MODE_NATIVE',
       10: 'A16',  # See if these are required
       11: 'A8',
       12: 'XY16',
       13: 'XY8'}

pass1_axy_variants = {
        '.a8': [0xe2, 0x20],  # sep 20 
        '.a16': [0xc2, 0x20],  # rep 20 
        '.xy8': [0xe2, 0x10],  # sep 10 
        '.xy16': [0xc2, 0x10]}  # rep 10 


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

for n, l in sc_axy:

    w = l.split()
    w0 = w[0].strip() 


    # -- Substep LABEL: See if we were given a label --
    # TODO Make this the single focus of a pass
    
    if w0 == '->':

        # If the labe name is missing, this is a local label
        
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
    
    try: 
        oc = mnemonics[w0]
    except KeyError:
        pass
    else:
        nb = opcode_table[oc][OT_N_BYTES] 
        
        # Single byte instructions are easy because we don't have to look for
        # symbols, so we get them out of the way fast
        if nb == 1:
            sc_pass1.append((n, OPC_DONE, [oc]))
            LCi += 1
            continue 
            
        # MVN and MVP are a serious pain, so we get them out of the way ASAP
        # TODO code this. 
        if oc == 0x44 or oc == 0x54:
            print('DUMMY: Found MVN or MVP, not coded yet, skipping')
            continue 

        # Multi-byte instruction, but all with only one operand
        is_number, opr = convert_number(w[1]) 

        # If we have a symbol, we punt the problem to the next pass
        if not is_number: 
            # We've got a symbol
            sc_pass1.append((n, OPC_SYMBOL, [oc, w[1]]))
            continue 

        # We've got a number, so we can convert everything right way
        if nb == 2: 
            li = [oc, lsb(opr)]  

        elif nb == 3: 
            oprl = little_endian_16(opr) 
            li = [oc]
            li.extend(oprl) 

        elif nb == 4: 
            oprl = little_endian_24(opr) 
            li = [oc]
            li.extend(oprl) 

        else:
            print('FATAL: Opcode claims to have length of more than 4 bytes')
            sys.exit(1)

        sc_pass1.append((n, OPC_DONE, li))
        LCi += nb 
        continue


    # --- Substep ADVANCE: See if we have an .ADVANCE directive
    # TODO Break this out and make it its own pass

    if w0 == '.advance':

        is_number, nz = convert_number(w[1]) 
        
        if not is_number:
            sc_pass1.append((n, ADV_SYMBOL, [w[1]]))
            continue 

        bs = [00] * (nz - (LC0 + LCi))
        sc_pass1.append((n, DATA_DONE, bs))

        verbose('Advanced {0} bytes from {1:x} to {2:x}, line {3}'.\
                format(len(bs), LC0+LCi, nz, n)) 

        continue 


    # --- Substep BYTE: See if we have a .BYTE directive
    # TODO Break these data out and make them their own pass
    
    if w0 == '.byte' or w0 == '.b':

        bs = [convert_number(b)[1] for b in w[1:]]
        sc_pass1.append((n, DATA_DONE, bs))
        LCi += len(w[1:])

        verbose('Stored {0} bytes of data from line {1} (BYTE directive)'.\
                format(len(w[1:]), n))

        continue 


    # --- Substep WORD: See if we have a .WORD directive

    if w0 == '.word' or w0 == '.w':

        bl = []

        for b in w[1:]:
            bl.extend(little_endian_16(convert_number(b)[1])) 

        verbose('Stored {0} bytes of data from line {1} (WORD directive)'.\
                format(len(w[1:])*2, n))

        sc_pass1.append((n, DATA_DONE, bl))
        LCi += len(w[1:]) * 2 
        continue 
   

    # --- Substep LONG: See if we have a .LONG directive

    if w0 == '.long' or w0 == '.l':

        bl = []
        for b in w[1:]:
            bl.extend(little_endian_24(convert_number(b)[1])) 

        verbose('Stored {0} bytes of data from line {1} (LONG directive)'.\
                format(len(w[1:])*3, n))

        sc_pass1.append((n, DATA_DONE, bl))
        LCi += len(w[1:]) * 3
        continue 


    # --- Substep STRING: See if we have a .STRING directive
    # TODO see if we want to combine all string directives

    if w0 == '.string' or w0 == '.str':

        sn, sl = string2bytes(l) 
        sc_pass1.append((n, DATA_DONE, sl))
        LCi += sn
        continue 


    # --- Substep STRING_ZERO: See if we have a .STRING0 directive

    if w0 == '.string0' or w0 == '.str0':

        sn, sl = string2bytes(l) 
        sl.append(00) 
        sn += 1

        sc_pass1.append((n, DATA_DONE, sl))
        LCi += sn
        continue 


    # --- Substep STRING_LF: See if we have a .STRINGLF directive

    if w0 == '.stringlf' or w0 == '.strlf':

        sn, sl = string2bytes(l) 
        sl.append(0x0a) 
        sn += 1

        sc_pass1.append((n, DATA_DONE, sl))
        LCi += sn
        continue 


   
    
    # --- Substep AXY: Handle AXY direcives
    
    # This is the last legal entry possible. 

    try:
        sl = pass1_axy_variants[w0]
    except KeyError:
        fatal(n, 'Instruction or directive "{0}" unknown.'.format(w[0])) 
    else:
        # TODO see if we have to append a marker for AXY etc for pass 2
        sc_pass1.append((n, OPC_DONE, sl))


verbose('STEP PASS1: Created intermediate file')

if args.dump:
    for l, t, bl in sc_pass1:
        print('{0:5d}: {1} {2}'.format(l, pass1_entry_types[t], bl))
    print()



# --- Step PASS2: Create binary file --- 

# TODO use bytearray because it is faster (http://www.dotnetperls.com/bytes)
sc_pass2 = []

def p2_done(l): 
    """Handle lines that are completely done, opcode or data"""
    sc_pass2.extend(l[IMF_PAYLOAD])

def p2_adv_symbol(l): 
    """Handle lines that contain an advance and an unresolved symbol"""
    print('DUMMY: Found ADVANCE with unresolved symbol, skipping') 

def p2_opc_symbol(l):
    """Handle lines that contain an opcode and an unresolved symbol"""
    print('DUMMY: Found opcode with unresolved symbol, skipping')

pass2_routines = {
        OPC_DONE: p2_done, DATA_DONE: p2_done, 
        ADV_SYMBOL: p2_adv_symbol, OPC_SYMBOL: p2_opc_symbol}

for l in sc_pass1:
    
    try:
        pass2_routines[l[IMF_STATUS]](l)
    except:
        # TODO change this to real error code
        print('DUMMY Intermediate File, entry not found.')
        print('Line was:', l) 

object_code = bytes(sc_pass2) 
code_size = len(object_code)

verbose('STEP PASS2: Generated binary object code') 

# TODO add dump of file

if args.dump:
    hexdump(sc_pass2, LC0)


# -------------------------------------------------------------------
# STEP BIN: Save binary file 

with open(args.output, 'wb') as f:
    f.write(object_code)

verbose('STEP BIN: Saved {0} bytes of object code as {1}'.\
        format(code_size, args.output))

if n_warnings != 0 and args.warnings:
    print('Generated {0} warning(s).'.format(n_warnings))


# -------------------------------------------------------------------
# STEP LIST: Create listing file

with open(args.listing, 'w') as f:
    f.write(title_string)
    f.write('Code listing for file {0}\n'.format(args.source))
    f.write('Generated on {0}\n'.format(time.asctime()))
    f.write('Target MPU was {0}\n'.format(MPU))
    time_end = timeit.default_timer() 
    f.write('Assembly time was {0:.5f} seconds\n'.format(time_end - time_start))
    if n_warnings != 0:
        f.write('Generated {0} warnings.\n'.format(n_warnings))
    f.write('Code origin is {0:06x}\n'.format(LC0))
    f.write('Generated {0} bytes of machine code\n'.format(code_size))

    # Add listing 
    f.write('\nLISTING:\n')

    # TODO write this 


    # Add macros
    f.write('\nMACROS:\n')

    if len(macros) > 0: 

        for m in macros.keys(): 
            f.write('Macro {0}\n'.format(m))

            for ml in macros[m]:
                f.write('    {0}\n'.format(ml)) 

        f.write('\n') 

    else:
        f.write('    (none)\n')


    # Add symbol list 
    f.write('\nSYMBOLS:\n')

    if len(symbol_table) > 0: 

        for v in sorted(symbol_table):
            f.write('{0} : {1:x}\n'.format(v.rjust(ST_WIDTH), symbol_table[v]))
        f.write('\n')

    else:
        f.write('    (empty)\n')


verbose('STEP LIST: Created listing as {0}\n'.\
        format(args.listing))


# -------------------------------------------------------------------
# STEP HEXDUMP: Create hexdump file if requested

if args.hexdump:
    print("DUMMY creating hexdump file TINK.HEX")
    




### END ###

time_end = timeit.default_timer() 
verbose('All steps completed in {0:.5f} seconds.'.format(time_end - time_start))
verbose('Enjoy the cake.')
sys.exit(0) 


