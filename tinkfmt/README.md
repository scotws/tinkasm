# A Formatter for a Tinkerer's Assembler 

Scot W. Stevenson <scot.stevenson@gmail.com>

This is a formatter for 6502/65c02/65816 assembler code written in Typist's
Assembler Notation (TAN) for the Tinkerer's Assembler. The general philosophy is
take from the Go programming language (golang): Every source code file should be
formatted exactly the same. This makes it easier for everybody to understand
what is going on. Go comes with "gofmt", Tinkasm with "tinkfmt".

More importantly, Tinkfmt will allow you to just slap down code without any
though of formatting and let the machine handle that. So we can start off with
```
.mpu 65816
.origin 8000

.equ athena 01
.equ zeus 02
.equ poseidon 03

.native
loop lda.# 00 ; naught for all!
sta.x 1000
bra loop

.byte 01,    02, 03 ; bad spaces!
.end
```

and get this:

```
        .mpu 65816
        .origin 8000

        .equ athena   01
        .equ zeus     02
        .equ poseidon 03

        .native
loop            lda.# 00  ; naught for all!
                sta.x 1000
                bra loop

        .byte 01, 02, 03  ; bad spaces!
        .end
```

The basic rules are currently:

- All full-line comments are kept unchanged, including their indentation
- Inline comments are separated by two spaces from the last code character in
  the line (`lda.# 01  ; not too close`)
- All labels, directives, and opcodes are lower case (case-sensitive labels are
  a nasty source of errors)
- Label targets (including anonymous labels) start in the first column. Nothing
  else (execpt comments) may be there
- Spaces are used for indentation, not tabs
- The default "indentation unit" is eight characters
- Directives are indented by one unit (a tab's worth of spaces; but see blocks)
- Code is indented by two units (two tab's worth of spaces; but see blocks)
- There is only one space between terms of .byte, .word, and .long
- Blocks of code are formatted together (see below).

Tinkfmt requires a filename at start. The resulting, reformated file takes the
name of this file, while the original version is given the extension `.orig`. 

## Definition and Data Blocks

CURRENTLY NOT IMPLEMENTED

Definitions that follow each other are coded as blocks. For instance:

```
        .equ derrial 1000
        .equ hoban   2000
        .equ inara   3000
        .equ jayne   4000
        .equ kaylee  5000  ; should be higher
        .equ malcolm 6000
        .equ river   7000
        .equ simon   8000
        .equ zoe     9000
```

Note the parameter is in one column. Definition blocks are separated by at
least one empty line.

As definition blocks, data blocks are formatted in columns. They also break with
the normal indentation rules

```
my_data    .byte 01, 02, 03, 04, 05, 06
his_data   .byte 11, 12, 13, 14, 15, 16
yalls_data .byte a1, a2, a3, a4, a5, a6
```

Note the `.byte` directive is formatted in columns. If there is an in-line
comment behind the label, it is not considered for blocks.

See the TinkAsm manual in `docs/MANUAL.txt` for further information.

### DEVELOPMENT

This program is a hobby, and is developed in fits and starts. Feedback is most
welcome. 
