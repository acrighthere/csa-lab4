.org 0x000
    .word isr_stub

.org 0x010
_start:
    DI

    ; print_str(msg_addr)
    PUSH msg_hello
    CALL print_str

    HALT

print_str:
.loop:
    DUP
    LOAD
    DUP
    JZ .done
    OUT 1
    PUSH 4
    ADD
    JMP .loop
.done:
    POP
    POP
    RET

isr_stub:
    IRET

.org 0x100
msg_hello:
    .str "Hello, World!\n"
