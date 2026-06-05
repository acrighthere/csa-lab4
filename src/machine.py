"""Stack processor simulator (tick-accurate model).

Features:
  - Von Neumann architecture (unified instruction + data memory)
  - Stack-based execution (data stack + return stack)
  - Hardwired Control Unit
  - Tick-accurate simulation
  - Trap-based I/O via port-mapped instructions (IN / OUT)
  - Interrupt system: external interrupts delivered at scheduled ticks
  - C-strings (null-terminated)

Interrupt schedule format (input file lines):
  <tick> <char_or_decimal>
  e.g.:   5 h
          10 e
          15 l

Usage:
  python machine.py <binary.bin> <input_schedule.txt> [--limit <ticks>] [--log <log.txt>]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from isa import (
    INT_VECTOR_ADDR,
    MEMORY_SIZE,
    PORT_INPUT,
    PORT_OUTPUT,
    PROG_START_DEFAULT,
    Opcode,
    decode_instruction,
)
from translator import read_binary

# Processor state

STACK_SIZE = 256
RETURN_STACK_SIZE = 256


class Processor:
    """Hardwired stack processor."""

    def __init__(
        self,
        memory_image: dict[int, int],
        interrupt_schedule: list[tuple[int, int]],
    ) -> None:
        # --- Memory ---
        self.memory: list[int] = [0] * MEMORY_SIZE
        for addr, word in memory_image.items():
            self.memory[addr] = word

        # --- Data stack ---
        self.dstack: list[int] = []

        # --- Return stack ---
        self.rstack: list[int] = []

        # --- Registers ---
        self.pc: int = PROG_START_DEFAULT
        self.ir: int = 0  # instruction register
        self.tick: int = 0  # global tick counter

        # --- Interrupt state ---
        self.interrupts_enabled: bool = False
        self.in_interrupt: bool = False
        self.interrupt_schedule: list[tuple[int, int]] = sorted(
            interrupt_schedule, key=lambda x: x[0]
        )
        self._interrupt_idx: int = 0  # next interrupt to deliver
        # Queue of pending interrupt char values (FIFO)
        self._interrupt_queue: list[int] = []

        # --- I/O ---
        self.input_port: int = 0  # value currently on input port
        self.output_buffer: list[str] = []

        # --- Halted ---
        self.halted: bool = False

        # --- Log ---
        self.log_lines: list[str] = []

    # Stack helpers

    def _push(self, value: int) -> None:
        if len(self.dstack) >= STACK_SIZE:
            raise RuntimeError("Data stack overflow")
        self.dstack.append(value & 0xFFFF_FFFF)

    def _pop(self) -> int:
        if not self.dstack:
            raise RuntimeError("Data stack underflow")
        return self.dstack.pop()

    def _peek(self) -> int:
        if not self.dstack:
            raise RuntimeError("Data stack underflow (peek)")
        return self.dstack[-1]

    def _rpush(self, value: int) -> None:
        if len(self.rstack) >= RETURN_STACK_SIZE:
            raise RuntimeError("Return stack overflow")
        self.rstack.append(value & 0xFFFF_FFFF)

    def _rpop(self) -> int:
        if not self.rstack:
            raise RuntimeError("Return stack underflow")
        return self.rstack.pop()

    # Sign helper

    @staticmethod
    def _signed(value: int) -> int:
        """Interpret 32-bit unsigned as signed."""
        value = value & 0xFFFF_FFFF
        if value >= 0x8000_0000:
            return value - 0x1_0000_0000
        return value

    # Memory access

    def _mem_read(self, addr: int) -> tuple[int, int]:
        """Read from memory. Returns (value, ticks)."""
        addr = addr & 0xFFFF_FFFF
        if addr >= MEMORY_SIZE:
            raise RuntimeError(f"Memory read out of bounds: {addr:#010x}")
        return self.memory[addr], 1

    def _mem_write(self, addr: int, value: int) -> int:
        """Write to memory. Returns ticks."""
        addr = addr & 0xFFFF_FFFF
        if addr >= MEMORY_SIZE:
            raise RuntimeError(f"Memory write out of bounds: {addr:#010x}")
        self.memory[addr] = value & 0xFFFF_FFFF
        return 1

    # Interrupt delivery

    def _check_interrupts(self) -> None:
        """Deliver pending interrupts if enabled and not in ISR."""
        # Enqueue newly arrived interrupts from schedule
        while (
            self._interrupt_idx < len(self.interrupt_schedule)
            and self.interrupt_schedule[self._interrupt_idx][0] <= self.tick
        ):
            _tick_val, char_val = self.interrupt_schedule[self._interrupt_idx]
            self._interrupt_queue.append(char_val)
            self._interrupt_idx += 1

        # Deliver one queued interrupt if enabled and not already in ISR
        if self._interrupt_queue and self.interrupts_enabled and not self.in_interrupt:
            char_val = self._interrupt_queue.pop(0)
            self.input_port = char_val
            self._enter_interrupt()

    def _enter_interrupt(self) -> None:
        """Enter interrupt service routine."""
        # Save PC to return stack
        self._rpush(self.pc)
        # Disable interrupts
        self.interrupts_enabled = False
        self.in_interrupt = True
        # Jump to interrupt vector
        handler_addr = self.memory[INT_VECTOR_ADDR]
        self._log(f"  [INT] entering ISR at {handler_addr:#06x}, saved PC={self.pc:#06x}")
        self.pc = handler_addr
        self.tick += 2  # interrupt acknowledge overhead

    # Fetch + decode

    def _fetch(self) -> tuple[Opcode, int]:
        """Fetch instruction at PC, advance PC. Returns (opcode, operand)."""
        val, ticks = self._mem_read(self.pc)
        self.tick += ticks
        self.ir = val
        opcode, operand = decode_instruction(val)
        self.pc += 1
        return opcode, operand

    # Execute one instruction

    def step(self) -> bool:
        """Execute one instruction. Returns False if halted."""
        if self.halted:
            return False

        self._check_interrupts()
        if self.halted:
            return False

        pc_before = self.pc
        opcode, operand = self._fetch()
        state_str = self._state_str(pc_before, opcode, operand)

        try:
            self._execute(opcode, operand)
        except RuntimeError as e:
            self._log(f"  [ERROR] {e}")
            self.halted = True
            return False

        self._log(state_str)
        return not self.halted

    def _execute(self, opcode: Opcode, operand: int) -> None:  # noqa: C901
        """Execute decoded instruction. Updates tick."""
        op = opcode

        if op == Opcode.NOP:
            self.tick += 1

        elif op == Opcode.PUSH:
            self._push(operand)
            self.tick += 1

        elif op == Opcode.POP:
            self._pop()
            self.tick += 1

        elif op == Opcode.DUP:
            v = self._peek()
            self._push(v)
            self.tick += 1

        elif op == Opcode.SWAP:
            a = self._pop()
            b = self._pop()
            self._push(a)
            self._push(b)
            self.tick += 1

        elif op == Opcode.OVER:
            if len(self.dstack) < 2:
                raise RuntimeError("OVER: stack underflow")
            v = self.dstack[-2]
            self._push(v)
            self.tick += 1

        elif op == Opcode.LOAD:
            addr = self._pop()
            val, ticks = self._mem_read(addr)
            self._push(val)
            self.tick += ticks

        elif op == Opcode.STORE:
            val = self._pop()
            addr = self._pop()
            ticks = self._mem_write(addr, val)
            self.tick += ticks

        elif op == Opcode.LOADA:
            val, ticks = self._mem_read(operand)
            self._push(val)
            self.tick += ticks

        elif op == Opcode.STOREA:
            val = self._pop()
            ticks = self._mem_write(operand, val)
            self.tick += ticks

        elif op == Opcode.ADD:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(a + b)
            self.tick += 1

        elif op == Opcode.SUB:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(a - b)
            self.tick += 1

        elif op == Opcode.MUL:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(a * b)
            self.tick += 1

        elif op == Opcode.DIV:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            if b == 0:
                raise RuntimeError("Division by zero")
            self._push(int(a / b))
            self.tick += 1

        elif op == Opcode.MOD:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            if b == 0:
                raise RuntimeError("Modulo by zero")
            self._push(a - int(a / b) * b)
            self.tick += 1

        elif op == Opcode.AND:
            b = self._pop()
            a = self._pop()
            self._push(a & b)
            self.tick += 1

        elif op == Opcode.OR:
            b = self._pop()
            a = self._pop()
            self._push(a | b)
            self.tick += 1

        elif op == Opcode.XOR:
            b = self._pop()
            a = self._pop()
            self._push(a ^ b)
            self.tick += 1

        elif op == Opcode.NOT:
            a = self._pop()
            self._push(~a)
            self.tick += 1

        elif op == Opcode.NEG:
            a = self._signed(self._pop())
            self._push(-a)
            self.tick += 1

        elif op == Opcode.SHL:
            b = self._pop() & 0x1F
            a = self._pop()
            self._push(a << b)
            self.tick += 1

        elif op == Opcode.SHR:
            b = self._pop() & 0x1F
            a = self._pop()
            self._push((a & 0xFFFF_FFFF) >> b)
            self.tick += 1

        elif op == Opcode.EQ:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(1 if a == b else 0)
            self.tick += 1

        elif op == Opcode.NEQ:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(1 if a != b else 0)
            self.tick += 1

        elif op == Opcode.LT:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(1 if a < b else 0)
            self.tick += 1

        elif op == Opcode.LE:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(1 if a <= b else 0)
            self.tick += 1

        elif op == Opcode.GT:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(1 if a > b else 0)
            self.tick += 1

        elif op == Opcode.GE:
            b = self._signed(self._pop())
            a = self._signed(self._pop())
            self._push(1 if a >= b else 0)
            self.tick += 1

        elif op == Opcode.JMP:
            self.pc = operand & 0xFFFF_FFFF
            self.tick += 1

        elif op == Opcode.JZ:
            v = self._signed(self._pop())
            if v == 0:
                self.pc = operand & 0xFFFF_FFFF
            self.tick += 1

        elif op == Opcode.JNZ:
            v = self._signed(self._pop())
            if v != 0:
                self.pc = operand & 0xFFFF_FFFF
            self.tick += 1

        elif op == Opcode.JGZ:
            v = self._signed(self._pop())
            if v > 0:
                self.pc = operand & 0xFFFF_FFFF
            self.tick += 1

        elif op == Opcode.JLZ:
            v = self._signed(self._pop())
            if v < 0:
                self.pc = operand & 0xFFFF_FFFF
            self.tick += 1

        elif op == Opcode.CALL:
            self._rpush(self.pc)
            self.pc = operand & 0xFFFF_FFFF
            self.tick += 1

        elif op == Opcode.RET:
            addr = self._rpop()
            self.pc = addr
            self.tick += 1

        elif op == Opcode.HALT:
            self.halted = True
            self.tick += 1

        elif op == Opcode.IN:
            port = operand
            if port == PORT_INPUT:
                value = self.input_port
                self._push(value)
                ch_repr = chr(value) if 32 <= value < 127 else "?"
                self._log(f"  [IN]  port={port} value={value}('{ch_repr}')")
            else:
                self._push(0)
            self.tick += 1

        elif op == Opcode.OUT:
            port = operand
            value = self._pop()
            if port == PORT_OUTPUT:
                ch = chr(value & 0xFF)
                self.output_buffer.append(ch)
                self._log(f"  [OUT] port={port} char='{ch}' (0x{value & 0xFF:02x})")
            self.tick += 1

        elif op == Opcode.EI:
            self.interrupts_enabled = True
            self.tick += 1

        elif op == Opcode.DI:
            self.interrupts_enabled = False
            self.tick += 1

        elif op == Opcode.IRET:
            addr = self._rpop()
            self.pc = addr
            self.in_interrupt = False
            self.interrupts_enabled = True
            self._log(f"  [IRET] returning to PC={addr:#06x}, re-enabling interrupts")
            self.tick += 1

        else:
            raise RuntimeError(f"Unknown opcode: {opcode:#04x}")

    # Logging

    def _state_str(self, pc: int, opcode: Opcode, operand: int) -> str:
        stack_repr = str(self.dstack[-8:]) if self.dstack else "[]"
        isr_flag = " ISR" if self.in_interrupt else "    "
        return (
            f"tick={self.tick:>6} PC={pc:#06x}{isr_flag} "
            f"{opcode.name:<8} {operand:>10}  stk={stack_repr}"
        )

    def _log(self, msg: str) -> None:
        self.log_lines.append(msg)

    # Run

    def run(self, max_ticks: int = 1_000_000) -> None:
        """Run until HALT or tick limit."""
        while not self.halted and self.tick < max_ticks:
            self.step()
        if self.tick >= max_ticks and not self.halted:
            self._log(f"[WARN] Tick limit {max_ticks} reached, stopping.")

    def output(self) -> str:
        return "".join(self.output_buffer)

    def log(self) -> str:
        return "\n".join(self.log_lines)


# Input schedule parser


def parse_input_schedule(text: str) -> list[tuple[int, int]]:
    """Parse interrupt schedule.

    Format per line:  <tick> <char_or_ascii>
    Lines starting with '#' are comments.
    """
    schedule: list[tuple[int, int]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        tick = int(parts[0])
        token = parts[1].strip()
        # If token looks like a decimal/hex number, use as int; otherwise treat as char
        try:
            char_val = int(token, 0)
        except ValueError:
            if len(token) == 1:
                char_val = ord(token)
            else:
                raise ValueError(f"Cannot parse token '{token}' as char or int") from None
        schedule.append((tick, char_val))
    return schedule


# CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="Stack processor simulator")
    parser.add_argument("binary", help="Binary machine code file")
    parser.add_argument("input", help="Interrupt input schedule file")
    parser.add_argument("--limit", type=int, default=1_000_000, help="Max ticks")
    parser.add_argument("--log", help="Optional log output file", default=None)
    args = parser.parse_args()

    binary_path = Path(args.binary)
    input_path = Path(args.input)

    if not binary_path.exists():
        print(f"Error: binary '{binary_path}' not found", file=sys.stderr)
        sys.exit(1)

    memory = read_binary(binary_path)

    schedule: list[tuple[int, int]] = []
    if input_path.exists():
        schedule = parse_input_schedule(input_path.read_text(encoding="utf-8"))
    else:
        print(
            f"Warning: input file '{input_path}' not found, no interrupts",
            file=sys.stderr,
        )

    cpu = Processor(memory, schedule)
    cpu.run(max_ticks=args.limit)

    output_text = cpu.output()
    log_text = cpu.log()

    print(output_text, end="")

    if args.log:
        Path(args.log).write_text(log_text, encoding="utf-8")
        print(f"\n[Log written to {args.log}]", file=sys.stderr)
    else:
        print("\n--- Simulation Log ---", file=sys.stderr)
        print(log_text, file=sys.stderr)

    print(
        f"\n--- Stats ---\n  Total ticks: {cpu.tick}\n  Output: '{output_text}'",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
