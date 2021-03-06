# Opcodes for the Tinkerer's Assembler for the 6502/65c02/65816 
# Scot W. Stevenson <scot.stevenson@gmail.com>
# First version: 23. Okt 2015
# This version: 03. Dec 2015

# OPCODE TABLE for the 6502

# Unused opcodes are left in the table and marked with "UNUSED" to give people
# the freedom to add undocumented functions. 

opcode_table = (
    (0x00, 'brk', 2),       # Assembler enforces signature byte
    (0x01, 'ora.zxi', 2),
    (0x02, 'UNUSED', 0),
    (0x03, 'UNUSED', 0),
    (0x04, 'UNUSED', 0),
    (0x05, 'ora.z', 2),
    (0x06, 'asl.z', 2),
    (0x07, 'UNUSED', 0),
    (0x08, 'php', 1),
    (0x09, 'ora.#', 2),
    (0x0a, 'asl.a', 1),
    (0x0b, 'UNUSED', 0),
    (0x0c, 'UNUSED', 0),
    (0x0d, 'ora', 3),
    (0x0e, 'asl', 3),
    (0x0f, 'UNUSED', 0),
    (0x10, 'bpl', 2),
    (0x11, 'ora.ziy', 2),
    (0x12, 'UNUSED', 0),
    (0x13, 'UNUSED', 0),
    (0x14, 'UNUSED', 0),
    (0x15, 'ora.zx', 2),
    (0x16, 'asl.zx', 2),
    (0x17, 'UNUSED', 0),
    (0x18, 'clc', 1),
    (0x19, 'ora.y', 3),
    (0x1a, 'UNUSED', 0),
    (0x1b, 'UNUSED', 0),
    (0x1c, 'UNUSED', ),
    (0x1d, 'ora.x', 3),
    (0x1e, 'asl.x', 3),
    (0x1f, 'UNUSED', 0),
    (0x20, 'jsr', 3),
    (0x21, 'and.zxi', 2),
    (0x22, 'UNUSED', 0),
    (0x23, 'UNUSED', 0),
    (0x24, 'bit.z', 2),
    (0x25, 'and.z', 2),
    (0x26, 'rol.z', 2),
    (0x27, 'UNUSED', 0),
    (0x28, 'plp', 1),
    (0x29, 'and.#', 2),
    (0x2a, 'rol.a', 1),
    (0x2b, 'UNUSED', 0),
    (0x2c, 'bit', 3),
    (0x2d, 'and', 3),
    (0x2e, 'rol', 3),
    (0x2f, 'UNUSED', 0),
    (0x30, 'bmi', 2),
    (0x31, 'and.ziy', 2),
    (0x32, 'UNUSED', ),
    (0x33, 'UNUSED', 0),
    (0x34, 'UNUSED', ),
    (0x35, 'and.zx', 2),
    (0x36, 'rol.zx', 2),
    (0x37, 'UNUSED', 0),
    (0x38, 'sec', 1),
    (0x39, 'and.y', 3),
    (0x3a, 'UNUSED', 0),
    (0x3b, 'UNUSED', 0),
    (0x3c, 'UNUSED', 0),
    (0x3d, 'and.x', 3),
    (0x3e, 'rol.x', 3),
    (0x3f, 'UNUSED', 0),
    (0x40, 'rti', 1),
    (0x41, 'eor.zxi', 2),
    (0x42, 'UNUSED', 0),
    (0x43, 'UNUSED', 0),
    (0x44, 'UNUSED', 0),
    (0x45, 'eor.z', 2),
    (0x46, 'lsr.z', 2),
    (0x47, 'UNUSED', 0),
    (0x48, 'pha', 1),
    (0x49, 'eor.#', 2),
    (0x4a, 'lsr.a', 1),
    (0x4b, 'UNUSED', 0),
    (0x4c, 'jmp', 3),
    (0x4d, 'eor', 3),
    (0x4e, 'lsr', 3),
    (0x4f, 'UNUSED', 0),
    (0x50, 'bvc', 2),
    (0x51, 'eor.ziy', 2),
    (0x52, 'UNUSED', 0),
    (0x53, 'UNUSED', 0),
    (0x54, 'UNUSED', 0),
    (0x55, 'eor.zx', 2),
    (0x56, 'lsr.zx', 2),
    (0x57, 'UNUSED', 0),
    (0x58, 'cli', 1),
    (0x59, 'eor.y', 3),
    (0x5a, 'UNUSED', 0),
    (0x5b, 'UNUSED', 0),
    (0x5c, 'UNUSED', 0),
    (0x5d, 'eor.x', 3),
    (0x5e, 'lsr.x', 3),
    (0x5f, 'UNUSED', 0),
    (0x60, 'rts', 1),
    (0x61, 'adc.zxi', 2),
    (0x62, 'UNUSED', 0),
    (0x63, 'UNUSED', 0),
    (0x64, 'UNUSED', 0),
    (0x65, 'adc.z', 2),
    (0x66, 'ror.z', 2),
    (0x67, 'UNUSED', 0),
    (0x68, 'pla', 1),
    (0x69, 'adc.#', 2),
    (0x6a, 'ror.a', 1),
    (0x6b, 'UNUSED', 0),
    (0x6c, 'jmp.i', 3),
    (0x6d, 'adc', 3),
    (0x6e, 'ror', 3),
    (0x6f, 'UNUSED', 0),
    (0x70, 'bvs', 2),
    (0x71, 'adc.ziy', 2),
    (0x72, 'UNUSED', 0),
    (0x73, 'UNUSED', 0),
    (0x74, 'UNUSED', 0),
    (0x75, 'adc.zx', 2),
    (0x76, 'ror.zx', 2),
    (0x77, 'UNUSED', 0),
    (0x78, 'sei', 1),
    (0x79, 'adc.y', 3),
    (0x7a, 'UNUSED', 0),
    (0x7b, 'UNUSED', 0),
    (0x7c, 'UNUSED', 0),
    (0x7d, 'adc.x', 3),
    (0x7e, 'ror.x', 3),
    (0x7f, 'UNUSED', 0),
    (0x80, 'UNUSED', 0),
    (0x81, 'sta.zxi', 2),
    (0x82, 'UNUSED', 0),
    (0x83, 'UNUSED', 0),
    (0x84, 'sty.z', 2),
    (0x85, 'sta.z', 2),
    (0x86, 'stx.z', 2),
    (0x87, 'UNUSED', 0),
    (0x88, 'dey', 1),
    (0x89, 'UNUSED', 0),
    (0x8a, 'txa', 1),
    (0x8b, 'UNUSED', 0),
    (0x8c, 'sty', 3),
    (0x8d, 'sta', 3),
    (0x8e, 'stx', 3),
    (0x8f, 'UNUSED', 0),
    (0x90, 'bcc', 2),
    (0x91, 'sta.ziy', 2),
    (0x92, 'UNUSED', 0),
    (0x93, 'UNUSED', 0),
    (0x94, 'sty.zx', 2),
    (0x95, 'sta.zx', 2),
    (0x96, 'stx.zy', 2),
    (0x97, 'UNUSED', 0),
    (0x98, 'tya', 1),
    (0x99, 'sta.y', 3),
    (0x9a, 'txs', 1),
    (0x9b, 'UNUSED', 0),
    (0x9c, 'UNUSED', 0),
    (0x9d, 'sta.x', 3),
    (0x9e, 'UNUSED', 0),
    (0x9f, 'UNUSED', 0),
    (0xa0, 'ldy.#', 2),
    (0xa1, 'lda.zxi', 2),
    (0xa2, 'ldx.#', 2),
    (0xa3, 'UNUSED', 0),
    (0xa4, 'ldy.z', 2),
    (0xa5, 'lda.z', 2),
    (0xa6, 'ldx.z', 2),
    (0xa7, 'UNUSED', 0),
    (0xa8, 'tay', 1),
    (0xa9, 'lda.#', 2),
    (0xaa, 'tax', 1),
    (0xab, 'UNUSED', 0),
    (0xac, 'ldy', 3),
    (0xad, 'lda', 3),
    (0xae, 'ldx', 3),
    (0xaf, 'UNUSED', 0),
    (0xb0, 'bcs', 2),
    (0xb1, 'lda.ziy', 2),
    (0xb2, 'UNUSED', 0),
    (0xb3, 'UNUSED', 0),
    (0xb4, 'ldy.zx', 2),
    (0xb5, 'lda.zx', 2),
    (0xb6, 'ldx.zy', 2),
    (0xb7, 'UNUSED', 0),
    (0xb8, 'clv', 1),
    (0xb9, 'lda.y', 3),
    (0xba, 'tsx', 1),
    (0xbb, 'UNUSED', 0),
    (0xbc, 'ldy.x', 3),
    (0xbd, 'lda.x', 3),
    (0xbe, 'ldx.y', 3),
    (0xbf, 'UNUSED', 0),
    (0xc0, 'cpy.#', 2),
    (0xc1, 'cmp.zxi', 2),
    (0xc2, 'UNUSED', 0),
    (0xc3, 'UNUSED', 0),
    (0xc4, 'cpy.z', 2),
    (0xc5, 'cmp.z', 2),
    (0xc6, 'dec.z', 2),
    (0xc7, 'UNUSED', 0),
    (0xc8, 'iny', 1),
    (0xc9, 'cmp.#', 2),
    (0xca, 'dex', 1),
    (0xcb, 'UNUSED', 0),
    (0xcc, 'cpy', 3),
    (0xcd, 'cmp', 3),
    (0xce, 'dec', 3),
    (0xcf, 'UNUSED', 0),
    (0xd0, 'bne', 2),
    (0xd1, 'cmp.ziy', 2),
    (0xd2, 'UNUSED', 0),
    (0xd3, 'UNUSED', 0),
    (0xd4, 'UNUSED', 0),
    (0xd5, 'cmp.zx', 2),
    (0xd6, 'dec.zx', 2),
    (0xd7, 'UNUSED', 0),
    (0xd8, 'cld', 1),
    (0xd9, 'cmp.y', 3),
    (0xda, 'UNUSED', 0),
    (0xdb, 'UNUSED', 0),
    (0xdc, 'UNUSED', 0),
    (0xdd, 'cmp.x', 3),
    (0xde, 'dec.x', 3),
    (0xdf, 'UNUSED', 0),
    (0xe0, 'cpx.#', 2),
    (0xe1, 'sbc.zxi', 2),
    (0xe2, 'UNUSED', 0),
    (0xe3, 'UNUSED', 0),
    (0xe4, 'cpx.z', 2),
    (0xe5, 'sbc.z', 2),
    (0xe6, 'inc.z', 2),
    (0xe7, 'UNUSED', 0),
    (0xe8, 'inx', 1),
    (0xe9, 'sbc.#', 2),
    (0xea, 'nop', 1),
    (0xeb, 'UNUSED', 0),
    (0xec, 'cpx', 3),
    (0xed, 'sbc', 3),
    (0xee, 'inc', 3),
    (0xef, 'UNUSED', 0),
    (0xf0, 'beq', 2),
    (0xf1, 'sbc.ziy', 2),
    (0xf2, 'UNUSED', 0),
    (0xf3, 'UNUSED', 0),
    (0xf4, 'UNUSED', 0),
    (0xf5, 'sbc.zx', 2),
    (0xf6, 'inc.zx', 2),
    (0xf7, 'UNUSED', 0),
    (0xf8, 'sed', 1),
    (0xf9, 'sbc.y', 3),
    (0xfa, 'UNUSED', 0),
    (0xfb, 'UNUSED', 0),
    (0xfc, 'UNUSED', 0),
    (0xfd, 'sbc.x', 3),
    (0xfe, 'inc.x', 3),
    (0xff, 'UNUSED', 0)) 
