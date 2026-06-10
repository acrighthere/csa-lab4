; demo_features: демонстрация особенностей варианта.
;   - препроцессор: %define, %macro/%endmacro, %ifdef/%else/%endif
;   - стековые идиомы: OVER, SWAP (без обращений к памяти)
;   - сдвиги (SHL), отрицательный immediate (PUSH -1), NEG
; Ожидаемый вывод: "751\n"

%define ONE 1

%macro DOUBLE          ; TOS = TOS * 2 через сдвиг
    PUSH ONE
    SHL
%endmacro

.org 0x000
    .word isr_stub

.org 0x010
_start:
    DI

    ; 1) макрос + сдвиги + отрицательный immediate: 2*2*2 - 1 = 7
    PUSH 2
    DOUBLE             ; 4
    DOUBLE             ; 8
    PUSH -1
    ADD                ; 7
    PUSH 48
    ADD
    OUT 1              ; '7'

    ; 2) OVER: вычислить a+b, не теряя a и b      stk: []
    PUSH 3             ; a                        stk: [3]
    PUSH 2             ; b                        stk: [3, 2]
    OVER               ; копия a                  stk: [3, 2, 3]
    OVER               ; копия b                  stk: [3, 2, 3, 2]
    ADD                ; a+b = 5                  stk: [3, 2, 5]
    PUSH 48
    ADD
    OUT 1              ; '5'                      stk: [3, 2]

    ; 3) SWAP + NEG: -(b - a) = a - b = 1
    SWAP               ;                          stk: [2, 3]
    SUB                ; 2 - 3 = -1               stk: [-1]
    NEG                ; 1                        stk: [1]
    PUSH 48
    ADD
    OUT 1              ; '1'                      stk: []

    ; 4) условная компиляция: эта ветка попадает в бинарник
%ifdef ONE
    PUSH 10
    OUT 1              ; '\n'
%else
    PUSH 33
    OUT 1              ; '!' — этой ветки в машинном коде нет
%endif

    HALT

isr_stub:
    IRET
