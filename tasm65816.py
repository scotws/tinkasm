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





## TODO TESTING routines 
print(" --- ") 
print(work_source) 



### PARSING STEPS ###

# Pass 0 : Macros (must be defined before ORIGIN line)
print ("Pass 0: Macros")


# Pass 1 : Symbols, create Symbol Table and Intermediate File
print ("Pass 1: Generating Symbol Table") 


# Pass 1.5 : Embedded Python Code
print ("Pass 1.5: Running embedded Python Code") 


# Pass 2 : Assemble binary file, create listing file
print ("Pass 2: Assembling binary file, creating listing file")


### END ###
sys.exit(0) 

