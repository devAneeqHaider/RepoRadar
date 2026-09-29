"""Tests for analyzer.services.python_parser (no DB required)."""
import os
import tempfile

from django.test import SimpleTestCase

from analyzer.services.python_parser import module_name_from_path, parse_python_files

SAMPLE_SOURCE = '''\
import os
import pkg.util
from pkg import helpers
from . import sibling
from .sub import thing
from .. import parent_mod
from wild import *


class Foo:
    def method_one(self):
        helper()
        self._private()

    def _private(self):
        pass


def helper():
    util_func()


def util_func():
    pass


def _unused_private():
    pass
'''


def _write_sample(tmpdir: str, rel_path: str = "pkg/sample.py") -> list[dict]:
    abs_path = os.path.join(tmpdir, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(SAMPLE_SOURCE)
    return [
        {
            "path": rel_path.replace(os.sep, "/"),
            "language": "Python",
            "size": len(SAMPLE_SOURCE),
        }
    ]


class ModuleNameTests(SimpleTestCase):
    def test_init_maps_to_package(self):
        self.assertEqual(module_name_from_path("pkg/__init__.py"), "pkg")

    def test_nested_module(self):
        self.assertEqual(module_name_from_path("a/b.py"), "a.b")


class ParsePythonFilesTests(SimpleTestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="reporadar-test-")
        self.files = _write_sample(self.tmpdir)

    def test_imports_resolved(self):
        parsed = parse_python_files(self.tmpdir, self.files)
        info = parsed["modules"]["pkg.sample"]
        imported = set(info["imported_modules"])
        # Absolute imports stay absolute...
        self.assertIn("os", imported)
        self.assertIn("pkg.util", imported)
        self.assertIn("pkg", imported)  # from pkg import helpers
        self.assertIn("wild", imported)  # from wild import *
        # ...relative imports resolve against the current package.
        self.assertIn("pkg.sibling", imported)  # from . import sibling
        self.assertIn("pkg.sub", imported)  # from .sub import thing
        self.assertIn("parent_mod", imported)  # from .. import parent_mod

    def test_classes_and_functions(self):
        parsed = parse_python_files(self.tmpdir, self.files)
        info = parsed["modules"]["pkg.sample"]
        self.assertEqual(
            [c["name"] for c in info["classes"]], ["Foo"]
        )
        self.assertEqual(info["classes"][0]["line"], 10)
        names = {f["name"] for f in info["functions"]}
        self.assertEqual(
            names,
            {"method_one", "_private", "helper", "util_func", "_unused_private"},
        )
        helper = next(f for f in info["functions"] if f["name"] == "helper")
        self.assertGreater(helper["length"], 1)
        self.assertEqual(helper["end_line"], helper["line"] + helper["length"] - 1)

    def test_within_file_call_edges(self):
        parsed = parse_python_files(self.tmpdir, self.files)
        edges = parsed["modules"]["pkg.sample"]["call_edges"]
        pairs = {(e["caller"], e["callee"]) for e in edges}
        self.assertIn(("Foo.method_one", "helper"), pairs)
        self.assertIn(("Foo.method_one", "_private"), pairs)  # self._private()
        self.assertIn(("helper", "util_func"), pairs)
        # _unused_private is never called -> no edge targets it.
        self.assertNotIn("_unused_private", {e["callee"] for e in edges})

    def test_wildcard_import_recorded(self):
        parsed = parse_python_files(self.tmpdir, self.files)
        self.assertEqual(len(parsed["wildcard_imports"]), 1)
        wild = parsed["wildcard_imports"][0]
        self.assertEqual(wild["file"], "pkg/sample.py")
        self.assertEqual(wild["module"], "wild")

    def test_syntax_error_does_not_crash(self):
        bad_path = os.path.join(self.tmpdir, "broken.py")
        with open(bad_path, "w", encoding="utf-8") as fh:
            fh.write("def oops(:\n  this is not python\n")
        files = self.files + [
            {"path": "broken.py", "language": "Python", "size": 10}
        ]
        parsed = parse_python_files(self.tmpdir, files)
        self.assertIn("broken.py", parsed["unparsed_files"])
        self.assertIn("pkg.sample", parsed["modules"])
