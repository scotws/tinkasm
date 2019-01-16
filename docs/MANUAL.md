# A Tinkerer's Assembler for the 6502/65c02/65816

Scot W. Stevenson <scot.stevenson@gmail.com>  

## Overview

The Tinkerer's Assembler (TinkAsm for short) is a multi-pass assembler in the
style of Sarkar *et al* for the 6502, 65c02, and 65816 8/16-MPUs written in
Python. Its aim is to provide hobbyists with an assembler that will run on
almost any operating system while being easy to understand and easy to modify. 


## The General Idea

People who want to play around with assemblers but are not computer scientists
have a rough time. Like compilers, professional-grade assemblers involve things
like lexers, parsers, and formal grammars. They want you to descend down to
strange places and using weird things called ASTs. And if writing one weren't
bad enough, but trying to adapt other people's assemblers to experiment with
them is far worse. 

This is an assembler for the 6502, 65c02, and 65816 MPUs for non-computer
scientists who like to tinker -- hence the name: A Tinkerer's Assembler. Instead
of parsing and lexing the source code and doing other complicated stuff, the
assembly process is broken down into a large number of simple steps that usually
only do one thing. The code is written in "primitive" Python: Easy to
understand, easy to modify, if not very fast or efficient.

This, then, is an assembler for those of us who associate the "Wizard Book" with
*Lord of the Rings* and the "Dragon Book" with *A Song of Ice and Fire.* 


### Drawbacks

Because of the way it is structured, as an assembler, TinkAsm is somewhat
inefficient as an assembler. If you're in it for raw speed, this is not the
assembler for you. Given the size of the data involved, this is probably not 
a problem.

TinkAsm assumes that there is one and one mnemonic for each opcode. This is why
the assembler uses Typist's Assembler Notation (TAN) instead of traditional
notation for these MPUs. 


### State of Development

TinkAsm, though very much functional, is not fully tested, and is being used for
Liara Forth for the 65816. See the `docs/TODO.txt` file for features that are to
be added soon and those that will come later. Suggestions are welcome. 


## Requirements 

TinkAsm requires Python 3.4 or later. It will not run with Python 2.7. 


### Options

**-i --input**      - Input assembler file (required) 

**-ir**             - Save intermediate state of assembler to file `tink.ir`

**-o --output**     - Other name for output file, otherwise it will be `tink.bin`

**-l --listing**    - Create a line-by-line listing file `tink.lst` 

**-v --verbose**    - Print more info about each assembly step

**-p --print**      - Print a listing to screen at the end of assembly

**-s28**            - Create a S28 data file for uploading (NOT WORKING)

**-x --hexdump**    - Create a human-readable hexdump file `tasm.hex`

Note that only an input file is required, and there will always be an output
file written. Note also that TinkAsm will happily overwrite the previous files
without a warning. 


## The Source File 

TinkAsm requires a text format source file that is passed with the `-i` or
`--input` options. The assembler does not distinguish between upper and lower
case (internally, all is converted to lower case). 

Directives always come first in their line (except for the Current Line Symbol,
see below). Assignments for example are `.equ mynumber 13.`


### Mnemonics 

TinkAsm uses a different format for the actual MPU instructions, the Typist's
Assembler Notation (TAN). See [the
introduction](https://docs.google.com/document/d/16Sv3Y-3rHPXyxT1J3zLBVq4reSPYtY2G6OSojNTm4SQ/)
to TAN for details.

TinkAsm and TAN try to ensure that all source files have the same formatting, a
philosophy it takes from the Go programming language. An equivalent tool to Go's
`gofmt`, `tinkfmt.py`, is included. 


### Definitions

TinkAsm requires two definitions at the beginning of the source file: Where
assembly is to start (`.origin`) and which processor the code is to be
generated for (`.mpu`). Failure to provide either one will abort the assembly
process with a FATAL error. Supported MPUs are `6502`, `65c02` (upper and
lowercase "c" are accepted), and `65816`. 


### Assignments 

To assign a value to a variable, use `.equ` with significant white space,
followed by the symbol and the value.

```
        .equ a_bore 4
```
Modifications and math terms are allowed (see below for details).

```
        .equ less 8001
        .equ some .lsb less
        .equ more [ less 1 + ]
        .equ other .msb [ less 1 + ]
```
Note that numbers by default are in hexadecimal format (see below).

*(Earlier versions of TinkAsm allowed assigments with the equal sign in the form
`of_course = 2a.` This has been removed to enforce a common style.)*

### Labels

TinkAsm sees any string as a label that starts in the first column of a line and
is not the comment directive (usually `;`) or the anonymous label (by default `@`).
In other words, anything that is *not* a label or a comment must have white space
in front of it. There are no rules for the string itself, so `*!$?` is a
perfectly legal string. 

```
ice&fire        nop
                nop
                jmp ice&fire
```
Note that in contrast to other assemblers, labels do not have to end with a `:`. 
You cannot have more than one label in the same line. Internally, labels are
moved to their own lines during processing.


### Anonymous Labels 

Anonymous labels are used for trivial uses such as loops that don't warrant a
full label. It consists of `@` as the generic label, used as a normal label, and
either a `+` or a `-` after the jump or branch instruction. 

```
@               nop
                nop
                jmp -           ; anonymous reference 
```

The `-` or `+` always refers to the next or previous `@`. These directives
cannot be modified. 

*(In earlier versions of TinkAsm, these labels were called "local" labels. They
were renamed to fit the common usage.)*


### Current Line Symbol

To reference the current address, by default the directive `.*` is used 
instead of an operand. It can be modified and subjected to mathematical 
operations.
```
                jmp [ .* 2 + ]
```
In contrast to other assemblers, the current line symbol cannot be used for
advancing the line counter. Use the directives `.advance` and `.skip` for these,
see below.


### Numbers 

TinkAsm follows the TAN convention that all numbers are hexadecimal by default,
because this is by far the most common format used in assembly and reduces
visual clutter. To flag decimal use, add `&` to the number (for example,
`lda.# &10`). The common hex prefixes `$` and `0x` are recognized, with `0x`
being the recommended format. For binary numbers, use `%`. Octal numbers are
not supported.

Numbers may contain `.` and `:` for better readability.

```
        .equ address 00:fffa
```

This is especially useful for the bank bytes of the 65816.

In cases where a term could be an already defined symbol or a hex number (for
example `aaa`), the assembler assumes a symbol. To force the use of a number,
use a hex prefix such as `0x` or `$`.


### Single Characters and Strings

Single characters are marked in single quotes (`lda.# 'a'`). Because of the way
Python 3 handles characters, the Unicode value is used, but might not fit into
the register. Strings are marked in double quotes (`.byte "Kaylee"`). The
assembler enforces not using double quotes for single characters (`"a"`) to
prevent errors.


### Modifiers and Math

Tinkasm allows complex math terms with Reverse Polish Notation (RPN) inside
square brackets:
```
        [ 2 2 + ]
        [ $0000 $0F0F .and ]
```
Numbers of different bases and symbols will be converted. At the end of the
calculation, there may only be one number left ("on the stack"). The following
directives and operations are supported:

**+**
**-**
*****
**/**
**.and**
**.bank**
**.drop** - Drop the number on the top of the stack
**.dup** - Duplicate the number on the top of the stack
**.inv** - Invert (compliment) number on the top of the stack
**.lshift**
**.lsb**
**.msb**
**.or**
**.over** - Copies second entry on stack to top of stack
**.rand** - Returns a random byte (calculated during assembly)
**.rshift**
**.swap** - Exchange the top of the stack and the number below it
**.xor**

Note these also must be in RPN format, so `[ $00FF .lsb ]` is the correct
format.

### Other 

It is assumed that branches will always be given a label, not the relative
offset. There is in fact currently no way to pass on such offset. 


## Macros

The macro system of TinkAsm is in its first stage. Macros do not accept
parameters and cannot reference other macros. Including parameters is a high
priority for the next version.

To define a macro, use the directive `.macro` followed by the name string of the
macro. No label may precede the directive. In a future version, parameters will
follow the name string. The actual macro contents follow in the subsequent
lines in the usual format. The macro definition is terminated by `.endmacro` in
its own line.

To expand a macro, use the `.invoke` directive followed by the macro's name. In
future versions, this will be followed optional parameters. 

Currently, there are no system macros such as `.if`, `.then`, `.else` or loop
constructs. These are to be added in a future version.


## List of Directives

### Directives for all MPUs

`@` - The default anonymous label symbol. Used at the very beginning of a line and
referenced by `+` and `-` for jumps and branches.

`+` - As an operand to a branch or jump instruction: Refer to the next anonymous 
label. 

`-` - As an operand to a branch or jump instruction: Refer to previous anonymous
label. 

`.*` - As an operand in the first position after the mnemonic: Marks current
address (eg `jmp [ .* 2 + ]`). 

`.advance` - Jump ahead to the address given as parameter, filling the space
in between with zeros.

`.bank` - Isolate bank byte - the highest byte - of following number. This is a
modifier. Thought it pretty much only makes sense for the 65816 MPU, it is
supported for other formats as well. 

`.byte` - Store the following list of comma-delimited bytes. Parameters
can be in any supported number base or symbols. 
Example: `.byte 'a', 2, [ size 1 + ], "Kaylee", %11001001`

`.end` - Marks the end of the assembly source code. Must be last line in
original source file. Required. 

`.endmacro` - End definition of the macro that was last defined by `.macro`. 

`.include` - Inserts code from an external file, the name of which is given as a
parameter. 

`.invoke` - Inserts the macro given as parameter. 

`.long` - Store the following list of comma-delimited 24-bit as bytes.
The assembler handles the conversion to little-endian format. Parameters can be
in any supported number base or symbols.

`.lsb` - Isolate least significant byte of following number. This is a 
modifier.

`.macro` - Start definition of the macros, the name of which follows
immediately as the next string. Parameters are not supported in this version.
The definition ends with the first `.endmacro`. Macros cannot be nested.

`.msb` - Isolate most significant byte of following number. This is a 
modifier.

`.mpu` - Provides the target MPU as the parameter. Required. Legal values are
`6502`, `65c02`, or `65816`. 

`.origin` - Start assembly at the address provided as a parameter.
Required for the program to run. Example: `.origin 8000`

`.save` - Given a symbol and a number, save the current address during assembly 
as the symbol and skip over the number of bytes. Used to reserve a certain
number of bytes at a certain location. Example: `.save counter 2`

`.skip` - Jump head by the number of bytes given as a parameter, filling the
space in between with zeros. Example: `.skip 100`

`.word` - Store the following list of comma-delimited 16-bit words as
bytes. The assembler handles the conversion to little-endian format. Parameters
can be in any supported number base or symbols. Note that WDC uses "double 
byte" for 16-bit values, but the rest of the world uses "word". 


### Directives for 65816 only

`.a8` and `.a16` - Switch the size of the A register to 8 or 16 bit. The switch
to 16 bit only works in native mode. These insert the required instructions
as well as the internal control sequences (see below) and should be used instead
of directly coding the `rep.#`/`sep.#` instructions.

`.xy8` and `.xy16` - Switch the size of the X and Y registers to 8 or 16 bit.
The switch to 16 bit only works in native mode. These insert the required instructions
as well as the internal control sequences (see below) and should be used instead
of directly coding the `rep.#`/`sep.#` instructions.

`.axy8` and `.axy16` - Switch the size of the A, X, and Y registers to 8 or 16
bit. The switch to 16 bit only works in native mode. These insert the required instructions
as well as the internal control sequences (see below) and should be used instead
of directly coding the `rep.#`/`sep.#` instructions.

`.emulated` - Switch the MPU to emulated mode, inserting the required
instructions and control sequences. Use this directive instead of directly
coding `sec`/`xce`. 

`.native` - Switch the MPU to native mode, inserting the required
instructions and control sequences. Use this directive instead of directly
coding `clc`/`xce`. 


### Direct use of 65816 control directives

Internally, the mode and register size switches are handled by inserting
"control directives" into the source code. Though the above directives such as
`.native` or `.a16` should be enough, you can insert the control sequences
directly to ensure that the assembler handles the sizes correctly. These do not
encode any instructions.

`.!a8`, `.!a16` - Tell the assembler to interpret the A register as 8 or 16 bit.
Note the switch to 16 bit only works in native mode.

`.!xy8`, `.!xy16` - Tell the assembler to interpret the X and Y register as 8 or
16 bit.  Note the switch to 16 bit only works in native mode.

`.!emulated` - Tell the assembler to ensure emulated mode. Note this does not
insert the control sequences `.a8!` and `.xy8!` as the full directive
`.emulated` does.

`.!native` - Tell the assembler to ensure we're in native mode. 


### Notes on various opcodes

TinkAsm enforces the signature byte of `brk` for all processors.

The `mvp` and `mvn` move instructions are annoying even in the Typist's
Assembler Notation because they break the rule that every instruction has only
one operand. Also, the source and destination parameters are reversed in machine
code from their positions in assembler. The format used here is 

```
                mvp <src>,<dest>
```

The source and destination parameters can be modified (such as `.lsb 1000`) or
consist of math terms (`[ home 2 + ]`).  For longer terms, you can use the
`.bank` directive.

```
        .equ source 01:0000
        .equ target 02:0000

                mvp .bank source , .bank target
```


## Internals 

Since this is an assembler that was written to be tinkered with, some notes on
the code. 


### Language and coding style

TinkAsm uses Python because it is one of the most widespread languages in use
and is easy to understand even for those who don't know it ("executable
pseudo-code"). 


### Structure 

The program has the most simple structure possible: It starts at the beginning,
runs to the end, and then stops. Everything is in one file, no external routines
are loaded, and only system library files are referenced (got to have your
batteries). There is exactly one class, generators and list comprehensions are
used sparingly. There are no map or filter constructs. The code just
brute-forces its way top-to-down.

On the next lower level, TinkAsm is built up out of **steps** and **passes**.  A
pass walks through the complete source code, while a step does something once.
Each is a closed unit that ideally does one thing and one thing only. However,
this is not a religion. 

Information is only passed through lists, not through "side channels". For
example, we never define a flag in one pass to signal something to a pass lower
down. 

### Known Issues

There is currently no way to load the single quotation mark character directly
without having to enter the hex value by hand (`lda.# "'"` or such will not
work).

## TOOLS

### Tinkfmt Source Code Formatter

TinkAsm is currently shipped with one tool, the formatter Tinkfmt. See the
README file in the directory `tinkfmt` for details. 


## SOURCES AND THANKS 

TinkAsm was inspired by Samuel A. Falvo II, who pointed me to a paper by Sarkar
*et al*, ["A Nanopass Framework for Compiler Education"](
http://www.cs.indiana.edu/~dyb/pubs/nano-jfp.pdf)
The authors discuss using compilers with multiple small passes for educational
purposes. 

David Salomon's [*Assemblers And
Loaders*](http://www.davidsalomon.name/assem.advertis/AssemAd.html) was
invaluable and is highly recommended for anybody who wants to write their own. 
