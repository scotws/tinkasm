# A Tinkerer's Assembler for the 6502/65c02/65816 in Forth
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 24. Jan 2017

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
n_switches = 0          # How many 8/16 bit register switches on 65816
n_warnings = 0          # How many warnings were generated
code_size = 0           # Final size in bytes


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
parser.add_argument('-l', '--listing', action='store_true',\
        help='Create listing file (default TINK.LST)')
parser.add_argument('-x', '--hexdump', action='store_true',\
        help='Create ASCII hexdump listing file (default TINK.HEX)')
parser.add_argument('-s28', action='store_true',\
        help='Create S28 format file from binary (default TINK.S28)')
parser.add_argument('-p', '--print', action='store_true', default=False,\
        help='Print listing to screen at end')
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
        fatal(line, 'TypeError in hexstr for "{0}": {1}'.format(i, err)) 

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
    global n_warnings
    n_warnings += 1
    if args.warnings:
        print('WARNING: {0}'.format(s))


### CONSTANTS ###

TITLE_STRING = \
"""A Tinkerer's Assembler for the 6502/65c02/65816
Version BETA 24. January 2017
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

# We store the general lists here, those specific to one processor type are put
# in the relevant passes
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
        self.action = ''        # First word of instruction or directive
        self.parameters = ''    # Parameter(s) of instruction or directive
        self.address = 0        # Address where line data begins (16/24 bit)
        self.il_comment = ''    # Storage area for any inline comments
        self.size = 0           # Size of instruction in bytes
        self.bytes = ''         # Bytes for actual, final assembly
        self.mode = 'em'        # For 65816: default mode (emulated)
        self.a_width = 8        # For 65816: defalt width of A register
        self.xy_width = 8       # For 65816: default width of XY registers



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

def lsb(line, n):
    """Return Least Significant Byte of a number"""
    try: 
        t = n & 0xff
    except TypeError:
        fatal(line, "Can't convert '{0}' to lsb".format(n))
    else:
        return t

def msb(line, n):
    """Return Most Significant Byte of a number"""
    try: 
        t = (n & 0xff00) >> 8
    except TypeError: 
        fatal(line, "Can't convert '{0}' to msb".format(n))
    else:
        return t

def bank(line, n):
    """Return Bank Byte of a number"""
    try: 
        t = (n & 0xff0000) >> 16
    except TypeError: 
        fatal(line, "Can't convert '{0}' to bank".format(n))
    else:
        return t


MODIFIERS = {'.lsb': lsb, '.msb': msb, '.bank': bank}

def little_endian_16(line, n):
    """Given a number, return a tuple with two bytes in correct format"""
    return lsb(line, n), msb(line, n)

def little_endian_24(line, n):
    """Given a number, return a tuple with three bytes in correct format"""
    return lsb(line, n), msb(line, n), bank(line, n)

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
            r = symbol_table[w.lower()]
        except KeyError:
            fatal(line, 'Illegal term "{0}" in math term'.format(w))
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
        fatal(line, 'Directive "{0}" cannot be redefined as a symbol'.\
                format(s))

    # We don't allow using mnemonics as symbols because that screws up other
    # stuff and is really weird anyway
    if s in mnemonics.keys(): 
        fatal(line, 'Mnemonic "{0}" cannot be redefined as a symbol'.\
                format(s))

    # We don't allow redefining existing symbols, this catches various errors 
    if s in symbol_table.keys():
        fatal(line, 'Symbol "{0}" already defined'.format(s))


def replace_symbols(src):
    """Given the list of CodeLine elements, replace the symbols we know.
    Will find symbols in math terms, but not in .BYTE etc data 
    directives.
    """
    sr_count = 0 

    for line in src: 

        if (line.status == DONE) or (line.type == LABEL):
            continue 
    
        # We need to go word-by-word because somebody might be defining .byte 
        # data as symbols
        wc = []
        ws = line.parameters.split()

        # Spliting the lines returns whatever is separated by whitespace. In
        # data directives such as .BYTE, however, this will return the symbol
        # with a comma tacked on. We take care of those cases separately
        for w in ws:

            try:
                # We don't define the number of digits because we have no idea
                # what the number they represent are supposed to be
                w = hexstr(6, symbol_table[w])
            except KeyError:
                pass
            else:
                sr_count += 1
                line.status = MODIFIED
            finally:
                wc.append(w)

        line.parameters = ' '.join(wc)

    verbose('PASS REPLACED: Replaced {0} known symbol(s) with known values'.\
            format(sr_count))


def dump_symbol_table(st, s=""):
    """Print Symbol Table to screen"""

    print('Symbol Table', s)

    if len(st) <= 0:
        print(' - (symbol table is empty)\n')
        return

    # Find longest symbol name in table
    max_sym_len = max([len(k) for k in st.keys()])

    for v in sorted(st):
        print('- {0:{width}} : {1:06x}'.format(v, st[v], width=max_sym_len))


def convert_term(line, s): 
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
        rest = s.split(' ', 1)[1]
        rt = convert_term(line, rest)
        r = MODIFIERS[w[0]](line, rt)
        return r 

    # --- SUBSTEP OOPS: If we made it to here, something is wrong ---
    fatal(line, 'Cannot convert term "{0}"'.format(s))


### OUTPUT DEFINITIONS ###

# TODO make format of 6502/65c02 output prettier by eliminating whitespace

def hide_zero_address(n):
    """Given the address of an instruction, if it is zero, return an
    empty string, else return a six-character hex string
    """
    if n == 0:
        return ' ' 
    else:
        if MPU == '65816':
            width = 6
        else:
            width = 4
        return hexstr(width, n)
 

def listing_header(l):
    """Create a header for all lines, regardless of type. Takes a line object 
    and returns a string.
    """

    if MPU == '65816':
        h = '{0:4}:{1:03} | {2} {3} | {4} {5:2} {6:2} |'.\
                format(l.ln, l.sec_ln, l.status, l.type, l.mode, l.a_width,\
                l.xy_width)
    else: 
        h = '{0:4}:{1:03} | {2} {3} |'.format(l.ln, l.sec_ln, l.status, l.type)
    
    return h
            

def listing_comment(l): 
    """Given a line object that contains a full-line comment, create a string
    for full-line comments. Assumes that the header will be added by calling
    program.
    """
    return '        |             | '+l.raw.rstrip()   # rstrip() is paranoid 


def listing_whitespace(l):
    """Given a line object that contains whitespace, return a string. Assumes
    that the header will be added by calling program.
    """
    return '        |             |'


def listing_instruction(l):
    """Template for instructions for the Intermediate Representation. 
    Takes a line object and returns a string for writing to the file.
    Assumes that the header will be added by the caller.
    """
    s = ' {0:6} | {1:11} | {2:36} {3}'.\
        format(hide_zero_address(l.address), l.bytes,\
        INDENT+INDENT+l.action+' '+l.parameters, l.il_comment)
    return s 


def listing_directive(l):
    """Template for directives for the Intermediate Representation. 
    Takes a line object and returns a string for writing to the file.
    """
    # If we get a data directive, we might have to add a table
    table = '' 

    # Some directives would overflow the line, we can simplify
    if l.action in ['.advance', '.skip', '.save']:
        b_list = '({0}x 00)'.format(l.size)
    else:
        b_list = l.bytes

    # Data directives can overflow a line so we have to treat them separately
    if l.action in DATA_DIRECTIVES:

        b_list = '({0} bytes)'.format(l.size)

        table_header = '\n'+listing_header(l)+\
                (' '*8)+'|'+(' '*13)+'|'+INDENT+INDENT
        table_line = table_header
        ascii_line = ''
        c = 0

        for b in l.bytes.split():
            table_line = table_line+' {0}'.format(b)

            char = chr(int(b, 16))

            if char not in string.printable:
                char = '.'

            ascii_line = ascii_line+' '+char
            c += 1
            
            if c % 8 == 0:
                table = table+'{0:96}  -- {1}'.format(table_line, ascii_line)
                ascii_line = ''
                table_line = table_header 

        table = table+'{0:96}  -- {1}'.format(table_line, ascii_line)

    lp = INDENT+l.action+' '+l.parameters

    # Some lines are just too long
    if len(lp) > 70:
        lp = lp[:65]+' (...)'

    s = ' {0:6} | {1:11} | {2:36} {3}{4}'.\
        format(hide_zero_address(l.address), b_list, lp, l.il_comment, table)
    return s 


def listing_label(l):
    """Template for a line object that contains a label, returns a string. 
    Assumes that the header will be added by calling program.
    """

    s = ' {0:6} |             | {1:36} {2}'.\
             format(hide_zero_address(l.address), l.action, l.il_comment)

    return s


def listing_control(l):
    """Template for a line object that contains a control instruction. 
    Returns a string. Assumes that the header will be added by calling 
    program.
    """
    s = '        |             | {0:11}'.format(INDENT+l.action)
    return s


line_listing_types = {
        INSTRUCTION: listing_instruction,
        COMMENT: listing_comment,
        WHITESPACE: listing_whitespace,
        CONTROL: listing_control,
        DIRECTIVE: listing_directive,
        LABEL: listing_label }


def make_listing(src):
    """Given a list of line objects, return a list of strings with each
    line processed for user output.
    """

    listing = []

    # Header

    listing.append(TITLE_STRING)
    listing.append('Code listing for file {0}'.format(args.source))
    listing.append('Generated on {0}'.format(time.asctime(time.localtime())))
    listing.append('Target MPU: {0}'.format(MPU))


    if n_external_files != 0:
        listing.append('External files loaded: {0}'.format(n_external_files))

    listing.append('Number of passes executed: {0}'.format(n_passes))
    listing.append('Number of steps executed: {0}'.format(n_steps))
    time_end = timeit.default_timer()
    listing.append('Assembly time: {0:.5f} seconds'.format(time_end - time_start))

    if n_warnings != 0:
        listing.append('Warnings generated: {0}'.format(n_warnings))
    listing.append('Code origin: {0:06x}'.format(LC0))
    listing.append('Bytes of machine code: {0}'.format(code_size))

    # Code listing
    listing.append('\nLISTING:')
    listing.append('   Line  Status/Type State/Width Address     Bytes     Instruction')

    for line in src:

        try:
            l = line_listing_types[line.type](line)
        except KeyError:
            fatal(line, 'ERROR: Unknown line type "{0}" in line {1}:{2}'.\
                    format(line.type, line.ln, line.sec_ln))
        else:
            listing.append(listing_header(line) + l)


    # Add macro list
    listing.append('\nMACROS:')

    if len(macros) > 0:

        for m in macros.keys():
            listing.append('Macro "{0}"'.format(m))

            for ml in macros[m]:
                listing.append('    {0}'.format(ml.action))

    else:
        listing.append(INDENT+'(none)')


    # Only add symbol table if we have one already
    if symbol_table:

        listing.append('\nSYMBOL TABLE:')

        if len(symbol_table) <= 0:
            listing.append(' - (symbol table is empty)\n')

        # Find longest symbol name in table
        max_sym_len = max([len(k) for k in symbol_table.keys()])

        for v in sorted(symbol_table):
            listing.append('- {0:{width}} : {1:06x}'.format(v, symbol_table[v], width=max_sym_len))

    return listing




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

# Line numbers start with 1 because this is for humans. 

raw_source = []

with open(args.source, "r") as f:
    for ln, ls in enumerate(f.readlines(), 1): 
        line = CodeLine(ls.rstrip(), ln, 0)    # right strip gets rid of LF
        raw_source.append(line)

n_steps += 1
verbose('STEP LOAD: Read {0} lines from {1}'.\
        format(len(raw_source), args.source))


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
verbose('PASS COMMENTS: Found {0} full-line comment(s)'.format(n_comment_lines))


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

mnemonics = {opcode_table[n][1]:n for n, e in enumerate(opcode_table)}

# For the 6502 and 65c02, we have 'UNUSED' for the entries in the opcode table
# that are, well, not used. We get rid of them here. The 65816 does not have 
# any unused opcodes.
if MPU != '65816':
    del mnemonics['UNUSED']

n_steps += 1
verbose('STEP MNEMONICS: Generated mnemonics list')
verbose('- Number of mnemonics found: {0}'.format(len(mnemonics.keys())))


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
    # but we accept this gracefully for the moment and stick it to him later
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
        line.il_comment = rest_of_line.strip()
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
    comment = s.replace(non_comment, '').strip()
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

else:
    modes_source = relabeled_source


# -------------------------------------------------------------------
# PASS REP/SEP: Warn if there are any direct REP/SEP 
#
# Must come before we handle the register size switches. 

if MPU == '65816': 

    verbose('PASS REP/SEP: Check for naked rep/sep instructions')

    for line in modes_source:

        if line.type != INSTRUCTION:
            continue

        if line.action == 'rep' or line.action == 'sep':
            warning('"{0}" in line {1}, switch will not be recognized'.\
                    format(line.action, line.ln))
            warning('Use register size directives such as .A8 instead')

    n_passes += 1


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
            fatal(line, 'Malformed "{0}" instruction ("{1}")'.\
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

# TODO pretty format this
for m in macros.keys():
    verbose('Macro {0}:'.format(m))

    for ml in macros[m]:
        verbose('- {0:04}:{1:03} | {2} {3} | {4:11}|{5:11}|{6:11} {7}||'\
                .format(ml.ln, ml.sec_ln, ml.status, ml.type, ml.action,\
                ml.parameters, ml.il_comment, ml.raw))


# -------------------------------------------------------------------
# PASS INVOKE: Insert macro definitions
# 
# REQUIRES macros to have been defined

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
verbose('PASS INVOKE: {0} macro expansion(s), net {1} line(s) added'.\
        format(n_invocations, post_invok_len - pre_invok_len))


# -------------------------------------------------------------------
# PASS RENUMBER SECONDARY LINE NUMBERS
# 
# REQUIRES all includes to be finished
# REQUIRES all macros to be expanded 

# Different combinations of macros and includes can lead to strange secondary
# line numbers. Instead of trying to figure them out in the previous steps, we
# renumber them here before. This count starts with zero

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

ir_source = macro_source

   
# -------------------------------------------------------------------
# ASSERT INTERMEDIATE REPRESENTATION
#
# REQUIRES all lines to have been read, expanded and correctly numbered

# The Intermediate Representation (IR) ends the phase of preprocessing (parsing
# etc) and is the basis for the actually assembly. The source code has now
# reached its maximal number of line.

n_steps += 1
verbose('STEP: Intermediate Representation (IR) created with {0} lines of code'.\
        format(len(ir_source)))


# -------------------------------------------------------------------
# PASS: SAVE IR FILE 
#
# REQUIRES Intermediate Representation to have been generated

if args.ir: 

    with open(IR_FILE, 'w') as f:

        for l in make_listing(ir_source):
            f.write(l+'\n')

n_steps += 1
verbose('- IR saved to file {0}'.format(IR_FILE))


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
        fatal(line, '".origin" directive gives "{0}", not number as required')

    line.status = DONE
    break
        

n_steps += 1
verbose('STEP ORIGIN: Found ."origin" directive, starting code at {0:06x}'.\
        format(LC0))


# -------------------------------------------------------------------
# STEP END: Find .END directive

# End directive must be in the last line

s = ir_source[len(ir_source)-1]
sa = s.action.strip().lower() 

if sa != '.end':
    fatal(s, "Can't find '.end' directive in last line, found '{0}'".\
            format(s.raw))

s.status = DONE

n_steps += 1
verbose('STEP END: Found ".end" directive in last line, very good')


# -------------------------------------------------------------------
# PASS SIMPLE ASSIGN: Handle first round of basic assigments

# Handle the simplest form of assignments, those were a number is assigned to
# a variable ('.equ jack 1') or a symbol we already know ('.equ jill jack')
# without modifiers or math. We can't do full assignments until we've dealt with
# labels, but we can do this now to cut down on the number of lines we have to
# go through every time. 

for line in ir_source:

    if (line.status == DONE) or (line.action != ASSIGNMENT):
        continue 

    w = line.parameters.split()

    # We need exactly two parameters, the new symbol and the number or old
    # symbol it is to be assigned to
    if len(w) != 2:
        continue 

    vet_newsymbol(w[0])

    # In '.equ frog abc', 'abc' can either be a symbol or a number. We want it
    # to be a symbol by default, so we check the symbol table first
    try:
        r = symbol_table[w[1]]
    except KeyError:
        pass
    else:
        symbol_table[w[0].lower()] = r
        line.status = DONE
        continue

    f_num, r = convert_number(w[1])

    # If it's a number, add it to the symbol table, otherwise we'll have to wait
    # until we've figured out more stuff
    if f_num:
        symbol_table[w[0].lower()] = r
        line.status = DONE

n_passes += 1
verbose('PASS SIMPLE ASSIGN: Assigned {0} new symbol(s) to symbol table'.\
        format(len(symbol_table)))

# Print symbol table
if args.verbose:
    dump_symbol_table(symbol_table, "after SIMPLE ASSIGN (numbers in hex)")


# -------------------------------------------------------------------
# PASS REPLACE (1): Handle known assignments

# Note this does not touch symbols in .BYTE etc directives
replace_symbols(ir_source)

n_passes += 1

 
# -------------------------------------------------------------------
# PASS STRINGS: Convert strings to bytes and byte lists

# Strings are constants, so we can convert them very early on: Because we have
# gotten rid of comments, every quotation mark must belong to a string. We
# convert these strings to comma-separated byte lists 
# Example: "aaa" -> 61, 61, 61

# This method could also work for single-character strings in instructions such
# as 'lda.# "a"'. However, this could be source of errors because the assembler
# will happily also try to turn multi-character strings into byte lists in this
# instance as well ('lda.# "ab"' would become 'lda.# 61, 62'). Use 
# single-quotation marks for this, see next step.

p = re.compile('\".*?\"')

for line in ir_source:

    if line.status == DONE:
        continue 

    # Most lines won't have a string, so we skip them first
    if '"' not in line.parameters:
        continue 

    # The save directive may not have a string as a parameter
    if line.action == '.save':
        fatal(line, 'Found {0} in ".save" directive, may not be string'.\
                format(line.parameters))

    ma = p.findall(line.parameters)

    # Replace the contents of the strings with a comma-separated list of 
    # bytes
    for m in ma:

        # It is an error to use double quotation marks for a single
        # character, use 'a' instead, see next step
        if len(m) == 3:
            fatal(line,\
                    "Found single-character string {0}, use 'x' for chars".\
                    format(m))

        line.parameters = line.parameters.replace(m, string2bytestring(m))
        line.status = MODIFIED

n_passes += 1
verbose('PASS STRINGS: Converted all strings to byte lists')


# -------------------------------------------------------------------
# PASS CHARS: Convert single characters delimited by single quotes

# Since characters are constants, we can convert them early on Single characters
# are put in single quotes ('a'). This step must come after the conversion of
# strings to make sure that we don't accidently find single characters that are
# part of a string.

p = re.compile("\'.\'")

for line in ir_source: 
    
    # We usually don't have a single quote in a line so we get rid of that
    # immediately
    if "'" not in line.parameters:
        continue

    ma = p.findall(line.parameters)

    # Replace each instance of a single-quoted string with the string of its
    # hex number. Note that ord() returns unicode, but we currently slice off 
    # anything that is not the last two hex digits
    for m in ma:
        line.parameters = line.parameters.replace(m, hexstr(2, ord(m[1])))
        line.status = MODIFIED

n_passes += 1
verbose('PASS CHARS: Converted all single characters to bytes')


# -------------------------------------------------------------------
# PASS REGISTER SWITCHES: Add size of registers to lines for 65816
#
# REQUIRES all register size directives turned into asserts
# ASSUMES no naked rep/sep instructions in code

# For the 65816, see where we have rep/sep register size switches and add the
# size we think A, X, and Y have to the line data. We do not recognize the
# rep/sep instructions directly, but only the assert directives, so when we get
# here, we should have checked to make sure there are no naked sep/rep in code
# and that all .A8 etc have been changed to .!A8

# TODO Rewrite this with cleaner IF logic

if MPU == '65816':

    # Keep these variables in this pass
    current_xy_width = 8  
    current_a_width = 8
    current_mode = 'em'

    register_asserts = ['.!a8', '.!a16', '.!xy8', '.!xy16', '.!axy8',\
            '.!axy16']


    for line in ir_source: 

        # We walk though all lines, not only instructions, which is probably
        # paranoid
        
        if line.action == '.!native':
            current_mode = 'na'
            line.status = DONE

        elif line.action == '.!emulated':
            current_mode = 'em'
            current_a_width = 8
            current_xy_width = 8
            line.status = DONE

        elif line.action in register_asserts:

            line.status = DONE
            n_switches += 1

            if line.action[-1] == '8':
                size = 8
            else:
                size = 16

            if 'a' in line.action: 
                current_a_width = size

            if 'xy' in line.action: 
                current_xy_width = size

        line.mode = current_mode
        line.a_width = current_a_width
        line.xy_width = current_xy_width

    n_passes += 1
    verbose('PASS REGISTER SWITCHES: Found {0} A/XY width change(s)'.\
            format(n_switches))
        
 
# -------------------------------------------------------------------
# PASS LABELS - Construct symbol table by finding all labels

# This is the equivalent of the traditional "Pass 1" in normal two-pass
# assemblers. 

def lc_offset(register_width):
    """For the 65816, convert the register width of A or XY to the byte
    offset that must be added during assembly for the immediate
    instructions.
    """
    return (register_width-8)//8


BRANCHES = ['bra', 'beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
           'bra.l', 'phe.r']

# These are only used for 65816. The offsets are used to calculate if an extra
# byte is needed for immediate forms such as lda.# with the 65816
A_IMM = ['adc.#', 'and.#', 'bit.#', 'cmp.#', 'eor.#', 'lda.#', 'ora.#', 'sbc.#']
XY_IMM = ['cpx.#', 'cpy.#', 'ldx.#', 'ldy.#']

verbose('PASS LABELS: Assigning value to all labels')

for line in ir_source: 

    if line.status == DONE:
        continue


    # --- SUBSTEP CURRENT: Replace the CURRENT symbol by current address ---
    # This must come before we handle mnemonics

    if CURRENT in line.parameters:
        LC = LC0 + LCi
        line.parameters = line.parameters.replace(CURRENT, hexstr(6, LC))
        line.status = MODIFIED

        verbose('- Current line marker in line {0} replaced with {1}'.\
                format(line.ln, hexstr(6, LC)))


    # --- SUBSTEP MNEMONIC: See if we have a mnemonic ---

    # Because we are using Typist's Assembler Notation and every mnemonic
    # maps to one and only one opcode, we don't have to look at the operand of
    # the instruction at all, which is a lot simpler

    if line.action in mnemonics:

        line.address = LC0+LCi
        line.status = MODIFIED
        line.size = opcode_table[mnemonics[line.action]][2]

        # Add extra byte according to register size for 65816
        # immediate instructions such as lda.#
        if MPU == '65816':

            if line.action in A_IMM:
                line.size += lc_offset(line.a_width)
            elif line.action in XY_IMM:
                line.size += lc_offset(line.xy_width)


        LCi += line.size
        continue


    # --- SUBSTEP SKIP: Convert .skip directive to zero bytes ---

    # This is the first step where we save final bytes

    if line.action == '.skip':

        # Number of bytes to be skipped should be in parameter
        r = convert_term(line, line.parameters)

        # We save r zeros (initialize skipped space)
        line.bytes = ' '.join(['00']*r)
        line.size = r
        line.status = DONE
        line.address = LC0+LCi

        verbose('- Converted ".skip" in line {0} to {1} zero byte(s)'.\
                format(line.ln, r))

        LCi += line.size
        continue

 
    # --- SUBSTEP SAVE: Convert .save directive to zero bytes ---
    
    # TODO see if we need to add a label line here

    if line.action == '.save':

        ws = line.parameters.split()

        # Add the symbol to the symbol list. This should be the first word of
        # the parameter string
        vet_newsymbol(ws[0])
        symbol_table[ws[0].lower()] = LC0+LCi

        # Number of bytes to save should be the second entry in the parameter
        # string
        r = convert_term(line, ws[1])

        # We save r zeros (initialize reserved space)
        line.bytes = ' '.join(['00']*r)
        line.size = r
        line.status = DONE
        line.address = LC0+LCi
        
        verbose('- Converted ".save" in line {0} to {1} zero byte(s)'.\
                    format(line.ln, r))
        LCi += line.size
        continue


    # --- SUBSTEP ADVANCE: See if we have the .advance directive ---
    
    if line.action == '.advance':

        line.address = LC0+LCi
        r = convert_term(line, line.parameters)

        # Make sure the user is not attempting to advance backwards
        if r < line.address:
            fatal(line, 'Negative ".advance" (you can never go back)')

        # While we're here, we might as well already convert this to .byte
        offset = r - line.address
        line.bytes= ' '.join(['00']*offset)
        line.size = offset
        line.status = DONE

        verbose('- Converted ".advance" in line {0} to {1} zero byte(s)'.\
                format(line.ln, offset))
        LCi += line.size
        continue


    # --- SUBSTEP LABELS: Figure out where our labels are ---

    if line.type == LABEL:

        line.address = LC0+LCi

        # Local (anonymous) labels are easiest, start with them first
        if line.action == LOCAL_LABEL:
            anon_labels.append((line.ln, line.address))
            line.status = DONE
            verbose('- New anonymous label found in line {0}, address {1:06x}'.\
                    format(line.ln, line.address))
            continue

        # This must be a real label. If we don't have it in the symbol table,
        # all is well and we add a new entry
        if line.action not in symbol_table:
            verbose('- New label "{0}" found in line {1}, address {2:06x}'.\
                    format(line.action, line.ln, line.address))
            symbol_table[line.action.lower()] = line.address
            line.status = DONE
            continue

        # If it is already known, something went wrong, because we can't
        # redefine a label, because that gets really confusing very fast
        else:
            fatal(line, 'Attempt to redefine symbol "{0}" in line {1}'.\
                    format(line.action, line.ln))


    # --- SUBSTEP DATA: See if we were given data to store ---
    
    # We don't convert the instructions at this point, but just count their
    # bytes. Note these entries are not separated by spaces, but by commas

    if line.action in DATA_DIRECTIVES:

        line.address = LC0+LCi
        line.status = MODIFIED

        # Make sure there is no trailing comma, or the split will produce an
        # extra empty entry in the list, throwing our count off. We only catch
        # one comma. We've already converted all strings and characters so we
        # don't have to be worried we'll get one of those by mistake
        p = line.parameters.strip()

        if p[-1] == ',':
            p = p[:-1] 

        # We're just interested in the number of parameters right now
        np = len(p.split(','))

        # .BYTE stores one byte per comma-separated word
        if line.action == '.byte':
            line.size = np 

        # .WORD stores two bytes per comma-separated word
        elif line.action == '.word':
            line.size = 2*np
 
        # .LONG stores three bytes per comma-separated word
        elif line.action == '.long':
             line.size = 3*np
 
        LCi += line.size
        continue

n_passes += 1


# -------------------------------------------------------------------
# PASS ASSIGN: Handle complex assignments

# Complete all .equ statements

for line in ir_source:

    if (line.status == DONE) or (line.action != ASSIGNMENT):
        continue

    w = line.parameters.split(' ', 1)
    vet_newsymbol(w[0])

    # In '.equ frog abc', 'abc' can either be a symbol or a number. We want it
    # to be a symbol by default, so we check the symbol table first
    try:
        r = symbol_table[w[1]]
    except KeyError:
        pass
    else:
        symbol_table[w[0]] = r
        line.status = DONE
        continue

    rs = convert_term(line, w[1])

    # If it's a number, add it to the symbol table, otherwise we'll have to wait
    # until we've figured out more stuff
    if f_num:
        symbol_table[w[0]] = rs
        line.status = DONE

n_passes += 1
verbose('PASS ASSIGN: Assigned all remaining symbol(s) to symbol table')

# Print symbol table
if args.verbose:
    dump_symbol_table(symbol_table, "after ASSIGN (numbers in hex)")


# -------------------------------------------------------------------
# PASS REPLACE (2): Handle known assignments

# At this point, we still haven't handled symbols in .BYTE etc directives
replace_symbols(ir_source)

n_passes += 1


# -------------------------------------------------------------------
# CLAIM: At this point we should have all symbols present and known in the
# symbol table, and anonymous labels in the anonymous label list

verbose('CLAMING that all symbols should now be known')


# -------------------------------------------------------------------
# PASS DATA: Convert various data formats like .byte

# Converts all .byte, .word and .long lines. We also allow .long for the 8-bit
# MPUs though they might be of little use

# TODO see what happens if there is a local (anon) label in the data directive

for line in ir_source:

    if (line.status == DONE) or (line.action not in DATA_DIRECTIVES):
        continue

    # Make sure there is no trailing comma, or the split will produce an
    # extra empty entry in the list, throwing our count off. We only catch
    # one comma. We've already converted all strings and characters so we
    # don't have to be worried we'll get one of those by mistake
    p = line.parameters.strip()

    if p[-1] == ',':
        p = p[:-1] 

    # We work with a list of terms
    ts = (p.split(','))
    new_ts = []

    for t in ts: 
        new_ts.append(convert_term(line, t))

    # We now have a list of the numbers, but need to break them down into
    # their bytes. This could be solved a lot more elegantly, but this is
    # easier to understand
    byte_list = []

    if line.action == '.byte':
        byte_list = new_ts

    elif line.action == '.word':
        for n in new_ts:
            for b in little_endian_16(line, n):
                byte_list.append(b)

    elif line.action == '.long':
        for n in new_ts:
            for b in little_endian_24(line, n):
                byte_list.append(b)


    # Reassemble the datastring, now without commas
    line.bytes = ' '.join([hexstr(2, b) for b in byte_list])
    line.status = DONE
    line.size = len(byte_list)

n_passes += 1
verbose('PASS DATA: Converted all data formats to .byte lists')


# -------------------------------------------------------------------
# PASS MATH

# Replace all math terms that are left in the text, eg 'jmp { label + 2 }'. 
# None of these should be in assignments any more, and none of them should be in
# data directives

for line in ir_source:

    if line.status == DONE:
        continue

    # We've gotten rid of all strings and characters so we don't have to worry
    # about them containing a LEFTMATH
    if LEFTMATH not in line.parameters:
        continue

    # More than one math term, so we have to do this the hard way
    while LEFTMATH in line.parameters:
        line.parameters = do_math(line.parameters)

    line.status = MODIFIED
    
n_passes += 1
verbose('PASS MATH: replaced all math terms by numbers')


# -------------------------------------------------------------------
# PASS MODIFY

# Replace all modify terms that are left in the text, eg 'lda.# .msb 1000'. 
# None of these should be in assignments any more

def has_modifier(s):
    """Given a string with space-separated words, return True if one of 
    these words is a modifier, else false.
    """
    return bool([i for i in MODIFIERS if i in s])


for line in ir_source:

    if line.status == DONE:
        continue

    if has_modifier(line.parameters):
        
        # We need to use next entry once we find a modifier, so we need to make
        # this iterable
        new_p = ""
        ws = iter(line.parameters.split())

        for w in ws:

            if w in MODIFIERS:
                f_num, r = convert_number(next(ws))

                if f_num:
                    w = hexstr(6, MODIFIERS[w](line, r))
                else: 
                    fatal(line.ln, 'Modifier operand "{0}" not a number'.format(w))

            new_p = new_p + ' ' + w
             
        line.paramenters = new_p
        line.status = MODIFIED

n_passes += 1
verbose('PASS MODIFY: replaced all modifier terms by numbers')


# -------------------------------------------------------------------
# PASS ANONYMOUS: Replace all anonymous label references by correct numbers

# We don't modify anonymous labels or do math on them. All strings and
# characters are taken care of, as all math terms, so the only '+' and '-' in
# the code should be in local (anonymous) label jumps

# TODO figure out what happens if there is a local label in a data directive, we
# might have to move this pass up

for line in ir_source:

    if (line.status == DONE) or (line.type != INSTRUCTION):
        continue

    if line.parameters.strip() == '+':   # strip() is paranoid
        for ln, ll in anon_labels:

            if ln > line.ln:
                line.parameters = hexstr(6, ll)
                line.status = MODIFIED
                break

    if line.parameters.strip() == '-':   # strip() is paranoid
        for ln, ll in reversed(anon_labels):

            if ln < line.ln:
                line.parameters = hexstr(6, ll)
                line.status = MODIFIED
                break

n_passes += 1
verbose('PASS ANONYMOUS: Replaced all anonymous labels with address values')


# -------------------------------------------------------------------
# CLAIM: At this point we should have completely replaced all labels and
# symbols with numerical values.

verbose('CLAMING there should be no labels or symbols left in the source')


# -------------------------------------------------------------------
# PASS 1BYTE: Convert all single-byte instructions to .byte directives

# Low-hanging fruit first: Compile the opcodes without operands

for line in ir_source:

    if (line.status == DONE) or (line.type != INSTRUCTION):
        continue

    try:
        oc = mnemonics[line.action]
    except KeyError:
        continue 
    else:

        if opcode_table[oc][2] == 1:    # look up length of instruction
            line.bytes = hexstr(2, oc)
            line.status = DONE

n_passes += 1
verbose('PASS SINGLE BYTE: Assembled all single byte instructions')


# -------------------------------------------------------------------
# PASS BRANCHES: Assemble branch instructions

# Keep this definition in the branches pass
BRANCHES = {
    '6502': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs'],\
    '65c02': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
        'bra'],\
    # We keep bra.l in this list though we filter it out beforehand
    '65816': ['beq', 'bne', 'bpl', 'bmi', 'bcc', 'bcs', 'bvc', 'bvs',\
        'bra', 'bra.l', 'phe.r']}


for line in ir_source: 

    if (line.status == DONE) or (line.type != INSTRUCTION):
        continue

    # We treat this as a special case. Check for MPU so we don't suddenly allow
    # a 6502 to do a long branch
    if (line.action == 'bra.l') and (MPU == '65816'):
        _, target_addr = convert_number(line.parameters)
        bl, bm = little_endian_16(line, target_addr - line.address - 3)
        opr = hexstr(2, bl)+' '+hexstr(2, bm)
        line.bytes = hexstr(2, mnemonics[line.action])+' '+opr
        line.status = DONE
        continue
   
    if line.action in BRANCHES[MPU]:
        _, target_addr = convert_number(line.parameters)
        opr = hexstr(2, lsb(line, target_addr - line.address - 2))
        line.bytes = hexstr(2, mnemonics[line.action])+' '+opr
        line.status = DONE
        continue

n_passes += 1
verbose('PASS BRANCHES: Encoded all branch instructions')


# -------------------------------------------------------------------
# PASS FUSE MOVE: Reassemble and convert move instructions

# All move instructions should have been split up and their operands converted.
# We now put them back together, remembering that destination comes before
# source in the machine code of MVN and MVP

if MPU == '65816':

    # We need to be able to skip ahead in the list so we have to use an iter
    # object in this case
    l = iter(ir_source)

    for line in l: 

        if (line.action == 'mvp') or (line.action == 'mvn'):

            # Handle source byte
            _, r = convert_number(line.parameters)
            src = hexstr(2,r)

            # Handle opcode
            line.bytes = str(mnemonics[line.action])

            # Handle destination byte
            nl = next(l)
            _, r = convert_number(nl.parameters)
            des = hexstr(2,r)
            nl.status = DONE

            # Put it all together
            line.bytes = line.bytes + ' ' + des + ' ' + src
            line.status = MODIFIED

    n_passes += 1
    verbose('PASS FUSE MOVE: Handled mvn/mvp instructions on the 65816')


# -------------------------------------------------------------------
# PASS ALL IN: Assemble all remaining operands

verbose('PASS ALL IN: Assembling all remaining operands')

for line in ir_source:

    if (line.status == DONE) or (line.type != INSTRUCTION):
        continue 

    # We already have some instructions that have been converted to .bytes
    try:
        oc = mnemonics[line.action]
    except KeyError:
        continue

    opr = convert_term(line, line.parameters)

    # We hand tuples to the next step
    if line.size == 2:
        bl = (lsb(line, opr), )
    elif line.size == 3:
        bl = little_endian_16(line, opr)
    elif line.size == 4:
        bl = little_endian_24(line, opr)
    else:
        # This should never happen, obviously, but we're checking anyway
        fatal(line, 'Found {0} byte instruction in opcode list'.\
                format(line.size))

    # Reassemble payload as a byte instruction
    line.bytes = hexstr(2, oc) + ' ' + ' '.join([hexstr(2, i) for i in bl])
    line.status = DONE

n_passes += 1


# -------------------------------------------------------------------
# PASS VALIDATE: Make sure we're really done  

for line in ir_source:

    if line.status != DONE:
        fatal(line, 'There is something strange and unknown in line "{0}"'.\
                format(line.ln))

n_passes += 1
verbose('PASS VALIDATE: Confirmed that all lines are done')


# -------------------------------------------------------------------
# PASS BYTE CHECK: Make sure all byte values are valid bytes

for line in ir_source:

    if not line.bytes: 
        continue

    bl = line.bytes.split()

    for b in bl:

        f_num, r = convert_number(b)

        if not f_num:
            fatal(line, 'Found non-number "{0}" in byte list'.format(b))

        if r > 0xff or r < 0:
            fatal(line, 'Value "{0}" refuses to fit into one byte'.format(b))

n_passes +=1
verbose('PASS BYTE CHECK: Confirmed all byte values are in range from 0 to 255')


# -------------------------------------------------------------------
# PASS OPTIMIZE: Analyze and optimize code

# We don't perform automatic optimizations at the moment, but only provide
# suggestions and warnings here. We need the line numbers so we can offer
# the user suggestions based on his original source code

verbose('PASS ANALYZE: Searched for obvious errors and improvements')

for line in ir_source: 

    if not line.bytes:
        continue

    if line.type == INSTRUCTION: 

        # --- SUBSTEP WDM: Check to see if we have WDM instruction --- 
        ws = line.bytes

        if w[0] == '42':
            warning('Reserved instruction WDM (0x42) found in line {0}'.\
                    format(line.ln))
            continue

n_passes += 1


# -------------------------------------------------------------------
# PASS BINARY: Convert lists of bytes into one byte array

# Take all lines that are not DONE and write their values to 

byte_list = []

for line in ir_source:

    if not line.bytes: 
        continue 

    line.bytes = line.bytes.strip()     # paranoid 
    bl = [int(b, 16) for b in line.bytes.split()]
    byte_list.extend(bl)
    
objectcode = bytes(byte_list)
code_size = len(objectcode)

n_passes += 1
verbose('PASS BINARY: Combined byte lists to {0} bytes of final code'.\
        format(len(objectcode)))


# -------------------------------------------------------------------
# STEP SAVEBIN: Save binary file

with open(args.output, 'wb') as f:
    f.write(objectcode)

n_steps += 1
verbose('STEP SAVE BINARY: Saved object code as {0}'.\
        format(args.output))


# -------------------------------------------------------------------
# STEP S28: Create S28 date file if requested

# The Motorola S-Record file format is described at
# https://en.wikipedia.org/wiki/SREC_(file_format) with further discussions at 
# http://www.s-record.com/ and http://srecord.sourceforge.net/ A handy chart is
# https://upload.wikimedia.org/wikipedia/commons/f/f1/Motorola_SREC_Chart.png

if args.s28:
    
    from binascii import unhexlify

    # Keep these definitions here

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


    # We could just hard-code the data string but that would make it
    # harder for other people to modify the code
    data_string = 'https://github.com/scotws/tinkasm'
    s0_line = make_s0(data_string)
    s8_line = make_s8(LC0)

    with open(S28_FILE, 'w') as f:
        f.write(s0_line+'\n')

        h_data = ''

        for c in objectcode:
            h_data = h_data+'{0:02x}'.format(c)

        t = h_data
        a = LC0

        while t:
            f.write(make_s2(t[:64], a)+'\n')
            t = t[64:]
            a += 32

        f.write(s8_line+'\n')

    n_steps += 1
    verbose('STEP S28: Saved Motorola S-Record file {0} as requested'.\
            format(S28_FILE))


# -------------------------------------------------------------------
# STEP HEXDUMP: Create hexdump file if requested

if args.hexdump:

    with open(HEX_FILE, 'w') as f:
        f.write(TITLE_STRING)
        f.write('Hexdump file of {0}'.format(args.source))
        f.write(' (total of {0} bytes)\n'.format(code_size))
        f.write('Generated on {0}\n\n'.\
                format(time.asctime(time.localtime())))
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
    verbose('STEP HEXDUMP: Saved hexdump file {0} as requested'.\
            format(HEX_FILE))


# -------------------------------------------------------------------
# STEP LIST: Create listing file if requested

if args.listing:

    n_steps += 1

    with open(LIST_FILE, 'w') as f:
        for l in make_listing(ir_source):
            f.write(l+'\n') 

    verbose('STEP LIST: Saved listing as {0}'.format(LIST_FILE))


# -------------------------------------------------------------------
# STEP PRINT: Print listing to screen if requested

if args.print: 

    n_steps += 1
    print () 

    for l in make_listing(ir_source):
        print(l)

    print()
    verbose('STEP LIST: Saved listing as {0}'.format(LIST_FILE))


# -------------------------------------------------------------------
# STEP END: Sign off

time_end = timeit.default_timer()
verbose('\nSuccess! All steps completed in {0:.5f} seconds.'.\
        format(time_end - time_start))
verbose('Enjoy your cake.')
sys.exit(0)

### END ###

