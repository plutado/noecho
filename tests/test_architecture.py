"""The engine core must stay free of web, storage, and network dependencies."""

from __future__ import annotations

import ast
from pathlib import Path

import noecho.core

CORE = Path(noecho.core.__file__).parent
FORBIDDEN = ("noecho.api", "noecho.storage", "noecho.service", "fastapi", "pydantic", "sqlite3")


def _imports(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_core_imports_nothing_outside_the_core():
    offenders = {
        f"{p.name}: {name}"
        for p in CORE.glob("*.py")
        for name in _imports(p)
        if name.startswith(FORBIDDEN)
    }
    assert not offenders
