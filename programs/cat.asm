%define FLAG_ADDR  0x200
%define CHAR_ADDR  0x204
%define EOF_CHAR   0

.org 0x000
    .word isr_input

.org 0x010
_start:
    ; Initialize flag
    PUSH 0
    STOREA FLAG_ADDR

    EI


.wait_loop:
    LOADA FLAG_ADDR
    JNZ .exit
    JMP .wait_loop

.exit:
    HALT

isr_input:
    IN 0
    DUP
    JZ .eof


    OUT 1
    IRET

.eof:
    POP
    PUSH 1
    STOREA FLAG_ADDR
    IRET
