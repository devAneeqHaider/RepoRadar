"""Tests for analyzer.services.smell_detector (no DB required)."""
from django.test import SimpleTestCase

from analyzer.services.smell_detector import detect_smells


def _module(
    path,
    imports=(),
    classes=0,
    functions=(),
    loc=10,
    call_edges=(),
    wildcards=(),
):
    return {
        "path": path,
        "imports": [
            {"module": m, "line": 1, "raw": f"import {m}", "wildcard": False}
            for m in imports
        ],
        "imported_modules": sorted(set(imports)),
        "classes": [{"name": f"C{i}", "line": i + 1} for i in range(classes)],
        "functions": [
            {
                "name": name,
                "qualified": name,
                "line": 1,
                "end_line": length,
                "length": length,
            }
            for name, length in functions
        ],
        "call_edges": list(call_edges),
        "loc": loc,
        "ok": True,
    }


def _parsed(modules, name_references=frozenset(), wildcards=()):
    return {
        "modules": modules,
        "module_count": len(modules),
        "class_count": sum(len(m["classes"]) for m in modules.values()),
        "function_count": sum(len(m["functions"]) for m in modules.values()),
        "unparsed_files": [],
        "name_references": set(name_references),
        "wildcard_imports": list(wildcards),
    }


class CircularImportTests(SimpleTestCase):
    def test_three_module_cycle_detected_once(self):
        parsed = _parsed(
            {
                "a": _module("a.py", imports=("b",)),
                "b": _module("b.py", imports=("c",)),
                "c": _module("c.py", imports=("a",)),
                "lonely": _module("lonely.py"),
            }
        )
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        cycles = [s for s in smells if s["type"] == "circular_import"]
        self.assertEqual(len(cycles), 1)
        cycle = cycles[0]
        self.assertEqual(cycle["severity"], "high")
        for mod in ("a", "b", "c"):
            self.assertIn(mod, cycle["title"])

    def test_no_cycle_no_smell(self):
        parsed = _parsed(
            {
                "a": _module("a.py", imports=("b",)),
                "b": _module("b.py"),
            }
        )
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        self.assertFalse(
            [s for s in smells if s["type"] == "circular_import"]
        )


class GodModuleTests(SimpleTestCase):
    def test_sixteen_classes_flagged(self):
        parsed = _parsed({"god": _module("god.py", classes=16)})
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        gods = [s for s in smells if s["type"] == "god_module"]
        self.assertEqual(len(gods), 1)
        self.assertEqual(gods[0]["severity"], "high")
        self.assertIn("god", gods[0]["title"])

    def test_many_functions_flagged(self):
        funcs = [(f"f{i}", 5) for i in range(41)]
        parsed = _parsed({"busy": _module("busy.py", functions=funcs)})
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        self.assertTrue([s for s in smells if s["type"] == "god_module"])

    def test_small_module_clean(self):
        parsed = _parsed({"ok": _module("ok.py", classes=2, functions=[("f", 5)])})
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        self.assertFalse([s for s in smells if s["type"] == "god_module"])


class LongFunctionTests(SimpleTestCase):
    def test_long_function_flagged(self):
        parsed = _parsed({"m": _module("m.py", functions=[("marathon", 51)])})
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        longs = [s for s in smells if s["type"] == "long_function"]
        self.assertEqual(len(longs), 1)
        self.assertEqual(longs[0]["severity"], "medium")


class DeadCodeTests(SimpleTestCase):
    def test_unreferenced_private_function_flagged(self):
        parsed = _parsed(
            {"m": _module("m.py", functions=[("_dead", 3), ("alive", 3), ("_used", 3)],
                            call_edges=[{"caller": "alive", "callee": "_used",
                                         "file": "m.py"}])},
            name_references={"alive"},
        )
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        dead = [s for s in smells if s["type"] == "dead_code"]
        self.assertEqual(len(dead), 1)
        self.assertIn("_dead", dead[0]["title"])
        self.assertEqual(dead[0]["severity"], "low")


class WildcardImportTests(SimpleTestCase):
    def test_wildcard_flagged(self):
        parsed = _parsed(
            {"m": _module("m.py")},
            wildcards=[{"file": "m.py", "line": 7, "module": "os"}],
        )
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        wilds = [s for s in smells if s["type"] == "wildcard_import"]
        self.assertEqual(len(wilds), 1)
        self.assertEqual(wilds[0]["severity"], "medium")
        self.assertEqual(wilds[0]["line"], 7)


class SmellShapeTests(SimpleTestCase):
    def test_ids_increment_and_fields_present(self):
        parsed = _parsed(
            {
                "a": _module("a.py", imports=("b",)),
                "b": _module("b.py", imports=("a",)),
                "god": _module("god.py", classes=16),
            }
        )
        smells = detect_smells(parsed, {"nodes": [], "edges": []})
        self.assertEqual([s["id"] for s in smells], ["1", "2"])
        for smell in smells:
            for field in (
                "id", "type", "severity", "title", "file", "line", "detail",
                "suggestion",
            ):
                self.assertIn(field, smell)
            self.assertIn(smell["severity"], ("high", "medium", "low"))
