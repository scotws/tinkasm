Math Engine for Tinkasm 
Scot W. Stevenson <scot.stevenson@gmail.com>
First version: 13. Jan 2019
This version: 21. Jan 2019

This folder contains the math engine for Tinkasm. Inside the assembler, it
implements a Reverse Polish Notation (RPN) stack-based calculator. It also uses
some words from Forth for stack manipulation.

The math engine accepts a string without the delimiters in the assembler (no "["
or "]"). The string can contain decimal numbers, math symbols, and directives.
Simple examples:

        "2 2 +" 

You can use whitespace to make the calculation clearer:

        "2 1 +  4 +"

The engine returns one number and an error code. It assumes all symbols have
been converted and all numbers are decimal integers. At the end of the process,
only one number may be on the stack ("top of the stack", TOS). It is up to the
caller to handle any numbers that are too large.

MATH 

Most of the following instructions affect TOS and NOS ("next on stack").

        +       plus
        -       minus
        *       multiplication
        /       division

        .and            logically AND TOS and NOS
        .or             logically OR TOS and NOS
        .xor            logically XOR TOS and NOS
        .lshift         shift NOS left by number of bits in TOS
        .rshift         shift NOS left by number of bits in TOS
        .invert         flip all bits (~ in most languages, ^ in Go (golang)
        .lsb            isolate the Least Significant Byte (LSB) in TOS
        .msb            isolate the Most Significant Byte (MSB) in TOS
        .bank           isoluate the Bank Byte (65816) in TOS
 

DIRECTIVES

All directives start with a dot.

        .drop   remove TOS
        .dup    dumplicate TOS
        .over   copy NOS over the TOS as new TOS
        .swap   switch TOS and NOS

EXAMPLES

Swap LSB and MSB of 0xAABB:

        "43707 .dup  .lsb 8 .lshift  .swap .msb 8 .rshift  .or"


