%define FLAG_DONE   0x200
%define BUF_LEN     0x204
%define BUF_START   0x208

.org 0x000
    .word isr_input

.org 0x010
_start:
    DI
    ; Initialize
    PUSH 0
    STOREA FLAG_DONE
    PUSH 0
    STOREA BUF_LEN

    ; Print prompt
    PUSH msg_prompt
    CALL print_str

    EI

.wait:
    LOADA FLAG_DONE
    JZ .wait

    DI
    LOADA BUF_LEN
    PUSH 4
    MUL
    PUSH BUF_START
    ADD
    PUSH 0
    SWAP
    STORE

    PUSH msg_hello
    CALL print_str


    PUSH BUF_START
    CALL print_str

    PUSH msg_suffix
    CALL print_str

    HALT

print_str:
.ps_loop:
    DUP
    LOAD
    DUP
    JZ .ps_done
    OUT 1
    PUSH 4
    ADD
    JMP .ps_loop
.ps_done:
    POP
    POP
    RET

isr_input:
    IN 0

    DUP
    PUSH 10
    EQ
    JNZ .newline

    DUP
    PUSH 13
    EQ
    JNZ .newline

    DUP
    JZ .eof_char

    LOADA BUF_LEN
    DUP
    PUSH 253
    GT
    JNZ .skip_store
    PUSH 4
    MUL
    PUSH BUF_START
    ADD
    SWAP
    STORE
    LOADA BUF_LEN
    PUSH 1
    ADD
    STOREA BUF_LEN
    IRET

.skip_store:
    POP
    POP
    IRET

.newline:
    POP
    PUSH 1
    STOREA FLAG_DONE
    IRET

.eof_char:
    POP
    PUSH 1
    STOREA FLAG_DONE
    IRET

.org 0x600
msg_prompt:
    .str "What is your name?\n"
msg_hello:
    .str "Hello, "
msg_suffix:
    .str "!\n"
