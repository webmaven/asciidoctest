import importlib.util
import pathlib
import re
import sys
from collections.abc import Iterable
from typing import Any

import pytest
from _pytest._code.code import ExceptionInfo, TerminalRepr

from asciidoctest.parser import (
    extract_docstring_tests,
    find_docstrings_in_py_file,
    parse_adoc_tests,
)
from asciidoctest.runner import AsciiDocTestFailure, run_test_blocks


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register custom command-line and ini configuration options."""
    group = parser.getgroup("asciidoctest")
    group.addoption(
        "--asciidoctest-mode",
        action="store",
        default="explicit",
        choices=["explicit", "eager"],
        help="asciidoctest target selection mode: 'explicit' or 'eager'",
    )
    parser.addini(
        "asciidoctest_mode",
        default="explicit",
        help="asciidoctest target selection mode: 'explicit' or 'eager'",
    )


def pytest_collect_file(
    file_path: pathlib.Path, parent: pytest.Collector
) -> pytest.Collector | None:
    """Hook into file discovery to collect .adoc and .py files."""
    if file_path.suffix == ".adoc":
        return AsciiDocFile.from_parent(parent, path=file_path)
    elif file_path.suffix == ".py":
        try:
            content = file_path.read_text("utf-8")
            # Quick pre-filter to keep discovery extremely fast
            if re.search(r"\[source\s*,\s*python", content):
                return PythonDocstringFile.from_parent(parent, path=file_path)
        except Exception:
            pass
    return None


class AsciiDocFile(pytest.File):
    """Custom collector for standalone .adoc files."""

    def collect(self) -> Iterable[pytest.Item | pytest.Collector]:
        # Retrieve the mode option, default to 'explicit'
        mode = (
            self.config.getoption("--asciidoctest-mode")
            or self.config.getini("asciidoctest_mode")
            or "explicit"
        )
        content = self.path.read_text("utf-8")

        try:
            blocks = parse_adoc_tests(content, mode=mode)
            if blocks:
                # All blocks inside a single file share sequential state, run as one item
                yield AsciiDocItem.from_parent(self, name="asciidoctest", blocks=blocks)
        except Exception as e:
            raise ValueError(f"Failed to parse AsciiDoc file {self.path}: {e}") from e


class AsciiDocItem(pytest.Item):
    """Test execution item for standalone AsciiDoc files."""

    def __init__(self, name: str, parent: pytest.Collector, blocks: list[Any]) -> None:
        super().__init__(name, parent)
        self.blocks = blocks
        self._fixtureinfo = getattr(self.session, "_fixturemanager", None)
        if self._fixtureinfo is not None:
            self._fixtureinfo = self.session._fixturemanager.getfixtureinfo(
                node=self, func=None, cls=None
            )

    def runtest(self) -> None:
        shared_globals: dict[str, Any] = {}
        run_test_blocks(self.blocks, shared_globals)

    def repr_failure(
        self,
        excinfo: ExceptionInfo[BaseException],
        style: Any = None,
    ) -> str | TerminalRepr:
        if isinstance(excinfo.value, AsciiDocTestFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo, style=style)

    def reportinfo(self) -> tuple[pathlib.Path | str, int | None, str]:
        return self.path, 0, f"AsciiDoc Document: {self.name}"


class PythonDocstringFile(pytest.File):
    """Custom collector for Python files with AsciiDoc-formatted docstrings."""

    def collect(self) -> Iterable[pytest.Item | pytest.Collector]:
        try:
            docstrings = find_docstrings_in_py_file(self.path)
        except Exception:
            return

        mode = (
            self.config.getoption("--asciidoctest-mode")
            or self.config.getini("asciidoctest_mode")
            or "explicit"
        )

        for name, lineno, docstring in docstrings:
            try:
                tests = extract_docstring_tests(docstring, mode=mode)
                if tests:
                    yield DocstringTestItem.from_parent(
                        self, name=f"{name}_docstring", lineno=lineno, blocks=tests
                    )
            except Exception:
                pass


class DocstringTestItem(pytest.Item):
    """Test execution item for Python docstring test blocks."""

    def __init__(
        self, name: str, parent: pytest.Collector, lineno: int, blocks: list[Any]
    ) -> None:
        super().__init__(name, parent)
        self.lineno = lineno
        self.blocks = blocks
        self._fixtureinfo = getattr(self.session, "_fixturemanager", None)
        if self._fixtureinfo is not None:
            self._fixtureinfo = self.session._fixturemanager.getfixtureinfo(
                node=self, func=None, cls=None
            )

    def runtest(self) -> None:
        # Dynamically load the containing module
        module_name = self.path.stem
        spec = importlib.util.spec_from_file_location(module_name, self.path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load spec for {self.path}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise RuntimeError(f"Error executing module {module_name}: {e}") from e

        # Run docstring tests in a copy of the module's globals dictionary
        globals_copy = dict(module.__dict__)
        run_test_blocks(self.blocks, globals_copy)

    def repr_failure(
        self,
        excinfo: ExceptionInfo[BaseException],
        style: Any = None,
    ) -> str | TerminalRepr:
        if isinstance(excinfo.value, AsciiDocTestFailure):
            return str(excinfo.value)
        return super().repr_failure(excinfo, style=style)

    def reportinfo(self) -> tuple[pathlib.Path | str, int | None, str]:
        return self.path, self.lineno, f"Python Docstring: {self.name}"
