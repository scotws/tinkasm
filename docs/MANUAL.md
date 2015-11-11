# A Tinkerer's Assembler for the 6502/65c02/65816

Scot W. Stevenson <scot.stevenson@gmail.com>


## Overview

The Tinkerer's Assembler (TinkAsm for short) is a multi-pass assembler for the
6502, 65c02, and 65816 8/16-MPUs. It is written in simple Python 3 code with the
intention to give computer hobbyists an assembler that is not only easy to
understand, but also easy to modify and adapt to their own needs. It uses the
Typist's Assembler Notation (TAN) and is released under the GPL. 


## Basic Idea

People who want to play around with assemblers but are not computer scientists
have a rough time. Like compilers, professional grade assemblers involve things
like lexers and parsers, formal grammars, descending down to strange places and
using weird things called ASTs. And if writing one weren't bad enough, but
trying to adapt other people's assemblers to experiment with them is far worse. 

This is an assembler for the 6502, 65c02, and 65816 MPUs for people who like to
tinker -- hence the name: A Tinkerer's Assembler. Instead of parsing and lexing
the source code and doing other computer science stuff, the assembly
process is broken down into a large number of very simple passes that each do
one thing. Easy to understand, easy to modify. 

This, then, is an assembler for those of us who associate the "Wizard Book" with
*Lord of the Rings* and the "Dragon Book" with *A Song of Ice and Fire.* Enjoy.


## Use

TinkAsm requires Python 3.4 or later. It will not run with Python 2.7. 

The assembler does not distinguish between upper and lower case (internally, all
is converted to lower case). 

(call options) 


### PARAMETERS

-i --input      - Input assembler file (required) 
-o --output     - Output file for the binary code, default is tasm.bin 
-l --listing    - Output file for the listing, default is tasm.txt  
-v --verbose    - Print more info about each assembly step
-d --dump       - Dump state of inbetween steps, produces lots of output
-x --hexdump    - Create a human-readable hexdump file tasm.hex



## Drawbacks

Because of the way it is structured, as an assembler, TinkAsm is horribly
inefficient as an actual assembler. If you're in it for raw speed, this is not
the assembler for you. 

TinkAsm assumes that there is one and one menemonic for each opcode. This is why
the assembler uses Typist's Assembler Notation (TAN) instead of traditional
notation for these MPUs. 

## Use 

### Labels

TinkAsm sees any string as a label that is in the first column of a line and is
not the comment directive. In other words, anything that is *not* a label or a
comment must have whitespace in front of it. Note there are no rules for the
string itself. `*!$?' is a perfectly legal string. (TODO check Unicode
characters). 

During use, there are two kinds of label references, global and local. A
**global** reference points to the label by name as is expected. 

```
ice&fire        nop
                nop
                jmp ice&fire    ; gobal reference
                
```

A **local reference** is an easy to use form of a label for trivial uses such as
loops. It consists of `@` as the generic label and either a `+` or a `-` after
the jump or branch instruction. 

```
@               nop
                nop
                jmp -           ; local reference
```
The `-` or `+` always refers to the next or previous `@`. 

It is assumed that branches will always be given a label, not the relative
offset. There is in fact currently no way to pass on such offset.

Currently, no arithmetic with label references is possible, such as `jmp cats +
2`. This feature will be added in a future version.


### Macros

The macro system of TinkAsm is currently very primitive. Macros do not accept
parameters and cannot reference other macros.

To define a macro, use the directive `.macro` followed by the name string of the
macro. No label may preceed the directive. In a future version, parameters will
follow the name string. The actual macro contents follow in the subsequent
lines in the usual format. The macro definition is terminated by `.endmacro` in
its own line.

To expand a macro, use the `.invoke` directive followed by the macro's name. In
future versions, this will be followed optional parameters. 

Currently, there are no system macros such as `.if`, `.then`, `.else` or loop
constructs. These are to be added in a future version.


## Internals 


### Structure 

The program has the most simple structure possible: It starts at the beginning,
runs to the end and then stops. No external routines are loaded, only system
library files are referenced (got to have your batteries). There are no objects.
The code just brute-forces its way top-down.

On the next lower level, TinkAsm is built up out of passes. Each pass is a
closed unit that ideally does one thing and one thing only. Information is
transmitted from one pass to another through a list of two-element tuples. The
first element of the tuple always contains the original line number of the
instruction so any problems can be referenced to the source code. The structure
of the second element depends on the pass. In the beginning, it is a simple
string with the content of the source code line. In the end, it is a list of
binary data representing the machine code. 

Information is only passed through these lists, not through "side channels". For
example, we don't define a flag in one pass to signal something to a pass lower
down. All information is contained in the lists that are passed. This doesn't
mean that the passes can't "collect" other information for later use. For
instance, full-line comments are put in a separate list so that the list file
can later access them. These, however, are not used by the following step but
only at the end.

(The sorta, kinda exception are counters for statistical use, for instance, how
many macros are defined and expanded. These are defined at the beginning of the
program to show that they are "global", so to speak.) 

Each pass starts by defining the empty list that will filled with the output of
this stage. Processing the previous list is usually handled by walking through
each line, modifying what needs to be changed, and then appending the processed
line to the new list. 

At the end, we offer the options of printing an
information string if we are in verbose mode, or dumping the complete list.

TinkAsm was developed primarily to code 65816 assembler, because there are lots
of great assemblers for the 6502 and 65c02 already out there; see FEHLT for an
overview.



### Coding Style


We try to avoid complicated IF/ELIF/ELSE constructs, using IF/CONTINUE instead.
For example, 

```
if cond:
    stuff1
else:
    stuff2
```

should be coded as

```
if cond:
    stuff1
    continue 

stuff 2
```
In the same manner, we usually use TRY/EXCEPT to get rid of the error condition
instead of including a complete construct with TRY/EXCEPT/ELSE/FINALLY.

The use of ELSE after FOR loops is prohibitted, as it confuses Python newbies no
end. 


### Notes on various opcodes

TinkAsm enforces the signature byte of `brk` for all processors.



# (OLD STUFF BELOW HERE) 


The 65816 is the ["big sibling"](http://en.wikipedia.org/wiki/WDC_65816/65802)
of the venerable 6502 8-bit processor. It is a hybrid processor that can run in
16-bit ("native") and 8-bit ("emulated") mode.

After bulding a 6502 machine as a hobby, [the "Übersquirrel" Mark Zero]
(http://uebersquirrel.blogspot.de/) (ÜSqM0), I found eight bits to be too
limiting. The 65816 is the logical next step up, since you can reuse the 8-bit
code at first. 

Unfortunately, assemblers for the 65816 are few and far between, so I decided I
would have to write my own. The first one was a simple single-pass assembler in
Forth, the ["Typist's Assembler for the 65816 in
Forth"](https://github.com/scotws/tasm65816). During that time, I developed
alternative, improved (at least I think so) syntax for the 6502 and 65816.

Because single-pass assemblers are limited and postfix notation can get on your
nerves after a while, I decided to write a second assembler in Python. This is
it.

See `docs/MANUAL.txt` for further information.





DIRECTIVES

### By tradition, assembler directives start with a dot.


        *
        .A16
        .A8
        .AXY16
        .AXY8
        .ADVANCE / .ADV
        .BYTE / .B
        .EMULATED
        .END 
        .LONG / .L
        .NATIVE
        .ORIGIN / .ORG
        .SKIP 
        .STRING / .S
        .STRING0 / .S0
        .STRINGLF / .SLF
        .WORD / .W
        .XY16
        .XY8
        = 
        @ 

### INTERNAL STRUCTURE

The Typist's Assembler was built with a few assumptions in mind. First, the code
to be assembled will be very small relative to current normal hardware
specifications: The total memory space of the 65816 is 16 MB, while my machine
has 16 GB of RAM. Because of this, saving space was a low priority. This is also
true for speed, because programs are going to be relatively short (if we had
wanted speed, we'd be using something like C or Go). The top priority was a
clear design that will break up the process in as many small steps as possible
to make the program easy to understand, easy to maintain and easy to change. 

For that reason, it was written in a "multipass" structure: Lots of little
steps, usually as loops, that do exactly one thing and then pass a list on to
the next step. 


(Tuples with original line number)




NOTES ON CODING STYLE 

Priority for the coding style was to make the program easy to understand -- and
thereby also easy to modify and adapt -- for people who might not be familiar
with the workings of an assembler. This is why Python was chosen as a language.
Speed and compactness of code are secondary; in both these cases, the
single-pass assember in Forth (https://github.com/scotws/tasm65816) is probably
the better choice. 

In practical terms, what this means is that IF constructs were used even in
cases when the result could have been achieved through calculation, because it
allows a quicker understanding of the logic involved. 


## SOURCES AND THANKS 

TinkAsm was inspired by Samuel A. Falvo II, who pointed me to a paper by Sarkar
*et al*, ["A Nanopass Framework for Compiler Education"](
https://www.google.de/url?sa=t&rct=j&q=&esrc=s&source=web&cd=1&cad=rja&uact=8&ved=0CCAQFjAAahUKEwi9-_29kffIAhWKVSwKHeM8CGk&url=http%3A%2F%2Fwww.cs.indiana.edu%2F~dyb%2Fpubs%2Fnano-jfp.pdf&usg=AFQjCNHxFyzbyfAHuc-cxgTggCzBbiI7bg&sig2=-YZn5Ztrh0Nj7-EoCMgL7A&bvm=bv.106674449,bs.2,d.bGg).
The authors discuss using compilers with multiple small passes for educational
purposes. 



