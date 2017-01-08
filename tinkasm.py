# A Tinkerer's Assembler for the 6502/65c02/65816 in Forth
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 08. Jan 2017

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
import copy
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
n_comment_lines = 0     # How many full-line comments
n_empty_lines = 0       # How many lines where only whitespace
n_external_files = 0    # How many external files were loaded
n_instructions = 0      # How many instruction lines
n_invocations = 0       # How many macros were expanded
n_passes = 0            # Number of passes during processing
n_steps = 0             # Number of steps during processing
n_warnings = 0          # How many warnings were generated


### ARGUMENTS ###

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True,\
        help='Assembler source code file (required)')
parser.add_argument('-ir', '--intermediate-representation',\
        action='store_true', dest='ir', default=False,\
        help='Save Intermediate Representation of assembly data (default TINK.IR)')
parser.add_argument('-o', '--output', dest='output',\
        help='Binary output file (default TINK.BIN)', default='tink.bin')
parser.add_argument('-v', '--verbose',\
        help='Display additional information', action='store_true')
parser.add_argument('-d', '--dump',\
        help='Print intermediate steps as (long) lists', action='store_true')
parser.add_argument('-l', '--listing', action='store_true',\
        help='Create listing file (default TINK.LST)')
parser.add_argument('-x', '--hexdump', action='store_true',\
        help='Create ASCII hexdump listing file (default TINK.HEX)')
parser.add_argument('-s28', action='store_true',\
        help='Create S28 format file from binary (default TINK.S28)')
parser.add_argument('-p', '--partial', action='store_true',\
        help='Save partial listing file on fatal error (default TINK.PRT)')
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

def fatal(line, s):
    """Abort program because of fatal error during assembly.
    """
    if line.sec_ln == 0: 
        print('FATAL ERROR line {0} - {1}'.format(line.ln, s))
    else: 
        print('FATAL ERROR line {0}:{1} - {2}'.format(line.ln, line.sec_ln, s))
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
Version BETA 08. January 2017
Copyright 2015-2017 Scot W. Stevenson <scot.stevenson@gmail.com>
This program comes with ABSOLUTELY NO WARRANTY
"""

COMMENT_MARKER = ';' # Comment marker, default is ";"
CURRENT = '.*'       # Current location counter, default is ".*"
ASSIGNMENT = '.equ'  # Assignment directive, default is ".equ"
LOCAL_LABEL = '@'    # Marker for anonymous labels, default is "@"
SEPARATORS = '[.:]'  # Legal separators in number strings for regex

HEX_PREFIX = '$'     # Prefix for hexadecimal numbers, default is "$"
BIN_PREFIX = '%'     # Prefix for binary numbers, default is "%"
DEC_PREFIX = '&'     # Prefix for decimal numbers, default "&"

LEFTMATH = '{'       # Opening bracket for Python math terms
RIGHTMATH = '}'      # Closing bracket for Python math terms

INDENT = ' '*8       # Indent in whitespace for formatting

LC0 = 0              # Start address of code ("location counter")
LCi = 0              # Index to where we are in code from the LC0

HEX_FILE = 'tink.hex'     # Default name of hexdump file
LIST_FILE = 'tink.lst'    # Default name of listing file
IR_FILE = 'tink.ir'       # Default name of IR file 
S28_FILE = 'tink.s28'     # Default name of S28 file
PARTIAL_FILE = 'tink.prt' # Default name of partial listing

# The user can request a correctly formatted source file as a goody while
# running the program. We call a separate program for this, which has the
# following command line 
# TODO make this work 
formatter = './tinkfmt/tinkfmt.py'

xy_width = 8    # For 65816, assumed width of XY registers at this point
a_width = 8     # For 65816, assumed width of A register at this point

SUPPORTED_MPUS = ['6502', '65c02', '65816']
DATA_DIRECTIVES = ['.byte', '.word', '.long']

symbol_table = {}
anon_labels = []

# Line types. Start off with UNKNOWN, then are later replaced by real type as
# discovered or added. CONTROL is added internally by the assembler for various
# control structures
UNKNOWN = '   '         # Pre-processing default
COMMENT = 'cmt'         # Whole-line comments, not inline 
DIRECTIVE = 'dir'     
INSTRUCTION = 'ins'
LABEL = 'lbl'
CONTROL = 'ctl'         # Used for lines added by the assembler
WHITESPACE = 'wsp'      # Used for whole-line whitespace

# Line status. Starts with UNTOUCHED, then MODIFIED if changes are made, and
# then DONE if line does not need any more work. 
UNTOUCHED = '    ' 
MODIFIED = 'work'
DONE = 'DONE'

# CLASSES

class CodeLine:
    def __init__(self, rawstring, ln, sec_ln=0):
        self.raw = rawstring    # Original line as a string
        self.ln = ln            # Primary line number (in source file)
        self.sec_ln = sec_ln    # Secondary line number for expanded lines
        self.status = UNTOUCHED # Flag if line has been processed
        self.type = UNKNOWN     # Type of line, starts UNKNOWN, ends DATA
        self.il_comment = ''    # Storage area for any inline comments
        self.action = ''        # First word of instruction or directive
        self.parameters = ''    # Parameter(s) of instruction or directive
        self.xy_width = 8       # For 65816 REP and SEP instructions
        self.a_width = 8        # For 65816 REP and SEP instructions
        self.address = 0        # Address where line data begins (16/24 bit)
        self.bytes = []         # List of bytes after assembly


# List of all directives. Note the anonymous label character is not included
# because this is used to keep the user from using these words as labels

DIRECTIVES = ['.!a8', '.!a16', '.a8', '.a16', '.origin', '.axy8', '.axy16',\
        '.end', ASSIGNMENT, '.byte', '.word', '.long', '.advance', '.skip',\
        '.native', '.emulated', '.mpu', '.save',\
        '.!xy8', '.!xy16', '.xy8', '.xy16', COMMENT_MARKER,\
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
        BASE = 16 # Default numbers are hex, not decimal
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


# TODO 
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

    # We store all symbols in lower case, humans be damned. If the following
    # step is omitted, upper- and mixed-case symbols will not be converted
    # correctly when inside .BYTE directives
    lcs = s.lower()
    
    try:
        r = symbol_table[lcs]
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

#####################################################################
### PASSES AND STEPS ###

# A STEP is executed once, a PASS can be excuted more than once, but usually
# only once per line
 
# -------------------------------------------------------------------
# STEP BANNER: Set up timing, print banner

# This step is not counted
 
verbose(TITLE_STRING)
time_start = timeit.default_timer()
verbose('Beginning assembly. Timer started.')
 
# -------------------------------------------------------------------
# STEP LOAD: Load original source code and add line numbers
#
# REQUIREMENTS: none

# Line numbers start with 1 because this is for humans. 

raw_source = []

with open(args.source, "r") as f:
    for ln, ls in enumerate(f.readlines(), 1): 
        line = CodeLine(ls.rstrip(), ln, 0)    # right strip gets rid of LF
        raw_source.append(line)

n_steps += 1
verbose('STEP LOAD: Read {0} lines from {1}'.\
        format(len(raw_source), args.source))
# dump(raw_source) 


# -------------------------------------------------------------------
# PASS INCLUDE: Add content from external files specified by the INCLUDE
# directive. 
#
# REQUIRED as first step of processing

# The .include directive must be alone in the line and the second string must
# be the name of the file without any spaces or quotation marks. Note that this
# means there will be no .include directives visible in the code listings, since
# everything will be one big file

expanded_source = []

for line in raw_source: 

    # We haven't converted everything to lower case yet so we have to do it the
    # hard way here. It is not legal to have a label in the same line as a
    # .include directive. Any inline comment after .include is silently
    # discarded
    w = line.raw.split()

    if len(w) > 1 and w[0].lower() == '.include':

        # Keep the line number of the .include directive for later reference
        # But add secondary line numbers for reference
        with open(w[1], 'r') as f:
            for sln, ls in enumerate(f.readlines(), 1): 
                nl = CodeLine(ls.rstrip(), line.ln, sln)
                expanded_source.append(nl)

        n_external_files += 1
        verbose('- Included code from file "{0}"'.format(w[1]))

    else:
        expanded_source.append(line)

n_passes += 1
verbose('PASS INCLUDE: Added {0} external file(s)'.format(n_external_files))
# dump(expanded_source) 


# -------------------------------------------------------------------
# PASS EMPTY: Process empty lines 
#
# REQUIRES inclusion of all lines from all includes
# REQUIRED for search for MPU type

# We want to cut down the number of lines we have to process as early as
# possible, so we handle empty lines right now 

for line in expanded_source: 

    if not line.raw.strip():
        line.type = WHITESPACE
        line.status = DONE
        n_empty_lines += 1

n_passes += 1
verbose('PASS EMPTY: Found {0} empty line(s)'.format(n_empty_lines))
# dump(expanded_source)


# -------------------------------------------------------------------
# PASS COMMENTS: Remove comments that span whole lines
#
# REQUIRES inclusion of all lines from all includes

for line in expanded_source: 

    if line.status == DONE:
        continue

    # Whole-line comment marked by ';'
    if line.raw.strip()[0] == COMMENT_MARKER:
        line.type = COMMENT
        line.status = DONE
        n_comment_lines +=1

n_passes += 1
verbose('PASS COMMENTS: Found {0} full-line comments'.format(n_comment_lines))
# dump(expanded_source)


# -------------------------------------------------------------------
# PASS MPU: Find MPU type
#
# REQUIRES inclusion of all lines from all includes
# REQUIRES that empty lines have been identified
# ASSUMES that no directives have been processed yet
# REQUIRED for loading mnemonics list 

for line in expanded_source: 

    if line.status == DONE:
        continue

    # We haven't converted to lower case yet so we have to do this by hand 
    # It is not legal to have a label in the same line as the .mpu
    # directive. Any inline comment after .mpu is silently discarded
    s = line.raw.lstrip()
    w = s.split()
    w1 = w[0]       # get first word in line 

    if w1.lower() != '.mpu': 
        continue

    try: 
        MPU = w[1]      # get second word in line
    except IndexError:
        fatal(line, 'No MPU given with ".mpu" directive')
    else:
        line.type = DIRECTIVE
        line.status = DONE 
        line.action = '.mpu'
        line.parameters = MPU
        break

if MPU not in SUPPORTED_MPUS:
    fatal(line, 'MPU "{0}" not supported'.format(MPU))

if not MPU:
    fatal(line, 'No ".mpu" directive found')

n_passes += 1
verbose('PASS MPU: Found MPU "{0}", is supported'.format(MPU))
# dump(expanded_source)


# -------------------------------------------------------------------
# STEP OPCODES: Load opcodes depending on MPU type
#
# REQUIRES MPU type is known
# REQUIRED to generate mnemonic list

# We use 65816 as the default. This step does not change the source code.
# Rewrite this for more than three MPU types.

if MPU == '6502':
    from opcodes6502 import opcode_table
elif MPU.lower() == '65c02':
    from opcodes65c02 import opcode_table
else:
    from opcodes65816 import opcode_table

# Paranoid: Make sure we were given the right number of opcodes
# Fatal error returns first line of code 
if len(opcode_table) != 256:
    fatal(expanded_source[0], 'Opcode table contains {0} entries, not 256'.\
        format(len(opcode_table)))

n_steps += 1
verbose('STEP OPCODES: Loaded opcode table for MPU {0}'.format(MPU))


# -------------------------------------------------------------------
# STEP MNEMONICS: Generate mnemonic list from opcode table
#
# REQUIRES opcodes loaded depending on CPU type

# This step does not change the source code

mnemonics = {opcode_table[n][1]:n for n, e in enumerate(opcode_table)}

# For the 6502 and 65c02, we have 'UNUSED' for the entries in the opcode table
# that are, well, not used. We get rid of them here. The 65816 does not have 
# any unused opcodes.
if MPU != '65816':
    del mnemonics['UNUSED']

n_steps += 1
verbose('STEP MNEMONICS: Generated mnemonics list')
verbose('- Number of mnemonics found: {0}'.format(len(mnemonics.keys())))
if args.dump:
    print('Mnemonics found: {0}'.format(mnemonics.keys()))
    print()


# -------------------------------------------------------------------
# PASS SPLIT LABEL: Move labels to their own line
#
# REQUIRES inclusion of all lines from all includes
# REQUIRES list of legal mnemonics available
# ASSUMES all empty lines have been taken care of 

# Though Typist's Assembler Notation requires labels to be in a separate line,
# we should be able to assemble code that hasn't been correctly formatted.
# Since we have gotten rid of the full-line comments, anything that is in the
# first column and is not whitespace is then considered a label. We don't
# distinguish between global and anonymous labels at this point

relabeled_source = []

for line in expanded_source: 

    if line.status == DONE:
        relabeled_source.append(line) 
        continue

    # In theory, labels should be the only thing that is in the first column,
    # but again, we want the assembly process be as robust as possible. We
    # therefore strip away left whitespace and try to figure out if we have an
    # instruction or a directive. If not, it's a label because we don't allow
    # anything else. While we're at it, we save information about the other
    # lines that we get as a side effect

    # w has to have at least one word because we've gotten rid of all empty
    # lines
    w = line.raw.split()
    w1 = w[0]

    # Directives start with a dot. We just remember that we've found one, but
    # don't process it yet
    if w1[0] == '.':
        line.type = DIRECTIVE
        relabeled_source.append(line) 
        continue 
        
    # We know all our mnemonics. We just remember that we've found one, but
    # don't process it yet. Silly user might have given us uppercase mnemonics,
    # but we accept this gracefully for the moment and stick itto him later
    if w1.lower() in mnemonics:
        line.type = INSTRUCTION
        relabeled_source.append(line) 
        continue 

    # We know now that we have a label. We put the label in the action field of
    # the line for later processing
    line.type = LABEL
    line.status = MODIFIED
    line.action = w1.strip() 

    # If there was only one word in the line, it has to be the label and
    # we can go on to the next line as quickly as possible
    if len(w) == 1:
        relabeled_source.append(line) 
        continue 

    # Nope, there is more on the line. We create a new line and come back and
    # figure it out what it was. We delete the label from the string. Note this
    # can lead to weird effects if the label string appears again in the rest of
    # the line - say, an inline comment - but we'll live with that risk for now
    rest_of_line = line.raw.replace(w1, '').strip()

    # We check again if this is an instruction or a directive. The duplication
    # of code is annoying, but makes processing faster because we bug out of
    # simple directive lines earlier
    rw = rest_of_line.split()
    rw1 = rw[0]

    # The simple case is that we have a comment after the label, and can just
    # put it in the inline comment field without adding another line
    if rw1[0] == ';':
        line.il_comment = rest_of_line
        relabeled_source.append(line) 
        continue

    # Whatever happens now, the label itself is safe
    relabeled_source.append(line) 

    if rw1[0] == '.':
        newline = CodeLine(rest_of_line, line.ln, 1)
        newline.type = DIRECTIVE
        relabeled_source.append(newline) 
        continue

    if rw1.lower() in mnemonics:
        newline = CodeLine(rest_of_line, line.ln, 1)
        newline.type = INSTRUCTION
        relabeled_source.append(newline) 
        continue

    # If we reach this point, we have something weird on the new line and give
    # up with a fatal error
    fatal(line, 'Unidentified characters "{0}" after label'.\
            format(rest_of_line))

n_passes += 1
verbose('PASS SPLIT LABELS: Split lines that have code following their labels')
# dump(relabeled_source)


# -------------------------------------------------------------------
# CLAIM: All labels should now be in a line of their own. Also, all directives
# and instruction lines should be identified 

verbose('CLAMING all labels should be in a line of their own')


# -------------------------------------------------------------------
# PASS VALIDATE TYPE: Confirm the type of every single line is known
#
# REQUIRES labels to be in own lines
# REQUIRES all types to have been identified

# This step does not change the source

for line in relabeled_source:

    if line.type == UNKNOWN:
        fatal(line, 'Line of unknown type remaining after processing')

n_passes += 1
verbose('PASS VALIDATE TYPE: All lines are of known type')

# -------------------------------------------------------------------
# PASS INLINE COMMENTS: Isolate inline comments
#
# REQUIRES all types to have been identified
# REQUIRES all types to be in a line of their own 

# Keep this definition with its pass
def remove_inlines(s):
    """Given a string, remove any inline comment, defined by the comment char.
    We only strip the right side because we need the whitespace on the left
    later.  
    """
    non_comment = s.split(COMMENT_MARKER)[0].rstrip()
    comment = s.replace(non_comment, '')
    return non_comment, comment


for line in relabeled_source:

    if line.status == DONE:
        continue

    # For the moment, we put "non_comment" (the actual directive or instructions
    # with any operands etc) in the parameters field
    if line.type == DIRECTIVE or line.type == INSTRUCTION:
        line.parameters, line.il_comment = remove_inlines(line.raw)
    
n_passes += 1
verbose('PASS INLINE COMMENTS: Isolated all inline comments')
# dump(relabeled_source)


# -------------------------------------------------------------------
# PASS SPLIT OPERATIONS: For directives and instructions, split into
# directive/parameter or opcode/operand pairs. Convert directives and opcodes to
# lower case. After this pass, we don't access the raw line string anymore
#
# REQUIRES all types to be in a line of their own
# REQUIRES all lines to have been identified by type
# REQUIRES all inline comments to have been removed
# ASSUMES that the directives and instructions are in the parameter field

for line in relabeled_source:

    if line.status == DONE:
        continue

    if line.type == DIRECTIVE or line.type == INSTRUCTION:
        w = line.parameters.split() 
        w1 = w[0]
        line.action = w[0].lower()
        line_rest = line.parameters.replace(w1, '').strip()
        line.parameters = line_rest

n_passes += 1
verbose('PASS SPLIT OPERATIONS: Isolated active word/parameters')


# -------------------------------------------------------------------
# PASS MODES: Handle '.native' and '.emulated' directives on the 65816
#
# REQUIRES all directives to be in action field of their line

# TODO refactor this mess once we're sure it works

modes_source = []

if MPU == '65816':

    for line in relabeled_source:

        if line.status == DONE or line.type != DIRECTIVE:
            modes_source.append(line)
            continue

        if line.action == '.native':

            clc_line = CodeLine(INDENT+line.action, line.ln, 1)
            clc_line.action = 'clc'
            clc_line.type = INSTRUCTION
            clc_line.status = MODIFIED
            modes_source.append(clc_line)

            xce_line = CodeLine(INDENT+line.action, line.ln, 2)
            xce_line.action = 'xce'
            xce_line.type = INSTRUCTION
            xce_line.status = MODIFIED
            modes_source.append(xce_line)

            bang_line = CodeLine(INDENT+line.action, line.ln, 3)
            bang_line.action = '.!native'
            bang_line.type = CONTROL
            bang_line.status = MODIFIED
            modes_source.append(bang_line)

            continue

        if line.action == '.emulated':

            sec_line = CodeLine(INDENT+line.action, line.ln, 1)
            sec_line.action = 'sec'
            sec_line.type = INSTRUCTION
            sec_line.status = MODIFIED
            modes_source.append(sec_line)

            xce_line = CodeLine(INDENT+line.action, line.ln, 2)
            xce_line.action = 'xce'
            xce_line.type = INSTRUCTION
            xce_line.status = MODIFIED
            modes_source.append(xce_line)

            bang_line = CodeLine(INDENT+line.action, line.ln, 3)
            bang_line.action = '.!emulated'
            bang_line.type = CONTROL
            bang_line.status = MODIFIED
            modes_source.append(bang_line)

            # Emulation drops us into 8-bit modes for A, X, and Y
            # automatically, no REP or SEP commands needed
            bang_line = CodeLine(INDENT+line.action, line.ln, 4)
            bang_line.action = '.!a8'
            bang_line.type = CONTROL
            bang_line.status = MODIFIED
            modes_source.append(bang_line)

            bang_line = CodeLine(INDENT+line.action, line.ln, 5)
            bang_line.action = '.!xy8'
            bang_line.type = CONTROL
            bang_line.status = MODIFIED
            modes_source.append(bang_line)

            continue

        # If we get here, just save the line, like, whatever
        modes_source.append(line)

    n_passes += 1
    verbose('PASS MODES: Handled 65816 native/emulated mode switches')
#   dump(modes_source)

else:
    modes_source = relabeled_source

# -------------------------------------------------------------------
# PASS AXY: Handle register size switches on the 65816

# We add the actual REP/SEP instructions as well as internal directives for the
# following steps.

axy_source = []

# We don't need to define these if we're not using a 65816
if MPU == '65816':

    AXY_INS = {'.a8': (('sep', '20', INSTRUCTION),\
                      ('.!a8', '', CONTROL)),\
               '.a16': (('rep', '20', INSTRUCTION),\
                       ('.!a16', '', CONTROL)),\
               '.xy8': (('sep', '10', INSTRUCTION),\
                       ('.!xy8', '', CONTROL)),\
               '.xy16': (('rep', '10', INSTRUCTION),\
                        ('.!xy16', '', CONTROL)),\
               '.axy8': (('sep', '30', INSTRUCTION),\
                        ('.!a8', '', CONTROL),\
                        ('.!xy8', '', CONTROL)),\
               '.axy16': (('rep', '30', INSTRUCTION),\
                         ('.!a16', '', CONTROL),\
                         ('.!xy16', '', CONTROL))}

    for line in modes_source: 

        have_found = False

        # Walk through every control directive for every line
        for ins in AXY_INS:

            # Because we moved labels to their own lines, we can assume that
            # register switches are alone in the line
            if ins in line.action:

                for e in AXY_INS[ins]:
                    nl = CodeLine(INDENT+line.action, line.ln, 1)
                    nl.action = e[0]
                    nl.parameters = e[1]
                    nl.type = e[2]
                    nl.status = MODIFIED

                    axy_source.append(nl)
                    have_found = True

        if not have_found:
            axy_source.append(line)

    n_passes += 1
    verbose('PASS AXY: Registered 8/16 bit switches for A, X, and Y')
#   dump(axy_source)

else:
    axy_source = modes_source 

# -------------------------------------------------------------------
# PASS SPLIT MOVES - Split up Move instructions on the 65816

# The MVP and MVN instructions are really, really annoying because they have two
# operands where every other instruction has one. We deal with this by splitting
# the instructions into two lines, dealing with the operands, and then later
# putting them back together again. We assume that the operands are separated by
# a comma ('mvp 00,01')

move_source = []

if MPU == '65816':

    for line in axy_source: 

        if line.action != 'mvp' and line.action != 'mvn': 
            move_source.append(line)
            continue 

        # Catch malformed move instructions
        try:
            l_bank, r_bank = line.parameters.split(',')
        except ValueError:
            fatal(num, 'Malformed "{0}" instruction ("{1}")'.\
                    format(line.action, line.parameters))

        line.parameters = l_bank
        line.status = MODIFIED
        move_source.append(line)

        nl = CodeLine(INDENT+INDENT+'(dummy)', line.ln, 1)
        nl.parameters = r_bank
        nl.status = MODIFIED
        nl.type = CONTROL
        move_source.append(nl)

    n_passes += 1
    verbose('PASS SPLIT MOVES: Split mvn/mvp instructions on the 65816')
#     dump(sc_splitmove, "nps")

else:
    move_source = axy_source


# -------------------------------------------------------------------
# PASS MACROS: Define macros
#
# REQUIRES all labels to be in their own lines

macros = {}
macro_name = ''
are_defining = False

for line in move_source: 

    if not are_defining:

        # This line might not have anything to do with macros
        if line.action != '.macro':
            continue 
        # If this is the start of a macro, create a line in the macro dictionary
        else:
            macro_name = line.parameters.strip() 
            macros[macro_name] = []
            are_defining = True
            verbose('- Found macro "{0}" in line {1}'.format(macro_name, line.ln))
            line.status = DONE
    else:

        # Currently, we don't allow nesting
        if line.action == '.macro':
            fatal(line, 'Illegal Attempt to nest macro "{0}"'\
                    .format(line.parameters))

        # Remember this line so we can invoke it later
        if line.action != ".endmacro":

            # We need to create a copy of the line so it isn't just a reference
            # For now, we use the line numbers of the macro definition. Later,
            # the invokation will overwrite them
            ml = copy.deepcopy(line) 
            ml.status = MODIFIED
            ml.sec_ln = 1
            macros[macro_name].append(ml)

            line.status = DONE
            
        # We're done, so enough of this 
        else:
            are_defining = False
            line.status = DONE
            continue

n_passes += 1
verbose('STEP MACROS: Defined {0} macros'.format(len(macros)))
# dump(sc_macros, "nps")

# TODO pretty format this
# TODO only print if dump requested
for m in macros.keys():
    print('Macro {0}:'.format(m))

    for ml in macros[m]:
        print('- {0:04}:{1:03} {2} {3:11} | {4:11}|{5:11}|{6:11} ||'\
                .format(ml.ln, ml.sec_ln, ml.status, ml.type, ml.action,\
                ml.parameters, ml.il_comment), ml.raw)


# -------------------------------------------------------------------
# PASS INVOKE: Insert macro definitions
# 
# REQUIRES macros to have been defined

# TODO add parameters, which might force us to move this to a later point

macro_source = []
pre_invok_len = len(move_source)

for line in move_source:

    if line.action != '.invoke':
        macro_source.append(line)
        continue

    # Name of macro to invoke must be second word in line
    try:
        m = macros[line.parameters.strip()]
    except KeyError:
        fatal(line, 'Attempt to invoke non-existing macro "{0}"'.format(line.action))

    for ml in m:
        macro_source.append(ml)
        ml.status = MODIFIED
        ml.ln = line.ln
        ml.sec_ln = 1   
        ml.raw = '; Invoked from macro "{0}" in line {1}'.\
                format(line.action, line.ln)

    n_invocations += 1
    verbose('- Expanding macro "{0}" into line {1}'.\
            format(line.parameters, line.ln))

post_invok_len = len(macro_source)
n_passes += 1

# We give the "net" number of lines added because we also remove the invocation
# line itself
verbose('PASS INVOKE: {0} macro expansions, net {1} line(s) added'.\
        format(n_invocations, post_invok_len - pre_invok_len))
# dump(sc_invoke, "nps")


# -------------------------------------------------------------------
# PASS RENUMBER SECONDARY LINE NUMBERS
# 
# REQUIRES all includes to be finished
# REQUIRES all macros to be expanded 

# Different combinations of macros and includes can lead to strange secondary
# line numbers. Instead of trying to figure them out in the previous steps, we
# renumber them here before
# TODO count of secondary lines currently starts with zero, change so it starts
# with one as well

prev_ln = 0
sec_ln_count = 0 

for line in macro_source:
    
    if line.ln == prev_ln: 
        sec_ln_count += 1 
        line.sec_ln = sec_ln_count
    else: 
        line.sec_ln = 0 
        sec_ln_count = 0    # TODO unelegant, rewrite

    prev_ln = line.ln

n_passes += 1
verbose('PASS RENAME SECONDARY LINES: Secondary lines now numbered in sequence.')
# dump(macro_source)

ir_source = macro_source
   
# -------------------------------------------------------------------
# ASSERT INTERMEDIATE REPRESENTATION
#
# REQUIRES all lines to have been read, expanded and correctly numbered

# The Intermediate Representation (IR) ends the phase of preprocessing (parsing
# etc) and is the basis for the actually assembly. The source code has now
# reached its maximal size.

n_steps += 1
verbose('ASSERT: Intermediate Representation (IR) created with {0} lines of code'.\
        format(len(ir_source)))


# -------------------------------------------------------------------
# PASS: SAVE IR FILE 
#
# REQUIRES Intermediate Representation to have been generated

if args.ir: 

    # Keep these with the IR pass
    # TODO rewrite this once we're happy with it
    
    def tmpl_ir_cmt(ir_line):
        """Template for commentaries for the Intermediate Representation.
        Takes a line object and returns a string for writing to the file.
        """
        s = '{0:5}:{1:3} | {2} | {3} | {4}\n'.format(ir_line.ln,\
                ir_line.sec_ln, ir_line.status, ir_line.type,\
                ir_line.raw)
        return s

    def tmpl_ir_ws(ir_line):
        """Template for whitespace for the Intermediate Representation.
        Takes a line object and returns a string for writing to the file.
        """
        s = '{0:5}:{1:3} | {2} | {3} |\n'.format(ir_line.ln,\
                ir_line.sec_ln, ir_line.status, ir_line.type)
        return s

    def tmpl_ir_ins(ir_line):
        """Template for instructions for the Intermediate Representation. 
        Takes a line object and returns a string for writing to the file.
        """
        s = '{0:5}:{1:3} | {2} | {3} | {4:11} | {5:30} | {6}\n'.\
            format(ir_line.ln, ir_line.sec_ln, ir_line.status, ir_line.type,\
            ir_line.action, ir_line.parameters, ir_line.il_comment.strip())
        return s 

    def tmpl_ir_dir(ir_line):
        """Template for directives for the Intermediate Representation. 
        Takes a line object and returns a string for writing to the file.
        """
        s = '{0:5}:{1:3} | {2} | {3} | {4:11} | {5:30} | {6}\n'.\
            format(ir_line.ln, ir_line.sec_ln, ir_line.status, ir_line.type,\
            ir_line.action, ir_line.parameters, ir_line.il_comment.strip())
        return s 

    def tmpl_ir_lbl(ir_line):
        """Template for labels for the Intermediate Representation.
        Takes a line object and returns a string for writing to the file.
        """
        s = '{0:5}:{1:3} | {2} | {3} | {4:11}   {5:30} | {6}\n'.format(ir_line.ln,\
                ir_line.sec_ln, ir_line.status, ir_line.type, ir_line.action,\
                ir_line.parameters, ir_line.il_comment.strip())
        return s

    def tmpl_ir_ctl(ir_line):
        """Template for control lines for the Intermediate Representation. 
        Takes a line object and returns a string for writing to the file.
        """
        s = '{0:5}:{1:3} | {2} | {3} | {4:11} | {5:30} | {6}\n'.\
            format(ir_line.ln, ir_line.sec_ln, ir_line.status, ir_line.type,\
            ir_line.action, ir_line.parameters, ir_line.il_comment.strip())
        return s 


    with open(IR_FILE, 'w') as f:

        f.write(TITLE_STRING)
        f.write('\nIntermediate Representation (IR) file of {0}\n'.format(args.source))
        f.write('Generated on {0}\n'.format(time.asctime(time.localtime())))
        f.write('Saving {0} lines of code\n'.format(len(ir_source)))
        f.write('\n') 
        f.write('    LINE   STATUS  TYPE    ACTION             PARAMETERS                   IN-LINE COMMENT\n')
        f.write('\n')

        for line in ir_source:

            if line.type == INSTRUCTION:
                f.write(tmpl_ir_ins(line))
            elif line.type == COMMENT:
                f.write(tmpl_ir_cmt(line))
            elif line.type == WHITESPACE:
                f.write(tmpl_ir_ws(line))
            elif line.type == CONTROL:
                f.write(tmpl_ir_ctl(line))
            elif line.type == DIRECTIVE:
                f.write(tmpl_ir_dir(line))
            elif line.type == LABEL:
                f.write(tmpl_ir_lbl(line))
            else:
                fatal(line, 'ERROR: Unknown line type "{0}" in line {1}:{2}'.\
                        format(line.type, line.ln, line.sec_ln))


# -------------------------------------------------------------------
# STEP ORIGIN: Find .ORIGIN directive

# Standard requires origin to be the highest line. Since we've alread taken care
# of the .MPU, this should be the first non-completed line. 

for line in ir_source:

    if line.status == DONE:
        continue

    # .ORIGIN should be first line, or else we're in trouble. Note that in
    # theory, it could be uppercase, so we go the extra mile and convert it
    s = line.action.strip().lower() 
    if s != '.origin':
        fatal(line, '".origin" directive missing or too late, found "{0}" instead'.\
                format(line.action))

    f_num, LC0 = convert_number(line.parameters)

    # ORIGIN may not take a symbol, because we haven't defined any yet, and
    # we don't accept math or modifiers either
    if not f_num:
        fatal(n, '".origin" directive gives "{0}", not number as required')

    line.status = DONE
    break
        

n_steps += 1
verbose('STEP ORIGIN: Found ."origin" directive, starting code at {0:06x}'.\
        format(LC0))
# dump(sc_origin, "nps")


# # -------------------------------------------------------------------
# # STEP END: Find .END directive
# 
# # End directive must be in the last line
# 
# endline = sc_origin[-1][1].strip().split()
# 
# if endline[0] != ".end":
#     n = sc_origin[0][0]   # Fatal always needs a number line, fake it
#     fatal(n, 'No END directive found, must be in last line')
# 
# sc_end = sc_origin[:-1]
# 
# n_steps += 1
# verbose('STEP END: Found END directive in last line')
# dump(sc_end, "nps")

# -------------------------------------------------------------------
# PRIMITIVE PRINTOUT FOR TESTING
# Replace by formated templates later
for e in macro_source:
    print('{0:04}:{1:03} {2} {3:11} | {4:11}|{5:11}|{6:11} ||'\
            .format(e.ln, e.sec_ln, e.status, e.type, e.action, e.parameters,\
            e.il_comment), e.raw)

# TODO HIER HIER TODO




# # -------------------------------------------------------------------
# # PASS SIMPLE ASSIGN: Handle first round of basic assigments
# 
# # Handle the simplest form of assignments, those were a number is assigned to
# # a variable ('.equ jack 1') or a symbol we already know ('.equ jill jack')
# # without modifiers or math. We can't do full assignments until we've dealt with
# # labels, but we can do this now to cut down on the number of lines we have to
# # go through every time. 
# 
# sc_simpleassign = []
# 
# for num, pay, sta in sc_end:
# 
#     w = pay.split()
#  
#     if w[0] != ASSIGNMENT:
#         sc_simpleassign.append((num, pay, sta))
#         continue
# 
#     # We want the length to be exactly three words so we don't get involved
#     # modifiers or math terms
#     if len(w) != 3:
#         sc_simpleassign.append((num, pay, sta))
#         continue
# 
#     vet_newsymbol(w[1])
# 
#     # In '.equ frog abc', 'abc' can either be a symbol or a number. We want it
#     # to be a symbol by default, so we check the symbol table first
#     try:
#         r = symbol_table[w[2]]
#         symbol_table[w[1]] = r
#         continue
#     except KeyError:
#         pass
# 
#     f_num, r = convert_number(w[2])
# 
#     # If it's a number, add it to the symbol table, otherwise we'll have to wait
#     # until we've figured out more stuff
#     if f_num:
#         symbol_table[w[1]] = r
#     else:
#         sc_simpleassign.append((num, pay, sta))
# 
# n_passes += 1
# verbose('PASS SIMPLE ASSIGN: Assigned {0} new symbol(s) to symbol table'.\
#         format(len(sc_end)-len(sc_simpleassign)))
# dump(sc_simpleassign, "nps")
# 
# # Print symbol table
# if args.verbose:
#     dump_symbol_table(symbol_table, "after SIMPLEASSIGN (numbers in hex)")
# 
# 
# # -------------------------------------------------------------------
# # PASS REPLACE (1): Handle known assignments
# sc_replaced01 = replace_symbols(sc_simpleassign)


 
# 
# # -------------------------------------------------------------------
# # PASS STRINGS: Convert strings to bytes and byte lists
# 
# # Since strings are constants, we can convert them very early on
# 
# # Since we have gotten rid of comments, every quotation mark must belong to
# # a string. We convert these strings to comma-separated byte lists 
# # Example: "aaa" -> 61, 61, 61
# 
# # This method could also work for single-character strings in instructions such
# # as 'lda.# "a"'. However, this could be source of errors because the assembler
# # will happily also try to turn multi-character strings into byte lists in this
# # instance as well ('lda.# "ab"' would become 'lda.# 61, 62'). Use 
# # single-quotation marks for this, see next step.
# 
# sc_strings = []
# p = re.compile('\".*?\"')
# 
# for num, pay, sta in sc_invoke:
# 
#         # Most lines won't have a string, so we skip them first
#         if '"' not in pay:
#             sc_strings.append((num, pay, sta))
#             continue 
# 
#         # The save directive may not have a string as a parameter
#         w = pay.split()
#         
#         if w[0] == '.save':
#             fatal(num, 'Illegal string in save directive, should be number.')
# 
#         ma = p.findall(pay)
#         new_pay = pay
# 
#         # Replace the contents of the strings with a comma-separated list of 
#         # bytes
#         for m in ma:
# 
#             # It is an error to use double quotation marks for a single
#             # character, use 'a' instead, see next step
#             if len(m) == 3:
#                 fatal(num,\
#                         "Found single-character string {0}, use 'x' for chars".\
#                         format(m))
# 
#             new_pay = new_pay.replace(m, string2bytestring(m))
#         
#         sc_strings.append((num, new_pay, sta))
# 
# verbose('PASS STRINGS: Converted all strings to byte lists')
# dump(sc_strings, "nps")
# 
# 
# # -------------------------------------------------------------------
# # PASS CHARS: Convert single characters delimited by single quotes
# 
# # Since characters are constants, we can convert them early on
# 
# # Single characters are put in single quotes ('a'). This step must come after
# # the conversion of strings to make sure that we don't accidently find single
# # characters that are part of a string.
# 
# sc_chars = []
# p = re.compile("\'.\'")
# 
# for num, pay, sta in sc_strings:
#     
#     # We usually don't have a single quote in a line so we get rid of that
#     # immediately
#     if "'" not in pay:
#         sc_chars.append((num, pay, sta))
#         continue
# 
#     ma = p.findall(pay)
#     new_pay = pay
# 
#     # Replace each instance of a single-quoted string with the string of its
#     # hex number. Note that ord() returns unicode, but we currently slice off 
#     # anything that is not the last two hex digits
#     for m in ma:
#         new_pay = new_pay.replace(m, hexstr(2, ord(m[1])))
# 
#     sc_chars.append((num, new_pay, sta))
# 
# verbose('PASS CHARS: Converted all single characters to bytes')
# dump(sc_chars, "nps")
# 
 
# # -------------------------------------------------------------------
# # PASS LABELS - Construct symbol table by finding all labels
# 
# # This is the equivalent of the traditional "Pass 1" in normal two-pass
# # assemblers. We assume that the most common line by far will be mnemonics, and
# # that then we'll see lots of labels (at some point, we should measure this).
# 
# # Though we don't start acutal assembling here, we do remember information for
# # later passes when it is useful, like for branches and such, and get rid of
# # some directives such as ADVANCE and SKIP
# 
# sc_labels = []
# 
# BRANCHES = ['bra', 'beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
#         'bra.l', 'phe.r']
# 
# # These are only used for 65816. The offsets are used to calculate if an extra
# # byte is needed for immediate forms such as lda.# with the 65816
# a_len_offset = 0
# xy_len_offset = 0
# mpu_status = 'emulated'   # Start 65816 out in emulated status
# A_IMM = ['adc.#', 'and.#', 'bit.#', 'cmp.#', 'eor.#', 'lda.#', 'ora.#', 'sbc.#']
# XY_IMM = ['cpx.#', 'cpy.#', 'ldx.#', 'ldy.#']
# 
# for num, pay, sta in sc_splitmove:
# 
#     w = pay.split()
# 
#     # --- SUBSTEP CURRENT: Replace the CURRENT symbol by current address
# 
#     # This must come before we handle mnemonics. Don't add a continue because
#     # that will screw up the line count; we replace in-place
#     if CURRENT in pay: 
#         pay = pay.replace(CURRENT, hexstr(6, LC0+LCi))
#         w = pay.split()
#         verbose('Current marker "{0}" in line {1}, replaced with {2}'.\
#                 format(CURRENT, num, hexstr(6, LC0+LCi)))
# 
# 
#     # --- SUBSTEP MNEMONIC: See if we have a mnemonic ---
# 
#     # Because we are using Typist's Assembler Notation and every mnemonic
#     # maps to one and only one opcode, we don't have to look at the operand of
#     # the instruction at all, which is a lot simpler
# 
#     try:
#         oc = mnemonics[w[0]]
#     except KeyError:
#         pass
#     else:
# 
#         # For branches, we want to remember were the instruction is to make our
#         # life easier later
#         if w[0] in BRANCHES:
#             pay = pay + ' ' + hexstr(4, LC0+LCi)
#             sta = MODIFIED
#             verbose('Added address of branch to its payload in line {0}'.\
#                     format(num))
# 
#         LCi += opcode_table[oc][2]
# 
#         # Factor in register size if this is a 65816
#         if MPU == '65816':
# 
#             if w[0] in A_IMM:
#                 LCi += a_len_offset
#             elif w[0] in XY_IMM:
#                 LCi += xy_len_offset
# 
#         sc_labels.append((num, pay, sta))
#         continue
# 
#     # --- SUBSTEP SAVE: Handle the .save directive ---
#     if w[0] == '.save':
# 
#         # Add the symbol to the symbol list
#         vet_newsymbol(w[1])
#         symbol_table[w[0]] = LC0+LCi
# 
#         # We've already taken care of any strings, which we couldn't use anyway,
#         # and characters, which is weird but legal.
#         wt = pay.strip().split(' ', 2)[2]
#         r = convert_term(num, wt)
# 
#         # We save r zeros (initialize reserved space)
#         zl = ' '.join(['00']*r)
#         new_pay = INDENT+'.byte '+zl
#         sc_labels.append((num, new_pay, DATA_DONE))
#         
#         verbose('Saved {0} bytes at address {1:06x} per directive in line {2}'.\
#                     format(r, LC0+LCi, num))
#  
#         LCi += r
#         continue 
# 
# 
#     # --- SUBSTEP LABELS: Figure out where our labels are ---
# 
#     # Labels and anonymous labels are the only things that should be in the first
#     # column at this point
# 
#     if pay[0] not in string.whitespace:
# 
#         # Local labels are easiest, start with them first
#         if w[0] == LOCAL_LABEL:
#             anon_labels.append((num, LC0+LCi))
#             verbose('New anonymous label found in line {0}, address {1:06x}'.\
#                     format(num, LC0+LCi))
#             continue
# 
#         # This must be a real label. If we don't have it in the symbol table,
#         # all is well and we add a new entry
#         if w[0] not in symbol_table.keys():
#             verbose('New label "{0}" found in line {1}, address {2:06x}'.\
#                     format(w[0], num, LC0+LCi))
#             symbol_table[w[0]] = LC0+LCi
#             continue
# 
#         # If it is already known, something went wrong, because we can't
#         # redefine a label, because that gets really confusing very fast
#         else:
#             fatal(num, 'Attempt to redefine symbol "{0}" in line {1}'.\
#                     format(w[0], pay))
# 
# 
#     # --- SUBSTEP DATA: See if we were given data to store ---
#     
#     # Because of ideological reasons, we don't convert the instructions at this
#     # point, but just count their bytes. Note these entries are not separated by
#     # spaces, but by commas, so we have to split them all over again.
# 
#     d = pay.split(',')
# 
#     # .BYTE stores one byte per comma-separated word
#     if w[0] == '.byte':
#         LCi += len(d)
#         sc_labels.append((num, pay, sta))
#         continue
# 
#     # .WORD stores two bytes per comma-separated word
#     if w[0] == '.word':
#         LCi += 2*(len(d))
#         sc_labels.append((num, pay, sta))
#         continue
# 
#     # .LONG stores three bytes per comma-separated word
#     if w[0] == '.long':
#         LCi += 3*(len(d))
#         sc_labels.append((num, pay, sta))
#         continue
# 
# 
#     # --- SUBSTEP SWITCHES: Handle Register Switches on the 65816 ---
# 
#     # For the 65816, we have to take care of the register size switches
#     # because the Immediate Mode instructions such as lda.# compile a different
#     # number of bytes. We need to keep the directives themselves for the later
#     # stages while we are at it
# 
#     if MPU == '65816':
# 
#         if w[0] == '.!native':
#             mpu_status = 'native'
#             continue
# 
#         if w[0] == '.!emulated':
#             mpu_status = 'emulated'
#             continue
# 
#         if w[0] == '.!a8':
#             a_len_offset = 0
#             sc_labels.append((num, pay, sta))
#             continue
# 
#         elif w[0] == '.!a16':
# 
#             # We can't switch to 16 bit A if we're not in native mode
#             if mpu_status == 'emulated':
#                 fatal(num, 'Attempt to switch A to 16 bit in emulated mode')
# 
#             a_len_offset = 1
#             sc_labels.append((num, pay, sta))
#             continue
# 
#         elif w[0] == '.!xy8':
#             xy_len_offset = 0
#             sc_labels.append((num, pay, sta))
#             continue
# 
#         elif w[0] == '.!xy16':
# 
#             # We can't switch to 16 bit X/Y if we're not in native mode
#             if mpu_status == 'emulated':
#                 fatal(num, 'Attempt to switch X/Y to 16 bit in emulated mode')
# 
#             xy_len_offset = 1
#             sc_labels.append((num, pay, sta))
#             continue
# 
# 
#     # --- SUBSTEP ADVANCE: See if we have the .advance directive ---
#     
#     if w[0] == '.advance':
#         r = convert_term(num, w[1])
# 
#         # Make sure the user is not attempting to advance backwards
#         if r < (LCi+LC0):
#             fatal(num, '.advance directive attempting to march backwards')
# 
#         # While we're here, we might as well already convert this to .byte
#         # though it violates our ideology ("Do as I say, don't do as I do")
#         
#         offset = r - (LCi+LC0)
#         zl = ' '.join(['00']*offset)
#         new_pay = INDENT+'.byte '+zl
#         sc_labels.append((num, new_pay, DATA_DONE))
#         LCi = r-(LCi+LC0)
#         verbose('Replaced .advance directive in line {0} by .byte directive'.\
#                 format(num))
#         continue
# 
# 
#     # --- SUBSTEP SKIP: See if we have a .skip directive ---
#     
#     if w[0] == '.skip':
#         r = convert_term(num, w[1])
# 
#         # While we're here, we might as well already convert this to .byte
#         # though it is against our ideology ("Do as I say, don't do as I do")
#         zl = ' '.join(['00']*r)
#         new_pay = INDENT+'.byte '+zl
#         sc_labels.append((num, new_pay, DATA_DONE))
#         LCi += r
#         verbose('Replaced .skip directive in line {0} by .byte directive'.\
#                 format(num))
#         continue
# 
#     # If none of that was right, keep the old line
#     sc_labels.append((num, pay, sta))
# 
# 
# n_passes += 1
# verbose('PASS LABELS: Assigned value to all labels.')
# dump(sc_labels, "nps")
# 
# if args.verbose:
#     dump_symbol_table(symbol_table, "after LABELS (numbers in hex)")
# 
# if args.dump:
#     print('Anonymous Labels:')
#     if len(anon_labels) > 0:
#         for ln, ll in anon_labels:
#             print('{0:5}: {1:06x} '.format(ln, ll))
#         print('\n')
#     else:
#         print('  (none)\n')
# 
# 
# # -------------------------------------------------------------------
# # PASS ASSIGN: Handle complex assignments
# 
# # We accept assignments in the form ".equ <SYM> <NBR>". Since we've
# # moved all labels to their own lines, any such directive must be the first
# # word in the line
# 
# sc_assign = []
# 
# for num, pay, sta in sc_labels:
# 
#     w = pay.split()
# 
#     # Leave if this is not an assignment (line doesn't start with '.equ')
#     if w[0] != ASSIGNMENT:
#         sc_assign.append((num, pay, sta))
#         continue
#         
#     vet_newsymbol(w[1]) 
#     
#     # Everything after the assignment directive and the symbol has to be part of
#     # the term
#     cp = pay.strip()
#     rs = convert_term(num, cp.split(' ', 2)[2])
#     symbol_table[w[1]] = rs
# 
# n_passes += 1
# verbose('PASS ASSIGN: Assigned {0} symbols to symbol table'.\
#         format(len(sc_labels)-len(sc_assign)))
# dump(sc_assign, "nps")
# 
# # Print symbol table
# if args.verbose:
#     dump_symbol_table(symbol_table, "after ASSIGN (numbers in hex)")
# 
# 
# # -------------------------------------------------------------------
# # PASS REPLACE (2): Handle known assignments, reprise
# sc_replaced02 = replace_symbols(sc_assign)
# 
# 
# # -------------------------------------------------------------------
# # CLAIM: At this point we should have all symbols present and known in the
# # symbol table, and anonymous labels in the anonymous label list
# 
# verbose('CLAMING that all symbols should now be known')
# 
# # -------------------------------------------------------------------
# # PASS DATA: Convert various data formats like .byte
# 
# sc_data = []
# 
# for num, pay, sta in sc_replaced02:
# 
#     w = pay.split()
# 
#     # This is for .byte, .word, and .long
#     if w[0] not in DATA_DIRECTIVES:
#         sc_data.append((num, pay, sta))
#         continue 
# 
#     # Stuff like .advance and .skip might already be done, we don't have to do
#     # it over
#     if sta == DATA_DONE or sta == CODE_DONE:
#         sc_data.append((num, pay, sta))
#         continue 
# 
#     # Regardless of which format we have, it should contain a list of
#     # comma-separated terms
#     ps = pay.strip().split(' ', 1)[1] # Get rid of the directive
#     ts = ps.split(',')
#     new_t = []
# 
#     for t in ts:
#         new_t.append(convert_term(num, t))
# 
#     # We now have a list of the numbers, but need to break them down into
#     # their bytes. This could be solved a lot more elegantly, but this is
#     # easier to understand
#     byte_t = []
# 
#     if w[0] == '.byte':
#         byte_t = new_t
# 
#     elif w[0] == '.word':
#         for n in new_t:
#             for b in little_endian_16(n):
#                 byte_t.append(b)
# 
#     elif w[0] == '.long':
#         for n in new_t:
#             for b in little_endian_24(n):
#                 byte_t.append(b)
# 
#     # Reassemble the datastring, getting rid of the trailing comma
#     new_pay = INDENT+'.byte '+' '.join([hexstr(2, b) for b in byte_t])
#     
#     sc_data.append((num, new_pay, DATA_DONE))
# 
# n_passes += 1
# verbose('PASS DATA: Converted all data formats to .byte')
# dump(sc_data, "nps")
# 
# # -------------------------------------------------------------------
# # PASS MATH
# 
# # Replace all math terms that are left in the text, eg 'jmp { label + 2 }'. 
# # None of these should be in assignments any more
# 
# sc_math = []
# 
# for num, pay, sta in sc_data:
# 
#     if LEFTMATH not in pay:
#         sc_math.append((num, pay, sta))
#         continue
# 
#     # Life is still easy if we only have one bracket
#     if pay.count(LEFTMATH) == 1:
#         sc_math.append((num, do_math(pay), MODIFIED))
#         continue
# 
#     # More than one math term, so we have to do this the hard way
#     while LEFTMATH in pay:
#         pay = do_math(pay)
# 
#     sc_math.append((num, pay, MODIFIED))
#     
# 
# n_passes += 1
# verbose('PASS MATH: replaced all math terms by numbers')
# dump(sc_math, "nps")
# 
# 
# # -------------------------------------------------------------------
# # PASS MODIFY
# 
# # Replace all modify terms that are left in the text, eg 'lda.# .msb 1000'. 
# # None of these should be in assignments any more
# 
# sc_modify = []
# 
# def has_modifier(s):
#     """Given a string with space-separated words, return True if one of 
#     these words is a modifier, else false.
#     """
#     return bool([i for i in MODIFIERS if i in s])
# 
# 
# for num, pay, sta in sc_math:
# 
#     if has_modifier(pay):
#         
#         # We need to use next entry once we find a modifier, so we need to make
#         # this iterable
#         new_pay = ""
#         ws = iter(pay.split())
# 
#         for w in ws:
# 
#             if w in MODIFIERS:
#                 f_num, r = convert_number(next(ws))
# 
#                 if f_num:
#                     w = hexstr(6, MODIFIERS[w](r))
#                 else: 
#                     fatal(num, 'Modifier operand "{0}" not a number'.format(w))
# 
#             new_pay = new_pay + ' ' + w
#              
#         pay = new_pay
#         sta = MODIFIED
# 
#     sc_modify.append((num, INDENT+pay.strip(), sta))
# 
# n_passes += 1
# verbose('PASS MODIFY: replaced all modifier terms by numbers')
# dump(sc_modify, "nps")
# 
# 
# # -------------------------------------------------------------------
# # PASS ANONYMOUS: Replace all anonymous label references by correct numbers
# 
# # We don't modify anonymous labels or do math on them
# 
# sc_anons = []
# 
# for num, pay, sta in sc_modify:
# 
#     w = pay.split()
# 
#     # We only allow the anonymous references to be in the second word of the line,
#     # that is, as an operand to an opcode
# 
#     if len(w) > 1 and w[1] == '+':
#         for ln, ll in anon_labels:
#             if ln > num:
#                 pay = pay.replace('+', hexstr(6, ll))
#                 sta = MODIFIED
#                 break
# 
#     if len(w) > 1 and w[1] == '-':
#         for ln, ll in reversed(anon_labels):
#             if ln < num:
#                 pay = pay.replace('-', hexstr(6, ll))
#                 sta = MODIFIED
#                 break
# 
#     sc_anons.append((num, pay, sta))
# 
# n_passes += 1
# verbose('PASS ANONYMOUS: Replaced all anonymous labels with address values')
# dump(sc_anons, "nps")
# 
# # -------------------------------------------------------------------
# # CLAIM: At this point we should have completely replaced all labels and
# # symbols with numerical values.
# 
# verbose('CLAMING there should be no labels or symbols left in the source')
# 
# 
# # -------------------------------------------------------------------
# # CLAIM: At this point there should only be .byte data directives in the code
# # with numerical values.
# 
# verbose('CLAMING that all data is now contained in .byte directives')
# 
# 
# # -------------------------------------------------------------------
# # PASS 1BYTE: Convert all single-byte instructions to .byte directives
# 
# # Low-hanging fruit first: Compile the opcodes without operands
# 
# sc_1byte = []
# 
# for num, pay, sta in sc_anons:
# 
#     w = pay.split()
# 
#     try:
#         oc = mnemonics[w[0]]
#     except KeyError:
#         sc_1byte.append((num, pay, sta))
#     else:
# 
#         if opcode_table[oc][2] == 1:    # look up length of instruction
#             bl = INDENT+'.byte '+hexstr(2, oc)
#             sc_1byte.append((num, bl, CODE_DONE))
#         else:
#             sc_1byte.append((num, pay, sta))
# 
# n_passes += 1
# verbose('PASS 1BYTE: Assembled single byte instructions')
# dump(sc_1byte, "nps")
# 
# 
# # -------------------------------------------------------------------
# # PASS BRANCHES: Assemble branch instructions
# 
# # All our branch instructions, including bra.l and phe.r on the 65816, should
# # include the line they are on as the last entry in the payload at this point
# 
# sc_branches = []
# 
# # Keep this definition in the branches pass
# BRANCHES = {
#     '6502': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs'],\
#     '65c02': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
#         'bra'],\
#     '65816': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
#         'bra', 'bra.l', 'phe.r']}
# 
# for num, pay, sta in sc_1byte:
# 
#     # Skip stuff that is already done
#     if sta == CODE_DONE or sta == DATA_DONE:
#         sc_branches.append((num, pay, sta))
#         continue
# 
#     w = pay.split()
# 
#     if w[0] in BRANCHES[MPU]:
#         new_pay = '.byte '+hexstr(2, mnemonics[w[0]])+' '
#         _, branch_addr = convert_number(w[-1])
#         _, target_addr = convert_number(w[-2])
#         opr = hexstr(2, lsb(target_addr - branch_addr - 2))
#         sc_branches.append((num, INDENT+new_pay+opr, CODE_DONE))
#         continue
# 
#     if MPU == '65816' and w[0] in BRANCHES[MPU]: 
#         new_pay = '.byte '+hexstr(2, mnemonics[w[0]])+' '
#         _, branch_addr = convert_number(w[-1])
#         _, target_addr = convert_number(w[-2])
#         bl, bm = little_endian_16(target_addr - branch_addr - 3)
#         opr = INDENT+new_pay+hexstr(2, bl)+' '+hexstr(2, bm)
#         sc_branches.append((num, opr, CODE_DONE))
#         continue
# 
#     # Everything else
#     sc_branches.append((num, pay, sta))
# 
# n_passes += 1
# verbose('PASS BRANCHES: Encoded all branch instructions')
# dump(sc_branches, "nps")
# 
# # -------------------------------------------------------------------
# # PASS FUSEMOVE: Reassemble and convert move instructions
# 
# # All move instructions should have been split up and their operands converted.
# # We now put them back together, remembering that destination comes before
# # source in the machine code of MVN and MVP
# 
# sc_move = []
# 
# if MPU == '65816':
# 
#     # We need to be able to skip ahead in the list so we have to use an iter
#     # object in this case
#     l = iter(sc_branches)
# 
#     for num, pay, _ in l:
# 
#         w = pay.split()
# 
#         if w[0] == 'mvp' or w[0] == 'mvn':
# 
#             # Handle opcode
#             tmp_pay = INDENT + '.byte ' + str(mnemonics[w[0]]) + ' '
# 
#             # Handle source byte
#             _, r = convert_number(w[1])
#             m_src = hexstr(2,r)
# 
#             # Handle destination byte
#             _, pay2, _ = next(l)
#             _, r = convert_number(pay2.split()[1])
#             m_des = hexstr(2,r)
# 
#             # Put it all together
#             tmp_pay = tmp_pay + m_des + ' ' + m_src
#             sc_move.append((num, tmp_pay, CODE_DONE))
# 
#         else:
# 
#             sc_move.append((num, pay, sta))
# 
#     n_passes += 1
#     verbose('PASS FUSEMOVE: Handled mvn/mvp instructions on the 65816')
#     dump(sc_move, "nps")
# 
# else:
#     sc_move = sc_branches
# 
# 
# # -------------------------------------------------------------------
# # PASS ALLIN: Assemble all remaining operands
# 
# # This should remove all CONTROL entries as well
# 
# sc_allin = []
# 
# # On the 65816, remember to start in emulated, 8-bit mode at the beginning
# mpu_status = 'emulated'
# a_len_offset = 0
# xy_len_offset = 0
# 
# for num, pay, sta in sc_move:
# 
#     w = pay.split()
# 
#     if MPU == '65816':
# 
#         # TODO Rewrite this horrible code once we are sure this is what we want
#         # to do. Note it appears twice
#         # TODO make sure switch to 16 only works in native mode
#         if w[0] == '.!a8':
#             a_len_offset = 0
#             continue
# 
#         elif w[0] == '.!a16':
#             a_len_offset = 1
#             continue
# 
#         elif w[0] == '.!xy8':
#             xy_len_offset = 0
#             continue
# 
#         elif w[0] == '.!xy16':
#             xy_len_offset = 1
#             continue
# 
#     try:
#         oc = mnemonics[w[0]]
#     except KeyError:
#         sc_allin.append((num, pay, sta))
#     else:
# 
#         # Get number of bytes in instruction
#         n_bytes = opcode_table[oc][2]
# 
#         # Factor in register size if this is a 65816
#         if MPU == '65816':
# 
#             if w[0] in A_IMM:
#                 n_bytes += a_len_offset
#             elif w[0] in XY_IMM:
#                 n_bytes += xy_len_offset
# 
#         _, opr = convert_number(w[1])
# 
#         # We hand tuples to the next step
#         if n_bytes == 2:
#             bl = (lsb(opr), )
#         elif n_bytes == 3:
#             bl = little_endian_16(opr)
#         elif n_bytes == 4:
#             bl = little_endian_24(opr)
#         else:
#             # This should never happen, obviously, but we're checking anyway
#             fatal(num, 'Found {0} byte instruction in opcode list'.\
#                     format(n_bytes))
# 
#         # Reassemble payload as a byte instruction. We keep the data in
#         # human-readable form instead of converting it to binary data
#         pay = '{0}.byte {1:02x} {2}'.\
#                 format(INDENT, oc, ' '.join([hexstr(2, i) for i in bl]))
#         sc_allin.append((num, pay, CODE_DONE))
# 
# n_passes += 1
# verbose('PASS ALLIN: Assembled all remaining operands')
# dump(sc_allin, "nps")
# 
# 
# # -------------------------------------------------------------------
# # PASS VALIDATE: Make sure we only have .byte instructions
# 
# # We shouldn't have anything left now that isn't a byte directive
# # This pass does not change the source file
# 
# for num, pay, _ in sc_allin:
# 
#     w = pay.split()
# 
#     if w[0] != '.byte':
#         fatal(num, 'Found illegal opcode/directive "{0}"'.format(pay.strip()))
# 
# n_passes += 1
# verbose('PASS VALIDATE: Confirmed that all lines are now byte data')
# 
# 
# # -------------------------------------------------------------------
# # PASS BYTECHECK: Make sure all values are valid bytes
# 
# for num, pay, _ in sc_allin:
# 
#     bl = pay.split()[1:]
# 
#     for b in bl:
# 
#         f_num, r = convert_number(b)
# 
#         if not f_num:
#             fatal(num, 'Found non-number "{0}" in byte list'.format(b))
# 
#         if r > 0xff or r < 0:
#             fatal(num, 'Value "{0}" does not fit into one byte'.format(b))
# 
# n_passes +=1
# verbose('PASS BYTECHECK: Confirmed all byte values are in range from 0 to 256')
# 
# 
# # -------------------------------------------------------------------
# # PASS ADR: Add addresses for human readers and listing generation
# 
# # This produces the final human readable version and is the basis for the
# # listing file
# 
# def format_adr16(i):
#     """Convert an integer to a 16 bit hex address string for the listing
#     file
#     """
#     return '{0:04x}'.format(i & 0xffff)
# 
# def format_adr24(i):
#     """Convert an integer to a 24 bit hex address string for the listing
#     file. We use a separator for the bank byte
#     """
#     return '{0:02x}:{1:04x}'.format(bank(i), i & 0xffff)
# 
# format_adr_mpu = {'6502': format_adr16,\
#         '65c02': format_adr16,\
#         '65816': format_adr24}
# 
# sc_adr = []
# LCi = 0
# 
# for num, pay, sta in sc_allin:
# 
#     b = len(pay.split())-1
#     adr = format_adr_mpu[MPU](LC0+LCi)
#     sc_adr.append((num, pay, sta, adr))
#     LCi += b
# 
# n_passes += 1
# verbose('PASS ADR: Added MPU address locations to each byte line')
# dump(sc_adr, "npsa")
# 
# 
# # -------------------------------------------------------------------
# # PASS OPTIMIZE: Analyze and optimize code
# 
# # We don't perform automatic optimizations at the moment, but only provide
# # suggestions and warnings here. We need the line numbers so we can offer
# # the user suggestions based on his original source code
# 
# for num, pay, _, _ in sc_adr:
# 
#     w = pay.split()[1:]  # get rid of '.byte' directive
# 
#     # SUBSTEP WDM: Check to see if we have WDM instruction
#     if w[0] == '42':
#         warning('Reserved instruction WDM (0x42) found in line {0}'.\
#                 format(num))
#         continue
# 
# n_passes += 1
# verbose('PASS ANALYZE: Searched for obvious errors and improvements')
# 
# 
# # -------------------------------------------------------------------
# # PASS PUREBYTES: Remove everything except byte values (ie, remove .byte)
# 
# def strip_byte(s):
#     """Strip out the '.byte' directive from a string"""
#     return s.replace('.byte ', '').strip()
# 
# sc_purebytes = []
# 
# for _, pay, _, _ in sc_adr:
#     pay_bytes = strip_byte(pay)
#     bl = [int(b, 16) for b in pay_bytes.split()]
#     sc_purebytes.append(bl)
# 
# n_passes += 1
# verbose('PASS PUREBYTES: Converted all lines to pure byte lists')
# 
# if args.dump:
# 
#     for l in sc_purebytes:
#         print('  ', end=' ')
#         for b in l:
#             print('{0:02x}'.format(b), end=' ')
#         print()
#     print()
# 
# 
# # -------------------------------------------------------------------
# # PASS TOBIN: Convert lists of bytes into one single byte list
# 
# sc_tobin = []
# 
# for i in sc_purebytes:
#     sc_tobin.extend(i)
# 
# objectcode = bytes(sc_tobin)
# code_size = len(objectcode)
# 
# n_passes += 1
# verbose('PASS TOBIN: Converted {0} lines of bytes to one list of {1} bytes'.\
#         format(len(sc_purebytes), code_size))
# 
# 
# # -------------------------------------------------------------------
# # STEP SAVEBIN: Save binary file
# 
# with open(args.output, 'wb') as f:
#     f.write(objectcode)
# 
# n_steps += 1
# verbose('STEP SAVEBIN: Saved {0} bytes of object code as {1}'.\
#         format(code_size, args.output))
# 
# 
# # -------------------------------------------------------------------
# # STEP WARNINGS: Print warnings unless user said not to
# #
# if n_warnings != 0 and args.warnings:
#     print('Generated {0} warning(s).'.format(n_warnings))
# 
# n_steps += 1
# 
# 
# # -------------------------------------------------------------------
# # STEP LIST: Create listing file if requested
# 
# # This is a simple listing file, we are waiting to figure out what we need
# # before we create a more complex one
# 
# LEN_BYTELIST = 11
# LEN_INSTRUCTION = 15
# ELLIPSIS = ' (...)'
# 
# if args.listing:
# 
#     with open(LIST_FILE, 'w') as f:
# 
#         # Header
#         f.write(TITLE_STRING)
#         f.write('Code listing for file {0}\n'.format(args.source))
#         f.write('Generated on {0}\n'.format(time.asctime(time.localtime())))
#         f.write('Target MPU: {0}\n'.format(MPU))
#         time_end = timeit.default_timer()
#         if n_external_files != 0:
#             f.write('External files loaded: {0}\n'.format(n_external_files))
#         f.write('Number of passes executed: {0}\n'.format(n_passes))
#         f.write('Number of steps executed: {0}\n'.format(n_steps))
#         f.write('Assembly time: {0:.5f} seconds\n'.format(time_end - time_start))
#         if n_warnings != 0:
#             f.write('Warnings generated: {0}\n'.format(n_warnings))
#         f.write('Code origin: {0:06x}\n'.format(LC0))
#         f.write('Bytes of machine code: {0}\n'.format(code_size))
# 
#         # Code listing
#         f.write('\nLISTING:\n')
#         f.write('       Line Address  Bytes        Instruction\n')
# 
# 
#         # We start with line 1 because that is the way editors count lines
#         c = 1
#         sc_tmp = sc_axy     # This is where we take the instructions from
# 
#         for num, pay, _, adr in sc_adr:
# 
#             # Format bytelist
#             bl = pay.replace('.byte', '').strip()
# 
#             # If the line is too long, replace later values by "..."
#             if len(bl) > LEN_BYTELIST:
#                 bl = bl[:LEN_BYTELIST-len(ELLIPSIS)]+ELLIPSIS
#             else:
#                 padding = (LEN_BYTELIST - len(bl))*' '
#                 bl = bl+padding
# 
#             # Format instruction
#             instr = '(data)'
# 
#             for i in range(len(sc_tmp)):
# 
#                 # Since we delete entries from sc_tmp, this loop will fail at
#                 # some point because the list gets shorter. That's when we're
#                 # done
#                 try:
#                     num_i, pay_i, sta_i = sc_tmp[i]
#                 except IndexError:
#                     break
#                 else:
#                     # Skip leftover CONTROL instructions
#                     if sta_i == CONTROL:
#                         continue
#                     if num_i == num:
#                         instr = pay_i.strip()
#                         del sc_tmp[i]
# 
#             # Format one line 
#             l = '{0:5d} {1:5d} {2}  {3!s}  {4}\n'.\
#                     format(c, num, adr, bl, instr)
# 
#             f.write(l)
#             c += 1
# 
# 
#         # Add macro list
#         f.write('\nMACROS:\n')
# 
#         if len(macros) > 0:
# 
#             for m in macros.keys():
#                 f.write('Macro "{0}"\n'.format(m))
# 
#                 for ml in macros[m]:
#                     f.write('    {0}\n'.format(ml))
# 
#             f.write('\n\n')
# 
#         else:
#             f.write(INDENT+'(none)\n\n')
# 
# 
#         # Add symbol table
#         f.write('SYMBOL TABLE:\n')
# 
#         if len(symbol_table) > 0:
# 
#             for v in sorted(symbol_table):
#                 f.write('{0} : {1:06x}\n'.\
#                         format(v.rjust(ST_WIDTH), symbol_table[v]))
#             f.write('\n')
# 
#         else:
#             f.write(INDENT+'(empty)\n')
# 
# 
#     n_steps += 1
#     verbose('STEP LIST: Saved listing as {0}'.format(LIST_FILE))
# 
# 
# # -------------------------------------------------------------------
# # STEP HEXDUMP: Create hexdump file if requested
# 
# if args.hexdump:
# 
#     with open(HEX_FILE, 'w') as f:
#         f.write(TITLE_STRING)
#         f.write('Hexdump file of {0}'.format(args.source))
#         f.write(' (total of {0} bytes)\n'.format(code_size))
#         f.write('Generated on {0}\n\n'.format(time.asctime(time.localtime())))
#         a65 = LC0
#         f.write('{0:06x}: '.format(a65))
# 
#         c = 0
# 
#         for e in objectcode:
#             f.write('{0:02x} '.format(e))
#             c += 1
#             if c % 16 == 0:
#                 f.write('\n')
#                 a65 += 16
#                 f.write('{0:06x}: '.format(a65))
#         f.write('\n')
# 
#     n_steps += 1
#     verbose('STEP HEXDUMP: Saved hexdump file as {0}'.format(HEX_FILE))
# 
# 
# # -------------------------------------------------------------------
# # STEP END: Sign off
# 
# time_end = timeit.default_timer()
# verbose('\nSuccess! All steps completed in {0:.5f} seconds.'.\
#         format(time_end - time_start))
# verbose('Enjoy your cake.')
# sys.exit(0)
# 
# ### END ###
# 
