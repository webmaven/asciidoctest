import inspect
import pathlib
import sys
import unittest
from typing import Any

from asciidoctest.parser import extract_docstring_tests, parse_adoc_tests
from asciidoctest.runner import run_test_blocks


class AsciiDocTestCase(unittest.TestCase):
    """TestCase representing sequential execution of test blocks in an .adoc file."""

    def __init__(self, name: str, blocks: list[Any], description: str = ""):
        super().__init__()
        self._name = name
        self._blocks = blocks
        self._description = description

    def runTest(self):
        shared_globals = {}
        run_test_blocks(self._blocks, shared_globals)

    def id(self):
        return self._name

    def shortDescription(self):
        return self._description or self._name

    def __str__(self):
        return f"{self._name} ({self.__class__.__module__}.{self.__class__.__name__})"


class DocstringTestCase(unittest.TestCase):
    """TestCase representing execution of Python docstring tests in module scope."""

    def __init__(
        self,
        name: str,
        blocks: list[Any],
        module_globals: dict[str, Any],
        description: str = "",
    ):
        super().__init__()
        self._name = name
        self._blocks = blocks
        self._module_globals = module_globals
        self._description = description

    def runTest(self):
        # Execute in a copy of the module globals to avoid state leakage across docstrings
        globals_copy = dict(self._module_globals)
        run_test_blocks(self._blocks, globals_copy)

    def id(self):
        return self._name

    def shortDescription(self):
        return self._description or self._name

    def __str__(self):
        return f"{self._name} ({self.__class__.__module__}.{self.__class__.__name__})"


def DocFileSuite(*paths, **kwargs) -> unittest.TestSuite:
    """
    Creates a unittest.TestSuite for running test blocks extracted from AsciiDoc files.
    """
    mode = kwargs.get("mode", "explicit")
    suite = unittest.TestSuite()

    for path_str in paths:
        path = pathlib.Path(path_str)
        content = path.read_text("utf-8")
        blocks = parse_adoc_tests(content, mode=mode)
        if blocks:
            test_case = AsciiDocTestCase(
                name=f"DocFile_{path.stem}",
                blocks=blocks,
                description=f"AsciiDoc tests from {path.name}",
            )
            suite.addTest(test_case)

    return suite


def DocTestSuite(module, **kwargs) -> unittest.TestSuite:
    """
    Creates a unittest.TestSuite for running AsciiDoc docstring tests from a module.
    """
    mode = kwargs.get("mode", "explicit")

    if isinstance(module, str):
        if module in sys.modules:
            mod = sys.modules[module]
        else:
            mod = __import__(module, globals(), locals(), ["*"])
    else:
        mod = module

    suite = unittest.TestSuite()
    discovered = set()

    def process_object(name: str, obj: Any):
        if obj in discovered:
            return
        discovered.add(obj)

        docstring = inspect.getdoc(obj)
        if docstring:
            try:
                tests = extract_docstring_tests(docstring, mode=mode)
                if tests:
                    # Capture current module globals dict
                    test_case = DocstringTestCase(
                        name=f"Docstring_{name}",
                        blocks=tests,
                        module_globals=mod.__dict__,
                        description=f"Docstring tests for {name}",
                    )
                    suite.addTest(test_case)
            except Exception:
                pass

    # Process the module docstring
    process_object(mod.__name__, mod)

    # Process members of the module
    for attr_name, member in inspect.getmembers(mod):
        # Keep only objects belonging to this module
        if hasattr(member, "__module__") and member.__module__ != mod.__name__:
            continue

        if inspect.isclass(member):
            process_object(f"{mod.__name__}.{attr_name}", member)
            for sub_name, sub_member in inspect.getmembers(
                member, predicate=inspect.isroutine
            ):
                process_object(f"{mod.__name__}.{attr_name}.{sub_name}", sub_member)
        elif inspect.isroutine(member):
            process_object(f"{mod.__name__}.{attr_name}", member)

    return suite
