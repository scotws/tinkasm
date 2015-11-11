# A Tinkerer's Assembler for the 6502/65c02/65816

Scot W. Stevenson <scot.stevenson@gmail.com>


### TL;DR

This is a PRE-ALPHA version of a easily modified multi-pass assembler for the
6502/65c02/65816 8/16-bit MPUs in Python 3. PRE-ALPHA means "it doesn't work
yet". Once BETA is reached, it will be announced on 6502.org.

### WHAT'S ALL THIS HERE NOW ANYWAY?

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
