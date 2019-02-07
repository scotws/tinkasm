# Math Engine for Tinkasm 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 13. Jan 2019
# This version: 13. Jan 2019
"""Provide a stack-based RPN math engine for the Tinkasm"""

from collections import deque
from random import randint

from common.common import convert_number

# ---- DIRECTIVES ----

def op_and(d):
    """Logically AND NOS and TOS"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: .and: Stack underflow')
    else:
        res = nos and tos
        d.append(res)


def op_bank(d):
    """Mask all but the Bank Byte (65816)"""
    try:
        tos = d.pop()
    except IndexError:
        print('MATH ERROR: .bank: Stack underflow')
    else:
        res = (tos and 0xFF0000) >> 16
        d.append(res)


def op_div(d):
    """Multiply TOS and NOS"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: *: Stack underflow')
    else:

        try:
            res = nos / tos
        except ZeroDivisionError:
            print('MATH ERROR: Division by Zero')
        else:
            d.append(res)
 

def op_drop(d):
    """Remove the TOS"""
    try:
        _= d.pop()
    except IndexError:
        print('MATH ERROR: .drop: Stack underflow')


def op_inv(d):
    """Invert the bits of the number"""
    try:
        tos = d.pop()
    except IndexError:
        print('MATH ERROR: .inv: Stack underflow')
    else:
        res = ~tos
        d.append(res)


def op_dup(d):
    """Duplicate the TOS"""
    try:
        tos = d.pop()
    except IndexError:
        print('MATH ERROR: .dup: Stack underflow')
    else:
        d.append(tos)
        d.append(tos)


def op_lsb(d):
    """Mask all but Least Significant Byte (LSB)"""
    try:
        tos = d.pop()
    except IndexError:
        print('MATH ERROR: .lsb: Stack underflow')
    else:
        res = tos and 0xFF
        d.append(res)


def op_lshift(d):
    """Shift NOS left TOS times"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: .lshift: Stack underflow')
    else:
        res = nos << tos
        d.append(res)


def op_msb(d):
    """Mask all but Most Significant Byte (MSB)"""
    try:
        tos = d.pop()
    except IndexError:
        print('MATH ERROR: .msb: Stack underflow')
    else:
        res = (tos and 0xFF00) >> 8
        d.append(res)


def op_minus(d):
    """Subtract TOS from NOS"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: -: Stack underflow')
    else:
        res = nos - tos
        d.append(res)


def op_mult(d):
    """Multiply TOS and NOS"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: *: Stack underflow')
    else:
        res = nos * tos
        d.append(res)
 

def op_or(d):
    """Logically OR NOS and TOS"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: .or: Stack underflow')
    else:
        res = nos or tos
        d.append(res)


def op_over(d):
    """Add NOS to TOS"""
    try:
        nos = d[-2]
    except IndexError:
        print('MATH ERROR: .over: Stack underflow')
    else:
        d.append(nos)


def op_plus(d):
    """Add NOS to TOS"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: +: Stack underflow')
    else:
        res = nos + tos
        d.append(res)
 
def op_rand(d):
     """Add a random byte to the stack"""
     res = randint(0,255)
     d.append(res)


def op_rshift(d):
    """Shift NOS right TOS times"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: .rshift: Stack underflow')
    else:
        res = nos >> tos
        d.append(res)


def op_swap(d):
    """Exchange TOS and NOS"""
    try: 
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: .over: Stack underflow')
    else:
        d.append(tos)
        d.append(nos)

def op_xor(d):
    """Logically XOR NOS and TOS. This requires the operator module"""
    try:
        tos = d.pop()
        nos = d.pop()
    except IndexError:
        print('MATH ERROR: .xor: Stack underflow')
    else:
        res = nos^tos
        d.append(res)


dir_table = {
        "+": op_plus,
        "-": op_minus,
        "*": op_mult,
        "/": op_div,
        ".and": op_and,
        ".bank": op_bank,
        ".drop": op_drop,
        ".dup": op_dup,
        ".inv": op_inv,
        ".lshift": op_lshift,
        ".lsb": op_lsb,
        ".msb": op_msb,
        ".or": op_or,
        ".over": op_over,
        ".rand": op_rand,
        ".rshift": op_rshift,
        ".swap": op_swap,
        ".xor": op_xor}
    

# ---- MAIN ROUTINE ----

def engine(s):
    """Take a string of space-delimited numbers, operations, and/or directives
    and calculate them as a stack-based RPN Forth-like machine. Return a
    single number and a flag showing success for failure.
    """
    ws = s.split()
    stack = deque()
    ok = True

    for w in ws:

        if w in dir_table.keys():
            dir_table[w](stack)
        else:
            f_conv, n = convert_number(w)

            if not f_conv:
                print(f'MATH ERROR: "{w}" is neither directive nor number')
                ok = False
            else:
                stack.append(n)

    if len(stack) != 1:
        print(f'MATH ERROR: Stack ends with length {len(stack)}, not 1, inserting 0')
        stack.append(0)
        ok = False

    return stack[0], ok


if __name__ == '__main__':
    test_string = f'.rand'
    print(engine(test_string))



