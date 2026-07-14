from __future__ import annotations

import ast
from pathlib import Path


def test_pool_unit_alarm_does_not_require_code_to_arm() -> None:
    source = Path("custom_components/bcone/alarm_control_panel.py").read_text()
    module = ast.parse(source)
    panel = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "BconePoolUnitAlarmControlPanel"
    )
    assignment = next(
        node
        for node in panel.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "_attr_code_arm_required" for target in node.targets)
    )

    assert isinstance(assignment.value, ast.Constant)
    assert assignment.value.value is False
