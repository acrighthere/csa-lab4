"""Assembler / Translator for the stack processor.

Syntax:
  - Lines starting with ';' are comments.
  - Inline comments start with ';'.
  - Labels: <name>:
  - Directives:
      .org <addr>          -- set current address
      .word <val> [, ...]  -- emit raw 32-bit words
      .str "text"          -- emit cstr (null-terminated), one char per word
      .equ <name> <val>    -- define constant (alias for %define)
      .section <name>      -- logical section (informational)
      %define <name> <val> -- text macro substitution
      %macro <name>        -- begin macro definition (no args)
      %endmacro            -- end macro definition
      %ifdef <name>        -- conditional: if macro defined
      %ifndef <name>       -- conditional: if macro NOT defined
      %else                -- else branch
      %endif               -- end conditional
  - Instructions: <MNEMONIC> [operand]
  - Operands can be: decimal / hex (0x...) number or label name.

Usage:
  python translator.py <source.asm> <output.bin> [--debug <debug.txt>]
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

from isa import (
    DATA_BYTES,
    INSTR_SIZE,
    MEMORY_SIZE,
    MNEMONIC_TO_OPCODE,
    PROG_START_DEFAULT,
    Opcode,
    encode_instruction,
)

# Tokenizer / pre-processor


def strip_comment(line: str) -> str:
    """Remove inline ';' comment and strip whitespace."""
    idx = line.find(";")
    if idx >= 0:
        line = line[:idx]
    return line.strip()


def parse_int(token: str) -> int:
    """Parse decimal or hex integer literal."""
    token = token.strip()
    if token.startswith("0x") or token.startswith("0X"):
        return int(token, 16)
    if token.startswith("-0x") or token.startswith("-0X"):
        return -int(token[1:], 16)
    return int(token, 10)


# Assembler

OpcodeHasOperand = frozenset(
    [
        Opcode.PUSH,
        Opcode.LOADA,
        Opcode.STOREA,
        Opcode.JMP,
        Opcode.JZ,
        Opcode.JNZ,
        Opcode.JGZ,
        Opcode.JLZ,
        Opcode.CALL,
        Opcode.IN,
        Opcode.OUT,
    ]
)


class Assembler:
    """Two-pass assembler."""

    def __init__(self) -> None:
        self.labels: dict[str, int] = {}
        self.constants: dict[str, str] = {}  # text macros / .equ
        self.macros: dict[str, list[str]] = {}  # macro name -> body lines
        self._memory: dict[int, int] = {}  # addr -> 32-bit word
        self._current_addr: int = PROG_START_DEFAULT
        self._source_map: dict[int, str] = {}  # addr -> original line

    # Public interface

    def assemble(self, source: str) -> tuple[dict[int, int], dict[int, str]]:
        """Assemble *source* text.

        Returns:
            memory: mapping addr->word
            source_map: mapping addr->mnemonic string (for debug)
        """
        lines = source.splitlines()
        lines = self._preprocess(lines)
        # Pass 1: collect labels and sizes
        self._pass1(lines)
        # Pass 2: emit code
        self._pass2(lines)
        return self._memory, self._source_map

    # Pre-processing: macro expansion, conditional compilation

    def _preprocess(self, lines: list[str]) -> list[str]:
        """Expand macros and process conditionals."""
        # Collect %define and %macro definitions first (single-pass simplification)
        # We do a two-sub-pass approach: first collect defs, then expand.
        # Collect macros
        macro_collecting: str | None = None
        macro_body: list[str] = []
        # First sub-pass: collect macro/define defs
        temp: list[str] = []
        for raw in lines:
            line = strip_comment(raw)
            if not line:
                temp.append("")
                continue
            tokens = line.split()
            if tokens[0] == "%define" and len(tokens) >= 3:
                self.constants[tokens[1]] = " ".join(tokens[2:])
                temp.append("")
            elif tokens[0] == ".equ" and len(tokens) >= 3:
                self.constants[tokens[1]] = " ".join(tokens[2:])
                temp.append("")
            elif tokens[0] == "%macro":
                macro_collecting = tokens[1]
                macro_body = []
                temp.append("")
            elif tokens[0] == "%endmacro":
                if macro_collecting:
                    self.macros[macro_collecting] = macro_body
                    macro_collecting = None
                temp.append("")
            elif macro_collecting is not None:
                macro_body.append(line)
                temp.append("")
            else:
                temp.append(line)

        # Second sub-pass: expand macros & conditionals
        cond_stack: list[bool] = []  # True = currently emitting
        result: list[str] = []
        for line in temp:
            if not line:
                result.append("")
                continue
            tokens = line.split()
            directive = tokens[0]
            if directive == "%ifdef":
                name = tokens[1] if len(tokens) > 1 else ""
                cond_stack.append(name in self.constants or name in self.macros)
                continue
            elif directive == "%ifndef":
                name = tokens[1] if len(tokens) > 1 else ""
                cond_stack.append(not (name in self.constants or name in self.macros))
                continue
            elif directive == "%else":
                if cond_stack:
                    cond_stack[-1] = not cond_stack[-1]
                continue
            elif directive == "%endif":
                if cond_stack:
                    cond_stack.pop()
                continue

            # Skip if inside false conditional
            if cond_stack and not cond_stack[-1]:
                continue

            # Apply constant substitution
            for name, val in self.constants.items():
                pattern = r"\b" + re.escape(name) + r"\b"
                line = re.sub(pattern, val, line)

            tokens = line.split()
            # Macro invocation
            if tokens[0] in self.macros:
                result.extend(self.macros[tokens[0]])
            else:
                result.append(line)

        return result

    # Pass 1: determine label addresses

    def _pass1(self, lines: list[str]) -> None:
        addr = PROG_START_DEFAULT
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # .org directive
            if line.startswith(".org"):
                parts = line.split()
                addr = parse_int(parts[1])
                continue
            # .section directive (no size effect)
            if line.startswith(".section"):
                continue
            # Label definition
            if line.endswith(":"):
                label = line[:-1].strip()
                self.labels[label] = addr
                continue
            # Label on same line as instruction: "label: INSTR operand"
            if ":" in line:
                colon_idx = line.index(":")
                label = line[:colon_idx].strip()
                rest = line[colon_idx + 1 :].strip()
                self.labels[label] = addr
                if rest:
                    line = rest
                else:
                    continue
            # Data directives
            tokens = line.split()
            if tokens[0] == ".word":
                values = " ".join(tokens[1:]).split(",")
                addr += len(values) * DATA_BYTES
                continue
            if tokens[0] == ".str":
                # Extract string literal (one word per char + null terminator)
                text = self._extract_string(line)
                addr += (len(text) + 1) * DATA_BYTES
                continue
            # Instruction
            addr += INSTR_SIZE

    # Pass 2: emit machine code

    def _pass2(self, lines: list[str]) -> None:
        addr = PROG_START_DEFAULT
        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith(".org"):
                parts = line.split()
                addr = parse_int(parts[1])
                continue
            if line.startswith(".section"):
                continue
            if line.endswith(":"):
                continue
            # Inline label
            if ":" in line:
                colon_idx = line.index(":")
                rest = line[colon_idx + 1 :].strip()
                if rest:
                    line = rest
                else:
                    continue
            tokens = line.split(None, 1)
            directive_or_mnemonic = tokens[0].upper()

            if directive_or_mnemonic == ".WORD":
                values = " ".join(tokens[1:]).split(",") if len(tokens) > 1 else []
                for v in values:
                    v = v.strip()
                    word = self._resolve_operand(v)
                    self._emit(addr, word & 0xFFFF_FFFF, line)
                    addr += DATA_BYTES
                continue

            if directive_or_mnemonic == ".STR":
                text = self._extract_string(line)
                for ch in text:
                    self._emit(addr, ord(ch), f".str '{ch}'")
                    addr += DATA_BYTES
                self._emit(addr, 0, ".str '\\0'")
                addr += DATA_BYTES
                continue

            # Instruction
            mnemonic = directive_or_mnemonic
            if mnemonic not in MNEMONIC_TO_OPCODE:
                raise SyntaxError(f"Unknown mnemonic: '{mnemonic}' in line: '{raw_line}'")
            opcode = MNEMONIC_TO_OPCODE[mnemonic]
            operand = 0
            operand_str = ""
            if len(tokens) > 1:
                operand_str = tokens[1].strip()
                operand = self._resolve_operand(operand_str)

            word = encode_instruction(opcode, operand)
            debug_str = f"{mnemonic}"
            if operand_str:
                debug_str += f" {operand_str}(={operand:#06x})"
            self._emit(addr, word, debug_str)
            addr += INSTR_SIZE

    # Helpers

    def _resolve_operand(self, token: str) -> int:
        """Resolve label or integer token to integer value."""
        token = token.strip()
        if token in self.labels:
            return self.labels[token]
        if token in self.constants:
            return self._resolve_operand(self.constants[token])
        try:
            return parse_int(token)
        except ValueError:
            raise SyntaxError(f"Cannot resolve operand: '{token}'") from None

    def _extract_string(self, line: str) -> str:
        """Extract content of a double-quoted string from a .str directive."""
        m = re.search(r'"((?:[^"\\]|\\.)*)"', line)
        if not m:
            raise SyntaxError(f"Missing string literal in: '{line}'")
        raw = m.group(1)
        # Process escape sequences
        result = []
        i = 0
        while i < len(raw):
            if raw[i] == "\\" and i + 1 < len(raw):
                esc = raw[i + 1]
                i += 2
                if esc == "n":
                    result.append("\n")
                elif esc == "t":
                    result.append("\t")
                elif esc == "r":
                    result.append("\r")
                elif esc == "0":
                    result.append("\0")
                elif esc == "\\":
                    result.append("\\")
                elif esc == '"':
                    result.append('"')
                else:
                    result.append(esc)
            else:
                result.append(raw[i])
                i += 1
        return "".join(result)

    def _emit(self, addr: int, word: int, comment: str = "") -> None:
        """Store word at byte address (word occupies DATA_BYTES cells)."""
        if addr + DATA_BYTES > MEMORY_SIZE:
            raise OverflowError(f"Address {addr:#06x} exceeds memory size")
        self._memory[addr] = word & 0xFFFF_FFFF
        self._source_map[addr] = comment


# Binary file I/O
def write_binary(memory: dict[int, int], path: Path) -> None:
    """Write memory image as binary.

    Format:
      Header: 4 bytes -- number of (addr, word) pairs (big-endian uint32)
      Then N * 8 bytes: addr (uint32) + word (uint32), sorted by addr.
    """
    pairs = sorted(memory.items())
    with open(path, "wb") as f:
        f.write(struct.pack(">I", len(pairs)))
        for addr, word in pairs:
            f.write(struct.pack(">II", addr, word))


def read_binary(path: Path) -> dict[int, int]:
    """Read binary memory image."""
    memory: dict[int, int] = {}
    with open(path, "rb") as f:
        (count,) = struct.unpack(">I", f.read(4))
        for _ in range(count):
            addr, word = struct.unpack(">II", f.read(8))
            memory[addr] = word
    return memory


def write_debug(memory: dict[int, int], source_map: dict[int, str], path: Path) -> None:
    """Write human-readable debug listing."""
    with open(path, "w") as f:
        f.write(f"{'Address':>8}  {'HEX':>10}  Mnemonic\n")
        f.write("-" * 60 + "\n")
        for addr in sorted(memory.keys()):
            word = memory[addr]
            comment = source_map.get(addr, "")
            f.write(f"{addr:>8}  {word:>10x}  {comment}\n")


# CLI
def main() -> None:
    parser = argparse.ArgumentParser(description="Stack processor assembler")
    parser.add_argument("source", help="Assembly source file")
    parser.add_argument("output", help="Output binary file")
    parser.add_argument("--debug", help="Optional debug listing file", default=None)
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)

    if not source_path.exists():
        print(f"Error: source file '{source_path}' not found", file=sys.stderr)
        sys.exit(1)

    source_text = source_path.read_text(encoding="utf-8")
    asm = Assembler()
    try:
        memory, source_map = asm.assemble(source_text)
    except (SyntaxError, ValueError, OverflowError) as e:
        print(f"Assembly error: {e}", file=sys.stderr)
        sys.exit(1)

    write_binary(memory, output_path)

    if args.debug:
        write_debug(memory, source_map, Path(args.debug))
        print(f"Debug listing written to {args.debug}")

    print(f"Assembled {len(memory)} words -> {output_path}")

    # Print debug to stdout as well
    print(f"\n{'Address':>8}  {'HEX':>10}  Mnemonic")
    print("-" * 60)
    for addr in sorted(memory.keys()):
        word = memory[addr]
        comment = source_map.get(addr, "")
        print(f"{addr:>8}  {word:>10x}  {comment}")


if __name__ == "__main__":
    main()
