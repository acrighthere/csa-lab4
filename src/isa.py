from __future__ import annotations

import struct
from enum import IntEnum


class Opcode(IntEnum):
    PUSH = 0x01  # PUSH <imm>   -- push 24-bit sign-extended immediate
    POP = 0x02  # POP          -- discard TOS
    DUP = 0x03  # DUP          -- duplicate TOS
    SWAP = 0x04  # SWAP         -- swap TOS and NOS (next on stack)
    OVER = 0x05  # OVER         -- copy NOS to TOS

    LOAD = 0x10  # LOAD         -- TOS = mem[TOS]
    STORE = 0x11  # STORE        -- mem[NOS] = TOS; pop two
    LOADA = 0x12  # LOADA <addr> -- push mem[addr]  (absolute addr)
    STOREA = 0x13  # STOREA <addr>-- mem[addr] = TOS; pop

    # --- Arithmetic/Logic ---
    ADD = 0x20  # TOS = NOS + TOS; pop one
    SUB = 0x21  # TOS = NOS - TOS; pop one
    MUL = 0x22  # TOS = NOS * TOS; pop one
    DIV = 0x23  # TOS = NOS / TOS; pop one (integer)
    MOD = 0x24  # TOS = NOS % TOS; pop one
    AND = 0x25  # TOS = NOS & TOS; pop one
    OR = 0x26  # TOS = NOS | TOS; pop one
    XOR = 0x27  # TOS = NOS ^ TOS; pop one
    NOT = 0x28  # TOS = ~TOS
    NEG = 0x29  # TOS = -TOS
    SHL = 0x2A  # TOS = NOS << TOS; pop one
    SHR = 0x2B  # TOS = NOS >> TOS; pop one (logical)

    # --- Comparison (push 1 if true, 0 if false) ---
    EQ = 0x30  # NOS == TOS
    NEQ = 0x31  # NOS != TOS
    LT = 0x32  # NOS < TOS  (signed)
    LE = 0x33  # NOS <= TOS (signed)
    GT = 0x34  # NOS > TOS  (signed)
    GE = 0x35  # NOS >= TOS (signed)

    # --- Control flow ---
    JMP = 0x40  # JMP <addr>   -- unconditional jump
    JZ = 0x41  # JZ  <addr>   -- jump if TOS == 0; pop
    JNZ = 0x42  # JNZ <addr>   -- jump if TOS != 0; pop
    JGZ = 0x43  # JGZ <addr>   -- jump if TOS > 0;  pop
    JLZ = 0x44  # JLZ <addr>   -- jump if TOS < 0;  pop
    CALL = 0x45  # CALL <addr>  -- push PC to return stack, jump
    RET = 0x46  # RET          -- pop return stack, jump
    HALT = 0x47  # HALT         -- stop execution

    # --- I/O (port-mapped) ---
    IN = 0x50  # IN  <port>   -- push value from port
    OUT = 0x51  # OUT <port>   -- pop TOS, send to port

    # --- Interrupt handling ---
    EI = 0x60  # EI           -- enable interrupts
    DI = 0x61  # DI           -- disable interrupts
    IRET = 0x62  # IRET         -- return from interrupt handler

    # --- Special ---
    NOP = 0x00  # NOP          -- no operation


# Port numbers
PORT_INPUT = 0  # read a character from stdin stream
PORT_OUTPUT = 1  # write a character to stdout stream

# Memory layout (byte-addressable)
INT_VECTOR_ADDR = 0x000  # byte address 0: interrupt vector (one word)
PROG_START_DEFAULT = 0x010  # default program start byte address

# Instruction word size (bytes)
INSTR_SIZE = 4

# Data word size
DATA_BITS = 32
DATA_BYTES = 4

# Immediate field size
IMM_BITS = 24
IMM_MASK = (1 << IMM_BITS) - 1
IMM_SIGN_BIT = 1 << (IMM_BITS - 1)

# Memory size (bytes). Addressing is byte-granular; a machine word spans
# DATA_BYTES (4) consecutive byte cells, stored big-endian.
MEMORY_SIZE = 0x40000  # 262144 bytes (== 65536 words)


def sign_extend_imm(value: int) -> int:
    """Sign-extend 24-bit immediate to Python int."""
    value = value & IMM_MASK
    if value & IMM_SIGN_BIT:
        value -= 1 << IMM_BITS
    return value


def encode_instruction(opcode: Opcode, operand: int = 0) -> int:
    """Pack opcode + 24-bit operand into a 32-bit word."""
    operand = operand & IMM_MASK
    return ((int(opcode) & 0xFF) << IMM_BITS) | operand


def decode_instruction(word: int) -> tuple[Opcode, int]:
    """Unpack 32-bit word into (opcode, sign-extended operand)."""
    opcode_raw = (word >> IMM_BITS) & 0xFF
    operand = sign_extend_imm(word & IMM_MASK)
    return Opcode(opcode_raw), operand


def word_to_bytes(word: int) -> bytes:
    """Convert 32-bit unsigned int to 4 bytes (big-endian)."""
    return struct.pack(">I", word & 0xFFFF_FFFF)


def bytes_to_word(data: bytes) -> int:
    """Convert 4 bytes (big-endian) to 32-bit unsigned int."""
    return int(struct.unpack(">I", data)[0])


OPCODE_MNEMONICS: dict[Opcode, str] = {op: op.name for op in Opcode}

MNEMONIC_TO_OPCODE: dict[str, Opcode] = {op.name: op for op in Opcode}
