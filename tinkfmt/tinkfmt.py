# A Formatter for the Tinkerer's Assembler 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 27. Aug 2016
# This version: 02. Sep 2016

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
source code is formatted the same. This makes writing code faster - the
machine does the formatting - and the code itself easier to understand. 
See the README.md file for more details and a discussion of the basic rules.
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
Version BETA  11. Jan 2019
Copyright 2016-2019 Scot W. Stevenson <scot.stevenson@gmail.com>
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
        '.include', '.!native', '.!emulated', '{', '}', '.save']

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


def has_label(s):
    """Given a line of code as a string, test to see if it starts with a 
    label. Assumes that all non-labels start with whitespace. Returns a
    bool.
    """

    try:
        f = (s[0] not in string.whitespace) and (s[0] != ';')
    except IndexError:
        return False
    else:
        return f


def is_data(s):
    """Takes a line of code and determines if it is a data entry (starts
    with .byte, .word, or .line). Returns a bool: True if it is a data,
    false if not. Should give correct result if there is a label or not. 
    Calls has_label()
    """

    # Get rid of empty strings and single labels
    if len(s.split()) < 2:
        return False
    
    # If we have a label, get rid of it
    if has_label:
        s = s.split(' ', 1)[1]

    # We keep a list of data directives to check against
    t = s.strip().split()

    return (t[0] in DATA_DIRECTIVES)


def is_label_too_long(label, line):
    """Checks to see if a label is too long to fit in the whitespace before the 
    first character in a line. Assumes that the line itself does not contain a
    label. Returns a bool.
    """
    ws = len(line) - len(line.lstrip())

    # We leave one space for padding
    return (len(label) > ws-1)


def flush_data(bl, l):
    """When a data block is complete, take it and the list of lines we have so far.
    Add the correctly formatted data block to the list, returnign the list. It is 
    the caller's responsibility to handle any flags.
    """
    # Get the maximal width of the first entry (the labels)
    max_width = max([len(row[0]) for row in bl])

    for row in bl:
        l.append((num, '{0:<{mw}} {1}'.format(row[0], row[1], mw=max_width)))

    return l


def flush_definitions(bl, l, i=INDENT):
    """When a defintion block is complete, take it and the list of lines we have 
    so far. Add the correctly formatted data block to the list, returnign the list.
    It is the caller's responsibility to handle any flags.
    """
    # Get the maximal width of the second word (the name of the symbol)
    max_width = max([len(row[1]) for row in bl])

    for row in bl:
        l.append((num, '{0}{1} {2:<{mw}} {3}'\
                .format(i, row[0], row[1], row[2], mw=max_width)))

    return l

 

### PARSE INPUT

parser = argparse.ArgumentParser()
parser.add_argument('-i', '--input', dest='source', required=True,\
        help='Assembler source code file (required)')
parser.add_argument('-t', '--test',\
        help="Test run, don't change files, just print", action='store_true')
parser.add_argument('-v', '--verbose',\
        help='Display additional information', action='store_true')
parser.add_argument('-m', '--mpu', dest='mpu',\
        help='Override target MPU: 6502, 65c02, or 65816')
args = parser.parse_args()


### GENERAL SETUP

verbose(TITLE_STRING)

with open(args.source, "r") as f:
        sc_in = list(enumerate(f.readlines(), 1))

verbose('Read {0} lines from {1}'.format(len(sc_in), args.source))


### PROCESSOR SETUP

MPU = ""

# Argument passed by user comes first
if args.mpu:
    MPU = args.mpu
else:
    for num, line in sc_in:

        if '.mpu' in line.lower():
            MPU = line.split()[1].strip()

if not MPU:
    fatal(num, 'No MPU found as directive or given, target MPU unknown.')

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

# The conversion routines themselves are in three stages: The most general stage
# comes first, with labels being moved to their own lines, everything being
# turned into lowercase, and directives and opcodes indented as they should be.
# The next two steps handle the block formatting of directives and data
# separately, making it easier to change these later.

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

    # After that, any semicolon left in the line must a comment indicator
    try:
        sc = tmp_line.index(';')
    except ValueError:
        pay = line
        # We don't like inline comments after labels, so we signal that we don't
        # have them by explicitly marking ilc as an empty string
        ilc = ''
    else:
        pay = line[:sc]
        ilc = '  '+line[sc:].strip() # Adjust the number of spaces before inlines here

    # CLAIM: line should not contain any more comments
    
    # Get rid of the user's formatting for mnemonics, directives, and labels,
    # because it probably sucks anyway. This step liberates the user from having
    # to care about formatting at all while entering the code.
    pay = pay.strip()
    w = pay.split()

    # LABELS: We deal with them first because we might have something that comes
    # on the same line. All labels get their own line at first.
    if (w[0] not in MNEMONICS) and (w[0] not in DIRECTIVES):
        w[0] = w[0].lower()

        # If this is all we have on this line, then we are done
        try:
            w[1]
        except IndexError:

            # If we had an inline comment after the label, we move it before the label
            # because we don't like comments after labels
            if ilc:
                sc_out.append((num, ilc.strip()))

            sc_out.append((num, w[0]))

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
        fatal(num, '"{0}" is neither label, directive, or mnemonic'.format(w[0]))


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
# TODO: If there is a label in a definition block, move it before or after the
# block instead of leaving it in the middle

sc_defs = []
block = []
in_block = False 

for num, line in sc_out:

    # If we have an .equ directive, split it up. Need the try/except so
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

        sc_defs = flush_definitions(block, sc_defs)
        in_block = False

    sc_defs.append((num, line))


# If we ended the file in a definition block, flush it or else we'll cut off the
# last lines. This doesn't happen in the main routines because of the .end
# directive, but can in included code
if in_block:
        sc_defs = flush_definitions(block, sc_defs)



### LABELS

# Labels should go in front of a mnemonic or directive (with special rules for
# data directives) if there is the space, otherwise they stay on their own line
# If there was an inline comment after a label, we put it in front of the label,
# because we don't like that sort of thing

# For data directives, we put any labels in front of .byte etc for now and deal
# with the formatting later in a different step

sc_labels = []
prev_line = ''
have_label = False

for num, line in sc_defs:

    # Get rid of empty lines 
    if not line.strip():
        sc_labels.append((num, line))
        continue

    # Get rid of comments
    if line.strip()[0] == ';':
        sc_labels.append((num, line))
        continue

    if has_label(line):
        
        # If we have more than one label, we just print them one below each
        # other
        if have_label:
            sc_labels.append((num, prev_line))
        else:
            have_label = True

        prev_line = line
        continue

    # Whatever is left must be a directive or a mnemonic. 
    if have_label:

        l = prev_line.strip()

        # If this is a data line (.byte etc), we just put the label in front of
        # the data directive and let a later step deal with the problem of
        # formatting
        if is_data(line):
            line = l + ' ' + line
        
        # In all other cases, we make sure that the label will fit, otherwise we
        # put the next line in a new line
        else:
       
            if is_label_too_long(l, line):
                sc_labels.append((num-1, l))
            else:    
                line = l + line[len(l):]
        
    # We've already checked for double labels
    have_label = False
    sc_labels.append((num, line))
    continue


### DATA BLOCKS

# The last step is to adjust the formatting of data blocks. At this point, 
# data lines (.byte etc) are either indented like normal directives, or have
# a label in front of them with incorrect formatting. We want to change this so
# that the .byte (etc) column starts after the longest label:
#
#
# one    .byte 01, 02, 03, 04 ; computer people count funny
# second .byte 11, 12, 13, 14
# four?  .byte "I really hate counting"
#
# If there is line without a label inside the data block, it should keep the
# formatting.

sc_data = []
block = []
in_block = False

for num, line in sc_labels:

    if not is_data(line):

        # If we were part of a block, now is the time to print it
        if in_block:
            sc_data = flush_data(block, sc_data)
            block = []
            in_block = False

        sc_data.append((num, line))
        continue

    # This is a date line. Start new block if we're not already in one
    if not in_block:
        block = []
        in_block = True

    # See if we have a label, and if yes, isolate it
    if has_label(line):
        l, d = line.split(' ', 1)
    else:
        l = ' '*(INDENT_SIZE-1)  # So we don't look like a label
        d = line

    block.append((l, d.lstrip()))


# If we ended still inside a block, we have to flush it one last time or else we
# cut off the last lines. This doesn't happen with the main source code file,
# because it ends with the .end directive
if in_block:
    sc_data = flush_data(block, sc_data)


### OUTPUT

if args.test:
    for l in sc_data:
        print(l[1])
else:
    filename, file_ext = os.path.splitext(args.source)
    os.rename(args.source, filename+'.orig')

    with open(filename+'.tasm', 'w') as f:
        for l in sc_data:
            f.write(l[1]+'\n')

verbose('All done. Enjoy your cake!')
sys.exit(0)

## END ###
