#!/usr/bin/env python3
# A Tinkerer's Assembler for the 65816 in Forth 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 12. Nov 2015

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
import operator
import re
import string
import sys
import time
import timeit

# Check for correct version of Python
if sys.version_info.major != 3:
    print("FATAL: Python 3 required. Aborting.")
    sys.exit(1) 

# Initialize various counts. Some of these are just for general data collection
n_external_files = 0    # How many external files were loaded
n_invocations = 0       # How many macros were expanded
n_mode_switches = 0     # TODO Count switches native/emulated (65816)
n_size_switches = 0     # TODO Count 8/16 bit register switches (65816)
n_warnings = 0          # How many warnings were generated


### ARGUMENTS ###

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True, 
        help='Assembler source code file (required)')
parser.add_argument('-o', '--output', dest='output', 
        help='Binary output file (default TINK.BIN)', default='tink.bin')
parser.add_argument('-l', '--listing', dest='listing', 
        help='Name of listing file (default TINK.LST)', default='tink.lst')
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

def hexstr(i):
    """Given an integer, return a hex number as a string that has the '0x' 
    portion stripped out and is limited to 24 bit (to correctly handle the
    negative numbers)"""
    return hex(i & 0x0ffffff).replace('0x', '')

def fatal(n, s): 
    """Abort program because of fatal error during assembly"""
    print('FATAL ERROR in line {0}: {1}'.format(n, s))
    sys.exit(1) 

def verbose(s):
    """Print information string given if --verbose flag was set. Later 
    expand this by the option of priting to a log file instead."""
    if args.verbose:
        print(s)

# TODO code this 
def suggestion(n, s):
    """Print a suggestion of how the code could be better"""
    print('SUGGESTION: DUMMY, ROUTINE NOT CODED YET')
    
def warning(s):
    """If program called with -w or --warnings, print a warning string"""
    if args.warnings:
        print('WARNING: {0}'.format(s)) 
        
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


### PRINT HEADER ###

title_string = "A Tinkerer's Assembler for the 65816 in Python\n"

verbose(title_string) 
# TODO add name


### CONSTANTS ###

COMMENT = ';'       # Change this for a different comment marker 
CURRENT = '*'       # Marks current location counter
LOCAL_LABEL = '@'   # Marks local labels
SEPARATORS = '[.:]' # Legal separators in number strings in RE format

HEX_PREFIX = '$'    # Prefix for hexadecimal numbers
BIN_PREFIX = '%'    # Prefix for binary numbers
DEC_PREFIX = '&'    # Prefix for decimal numbers (SUBJECT TO CHANGE)

ST_WIDTH = 10       # Number of chars of symbol from Symbol Table printed
INDENT = ' '*12     # Indent in whitespace for inserted instructions

LC0 = 0             # Start address of code ("location counter") 
LCi = 0             # Index to where we are in code

HEX_FILE  = 'tink.hex'   # Name of hexdump file
LIST_FILE = 'tink.lst'   # Name of listing file 

legal_mpus = ['6502', '65c02', '65816'] 

symbol_table = {}
local_labels = [] 

# Positions in the opcode tables
# TODO see if we need these
OPCT_OPCODE = 0 
OPCT_MNEMONIC = 1 
OPCT_N_BYTES = 2


# Line Status. Leave these as strings so humans can read them. We start with
# SOURCE and end up with everything either as CODE_DONE or DATA_DONE. Make
# the strings the same length to make formatting easier
ADDED     = 'ADDED      '  # Line that was added by the assembler 
CODE_DONE = 'done (code)'  # Finished entry from code, now machine code bytes
CONTROL   = 'CONTROL    '  # Entry for flow control w/ no code or data
DATA_DONE = 'done (data)'  # Finished entry from data, now pure bytes
MACRO     = 'MACRO      '  # Line created by macro expansion 
SOURCE    = 'src        '  # Raw entry line (without whitespace) 
MODIFIED  = 'MODIFIED   '  # Entry that has been partially processed




# List of all directives
directives = ['.a->8', '.a->16', '.a8', '.a16', '.append', '.origin',\
        '.org', '.end', '.b', '.byte', '.w', '.word', '.l', '.long',\
        '.native', '.emulated', '.s', '.string', '.s0', '.string0', '.slf',\
        '.stringlf', '.xy->8', '.xy->16', '.xy8', '.xy16', COMMENT,\
        '.lsb', '.msb', '.bank', '.lshift', '.rshift', '.invert',\
        '.and', '.or', '.xor', CURRENT, LOCAL_LABEL]


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
    """Given a number, return a tuple with two bytes in correct format"""
    return lsb(n), msb(n)

def little_endian_24(n):
    """Given a number, return a tuple with three bytes in correct format"""
    return lsb(n), msb(n), bank(n)

def string2bytes(s):
    """Given a string with quotation marks, isolate what is between them
    and return the number of characters and a list of the hex ASCII values of
    the characters in that string. Assumes that there is one and only one
    string in the line that is delimited by quotation marks"""
    return len(s), [hexstr(ord(c)) for c in s]

def convert_number(s): 
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
    # TODO handle various formats more gracefully once we know what they are
    """At each assembly stage, print the complete stage as a list. Produces
    an enormous amount of output, probably only interesting for debugging."""
    if args.dump:
        for line in l:

            # For lines without status codes at the beginning of the code
            if len(line) == 2: 
                print('{0:5d}: {1}'.format(line[0], repr(line[1])))
                continue 

            # For lines with status codes
            # TODO make the final line dump numbers in hex
            if len(line) == 3: 
                print('{0:5d}: {1} {2!s}'.\
                        format(line[0], line[1], line[2]))
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


### MODIFIER AND MATH FUNCTIONS ###

# The math functions for TinkAsm are very primative. For the assignments and
# instructions with as single operand such as an address, there are two cases:
#
# 1) If the operand is split into two words, it's a "modifier" case with an
#    action and a number or symbol (eg "lda.# .lsb muggle'). 
# 2) If the operand is split into three words, it's a "math" case with an action
#    between two numbers of symbols (eg "lda.# muggle + 1")
#
# Note that in both cases, white space is significant. Also, the mvp and mvn
# instructions of the 65816 are treated separately because their structure does
# not fit the single-operand mode. 

modifier_funcs = { '.lsb': lsb, '.msb': msb, '.bank': bank,\
        '.invert': operator.invert}

def modify_operand(lw, n): 
    """Given a list lw of two strings, apply the modifier function that is 
    the first word to the actual operand that is the second word."""
    is_number, opr = convert_number(lw[1])

    # Paranoid, we shouldn't have symbols anymore
    if not is_number:
        fatal(n, 'Symbol found during modify function {0}'.format(lw[0]))

    try:
        r = modifier_funcs[lw[0]](opr)
    except KeyError:
        fatal(n, 'Illegal modifier {0} given'.format(lw[0]))

    return r 


math_funcs = { '+': operator.add, '-': operator.sub, '*': operator.mul,\
        '/': operator.floordiv, '.and': operator.and_, '.or': operator.or_,\
        '.xor': operator.xor, '.lshift': operator.lshift,\
        '.rshift': operator.rshift} 

def math_operand(lw, n):
    """Given a list lw of three strings, apply the math function in
    the second word to the two other operands"""
    is_number, a1 = convert_number(lw[0])

    # Paranoid, we shouldn't have symbols anymore
    if not is_number:
        fatal(n, 'Symbol found during modify function {0}'.format(lw[1]))

    is_number, a2 = convert_number(lw[2])

    # Paranoid, we shouldn't have symbols anymore
    if not is_number:
        fatal(n, 'Symbol found during modify function {0}'.format(lw[1]))

    try:
        r = math_funcs[lw[1]](a1, a2)
    except KeyError:
        fatal(n, 'Illegal modifier {0} given'.format(lw[1]))

    return r 


### PASSES AND STEPS ###

# The assembler works by connecting as many little steps as possible (see the 
# Manual for details). Each step is given a title such as STATUS, and all
# requirements for that step are kept close to the actual processing. 
#
# Each step passes on a list with a tuple that can contain at various times:
#
#   num - The original line number in the source for reference
#   sta - A status string that shows the status of the line
#   add - Address of the instruction 
#   pay - The payload of the line, either a string or later a list of bytes
#
# After each step we pass on the processed list and, if requested by the user,
# print a verbose information string and a dump of the processes lists. 


# -------------------------------------------------------------------
# STEP BANNER: Set up timing, print banner 

# TODO print banner

time_start = timeit.default_timer() 

verbose('Beginning assembly, timer started.')


# -------------------------------------------------------------------
# STEP LOAD: Load original source code and add line numbers

# Line numbers start with 1 because this is for humans. Note that at this point,
# the tuples in the list entries only have two elements, line number and payload

sc_load = []

with open(args.source, "r") as f:
    sc_load = list(enumerate(f.readlines(), 1))

verbose('STEP IMPORT: Read {0} lines from {1}'.\
        format(len(sc_load), args.source))
dump(sc_load) 


# -------------------------------------------------------------------
# PASS INCLUDE: Add content from extermal files specified by the INCLUDE
# directive

# The .include directive must be alone in the line and the second string must be
# the name of the file without spaces. 

sc_include = []

for num, pay in sc_load:

    w = pay.split() 

    try: 
        if w[0].lower() == '.include':

            # We keep the line number for later reference
            with open(w[1], "r") as f:
                sc_include.extend([(num, l) for l in f.readlines()])

            n_external_files += 1
            verbose('Included code from file "{0}"'.format(w[1]))
            continue 

    # TODO This looks stupid, rewrite
    except IndexError:
        sc_include.append((num, pay)) 
    else:
        sc_include.append((num, pay)) 

verbose('STEP INCLUDE: Added {0} external files'.format(n_external_files))  
dump(sc_include) 


# -------------------------------------------------------------------
# PASS EMPTY: Remove empty lines

sc_empty = []
empty_lines = []

for num, pay in sc_include:
    if pay.strip():
        sc_empty.append((num, pay)) 
    else:
        empty_lines.append(num)

verbose('STEP EMPTY: Removed {0} empty lines'\
        .format(len(sc_include)-len(sc_empty)))
verbose('Empty lines are {0}'.format(empty_lines))
dump(sc_empty) 


# -------------------------------------------------------------------
# PASS COMMENTS: Remove comments that span whole lines

sc_comments = []
full_line_comments = [] 

for num, pay in sc_empty:
    if pay.strip()[0] != COMMENT :
        sc_comments.append((num, pay)) 
    else:
        full_line_comments.append((num, pay))

verbose('STEP COMMENTS: Removed {0} full-line comments'.\
        format(len(sc_empty)-len(sc_comments)))
dump(sc_comments) 


# -------------------------------------------------------------------
# PASS INLINES: Remove comments that are inline

# TODO keep inline comments in a separate list to reconstruct file listing

def remove_inlines(p): 
    """Remove any inlines, defined by COMMENT char. We only strip the 
    right side because we need the whitespace on the left later."""
    return p.split(COMMENT)[0].rstrip() 

sc_inlines = []

for num, pay in sc_comments:
    sc_inlines.append((num, remove_inlines(pay)))

verbose('STEP INLINES: Removed all inline comments and terminating linefeeds') 
dump(sc_inlines) 


# -------------------------------------------------------------------
# PASS LOWER: Convert everything to lower case

sc_lower = [(num, pay.lower()) for num, pay in sc_inlines] 

verbose('STEP LOWER: Converted all lines to lower case')
dump(sc_lower) 


# -------------------------------------------------------------------
# PASS MPU: Find MPU type 

sc_mpu = []
MPU = ''

for num, pay in sc_lower:

    if '.mpu' in pay:
        MPU = pay.split()[1].strip() 
    else: 
        sc_mpu.append((num, pay)) 

if not MPU:
    fatal('No ".mpu" directive found')

if MPU not in legal_mpus:
    fatal('MPU "{0}" not supported'.format(MPU))

verbose('PASS MPU: Found MPU "{0}", is supported'.format(MPU))
dump(sc_mpu)


# -------------------------------------------------------------------
# STEP OPCODES: Load opcodes depending on MPU type

# We use 65816 as the default. This step does not change the source code

# If we ever have have more than these three types, rewrite
if MPU == '6502':
    from opcodes6502 import opcode_table
elif MPU == '65c02':
    from opcodes65c02 import opcode_table
else: 
    from opcodes65816 import opcode_table

verbose('STEP OPCODES: Loaded opcode table for MPU {0}'.format(MPU))


# -------------------------------------------------------------------
# STEP MNEMONICS: Generate mnemonic list from opcode table

# This step does not change the source code
#
mnemonics = {opcode_table[n][1]:n for n, e in enumerate(opcode_table)}

verbose('STEP MNEMONICS: Generated mnemonics list')
if args.dump:
    print('Mnemonics found: {0}'.format(mnemonics.keys()))


# -------------------------------------------------------------------
# STEP STATUS: Add status strings to end of line 

# Starting here, each line has a three-element tuple 

sc_status = [(n, SOURCE, p) for n, p in sc_mpu]

verbose('STEP STATUS: Added status strings')
dump(sc_status) 


# -------------------------------------------------------------------
# PASS BREAKUP: Split labels into their own lines, reformat others

# It's legal to have a label and either an opcode or a directive in the same
# line. To make life easier for the following routines, here we make sure each
# label has it's own line. Since we have gotten rid of the full-line comments,
# anything that is in the first column and is not whitespace is then considered
# a label. We don't distinguish between global and local labels at this point

# It is tempting to start filling the symbol table here because we're touching
# all the labels and that would be far more efficient. However, we keep these
# steps separate for ideological reasons. 

sc_breakup = []

for n, s, p in sc_status:

    # Most of the stuff will be whitespace
    if p[0] in string.whitespace:
        sc_breakup.append((n, s, INDENT+p.strip()))
        continue 

    # We now know we have a label, we just don't know if it is alone in its
    # line. 
    w = p.split() 

    # If we're alone in the line we're done 
    if len(w) == 1:
        sc_breakup.append((n, MODIFIED, p.strip()))
        continue 

    # Nope, there is something after the label
    sc_breakup.append((n, MODIFIED, w[0].strip()))
    rest = p.replace(w[0], '').strip()  # Delete word from string
    sc_breakup.append((n, s, INDENT+rest))

verbose('STEP BREAKUP: All labels now have a line to themselves')
dump(sc_breakup)


# -------------------------------------------------------------------
# STEP MACROS: Define macros 

# TODO add parameters 

sc_macros = []

macros = {}
macro_name = ''
are_defining = False 

for n, s, p in sc_breakup: 

    w = p.split() 

    if not are_defining:
        
        # MACRO directive must be first in the line, no labels allowed
        if w[0] != '.macro':    
            sc_macros.append((n, s, p)) 
            continue 
        else: 
            macro_name = w[1]
            macros[macro_name] = []
            are_defining = True 
            verbose('Found macro "{0}" in line {1}'.format(w[1], n))

    else:

        if w[0] != ".endmacro": 
            macros[macro_name].append((n, MACRO, p))
        else: 
            are_defining = False 
            continue 

verbose('STEP MACROS: Defined {0} macros'.format(len(macros)))
dump(sc_macros)

# TODO pretty format this 
if args.dump: 

    for m in macros.keys(): 
        print('Macro {0}:'.format(m))

        for ml in macros[m]:
            print('    {0}'.format(repr(ml))) 

    print() 


# -------------------------------------------------------------------
# STEP ORIGIN: Find .ORIGIN directive

# TODO See if we want to give the user the option of passing the origin at the
#      command line, possibly with -s --start option

# We accept both ".origin" and ".org". 

sc_origin = []

# ORIGIN line should be at the top of the list now 
originline = sc_macros[0][2].strip().split() 

if originline[0] != '.origin' and originline[0] != '.org':
    n = sc_macros[0][0]
    fatal(n, 'No ORIGIN directive found, must be first line after macros') 

is_number, LC0 = convert_number(originline[1])  

# ORIGIN may not take a symbol, because we haven't defined any yet
if not is_number: 
    n = sc_macros[0][0]
    fatal(n, 'ORIGIN directive gives "{0}", not number as required')

sc_origin = sc_macros[1:]

verbose('STEP ORIGIN: Found ORIGIN directive, starting at {0:06x}'.\
        format(LC0))
dump(sc_origin) 


# -------------------------------------------------------------------
# STEP END: Find .END directive 

endline = sc_origin[-1][2].strip().split() 

if endline[0] != ".end":
    fatal(sc_origin[0][0], 'No END directive found, must be in last line') 

sc_end = sc_origin[:-1]

verbose('STEP END: Found END directive in last line') 
dump(sc_end) 


# -------------------------------------------------------------------
# PASS ASSIGN: Handle assignments

# TODO add math and modifiers

# We accept two kinds of assignment directives , "=" and ".equ". Since we've
# moved all labels to their own lines, any such directive must be the second
# word in the line.

sc_assign = []

for n, s, p in sc_end:

    w = p.split() 

    # An assigment line must have three words at least. The "at least" part
    # is so we will be able to add math functions later
    if len(w) < 3:
        sc_assign.append((n, s, p))
        continue 

    # Sorry, Lisp and Forth coders, infix notation only
    if w[1] == '=' or w[1] == '.equ': 
        sy, v = p.split(w[1])
        symbol = sy.split()[-1] 
        is_number, value = convert_number(v.split()[0])

        # We can't do symbol to symbol assignment because we have no way to make
        # sure that there was a real number there back up the line 
        if not is_number:
            fatal(n, 'Illegal attempt to assign a symbol to another symbol')

        symbol_table[symbol] = value  
    else: 
        sc_assign.append((n, s, p))

verbose('STEP ASSIGN: Assigned {0} symbols to symbol table'.\
        format(len(sc_end)-len(sc_assign))) 
dump(sc_assign)

if args.verbose:
    dump_symbol_table(symbol_table, "after ASSIGN (numbers in hex)")


# -------------------------------------------------------------------
# STEP INVOKE: Insert macro definitions
# TODO Add parameters

# Macros must be expanded before we touch the .NATIVE and .AXY directives
# because those might be present in the macros

sc_invoke = []
pre_len = len(sc_assign)

for n, s, p in sc_assign: 
    
    if '.invoke' not in p:
        sc_invoke.append((n, s, p)) 
        continue 
        
    # Name of macro to invoke must be second word in line
    w = p.split()
    
    try:
        m = macros[w[1]]
    except KeyError:
        fatal(n, 'Attempt to invoke non-existing macro "{0}"'.\
                format(w[1]))

    for ml in m:
        sc_invoke.append(ml)

    n_invocations += 1
    verbose('Expanding macro "{0}" into line {1}'.\
                format(w[1], n))

post_len = len(sc_invoke)

# We give the "net" number of lines added because we also remove the invocation
# line itself
verbose('STEP INVOKE: {0} macro expansions, net {1} lines added'.\
        format(n_invocations, post_len - pre_len))
dump(sc_invoke)


# -------------------------------------------------------------------
# PASS MODES: Handle '.native' and '.emulated' directives on the 65816

# TODO count and print number of mode switches

# Since we have moved labels to their own lines, we assume that both .NATVIE
# and .EMULATED alone in their respective lines

sc_modes = []

if MPU == '65816':

    for n, s, p in sc_invoke:

        if '.native' in p:
            # Spaces are for cosmetic reasons, as we have already handled 
            # labels
            sc_modes.append((n, ADDED, INDENT+'clc'))
            sc_modes.append((n, ADDED, INDENT+'xce'))
            continue 

        if '.emulated' in p: 
            # Spaces are for cosmetic reasons, as we have already handled 
            # labels
            sc_modes.append((n, ADDED, INDENT+'sec'))
            sc_modes.append((n, ADDED, INDENT+'xce'))

            # Emulation drops us into 8-bit modes for A, X, and Y 
            # automatically, no REP or SEP commands needed
            sc_modes.append((n, CONTROL, INDENT+'.a->8'))
            sc_modes.append((n, CONTROL, INDENT+'.xy->8'))
            continue
        
        sc_modes.append((n, s, p))

    verbose('STEP MODES: Handled mode switches')
    dump(sc_modes) 

else:
    sc_modes = sc_invoke    # Keep the chain going 


# -------------------------------------------------------------------
# PASS AXY: Handle register size switches on the 65816

# TODO count and print number of mode switches

# We add the actual REP/SEP instructions as well as internal directives for the
# following steps 

sc_axy = []

if MPU == '65816':

    # Indentation is cosmetic, as we have already handled labels
    axy_ins = {
    '.a8':    ((ADDED, 'sep 20'), (CONTROL, '.a->8')),
    '.a16':   ((ADDED, 'rep 20'), (CONTROL, '.a->16')), 
    '.xy8':   ((ADDED, 'sep 10'), (CONTROL, '.xy->8')) ,
    '.xy16':  ((ADDED, 'rep 10'), (CONTROL, '.xy->16')), 
    '.axy8':  ((ADDED, 'sep 30'), (CONTROL, '.a->8'), (CONTROL, '.xy->8')),
    '.axy16': ((ADDED, 'rep 30'), (CONTROL, '.a->16'), (CONTROL, '.xy->16')) } 

    for n, s, p in sc_modes:
        have_found = False

        for a in axy_ins: 

            # Because we moved labels to their own lines, we can assume that
            # register switches are alone in the line
            if a in p:

                for e in axy_ins[a]:
                    sc_axy.append((n, e[0], INDENT+e[1]))
                    have_found = True

        if not have_found:
            sc_axy.append((n, s, p)) 

    verbose('STEP AXY: Registered register 8/16 bit switches')
    dump(sc_axy) 

else:
    sc_axy = sc_modes    # Keep the chain going 


# -------------------------------------------------------------------
# STEP LABELS - Construct symbol table by finding all labels 

# This is the equivalent of the traditional "Pass 1" in normal two-pass
# assemblers. We assume that the most common line by far will be mnemonics, and
# that then we'll see lots of labels (at some point, we should measure this).
# Put the mnemonics first then to speed stuff up slightly at least.

# Though we don't start acutal assembling here, we do remember information for
# later passes when it is useful, like for branches and such, and get rid of
# some directives such as ADVANCE and SKIP.  

sc_labels = []

branches = ['bra', 'beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
        'bra.l', 'phe.r']  

# These are only used for 65816. The offsets are used to calculate if an extra
# byte is needed for immediate forms such as lda.# with the 65816

a_len_offset = 0 
xy_len_offset = 0 
a_imm = ['adc.#', 'and.#', 'bit.#', 'cmp.#', 'eor.#', 'lda.#', 'ora.#', 'sbc.#'] 
xy_imm = ['cpx.#', 'cpy.#', 'ldx.#', 'ldy.#']

for n, s, p in sc_axy:

    w = p.split() 


    # --- SUBSTEP CURRENT: Replace the CURRENT symbol by current address
    
    # This must come before we handle mnemonics. Don't add a continue because
    # that will screw up the line count; we replace in-place, so to speak

    # TODO This version is too primitive because CURRENT is probably the star
    # which will also be used for multiplication at some point. Right now, we
    # just brute force it.

    # TODO consider giving this its own full pass
    
    if CURRENT in p:
        hc = hexstr(LC0+LCi)     # TODO make this a separate function
        p = p.replace(CURRENT, hc)
        w = p.split() 
        verbose('Current marker "{0}" in line {1}, replaced with {2}'.\
                format(CURRENT, n, hc))



    # --- SUBSTEP MNEMONIC: See if we have a mnemonic ---
    
    # Because we are using Typist's Assembler Notation and every mnemonic
    # maps to one and only one opcode, we don't have to look at the operand of
    # the instruction at all
 
    try:
        oc = mnemonics[w[0]]
    except KeyError:
        pass
    else: 
        # For branches, we want to remember were the instruction is to make our
        # life easier later
        if w[0] in branches: 
            p = p + ' ' + hexstr(LC0+LCi)
            s = MODIFIED 
            verbose('Added address of branch to its payload in line {0}'.\
                    format(n)) 

        LCi += opcode_table[oc][OPCT_N_BYTES]

        # Factor in register size if this is a 65816
        if MPU == '65816':

            if w[0] in a_imm:
                LCi += a_len_offset 
            elif w[0] in xy_imm:
                LCi += xy_len_offset 

        sc_labels.append((n, s, p))
        continue 


    # --- SUBSTEP LABELS: Figure out where our labels are ---
   
    # Labels and local labels are the only thing that should be in the first
    # column at this point
    
    if p[0] not in string.whitespace:

        # Local labels are easiest, start with them first
        if w[0] == LOCAL_LABEL:
            local_labels.append((n, LC0+LCi))
            verbose('New local label found in line {0}, address {1:06x}'.\
                    format(n, LC0+LCi))
            continue 

        # This must be a real label. If we don't have it in the symbol table,
        # all is well and we add a new entry
        if w[0] not in symbol_table.keys():
            verbose('New label "{0}" found in line {1}, address {2:06x}'.\
                    format(w[0], n, LC0+LCi))
            symbol_table[w[0]] = LC0+LCi
            continue

        # If it is already known, something went wrong, because we can't
        # redefine a label. 
        else: 
            fatal(n, 'Attempt to redefine symbol "{0}" in line {1}'.\
                    format(w[0], p))


    # --- SUBSTEP DATA: See if we were given data to store ---
    
    # .BYTE stores one byte per whitespace separated word
    # This is a freebee because that is where we want to end up
    if w[0] == '.byte' or w[0] == '.b':
        LCi += len(w)-1 
        sc_labels.append((n, s, p)) 
        continue 

    # .WORD stores two bytes per whitespace separated word
    if w[0] == '.word' or w[0] == '.w':
        LCi += 2*(len(w)-1) 
        sc_labels.append((n, s, p)) 
        continue 
    
    # .LONG stores three bytes per whitespace separated word
    if w[0] == '.long' or w[0] == '.l':
        LCi += 3*(len(w)-1) 
        sc_labels.append((n, s, p)) 
        continue 


    # --- SUBSTEP SWITCHES: Handle Register Switches on the 65816 --- 
    
    # For the 65816, we have to take care of the register size switches
    # because the Immediate Mode instructions such as lda.# compile a different
    # number of bytes. We need to keep the directives themselves for the later
    # stages

    if MPU == '65816':

        # TODO Rewrite this horrible code once we are sure this is what we want
        # to do 
        # TODO make sure the switch to 16 bits only works in native mode
        if w[0] == '.a->8':
            a_len_offset = 0 
            sc_labels.append((n, s, p)) 
            continue 

        elif w[0] == '.a->16':
            a_len_offset = 1 
            sc_labels.append((n, s, p)) 
            continue 

        elif w[0] == '.xy->8':
            xy_len_offset = 0 
            sc_labels.append((n, s, p)) 
            continue 

        elif w[0] == '.xy->16':
            xy_len_offset = 1 
            sc_labels.append((n, s, p)) 
            continue 


    # --- SUBSTEP ADVANCE: See if we have the .advance directive ---
    if w[0] == '.advance' or w[0] == '.adv':
        is_number, r = convert_number(w[1]) 
        
        # If this is a symbol, it must be defined already or we're screwed
        if not is_number:

            try: 
                r = symbol_table[r]
            except KeyError:
                fatal(n, '.advance directive has undefined symbol "{0}"'.\
                        format(r))


        # Make sure the user is not attempting to advance backwards
        if r < (LCi+LC0):
            fatal(n, '.advance directive attempting to march backwards')

        # While we're here, we might as well already convert this to .byte 
        # (This is called "Do as I say, don't do as I do") 
        offset = r - (LCi+LC0)  
        zl = ' '.join(['00']*offset)
        new_p = INDENT+'.byte '+zl
        sc_labels.append((n, DATA_DONE, new_p))
        LCi = r-(LCi+LC0)
        verbose('Replaced .advance directive in line {0} by .byte directive'.\
                format(n)) 
        continue 


    # --- SUBSTEP SKIP: See if we have a .skip directive ---
    if w[0] == '.skip':
        is_number, r = convert_number(w[1]) 

        # If this is a symbol, it must be defined already or we're screwed
        if not is_number:

            try: 
                r = symbol_table[r]
            except KeyError:
                fatal(n, '.skip directive has undefined symbol "{0}"'.\
                        format(r))

        # While we're here, we might as well already convert this to .byte 
        # (This is called "Do as I say, don't do as I do") 
        zl = ' '.join(['00']*r)
        new_p = INDENT+'.byte '+zl
        sc_labels.append((n, DATA_DONE, new_p))
        LCi += r
        verbose('Replaced .skip directive in line {0} by .byte directive'.\
                format(n)) 
        continue 

    # If none of that was right, keep the old line 
    sc_labels.append((n, s, p)) 


verbose('STEP LABELS: Assigned value to all labels.') 

if args.verbose:
    dump_symbol_table(symbol_table, "after LABELS (numbers in hex)")

if args.dump:
    print('Local Labels:')
    if len(local_labels) > 0: 
        for ln, ll in local_labels:
            print('{0:5}: {1:06x} '.format(ln, ll))
        print('\n') 
    else: 
        print('  (none)\n')

dump(sc_labels) 


# -------------------------------------------------------------------
# ASSERT: At this point we should have all symbols present and known in the
# symbol table, and local labels in the local label list
verbose('ASSERTING that all symbols should now be known')


# -------------------------------------------------------------------
# PASS STEP REPLACE: Replace all symbols in code by correct numbers

sc_replace = []

for n, s, p in sc_labels:

    # We need to go word-by-word because somebody might have the bright idea of
    # defining lots of .byte data as symbols 
    wc = []
    ws = p.split() 
    s_temp = s

    for w in ws: 
        
        try:
            w = hexstr(symbol_table[w])
        except KeyError:
            pass
        else:
            s_temp = MODIFIED
        finally:
            wc.append(w)
                
    sc_replace.append((n, s_temp, INDENT+' '.join(wc))) 
        
verbose('STEP REPLACED: Replaced all symbols with their number values') 
dump(sc_replace) 


# -------------------------------------------------------------------
# PASS LOCALS: Replace all local label references by correct numbers

# Note we can't do math or modify local labels 

sc_locals = [] 

for n, s, p in sc_replace:

    w = p.split() 

    # We only allow the local references to be in the second word of the line,
    # that is, as an operand to an opcode. To be sure, we might want to check to
    # see if the first word is a mnemonic, but so far this is unnecessary
    if len(w) > 1 and w[1] == '+': 
        for ln, ll in local_labels: 
            if ln > n: 
                p = p.replace('+', hexstr(ll))
                s = MODIFIED
                break

    if len(w) > 1 and w[1] == '-': 
        for ln, ll in reversed(local_labels): 
            if ln < n: 
                p = p.replace('-', hexstr(ll))
                s = MODIFIED
                break

    sc_locals.append((n, s, p))

verbose('STEP LOCALS: Replaced all local labels with address values')
dump(sc_locals)


# -------------------------------------------------------------------
# ASSERT: At this point we should have comletely replaced all labels and symbols
# with numerical values.
verbose('ASSERTING there should be no labels or symbols left in the source')


# -------------------------------------------------------------------
# PASS BYTEDATA: Convert various data formats like .word and .string to .byte

# TODO these can be condensed once we know what is going on 

sc_bytedata = []

for n, s, p in sc_locals:

    w = p.split()

    # SUBSTEP BYTE: Change status of .byte instructions
    if w[0] == '.byte':
        sc_bytedata.append((n, DATA_DONE, p)) 
        continue 


    # SUBSTEP WORD: Produce two byte per word
    if w[0] == '.word':
        lw = w[1:]
        bl = []

        for aw in lw:
            
            is_number, r = convert_number(aw)

            # Paranoid, all symbols should be gone
            if not is_number:
                fatal(n, 'Found symbol left over in .word directive')

            for b in little_endian_16(r):
                bl.append(hexstr(b)) 

        p = INDENT+'.byte '+' '.join(bl) 
        sc_bytedata.append((n, DATA_DONE, p))
        verbose('Converted .word directive in line {0} to .byte directive'.\
                format(n)) 
        continue

    # SUBSTEP LONG: Produce three bytes per word
    if w[0] == '.long':
        lw = w[1:]
        bl = []

        for al in lw:
            
            is_number, r = convert_number(al)

            # Paranoid, all symbols should be gone
            if not is_number:
                fatal(n, 'Found symbol left over in .long directive')

            for b in little_endian_24(r):
                bl.append(hexstr(b)) 

        p = INDENT+'.byte '+' '.join(bl) 
        sc_bytedata.append((n, DATA_DONE, p))
        verbose('Converted .long directive in line {0} to .byte directive'.\
                format(n)) 
        continue

    # SUBSTEP STRING: Convert .string directive to bytes
    if w[0] == '.string' or w[0] == '.str':
        s = p.split('"')[1] 
        _, bl = string2bytes(s)  
        p = INDENT+'.byte '+' '.join(bl) 
        sc_bytedata.append((n, DATA_DONE, p))
        verbose('Converted .string directive in line {0} to .byte directive'.\
                format(n)) 
        continue 
    
    # SUBSTEP STRING0: Convert .string0 directive to bytes
    if w[0] == '.string0' or w[0] == '.str0':
        s = p.split('"')[1] 
        _, bl = string2bytes(s)  
        bl.append(hexstr(00)) 
        p = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((n, DATA_DONE, p))
        verbose('Converted .string0 directive in line {0} to .byte directive'.\
                format(n)) 
        continue 
    
    # SUBSTEP STRINGLF: Convert .stringlf directive to bytes
    if w[0] == '.stringlf' or w[0] == '.strlf':
        s = p.split('"')[1] 
        _, bl = string2bytes(s)  
        bl.append(hexstr(ord('\n'))) 
        p = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((n, DATA_DONE, p))
        verbose('Converted .stringlf directive in line {0} to .byte directive'.\
                format(n)) 
        continue 

    # If this is something else, keep it
    sc_bytedata.append((n, s, p))


verbose('STEP BYTEDATA: Converted all other data formats to .byte')
dump(sc_bytedata)


# -------------------------------------------------------------------
# ASSERT: At this point there should only be .byte data directives in the code
# with numerical values.
verbose('ASSERTING that all data is now contained in .byte directives')


# -------------------------------------------------------------------
# PASS 1BYTE: Convert all single-byte instructions to .byte directives

# Low-hanging fruit first: Compile the opcodes without operands

sc_1byte = []

for n, s, p in sc_bytedata: 

    w = p.split() 

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        sc_1byte.append((n, s, p)) 
    else: 

        if opcode_table[oc][OPCT_N_BYTES] == 1: 
            bl = INDENT+'.byte '+hexstr(oc)
            sc_1byte.append((n, CODE_DONE, bl))
        else:
            sc_1byte.append((n, s, p)) 


verbose('STEP 1BYTE: Assembled single byte instructions')
dump(sc_1byte)

# -------------------------------------------------------------------
# STEP BRANCHES: Assemble branch instructions

# All our branch instructions, including bra.l and phe.r on the 65816, should
# include the line they are on as the last entry in the payload 

# TODO These can be fused 

sc_branches = []

branches_8 = ['bra', 'beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs']
branches_16 = ['bra.l', 'phe.r']  

for n, s, p in sc_1byte: 

    # Skip the finished stuff
    if s == CODE_DONE or s == DATA_DONE:
            sc_branches.append((n, s, p))
            continue

    w = p.split() 

    if w[0] in branches_8:
        new_p = '.byte '+hexstr(mnemonics[w[0]])+' '  
        is_number,  branch_addr = convert_number(w[-1])

        # Paranoid, we should have converted all symbols
        if not is_number:
            fatal(n, 'Found unconverted symbol "{0}" during branch handling'.\
                    format(w[-1]))
        
        is_number,  target_addr = convert_number(w[-2])
        
        # Paranoid, we should have converted all symbols
        if not is_number:
            fatal(n, 'Found unconverted symbol "{0}" during branch handling'.\
                    format(w[-2]))

        opr = hexstr(lsb(target_addr - branch_addr - 2))
        sc_branches.append((n, CODE_DONE, INDENT+new_p+opr)) 
        continue 

    # 16-bit branches (65816 only) 
    if MPU == '65816' and w[0] in branches_16:

        oc_p = '.byte '+hexstr(mnemonics[w[0]])+' '  
        is_number,  branch_addr = convert_number(w[-1])

        # Paranoid, we should have converted all symbols
        if not is_number:
            fatal(n, 'Found unconverted symbol "{0}" during branch handling'.\
                    format(w[-1]))
        
        is_number,  target_addr = convert_number(w[-2])
        
        # Paranoid, we should have converted all symbols
        if not is_number:
            fatal(n, 'Found unconverted symbol "{0}" during branch handling'.\
                    format(w[-2]))

        bl, bm = little_endian_16(target_addr - branch_addr - 3)
        opr = INDENT+oc_p+' '+hexstr(bl)+' '+hexstr(bm)
        sc_branches.append((n, CODE_DONE, opr)) 
        continue 
 
    # Everything else 
    sc_branches.append((n, s, p)) 


verbose('STEP BRANCHES: Encoded all branch instructions')
dump(sc_branches) 


# -------------------------------------------------------------------
# PASS MOVE: Handle the 65816 move instructions MVP and MVN

# TODO code this 

# These two instructions are really, really annoying because they have two
# operands where every other instruction has one. 

sc_move = []

if MPU == '65816':

    for n, s, p in sc_branches:

        w = p.split()

        if w[0] == 'mvp' or w[0] == 'mvn':
            print('DUMMY Found move instruction, skipping') 
            continue 
        else:
            sc_move.append((n, s, p)) 

    verbose('PASS MOVE: Handled mvn/mvp instructions on the 65816 (DUMMY)')
    dump(sc_move) 

else:
    sc_move = sc_branches


# -------------------------------------------------------------------
# STEP MATH: Handle modifiers and math functions

# As discussed above, we distingish between "modifiers" and "math" by the number
# of whitespace delimited words the operand is made up of. Assumes that all
# symbols have been converted to numbers. At the end of this step, each opcode
# remaining should have one and only one operand

sc_math = [] 

for n, s, p  in sc_branches: 

    w = p.split() 

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        pass 
    else: 

        n_words = len(w)-1

        if n_words == 1:
            _, res = convert_number(w[1])
        elif n_words == 2:
            res = modify_operand(w[1:], n)
        elif n_words == 3:
            res = math_operand(w[1:], n)
        else:
            fatal(n, 'Too many termn for modifier or math routines')

        # Reassemble p as a string
        p = INDENT+w[0]+' '+hexstr(res)
        s = MODIFIED

    sc_math.append((n, s, p)) 

verbose('STEP MATH: Calculated all modifiers and math terms.')
dump(sc_math)


# -------------------------------------------------------------------
# PASS ALLOPR: Assemble all remaining operands

sc_allopr = []

for n, s, p in sc_math:

    w = p.split() 

    if MPU == '65816':

        # TODO Rewrite this horrible code once we are sure this is what we want
        # to do. Note it appears twice 
        # TODO make sure switch to 16 only works in native mode
        if w[0] == '.a->8':
            a_len_offset = 0 
            continue 

        elif w[0] == '.a->16':
            a_len_offset = 1 
            continue 

        elif w[0] == '.xy->8':
            xy_len_offset = 0 
            continue 

        elif w[0] == '.xy->16':
            xy_len_offset = 1 
            continue 

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        sc_allopr.append((n, s, p)) 
    else:

        # Get number of bytes in instruction
        n_bytes = opcode_table[oc][2]

        # Factor in register size if this is a 65816
        if MPU == '65816':

            if w[0] in a_imm:
                n_bytes += a_len_offset
            elif w[0] in xy_imm:
                n_bytes += xy_len_offset

        is_number, opr = convert_number(w[1]) 

        # Paranoid, we should have converted all symbols
        if not is_number:
            fatal(n, 'Symbol "{0}" mysteriously not converted'.format(opr))

        # We hand tuples to the next step 
        if n_bytes == 2: 
            bl = (lsb(opr), ) 
        elif n_bytes == 3:
            bl = little_endian_16(opr)
        elif n_bytes == 4:
            bl = little_endian_24(opr)
        else:
            fatal(n, 'Found {0} byte instruction in opcode list'.\
                    format(n_bytes))

        # p = INDENT+'.byte '+hexstr(oc)+' '+' '.join([hexstr(i) for i in bl])
        #
        p = '{0}.byte {1:02x} {2}'.\
                format(INDENT, oc, ' '.join([hexstr(i) for i in bl]))
        sc_allopr.append((n, CODE_DONE, p)) 

verbose('PASS ALLOPR: Assembled all remaining operands')
dump(sc_allopr)


# -------------------------------------------------------------------
# PASS BINONLY: strip out everything that isn't a .byte directive

# This is the last human-readable source listing. We need to keep the line
# numbers for the next step; we keep the status line so we can distinguish
# between data and code bytes 

sc_binonly = [(n, s, p) for n, s, p in sc_allopr if '.byte' in p] 

verbose('PASS BINONLY: Source completely converted to byte list') 
dump(sc_binonly) 


# -------------------------------------------------------------------
# PASS OPTIMIZE: Analyze and optimize code

# We don't perform automatic optimizations at the moment, but only give
# suggestions and warnings here. We need the line numbers here so we can offer
# the user suggestions

verbose('PASS ANALYZE: Searched for obvious errors and improvements') 

for n, _, p in sc_binonly:

    w = p.split()[1:]  # get rid of '.byte' directive 
    
    # SUBSTEP WDM: Check to see if we have WDM instruction
    if w[0] == '42':
        warning('Reserved instruction WDM (0x42) found in line {0}'.\
                format(n))
        continue 


# -------------------------------------------------------------------
# PASS PUREBYTES: Remove everything except the byte strings

def strip_byte(s):
    """Strip out the '.byte' directive from a string"""
    return s.replace('.byte ', '').strip()  

sc_purebytes = []

for _, _, p in sc_binonly: 
    p_bytes = strip_byte(p) 
    bl = [int(b, 16) for b in p_bytes.split()] 
    sc_purebytes.append(bl)

verbose('PASS PUREBYTES: Converted line to pure byte lists')

if args.dump: 

    for l in sc_purebytes:
        print('  ', end=' ') 
        for b in l:
            print('{0:02x}'.format(b), end=' ') 
        print() 
    print() 


# -------------------------------------------------------------------
# PASS TOBIN: Convert lists of bytes into one single byte list

sc_tobin = []

for i in sc_purebytes:
    sc_tobin.extend(i) 
    
objectcode = bytes(sc_tobin) 
code_size = len(objectcode) 

verbose('PASS TOBIN: Converted {0} lines of bytes to {1} bytes'.\
        format(len(sc_purebytes), code_size))


# -------------------------------------------------------------------
# STEP SAVEBIN: Save binary file 

with open(args.output, 'wb') as f:
    f.write(objectcode)

verbose('STEP SAVEBIN: Saved {0} bytes of object code as {1}'.\
        format(code_size, args.output))

if n_warnings != 0 and args.warnings:
    print('Generated {0} warning(s).'.format(n_warnings))


# -------------------------------------------------------------------
# STEP LIST: Create listing file

with open(args.listing, 'w') as f:
    f.write(title_string)
    f.write('Code listing for file {0}\n'.format(args.source))
    f.write('Generated on {0}\n'.format(time.asctime(time.localtime())))
    f.write('Target MPU: {0}\n'.format(MPU))
    time_end = timeit.default_timer() 
    f.write('Assembly time: {0:.5f} seconds\n'.format(time_end - time_start))
    if n_warnings != 0:
        f.write('Warnings generated: {0}\n'.format(n_warnings))
    if n_external_files != 0:
        f.write('External files loaded: {0}\n'.format(n_external_files))
    f.write('Code origin: {0:06x}\n'.format(LC0))
    f.write('Bytes of machine code generated: {0}\n'.format(code_size))

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
    f.write('\nSYMBOL TABLE:\n')

    if len(symbol_table) > 0: 

        for v in sorted(symbol_table):
            f.write('{0} : {1:x}\n'.format(v.rjust(ST_WIDTH), symbol_table[v]))
        f.write('\n')

    else:
        f.write('    (empty)\n')

# TODO add local labels list

verbose('STEP LIST: Saved listing as {0}'.format(args.listing))


# -------------------------------------------------------------------
# STEP HEXDUMP: Create hexdump file if requested

if args.hexdump:

    with open(HEX_FILE, 'w') as f:
        f.write(title_string)
        f.write('Hexdump file of {0}\n'.format(args.source)) 
        f.write('Generated on {0}\n\n'.format(time.asctime(time.localtime())))
        a65 = LC0
        f.write('{0:06x}: '.format(a65))
    
        c = 0 

        for e in objectcode: 
            f.write('{0:02x} '.format(e))
            c += 1
            if c % 16 == 0:
                f.write('\n')
                a65 += 16
                f.write('{0:06x}: '.format(a65))
        f.write('\n') 

    verbose('STEP HEXDUMP: Saved hexdump file as {0}'.format(HEX_FILE))


# -------------------------------------------------------------------
# STEP END: Sign off

time_end = timeit.default_timer() 
verbose('\nSuccess! All steps completed in {0:.5f} seconds.'.\
        format(time_end - time_start))
verbose('Enjoy the cake.')
sys.exit(0) 

### END ###
