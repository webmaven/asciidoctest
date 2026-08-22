# Implementation Plan - Address GitHub Issues #1, #2, and #3

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve open GitHub issues in `asciidoctest`: prevent include preprocessing crashes on standalone documents (#1), implement AST section boundary scoping, named context scopes, and explicit reset markers (#2), and provide direct Python source and docstring doctest extraction with per-symbol isolation (#3).

**Architecture:**
1. Configure AsciiDoc AST parser (`asciidoctest/parser.py`) to disable directive preprocessing by default (`preprocess_directives=False`), preventing missing illustrative includes from crashing doctest extraction.
2. Extend `SafeTestBlockExtractorVisitor` and `asciidoctest/runner.py` to support section boundary tracking, named context tags (`shared="context_name"`), and reset markers (`[source,python,reset]`).
3. Add `asciidoctest.extract_and_run_docstring_tests(source_path_or_module, mode='explicit')` for programmatic extraction of doctests directly from Python files, directories, and module objects with symbol-level isolation.
4. Prevent `pytest` dependency leakage by moving `find_docstrings_in_py_file` from `pytest_plugin.py` to `parser.py` so the core extraction API remains framework-agnostic.

**Tech Stack:** Python >= 3.14, `asciidoctrine>=0.2.0a2`, `asciidocstring>=0.1.0a7`, `lark>=1.3.1`, `pytest`, `unittest`.

## Global Constraints

- Python 3.14+ compatibility.
- Minimum dependencies: `asciidoctrine>=0.2.0a2`, `asciidocstring>=0.1.0a7`.
- Follow existing formatting and linting rules (Ruff line length 88, rules E, F, I, UP, B; ignore S102, E501).
- Strictly adhere to Test-Driven Development (TDD): write failing tests first, verify red, implement minimal code, verify green.
- Backward compatibility: existing tests in `tests/` must remain passing.

---

### Task 1: Fix Issue #1 - PreprocessorError on Illustrative Includes

**Files:**
- Modify: `asciidoctest/parser.py:50-70`
- Test: `tests/test_parser_includes.py`

**Interfaces:**
- Consumes: `asciidoctrine.lark_parser.parse_to_ast(source, preprocess_directives=False)`
- Produces: `parse_adoc_tests(content: str, mode: str = "explicit", preprocess_directives: bool = False) -> list[TestBlock]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_parser_includes.py`:
```python
import textwrap
import pytest
from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import run_test_blocks


def test_parse_adoc_with_missing_illustrative_include():
    content = textwrap.dedent("""\
        = Document with Illustrative Include

        include::non_existent_file_illustrative.adoc[]

        [source,python,test]
        ----
        x = 10
        assert x == 10
        ----
        """)
    # Should not raise PreprocessorError
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 1
    assert "assert x == 10" in blocks[0].content

    # Execute blocks
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_parse_adoc_with_custom_preprocess_directives_flag():
    content = textwrap.dedent("""\
        = Document

        [source,python,test]
        ----
        y = 20
        assert y == 20
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit", preprocess_directives=False)
    assert len(blocks) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parser_includes.py -v`
Expected: FAIL with `asciidoctrine.preprocessor.PreprocessorError: Include file not found`

- [ ] **Step 3: Write minimal implementation**

Modify `asciidoctest/parser.py`:
Update `parse_adoc_tests` to accept `preprocess_directives: bool = False` and pass it to `parse_to_ast`:
```python
def parse_adoc_tests(
    content: str, mode: str = "explicit", preprocess_directives: bool = False
) -> list[Any]:
    """
    Parses AsciiDoc source string and extracts python test blocks under
    a unified, symmetric safety-first design.
    """
    try:
        ast = parse_to_ast(content, preprocess_directives=preprocess_directives)
    except Exception as e:
        raise ValueError(f"AsciiDoc Parse Error: {e}") from e

    visitor = SafeTestBlockExtractorVisitor(
        target_language="python", requires_test_marker=False
    )
    all_blocks = visitor.extract(ast)

    def has_explicit_markers(block: Any) -> bool:
        return block_has_test_marker(block) or block_has_shared_marker(block)

    any_explicit = any(has_explicit_markers(b) for b in all_blocks)

    if any_explicit:
        return [b for b in all_blocks if has_explicit_markers(b)]
    else:
        if mode == "eager":
            return all_blocks
        return []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_parser_includes.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite and commit**

Run: `pytest`
Expected: All passed

Commit:
```bash
git add tests/test_parser_includes.py asciidoctest/parser.py
git commit -m "fix: disable include preprocessing by default during doctest parsing (#1)"
```

---

### Task 2: Refactor `find_docstrings_in_py_file` out of pytest plugin

**Files:**
- Modify: `asciidoctest/parser.py`
- Modify: `asciidoctest/pytest_plugin.py`

**Interfaces:**
- Consumes: Python source code AST
- Produces: Framework-agnostic static docstring extraction in `parser.py` to prevent `pytest` dependency leakage.

- [ ] **Step 1: Move implementation**

In `asciidoctest/parser.py`, add the required `ast` import and the extraction function:
```python
import ast


def find_docstrings_in_py_file(path) -> list[tuple[str, int, str]]:
    """Statically parse a Python file and return all docstrings with metadata."""
    content = path.read_text("utf-8")
    try:
        tree = ast.parse(content)
    except SyntaxError, ValueError:
        return []

    docstrings = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            docstring = ast.get_docstring(node)
            if docstring:
                lineno = getattr(node, "lineno", 1)
                name = node.name if hasattr(node, "name") else "<module>"
                docstrings.append((name, lineno, docstring))
    return docstrings
```

- [ ] **Step 2: Update callers**

In `asciidoctest/pytest_plugin.py`:
Remove the `find_docstrings_in_py_file` definition.
Update the imports:
```python
import importlib.util
import sys

import pytest

from asciidoctest.parser import (
    extract_docstring_tests,
    find_docstrings_in_py_file,
    parse_adoc_tests,
)
from asciidoctest.runner import AsciiDocTestFailure, run_test_blocks
```

- [ ] **Step 3: Run full test suite to verify refactor**

Run: `pytest tests/test_plugin.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add asciidoctest/parser.py asciidoctest/pytest_plugin.py
git commit -m "refactor: move find_docstrings_in_py_file to parser to avoid pytest dependency"
```

---

### Task 3: Implement Issue #2 - Reset Marker & Named Context Scopes

**Files:**
- Modify: `asciidoctest/parser.py`
- Modify: `asciidoctest/runner.py`
- Test: `tests/test_scoping.py`

**Interfaces:**
- Consumes: Block attributes
- Produces: `block_has_reset_marker(block)`, `block_get_shared_context(block)`, updated `run_test_blocks`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_scoping.py`:
```python
import textwrap
import pytest
from asciidoctest.parser import (
    block_has_reset_marker,
    block_get_shared_context,
    parse_adoc_tests,
)
from asciidoctest.runner import run_test_blocks, AsciiDocTestFailure


class MockBlock:
    def __init__(self, content, is_interactive=False, line_number=1, attributes=None):
        self.content = content
        self.is_interactive = is_interactive
        self.line_number = line_number
        self.attributes = attributes or {}


def test_explicit_reset_marker():
    blocks = [
        MockBlock("a = 10", attributes={"shared": "true"}),
        MockBlock("assert a == 10", attributes={"shared": "true"}),
        MockBlock("b = 20", attributes={"reset": "true", "shared": "true"}),
        MockBlock(
            "assert 'a' not in globals() and b == 20", attributes={"shared": "true"}
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert "a" not in shared_globals
    assert shared_globals.get("b") == 20


def test_named_context_scopes():
    blocks = [
        MockBlock("x = 100", attributes={"shared": "ctx_a"}),
        MockBlock("y = 200", attributes={"shared": "ctx_b"}),
        MockBlock(
            "assert x == 100 and 'y' not in globals()", attributes={"shared": "ctx_a"}
        ),
        MockBlock(
            "assert y == 200 and 'x' not in globals()", attributes={"shared": "ctx_b"}
        ),
        MockBlock(
            "assert 'x' not in globals() and 'y' not in globals()",
            attributes={"shared": "true"},
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_named_context_ephemeral_test():
    blocks = [
        MockBlock("val = 'persistent'", attributes={"shared": "db_ctx"}),
        MockBlock(
            "assert val == 'persistent'\nval = 'mutated'\n",
            attributes={"shared": "db_ctx", "test": "true"},
        ),
        MockBlock("assert val == 'persistent'", attributes={"shared": "db_ctx"}),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_parse_named_context_and_reset_from_adoc():
    content = textwrap.dedent("""\
        = Document

        [source,python,shared="auth_flow"]
        ----
        token = "secret123"
        ----

        [source,python,shared="auth_flow"]
        ----
        assert token == "secret123"
        ----

        [source,python,reset]
        ----
        z = 99
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 3
    assert block_get_shared_context(blocks[0]) == "auth_flow"
    assert block_has_reset_marker(blocks[2]) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoping.py -v`
Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

In `asciidoctest/parser.py`, add helpers:
```python
def block_has_reset_marker(block: Any) -> bool:
    """
    Inspects a block's attributes, roles, and positional parameters
    to determine if it has been marked with a 'reset' directive.
    """
    attrs = getattr(block, "attributes", {}) or {}
    return (
        "reset" in attrs
        or attrs.get("reset") == "true"
        or attrs.get("role") == "reset"
        or "reset" in attrs.get("positional", [])
        or ("reset" in str(attrs.get("role", "")).split())
    )


def block_get_shared_context(block: Any) -> str | None:
    """
    Returns the named shared context identifier if specified (e.g. shared="context_name"),
    or None if it uses default shared context or is not shared.
    """
    attrs = getattr(block, "attributes", {}) or {}
    shared_val = attrs.get("shared")
    if shared_val and str(shared_val).lower() not in ("true", "1", "yes"):
        return str(shared_val)
    return None
```

In `asciidoctest/runner.py`, update `run_test_blocks`:
```python
from asciidoctest.parser import (
    block_get_shared_context,
    block_has_reset_marker,
    block_has_shared_marker,
    block_has_test_marker,
)
import doctest
import traceback
from typing import Any


class AsciiDocTestFailure(AssertionError):
    """Exception raised when an asciidoc test block execution fails."""


class CustomDocTestRunner(doctest.DocTestRunner):
    """A customized doctest runner that gathers failures in-memory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.test_failures = []

    def report_failure(self, out, test, example, got):
        msg = (
            f"Failed example:\n    {example.source.strip()}\n"
            f"Expected:\n    {example.want.strip()}\n"
            f"Got:\n    {got.strip()}"
        )
        self.test_failures.append((example, got, msg))

    def report_unexpected_exception(self, out, test, example, exc_info):
        tb_str = "".join(traceback.format_exception(*exc_info))
        msg = (
            f"Failed example:\n    {example.source.strip()}\n"
            f"Unexpected Exception:\n{tb_str}"
        )
        self.test_failures.append((example, exc_info, msg))


def run_test_blocks(blocks: list[Any], shared_globals: dict[str, Any]) -> None:
    """
    Executes a sequence of test blocks under a unified, symmetric state model.
    Supports section boundaries, named context scopes, and explicit reset markers.
    """
    optionflags = doctest.ELLIPSIS | doctest.IGNORE_EXCEPTION_DETAIL
    initial_globals = shared_globals.copy()
    named_contexts: dict[str, dict[str, Any]] = {}
    current_section_id = None

    for block in blocks:
        block_section_id = getattr(block, "attributes", {}).get("__section_id__")
        if (
            block_section_id is not None
            and current_section_id is not None
            and block_section_id != current_section_id
        ):
            shared_globals.clear()
            shared_globals.update(initial_globals.copy())
            named_contexts.clear()
        if block_section_id is not None:
            current_section_id = block_section_id

        has_reset = block_has_reset_marker(block)
        if has_reset:
            shared_globals.clear()
            shared_globals.update(initial_globals.copy())
            named_contexts.clear()

        has_test = block_has_test_marker(block)
        has_shared = block_has_shared_marker(block)
        context_name = block_get_shared_context(block)

        if context_name:
            if context_name not in named_contexts:
                named_contexts[context_name] = initial_globals.copy()
            target_shared = named_contexts[context_name]
        else:
            target_shared = shared_globals

        if has_shared and has_test:
            test_globals = target_shared.copy()
            should_write_back = False
        elif has_shared or context_name:
            test_globals = target_shared
            should_write_back = True
        else:
            test_globals = initial_globals.copy()
            should_write_back = False

        if getattr(block, "is_interactive", False):
            parser = doctest.DocTestParser()
            test = parser.get_doctest(
                block.content,
                test_globals,
                name=f"block_at_line_{block.line_number}",
                filename="<string>",
                lineno=block.line_number,
            )
            runner = CustomDocTestRunner(optionflags=optionflags)
            runner.run(test, clear_globs=False)

            if should_write_back:
                target_shared.update(test.globs)

            if runner.test_failures:
                first_fail_msg = runner.test_failures[0][2]
                raise AsciiDocTestFailure(
                    f"Test block failure at line {block.line_number}:\n{first_fail_msg}"
                )
        else:
            try:
                code_content = block.content
                if not code_content.endswith("\n"):
                    code_content += "\n"
                compiled_code = compile(
                    code_content, f"<block_at_line_{block.line_number}>", "exec"
                )
                exec(compiled_code, test_globals)
            except AssertionError:
                tb = traceback.format_exc()
                raise AsciiDocTestFailure(
                    f"Assertion failed in non-interactive block at line {block.line_number}:\n{tb}"
                ) from None
            except Exception:
                tb = traceback.format_exc()
                raise AsciiDocTestFailure(
                    f"Exception raised in non-interactive block at line {block.line_number}:\n{tb}"
                ) from None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scoping.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add asciidoctest/parser.py asciidoctest/runner.py tests/test_scoping.py
git commit -m "feat: add reset markers and named context scopes (#2)"
```

---

### Task 4: Implement Issue #2 - AST Section Boundary Scoping

**Files:**
- Modify: `asciidoctest/parser.py`
- Test: `tests/test_section_scoping.py`

**Interfaces:**
- Consumes: AST Section nodes
- Produces: `SafeTestBlockExtractorVisitor` annotating `__section_id__` on block attributes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_section_scoping.py`:
```python
import textwrap
import pytest
from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import run_test_blocks


def test_section_boundary_resets_shared_state():
    content = textwrap.dedent("""\
        = API Documentation

        == class ClassA

        [source,python,shared]
        ----
        client = "Client A Instance"
        ----

        [source,python,shared]
        ----
        assert client == "Client A Instance"
        ----

        == class ClassB

        [source,python,shared]
        ----
        # Crossing the Section boundary from ClassA to ClassB should reset shared_globals
        assert 'client' not in globals()
        client = "Client B Instance"
        ----

        [source,python,shared]
        ----
        assert client == "Client B Instance"
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 4
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_section_scoping.py -v`
Expected: FAIL (`AssertionError` because `client` leaked across `== class ClassB`)

- [ ] **Step 3: Write minimal implementation**

In `asciidoctest/parser.py`, update `SafeTestBlockExtractorVisitor`:
```python
class SafeTestBlockExtractorVisitor(TestBlockExtractorVisitor):
    """
    A robust subclass of TestBlockExtractorVisitor that safely handles raw strings
    or other non-Node elements encountered during generic AST traversal, and tracks
    top-level Section boundaries.
    """

    def __init__(self, target_language: str, requires_test_marker: bool):
        super().__init__(target_language, requires_test_marker)
        self._current_section_id = 0
        self._section_counter = 0

    def visit(self, node: Any, **kwargs: Any) -> Any:
        if isinstance(node, str) or not hasattr(node, "name"):
            return None

        if getattr(node, "name", "") == "section":
            level = getattr(node, "level", 1)
            if level <= 1:
                self._section_counter += 1
                prev_section_id = self._current_section_id
                self._current_section_id = self._section_counter
                result = super().visit(node, **kwargs)
                self._current_section_id = prev_section_id
                return result

        return super().visit(node, **kwargs)

    def visit_listing(self, node: Any) -> None:
        count_before = len(self.extracted_tests)
        super().visit_listing(node)
        if len(self.extracted_tests) > count_before:
            block = self.extracted_tests[-1]
            if getattr(block, "attributes", None) is None:
                block.attributes = {}
            block.attributes["__section_id__"] = self._current_section_id
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_section_scoping.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite and commit**

Run: `pytest`
Expected: All tests pass

Commit:
```bash
git add asciidoctest/parser.py tests/test_section_scoping.py
git commit -m "feat: implement AST section boundary scoping (#2)"
```

---

### Task 5: Implement Issue #3 - Direct Docstring Doctest Extraction

**Files:**
- Modify: `asciidoctest/__init__.py`
- Create: `asciidoctest/docstring_extractor.py`
- Test: `tests/test_docstring_extraction.py`

**Interfaces:**
- Consumes: Python file path (`str` or `pathlib.Path`), directory path, module object, or module name string.
- Produces: `asciidoctest.extract_and_run_docstring_tests(source_path_or_module, mode: str = 'explicit') -> dict[str, Any]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_docstring_extraction.py`:
```python
import sys
import types
import textwrap
import pytest
import asciidoctest
from asciidoctest import extract_and_run_docstring_tests
from asciidoctest.runner import AsciiDocTestFailure


def test_extract_and_run_docstring_tests_from_module_object():
    mod = types.ModuleType("test_sample_mod")
    mod_code = textwrap.dedent('''\
        def func_a(x):
            """
            [source,python,test]
            ----
            >>> func_a(5)
            10
            ----
            """
            return x * 2

        class MyClass:
            """
            [source,python,shared]
            ----
            obj = MyClass(3)
            ----
            [source,python,shared]
            ----
            assert obj.val == 3
            ----
            """
            def __init__(self, val):
                self.val = val
    ''')
    exec(mod_code, mod.__dict__)

    results = extract_and_run_docstring_tests(mod, mode="explicit")
    assert results["total"] == 2
    assert results["passed"] == 2
    assert results["failed"] == 0


def test_extract_and_run_docstring_tests_per_symbol_isolation():
    mod = types.ModuleType("test_symbol_isolation_mod")
    mod_code = textwrap.dedent('''\
        def func_one():
            """
            [source,python,shared]
            ----
            shared_var = "from_func_one"
            ----
            """
            pass

        def func_two():
            """
            [source,python,shared]
            ----
            assert 'shared_var' not in globals()
            ----
            """
            pass
    ''')
    exec(mod_code, mod.__dict__)

    results = extract_and_run_docstring_tests(mod, mode="explicit")
    assert results["passed"] == 2
    assert results["failed"] == 0


def test_extract_and_run_docstring_tests_from_py_file(tmp_path):
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        textwrap.dedent('''\
        def double(n):
            """
            [source,python,test]
            ----
            assert double(4) == 8
            ----
            """
            return n * 2
    '''),
        encoding="utf-8",
    )

    results = extract_and_run_docstring_tests(py_file, mode="explicit")
    assert results["total"] == 1
    assert results["passed"] == 1


def test_extract_and_run_docstring_tests_failure_raises(tmp_path):
    py_file = tmp_path / "fail_sample.py"
    py_file.write_text(
        textwrap.dedent('''\
        def broken():
            """
            [source,python,test]
            ----
            assert 1 == 2
            ----
            """
            pass
    '''),
        encoding="utf-8",
    )

    with pytest.raises(AsciiDocTestFailure):
        extract_and_run_docstring_tests(py_file, mode="explicit")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_docstring_extraction.py -v`
Expected: FAIL with `ImportError: cannot import name 'extract_and_run_docstring_tests'`

- [ ] **Step 3: Write minimal implementation**

Create `asciidoctest/docstring_extractor.py`:
```python
import importlib.util
import inspect
import os
import pathlib
import sys
import types
from typing import Any

from asciidoctest.parser import extract_docstring_tests, find_docstrings_in_py_file
from asciidoctest.runner import run_test_blocks


def extract_and_run_docstring_tests(
    source_path_or_module: str | pathlib.Path | types.ModuleType,
    mode: str = "explicit",
) -> dict[str, Any]:
    """
    Extracts and executes AsciiDoc doctests directly from Python source files,
    directories, or loaded module objects with per-symbol scope isolation.

    Returns a summary dictionary: {'total': int, 'passed': int, 'failed': int}.
    Raises AsciiDocTestFailure upon the first test block failure encountered.
    """
    stats = {"total": 0, "passed": 0, "failed": 0}

    if isinstance(source_path_or_module, types.ModuleType):
        _run_tests_on_module(source_path_or_module, mode=mode, stats=stats)
        return stats

    if isinstance(source_path_or_module, str) and not os.path.exists(
        source_path_or_module
    ):
        if source_path_or_module in sys.modules:
            mod = sys.modules[source_path_or_module]
        else:
            mod = __import__(source_path_or_module, globals(), locals(), ["*"])
        _run_tests_on_module(mod, mode=mode, stats=stats)
        return stats

    path = pathlib.Path(source_path_or_module).resolve()
    if path.is_file() and path.suffix == ".py":
        _run_tests_on_py_file(path, mode=mode, stats=stats)
    elif path.is_dir():
        for py_file in sorted(path.rglob("*.py")):
            _run_tests_on_py_file(py_file, mode=mode, stats=stats)
    else:
        raise ValueError(f"Invalid source path or module: {source_path_or_module}")

    return stats


def _run_tests_on_py_file(path: pathlib.Path, mode: str, stats: dict[str, Any]) -> None:
    docstrings = find_docstrings_in_py_file(path)
    if not docstrings:
        return

    module_name = path.stem
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return

    # Add parent directory to sys.path to resolve relative imports safely
    parent_dir = str(path.parent)
    sys.path.insert(0, parent_dir)
    try:
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        raise RuntimeError(f"Error executing module {module_name}: {e}") from e
    finally:
        if sys.path and sys.path[0] == parent_dir:
            sys.path.pop(0)

    for name, lineno, docstring in docstrings:
        tests = extract_docstring_tests(docstring, mode=mode)
        if tests:
            stats["total"] += 1
            globals_copy = dict(module.__dict__)
            run_test_blocks(tests, globals_copy)
            stats["passed"] += 1


def _run_tests_on_module(
    mod: types.ModuleType, mode: str, stats: dict[str, Any]
) -> None:
    discovered = set()

    def process_object(name: str, obj: Any):
        if id(obj) in discovered:
            return
        discovered.add(id(obj))

        docstring = inspect.getdoc(obj)
        if docstring:
            try:
                tests = extract_docstring_tests(docstring, mode=mode)
                if tests:
                    stats["total"] += 1
                    globals_copy = dict(mod.__dict__)
                    run_test_blocks(tests, globals_copy)
                    stats["passed"] += 1
            except Exception:
                raise

    process_object(mod.__name__, mod)

    for attr_name, member in inspect.getmembers(mod):
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
```

In `asciidoctest/__init__.py`:
```python
from asciidoctest.docstring_extractor import extract_and_run_docstring_tests
from asciidoctest.unittest_integration import DocFileSuite, DocTestSuite

__all__ = ["DocFileSuite", "DocTestSuite", "extract_and_run_docstring_tests"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_docstring_extraction.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite and commit**

Run: `pytest`
Expected: All tests pass

Commit:
```bash
git add asciidoctest/docstring_extractor.py asciidoctest/__init__.py tests/test_docstring_extraction.py
git commit -m "feat: add direct python source and docstring doctest extraction (#3)"
```

---

### Task 6: Documentation & Version Updates

**Files:**
- Modify: `README.adoc`
- Modify: `CHANGELOG.adoc`
- Modify: `docs/developer-handbook.adoc`

**Interfaces:**
- Document new features and syntax: section scoping, named context `[source,python,shared="context_name"]`, reset marker `[source,python,reset]`, and `extract_and_run_docstring_tests`.

- [ ] **Step 1: Update README.adoc and developer handbook**

Document the new scoping capabilities and `extract_and_run_docstring_tests` function with examples.

- [ ] **Step 2: Update CHANGELOG.adoc**

Add release notes for Issues #1, #2, and #3.

- [ ] **Step 3: Run full pytest suite including README.adoc doctests**

Run: `pytest`
Expected: All tests pass including `README.adoc` doctests.

- [ ] **Step 4: Commit**

```bash
git add README.adoc CHANGELOG.adoc docs/developer-handbook.adoc
git commit -m "docs: document section scoping, named contexts, reset markers, and direct extraction"
```
