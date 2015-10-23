# Pickel Opcodes for the Typist's Assembler for the 65816 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 23. Okt 2015
# This version: 23. Okt 2015

# See background at https://docs.python.org/3.5/library/pickle.html

# Run this program to create a file with pickled opcodes, then copy it to the
# main directory.


import pickle 

### 65816 OPCODES ###

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

# Entries in the opcode table are tuples (immutable) of opcode in hex, mnemonic
# string, length in bytes, number of operands, special routines to execute. 

opcode_table = (
        (0x00, 'brk', 1, 0, ocs_brk),
        (0x01, 'ora.dx', 2, 1, None),
        (0x02, 'cop', 2, 1, ocs_cop),
        (0x03, 'ora.s', 2, 1, ocs_stack0 ),
        (0x04, 'tsb.d', 2, 1, None ),
        (0x05, 'ora.d', 2, 1, None )) 

with open('opcodes65816.pickle', 'wb') as f:
    pickle.dump(opcode_table, f, pickle.HIGHEST_PROTOCOL)
    
