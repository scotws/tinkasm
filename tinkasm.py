# A Tinkerer's Assembler for the 6502/65c02/65816 in Forth
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 27. Aug 2016

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
    """Given an integer i, return a hex number with n digits as a string that
    has the '0x' portion stripped out and is limited to 24 bit (to correctly
    handle the negative numbers) and is n characters wide.  
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
Version BETA  28. August 2016
Copyright 2015, 2016 Scot W. Stevenson <scot.stevenson@gmail.com>
This program comes with ABSOLUTELY NO WARRANTY
"""

COMMENT = ';'       # Comment marker, default is ";"
CURRENT = '.*'      # Current location counter, default is ".*"
ASSIGNMENT = '.equ' # Assignment directive, default is ".equ"
LOCAL_LABEL = '@'   # Marker for anonymous labels, default is "@"
SEPARATORS = '[.:]' # Legal separators in number strings for regex

HEX_PREFIX = '$'    # Prefix for hexadecimal numbers, default is "$"
BIN_PREFIX = '%'    # Prefix for binary numbers, default is "%"
DEC_PREFIX = '&'    # Prefix for decimal numbers, default "&"

LEFTMATH = '{'      # Opening bracket for Python math terms
RIGHTMATH = '}'     # Closing bracket for Python math terms

ST_WIDTH = 24       # Number of chars of symbol from Symbol Table printed
INDENT = ' '*12     # Indent in whitespace for inserted instructions

LC0 = 0             # Start address of code ("location counter")
LCi = 0             # Index to where we are in code from the LC0

HEX_FILE = 'tink.hex'   # Name of hexdump file
LIST_FILE = 'tink.lst'  # Name of listing file

SUPPORTED_MPUS = ['6502', '65c02', '65816']
DATA_DIRECTIVES = ['.byte', '.word', '.long']

symbol_table = {}
anon_labels = []

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

# List of all directives. Note the anonymous label character is not included
# because this is used to keep the user from using these words as labels

DIRECTIVES = ['.!a8', '.!a16', '.a8', '.a16', '.origin', '.axy8', '.axy16',\
        '.end', ASSIGNMENT, '.byte', '.word', '.long', '.advance', '.skip',\
        '.native', '.emulated', '.mpu',\
        '.!xy8', '.!xy16', '.xy8', '.xy16', COMMENT,\
        '.lsb', '.msb', '.bank', '.lshift', '.rshift', '.invert',\
        '.and', '.or', '.xor', CURRENT, '.macro', '.endmacro', '.invoke',\
        '.include', '.!native', '.!emulated', LEFTMATH, RIGHTMATH]


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

MODIFIERS = {'.lsb': lsb, '.msb': msb, '.bank': bank}

def little_endian_16(n):
    """Given a number, return a tuple with two bytes in correct format"""
    return lsb(n), msb(n)

def little_endian_24(n):
    """Given a number, return a tuple with three bytes in correct format"""
    return lsb(n), msb(n), bank(n)

def string2bytestring(s):
    """Given a string marked with quotation marks, return a string that is a
    comma-separated list of their hex ASCII values. Assumes that there is one 
    and only one string in the line that is delimited by quotation marks.
    Example: "abc" -> "61, 62, 63"
    """

    # We slice one character off both ends because those are the quotation marks
    t = ' '.join([hexstr(2, ord(c))+',' for c in s[1:-1]])

    # We don't want to add a comma to the end of the list because either the
    # string was at the end of the line or there is already a comma present
    # from the listing
    return t[:-1]

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

    if c == DEC_PREFIX: # usually '&'
        BASE = 10
        s2 = s1[1:]
    elif c == BIN_PREFIX: # usually '%'
        BASE = 2
        s2 = s1[1:]
    elif c == HEX_PREFIX: # usually '$'
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


# Math functions are contained in curly brace delimiters ("{1 + 1}"), and
# sanitized before being sent to Python3's EVAL function. Be careful changing
# the this function because is EVAL is dangerous (and possibly even evil). Math
# operators and even round brances must be separated by whitespace, so "{1
# * ( 2 + 2 )}" is legal, while "{(1*(2+2)}" will throw an error.  Note the MVP
# and MVN instructions of the 65816 are treated separately.

LEGAL_MATH = ['+', '-', '/', '//', '*', '(', ')',\
        '%', '**', '|', '^', '&', '<<', '>>', '~']

def sanitize_math(s):
    """Given a string with numbers, variables, or Python3 math terms, make sure
    it only contains these elements so we can (more or less) safely use EVAL."""

    evalstring = []

    for w in s.split():

        # See if it's a number, converting it while we're at it
        f_num, opr = convert_number(w)

        if f_num:
            evalstring.append(str(opr))
            continue

        # Okay, then see if it's an operand
        if w in LEGAL_MATH:
            evalstring.append(w)
            continue

        # Last chance, maybe it's a variable we already know about. In theory,
        # we should have converted them all already, of course
        try:
            r = symbol_table[w]
        except KeyError:
            fatal(num, 'Illegal term "{0}" in math term'.format(w))
        else:
            evalstring.append(str(r))

    return ' '.join(evalstring)


def do_math(s):
    """Given a payload string with math term inside, replace the math term by
    a string representation of the number by invoking the Python EVAL routine.
    What is before and after the math term is conserved. Returns a string 
    representation of a hex number
    """

    # Save the parts that are left and right of the math term
    w1 = s.split(LEFTMATH, 1)
    pre_math = w1[0]
    w2 = w1[1].split(RIGHTMATH, 1)
    post_math = w2[1]

    mt = sanitize_math(w2[0])
    r = eval(mt)

    return pre_math + hexstr(6, r) + post_math

def vet_newsymbol(s):
    """Given a word that the user wants to define as a new symbol, make sure
    that is is legal. Does not return anything if okay, jumps to fatal error
    if not.
    """

    # We don't allow using directives as symbols because that gets very
    # confusing really fast
    if s in DIRECTIVES:
        fatal(num, 'Directive "{0}" cannot be redefined as a symbol'.\
                format(s))

    # We don't allow using mnemonics as symbols because that screws up other
    # stuff and is really weird anyway
    if s in mnemonics.keys(): 
        fatal(num, 'Mnemonic "{0}" cannot be redefined as a symbol'.\
                format(s))

    # We don't allow redefining existing symbols, this catches various errors 
    if s in symbol_table.keys():
        fatal(num, 'Symbol "{0}" already defined'.format(s))

def replace_symbols(sc_tmp):
    """Given the complete source code, replace all symbols we know so far. 
    Called from various steps, assumes we have stripped out all commentary,
    assumes that sc_tmp has three entries (no addresses yet). Will also 
    replace symbols in math terms. Returns the modified source code, dumps
    text if requested. 
    """

    sc_replaced = []
    global n_passes
    
    for num, pay, sta in sc_tmp:

        # Skip this all if we have a label, which can't ever contain a symbol.
        # This also takes care of any problems with indents
        if pay[0] not in string.whitespace:
            sc_replaced.append((num, pay, sta))
            continue

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

        sc_replaced.append((num, INDENT+' '.join(wc), s_temp))

    n_passes += 1
    verbose('PASS REPLACED: Replaced currently known symbols with their values')
    dump(sc_replaced, "nps")

    return sc_replaced


def dump(ls, fs='npsa'):
    """At each assembly stage, print the complete stage as a list, with the
    exact type of elements to print depending on the format string. Produces
    an enormous amount of output. Format string controls which parts of the 
    line are printed: 
    
        'n' for line number ('num', element 0) 
        'p' for payload ('pay', element 1)
        's' for status ('sta', element 2) 
        'a' for address ('adr', element 3)

    In addition, there is the letter 'r' to print the 'raw payload' (element
    1) with linefeeds etc.
    """

    if args.dump:

        for l in ls:

            s = ''

            if 'n' in fs:
                s = s + "{0:5d}: ".format(l[0]) 
            if 's' in fs:
                s = s + "{0} ".format(l[2])
            if 'a' in fs:
                s = s + "{0!s} ".format(l[3])
            if 'p' in fs:
                s = s + "{0!s}".format(l[1].rstrip())
            if 'r' in fs:
                s = s + "{0}".format(repr(l[1]))

            print(s.rstrip())

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


def convert_term(n, s): 
    """Given the line number and a string that can be a number (in various 
    formats), a symbol (that must already be known), a modifier (such as
    '.lsb'), a math term (such as '{ 1 + 1 }') or a combination of modifier
    and math term ('.lsb { 1 + 1 }'), return a string represenation of the
    hex number they result in. Abort with fatal error, printing the line
    number, if conversion is unsuccessful.

    Characters ('a') and strings ("abc") are not included in this routine
    because there are assumed to have been already converted as part of a 
    diffent step.
    """
    
    # --- SUBSTEP 1: KNOWN SYMBOL ---
       
    # We test to see if the term is a symbol before it is a number. Therefore, by
    # default, terms such as 'abc' will be seen as symbols; numbers must start
    # with '0x' or '$' if they only have hex letters

    s = s.strip()

    try:
        r = symbol_table[s]
    except KeyError:
        pass
    else:
        return r

    # --- SUBSTEP 2: NUMBER ('1', '%000001') ---
    
    f_num, r = convert_number(s)

    if f_num:
        return r

    # --- SUBSTEP 3: MATH TERM ('{ 1 + 1 }') ---

    if (s[0] == LEFTMATH):
        _, r = convert_number(do_math(s))
        return r

    # --- SUBSTEP 3: MODIFICATION ('.lsb 0102', '.msb { 1 + 1 }') ---

    w = s.split()

    if (w[0] in MODIFIERS):

        # The parameter offered to the modification can be a number, symbol, 
        # math term etc itself. We isolate it and send it and call ourselves to
        # convert it again
        rt = convert_term(n, s.split(' ', 1)[1])
        r = MODIFIERS[w[0]](rt)
        return r 

    # --- SUBSTEP OOPS: If we made it to here, something is wrong ---
    fatal(n, 'Cannot convert term "{0}"'.format(s))



### PASSES AND STEPS ###

# The assembler works by connecting as many little steps as possible (see the
# Manual for details). Each step is given a title such as STATUS, and all
# requirements for that step are kept close to the actual processing.
#
# Each step passes on a list with a tuple that contains at various times:
#
#   num - The original line number in the source for human reference
#   pay - The payload of the line, either a string or later a list of bytes
#   sta - A status string that shows how this line has been processed
#   adr - Address of the instruction in the 6502/65c02/65816 address space
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
dump(sc_load, 'nr')


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
dump(sc_include, 'nr')


# -------------------------------------------------------------------
# PASS EMPTY: Strip out empty lines

# We want to cut down the number of lines we have to process as early as
# possible. First, we get rid of the empty lines, then we get rid of the
# comments. We keep the line number of the empty lines to allow us to re-insert
# them for the listing file (currently not implemented)

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
verbose('Empty lines were {0}'.format(empty_lines))
dump(sc_empty, 'nr')


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
verbose('Full-lines comments were {0}'.format(full_line_comments))
dump(sc_comments, 'nr')


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
dump(sc_inlines, 'np')


# -------------------------------------------------------------------
# PASS MPU: Find MPU type

sc_mpu = []
MPU = ''

for num, pay in sc_inlines:

    # We haven't converted to lower case yet so we have to do this by hand 
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
dump(sc_mpu, 'np')


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
    print()


# -------------------------------------------------------------------
# PASS STATUS: Add status strings to end of line

# Starting here, each line has a three-element tuple

sc_status = [(num, pay, SOURCE) for num, pay in sc_mpu]

n_passes += 1
verbose('PASS STATUS: Added status strings')
dump(sc_status, 'nps')


# -------------------------------------------------------------------
# PASS BREAKUP: Split labels into their own lines, reformat others

# It's legal to have a label and either an opcode or a directive in the same
# line. To make life easier for the following routines, here we make sure each
# label has it's own line. Since we have gotten rid of the full-line comments,
# anything that is in the first column and is not whitespace is then considered
# a label. We don't distinguish between global and anonymous labels at this point

# This step also cleans up the formating in the source codes for the user
# by standardizing the indent

# It is tempting to already start filling the symbol table here because we're
# touching all the labels and that would be far more efficient. However, 
# we keep these steps separate for ideological reasons.

sc_breakup = []

for num, pay, sta in sc_status:

    # Most of the lines will not be labels, which means the first character in
    # the line will be whitespace
    if pay[0] in string.whitespace:
        sc_breakup.append((num, INDENT+pay.strip(), sta))
        continue

    # We now know we have a label, we just don't know if it is alone in its
    # line ...
    w = pay.split()

    # .... but if yes, we're done already
    if len(w) == 1:
        sc_breakup.append((num, pay.strip(), MODIFIED))
        continue

    # Nope, there is something after the label
    sc_breakup.append((num, w[0].strip(), MODIFIED))
    rest = pay.replace(w[0], '').strip()  # Delete label from string
    sc_breakup.append((num, INDENT+rest, sta))

n_passes += 1
verbose('PASS BREAKUP: All labels now have a line to themselves')
dump(sc_breakup, "nps")


# -------------------------------------------------------------------
# PASS LOWER: Convert source to lower case

# We can't just lowercase everything in one list comprehension because the
# strings might contain upper cases we want to keep

# This pass must come after splitting the labels into their own lines or else we
# have problem with lines that have both a label and an string directive 

# TODO test this more extensively, possibly string and character conversion must
# be moved up

sc_lower = []

for num, pay, sta in sc_breakup:

    if '"' not in pay:
        sc_lower.append((num, pay.lower(), sta))
    else:
        w = pay.split()
        new_inst = w[0].lower()    # only convert the directive 
        new_pay = INDENT+new_inst+' '+' '.join(w[1:])
        sc_lower.append((num, new_pay, sta))

n_passes += 1
verbose('STEP LOWER: Converted all lines to lower case')
dump(sc_lower, "nps")


# -------------------------------------------------------------------
# PASS MACROS: Define macros

# This step assumes all labels are now in their own lines

sc_macros = []

macros = {}
macro_name = ''
are_defining = False

for num, pay, sta in sc_lower:

    w = pay.split()

    if not are_defining:

        # MACRO directive must be first in the line, no labels allowed
        if w[0] != '.macro':
            sc_macros.append((num, pay, sta))
            continue
        else:
            macro_name = w[1]
            macros[macro_name] = []
            are_defining = True
            verbose('Found macro "{0}" in line {1}'.format(w[1], num))

    else:

        if w[0] != ".endmacro":
            macros[macro_name].append((num, pay, MACRO))
        else:
            are_defining = False
            continue

n_passes += 1
verbose('STEP MACROS: Defined {0} macros'.format(len(macros)))
dump(sc_macros, "nps")

# TODO pretty format this
if args.dump:

    for m in macros.keys():
        print('Macro {0}:'.format(m))

        for ml in macros[m]:
            print('    {0}'.format(repr(ml)))

    print()


# -------------------------------------------------------------------
# STEP ORIGIN: Find .ORIGIN directive

# Origin line should be at the top of the list now. 

sc_origin = []

originline = sc_macros[0][1].strip().split()

if originline[0] != '.origin':
    n = sc_macros[0][0]   # Fatal always needs a number line, fake it
    fatal(n, 'No ORIGIN directive found, must be first line after macros')

f_num, LC0 = convert_number(originline[1])

# ORIGIN may not take a symbol, because we haven't defined any yet, and
# we don't accept math or modifiers either
if not f_num:
    n = sc_macros[0][0]
    fatal(n, 'ORIGIN directive gives "{0}", not number as required')

sc_origin = sc_macros[1:]

n_steps += 1
verbose('STEP ORIGIN: Found ORIGIN directive, starting at {0:06x}'.\
        format(LC0))
dump(sc_origin, "nps")


# -------------------------------------------------------------------
# STEP END: Find .END directive

# End directive must be in the last line

endline = sc_origin[-1][1].strip().split()

if endline[0] != ".end":
    n = sc_origin[0][0]   # Fatal always needs a number line, fake it
    fatal(n, 'No END directive found, must be in last line')

sc_end = sc_origin[:-1]

n_steps += 1
verbose('STEP END: Found END directive in last line')
dump(sc_end, "nps")


# -------------------------------------------------------------------
# PASS SIMPLE ASSIGN: Handle first round of basic assigments

# Handle the simplest form of assignments, those were a number is assigned to
# a variable ('.equ jack 1') or a symbol we already know ('.equ jill jack')
# without modifiers or math. We can't do full assignments until we've dealt with
# labels, but we can do this now to cut down on the number of lines we have to
# go through every time. 

sc_simpleassign = []

for num, pay, sta in sc_end:

    w = pay.split()
 
    if w[0] != ASSIGNMENT:
        sc_simpleassign.append((num, pay, sta))
        continue

    # We want the length to be exactly three words so we don't get involved
    # modifiers or math terms
    if len(w) != 3:
        sc_simpleassign.append((num, pay, sta))
        continue

    vet_newsymbol(w[1])

    # In '.equ frog abc', 'abc' can either be a symbol or a number. We want it
    # to be a symbol by default, so we check the symbol table first
    try:
        r = symbol_table[w[2]]
        symbol_table[w[1]] = r
        continue
    except KeyError:
        pass

    f_num, r = convert_number(w[2])

    # If it's a number, add it to the symbol table, otherwise we'll have to wait
    # until we've figured out more stuff
    if f_num:
        symbol_table[w[1]] = r
    else:
        sc_simpleassign.append((num, pay, sta))

n_passes += 1
verbose('PASS SIMPLE ASSIGN: Assigned {0} new symbol(s) to symbol table'.\
        format(len(sc_end)-len(sc_simpleassign)))
dump(sc_simpleassign, "nps")

# Print symbol table
if args.verbose:
    dump_symbol_table(symbol_table, "after SIMPLEASSIGN (numbers in hex)")


# -------------------------------------------------------------------
# PASS REPLACE (1): Handle known assignments
sc_replaced01 = replace_symbols(sc_simpleassign)


# -------------------------------------------------------------------
# PASS INVOKE: Insert macro definitions

# Macros must be expanded before we touch the .NATIVE and .AXY directives
# because those might be present in the macros
# TODO add parameters, which might force us to move this to a later point

sc_invoke = []
pre_len = len(sc_replaced01)

for num, pay, sta in sc_replaced01:

    w = pay.split()

    # Usually the line will not be a macro, so get it out of the way
    if w[0] != '.invoke':
        sc_invoke.append((num, pay, sta))
        continue

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
dump(sc_invoke, "nps")


# -------------------------------------------------------------------
# PASS STRINGS: Convert strings to bytes and byte lists

# Since strings are constants, we can convert them very early on

# Since we have gotten rid of comments, every quotation mark must belong to
# a string. We convert these strings to comma-separated byte lists 
# Example: "aaa" -> 61, 61, 61

# This method could also work for single-character strings in instructions such
# as 'lda.# "a"'. However, this could be source of errors because the assembler
# will happily also try to turn multi-character strings into byte lists in this
# instance as well ('lda.# "ab"' would become 'lda.# 61, 62'). Use 
# single-quotation marks for this, see next step.

sc_strings = []
p = re.compile('\".*?\"')

for num, pay, sta in sc_invoke:

        # Most lines won't have a string, so we skip them first
        if '"' not in pay:
            sc_strings.append((num, pay, sta))
            continue 

        ma = p.findall(pay)
        new_pay = pay

        # Replace the contents of the strings with a comma-separated list of 
        # bytes
        for m in ma:

            # It is an error to use double quotation marks for a single
            # character, use 'a' instead, see next step
            if len(m) == 3:
                fatal(num,\
                        "Found single-character string {0}, use 'x' for chars".\
                        format(m))

            new_pay = new_pay.replace(m, string2bytestring(m))
        
        sc_strings.append((num, new_pay, sta))

verbose('PASS STRINGS: Converted all strings to byte lists')
dump(sc_strings, "nps")


# -------------------------------------------------------------------
# PASS CHARS: Convert single characters delimited by single quotes

# Since characters are constants, we can convert them early on

# Single characters are put in single quotes ('a'). This step must come after
# the conversion of strings to make sure that we don't accidently find single
# characters that are part of a string.

sc_chars = []
p = re.compile("\'.\'")

for num, pay, sta in sc_strings:
    
    # We usually don't have a single quote in a line so we get rid of that
    # immediately
    if "'" not in pay:
        sc_chars.append((num, pay, sta))
        continue

    ma = p.findall(pay)
    new_pay = pay

    # Replace each instance of a single-quoted string with the string of its
    # hex number. Note that ord() returns unicode, but we currently slice off 
    # anything that is not the last two hex digits
    for m in ma:
        new_pay = new_pay.replace(m, hexstr(2, ord(m[1])))

    sc_chars.append((num, new_pay, sta))

verbose('PASS CHARS: Converted all single characters to bytes')
dump(sc_chars, "nps")

# -------------------------------------------------------------------
# PASS MODES: Handle '.native' and '.emulated' directives on the 65816

# Since we have moved labels to their own lines, we assume that both .native
# and .emulated alone in their respective lines.

sc_modes = []

if MPU == '65816':

    for num, pay, sta in sc_chars:

        if '.native' in pay:
            sc_modes.append((num, INDENT+'clc', ADDED))
            sc_modes.append((num, INDENT+'xce', ADDED))
            sc_modes.append((num, INDENT+'.!native', CONTROL))
            continue

        if '.emulated' in pay:
            sc_modes.append((num, INDENT+'sec', ADDED))
            sc_modes.append((num, INDENT+'xce', ADDED))
            sc_modes.append((num, INDENT+'.!emulated', CONTROL))

            # Emulation drops us into 8-bit modes for A, X, and Y
            # automatically, no REP or SEP commands needed
            sc_modes.append((num, INDENT+'.!a8', CONTROL))
            sc_modes.append((num, INDENT+'.!xy8', CONTROL))
            continue

        sc_modes.append((num, pay, sta))

    n_passes += 1
    verbose('PASS MODES: Handled 65816 native/emulated mode switches')
    dump(sc_modes, "nps")

else:
    sc_modes = sc_strings # Keep the chain going


# -------------------------------------------------------------------
# PASS AXY: Handle register size switches on the 65816

# We add the actual REP/SEP instructions as well as internal directives for the
# following steps.

sc_axy = []

# We don't need to define these if we're not using a 65816
if MPU == '65816':

    AXY_INS = {'.a8':    (('sep 20', ADDED), ('.!a8', CONTROL)),\
    '.a16': (('rep 20', ADDED), ('.!a16', CONTROL)),\
    '.xy8': (('sep 10', ADDED), ('.!xy8', CONTROL)),\
    '.xy16': (('rep 10', ADDED), ('.!xy16', CONTROL)),\
    '.axy8': (('sep 30', ADDED), ('.!a8', CONTROL), ('.!xy8', CONTROL)),\
    '.axy16': (('rep 30', ADDED), ('.!a16', CONTROL), ('.!xy16', CONTROL))}

    for num, pay, sta in sc_modes:
        have_found = False

        # Walk through every control directive for every line
        for ins in AXY_INS:

            # Because we moved labels to their own lines, we can assume that
            # register switches are alone in the line
            if ins in pay:

                for e in AXY_INS[ins]:
                    sc_axy.append((num, INDENT+e[0], e[1]))
                    have_found = True

        if not have_found:
            sc_axy.append((num, pay, sta))

    n_passes += 1
    verbose('PASS AXY: Registered 8/16 bit switches for A, X, and Y')
    dump(sc_axy, "nps")

else:
    sc_axy = sc_modes    # Keep the chain going


# -------------------------------------------------------------------
# PASS SPLIT MOVES - Split up Move instructions on the 65816

# The MVP and MVN instructions are really, really annoying because they have two
# operands where every other instruction has one. We deal with this by splitting
# the instructions into two lines, dealing with the operands, and then later
# putting them back together again. We assume that the operands are separated by
# a comma ('mvp 00,01')

sc_splitmove = []

if MPU == '65816':

    for num, pay, sta in sc_axy:

        w = pay.split()

        if w[0] == 'mvp' or w[0] == 'mvn':

            # Catch malformed move instructions
            try:
                l_pay, r_pay = pay.split(',') 
            except ValueError:
                fatal(num, 'Malformed move instruction')

            sc_splitmove.append((num, INDENT+l_pay.strip(), MODIFIED))
            sc_splitmove.append((num, INDENT+'DUMMY '+r_pay.strip(), ADDED)) 

        else:
            sc_splitmove.append((num, pay, sta))

    n_passes += 1
    verbose('PASS SPLIT MOVES: Split mvn/mvp instructions on the 65816')
    dump(sc_splitmove, "nps")

else:
    sc_splitmove = sc_axy


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

for num, pay, sta in sc_splitmove:

    w = pay.split()

    # --- SUBSTEP CURRENT: Replace the CURRENT symbol by current address

    # This must come before we handle mnemonics. Don't add a continue because
    # that will screw up the line count; we replace in-place
    if CURRENT in pay: 
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

        sc_labels.append((num, pay, sta))
        continue


    # --- SUBSTEP LABELS: Figure out where our labels are ---

    # Labels and anonymous labels are the only things that should be in the first
    # column at this point

    if pay[0] not in string.whitespace:

        # Local labels are easiest, start with them first
        if w[0] == LOCAL_LABEL:
            anon_labels.append((num, LC0+LCi))
            verbose('New anonymous label found in line {0}, address {1:06x}'.\
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
    # point, but just count their bytes. Note these entries are not separated by
    # spaces, but by commas, so we have to split them all over again.

    d = pay.split(',')

    # .BYTE stores one byte per comma-separated word
    if w[0] == '.byte':
        LCi += len(d)
        sc_labels.append((num, pay, sta))
        continue

    # .WORD stores two bytes per comma-separated word
    if w[0] == '.word':
        LCi += 2*(len(d))
        sc_labels.append((num, pay, sta))
        continue

    # .LONG stores three bytes per comma-separated word
    if w[0] == '.long':
        LCi += 3*(len(d))
        sc_labels.append((num, pay, sta))
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
            sc_labels.append((num, pay, sta))
            continue

        elif w[0] == '.!a16':

            # We can't switch to 16 bit A if we're not in native mode
            if mpu_status == 'emulated':
                fatal(num, 'Attempt to switch A to 16 bit in emulated mode')

            a_len_offset = 1
            sc_labels.append((num, pay, sta))
            continue

        elif w[0] == '.!xy8':
            xy_len_offset = 0
            sc_labels.append((num, pay, sta))
            continue

        elif w[0] == '.!xy16':

            # We can't switch to 16 bit X/Y if we're not in native mode
            if mpu_status == 'emulated':
                fatal(num, 'Attempt to switch X/Y to 16 bit in emulated mode')

            xy_len_offset = 1
            sc_labels.append((num, pay, sta))
            continue


    # --- SUBSTEP ADVANCE: See if we have the .advance directive ---
    
    if w[0] == '.advance':
        r = convert_term(num, w[1])

        # Make sure the user is not attempting to advance backwards
        if r < (LCi+LC0):
            fatal(num, '.advance directive attempting to march backwards')

        # While we're here, we might as well already convert this to .byte
        # though it violates our ideology ("Do as I say, don't do as I do")
        
        offset = r - (LCi+LC0)
        zl = ' '.join(['00']*offset)
        new_pay = INDENT+'.byte '+zl
        sc_labels.append((num, new_pay, DATA_DONE))
        LCi = r-(LCi+LC0)
        verbose('Replaced .advance directive in line {0} by .byte directive'.\
                format(num))
        continue


    # --- SUBSTEP SKIP: See if we have a .skip directive ---
    
    if w[0] == '.skip':
        r = convert_term(num, w[1])

        # While we're here, we might as well already convert this to .byte
        # though it is against our ideology ("Do as I say, don't do as I do")
        zl = ' '.join(['00']*r)
        new_pay = INDENT+'.byte '+zl
        sc_labels.append((num, new_pay, DATA_DONE))
        LCi += r
        verbose('Replaced .skip directive in line {0} by .byte directive'.\
                format(num))
        continue

    # If none of that was right, keep the old line
    sc_labels.append((num, pay, sta))


n_passes += 1
verbose('PASS LABELS: Assigned value to all labels.')
dump(sc_labels, "nps")

if args.verbose:
    dump_symbol_table(symbol_table, "after LABELS (numbers in hex)")

if args.dump:
    print('Anonymous Labels:')
    if len(anon_labels) > 0:
        for ln, ll in anon_labels:
            print('{0:5}: {1:06x} '.format(ln, ll))
        print('\n')
    else:
        print('  (none)\n')


# -------------------------------------------------------------------
# PASS ASSIGN: Handle complex assignments

# We accept assignments in the form ".equ <SYM> <NBR>". Since we've
# moved all labels to their own lines, any such directive must be the first
# word in the line

sc_assign = []

for num, pay, sta in sc_labels:

    w = pay.split()

    # Leave if this is not an assignment (line doesn't start with '.equ')
    if w[0] != ASSIGNMENT:
        sc_assign.append((num, pay, sta))
        continue
        
    vet_newsymbol(w[1]) 
    
    # Everything after the assignment directive and the symbol has to be part of
    # the term
    cp = pay.strip()
    rs = convert_term(num, cp.split(' ', 2)[2])
    symbol_table[w[1]] = rs

n_passes += 1
verbose('PASS ASSIGN: Assigned {0} symbols to symbol table'.\
        format(len(sc_labels)-len(sc_assign)))
dump(sc_assign, "nps")

# Print symbol table
if args.verbose:
    dump_symbol_table(symbol_table, "after ASSIGN (numbers in hex)")


# -------------------------------------------------------------------
# PASS REPLACE (2): Handle known assignments, reprise
sc_replaced02 = replace_symbols(sc_assign)


# -------------------------------------------------------------------
# CLAIM: At this point we should have all symbols present and known in the
# symbol table, and anonymous labels in the anonymous label list

verbose('CLAMING that all symbols should now be known')

# -------------------------------------------------------------------
# PASS DATA: Convert various data formats like .byte

sc_data = []

for num, pay, sta in sc_replaced02:

    w = pay.split()

    # This is for .byte, .word, and .long
    if w[0] not in DATA_DIRECTIVES:
        sc_data.append((num, pay, sta))
        continue 

    # Stuff like .advance and .skip might already be done, we don't have to do
    # it over
    if sta == DATA_DONE or sta == CODE_DONE:
        sc_data.append((num, pay, sta))
        continue 

    # Regardless of which format we have, it should contain a list of
    # comma-separated terms
    ps = pay.strip().split(' ', 1)[1] # Get rid of the directive
    ts = ps.split(',')
    new_t = []

    for t in ts:
        new_t.append(convert_term(num, t))

    # We now have a list of the numbers, but need to break them down into
    # their bytes. This could be solved a lot more elegantly, but this is
    # easier to understand
    byte_t = []

    if w[0] == '.byte':
        byte_t = new_t

    elif w[0] == '.word':
        for n in new_t:
            for b in little_endian_16(n):
                byte_t.append(b)

    elif w[0] == '.long':
        for n in new_t:
            for b in little_endian_24(n):
                byte_t.append(b)

    # Reassemble the datastring, getting rid of the trailing comma
    new_pay = INDENT+'.byte '+' '.join([hexstr(2, b) for b in byte_t])
    
    sc_data.append((num, new_pay, DATA_DONE))

n_passes += 1
verbose('PASS DATA: Converted all data formats to .byte')
dump(sc_data, "nps")

# -------------------------------------------------------------------
# PASS MATH

# Replace all math terms that are left in the text, eg 'jmp { label + 2 }'. 
# None of these should be in assignments any more

sc_math = []

for num, pay, sta in sc_data:

    if LEFTMATH not in pay:
        sc_math.append((num, pay, sta))
        continue

    # Life is still easy if we only have one bracket
    if pay.count(LEFTMATH) == 1:
        sc_math.append((num, do_math(pay), MODIFIED))
        continue

    # More than one math term, so we have to do this the hard way
    while LEFTMATH in pay:
        pay = do_math(pay)

    sc_math.append((num, pay, MODIFIED))
    

n_passes += 1
verbose('PASS MATH: replaced all math terms by numbers')
dump(sc_math, "nps")


# -------------------------------------------------------------------
# PASS MODIFY

# Replace all modify terms that are left in the text, eg 'lda.# .msb 1000'. 
# None of these should be in assignments any more

sc_modify = []

def has_modifier(s):
    """Given a string with space-separated words, return True if one of 
    these words is a modifier, else false.
    """
    return bool([i for i in MODIFIERS if i in s])


for num, pay, sta in sc_math:

    if has_modifier(pay):
        
        # We need to use next entry once we find a modifier, so we need to make
        # this iterable
        new_pay = ""
        ws = iter(pay.split())

        for w in ws:

            if w in MODIFIERS:
                f_num, r = convert_number(next(ws))

                if f_num:
                    w = hexstr(6, MODIFIERS[w](r))
                else: 
                    fatal(num, 'Modifier operand "{0}" not a number'.format(w))

            new_pay = new_pay + ' ' + w
             
        pay = new_pay
        sta = MODIFIED

    sc_modify.append((num, INDENT+pay.strip(), sta))

n_passes += 1
verbose('PASS MODIFY: replaced all modifier terms by numbers')
dump(sc_modify, "nps")


# -------------------------------------------------------------------
# PASS ANONYMOUS: Replace all anonymous label references by correct numbers

# We don't modify anonymous labels or do math on them

sc_anons = []

for num, pay, sta in sc_modify:

    w = pay.split()

    # We only allow the anonymous references to be in the second word of the line,
    # that is, as an operand to an opcode

    if len(w) > 1 and w[1] == '+':
        for ln, ll in anon_labels:
            if ln > num:
                pay = pay.replace('+', hexstr(6, ll))
                sta = MODIFIED
                break

    if len(w) > 1 and w[1] == '-':
        for ln, ll in reversed(anon_labels):
            if ln < num:
                pay = pay.replace('-', hexstr(6, ll))
                sta = MODIFIED
                break

    sc_anons.append((num, pay, sta))

n_passes += 1
verbose('PASS ANONYMOUS: Replaced all anonymous labels with address values')
dump(sc_anons, "nps")

# -------------------------------------------------------------------
# CLAIM: At this point we should have completely replaced all labels and
# symbols with numerical values.

verbose('CLAMING there should be no labels or symbols left in the source')


# -------------------------------------------------------------------
# CLAIM: At this point there should only be .byte data directives in the code
# with numerical values.

verbose('CLAMING that all data is now contained in .byte directives')


# -------------------------------------------------------------------
# PASS 1BYTE: Convert all single-byte instructions to .byte directives

# Low-hanging fruit first: Compile the opcodes without operands

sc_1byte = []

for num, pay, sta in sc_anons:

    w = pay.split()

    try:
        oc = mnemonics[w[0]]
    except KeyError:
        sc_1byte.append((num, pay, sta))
    else:

        if opcode_table[oc][2] == 1:    # look up length of instruction
            bl = INDENT+'.byte '+hexstr(2, oc)
            sc_1byte.append((num, bl, CODE_DONE))
        else:
            sc_1byte.append((num, pay, sta))

n_passes += 1
verbose('PASS 1BYTE: Assembled single byte instructions')
dump(sc_1byte, "nps")


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

for num, pay, sta in sc_1byte:

    # Skip stuff that is already done
    if sta == CODE_DONE or sta == DATA_DONE:
        sc_branches.append((num, pay, sta))
        continue

    w = pay.split()

    if w[0] in BRANCHES[MPU]:
        new_pay = '.byte '+hexstr(2, mnemonics[w[0]])+' '
        _, branch_addr = convert_number(w[-1])
        _, target_addr = convert_number(w[-2])
        opr = hexstr(2, lsb(target_addr - branch_addr - 2))
        sc_branches.append((num, INDENT+new_pay+opr, CODE_DONE))
        continue

    if MPU == '65816' and w[0] in BRANCHES[MPU]: 
        new_pay = '.byte '+hexstr(2, mnemonics[w[0]])+' '
        _, branch_addr = convert_number(w[-1])
        _, target_addr = convert_number(w[-2])
        bl, bm = little_endian_16(target_addr - branch_addr - 3)
        opr = INDENT+new_pay+hexstr(2, bl)+' '+hexstr(2, bm)
        sc_branches.append((num, opr, CODE_DONE))
        continue

    # Everything else
    sc_branches.append((num, pay, sta))

n_passes += 1
verbose('PASS BRANCHES: Encoded all branch instructions')
dump(sc_branches, "nps")

# -------------------------------------------------------------------
# PASS FUSEMOVE: Reassemble and convert move instructions

# All move instructions should have been split up and their operands converted.
# We now put them back together, remembering that destination comes before
# source in the machine code of MVN and MVP

sc_move = []

if MPU == '65816':

    # We need to be able to skip ahead in the list so we have to use an iter
    # object in this case
    l = iter(sc_branches)

    for num, pay, _ in l:

        w = pay.split()

        if w[0] == 'mvp' or w[0] == 'mvn':

            # Handle opcode
            tmp_pay = INDENT + '.byte ' + str(mnemonics[w[0]]) + ' '

            # Handle source byte
            _, r = convert_number(w[1])
            m_src = hexstr(2,r)

            # Handle destination byte
            _, pay2, _ = next(l)
            _, r = convert_number(pay2.split()[1])
            m_des = hexstr(2,r)

            # Put it all together
            tmp_pay = tmp_pay + m_des + ' ' + m_src
            sc_move.append((num, tmp_pay, CODE_DONE))

        else:

            sc_move.append((num, pay, sta))

    n_passes += 1
    verbose('PASS FUSEMOVE: Handled mvn/mvp instructions on the 65816')
    dump(sc_move, "nps")

else:
    sc_move = sc_branches


# -------------------------------------------------------------------
# PASS ALLIN: Assemble all remaining operands

# This should remove all CONTROL entries as well

sc_allin = []

# On the 65816, remember to start in emulated, 8-bit mode at the beginning
mpu_status = 'emulated'
a_len_offset = 0
xy_len_offset = 0

for num, pay, sta in sc_move:

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
        sc_allin.append((num, pay, sta))
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
        sc_allin.append((num, pay, CODE_DONE))

n_passes += 1
verbose('PASS ALLIN: Assembled all remaining operands')
dump(sc_allin, "nps")


# -------------------------------------------------------------------
# PASS VALIDATE: Make sure we only have .byte instructions

# We shouldn't have anything left now that isn't a byte directive
# This pass does not change the source file

for num, pay, _ in sc_allin:

    w = pay.split()

    if w[0] != '.byte':
        fatal(num, 'Found illegal opcode/directive "{0}"'.format(pay.strip()))

n_passes += 1
verbose('PASS VALIDATE: Confirmed that all lines are now byte data')


# -------------------------------------------------------------------
# PASS BYTECHECK: Make sure all values are valid bytes

for num, pay, _ in sc_allin:

    bl = pay.split()[1:]

    for b in bl:

        f_num, r = convert_number(b)

        if not f_num:
            fatal(num, 'Found non-number "{0}" in byte list'.format(b))

        if r > 0xff or r < 0:
            fatal(num, 'Value "{0}" does not fit into one byte'.format(b))

n_passes +=1
verbose('PASS BYTECHECK: Confirmed all byte values are in range from 0 to 256')


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

for num, pay, sta in sc_allin:

    b = len(pay.split())-1
    adr = format_adr_mpu[MPU](LC0+LCi)
    sc_adr.append((num, pay, sta, adr))
    LCi += b

n_passes += 1
verbose('PASS ADR: Added MPU address locations to each byte line')
dump(sc_adr, "npsa")


# -------------------------------------------------------------------
# PASS OPTIMIZE: Analyze and optimize code

# We don't perform automatic optimizations at the moment, but only provide
# suggestions and warnings here. We need the line numbers so we can offer
# the user suggestions based on his original source code

for num, pay, _, _ in sc_adr:

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

for _, pay, _, _ in sc_adr:
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
        f.write('       Line Address  Bytes        Instruction\n')


        # We start with line 1 because that is the way editors count lines
        c = 1
        sc_tmp = sc_axy     # This is where we take the instructions from

        for num, pay, _, adr in sc_adr:

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
                    num_i, pay_i, sta_i = sc_tmp[i]
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
            l = '{0:5d} {1:5d} {2}  {3!s}  {4}\n'.\
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
