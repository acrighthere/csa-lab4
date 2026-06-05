%define HI     0x200
%define LO     0x201
%define CNT    0x202
%define SC0    0x230
%define SC1    0x231

; Digit buffer
%define DIG_BUF  0x210
%define DIG_LEN  0x224

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

%define PI_VAL  0x540
%define PI_BUF  0x541
%define PI_LEN  0x54B

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

%define PI6_VAL  0x560
%define PI6_CNT  0x561

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
    STOREA 0x542

    LOADA PI6_VAL
    PUSH 1000
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x543

    LOADA PI6_VAL
    PUSH 100
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x544

    LOADA PI6_VAL
    PUSH 10
    DIV
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x545

    LOADA PI6_VAL
    PUSH 10
    MOD
    PUSH 48
    ADD
    STOREA 0x546

    LOADA PI_BUF
    OUT 1
    LOADA 0x542
    OUT 1
    LOADA 0x543
    OUT 1
    LOADA 0x544
    OUT 1
    LOADA 0x545
    OUT 1
    LOADA 0x546
    OUT 1
    RET

isr_stub:
    IRET
