"""Deterministic, fast code-smell detection over parsed modules.

Detectors (all pure functions of ``parsed`` + ``graph``):
- circular imports (high)
- god modules: >15 classes OR >40 functions OR >1500 LOC (high)
- long functions: >50 lines (medium)
- dead private code: ``_x`` never referenced by any call edge or name usage (low)
- wildcard imports: ``from x import *`` (medium)

Every smell is ``{"id","type","severity","title","file","line","detail",
"suggestion"}`` with ``id`` an incrementing integer as a string.
"""
import sys

SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}

GOD_MODULE_CLASSES = 15
GOD_MODULE_FUNCTIONS = 40
GOD_MODULE_LOC = 1500
LONG_FUNCTION_LINES = 50


def detect_smells(parsed: dict, graph: dict) -> list[dict]:
    smells: list[dict] = []
    _check_circular_imports(parsed, smells)
    _check_god_modules(parsed, smells)
    _check_long_functions(parsed, smells)
    _check_dead_private_code(parsed, smells)
    _check_wildcard_imports(parsed, smells)
    for index, smell in enumerate(smells, start=1):
        smell["id"] = str(index)
    return smells


def _find_cycles(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """All simple import cycles, canonicalized (rotated, deduplicated)."""
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 10000))
    white, gray, black = 0, 1, 2
    color = {node: white for node in adjacency}
    stack: list[str] = []
    cycles: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        color[node] = gray
        stack.append(node)
        for target in sorted(adjacency.get(node, ())):
            if target not in color:
                continue
            if color[target] == gray:
                raw = stack[stack.index(target):]
                pivot = min(range(len(raw)), key=lambda i: raw[i])
                canonical = tuple(raw[pivot:] + raw[:pivot])
                if canonical not in seen:
                    seen.add(canonical)
                    cycles.append(list(canonical))
            elif color[target] == white:
                visit(target)
        stack.pop()
        color[node] = black

    for node in sorted(adjacency):
        if color[node] == white:
            visit(node)
    return cycles


def _check_circular_imports(parsed: dict, smells: list[dict]) -> None:
    modules: dict = parsed.get("modules", {})
    module_ids = set(modules)
    adjacency = {
        dotted: {t for t in info.get("imported_modules", []) if t in module_ids}
        for dotted, info in modules.items()
    }
    # Map (importer, imported) -> first import line for reporting.
    import_lines: dict[tuple[str, str], int] = {}
    for dotted, info in modules.items():
        for imp in info.get("imports", []):
            import_lines.setdefault((dotted, imp["module"]), imp["line"])

    for cycle in _find_cycles(adjacency):
        chain = " -> ".join(cycle + [cycle[0]])
        first, second = cycle[0], cycle[1]
        smells.append(
            {
                "type": "circular_import",
                "severity": "high",
                "title": f"Circular import: {chain}",
                "file": modules[first]["path"],
                "line": import_lines.get((first, second), 1),
                "detail": (
                    f"Modules {', '.join(cycle)} import each other in a cycle. "
                    "Circular imports make the codebase harder to reason about, "
                    "can cause ImportError at startup, and slow down refactors."
                ),
                "suggestion": (
                    "Break the cycle by extracting the shared code into a third "
                    "module that both sides import, or move one import inside "
                    "the function that needs it."
                ),
            }
        )


def _check_god_modules(parsed: dict, smells: list[dict]) -> None:
    modules: dict = parsed.get("modules", {})
    for dotted in sorted(modules):
        info = modules[dotted]
        n_classes = len(info.get("classes", []))
        n_funcs = len(info.get("functions", []))
        loc = info.get("loc", 0)
        reasons = []
        if n_classes > GOD_MODULE_CLASSES:
            reasons.append(f"{n_classes} classes")
        if n_funcs > GOD_MODULE_FUNCTIONS:
            reasons.append(f"{n_funcs} functions")
        if loc > GOD_MODULE_LOC:
            reasons.append(f"{loc} lines of code")
        if reasons:
            smells.append(
                {
                    "type": "god_module",
                    "severity": "high",
                    "title": f"God module: {dotted or info['path']} ({', '.join(reasons)})",
                    "file": info["path"],
                    "line": 1,
                    "detail": (
                        f"Module {dotted or info['path']} has {', '.join(reasons)}, "
                        "which suggests it owns too many responsibilities."
                    ),
                    "suggestion": (
                        "Split the module by responsibility into smaller focused "
                        "modules (e.g. separate data models, business logic, and "
                        "I/O helpers) and re-export a clean public API."
                    ),
                }
            )


def _check_long_functions(parsed: dict, smells: list[dict]) -> None:
    modules: dict = parsed.get("modules", {})
    for dotted in sorted(modules):
        info = modules[dotted]
        for func in info.get("functions", []):
            if func["length"] > LONG_FUNCTION_LINES:
                smells.append(
                    {
                        "type": "long_function",
                        "severity": "medium",
                        "title": (
                            f"Long function: {func['qualified']} "
                            f"({func['length']} lines)"
                        ),
                        "file": info["path"],
                        "line": func["line"],
                        "detail": (
                            f"{func['qualified']} spans {func['length']} lines "
                            f"(lines {func['line']}-{func['end_line']}), well above "
                            f"the {LONG_FUNCTION_LINES}-line guideline."
                        ),
                        "suggestion": (
                            "Extract logical blocks into small helper functions "
                            "with descriptive names so each function does one thing."
                        ),
                    }
                )


def _is_private(name: str) -> bool:
    return (
        name.startswith("_")
        and not name.startswith("__")
        and name != "_"
        and not name.endswith("__")
    )


def _check_dead_private_code(parsed: dict, smells: list[dict]) -> None:
    modules: dict = parsed.get("modules", {})
    called: set[str] = set()
    for info in modules.values():
        for edge in info.get("call_edges", []):
            called.add(edge["callee"])
    referenced: set[str] = set(parsed.get("name_references", set()))

    for dotted in sorted(modules):
        info = modules[dotted]
        for func in info.get("functions", []):
            name = func["name"]
            if not _is_private(name):
                continue
            if name in called or name in referenced:
                continue
            smells.append(
                {
                    "type": "dead_code",
                    "severity": "low",
                    "title": f"Possibly dead private code: {func['qualified']}",
                    "file": info["path"],
                    "line": func["line"],
                    "detail": (
                        f"{func['qualified']} is private but is never called or "
                        "referenced anywhere in the repository."
                    ),
                    "suggestion": (
                        "If it is genuinely unused, delete it to reduce noise. "
                        "If it is part of a planned API, consider making it "
                        "public or documenting why it exists."
                    ),
                }
            )


def _check_wildcard_imports(parsed: dict, smells: list[dict]) -> None:
    for entry in parsed.get("wildcard_imports", []):
        smells.append(
            {
                "type": "wildcard_import",
                "severity": "medium",
                "title": f"Wildcard import: from {entry['module']} import *",
                "file": entry["file"],
                "line": entry["line"],
                "detail": (
                    f"{entry['file']}:{entry['line']} uses "
                    f"'from {entry['module']} import *', which pollutes the "
                    "namespace, hides where names come from, and can silently "
                    "shadow definitions."
                ),
                "suggestion": (
                    "Import only the names you need explicitly, e.g. "
                    f"'from {entry['module']} import name1, name2'."
                ),
            }
        )
