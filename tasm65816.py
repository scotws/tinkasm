# #!/usr/bin/env python3
# A Typist's Assembler for the 65816 in Forth 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 24. Sep 2015
# This version: 20. Oct 2015

# TODO License



### SETUP ### 

import argparse
import shlex        # https://docs.python.org/3/library/shlex.html
import sys

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True, 
        help='Assembler source code file')
parser.add_argument('-o', '--output', dest='output', 
        help='Binary output file', default='tasm.bin')
parser.add_argument('-l', '--listing', dest='listing', 
        help='Human-readable code listing', default='listing.txt')
args = parser.parse_args()


### IMPORTING SOURCE FILE ###

# import raw source file 
with open(args.source, "r") as f:
    pure_source = f.read()

# clean up raw source file 
work_source = pure_source.strip()

# Must have ORIGIN and END directives
if 'origin' not in work_source: 
    print ("FATAL: No 'origin' directive found in source code.") 
    sys.exit(1) 

if 'end' not in work_source: 
    print ("FATAL: No 'end' directive found in source code.") 
    sys.exit(1) 


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


### OPCODES ###

# Opcode special routines. These are called during assembly of the opcode
# becasuse special treatment or checks are required

def ocs_brk():
    "Check brk instruction to make sure that extra byte is provided."
    print ("Special routine for BRK not coded yet") 

def ocs_cop():
    "Check cop instruction to make sure that extra byte is provided."
    print ("Special routine for COP not coded yet") 

def ocs_wdm():
    "Warn user that wdm instruction is being assembled"
    print ("Special routine for WDM not coded yet") 

def ocs_stack0():
    "Warn user that Stack Addressing Mode has operand 0"
    print ("Warning for Stack Addressing with operand 0 not coded yet") 



# Entries in the opcode table are tuples (immutable) of opcode, length in 
# bytes, number of operands, special routines to execute

# TODO load these from an external file 

opcode_table = (
        (0x00, 'brk', 1, 0, ocs_brk),
        (0x01, 'ora.dx', 2, 1, None),
        (0x02, 'cop', 2, 1, ocs_cop),
        (0x03, 'ora.s', 2, 1, ocs_stack0 ),
        (0x04, 'tsb.d', 2, 1, None ),
        (0x05, 'ora.d', 2, 1, None )) 
        
def opcode_entry(opcode):
    "Given an opcode, retrieve tuple for that instruction from opcode_table"
    return opcode_table[opcode] 


### PARSING STEPS ###

# Pass 0 : Macros (must be defined before ORIGIN line)
print ("Pass 0: Macros (NON-FUNCTIONAL IN PRE-ALPHA)")

# Handle INCLUDE 


# Pass 1 : Symbols, create Symbol Table and Intermediate File
print ("Pass 1: Generating Symbol Table") 


# Pass 1.5 : Embedded Python Code
print ("Pass 1.5: Running embedded Python Code (NON-FUNCTIONAL IN PRE-ALPHA)") 

# Creates intermediate file 

# Pass 2 : Assemble binary file, create listing file
print ("Pass 2: Assembling binary file, creating listing file")

### TODO TESTING TODO ###

print ("---")
print (work_source) 


### END ###
sys.exit(0) 

