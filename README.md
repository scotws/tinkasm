# A Tinkerer's Assembler for the 6502/65c02/65816

Scot W. Stevenson <scot.stevenson@gmail.com>

**THIS BRANCH IS CURRENTLY BEING REWRITTEN AND IS NOT STABLE**

This is a BETA version of a easily modified multi-pass assembler for the
6502/65c02/65816 8/16-bit MPUs in Python 3. It uses Simpler Assembler Notation
(SAN), see https://github.com/scotws/SAN for details. 

BETA means "it should probably all work as intended, but it probably doesn't".
Use at your own risk. 

"Easily modified" means that is is not an assembler based on lexers and parsers,
but a large number of simple, single passes that modify one thing. It is also
intentionally written in "primitive" Python. The idea is to provide a base so
hobbyists who are not computer scientists can play around with assemblers --
hence the name. 

See `docs/MANUAL.txt` for further information.

### DEVELOPMENT

This program is a hobby, and is developed in fits and starts. Feedback is most
welcome. 
