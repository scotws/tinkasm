# Opcodes for the Tinkerer's Assembler for the 65816 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 23. Okt 2015
# This version: 18. Nov 2015

# The Immediate Mode forms (<opc>.#) are listed as two-byte instructions and
# then expanded by the assembler when the relevant instruction is called during
# 16 bit modes

opcode_table = (
    (0x00, 'brk', 2),       # Assembler enforces signature byte
    (0x01, 'ora.dxi', 2),
    (0x02, 'cop', 2),
    (0x03, 'ora.s', 2),
    (0x04, 'tsb.d', 2),
    (0x05, 'ora.d', 2),
    (0x06, 'asl.d', 2),
    (0x07, 'ora.dil', 2),
    (0x08, 'php', 1),
    (0x09, 'ora.#', 2),
    (0x0a, 'asl.a', 1),
    (0x0b, 'phd', 1),
    (0x0c, 'tsb', 3),
    (0x0d, 'ora', 3),
    (0x0e, 'asl', 3),
    (0x0f, 'ora.l', 4),
    (0x10, 'bpl', 2),
    (0x11, 'ora.diy', 2),
    (0x12, 'ora.di', 2),
    (0x13, 'ora.siy', 2),
    (0x14, 'trb.d', 2),
    (0x15, 'ora.dx', 2),
    (0x16, 'asl.dx', 2),
    (0x17, 'ora.dily', 2),
    (0x18, 'clc', 1),
    (0x19, 'ora.y', 3),
    (0x1a, 'inc.a', 1),
    (0x1b, 'tcs', 1),
    (0x1c, 'trb', 3),
    (0x1d, 'ora.x', 3),
    (0x1e, 'asl.x', 3),
    (0x1f, 'ora.lx', 4),
    (0x20, 'jsr', 3),
    (0x21, 'and.dxi', 2),
    (0x22, 'jsr.l', 4),
    (0x23, 'and.s', 2),
    (0x24, 'bit.d', 2),
    (0x25, 'and.d', 2),
    (0x26, 'rol.d', 2),
    (0x27, 'and.dil', 2),
    (0x28, 'plp', 1),
    (0x29, 'and.#', 2),
    (0x2a, 'rol.a', 2),
    (0x2b, 'pld', 1),
    (0x2c, 'bit', 3),
    (0x2d, 'and', 3),
    (0x2e, 'rol', 3),
    (0x2f, 'and.l', 4),
    (0x30, 'bmi', 2),
    (0x31, 'and.diy', 2),
    (0x32, 'and.di', 2),
    (0x33, 'and.siy', 2),
    (0x34, 'bit.dx', 2),
    (0x35, 'and.dx', 2),
    (0x36, 'rol.dx', 2),
    (0x37, 'and.dily', 2),
    (0x38, 'sec', 1),
    (0x39, 'and.y', 3),
    (0x3a, 'dec.a', 1),
    (0x3b, 'tsc', 1),
    (0x3c, 'bit.x', 3),
    (0x3d, 'and.x', 3),
    (0x3e, 'rol.x', 3),
    (0x3f, 'and.lx', 4),
    (0x40, 'rti', 1),
    (0x41, 'eor.dxi', 2),
    (0x42, 'wdm', 2),       # Should produce warning
    (0x43, 'eor.s', 2),
    (0x44, 'mvp', 3),
    (0x45, 'eor.d', 2),
    (0x46, 'lsr.d', 2),
    (0x47, 'eor.dil', 2),
    (0x48, 'pha', 1),
    (0x49, 'eor.#', 2),
    (0x4a, 'lsr.a', 1),
    (0x4b, 'phk', 1),
    (0x4c, 'jmp', 3),
    (0x4d, 'eor', 3),
    (0x4e, 'lsr', 3),
    (0x4f, 'eor.l', 4),
    (0x50, 'bvc', 2),
    (0x51, 'eor.diy', 2),
    (0x52, 'eor.di', 2),
    (0x53, 'eor.siy', 2),
    (0x54, 'mvn', 3),
    (0x55, 'eor.dx', 2),
    (0x56, 'lsr.dx', 2),
    (0x57, 'eor.dily', 2),
    (0x60, 'rts', 1),
    (0x61, 'adc.dxi', 2),
    (0x62, 'phe.r', 3),
    (0x63, 'adc.s', 2),
    (0x64, 'stz.d', 2),
    (0x65, 'adc.d', 2),
    (0x66, 'ror.d', 2),
    (0x67, 'adc.dil', 2),
    (0x68, 'pla', 1),
    (0x69, 'adc.#', 2),
    (0x6a, 'ror.a', 1),
    (0x6b, 'rts.l', 4),
    (0x6c, 'jmp.i', 3),
    (0x6d, 'adc', 3),
    (0x6e, 'ror', 3),
    (0x6f, 'adc.l', 3),
    (0x70, 'bvs', 2),
    (0x71, 'adc.diy', 2),
    (0x72, 'adc.di', 2),
    (0x73, 'adc.siy', 2),
    (0x74, 'stx.dx', 2),
    (0x75, 'adx.dx', 2),
    (0x76, 'ror.dx', 2),
    (0x77, 'adc.dy', 2),
    (0x78, 'sei', 1),
    (0x79, 'acd.y', 3),
    (0x7a, 'ply', 1),
    (0x7b, 'tdc', 1),
    (0x7c, 'jmp.xi', 3),
    (0x7d, 'adc.x', 3),
    (0x7e, 'ror.x', 3),
    (0x7f, 'adc.lx', 4),
    (0x80, 'bra', 2),
    (0x81, 'sta.dxi', 2),
    (0x82, 'bra.l', 3),
    (0x83, 'sta.s', 2),
    (0x84, 'sty.d', 2),
    (0x85, 'sta.d', 2),
    (0x86, 'stx.d', 2),
    (0x87, 'sta.dil', 2),
    (0x88, 'dey', 1),
    (0x89, 'bit.#', 2),
    (0x8a, 'txa', 1),
    (0x8b, 'phb', 1),
    (0x8c, 'sty', 3),
    (0x8d, 'sta', 3),
    (0x8e, 'stx', 3),
    (0x8f, 'sta.l', 4),
    (0x90, 'bcc', 2),
    (0x91, 'sta.diy', 2),
    (0x92, 'sta.di', 2),
    (0x93, 'sta.siy', 2),
    (0x94, 'sty.dx', 2),
    (0x95, 'sta.dx', 2),
    (0x96, 'stx.dy', 2),
    (0x97, 'sta.dily', 2),
    (0x98, 'tya', 1),
    (0x99, 'sta.y', 3),
    (0x9a, 'txs', 1),
    (0x9b, 'txy', 1),
    (0x9c, 'stz', 3),
    (0x9d, 'sta.x', 3),
    (0x9e, 'stz.x', 3),
    (0x9f, 'sta.lx', 4),
    (0xa0, 'ldy.#', 2),
    (0xa1, 'lda.dxi', 2),
    (0xa2, 'ldx.#', 2),
    (0xa3, 'lda.s', 2),
    (0xa4, 'ldy.d', 2),
    (0xa5, 'lda.d', 2),
    (0xa6, 'ldx.d', 2),
    (0xa7, 'lda.dil', 2),
    (0xa8, 'tay', 1),
    (0xa9, 'lda.#', 2),
    (0xaa, 'tax', 1),
    (0xab, 'plb', 1),
    (0xac, 'ldy', 3),
    (0xad, 'lda', 3),
    (0xae, 'ldx', 3),
    (0xaf, 'lda.l', 4),
    (0xb0, 'bcs', 2),
    (0xb1, 'lda.diy', 2),
    (0xb2, 'lda.di', 2),
    (0xb3, 'lda.siy', 2),
    (0xb4, 'ldy.dx', 2),
    (0xb5, 'lda.dx', 2),
    (0xb6, 'ldx.dy', 2),
    (0xb7, 'lda.dy', 2),
    (0xb8, 'clv', 1),
    (0xb9, 'lda.y', 3),
    (0xba, 'tsx', 1),
    (0xbb, 'tyx', 1),
    (0xbc, 'ldy.x', 3),
    (0xbd, 'lda.x', 3),
    (0xbe, 'ldx.y', 3),
    (0xbf, 'lda.lx', 4),
    (0xc0, 'cpy.#', 2),
    (0xc1, 'cpy.dxi', 2),
    (0xc2, 'rep', 2),
    (0xc3, 'cmp.s', 2),
    (0xc4, 'cpy.d', 2),
    (0xc5, 'cmp.d', 2),
    (0xc6, 'dec.d', 2),
    (0xc7, 'cmp.dil', 2),
    (0xc8, 'iny', 1),
    (0xc9, 'cmp.#', 2),
    (0xca, 'dex', 1),
    (0xcb, 'wai', 1),
    (0xcc, 'cpy', 3),
    (0xcd, 'cmp', 3),
    (0xce, 'dec', 3),
    (0xcf, 'cmp.l', 4),
    (0xd0, 'bne', 2),
    (0xd1, 'cmp.diy', 2),
    (0xd2, 'cmp.di', 2),
    (0xd3, 'cmp.siy', 2),
    (0xd4, 'phe.d', 2),
    (0xd5, 'cmp.dx', 2),
    (0xd6, 'dec.dx', 2),
    (0xd7, 'cmp.dily', 2),
    (0xd8, 'cld', 1),
    (0xd9, 'cmp.y', 3),
    (0xda, 'phx', 1),
    (0xdb, 'stp', 1),
    (0xdc, 'jmp.il', 3),
    (0xdd, 'cmp.x', 3),
    (0xde, 'dec.x', 3),
    (0xdf, 'cmp.lx', 4),
    (0xe0, 'cpx.#', 2),
    (0xe1, 'sbc.dxi', 2),
    (0xe2, 'sep', 2),
    (0xe3, 'sbc.s', 2),
    (0xe4, 'cpx.d', 2),
    (0xe5, 'sbc.d', 2),
    (0xe6, 'inc.d', 2),
    (0xe7, 'sbc.dil', 2),
    (0xe8, 'inx', 1),
    (0xe9, 'sbc.#', 2),
    (0xea, 'nop', 1),
    (0xeb, 'xba', 1),
    (0xec, 'cpx', 3),
    (0xed, 'sbc', 3),
    (0xee, 'inc', 3),
    (0xef, 'sbc.l', 4),
    (0xf0, 'beq', 2),
    (0xf1, 'sbc.diy', 2),
    (0xf2, 'sbc.di', 2),
    (0xf3, 'sbc.siy', 2),
    (0xf4, 'phe.#', 3),
    (0xf5, 'sbc.dx', 2),
    (0xf6, 'inc.dx', 2),
    (0xf7, 'sbc.dily', 2),
    (0xf8, 'sec', 1),
    (0xf9, 'sbc.y', 3),
    (0xfa, 'plx', 1),
    (0xfb, 'xce', 1),
    (0xfc, 'jsr.xi', 3),
    (0xfd, 'sbc.x', 3),
    (0xfe, 'inc.x', 3),
    (0xff, 'sbc.lx', 4)) 
