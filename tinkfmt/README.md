# A Formatter for a Tinkerer's Assembler 

Scot W. Stevenson <scot.stevenson@gmail.com>

This is a formatter for 6502/65c02/65816 assembler code written in Typist's
Assembler Notation (TAN) for the Tinkerer's Assembler. The general philosophy is
take from the Go programming language (golang): Every source code file should be
formatted exactly the same. This makes it easier for everybody to understand
what is going on. Go comes with "gofmt", TinkAsm with "tinkfmt".

The basic rules are currently:

- Comments are kept unchanged
- All directives and opcodes are lower case 
- Label target (including anonymous labels) start in the first column
- All directives are indented by one unit (a tab's worth of spaces)
- All code is indented by two units (two tab's worth of spaces)
- Spaces are used for indentation, not tabs
- The default indentation unit is eight characters
- There is only one space between terms

Tinkfmt requires a filename at start. The resulting, reformated file takes the
name of this file, while the original version is given the extension `.old`. The
converter uses a temporary file to avoid a loss of data during a crash. 

See the TinkAsm manual in `docs/MANUAL.txt` for further information.

### DEVELOPMENT

This program is a hobby, and is developed in fits and starts. Feedback is most
welcome. 
