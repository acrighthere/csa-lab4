; Data region placed above the (byte-addressed) code segment.
%define FLAG_DONE  0x1000
%define BUF_LEN    0x1004
%define IBUF       0x1100
%define ARR_LEN    0x1600
%define ARR        0x1604

%define S0  0x2000
%define S1  0x2004
%define S2  0x2008
%define S3  0x200C
%define S4  0x2010
%define S5  0x2014
%define S6  0x2018
%define S7  0x201C
%define S8  0x2020
%define S9  0x2024

.org 0x000
    .word isr_input

.org 0x010
_start:
    DI
    PUSH 0
    STOREA FLAG_DONE
    PUSH 0
    STOREA BUF_LEN
    PUSH 0
    STOREA ARR_LEN

    EI

.wait:
    LOADA FLAG_DONE
    JZ .wait

    DI

    LOADA BUF_LEN
    PUSH 4
    MUL
    PUSH IBUF
    ADD
    PUSH 0
    SWAP
    STORE

    CALL parse_ints

    CALL bubble_sort

    CALL print_array

    HALT

parse_ints:
    PUSH IBUF
    STOREA S0

.pi_loop:
    ; skip whitespace
    LOADA S0
    CALL skip_ws
    STOREA S0

    ; check end of string
    LOADA S0
    LOAD
    JZ .pi_done

    ; parse one decimal number
    LOADA S0
    CALL parse_num
    LOADA S0

    ; store ARR[ARR_LEN] = number
    LOADA ARR_LEN
    PUSH 4
    MUL
    PUSH ARR
    ADD
    STOREA S1
    LOADA S3
    LOADA S1
    SWAP
    STORE

    LOADA ARR_LEN
    PUSH 1
    ADD
    STOREA ARR_LEN

    JMP .pi_loop

.pi_done:
    RET

skip_ws:
.sw_loop:
    DUP
    LOAD
    STOREA S4
    LOADA S4
    PUSH 32
    EQ
    JNZ .sw_advance
    LOADA S4
    PUSH 9
    EQ
    JNZ .sw_advance
    LOADA S4
    PUSH 10
    EQ
    JNZ .sw_advance
    LOADA S4
    PUSH 13
    EQ
    JNZ .sw_advance
    RET

.sw_advance:
    PUSH 4
    ADD
    JMP .sw_loop

parse_num:
    STOREA S2           ; S2 = ptr
    PUSH 0
    STOREA S3           ; S3 = 0 (accumulator)

.pn_loop:
    LOADA S2
    LOAD                ; char
    DUP
    PUSH 48
    LT
    JNZ .pn_done        ; char < '0' -> stop
    DUP
    PUSH 57
    GT
    JNZ .pn_done        ; char > '9' -> stop
    ; digit
    PUSH 48
    SUB                 ; digit value
    LOADA S3
    PUSH 10
    MUL
    ADD
    STOREA S3           ; S3 = S3*10 + digit
    LOADA S2
    PUSH 4
    ADD
    STOREA S2           ; advance ptr
    JMP .pn_loop

.pn_done:
    POP                 ; discard char copy
    ; store updated ptr back to S0 (caller reads it)
    LOADA S2
    STOREA S0
    RET

%define BS_I    0x2100
%define BS_J    0x2104
%define BS_N    0x2108
%define BS_AJ   0x210C
%define BS_VJ   0x2110
%define BS_AJ1  0x2114
%define BS_VJ1  0x2118

bubble_sort:
    LOADA ARR_LEN
    STOREA BS_N
    PUSH 0
    STOREA BS_I

.bs_outer:
    ; if i >= n-1: done
    LOADA BS_I
    LOADA BS_N
    PUSH 1
    SUB
    GE
    JNZ .bs_done

    PUSH 0
    STOREA BS_J

.bs_inner:
    ; if j >= n-1-i: next outer
    LOADA BS_J
    LOADA BS_N
    PUSH 1
    SUB
    LOADA BS_I
    SUB
    GE
    JNZ .bs_next_i

    ; addr_j = ARR + j*4
    LOADA BS_J
    PUSH 4
    MUL
    PUSH ARR
    ADD
    STOREA BS_AJ
    LOADA BS_AJ
    LOAD
    STOREA BS_VJ

    ; addr_j1 = addr_j + 4
    LOADA BS_AJ
    PUSH 4
    ADD
    STOREA BS_AJ1
    LOADA BS_AJ1
    LOAD
    STOREA BS_VJ1

    ; if arr[j] <= arr[j+1]: no swap
    LOADA BS_VJ
    LOADA BS_VJ1
    LE
    JNZ .bs_no_swap

    ; swap
    LOADA BS_VJ1
    LOADA BS_AJ
    SWAP
    STORE           ; mem[addr_j] = val_j1
    LOADA BS_VJ
    LOADA BS_AJ1
    SWAP
    STORE           ; mem[addr_j1] = val_j

.bs_no_swap:
    LOADA BS_J
    PUSH 1
    ADD
    STOREA BS_J
    JMP .bs_inner

.bs_next_i:
    LOADA BS_I
    PUSH 1
    ADD
    STOREA BS_I
    JMP .bs_outer

.bs_done:
    RET

%define PA_I  0x2200
print_array:
    PUSH 0
    STOREA PA_I
.pa_loop:
    LOADA PA_I
    LOADA ARR_LEN
    GE
    JNZ .pa_done
    LOADA PA_I
    PUSH 4
    MUL
    PUSH ARR
    ADD
    LOAD
    CALL print_int
    PUSH 10
    OUT 1
    LOADA PA_I
    PUSH 1
    ADD
    STOREA PA_I
    JMP .pa_loop
.pa_done:
    RET

%define PI_VAL  0x2210
%define PI_BUF  0x2300
%define PI_LEN  0x2400

print_int:
    STOREA PI_VAL
    LOADA PI_VAL
    JNZ .pint_nz
    PUSH 48
    OUT 1
    RET
.pint_nz:
    PUSH 0
    STOREA PI_LEN
.pint_ext:
    LOADA PI_VAL
    JZ .pint_pr
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
    JMP .pint_ext
.pint_pr:
    LOADA PI_LEN
    PUSH 1
    SUB
    STOREA PI_LEN
.pint_pl:
    LOADA PI_LEN
    PUSH 0
    LT
    JNZ .pint_done
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
    JMP .pint_pl
.pint_done:
    RET

isr_input:
    IN 0
    DUP
    JZ .isr_eof

    LOADA BUF_LEN
    PUSH 4
    MUL
    PUSH IBUF
    ADD
    SWAP
    STORE

    LOADA BUF_LEN
    PUSH 1
    ADD
    STOREA BUF_LEN
    IRET

.isr_eof:
    POP                     
    PUSH 1
    STOREA FLAG_DONE
    IRET
