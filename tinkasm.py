#!/usr/bin/env python3
# A Tinkerer's Assembler for the 6502/65c02/65816 in Forth
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 11. April 2016 (Commander Shepard's Birthday)

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

"""TinkAsm is a multi-pass assembler for the 6502/65c02/65816 MPUs. 
It is intended to be easy to modify by hobbyists without advanced knowledge
of how lexing and parsing works -- so they can "tinker" -- and is 
intentionally written in a "primitive" style of Python. See doc/MANUAL.md for
details.
"""


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
n_passes = 0            # Number of passes during processing
n_steps = 0             # Number of steps during processing
n_warnings = 0          # How many warnings were generated


### ARGUMENTS ###

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True,\
        help='Assembler source code file (required)')
parser.add_argument('-o', '--output', dest='output',\
        help='Binary output file (default TINK.BIN)', default='tink.bin')
parser.add_argument('-v', '--verbose',\
        help='Display additional information', action='store_true')
parser.add_argument('-d', '--dump',\
        help='Print intermediate steps as (long) lists', action='store_true')
parser.add_argument('-l', '--listing', action='store_true',\
        help='Create listing file TINK.LST')
parser.add_argument('-x', '--hexdump', action='store_true',\
        help='Create ASCII hexdump listing file TINK.HEX')
parser.add_argument('-w', '--warnings', default=True,\
        help='Disable warnings (default: print them)', action='store_false')
args = parser.parse_args()


### BASIC OUTPUT FUNCTIONS ###

def hexstr(n, i):
    """Given an integer, return a hex number as a string that has the '0x'
    portion stripped out and is limited to 24 bit (to correctly handle the
    negative numbers) and is n characters wide.
    """
    try:
        fmtstr = '{0:0'+str(n)+'x}'
        return fmtstr.format(i & 0x0ffffff)
    except TypeError as err:
        fatal(num, 'TypeError in hexstr for "{0}": {1}'.format(i, err)) 

def fatal(n, s):
    """Abort program because of fatal error during assembly.
    """
    print('FATAL ERROR in line {0}: {1}'.format(n, s))
    sys.exit(1)

def verbose(s):
    """Print information string given if --verbose flag was set. Later
    expand this by the option of priting to a log file instead.
    """
    if args.verbose:
        print(s)

def suggestion(n, s):
    """Print a suggestion of how the code could be better. This is to
    be used in the analysis pass.
    """
    print('SUGGESTION: {0} in line {1}'.format(s, n))

def warning(s):
    """If program called with -w or --warnings, print a warning string.
    """
    if args.warnings:
        print('WARNING: {0}'.format(s))


### CONSTANTS ###

TITLE_STRING = \
"""A Tinkerer's Assembler for the 6502/65c02/65816
Version BETA  23. February 2016
Copyright 2015, 2016 Scot W. Stevenson <scot.stevenson@gmail.com>
This program comes with ABSOLUTELY NO WARRANTY
"""

COMMENT = ';'       # Default comment marker
CURRENT = '*'       # Default current location counter
LOCAL_LABEL = '@'   # Default marker for local labels
SEPARATORS = '[.:]' # Legal separators in number strings for regex

HEX_PREFIX = '$'    # Default prefix for hexadecimal numbers
BIN_PREFIX = '%'    # Default prefix for binary numbers
DEC_PREFIX = '&'    # Default prefix for decimal numbers

ST_WIDTH = 24       # Number of chars of symbol from Symbol Table printed
INDENT = ' '*12     # Indent in whitespace for inserted instructions

LC0 = 0             # Start address of code ("location counter")
LCi = 0             # Index to where we are in code from the LC0

HEX_FILE = 'tink.hex'   # Name of hexdump file
LIST_FILE = 'tink.lst'  # Name of listing file

SUPPORTED_MPUS = ['6502', '65c02', '65816']

symbol_table = {}
local_labels = []


# Line Status. Leave these as strings so humans can read them. We start with
# SOURCE and end up with everything either as CODE_DONE or DATA_DONE. Make
# the strings the same length to make formatting easier

ADDED = 'ADDED      '      # Line that was added by the assembler
CODE_DONE = 'done (code)'  # Finished entry from code, now machine code bytes
CONTROL = 'CONTROL    '    # Entry for flow control w/ no code or data
DATA_DONE = 'done (data)'  # Finished entry from data, now pure bytes
MACRO = 'MACRO      '      # Line created by macro expansion
SOURCE = 'source     '     # Raw entry line (without whitespace)
MODIFIED = 'MODIFIED   '   # Entry that has been partially processed

# List of all directives. Note the local label character is not included
# because this is used to keep the user from using these words as labels

DIRECTIVES = ['.!a8', '.!a16', '.a8', '.a16', '.origin', '.axy8', '.axy16',\
        '.org', '.end', '.b', '.byte', '.w', '.word', '.l', '.long',\
        '.native', '.emulated', '.s', '.string', '.s0', '.string0', '.slf',\
        '.stringlf', '.!xy8', '.!xy16', '.xy8', '.xy16', COMMENT,\
        '.lsb', '.msb', '.bank', '.lshift', '.rshift', '.invert',\
        '.and', '.or', '.xor', CURRENT, '.macro', '.endmacro', '.invoke',\
        '.include', '.!native', '.!emulated']


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
    """Given a string marked with quotation marks, isolate what is between them
    and return the number of characters and a list of the hex ASCII values of
    the characters in that string. Assumes that there is one and only one
    string in the line that is delimited by quotation marks.
    """
    return len(s), [hexstr(2, ord(c)) for c in s]



def convert_number(s):
    """Convert a number string provided by the user in one of various
    formats to an integer we can use internally. See Manual for details
    on supported formats. Returns a tuple of a bool and an int, or a
    bool and a string.
    """

    # Remove separator markings such as "." or ":"
    s1 = re.sub(SEPARATORS, '', s)

    # By default, all numbers are hexadecimal. See if we were given a different
    # number such as "%01010000". Default is hex.
    c = s1[0]

    if c == DEC_PREFIX:
        BASE = 10
        s2 = s1[1:]
    elif c == BIN_PREFIX:
        BASE = 2
        s2 = s1[1:]
    elif c == HEX_PREFIX:
        BASE = 16
        s2 = s1[1:]
    else:
        BASE = 16
        s2 = s1

    # If we can convert this to a number, it's a number, otherweise we claim
    # it's a symbol. The default is to convert to a number, so "dead" will be
    # considered a hex number, not a label.
    
    try:
        r = int(s2, BASE)
        f = True
    except ValueError:
        r = s
        f = False

    return f, r


def lookup_symbol(s, n):
    """Given a string, look it up in the symbol table and return an int if
    found. Takes the line number for error message if symbol not in table. Use
    this instead of a straight lookup for error handling.
    """

    try:
        r = symbol_table[s]
    except KeyError:
        fatal(n, 'Symbol "{0}" unknown, lookup failed'.format(s))
    else:
        return r

# Math functions are contained in curly brace delimiters ("{1 + 1}"), and
# sanitized before being sent to Python3's EVAL function. Be careful changing
# the this function because is EVAL is dangerous (and possibly even evil). Math
# operators and even round brances must be separated by whitespace, so "{1
# * ( 2 + 2 )}" is legal, while "{(1*(2+2)}" will throw an error.  Note the MVP
# and MVN instructions of the 65816 are treated separately.

LEGAL_MATH = ['+', '-', '/', '//', '*', '(', ')',\
        '%', '**', '|', '^', '&', '<<', '>>', '~']

def convert_mathterm(s):
    """Given a string with numbers, variables, or Python3 math terms, make sure
    it only contains these elements so we can (more or less) safely use EVAL."""

    evalstring = []

    for w in s.split():

        # See if it's a number, converting it while we're at it
        is_number, opr = convert_number(w)

        if is_number:
            evalstring.append('{0:x}'.format(opr))
            continue

        # Okay, then see if it's an operand
        if w in LEGAL_MATH:
            evalstring.append(w)
            continue

        # Last chance, maybe it's a variable we already know about
        try:
            r = symbol_table[w]
        except KeyError:
            fatal(num, 'Illegal term "{0}" in math term'.format(w))

    print(evalstring)

    return ' '.join(evalstring)


# We support three modifiers to isolate various bytes of a two- or three-byte
# number

MODIFIER_FUNCS = {'.lsb': lsb, '.msb': msb, '.bank': bank}

def modify_operand(ls, n):
    """Given a list ls of two strings, apply the modifier function that is
    the first word to the actual operand that is the second word. Returns
    an int.
    """
    is_number, opr = convert_number(ls[1])

    # Paranoid, we shouldn't have symbols at this point
    if not is_number:
        fatal(n, 'Symbol found during modify function {0}'.format(ls[0]))

    try:
        r = MODIFIER_FUNCS[ls[0]](opr)
    except KeyError:
        fatal(n, 'Illegal modifier {0} given'.format(ls[0]))

    return r


def math_operand(ls, n):
    """Given a list ls of three strings, apply the math function in
    the second word to the two other operands. Returns an int. If we were
    given a symbol instead of a number (which can happend during PASS ASSIGN),
    try to look it up in the symbol table.
    """

    a1_is_number, a1 = convert_number(ls[0])

    if not a1_is_number:
        a1 = lookup_symbol(a1, n)

    a2_is_number, a2 = convert_number(ls[2])

    if not a2_is_number:
        a2 = lookup_symbol(a2, n)

    try:
        r = MATH_FUNCS[ls[1]](a1, a2)
    except KeyError:
        fatal(n, 'Illegal modifier {0} given'.format(ls[1]))

    return r


def convert_term(s, n):
    """Given a string that is either a number, a modifier and a number, or
    a math term, return the resulting number as an int. Also takes line
    number for errors. This is the highest level modifier or math function. 
    Returns an int.
    """

    w = s.split()
    n_words = len(w)

    if n_words == 1:
        _, res = convert_number(w[0])
    elif n_words == 2:
        res = modify_operand(w, n)
    elif n_words == 3:
        res = math_operand(w, n)
    else:
        fatal(n, 'Wrong number of terms for modifier or math routines')

    return res


def dump(l):
    """At each assembly stage, print the complete stage as a list. Produces
    an enormous amount of output.
    """
    if args.dump:

        # Fail gracefully: If we are given anything else than these number of
        # entries, don't print anything at all
        for line in l:

            n_entries = len(line)

            # For lines without status codes at the beginning of the code
            if n_entries == 2:
                print('{0:5d}: {1}'.format(line[0], repr(line[1])))
                continue

            # For lines with status codes
            elif n_entries == 3:
                print('{0:5d}: {1} {2!s}'.\
                        format(line[0], line[1], line[2]))
                continue

            # For lines with status and address codes
            elif n_entries == 4:
                print('{0:5d}: {1}  {2}  {3!s}'.\
                        format(line[0], line[1], line[2], line[3].strip()))

        print()


def dump_symbol_table(st, s=""):
    """Print Symbol Table to screen"""

    print('Symbol Table', s)

    if len(st) > 0:

        for v in sorted(st):
            print('{0} : {1:06x}'.format(v.rjust(ST_WIDTH), st[v]))
        print()

    else:
        print('    (empty)\n')



### PASSES AND STEPS ###

# The assembler works by connecting as many little steps as possible (see the
# Manual for details). Each step is given a title such as STATUS, and all
# requirements for that step are kept close to the actual processing.
#
# Each step passes on a list with a tuple that can contain at various times:
#
#   num - The original line number in the source for human reference
#   sta - A status string that shows how this line has been processed
#   adr - Address of the instruction in the 6502/65c02/65816 address space
#   pay - The payload of the line, either a string or later a list of bytes
#
# After each step we pass on the processed list and, if requested by the user,
# print a verbose information string and a dump of the processes lists.


# -------------------------------------------------------------------
# STEP BANNER: Set up timing, print banner

# This step is not counted

verbose(TITLE_STRING)
time_start = timeit.default_timer()
verbose('Beginning assembly, timer started.')


# -------------------------------------------------------------------
# STEP LOAD: Load original source code and add line numbers

# Line numbers start with 1 because this is for humans. At this point, the
# tuples in the list entries only contain two elements, line number and payload

sc_load = []

with open(args.source, "r") as f:
    sc_load = list(enumerate(f.readlines(), 1))

n_steps += 1
verbose('STEP IMPORT: Read {0} lines from {1}'.\
        format(len(sc_load), args.source))
dump(sc_load)


# -------------------------------------------------------------------
# PASS INCLUDE: Add content from extermal files specified by the INCLUDE
# directive

# The .include directive must be alone in the line and the second string must
# be the name of the file without any spaces or quotation marks

sc_include = []

for num, pay in sc_load:

    w = pay.split()

    # We haven't converted everything to lower case yet so we have to do it the
    # hard way here
    if len(w) > 1 and w[0].lower() == '.include':

        # Keep the line number of the .include directive for later reference
        with open(w[1], 'r') as f:
            sc_include.extend([(num, l) for l in f.readlines()])

        n_external_files += 1
        verbose('Included code from file "{0}"'.format(w[1]))

    else:
        sc_include.append((num, pay))

n_passes += 1
verbose('STEP INCLUDE: Added {0} external files'.format(n_external_files))
dump(sc_include)


# -------------------------------------------------------------------
# PASS EMPTY: Strip out empty lines

# We keep the line number of the empty lines to allow us to re-insert them for
# the listing file (currently not implemented)

sc_empty = []
empty_lines = []

for num, pay in sc_include:

    if pay.strip():
        sc_empty.append((num, pay))
    else:
        empty_lines.append(num)

n_passes += 1
verbose('STEP EMPTY: Removed {0} empty lines'.\
        format(len(sc_include)-len(sc_empty)))
verbose('Empty lines are {0}'.format(empty_lines))
dump(sc_empty)


# -------------------------------------------------------------------
# PASS COMMENTS: Remove comments that span whole lines

# We keep the comments so we can included them in the listing at some point
# (currently not implemented)

sc_comments = []
full_line_comments = []

for num, pay in sc_empty:

    if pay.strip()[0] != COMMENT:
        sc_comments.append((num, pay))
    else:
        full_line_comments.append(num)

n_passes += 1
verbose('STEP COMMENTS: Removed {0} full-line comments'.\
        format(len(sc_empty)-len(sc_comments)))
dump(sc_comments)


# -------------------------------------------------------------------
# PASS INLINES: Remove comments that are inline

# TODO keep inline comments in a separate list to reconstruct file listing

# Keep this function in this pass 
def remove_inlines(p):
    """Remove any inlines, defined by COMMENT char. We only strip the
    right side because we need the whitespace on the left later.
    """
    return p.split(COMMENT)[0].rstrip()

sc_inlines = []

for num, pay in sc_comments:
    sc_inlines.append((num, remove_inlines(pay)))

n_passes += 1
verbose('STEP INLINES: Removed all inline comments and terminating linefeeds')
dump(sc_inlines)


# -------------------------------------------------------------------
# PASS MPU: Find MPU type

sc_mpu = []
MPU = ''

for num, pay in sc_inlines:


    # We haven't converted to lower case yet so we have to do this by hand for
    # now 
    if '.mpu' in pay.lower():
        MPU = pay.split()[1].strip()
    else:
        sc_mpu.append((num, pay))

if not MPU:
    fatal(num, 'No ".mpu" directive found')

if MPU not in SUPPORTED_MPUS:
    fatal(num, 'MPU "{0}" not supported'.format(MPU))

n_passes += 1
verbose('PASS MPU: Found MPU "{0}", is supported'.format(MPU))
dump(sc_mpu)


# -------------------------------------------------------------------
# STEP OPCODES: Load opcodes depending on MPU type

# We use 65816 as the default. This step does not change the source code

# If we ever have have more than these three types, rewrite
if MPU == '6502':
    from opcodes6502 import opcode_table
elif MPU.lower() == '65c02':
    from opcodes65c02 import opcode_table
else:
    from opcodes65816 import opcode_table

# Paranoid: Make sure we were given the right number of opcodes
if len(opcode_table) != 256:
    fatal(0, 'Opcode table contains {0} entries, not 256'.\
        format(len(opcode_table)))

n_steps += 1
verbose('STEP OPCODES: Loaded opcode table for MPU {0}'.format(MPU))


# -------------------------------------------------------------------
# STEP MNEMONICS: Generate mnemonic list from opcode table

# This step does not change the source code

mnemonics = {opcode_table[n][1]:n for n, e in enumerate(opcode_table)}

# For the 6502 and 65c02, we have 'UNUSED' for the entries in the opcode table
# that are, well, not used. We get rid of them here. The 65816 does not have 
# any unused opcodes.
if MPU != '65816':
    del mnemonics['UNUSED']

n_steps += 1
verbose('STEP MNEMONICS: Generated mnemonics list')
verbose('Number of mnemonics found: {0}'.format(len(mnemonics.keys())))
if args.dump:
    print('Mnemonics found: {0}'.format(mnemonics.keys()))


# -------------------------------------------------------------------
# PASS STATUS: Add status strings to end of line

# Starting here, each line has a three-element tuple

sc_status = [(num, SOURCE, pay) for num, pay in sc_mpu]

n_passes += 1
verbose('PASS STATUS: Added status strings')
dump(sc_status)


# -------------------------------------------------------------------
# PASS BREAKUP: Split labels into their own lines, reformat others

# It's legal to have a label and either an opcode or a directive in the same
# line. To make life easier for the following routines, here we make sure each
# label has it's own line. Since we have gotten rid of the full-line comments,
# anything that is in the first column and is not whitespace is then considered
# a label. We don't distinguish between global and local labels at this point

# This step also cleans up the formating in the source codes for the user

# It is tempting to already start filling the symbol table here because we're
# touching all the labels and that would be far more efficient. However, 
# we keep these steps separate for ideological reasons.

sc_breakup = []

for num, sta, pay in sc_status:

    # Most of the lines will not be labels, which means the first character in
    # the line will be whitespace
    if pay[0] in string.whitespace:
        sc_breakup.append((num, sta, INDENT+pay.strip()))
        continue

    # We now know we have a label, we just don't know if it is alone in its
    # line ...
    w = pay.split()

    # .... but if yes, we're done already
    if len(w) == 1:
        sc_breakup.append((num, MODIFIED, pay.strip()))
        continue

    # Nope, there is something after the label
    sc_breakup.append((num, MODIFIED, w[0].strip()))
    rest = pay.replace(w[0], '').strip()  # Delete label from string
    sc_breakup.append((num, sta, INDENT+rest))

n_passes += 1
verbose('PASS BREAKUP: All labels now have a line to themselves')
dump(sc_breakup)

# -------------------------------------------------------------------
# PASS LOWER: Convert source to lower case

# We can't just lowercase everything in one list comprehension because the
# strings might contain upper cases we want to keep

# This pass must come after splitting the labels into their own lines or else we
# have problem with lines that have both a label and an string directive 

sc_lower = []

for num, sta, pay in sc_breakup:

    if '"' not in pay:
        sc_lower.append((num, sta, pay.lower()))
    else:
        w = pay.split()
        new_inst = w[0].lower()    # only convert the directive 
        new_pay = INDENT+new_inst+' '+' '.join(w[1:])
        sc_lower.append((num, sta, new_pay))

n_passes += 1
verbose('STEP LOWER: Converted all lines to lower case')
dump(sc_lower)

# -------------------------------------------------------------------
# PASS MACROS: Define macros

# This step assumes all labels are now in their own lines

sc_macros = []

macros = {}
macro_name = ''
are_defining = False

for num, sta, pay in sc_lower:

    w = pay.split()

    if not are_defining:

        # MACRO directive must be first in the line, no labels allowed
        if w[0] != '.macro':
            sc_macros.append((num, sta, pay))
            continue
        else:
            macro_name = w[1]
            macros[macro_name] = []
            are_defining = True
            verbose('Found macro "{0}" in line {1}'.format(w[1], num))

    else:

        if w[0] != ".endmacro":
            macros[macro_name].append((num, MACRO, pay))
        else:
            are_defining = False
            continue

n_passes += 1
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

# We accept both ".origin" and ".org".

sc_origin = []

# Origin line should be at the top of the list now
originline = sc_macros[0][2].strip().split()

if originline[0] != '.origin' and originline[0] != '.org':
    n = sc_macros[0][0]   # Fatal always needs a number line, fake it
    fatal(n, 'No ORIGIN directive found, must be first line after macros')

is_number, LC0 = convert_number(originline[1])

# ORIGIN may not take a symbol, because we haven't defined any yet
if not is_number:
    n = sc_macros[0][0]
    fatal(n, 'ORIGIN directive gives "{0}", not number as required')

sc_origin = sc_macros[1:]

n_steps += 1
verbose('STEP ORIGIN: Found ORIGIN directive, starting at {0:06x}'.\
        format(LC0))
dump(sc_origin)


# -------------------------------------------------------------------
# STEP END: Find .END directive

# End directive must be in the last line

endline = sc_origin[-1][2].strip().split()

if endline[0] != ".end":
    n = sc_origin[0][0]   # Fatal always needs a number line, fake it
    fatal(n, 'No END directive found, must be in last line')

sc_end = sc_origin[:-1]

n_steps += 1
verbose('STEP END: Found END directive in last line')
dump(sc_end)


# -------------------------------------------------------------------
# PASS ASSIGN: Handle assignments

# We accept two variants of assignment directives , "=" and ".equ". Since we've
# moved all labels to their own lines, any such directive must be the second
# word in the line

sc_assign = []

for num, sta, pay in sc_end:

    w = pay.split()

    # An assigment line must have three words at least. The "at least" part
    # is so we can modifiy and do math with the assignment lines. Anything
    # shorter is something else
    if len(w) < 3:
        sc_assign.append((num, sta, pay))
        continue

    # Sorry, Lisp and Forth coders, infix notation only
    if w[1] == '=' or w[1] == '.equ':
        sy, va = pay.split(w[1])

        symbol = sy.split()[-1]

        # We don't allow using directives as symbols because that gets very
        # confusing really fast
        if symbol in DIRECTIVES:
            fatal(num, 'Directive "{0}" cannot be redefined as a symbol'.\
                    format(symbol))

        value = convert_term(va, num)

        # If value is just a single string, then the conversion failed and 
        # we're struck with some "symbol = symbol" line
        if isinstance(value, str):
            fatal(num, 'Value "{0}" not defined'.\
                    format(value))

        symbol_table[symbol] = value
    else:
        sc_assign.append((num, sta, pay))

n_passes += 1
verbose('PASS ASSIGN: Assigned {0} symbols to symbol table'.\
        format(len(sc_end)-len(sc_assign)))
dump(sc_assign)

# Print symbol table
if args.verbose:
    dump_symbol_table(symbol_table, "after ASSIGN (numbers in hex)")


# -------------------------------------------------------------------
# PASS INVOKE: Insert macro definitions

# Macros must be expanded before we touch the .NATIVE and .AXY directives
# because those might be present in the macros

sc_invoke = []
pre_len = len(sc_assign)

for num, sta, pay in sc_assign:

    # Usually the line will not be a macro, so get it out of the way
    if '.invoke' not in pay:
        sc_invoke.append((num, sta, pay))
        continue

    w = pay.split()

    # Name of macro to invoke must be second word in line
    try:
        m = macros[w[1]]
    except KeyError:
        fatal(num, 'Attempt to invoke non-existing macro "{0}"'.format(w[1]))

    for ml in m:
        sc_invoke.append(ml)

    n_invocations += 1
    verbose('Expanding macro "{0}" into line {1}'.format(w[1], num))

post_len = len(sc_invoke)

n_passes += 1

# We give the "net" number of lines added because we also remove the invocation
# line itself
verbose('PASS INVOKE: {0} macro expansions, net {1} lines added'.\
        format(n_invocations, post_len - pre_len))
dump(sc_invoke)


# -------------------------------------------------------------------
# PASS MODES: Handle '.native' and '.emulated' directives on the 65816

# Since we have moved labels to their own lines, we assume that both .native
# and .emulated alone in their respective lines.

sc_modes = []

if MPU == '65816':

    for num, sta, pay in sc_invoke:

        if '.native' in pay:
            sc_modes.append((num, ADDED, INDENT+'clc'))
            sc_modes.append((num, ADDED, INDENT+'xce'))
            sc_modes.append((num, CONTROL, INDENT+'.!native'))
            continue

        if '.emulated' in pay:
            sc_modes.append((num, ADDED, INDENT+'sec'))
            sc_modes.append((num, ADDED, INDENT+'xce'))
            sc_modes.append((num, CONTROL, INDENT+'.!emulated'))

            # Emulation drops us into 8-bit modes for A, X, and Y
            # automatically, no REP or SEP commands needed
            sc_modes.append((num, CONTROL, INDENT+'.!a8'))
            sc_modes.append((num, CONTROL, INDENT+'.!xy8'))
            continue

        sc_modes.append((num, sta, pay))

    n_passes += 1
    verbose('PASS MODES: Handled 65816 native/emulated mode switches')
    dump(sc_modes)

else:
    sc_modes = sc_invoke    # Keep the chain going


# -------------------------------------------------------------------
# PASS AXY: Handle register size switches on the 65816

# We add the actual REP/SEP instructions as well as internal directives for the
# following steps.

sc_axy = []

if MPU == '65816':

    # We don't need to define these if we're not using a 65816
    AXY_INS = {'.a8':    ((ADDED, 'sep 20'), (CONTROL, '.!a8')),\
    '.a16': ((ADDED, 'rep 20'), (CONTROL, '.!a16')),\
    '.xy8': ((ADDED, 'sep 10'), (CONTROL, '.!xy8')),\
    '.xy16': ((ADDED, 'rep 10'), (CONTROL, '.!xy16')),\
    '.axy8': ((ADDED, 'sep 30'), (CONTROL, '.!a8'), (CONTROL, '.!xy8')),\
    '.axy16': ((ADDED, 'rep 30'), (CONTROL, '.!a16'), (CONTROL, '.!xy16'))}

    for num, sta, pay in sc_modes:
        have_found = False

        # Walk through every control directive for every line
        for ins in AXY_INS:

            # Because we moved labels to their own lines, we can assume that
            # register switches are alone in the line
            if ins in pay:

                for e in AXY_INS[ins]:
                    sc_axy.append((num, e[0], INDENT+e[1]))
                    have_found = True

        if not have_found:
            sc_axy.append((num, sta, pay))

    n_passes += 1
    verbose('PASS AXY: Registered 8/16 bit switches for A, X, and Y')
    dump(sc_axy)

else:
    sc_axy = sc_modes    # Keep the chain going


# -------------------------------------------------------------------
# PASS LABELS - Construct symbol table by finding all labels

# This is the equivalent of the traditional "Pass 1" in normal two-pass
# assemblers. We assume that the most common line by far will be mnemonics, and
# that then we'll see lots of labels (at some point, we should measure this).

# Though we don't start acutal assembling here, we do remember information for
# later passes when it is useful, like for branches and such, and get rid of
# some directives such as ADVANCE and SKIP

sc_labels = []

BRANCHES = ['bra', 'beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
        'bra.l', 'phe.r']

# These are only used for 65816. The offsets are used to calculate if an extra
# byte is needed for immediate forms such as lda.# with the 65816
a_len_offset = 0
xy_len_offset = 0
mpu_status = 'emulated'   # Start 65816 out in emulated status
A_IMM = ['adc.#', 'and.#', 'bit.#', 'cmp.#', 'eor.#', 'lda.#', 'ora.#', 'sbc.#']
XY_IMM = ['cpx.#', 'cpy.#', 'ldx.#', 'ldy.#']


# Keep this function in the labels pass
def has_current(s):
    """Given a string of the payload, see if we have been given the CURRENT
    symbol (usually '*') as part of the payload. This can be the case for one
    word; for two words if the second one is the CURRENT symbol (for example
    ".lsb *"); for three words if the first one is the symbol (for example "*
    + 1"). We test the reverse, making sure that '*' is not in the second
    position in an operand term with three words, which would be a
    multiplication. Returns a bool. 
    """

    w = s.split()[1:]
    res = False

    # A length of 1 means we have a "jmp *" situation; a '*' at second
    # place and a length of three means we have a multiply
    if CURRENT in s:

        if len(w) == 1 or not (w[1] == CURRENT and len(w) == 3):
            res = True

    return res


for num, sta, pay in sc_axy:

    w = pay.split()


    # --- SUBSTEP CURRENT: Replace the CURRENT symbol by current address

    # This must come before we handle mnemonics. Don't add a continue because
    # that will screw up the line count; we replace in-place
    if has_current(pay):
        pay = pay.replace(CURRENT, hexstr(6, LC0+LCi))
        w = pay.split()
        verbose('Current marker "{0}" in line {1}, replaced with {2}'.\
                format(CURRENT, num, hexstr(6, LC0+LCi)))


    # --- SUBSTEP MNEMONIC: See if we have a mnemonic ---

    # Because we are using Typist's Assembler Notation and every mnemonic
    # maps to one and only one opcode, we don't have to look at the operand of
    # the instruction at all, which is a lot simpler

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        pass
    else:

        # For branches, we want to remember were the instruction is to make our
        # life easier later
        if w[0] in BRANCHES:
            pay = pay + ' ' + hexstr(4, LC0+LCi)
            sta = MODIFIED
            verbose('Added address of branch to its payload in line {0}'.\
                    format(num))

        LCi += opcode_table[oc][2]

        # Factor in register size if this is a 65816
        if MPU == '65816':

            if w[0] in A_IMM:
                LCi += a_len_offset
            elif w[0] in XY_IMM:
                LCi += xy_len_offset

        sc_labels.append((num, sta, pay))
        continue


    # --- SUBSTEP LABELS: Figure out where our labels are ---

    # Labels and local labels are the only things that should be in the first
    # column at this point

    if pay[0] not in string.whitespace:

        # Local labels are easiest, start with them first
        if w[0] == LOCAL_LABEL:
            local_labels.append((num, LC0+LCi))
            verbose('New local label found in line {0}, address {1:06x}'.\
                    format(num, LC0+LCi))
            continue

        # This must be a real label. If we don't have it in the symbol table,
        # all is well and we add a new entry
        if w[0] not in symbol_table.keys():
            verbose('New label "{0}" found in line {1}, address {2:06x}'.\
                    format(w[0], num, LC0+LCi))
            symbol_table[w[0]] = LC0+LCi
            continue

        # If it is already known, something went wrong, because we can't
        # redefine a label, because that gets really confusing very fast
        else:
            fatal(num, 'Attempt to redefine symbol "{0}" in line {1}'.\
                    format(w[0], pay))


    # --- SUBSTEP DATA: See if we were given data to store ---
    
    # Because of ideological reasons, we don't convert the instructions at this
    # point, but just count their bytes

    # .BYTE stores one byte per whitespace separated word
    if w[0] == '.byte' or w[0] == '.b':
        LCi += len(w)-1
        sc_labels.append((num, sta, pay))
        continue

    # .WORD stores two bytes per whitespace separated word
    if w[0] == '.word' or w[0] == '.w':
        LCi += 2*(len(w)-1)
        sc_labels.append((num, sta, pay))
        continue

    # .LONG stores three bytes per whitespace separated word
    if w[0] == '.long' or w[0] == '.l':
        LCi += 3*(len(w)-1)
        sc_labels.append((num, sta, pay))
        continue

    # .STRING stores characters inside parens
    if w[0] == '.string' or w[0] == '.str':
        st = pay.split('"')[1]
        LCi += len(st)
        sc_labels.append((num, sta, pay))
        continue

    # .STRING0 stores characters inside parens plus a zero 
    if w[0] == '.string0' or w[0] == '.str0':
        st = pay.split('"')[1]
        LCi += len(st)+1
        sc_labels.append((num, sta, pay))
        continue

    # .STRINGLF stores characters inside parens plus a Line Feed char
    if w[0] == '.stringlf' or w[0] == '.strlf':
        st = pay.split('"')[1]
        LCi += len(st)+1
        sc_labels.append((num, sta, pay))
        continue


    # --- SUBSTEP SWITCHES: Handle Register Switches on the 65816 ---

    # For the 65816, we have to take care of the register size switches
    # because the Immediate Mode instructions such as lda.# compile a different
    # number of bytes. We need to keep the directives themselves for the later
    # stages while we are at it

    if MPU == '65816':

        if w[0] == '.!native':
            mpu_status = 'native'
            continue

        if w[0] == '.!emulated':
            mpu_status = 'emulated'
            continue

        if w[0] == '.!a8':
            a_len_offset = 0
            sc_labels.append((num, sta, pay))
            continue

        elif w[0] == '.!a16':

            # We can't switch to 16 bit A if we're not in native mode
            if mpu_status == 'emulated':
                fatal(num, 'Attempt to switch A to 16 bit in emulated mode')

            a_len_offset = 1
            sc_labels.append((num, sta, pay))
            continue

        elif w[0] == '.!xy8':
            xy_len_offset = 0
            sc_labels.append((num, sta, pay))
            continue

        elif w[0] == '.!xy16':

            # We can't switch to 16 bit X/Y if we're not in native mode
            if mpu_status == 'emulated':
                fatal(num, 'Attempt to switch X/Y to 16 bit in emulated mode')

            xy_len_offset = 1
            sc_labels.append((num, sta, pay))
            continue


    # --- SUBSTEP ADVANCE: See if we have the .advance directive ---
    
    if w[0] == '.advance' or w[0] == '.adv':
        is_number, r = convert_number(w[1])

        # If this is a symbol, it must be defined already or we're screwed
        if not is_number:
            r = lookup_symbol(r, num)

        # Make sure the user is not attempting to advance backwards
        if r < (LCi+LC0):
            fatal(num, '.advance directive attempting to march backwards')

        # While we're here, we might as well already convert this to .byte
        # though it violates our ideology ("Do as I say, don't do as I do")
        
        offset = r - (LCi+LC0)
        zl = ' '.join(['00']*offset)
        new_pay = INDENT+'.byte '+zl
        sc_labels.append((num, DATA_DONE, new_pay))
        LCi = r-(LCi+LC0)
        verbose('Replaced .advance directive in line {0} by .byte directive'.\
                format(num))
        continue


    # --- SUBSTEP SKIP: See if we have a .skip directive ---
    #
    if w[0] == '.skip':
        is_number, r = convert_number(w[1])

        # If this is a symbol, it must be defined already or we're screwed
        if not is_number:
            r = lookup_symbol(r, num)

        # While we're here, we might as well already convert this to .byte
        # though it is against our ideology ("Do as I say, don't do as I do")
        zl = ' '.join(['00']*r)
        new_pay = INDENT+'.byte '+zl
        sc_labels.append((num, DATA_DONE, new_pay))
        LCi += r
        verbose('Replaced .skip directive in line {0} by .byte directive'.\
                format(num))
        continue

    # If none of that was right, keep the old line
    sc_labels.append((num, sta, pay))


n_passes += 1
verbose('PASS LABELS: Assigned value to all labels.')

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
# CLAIM: At this point we should have all symbols present and known in the
# symbol table, and local labels in the local label list

verbose('CLAMING that all symbols should now be known')


# -------------------------------------------------------------------
# PASS REPLACE: Replace all symbols in code by correct numbers

sc_replace = []

for num, sta, pay in sc_labels:

    # We need to go word-by-word because somebody might be defining .byte 
    # data as symbols
    wc = []
    ws = pay.split()
    s_temp = sta

    for w in ws:

        try:
            # We don't define the number of digits because we have no idea
            # what the number they represent are supposed to be
            w = hexstr(6, symbol_table[w])
        except KeyError:
            pass
        else:
            s_temp = MODIFIED
        finally:
            wc.append(w)

    sc_replace.append((num, s_temp, INDENT+' '.join(wc)))

n_passes += 1
verbose('PASS REPLACED: Replaced all symbols with their number values')
dump(sc_replace)


# -------------------------------------------------------------------
# PASS LOCALS: Replace all local label references by correct numbers

# We don't modify local labels or do math on them

sc_locals = []

for num, sta, pay in sc_replace:

    w = pay.split()

    # We only allow the local references to be in the second word of the line,
    # that is, as an operand to an opcode

    if len(w) > 1 and w[1] == '+':
        for ln, ll in local_labels:
            if ln > num:
                pay = pay.replace('+', hexstr(6, ll))
                sta = MODIFIED
                break

    if len(w) > 1 and w[1] == '-':
        for ln, ll in reversed(local_labels):
            if ln < num:
                pay = pay.replace('-', hexstr(6, ll))
                sta = MODIFIED
                break

    sc_locals.append((num, sta, pay))

n_passes += 1
verbose('PASS LOCALS: Replaced all local labels with address values')
dump(sc_locals)


# -------------------------------------------------------------------
# CLAIM: At this point we should have completely replaced all labels and
# symbols with numerical values.

verbose('CLAMING there should be no labels or symbols left in the source')

# -------------------------------------------------------------------
# PASS MATH: Calculate all math terms. Assumes that all symbols and labels are
# now numbers that are identified as such by str.isdigit()

# Math terms are delimited by "{" and "}", which need to be surrounded by
# whitespace. They may only contain the basic math terms decribed below. See
# https://docs.python.org/3/library/stdtypes.html for a detailed description.
# Note invert ('~') and brackets ('(', ')') must be separated by a space from
# the number is inverting. 

def have_math(s):
    """See if a string contains the delimiter that signals the start of a math
    term ('{'). Returns a bool."""
    return True if '{' in s else False

sc_math = []
n_mathterms = 0

for num, sta, pay in sc_locals:
    
    if have_math(pay):

        # isolate math term string, saving what is before and after in the 
        # payload
        w1 = pay.split('{')
        pre_math = w1[0]
        w2 = w1[1].split('}')
        post_math = w2[1]

        p = w2[0]
        p_term = convert_mathterm(p)
        p_eval = eval(p_term)

        p_new = pre_math + str(p_eval) + post_math
        sc_math.append((num, MODIFIED, p_new))
    else:
        sc_math.append((num, sta, pay))

n_passes += 1
verbose('PASS MATH: Calculated all math terms.')
dump(sc_locals)

# -------------------------------------------------------------------
# PASS MODIFIERS: Handle modifiers 

# Assumes that all symbols have been converted to numbers and we have no more
# math terms. At the end of this step, each opcode remaining should have one and
# only one operand

sc_modifiers= []

for num, sta, pay in sc_math:

    w = pay.split()

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        pass
    else:
        opr = pay.replace(w[0], '').strip()
        res = convert_term(opr, num)

        try:
            pay = INDENT+w[0]+' '+hexstr(4, res)
        except TypeError:
            # A crash here means that we have an unidentified symbol, which in
            # turn probably means that we have a symbol that hasn't been defined
            # yet, or even more probably means that we have a typo in the symbol
            # name
            fatal(num, 'Modifier/math conversion error: {0}'.format(res))

        sta = MODIFIED

    sc_modifiers.append((num, sta, pay))

n_passes += 1
verbose('PASS MODIFIERS: Calculated all modifiers.')
dump(sc_modifiers)

# -------------------------------------------------------------------
# PASS BYTEDATA: Convert various data formats like .word and .string to .byte

sc_bytedata = []

for num, sta, pay in sc_modifiers:

    w = pay.split()

    # SUBSTEP BYTE: Change status of .byte instructions
    if w[0] == '.byte':
        bw = w[1:]
        bl = []

        for ab in bw:
            is_number, r = convert_number(ab)

            # We might still have an operand here, so we need to test if 
            # we really got a number
            if is_number:
                bl.append(hexstr(2, r))
            else:
                bl.append(r)

        pay = INDENT+'.byte '+' '.join(bl)

        sc_bytedata.append((num, DATA_DONE, pay))
        continue

    # SUBSTEP WORD: Produce two byte per word
    if w[0] == '.word':
        ww = w[1:]
        bl = []

        for aw in ww:
            is_number, r = convert_number(aw)

            if is_number:
                for b in little_endian_16(r):
                    bl.append(hexstr(2, b))
            else:
                bl.append(r)

        pay = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((num, DATA_DONE, pay))
        verbose('Converted .word directive in line {0} to .byte directive'.\
                format(num))
        continue

    # SUBSTEP LONG: Produce three bytes per word
    if w[0] == '.long':
        lw = w[1:]
        bl = []

        for al in lw:

            is_number, r = convert_number(al)

            if is_number:
                for b in little_endian_24(r):
                    bl.append(hexstr(2, b))
            else:
                bl.append(r)

        pay = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((num, DATA_DONE, pay))
        verbose('Converted .long directive in line {0} to .byte directive'.\
                format(num))
        continue

    # SUBSTEP STRING: Convert .string directive to bytes
    if w[0] == '.string' or w[0] == '.str':
        st = pay.split('"')[1]
        _, bl = string2bytes(st)
        pay = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((num, DATA_DONE, pay))
        verbose('Converted .string directive in line {0} to .byte directive'.\
                format(num))
        continue

    # SUBSTEP STRING0: Convert .string0 directive to bytes
    if w[0] == '.string0' or w[0] == '.str0':
        st = pay.split('"')[1]
        _, bl = string2bytes(st)
        bl.append(hexstr(2, 00))
        pay = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((num, DATA_DONE, pay))
        verbose('Converted .string0 directive in line {0} to .byte directive'.\
                format(num))
        continue

    # SUBSTEP STRINGLF: Convert .stringlf directive to bytes
    if w[0] == '.stringlf' or w[0] == '.strlf':
        st = pay.split('"')[1]
        _, bl = string2bytes(st)
        bl.append(hexstr(2, ord('\n')))
        pay = INDENT+'.byte '+' '.join(bl)
        sc_bytedata.append((num, DATA_DONE, pay))
        verbose('Converted .stringlf directive in line {0} to .byte directive'.\
                format(num))
        continue

    # If this is something else, just keep it
    sc_bytedata.append((num, sta, pay))

n_passes += 1
verbose('PASS BYTEDATA: Converted all other data formats to .byte')
dump(sc_bytedata)


# -------------------------------------------------------------------
# CLAIM: At this point there should only be .byte data directives in the code
# with numerical values.

verbose('CLAMING that all data is now contained in .byte directives')


# -------------------------------------------------------------------
# PASS 1BYTE: Convert all single-byte instructions to .byte directives

# Low-hanging fruit first: Compile the opcodes without operands

sc_1byte = []

for num, sta, pay in sc_bytedata:

    w = pay.split()

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        sc_1byte.append((num, sta, pay))
    else:

        if opcode_table[oc][2] == 1:    # look up length of instruction
            bl = INDENT+'.byte '+hexstr(2, oc)
            sc_1byte.append((num, CODE_DONE, bl))
        else:
            sc_1byte.append((num, sta, pay))

n_passes += 1
verbose('PASS 1BYTE: Assembled single byte instructions')
dump(sc_1byte)


# -------------------------------------------------------------------
# PASS BRANCHES: Assemble branch instructions

# All our branch instructions, including bra.l and phe.r on the 65816, should
# include the line they are on as the last entry in the payload at this point

sc_branches = []

# Keep this definition in the branches pass
BRANCHES = {
    '6502': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs'],\
    '65c02': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
        'bra'],\
    '65816': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
        'bra', 'bra.l', 'phe.r']}

for num, sta, pay in sc_1byte:

    # Skip stuff that is already done
    if sta == CODE_DONE or sta == DATA_DONE:
        sc_branches.append((num, sta, pay))
        continue

    w = pay.split()

    if w[0] in BRANCHES[MPU]:
        new_pay = '.byte '+hexstr(2, mnemonics[w[0]])+' '
        _, branch_addr = convert_number(w[-1])
        _, target_addr = convert_number(w[-2])
        opr = hexstr(2, lsb(target_addr - branch_addr - 2))
        sc_branches.append((num, CODE_DONE, INDENT+new_pay+opr))
        continue

    if MPU == '65816' and w[0] in BRANCHES[MPU]: 
        new_pay = '.byte '+hexstr(2, mnemonics[w[0]])+' '
        _, branch_addr = convert_number(w[-1])
        _, target_addr = convert_number(w[-2])
        bl, bm = little_endian_16(target_addr - branch_addr - 3)
        opr = INDENT+new_pay+hexstr(2, bl)+' '+hexstr(2, bm)
        sc_branches.append((num, CODE_DONE, opr))
        continue

    # Everything else
    sc_branches.append((num, sta, pay))

n_passes += 1
verbose('PASS BRANCHES: Encoded all branch instructions')
dump(sc_branches)


# -------------------------------------------------------------------
# PASS MOVE: Handle the 65816 move instructions MVP and MVN

# These two instructions are really, really annoying because they have two
# operands where every other instruction has one. We assume that the operand is
# split by a comma

sc_move = []

if MPU == '65816':

    for num, sta, pay in sc_branches:

        w = pay.split()

        if w[0] == 'mvp' or w[0] == 'mvn':

            tmp_pay = pay.replace(w[0], '').strip()
            a1, a2 = tmp_pay.split(',')

            src = convert_term(a1, num)
            des = convert_term(a2, num)

            oc = mnemonics[w[0]]

            # Remember destination comes before source with move instruction
            pay1 = INDENT+'.byte '+hexstr(2, oc)+' '
            pay2 = hexstr(2, lsb(des))+' '+hexstr(2, lsb(src))
            pay = pay1+pay2
            sta = CODE_DONE

        sc_move.append((num, sta, pay))

    n_passes += 1
    verbose('PASS MOVE: Handled mvn/mvp instructions on the 65816')
    dump(sc_move)

else:
    sc_move = sc_branches


# -------------------------------------------------------------------
# PASS ALLIN: Assemble all remaining operands

# This should remove all CONTROL entries as well

sc_allin = []

for num, sta, pay in sc_move:

    w = pay.split()

    if MPU == '65816':

        # TODO Rewrite this horrible code once we are sure this is what we want
        # to do. Note it appears twice
        # TODO make sure switch to 16 only works in native mode
        if w[0] == '.!a8':
            a_len_offset = 0
            continue

        elif w[0] == '.!a16':
            a_len_offset = 1
            continue

        elif w[0] == '.!xy8':
            xy_len_offset = 0
            continue

        elif w[0] == '.!xy16':
            xy_len_offset = 1
            continue

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        sc_allin.append((num, sta, pay))
    else:

        # Get number of bytes in instruction
        n_bytes = opcode_table[oc][2]

        # Factor in register size if this is a 65816
        if MPU == '65816':

            if w[0] in A_IMM:
                n_bytes += a_len_offset
            elif w[0] in XY_IMM:
                n_bytes += xy_len_offset

        _, opr = convert_number(w[1])

        # We hand tuples to the next step
        if n_bytes == 2:
            bl = (lsb(opr), )
        elif n_bytes == 3:
            bl = little_endian_16(opr)
        elif n_bytes == 4:
            bl = little_endian_24(opr)
        else:
            # This should never happen, obviously, but we're checking anyway
            fatal(num, 'Found {0} byte instruction in opcode list'.\
                    format(n_bytes))

        # Reassemble payload as a byte instruction. We keep the data in
        # human-readable form instead of converting it to binary data
        pay = '{0}.byte {1:02x} {2}'.\
                format(INDENT, oc, ' '.join([hexstr(2, i) for i in bl]))
        sc_allin.append((num, CODE_DONE, pay))

n_passes += 1
verbose('PASS ALLIN: Assembled all remaining operands')
dump(sc_allin)


# -------------------------------------------------------------------
# PASS VALIDATE: Make sure we only have .byte instructions

# We shouldn't have anything left now that isn't a byte directive
# This pass does not change the source file

for num, _, pay in sc_allin:

    w = pay.split()

    if w[0] != '.byte':
        fatal(num, 'Found illegal opcode/directive "{0}"'.format(pay.strip()))

n_passes += 1
verbose('PASS VALIDATE: Confirmed that all lines are now byte data')

# -------------------------------------------------------------------
# PASS BYTECHECK: Make sure all byte values are actually 0 to 256

for num, _, pay in sc_allin:

    bl = pay.split()[1:]

    for b in bl:
        if int(b) > 256 or int(b) < 0:
            fatal(num, 'Value of "{0}" does not fit in a byte'.format(b))

n_passes +=1
verbose('PASS BYTECHECK: All byte values are in range from 0 to 256')

# -------------------------------------------------------------------
# PASS ADR: Add addresses for human readers and listing generation

# This produces the final human readable version and is the basis for the
# listing file

def format_adr16(i):
    """Convert an integer to a 16 bit hex address string for the listing
    file
    """
    return '{0:04x}'.format(i & 0xffff)

def format_adr24(i):
    """Convert an integer to a 24 bit hex address string for the listing
    file. We use a separator for the bank byte
    """
    return '{0:02x}:{1:04x}'.format(bank(i), i & 0xffff)

format_adr_mpu = {'6502': format_adr16,\
        '65c02': format_adr16,\
        '65816': format_adr24}

sc_adr = []
LCi = 0

for num, sta, pay in sc_allin:

    b = len(pay.split())-1
    adr = format_adr_mpu[MPU](LC0+LCi)
    sc_adr.append((num, sta, adr, pay))
    LCi += b

n_passes += 1
verbose('PASS ADR: Added MPU address locations to each byte line')
dump(sc_adr)


# -------------------------------------------------------------------
# PASS OPTIMIZE: Analyze and optimize code

# We don't perform automatic optimizations at the moment, but only provide
# suggestions and warnings here. We need the line numbers so we can offer
# the user suggestions based on his original source code

for num, _, _, pay in sc_adr:

    w = pay.split()[1:]  # get rid of '.byte' directive

    # SUBSTEP WDM: Check to see if we have WDM instruction
    if w[0] == '42':
        warning('Reserved instruction WDM (0x42) found in line {0}'.\
                format(num))
        continue

n_passes += 1
verbose('PASS ANALYZE: Searched for obvious errors and improvements')


# -------------------------------------------------------------------
# PASS PUREBYTES: Remove everything except byte values (ie, remove .byte)

def strip_byte(s):
    """Strip out the '.byte' directive from a string"""
    return s.replace('.byte ', '').strip()

sc_purebytes = []

for _, _, _, pay in sc_adr:
    pay_bytes = strip_byte(pay)
    bl = [int(b, 16) for b in pay_bytes.split()]
    sc_purebytes.append(bl)

n_passes += 1
verbose('PASS PUREBYTES: Converted all lines to pure byte lists')

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

n_passes += 1
verbose('PASS TOBIN: Converted {0} lines of bytes to one list of {1} bytes'.\
        format(len(sc_purebytes), code_size))


# -------------------------------------------------------------------
# STEP SAVEBIN: Save binary file

with open(args.output, 'wb') as f:
    f.write(objectcode)

n_steps += 1
verbose('STEP SAVEBIN: Saved {0} bytes of object code as {1}'.\
        format(code_size, args.output))


# -------------------------------------------------------------------
# STEP WARNINGS: Print warnings unless user said not to
#
if n_warnings != 0 and args.warnings:
    print('Generated {0} warning(s).'.format(n_warnings))

n_steps += 1


# -------------------------------------------------------------------
# STEP LIST: Create listing file if requested

# This is a simple listing file, we are waiting to figure out what we need
# before we create a more complex one

LEN_BYTELIST = 11
LEN_INSTRUCTION = 15
ELLIPSIS = ' (...)'

if args.listing:

    with open(LIST_FILE, 'w') as f:

        # Header
        f.write(TITLE_STRING)
        f.write('Code listing for file {0}\n'.format(args.source))
        f.write('Generated on {0}\n'.format(time.asctime(time.localtime())))
        f.write('Target MPU: {0}\n'.format(MPU))
        time_end = timeit.default_timer()
        if n_external_files != 0:
            f.write('External files loaded: {0}\n'.format(n_external_files))
        f.write('Number of passes executed: {0}\n'.format(n_passes))
        f.write('Number of steps executed: {0}\n'.format(n_steps))
        f.write('Assembly time: {0:.5f} seconds\n'.format(time_end - time_start))
        if n_warnings != 0:
            f.write('Warnings generated: {0}\n'.format(n_warnings))
        f.write('Code origin: {0:06x}\n'.format(LC0))
        f.write('Bytes of machine code: {0}\n'.format(code_size))

        # Code listing
        f.write('\nLISTING:\n')
        f.write('       Line Address  Bytes       Instruction\n')


        # We start with line 1 because that is the way editors count lines
        c = 1
        sc_tmp = sc_axy     # This is where we take the instructions from

        for num, _, adr, pay in sc_adr:

            # Format bytelist
            bl = pay.replace('.byte', '').strip()

            # If the line is too long, replace later values by "..."
            if len(bl) > LEN_BYTELIST:
                bl = bl[:LEN_BYTELIST-len(ELLIPSIS)]+ELLIPSIS
            else:
                padding = (LEN_BYTELIST - len(bl))*' '
                bl = bl+padding

            # Format instruction
            instr = '(data)'

            for i in range(len(sc_tmp)):

                # Since we delete entries from sc_tmp, this loop will fail at
                # some point because the list gets shorter. That's when we're
                # done
                try:
                    num_i, sta_i, pay_i = sc_tmp[i]
                except IndexError:
                    break
                else:
                    # Skip leftover CONTROL instructions
                    if sta_i == CONTROL:
                        continue
                    if num_i == num:
                        instr = pay_i.strip()
                        del sc_tmp[i]

            # Format one line 
            l = '{0:5d} {1:5d} {2}  {3!s} {4}\n'.\
                    format(c, num, adr, bl, instr)

            f.write(l)
            c += 1


        # Add macro list
        f.write('\nMACROS:\n')

        if len(macros) > 0:

            for m in macros.keys():
                f.write('Macro "{0}"\n'.format(m))

                for ml in macros[m]:
                    f.write('    {0}\n'.format(ml))

            f.write('\n\n')

        else:
            f.write(INDENT+'(none)\n\n')


        # Add symbol table
        f.write('SYMBOL TABLE:\n')

        if len(symbol_table) > 0:

            for v in sorted(symbol_table):
                f.write('{0} : {1:06x}\n'.\
                        format(v.rjust(ST_WIDTH), symbol_table[v]))
            f.write('\n')

        else:
            f.write(INDENT+'(empty)\n')


    n_steps += 1
    verbose('STEP LIST: Saved listing as {0}'.format(LIST_FILE))


# -------------------------------------------------------------------
# STEP HEXDUMP: Create hexdump file if requested

if args.hexdump:

    with open(HEX_FILE, 'w') as f:
        f.write(TITLE_STRING)
        f.write('Hexdump file of {0}'.format(args.source))
        f.write(' (total of {0} bytes)\n'.format(code_size))
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

    n_steps += 1
    verbose('STEP HEXDUMP: Saved hexdump file as {0}'.format(HEX_FILE))


# -------------------------------------------------------------------
# STEP END: Sign off

time_end = timeit.default_timer()
verbose('\nSuccess! All steps completed in {0:.5f} seconds.'.\
        format(time_end - time_start))
verbose('Enjoy your cake.')
sys.exit(0)

### END ###
