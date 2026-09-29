"""AST-based parsing of Python source files.

Produces a JSON-serializable model of every module: imports (resolved to
in-repo dotted names where possible), classes, functions (including methods
and nested functions), and simple within-file call edges. Files that fail
to parse are recorded in ``unparsed_files`` and never abort the run.
"""
import ast
import os


def module_name_from_path(rel_path: str) -> str:
    """Derive a dotted module name from a repo-relative path.

    ``pkg/__init__.py`` -> ``pkg``; ``a/b.py`` -> ``a.b``.
    """
    normalized = rel_path.replace(os.sep, "/")
    if normalized.endswith(".py"):
        normalized = normalized[: -len(".py")]
    parts = [p for p in normalized.split("/") if p]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _current_package(module_name: str, is_package: bool) -> str:
    if is_package:
        return module_name
    parts = module_name.split(".")
    return ".".join(parts[:-1])


def _resolve_relative_base(
    module_name: str, is_package: bool, level: int
) -> list[str] | None:
    """Base package parts for ``from .[*level] import ...`` (level dots)."""
    package = _current_package(module_name, is_package)
    pkg_parts = package.split(".") if package else []
    up = level - 1  # level=1 stays in the current package
    if up > len(pkg_parts):
        return None
    return pkg_parts[: len(pkg_parts) - up]


def _resolve_relative(
    module_name: str, is_package: bool, level: int, target: str | None
) -> str | None:
    """Resolve ``from .[target] import ...`` (level dots) to a dotted name."""
    base = _resolve_relative_base(module_name, is_package, level)
    if base is None:
        return None
    if target:
        base = base + target.split(".")
    return ".".join(base) or None


class _Collector(ast.NodeVisitor):
    """Collect classes and functions (incl. methods and nested functions)."""

    def __init__(self) -> None:
        self.classes: list[dict] = []
        self.functions: list[dict] = []
        self._class_stack: list[str] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.classes.append({"name": node.name, "line": node.lineno})
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_function(node)
        self.generic_visit(node)

    def _record_function(self, node: ast.AST) -> None:
        qualified = (
            ".".join(self._class_stack + [node.name])
            if self._class_stack
            else node.name
        )
        end_line = getattr(node, "end_lineno", None) or node.lineno
        self.functions.append(
            {
                "name": node.name,
                "qualified": qualified,
                "line": node.lineno,
                "end_line": end_line,
                "length": end_line - node.lineno + 1,
                "node": node,  # transient: stripped before returning
            }
        )


def _extract_imports(
    tree: ast.AST, module_name: str, is_package: bool
) -> tuple[list[dict], list[dict]]:
    """Return (imports, wildcard_imports) for one module's AST."""
    imports: list[dict] = []
    wildcards: list[dict] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    {
                        "module": alias.name,
                        "line": node.lineno,
                        "raw": f"import {alias.asname or alias.name}"
                        if alias.asname
                        else f"import {alias.name}",
                        "wildcard": False,
                    }
                )
        elif isinstance(node, ast.ImportFrom):
            level = node.level or 0
            from_mod = node.module or ""
            is_wildcard = any(a.name == "*" for a in node.names)
            raw = f"from {'.' * level}{from_mod} import ..."
            if level and not from_mod:
                # `from . import x` / `from .. import z`: each imported name
                # is treated as a submodule of the resolved base package.
                base = _resolve_relative_base(module_name, is_package, level)
                base_name = ".".join(base) if base is not None else ""
                resolved_names: list[str] = []
                for alias in node.names:
                    if alias.name == "*":
                        if base_name:
                            resolved_names.append(base_name)
                    elif base_name:
                        resolved_names.append(f"{base_name}.{alias.name}")
                    else:
                        resolved_names.append(alias.name)
            elif level:
                resolved = _resolve_relative(
                    module_name, is_package, level, from_mod or None
                )
                resolved_names = [resolved] if resolved else []
            else:
                resolved_names = [from_mod] if from_mod else []
            for resolved in resolved_names:
                entry = {
                    "module": resolved,
                    "line": node.lineno,
                    "raw": raw,
                    "wildcard": is_wildcard,
                }
                imports.append(entry)
                if is_wildcard:
                    wildcards.append(entry)
    # Drop unresolvable relative imports (e.g. "from ... import" past top level).
    imports = [i for i in imports if i["module"]]
    wildcards = [w for w in wildcards if w["module"]]
    return imports, wildcards


def _extract_call_edges(functions: list[dict], rel_path: str) -> list[dict]:
    """Within-file call edges: caller qualified name -> callee short name.

    Matches ``Name`` calls and ``Attribute`` calls (e.g. ``self.helper()``)
    against function names defined in the same file. Self-recursive calls
    are excluded so they don't mask dead code.
    """
    defined = {f["name"] for f in functions}
    edges: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for func in functions:
        callees: set[str] = set()
        for node in ast.walk(func["node"]):
            if not isinstance(node, ast.Call):
                continue
            target = node.func
            callee = None
            if isinstance(target, ast.Name):
                callee = target.id
            elif isinstance(target, ast.Attribute):
                callee = target.attr
            if callee and callee in defined and callee != func["name"]:
                callees.add(callee)
        for callee in sorted(callees):
            key = (func["qualified"], callee)
            if key not in seen:
                seen.add(key)
                edges.append(
                    {"caller": func["qualified"], "callee": callee, "file": rel_path}
                )
    return edges


def _collect_name_references(tree: ast.AST) -> set[str]:
    """All loaded ``Name`` identifiers in a file (feeds dead-code detection)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            names.add(node.id)
    return names


def parse_python_files(root: str, files: list[dict]) -> dict:
    """Parse every Python file under ``root``.

    ``files`` is the walker output. Returns a dict with ``modules`` keyed by
    dotted name, plus aggregate counts, ``unparsed_files``, ``name_references``
    (transient set) and ``wildcard_imports``.
    """
    modules: dict[str, dict] = {}
    unparsed_files: list[str] = []
    name_references: set[str] = set()
    wildcard_imports: list[dict] = []
    class_count = 0
    function_count = 0

    for entry in files:
        if entry["language"] != "Python":
            continue
        rel_path = entry["path"]
        abs_path = os.path.join(root, rel_path)
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
        except OSError:
            unparsed_files.append(rel_path)
            continue
        loc = source.count("\n") + 1
        try:
            tree = ast.parse(source, filename=rel_path)
        except SyntaxError:
            unparsed_files.append(rel_path)
            continue

        dotted = module_name_from_path(rel_path)
        is_package = rel_path.replace(os.sep, "/").endswith("__init__.py")
        imports, wildcards = _extract_imports(tree, dotted, is_package)
        collector = _Collector()
        collector.visit(tree)
        call_edges = _extract_call_edges(collector.functions, rel_path)
        name_references.update(_collect_name_references(tree))
        for w in wildcards:
            wildcard_imports.append(
                {"file": rel_path, "line": w["line"], "module": w["module"]}
            )

        imported_modules = sorted({i["module"] for i in imports})
        public_functions = [
            {k: f[k] for k in ("name", "qualified", "line", "end_line", "length")}
            for f in collector.functions
        ]
        modules[dotted] = {
            "path": rel_path,
            "imports": imports,
            "imported_modules": imported_modules,
            "classes": collector.classes,
            "functions": public_functions,
            "call_edges": call_edges,
            "loc": loc,
            "ok": True,
        }
        class_count += len(collector.classes)
        function_count += len(collector.functions)

    return {
        "modules": modules,
        "module_count": len(modules),
        "class_count": class_count,
        "function_count": function_count,
        "unparsed_files": sorted(unparsed_files),
        "name_references": name_references,
        "wildcard_imports": wildcard_imports,
    }
