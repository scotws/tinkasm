# Opcode Routines for the 65816 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 22. Okt 2015
# This version: 23. Okt 2015

# Opcode routines for the MPUs. Make common routines so they can be used if we
# ever expand to other processors. Load this before we load the pickled opcode
# table 

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

