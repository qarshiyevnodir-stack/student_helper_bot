import ast
from pathlib import Path


UTILS = Path(__file__).parents[1] / "utils.py"


def _tree():
    return ast.parse(UTILS.read_text(encoding="utf-8"))


def test_oddiy1_generator_helpers_are_defined():
    tree = _tree()
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    required = {
        "fill_oddiy1_slide_5_three_col",
        "fill_oddiy1_slide_6_two_col_bold",
        "fill_oddiy1_slide_7_single_body",
        "fill_oddiy1_slide_8_outro",
    }
    assert required <= defined


def test_oddiy1_generator_has_no_missing_oddiy1_function_references():
    tree = _tree()
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id.startswith("fill_oddiy1_")
        and node.id not in defined
    }
    assert not missing
