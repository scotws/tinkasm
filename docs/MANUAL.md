# A Tinkerer's Assembler for the 6502/65c02/65816

Scot W. Stevenson <scot.stevenson@gmail.com>


### Overview

The Tinkerer's Assembler (TinkAsm for short) is a multi-pass assembler for the
6502, 65c02, and 65816 8/16-MPUs. It is written in simple Python 3 code with the
intention to give computer hobbyists an assembler that is not only easy to
understand, but also easy to modify and adapt to their own needs. It uses the
Typist's Assembler Notation (TAN) and is released under the GPL. 


### Basic Idea


(Assemblers involve all kinds of complicated words like parsers, lexers)

TinkAsm, in contrast, is written in a series of simple passes that (usually) do
exactly one thing. 

It is written in Python, probably the most widespread easily accessable
language. What is more, it is written in *simple* Python. There are no objects,
and though some simple list comprehensions and enumerations are used, it relies
heavily on FOR/ELIF/ELSE and TRY/EXCEPT constructs. 


This, then, is an assembler for non-computer scientists - for those of us who
associate "the Wizard Book" with *Lord of the Rings* and "the Dragon Book" with *A Song
of Ice and Fire*. 


### Drawbacks

The first problem is that as an assembler, TinkAsm is horribly, horribly
inefficient. 


### Internal Structure 





### (OLD STUFF BELOW HERE) 


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

### DEVELOPMENT

This program is a hobby, and is developed in fits and starts. Feedback is most
welcome. 



- Requires Python 3.4 or later. Will not run with Python 2.7. 
- Does not distinguish between upper and lower case (internally, all is converted to lower case)



### PARAMETERS

-i --input      - Input assembler file (required) 
-o --output     - Output file for the binary code, default is tasm.bin 
-l --listing    - Output file for the listing, default is tasm.txt  
-v --verbose    - Print more info about each assembly step
-d --dump       - Dump state of inbetween steps, produces lots of output


DIRECTIVES

### By tradition, assembler directives start with a dot.


        *
        .A16
        .A8
        .AXY16
        .AXY8
        .BYTE / .B
        .EMULATED
        .END 
        .LONG / .L
        .NATIVE
        .ORIGIN
        .STRING / .STR
        .STRING0 / .STR0
        .STRINGLF / .STRLF
        .WORD / .W
        .XY16
        .XY8
        = 

### INTERNAL STRUCTURE

The Typist's Assembler was built with a few assumptions in mind. First, the code to be assembled will be very small relative to current normal hardware specifications: The total memory space of the 65816 is 16 MB, while my machine 
has 16 GB of RAM. Because of this, saving space was a low priority. This is also true for speed, because programs are going to be relatively short (if we had wanted speed, we'd be using something like C or Go). The top priority was a clear design that will break up the process in as many small steps as possible to make the program easy to understand, easy to maintain and easy to change. 

For that reason, it was written in a "multipass" structure: Lots of little steps, usually as loops, that do exactly one thing and then pass a list on to the next step. 


(Tuples with original line number)




NOTES ON CODING STYLE 

Priority for the coding style was to make the program easy to understand -- and thereby also easy to modify and adapt -- for people who might not be familiar with the workings of an assembler. This is why Python was chosen as a language. Speed and compactness of code are secondary; in both these cases, the single-pass assember in Forth (https://github.com/scotws/tasm65816) is probably the better choice. 

In practical terms, what this means is that IF constructs were used even in cases when the result could have been achieved through calculation, because it allows a quicker understanding of the logic involved. 




