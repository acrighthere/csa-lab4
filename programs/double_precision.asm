%define HI     0x800
%define LO     0x804
%define CNT    0x808
%define SC0    0x810
%define SC1    0x814

; Digit buffer
%define DIG_BUF  0x900
%define DIG_LEN  0x9D0

.org 0x000
    .word isr_stub

.org 0x010
_start:
    DI
    ; Init: 2^0 = 1
    PUSH 0
    STOREA HI
    PUSH 1
    STOREA LO
    PUSH 40
    STOREA CNT

.shl_loop:
    LOADA CNT
    JZ .print_result

    ; carry = (lo >> 31) & 1
    LOADA LO
    PUSH 31
    SHR
    PUSH 1
    AND
    STOREA SC0

    LOADA LO
    PUSH 1
    SHL
    STOREA LO

    LOADA HI
    PUSH 1
    SHL
    LOADA SC0
    OR
    STOREA HI

    LOADA CNT
    PUSH 1
    SUB
    STOREA CNT
    JMP .shl_loop

.print_result:
    LOADA HI
    PUSH 967296
    MUL
    LOADA LO
    ADD
    STOREA SC0

    ; high6 = HI * 4294 + SC0 / 1000000
    LOADA HI
    PUSH 4294
    MUL
    LOADA SC0
    PUSH 1000000
    DIV
    ADD
    STOREA SC1

    LOADA SC0
    PUSH 1000000
    MOD
    STOREA SC0

    LOADA SC1
    CALL print_int

    LOADA SC0
    CALL print_int6
    PUSH 10
    OUT 1
    HALT

%define PI_VAL  0x500
%define PI_BUF  0x540
%define PI_LEN  0x600

print_int:
    STOREA PI_VAL
    LOADA PI_VAL
    JNZ .pi_nz
    PUSH 48
    OUT 1
    RET
.pi_nz:
    PUSH 0
    STOREA PI_LEN
.pi_ext:
    LOADA PI_VAL
    JZ .pi_pr
    LOADA PI_VAL
    PUSH 10
    MOD
    PUSH 48
    ADD
    LOADA PI_LEN
    PUSH 4
    MUL
    PUSH PI_BUF
    ADD
    SWAP
    STORE
    LOADA PI_VAL
    PUSH 10
    DIV
    STOREA PI_VAL
    LOADA PI_LEN
    PUSH 1
    ADD
    STOREA PI_LEN
    JMP .pi_ext
.pi_pr:
    LOADA PI_LEN
    PUSH 1
    SUB
    STOREA PI_LEN
.pi_pl:
    LOADA PI_LEN
    PUSH 0
    LT
    JNZ .pi_done
    LOADA PI_LEN
    PUSH 4
    MUL
    PUSH PI_BUF
    ADD
    LOAD
    OUT 1
    LOADA PI_LEN
    PUSH 1
    SUB
    STOREA PI_LEN
    JMP .pi_pl
.pi_done:
    RET

%define PI6_VAL  0x700
%define PI6_CNT  0x704

print_int6:
    STOREA PI6_VAL
    PUSH 6
    STOREA PI6_CNT
    LOADA PI6_VAL
    PUSH 100000
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA PI_BUF

    LOADA PI6_VAL
    PUSH 10000
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x544

    LOADA PI6_VAL
    PUSH 1000
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x548

    LOADA PI6_VAL
    PUSH 100
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x54C

    LOADA PI6_VAL
    PUSH 10
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x550

    LOADA PI6_VAL
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x554

    LOADA PI_BUF
    OUT 1
    LOADA 0x544
    OUT 1
    LOADA 0x548
    OUT 1
    LOADA 0x54C
    OUT 1
    LOADA 0x550
    OUT 1
    LOADA 0x554
    OUT 1
    RET

isr_stub:
    IRET
