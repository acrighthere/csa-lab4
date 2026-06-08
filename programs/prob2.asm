%define LIMIT    4000000
%define FIB_A    0x200      ; F(n-2)
%define FIB_B    0x204      ; F(n-1)
%define FIB_C    0x208      ; F(n) current
%define SUM_LO   0x20C      ; lower 32 bits of sum
%define SUM_HI   0x210      ; upper 32 bits of sum (double precision)

.org 0x000
    .word isr_stub

.org 0x010
_start:
    DI

    PUSH 1
    STOREA FIB_A
    PUSH 2
    STOREA FIB_B
    PUSH 0
    STOREA SUM_LO
    PUSH 0
    STOREA SUM_HI


.fib_loop:
    LOADA FIB_B
    PUSH LIMIT
    GT
    JNZ .done

    ; if b % 2 == 0: sum += b
    LOADA FIB_B
    PUSH 2
    MOD
    JNZ .not_even

    ; sum_lo += b, handle carry
    LOADA SUM_LO
    LOADA FIB_B
    ADD
    STOREA SUM_LO

.not_even:
    ; Next Fibonacci: c = a + b, a = b, b = c
    LOADA FIB_A
    LOADA FIB_B
    ADD                     ; c = a + b
    STOREA FIB_C
    LOADA FIB_B
    STOREA FIB_A
    LOADA FIB_C
    STOREA FIB_B
    JMP .fib_loop

.done:
    ; Print SUM_LO
    LOADA SUM_LO
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
