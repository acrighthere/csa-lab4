"""Golden integration tests:

Run normally:
    pytest tests/test_golden.py -v

Regenerate snapshots:
    pytest tests/test_golden.py --update-goldens
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from yaml.representer import SafeRepresenter


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return SafeRepresenter.represent_str(dumper, data)


yaml.add_representer(str, _str_representer)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from machine import Processor, parse_input_schedule  # noqa: E402
from translator import Assembler  # noqa: E402

PROGRAMS_DIR = Path(__file__).parent.parent / "programs"
GOLDEN_DIR = Path(__file__).parent / "golden"

_LOG_MAX = 102400


# Test cases: (program_stem, in_stdin schedule text, max_ticks)


CASES: list[tuple[str, str, int]] = [
    ("hello", "", 1_000_000),
    (
        "cat",
        "5 104\n10 101\n15 108\n20 108\n25 111\n35 0\n",
        1_000_000,
    ),
    (
        "hello_user_name",
        "100 65\n110 108\n120 105\n130 99\n140 101\n150 10\n",
        1_000_000,
    ),
    (
        "sort",
        "100 53\n105 32\n110 51\n115 32\n120 49\n125 32\n130 52\n135 32\n140 50\n145 0\n",
        200_000,
    ),
    ("prob2", "", 50_000),
    ("double_precision", "", 100_000),
]


# Helpers


def _make_debug_str(memory: dict[int, int], source_map: dict[int, str]) -> str:
    lines = [f"{'Address':>8}  {'HEX':>10}  Mnemonic", "-" * 60]
    for addr in sorted(memory.keys()):
        word = memory[addr]
        comment = source_map.get(addr, "")
        lines.append(f"{addr:>8}  {word:>10x}  {comment}")
    return "\n".join(lines) + "\n"


def _truncate_log(log: str) -> str:
    if len(log) <= _LOG_MAX:
        return log
    log = log[:_LOG_MAX]
    return log if log.endswith("\n") else log[: log.rfind("\n")]


def _run(program_stem: str, schedule_text: str, max_ticks: int) -> tuple[str, str, str]:
    """Assemble and simulate. Returns (machine_code_dump, output, log)."""
    source = (PROGRAMS_DIR / f"{program_stem}.asm").read_text(encoding="utf-8")
    asm = Assembler()
    memory, source_map = asm.assemble(source)

    schedule = parse_input_schedule(schedule_text)
    cpu = Processor(memory, schedule)
    cpu.run(max_ticks=max_ticks)

    machine_code = _make_debug_str(memory, source_map)
    output = cpu.output()
    log = _truncate_log(cpu.log())
    return machine_code, output, log


# Tests


@pytest.mark.parametrize("stem,schedule,max_ticks", CASES, ids=[c[0] for c in CASES])
def test_golden(stem: str, schedule: str, max_ticks: int, request: pytest.FixtureRequest) -> None:
    update = request.config.getoption("--update-goldens")
    golden_path = GOLDEN_DIR / f"{stem}.yml"

    machine_code, output, log = _run(stem, schedule, max_ticks)

    if update:
        data: dict[str, Any] = {
            "in_source": (PROGRAMS_DIR / f"{stem}.asm").read_text(encoding="utf-8"),
            "machine_code": machine_code,
            "output": output,
            "out_log": log,
        }
        if schedule:
            data["in_stdin"] = schedule
        golden_path.write_text(
            yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        return

    if not golden_path.exists():
        pytest.fail(f"Golden file {golden_path} not found. Run with --update-goldens to create it.")

    data = yaml.safe_load(golden_path.read_text(encoding="utf-8"))

    assert data["machine_code"] == machine_code, f"{stem}: machine_code mismatch"
    assert data["output"] == output, f"{stem}: output mismatch"
    assert data["out_log"] == log, f"{stem}: out_log mismatch"
