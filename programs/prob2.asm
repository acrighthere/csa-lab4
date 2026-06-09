%define N        100        ; first N natural numbers
%define I        0x200      ; loop counter i
%define SUM      0x204      ; running sum of i
%define SUMSQ    0x208      ; running sum of i*i

.org 0x000
    .word isr_stub

.org 0x010
_start:
    DI

    PUSH 1
    STOREA I
    PUSH 0
    STOREA SUM
    PUSH 0
    STOREA SUMSQ

.loop:
    LOADA I
    PUSH N
    GT
    JNZ .done               ; while i <= N

    ; sum += i
    LOADA SUM
    LOADA I
    ADD
    STOREA SUM

    ; sumsq += i*i
    LOADA SUMSQ
    LOADA I
    LOADA I
    MUL
    ADD
    STOREA SUMSQ

    ; i += 1
    LOADA I
    PUSH 1
    ADD
    STOREA I
    JMP .loop

.done:
    ; result = (sum)^2 - (sum of squares)
    LOADA SUM
    LOADA SUM
    MUL
    LOADA SUMSQ
    SUB
    CALL print_int
    PUSH 10
    OUT 1
    HALT

%define PRI_VAL  0x300
%define PRI_BUF  0x304
%define PRI_LEN  0x360

print_int:
    STOREA PRI_VAL
    LOADA PRI_VAL
    JNZ .pi_nonzero
    PUSH 48
    OUT 1
    RET
.pi_nonzero:
    PUSH 0
    STOREA PRI_LEN
.pi_extract:
    LOADA PRI_VAL
    JZ .pi_print
    LOADA PRI_VAL
    PUSH 10
    MOD
    PUSH 48
    ADD
    LOADA PRI_LEN
    PUSH 4
    MUL
    PUSH PRI_BUF
    ADD
    SWAP
    STORE
    LOADA PRI_VAL
    PUSH 10
    DIV
    STOREA PRI_VAL
    LOADA PRI_LEN
    PUSH 1
    ADD
    STOREA PRI_LEN
    JMP .pi_extract
.pi_print:
    LOADA PRI_LEN
    PUSH 1
    SUB
    STOREA PRI_LEN
.pi_ploop:
    LOADA PRI_LEN
    PUSH 0
    LT
    JNZ .pi_done
    LOADA PRI_LEN
    PUSH 4
    MUL
    PUSH PRI_BUF
    ADD
    LOAD
    OUT 1
    LOADA PRI_LEN
    PUSH 1
    SUB
    STOREA PRI_LEN
    JMP .pi_ploop
.pi_done:
    RET

isr_stub:
    IRET
