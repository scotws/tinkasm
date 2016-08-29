# A Formatter for the Tinkerer's Assembler 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 27. Aug 2016
# This version: 29. Aug 2016

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

"""TinkFmt is a formatting program for assembler source code that was 
written for the Tinkerer's Assembler for the 6502/65c02/65816. Based on
the idea behind Go's gofmt program, it strives to make sure all Tinkerer
source code is formatted the same. This makes it easier to understand
the logic. See the README.md file for more details and a discussion
of the basic rules.
"""

### SETUP ###

import argparse
import os
import re
import string
import sys


# Check for correct version of Python
if sys.version_info.major != 3:
    print("FATAL: Python 3 required. Aborting.")
    sys.exit(1)


### CONSTANTS AND VARIABLES

TITLE_STRING = \
"""A Formatter for the Tinkerer's Assembler for the 6502/65c02/65816
Version BETA  28. August 2016
Copyright 2015, 2016 Scot W. Stevenson <scot.stevenson@gmail.com>
This program comes with ABSOLUTELY NO WARRANTY
"""

INDENT_SIZE = 8 
INDENT = ' '*INDENT_SIZE
SUPPORTED_MPUS = ['6502', '65c02', '65816']
DATA_DIRECTIVES = ['.byte', '.word', '.long']

DIRECTIVES = ['.!a8', '.!a16', '.a8', '.a16', '.origin', '.axy8', '.axy16',\
        '.end', '.equ', '.byte', '.word', '.long', '.advance', '.skip',\
        '.native', '.emulated', '.!xy8', '.!xy16', '.xy8', '.xy16', ';',\
        '.lsb', '.msb', '.bank', '.lshift', '.rshift', '.invert', '.and',\
        '.or', '.xor', '.*', '.macro', '.endmacro', '.invoke', '.mpu',\
        '.include', '.!native', '.!emulated', '{', '}']

sc_out = []


### HELPER FUNCTIONS

def fatal(n, s):
    """Abort program because of fatal error during assembly.
    """
    print('FATAL ERROR in line {0}: {1}'.format(n, s))
    sys.exit(1)


def verbose(s): 
    """Print information string given if --verbose flag was set.
    Later expand this by the option of priting to a log file instead.  
    """ 
    if args.verbose:
        print(s)



### PARSE INPUT

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True,\
                help='Assembler source code file (required)')
parser.add_argument('-t', '--test',\
                help="Test run, don't change files, just print", action='store_true')
parser.add_argument('-v', '--verbose',\
                help='Display additional information', action='store_true')
args = parser.parse_args()


### GENERAL SETUP

verbose(TITLE_STRING)

with open(args.source, "r") as f:
        sc_in = list(enumerate(f.readlines(), 1))

verbose('Read {0} lines from {1}'.format(len(sc_in), args.source))


### PROCESSOR SETUP
MPU = ""

for num, line in sc_in:
    if '.mpu' in line.lower():
        MPU = line.split()[1].strip()

if not MPU:
    fatal(num, 'No .mpu directive found, target CPU unknown.')

if MPU not in SUPPORTED_MPUS:
    fatal(num, 'MPU "{0}" not supported'.format(MPU))

verbose('Found CPU type {0}'.format(MPU))

if MPU == '6502':
    from opcodes6502 import opcode_table
elif MPU.lower() == '65c02':
    from opcodes65c02 import opcode_table
else:
    from opcodes65816 import opcode_table

# Paranoid: Make sure we were given the right number of opcodes
if len(opcode_table) != 256:
    fatal(0, 'Opcode table contains {0} entries, not 256'.format(len(opcode_table)))

MNEMONICS = {opcode_table[n][1]:n for n, e in enumerate(opcode_table)}

if MPU != '65816':
    del MNEMONICS['UNUSED']



### CONVERSION

for num, line in sc_in: 

    # RULE 1: Keep empty lines (for now)
    if not line.strip():
        sc_out.append((num, ''))
        continue

    # RULE 2: Keep lines that are comments unchanged because user knows best
    # about these, but remove trailing whitespace 
    if line.strip()[0] == ';':
        sc_out.append((num, line.rstrip()))
        continue

    # REMOVE in-line comments for later use. Note that we have to make sure that
    # the comment directive (';') is not inside a string or a character, so we
    # replace all strings and characters temporarily
    tmp_line = line
    ilc = '' 
    dq = re.compile('\".*?\"')
    sq = re.compile("\'.\'")

    # Mask all strings
    dqa = dq.findall(line)
    for q in dqa:
        tmp_line = line.replace(q, 'x'*len(q))

    # Mask all characters
    sqa = sq.findall(tmp_line)
    for q in sqa:
        tmp_line = tmp_line.replace(q, 'x'*len(q))

    # Any semicolon left in the line must a comment indicator
    try:
        sc = tmp_line.index(';')
    except ValueError:
        pay = line
    else:
        pay = line[:sc]
        ilc = '  '+line[sc:].strip() # Adjust the number of spaces before inlines here

    # CLAIM: pay should not contain any more comments
    
    # Get rid of the user's formatting for mnemonics, directives, and labels,
    # because it might suck anyway
    pay = pay.strip()
    w = pay.split()

    # LABELS: We deal with them first because we might have something that comes
    # on the same line. 
    if (w[0] not in MNEMONICS) and (w[0] not in DIRECTIVES):
        w[0] = w[0].lower()

        # If this is all we have on this line, then we are done
        try:
            w[1]
        except IndexError:
            sc_out.append((num, w[0]+ilc))
            continue
        # No such luck, there is more. Save the label in its own line for later
        # processing and look at the rest, which must be either an mnemonic or
        # a directive (or something is seriously wrong)
        else: 
            sc_out.append((num, w[0]))
            pay = ' '.join(w[1:])
            w = pay.split()

    if w[0] in MNEMONICS:
        w[0] = INDENT+INDENT+w[0].lower()
        new_pay = ' '.join(w)
        sc_out.append((num, new_pay+ilc))
        continue

    elif w[0] in DIRECTIVES:
        w[0] = INDENT+w[0].lower()

        # Problem: The data directives such as .byte might contain a string that
        # has more than one spaces, which would get shrunk to a single space
        # with the normal procedure
        if w[0].strip() not in DATA_DIRECTIVES:
            new_pay = ' '.join(w)
        else:
            dd = w[0]+' '  # Save the data directive
            w = pay.split(' ', 1)[1]  # Get the payload
            wt = w.split(',')
            new_pay = dd+', '.join([t.strip() for t in wt])

        sc_out.append((num, new_pay+ilc))
        continue

    else:
        fatal(num, '"{0}" is neither label, directive, of mnemonic'.format(w[0]))


### DEFINITION BLOCKS

# A definition block consists of two or more .equ statements in sequence. We want
# them to be formatted so that the first, second, and third element are all
# justified:
#
#       .equ athena   100
#       .equ zeus     1000
#       .equ poseidon 11
#
# Any inline comments follow in their lines as usual with two spaces distance.

sc_defs = []
block = []
in_block = False 

for num, line in sc_out:

    # If we have an .equ directive, split it up. Need the try/except routine so
    # we don't crash on empty lines
    try:

        if line.split()[0] == '.equ':
            e = line.strip().split(' ', 2)

            # If we're not already in a block, create a new one
            if not in_block:
                block = []
                in_block = True

            block.append(e)
            continue 

    except IndexError:
        pass

    # If this is not a definition directive and we're in a block, the block is
    # done and we need to format and save it
    if in_block:

        # Get the maximal width of the second word (the name of the symbol)
        max_width = max([len(row[1]) for row in block])

        for row in block:
            sc_defs.append((num, '{0}{1} {2:<{mw}} {3}'\
                    .format(INDENT, row[0], row[1], row[2], mw=max_width)))

        in_block = False

    sc_defs.append((num, line))


### DATA BLOCKS

# A data block consists of two or more data directives (.byte, .word, .long)
# with an identifying label. The usual space between the label and the directive
# is removed:
#
# first  .byte 01, 02, 03, 04 ; computer people count funny
# second .byte 11, 12, 13, 14
# third  .byte 21, 22, 23, 24
#
# They need to be formatted so that the data directives are all justified. This
# should also be true for lines where one label is not present.
    

### OUTPUT

if args.test:
    for l in sc_defs:
        print(l[1])
else:
    filename, file_ext = os.path.splitext(args.source)
    os.rename(args.source, filename+'.orig')

    with open(filename+'.tasm', 'w') as f:
        for l in sc_defs:
            f.write(l[1]+'\n')

verbose('All done. Enjoy your cake!')
sys.exit(0)

### END ###
