"""Inert recognition of fixed language-label lookups, not game profiles."""
from __future__ import annotations

import ast
import re
import textwrap

_LANGUAGE_NAMES = {
    "Russian": "Русский", "French": "Français", "Italian": "Italiano",
    "German": "Deutsch", "Spanish": "Español", "Indonesian": "Indonesian",
    "Polish": "Polski", "Turkish": "Türkçe", "Portuguese": "Português",
    "Chinese": "中文", "Korean": "한국어", "Japanese": "日本語",
    "English": "English",
}


def _language_names(table: ast.Dict) -> bool:
    if len(table.keys) < 3:
        return False
    for key, value in zip(table.keys, table.values):
        if not isinstance(key, ast.Constant) or not isinstance(value, ast.Constant):
            return False
        if not isinstance(key.value, str) or not isinstance(value.value, str):
            return False
        label = re.sub(r"\{/?font(?:=[^{}]+)?\}", "", value.value)
        if _LANGUAGE_NAMES.get(key.value) != label:
            return False
    return True


def _language(node: ast.AST) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "language" and isinstance(node.value, ast.Name) and node.value.id == "_preferences"


def _label_return(node: ast.AST, table: str) -> bool:
    if not isinstance(node, ast.Return):
        return False
    value = node.value
    return (isinstance(value, ast.Constant) and isinstance(value.value, str)) or (
        isinstance(value, ast.Subscript) and isinstance(value.value, ast.Name)
        and value.value.id == table and _language(value.slice)
    )


def _label_branch(node: ast.AST, table: str) -> bool:
    if _label_return(node, table):
        return True
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not (isinstance(test, ast.Compare) and _language(test.left) and len(test.ops) == 1
            and isinstance(test.ops[0], ast.Eq) and len(test.comparators) == 1
            and isinstance(test.comparators[0], ast.Constant)
            and (test.comparators[0].value is None or isinstance(test.comparators[0].value, str))):
        return False
    return len(node.body) == len(node.orelse) == 1 and _label_branch(node.body[0], table) and _label_branch(node.orelse[0], table)


def fixed_label_functions(scripts: list[str]) -> list[str]:
    """Accept only zero-argument, side-effect-free static dictionary functions.

    Any calls, decorators, dynamic values, extra statements or ambiguous global
    definitions disqualify the function. Source is parsed, never executed.
    """
    candidates: list[str] = []
    definitions: dict[str, int] = {}
    for script in scripts:
        lines = script.splitlines()
        index = 0
        while index < len(lines):
            match = re.fullmatch(r"init(?:\s+(-?\d+))?\s+python:\s*(?:#.*)?", lines[index])
            index += 1
            if not match:
                continue
            body = []
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                body.append(lines[index]); index += 1
            try:
                tree = ast.parse(textwrap.dedent("\n".join(body)))
            except (SyntaxError, ValueError, RecursionError):
                continue
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    definitions[node.name] = definitions.get(node.name, 0) + 1
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name):
                            definitions[target.id] = definitions.get(target.id, 0) + 1
                if int(match.group(1) or 0) >= 999:
                    continue
                if not isinstance(node, ast.FunctionDef) or node.decorator_list:
                    continue
                args = node.args
                if args.posonlyargs or args.args or args.kwonlyargs or args.vararg or args.kwarg or len(node.body) != 2:
                    continue
                assignment, branch = node.body
                if not (isinstance(assignment, ast.Assign) and len(assignment.targets) == 1
                        and isinstance(assignment.targets[0], ast.Name) and isinstance(assignment.value, ast.Dict)):
                    continue
                table = assignment.value
                if not _language_names(table):
                    continue
                if "vietnamese" in [key.value for key in table.keys]:
                    continue
                called_by_text = any(re.search(r"^\s+text\s+" + re.escape(node.name) + r"\(\)\s*:", source, re.M) for source in scripts)
                if called_by_text and _label_branch(branch, assignment.targets[0].id):
                    candidates.append(node.name)
    return sorted(name for name in set(candidates) if definitions.get(name) == 1 and not name.startswith("_vntext_")
                  and not any("_vntext_label_original_" + name in script for script in scripts))


def render_language_support(scripts: list[str]) -> str:
    names = fixed_label_functions(scripts)
    if not names:
        return ""
    lines = ["# VNText fixed language-label support v1", "init 999 python:"]
    for name in names:
        # Identifiers came from the Python parser; never interpolate source code.
        lines.extend([
            f'    if not getattr({name}, "_vntext_language_label", False):',
            f"        _vntext_label_original_{name} = {name}",
            f"        def {name}():",
            '            if _preferences.language == "vietnamese":',
            '                return "{font=DejaVuSans.ttf}Tiếng Việt{/font}"',
            f"            return _vntext_label_original_{name}()",
            f"        {name}._vntext_language_label = True",
        ])
    for variable, item_class in fixed_language_dropdowns(scripts):
        lines.extend([
            f"    if isinstance({variable}.dropdown_list, list):",
            f"        if not any(item.value == \"_vntext_vi\" for item in {variable}.dropdown_list):",
            f'            {variable}.dropdown_list.append({item_class}("_vntext_vi", "{{font=DejaVuSans.ttf}}Tiếng Việt{{/font}}", Language("vietnamese")))',
        ])
    return "\n".join(lines) + "\n\n"


def fixed_language_dropdowns(scripts: list[str]) -> list[tuple[str, str]]:
    """Recognize a single static language list with a pure four-field item.

    The generated addition uses that same item constructor and never changes
    selection, existing items or game source. Ambiguity/dynamic lists opt out.
    """
    nodes = []
    for script in scripts:
        lines = script.splitlines()
        index = 0
        while index < len(lines):
            match = re.fullmatch(r"init(?:\s+(-?\d+))?\s+python:\s*(?:#.*)?", lines[index])
            index += 1
            if not match:
                continue
            body = []
            while index < len(lines) and (not lines[index].strip() or lines[index][:1].isspace()):
                body.append(lines[index]); index += 1
            if int(match.group(1) or 0) >= 999:
                continue
            try:
                nodes.extend(ast.parse(textwrap.dedent("\n".join(body))).body)
            except (SyntaxError, ValueError, RecursionError):
                continue
    definitions = {}
    for node in nodes:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            definitions[node.name] = definitions.get(node.name, 0) + 1
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    definitions[target.id] = definitions.get(target.id, 0) + 1
    classes = set()
    for node in nodes:
        if not isinstance(node, ast.ClassDef) or definitions.get(node.name) != 1 or node.bases or node.decorator_list or node.keywords or len(node.body) != 1:
            continue
        init = node.body[0]
        if not isinstance(init, ast.FunctionDef) or init.name != "__init__" or init.decorator_list:
            continue
        args = init.args
        if [arg.arg for arg in args.args] != ["self", "value", "name", "action", "selected"] or args.posonlyargs or args.kwonlyargs or args.vararg or args.kwarg:
            continue
        if len(args.defaults) != 2 or not all(isinstance(v, ast.Constant) for v in args.defaults) or [v.value for v in args.defaults] != [None, False]:
            continue
        assigned = []
        for statement in init.body:
            if not isinstance(statement, ast.Assign) or len(statement.targets) != 1:
                break
            target = statement.targets[0]
            if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"
                    and isinstance(statement.value, ast.Name) and statement.value.id == target.attr):
                break
            assigned.append(target.attr)
        if assigned == ["value", "name", "action", "selected"]:
            classes.add(node.name)
    candidates = []
    for node in nodes:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name) or definitions.get(node.targets[0].id) != 1:
            continue
        call = node.value
        if not isinstance(call, ast.Call) or len(call.args) != 1 or call.keywords or not isinstance(call.args[0], ast.List):
            continue
        items = call.args[0].elts
        item_class = None
        languages = []
        for item in items:
            if not isinstance(item, ast.Call) or not isinstance(item.func, ast.Name) or item.func.id not in classes or len(item.args) != 3:
                break
            if item_class is not None and item_class != item.func.id:
                break
            item_class = item.func.id
            action = item.args[2]
            if not (isinstance(action, ast.Call) and isinstance(action.func, ast.Name) and action.func.id == "Language"
                    and len(action.args) == 1 and not action.keywords and isinstance(action.args[0], ast.Constant)):
                break
            language = action.args[0].value
            label = item.args[1]
            if not isinstance(label, ast.Constant) or not isinstance(label.value, str):
                break
            expected = "English" if language is None else _LANGUAGE_NAMES.get(language)
            if expected is None or re.sub(r"\{/?font(?:=[^{}]+)?\}", "", label.value) != expected:
                break
            languages.append(language)
        else:
            if len(languages) >= 3 and item_class:
                candidates.append((node.targets[0].id, item_class))
    return candidates if len(candidates) == 1 else []
