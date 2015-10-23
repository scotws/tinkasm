# #!/usr/bin/env python3
# A Typist's Assembler for the 65816 in Forth 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 22. Oct 2015

# TODO License



### SETUP ### 

import argparse
import pickle 
# import shlex        # https://docs.python.org/3/library/shlex.html
import sys

symbol_table = {}

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True, 
        help='Assembler source code file')
parser.add_argument('-o', '--output', dest='output', 
        help='Binary output file', default='tasm.bin')
parser.add_argument('-l', '--listing', dest='listing', 
        help='Human-readable code listing', default='tasm.txt')
parser.add_argument('-v', '--verbose', 
        help='Display each step as it is happening', action='store_true')
parser.add_argument('-d', '--dump', 
        help='Dump content of each inbetween step', action='store_true')
parser.add_argument('-c', '--opcodes', dest='opcodes', 
        default='opcodes65816.pickle', help='Opcode table, default for 65816') 
args = parser.parse_args()

### OUTPUT FUNCTIONS ###

def verbose(s):
    """Print information string given if --verbose flag was set. Later 
    expand this by the option of priting to a log file instead."""
    if args.verbose:
        print('STEP', s)

def dump(l):
    """At each assembly stage, print the complete stage as a list. Produces
    an enormous amount of output, probably only interesting for debugging."""
    if args.dump:
        for line in l:
            print(line)

def symbols():
    """Dump symbol table if dump argument was given"""
    if args.dump:
        for s in sorted(symbol_table):
            print("Symbol", s, ":", symbol_table[s]) 


### CONSTANTS ###

ASSIGN = "="        # Change this to " equ " or whatever 
COMMENT = ';'       # Change this for a different comment marker 


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


### MULTI-PASS ASSEMBLER ###

# The assembler works by connecting as many little steps as possible (see the 
# Manual for details). Each step is given a title such as RAW, and all
# requirements for that step are kept close to the actual processing. 

# Note we don't process lists of code, but lists of tuples which consist of
# the original line number and a line of code as a string. That way, we can
# always reference the original line number at each stage. 

# TODO Print banner if verbose 


# --- Step RAW: Import original code and add line numbers ---

# Line numbers start with 1 because this is for humans

with open(args.source, "r") as f:
    sc_raw = list(enumerate(f.readlines(),1))

verbose('RAW: Read {0} lines from {1}'.format (len(sc_raw), args.source))
dump(sc_raw) 


# --- Step EMPTY: Remove empty lines ---
# TODO keep empty lines in separate list to reconstruct listing file

sc_empty = []

for l in sc_raw:
    if l[1].strip():
        sc_empty.append(l) 

verbose('EMPTY: Removed {0} empty lines'.format(len(sc_raw)-len(sc_empty)))
dump(sc_empty) 


# --- Step COMMENTS: Remove comments that span whole lines ---
# TODO keep comment lines in separate list to reconstruct listing file

sc_comments = []

for l in sc_empty:
    if l[1].strip()[0] != COMMENT :
        sc_comments.append(l) 

verbose('COMMENTS: Removed {0} full-line comments'.format(len(sc_empty)-len(sc_comments)))
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

verbose('INLINES: Removed all inline comments') 
dump(sc_inlines) 

    
# --- Step MACROS: Define macros ---
# TODO code this 

verbose('MACROS: Defined 0 macros (DUMMY, not coded yet)')
# TODO add dump 


# --- STEP EXPAND: Expand macros in source code --- 
# TODO code this 

sc_expand = sc_inlines

verbose('EXPAND: Expanded 0 macros (DUMMY, not coded yet)')
dump(sc_expand) 


# --- Step LOWER: Convert everything to lower case ---

sc_lower = [(n, l.lower()) for n, l in sc_expand] 
verbose('LOWER: Converted all remaining code to lower case')
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

verbose('ORIGIN: Found ORIGIN directive, setting LC to {0}'.format(originline[1]))
dump(sc_origin) 


# --- Step END: Make sure we have an END directive --- 

endline = sc_origin[-1][1].strip().split() 

if endline[0] != "end":
    fatal(sc_origin[0][0], 'No END directive found') 

sc_end = sc_origin[:-1]

verbose('END: Found END directive in last line') 
dump(sc_end) 


# --- Step ASSIGN: Handle the clear assignment lines ---

if args.verbose:
    print('Initializing symbol table') 

sc_assign = []

for n, l in sc_end:
    if ASSIGN in l: 
        s, v = l.split(ASSIGN)
        symbol = s.split()[-1] 
        value = number2int(v.split()[0])
        symbol_table[symbol] = value  
    else: 
        sc_assign.append((n, l))

verbose('ASSIGN: Assigned {0} symbols to symbol table'.format(len(sc_end)-len(sc_assign))) 
dump(sc_assign) 
symbols() 


# --- Step PASS1: Create Intermediate File ---

intermediate_file = []

# Load opcodes. The opcode routines are kept in a common file, regardless of
# which processor we use, the opcode tables are by processor type. 

# TODO make this more general with importlib, get rid of *
from opcode_routines import * 

# Load opcode table 
with open(args.opcodes, 'rb') as f:
    opcode_table = pickle.load(f) 

if args.verbose: 
    print('Loaded opcode table {0}'.format(args.opcodes))


# HIER HIER 



####################################################


### BASIC DATA STRUCTURES ###

# Source file seems legit, now load everything else

directive_list = ['advance', 'a:8', 'a:16', 'xy:8', 'xy:16', 'axy:8',\
        'axy:16', 'b', 'w', 'lw', 'emulated', 'end', 'include', 'macro',\
        'mend', 'native', 'origin', 'str', 'str0', 'strlf', 'lsb', 'msb',\
        'bank']

LC = 0 



### DIRECTIVES ###

def d_advance(addr65): 
    "Advance to address given, filling up space inbetween with zeros"
    print ("ADVANCE not coded yet")

def d_a8():
    "Switch Accumulator size to 8 bits. Assumes Native Mode."
    print ("A:8 not coded yet")

def d_include(filename):
    "Include source code from external file."
    print ("INCLUDE not coded yet")

def d_end(): 
    "Mark end of assembly text. Required." 
    print ("END not coded yet") 

def d_origin(addr65): 
    "Set origin of assembly. Also marks end of macro section. Required."
    print ("ORIGIN not coded yet") 

directives = {'advance': d_advance, 'a:8': d_a8, 'include': d_include,\
        'end': d_end, 'origin': d_origin} 

directives_list = list(directives.keys())

def is_directive(s):
    "See if string is a valid mnemonic. Returns boolian."
    if s in directives_list:
        return True 
    else:
        return False



### OPCODES ###

# Generate full list of mnemonics from opcode table automatically
mnemonics = {}

for o in opcode_table: 
    mnemonics[o[1]] = o[0]

mnemonic_list = list(mnemonics.keys())

# See if this is redundant because we use TRY/EXCEPT structure
def is_mnemonic(s):
    "See if string is a valid mnemonic. Returns boolian."
    if s in mnemonic_list:
        return True 
    else:
        return False

def opcode(s): 
    "Return opcode when given lowercase mnemonic."
    return mnemonics[s]
        
def opcode_data(opc):
    "Given an opcode, retrieve tuple for that instruction from opcode_table"
    return opcode_table[opc] 

def opcode_length(opc): 
    "Return length of complete instruction (opcode and operand) in bytes"
    return opcode_data(opc)[2]




### END ###
sys.exit(0) 

