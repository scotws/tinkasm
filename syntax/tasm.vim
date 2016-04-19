" Vim Syntax File for a Typist's Assembler Notation, Python version 
" Language: Assembler (6502/65c02/65816 8/16-bit CPU) 
" Maintainer: Scot W. Stevenson <scot.stevenson@gmail.com>
" Latest Revision: 17. April 2016

" This script is distributed in the hope that it will be useful,
" but WITHOUT ANY WARRANTY; without even the implied warranty of
" MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. Use at your
" own risk.

" Don't load this file twice
if exists("b:current_syntax")
	finish
endif


" === Basic Setup ===
setlocal iskeyword=!,@,33-35,%,$,38-64,91-96,a-z,123-126,128-255
setlocal ts=4 shiftwidth=4 expandtab tw=80 nowrap number fo=cronq1


" === Keyword Lists ===
" Keywords for normal 65816 assember mnemonics 
syn keyword tasmMnemonics 
    \ adc adc.# adc.d adc.dil adc.di adc.diy adc.dily adc.dx adc.dxi adc.l 
    \ adc.lx adc.s adc.siy adc.x adc.y 
    \ and and.# and.d and.di and.dil and.dily and.diy and.dx and.dxi 
    \ and.l and.lx and.s and.siy and.x and.y asl asl.a asl.d 
    \ asl.dx asl.x
    \ bit bit.# bit.d bit.dxi bit.x 
    \ clc cld cli clv
    \ cmp cmp.# cmp.d cmp.di cmp.dil cmp.diy cmp.dily cmp.dx cmp.dxi 
    \ cmp.l cmp.lx cmp.s cmp.x cmp.y cmp.siy
    \ cpx cpx.# cpx.d
    \ cpy cpy.# cpy.d
    \ dec dec.a dec.d dec.dx dec.x dex dey 
    \ eor eor.# eor.d eor.dil eor.diy eor.di eor.dx eor.dxi eor.l eor.lx
    \ eor.s eor.siy 
    \ eor.x eor.y 
    \ inc inc.a inc.d inc.dx inc.x  
    \ inx iny
    \ lda lda.# lda.d lda.di lda.dil lda.diy lda.dily lda.dx
    \ lda.dxi lda.l lda.lx lda.s lda.siy lda.x lda.y 
    \ ldx ldx.# ldx.d ldx.y
    \ ldy ldy.# ldy.d ldy.dx ldy.x
    \ lsr lsr.a lsr.d lsr.dily lsr.dx lsr.x
    \ mvn mvp
    \ ora ora.# ora.d ora.di ora.dil ora.diy ora.dily ora.dx ora.dxi ora.l 
    \ ora.lx ora.s ora.x ora.y ora.siy
    \ pha phb phd phe.# phe.d phe.r phk php phx phy 
    \ pla plb pld plp plx ply
    \ rol rol.a rol.d rol.dx rol.x
    \ ror ror.a ror.d ror.dx ror.x
    \ sbc sbc.# sbc.d sbc.di sbc.dil sbc.dily sbc.diy sbc.dx sbc.dxi 
    \ sbc.l sbc.lx sbc.s sbc.siy sbc.x sbc.y
    \ sec sed sei 
    \ sta sta.d sta.di sta.dil sta.dily sta.diy sta.dx sta.dxi 
    \ sta.l sta.lx sta.s sta.siy sta.x sta.y
    \ stx stx.d stx.dy
    \ sty sty.d sty.dx
    \ stz stz.d stz.dx stz.x
    \ tax tay tcd tcs tdc trb trb.d tsb tsb.d tsc tsx txa txs txy tya tyx
    \ wai
    \ xba


" Keywords for 6502/65c02 direct page assember mnemonics 
syn keyword tasmMnemonics 
    \ ora.zxi tsb.z ora.z asl.z rmb0.z
    \ ora.ziy ora.zi trb.z ora.zx asl.zx rmb1.z
    \ and.zxi bit.z and.z rol.z rmb2.z 
    \ and.ziy and.zi bit.zxi and.zx rol.zx rmb3.z
    \ eor.zxi eor.z lsr.z rmb4.z 
    \ eor.ziy eor.zi eor.zx lsr.zx rmb5.z 
    \ adc.zxi stz.z adc.z ror.z rmb6.z 
    \ adc.ziy adc.zi stz.zx adc.zx ror.zx rmb7.z
    \ sta.zxi sty.z sta.z stx.z smb0.z
    \ sta.ziy sta.zi sty.zx sta.zx stx.zy smb1.z
    \ lda.zxi ldy.z lda.z ldx.z smb2.z
    \ lda.ziy lda.zi ldy.zx lda.zx ldx.zy smb3.z
    \ cmp.zxi cpy.z cmp.z dec.z smb4.z 
    \ cmp.ziy cmp.zi cmp.zx dec.zx smb5.z
    \ cmp.sbc.zxi cpx.z sbc.z inc.z smb6.z
    \ sbc.ziy sbc.zi sbc.zx inc.zx smb7.z


" Keywords for 6502/65c02/65816 branch and jump instructions
syn keyword tasmFlow 
    \ bra bra.l 
    \ bcc bcs beq bmi bne bpl bvc bvs
    \ jmp jmp.i jmp.il jmp.l jmp.xi jsr jsr.l jsr.xi
    \ rts rts.l rti 

" Keywords for Rockwell 65c02 branch and jump instructions
syn keyword tasmFlow 
    \ bbr0 bbr1 bbr2 bbr3 bbr4 bbr5 bbr6 bbr7
    \ bbs0 bbs1 bbs2 bbs3 bbs4 bbs5 bbs6 bbs7
 
" Keywords for 65816 special mnemonics (stp, rep ) 
syn keyword tasmSpecial brk cop xce rep sep stp wai

" Keywords for 65816 traditional instructions (pea, pei)
syn keyword tasmLegacy brl jml jsl pea pei per rtl  

" Keywords for 65816 functional nops (nop, wdm)  
syn keyword tasmBoring nop wdm

" Keywords for directives of the Tinkerer's Assembler
" See https://github.com/scotws/tinkasm
syn keyword tasmDirective 
    \ .advance .adv .emulated .end .include .mpu .native .origin .skip .*
    \ .a8 .a16 .xy8 .xy16 .axy8 .axy16
    \ .a8! .a16! .xy8! .xy16! .native! .emulated!
    \ .byte .b .word .w .long .l 
    \ .string .str .string0 .str0 .stringlf .strlf
    \ .lsb .msb .bank
    \ .macro .endmacro .invoke
    \ .equ = @ + - / * .lshift .rshift .and .or .xor .invert

" Keywords for programmer's notes. The last two are German
syn keyword tasmTodo TODO CHECK FIXME HIER FEHLT


" === Define Numbers ===
" End of line version
syn match tasmNumber ' \d\+\n' display 
syn match tasmNumber ' [-+]\d+\n' display 
syn match tasmNumber ' \x\+\n' display 
syn match tasmNumber ' [-+]\x+\n' display 
" String at end version
syn match tasmNumber ' \d\+ ' display 
syn match tasmNumber ' [-+]\d+ ' display 
syn match tasmNumber ' \x\+ ' display 
syn match tasmNumber ' [-+]\x+ ' display 



" === All Other Definitions ===

" Define comments
syn match tasmComment "\v;.*$"

" Define Strings
syn region tasmString start='"' end='"'

" Define Python Code Instert (experimental)
syn region pythonString start='{' end='}'

" === Define our own color system === 

hi tasmBoring ctermfg=LightGrey
hi tasmDirective ctermfg=Magenta
hi tasmForth ctermfg=Magenta
hi tasmFlow ctermfg=blue
hi tasmLabelDirs ctermfg=blue
hi tasmMnemonics cterm=bold
hi tasmSpecial ctermfg=red
hi tasmPython ctermfg=red cterm=bold

" === Link definitions === 

hi def link tasmLegacy     Error
hi def link tasmComment    Comment 
hi def link tasmNumber     Constant
hi def link tasmString     String
hi def link tasmTodo	   Todo
hi def link pythonString   tasmPython

" We're done
let b:current_syntax = "tasm"
