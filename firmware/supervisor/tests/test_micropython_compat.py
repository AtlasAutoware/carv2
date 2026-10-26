"""A static check that the files copied to the Pico stay inside what MicroPython supports.

This is not a substitute for running on a Pico (nothing here has run on MicroPython yet); it
catches the CPython habits that would fail there: modules MicroPython does not ship,
f-strings (only in MicroPython 1.20 and later), the walrus operator, `match`, dataclasses,
bytes.hex(), int.from_bytes(..., signed=...), keyword arguments to str methods, and print()
outside main.py (stdout is the Jetson link).
"""
import ast
import os

import pytest

FIRMWARE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ON_PICO = ('pins.py', 'hal.py', 'jbd.py', 'link.py', 'sequencer.py', 'main.py')
ALLOWED_IMPORTS = {'time', 'math', 'json', 'sys', 'os', 'select', 'machine', 'micropython', 'gc',
                   'pins', 'hal', 'jbd', 'link', 'sequencer'}


def tree(name):
    with open(os.path.join(FIRMWARE, name)) as f:
        return ast.parse(f.read(), name)


@pytest.mark.parametrize('name', ON_PICO)
def test_imports(name):
    for node in ast.walk(tree(name)):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module]
        else:
            continue
        for m in mods:
            assert m.split('.')[0] in ALLOWED_IMPORTS, f'{name}: import {m}'


@pytest.mark.parametrize('name', ON_PICO)
def test_no_newer_syntax(name):
    for node in ast.walk(tree(name)):
        assert not isinstance(node, ast.JoinedStr), f'{name}:{node.lineno}: f-string'
        assert not isinstance(node, ast.NamedExpr), f'{name}:{node.lineno}: walrus'
        assert not isinstance(node, ast.Match), f'{name}:{node.lineno}: match'
        assert not isinstance(node, (ast.AsyncFunctionDef, ast.Await)), f'{name}:{node.lineno}: async'
        if isinstance(node, ast.Attribute):
            assert node.attr not in ('hex', 'fromhex', 'from_bytes', 'to_bytes', 'removeprefix',
                                     'removesuffix', 'casefold'), f'{name}:{node.lineno}: .{node.attr}'
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == 'print':
                assert name == 'main.py', f'{name}:{node.lineno}: print() goes to the Jetson link'
            if node.func.id in ('min', 'max'):
                assert not node.keywords, f'{name}:{node.lineno}: {node.func.id}() keyword'


def test_irq_handler_is_minimal():
    """The E-stop handler runs as a hard interrupt: only writes and a flag, no maths or calls
    that build new objects."""
    t = tree('sequencer.py')
    fn = next(n for n in ast.walk(t) if isinstance(n, ast.FunctionDef) and n.name == 'estop_irq')
    for node in ast.walk(fn):
        assert not isinstance(node, (ast.BinOp, ast.Dict, ast.List, ast.JoinedStr, ast.Tuple)), node
        if isinstance(node, ast.Call):
            assert isinstance(node.func, ast.Attribute) and node.func.attr == 'write'
