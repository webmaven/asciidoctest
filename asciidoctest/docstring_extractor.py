import importlib
import importlib.util
import inspect
import os
import pathlib
import sys
import types
from typing import Any, TypedDict

from asciidoctest.parser import extract_docstring_tests, find_docstrings_in_py_file
from asciidoctest.runner import AsciiDocTestFailure, run_test_blocks


class TestFailureDetail(TypedDict):
    """Structured information about a single test block failure."""

    lineno: int
    got: str
    want: str
    name: str
    message: str


class TestSuiteResult(TypedDict):
    """Aggregate result returned by programmatic test runners."""

    total: int
    passed: int
    failed: int
    failures: list[TestFailureDetail]


def extract_and_run_docstring_tests(
    source_path_or_module: str | pathlib.Path | types.ModuleType,
    mode: str = "explicit",
    fail_fast: bool = True,
) -> TestSuiteResult:
    """
    Extracts and executes AsciiDoc doctests directly from Python source files,
    directories, or loaded module objects with per-symbol scope isolation.

    Returns a :class:`TestSuiteResult` with keys: ``total``, ``passed``,
    ``failed``, ``failures``.

    When *fail_fast* is ``True`` (the default), raises
    :exc:`AsciiDocTestFailure` upon the first test block failure.  When
    ``False``, all blocks are run and every failure is collected into
    ``result["failures"]`` without raising.
    """
    stats: TestSuiteResult = {"total": 0, "passed": 0, "failed": 0, "failures": []}

    if isinstance(source_path_or_module, types.ModuleType):
        _run_tests_on_module(
            source_path_or_module, mode=mode, stats=stats, fail_fast=fail_fast
        )
        return stats

    if isinstance(source_path_or_module, str) and not os.path.exists(
        source_path_or_module
    ):
        try:
            if source_path_or_module in sys.modules:
                mod = sys.modules[source_path_or_module]
            else:
                mod = importlib.import_module(source_path_or_module)
            _run_tests_on_module(mod, mode=mode, stats=stats, fail_fast=fail_fast)
            return stats
        except (ImportError, ModuleNotFoundError, ValueError, AttributeError) as e:
            raise ValueError(
                f"Invalid source path or module: {source_path_or_module}"
            ) from e

    if isinstance(source_path_or_module, (str, pathlib.Path)):
        path = pathlib.Path(source_path_or_module).resolve()
        if path.is_file() and path.suffix == ".py":
            _run_tests_on_py_file(path, mode=mode, stats=stats, fail_fast=fail_fast)
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                _run_tests_on_py_file(
                    py_file, mode=mode, stats=stats, fail_fast=fail_fast
                )
        else:
            raise ValueError(f"Invalid source path or module: {source_path_or_module}")
    else:
        raise ValueError(f"Invalid source path or module: {source_path_or_module}")

    return stats


def run_adoc_tests(
    source: str | pathlib.Path | types.ModuleType,
    *,
    setup_globs: dict[str, Any] | None = None,
    mode: str = "explicit",
    fail_fast: bool = False,
) -> TestSuiteResult:
    """
    Programmatic runner for AsciiDoc tests.  Accepts an ``.adoc`` file path,
    a ``.py`` file path, a directory path, a loaded ``ModuleType``, or a raw
    AsciiDoc content string (used when the value does not correspond to an
    existing filesystem path).

    Returns a :class:`TestSuiteResult` without requiring pytest.  Unlike
    :func:`extract_and_run_docstring_tests`, the default for *fail_fast* here
    is ``False`` so that callers get a complete picture of all failures.

    Parameters
    ----------
    source:
        An ``.adoc`` path, ``.py`` path, directory, a loaded module, or a raw
        AsciiDoc string.
    setup_globs:
        Optional mapping of names pre-injected into every test block's globals.
    mode:
        Passed through to the underlying parser (``"explicit"`` or ``"eager"``).
    fail_fast:
        When ``True``, re-raises :exc:`AsciiDocTestFailure` on the first block
        failure.  When ``False`` (the default), all failures are collected.
    """
    stats: TestSuiteResult = {"total": 0, "passed": 0, "failed": 0, "failures": []}
    globs: dict[str, Any] = dict(setup_globs) if setup_globs else {}

    if isinstance(source, types.ModuleType):
        _run_tests_on_module(source, mode=mode, stats=stats, fail_fast=fail_fast)
        return stats

    path = pathlib.Path(source) if not isinstance(source, pathlib.Path) else source

    if path.exists():
        if path.suffix == ".adoc":
            content = path.read_text("utf-8")
            _run_adoc_content(
                content,
                name=str(path),
                globs=globs,
                mode=mode,
                fail_fast=fail_fast,
                stats=stats,
            )
        elif path.suffix == ".py":
            _run_tests_on_py_file(path, mode=mode, stats=stats, fail_fast=fail_fast)
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                _run_tests_on_py_file(
                    py_file, mode=mode, stats=stats, fail_fast=fail_fast
                )
    else:
        # Treat as raw AsciiDoc content string
        _run_adoc_content(
            str(source),
            name="<string>",
            globs=globs,
            mode=mode,
            fail_fast=fail_fast,
            stats=stats,
        )

    return stats


def _run_adoc_content(
    content: str,
    *,
    name: str,
    globs: dict[str, Any],
    mode: str,
    fail_fast: bool,
    stats: TestSuiteResult,
) -> None:
    """Run all test blocks in a raw AsciiDoc string, updating *stats* in place."""
    from asciidoctest.parser import parse_adoc_tests

    blocks = parse_adoc_tests(content, mode=mode)
    for block in blocks:
        stats["total"] += 1
        block_globs = dict(globs)
        try:
            run_test_blocks([block], block_globs)
            stats["passed"] += 1
        except AsciiDocTestFailure as e:
            if fail_fast:
                raise
            stats["failed"] += 1
            detail: TestFailureDetail = {
                "lineno": getattr(block, "line_number", 0),
                "got": "",
                "want": "",
                "name": name,
                "message": str(e),
            }
            stats["failures"].append(detail)


def _run_tests_on_py_file(
    path: pathlib.Path,
    mode: str,
    stats: TestSuiteResult,
    fail_fast: bool = True,
) -> None:
    docstrings = find_docstrings_in_py_file(path)
    if not docstrings:
        return

    # Use a unique, path-derived name to avoid sys.modules collisions between
    # same-named files in different subdirectories (Issue #8).
    module_name = (
        "_asciidoctest_"
        + "_".join(path.with_suffix("").parts)
        .replace("-", "_")
        .replace(".", "_")
    )
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
        sys.modules.pop(module_name, None)
        if sys.path and sys.path[0] == parent_dir:
            sys.path.pop(0)

    for name, _lineno, docstring in docstrings:
        tests = extract_docstring_tests(docstring, mode=mode)
        if tests:
            stats["total"] += 1
            globals_copy = dict(module.__dict__)
            try:
                run_test_blocks(tests, globals_copy)
                stats["passed"] += 1
            except AsciiDocTestFailure as e:
                full_name = f"[{path}:{name}]"
                if fail_fast:
                    raise AsciiDocTestFailure(f"{full_name} {e}") from None
                stats["failed"] += 1
                detail: TestFailureDetail = {
                    "lineno": 0,
                    "got": "",
                    "want": "",
                    "name": full_name,
                    "message": str(e),
                }
                stats["failures"].append(detail)


def _run_tests_on_module(
    mod: types.ModuleType,
    mode: str,
    stats: TestSuiteResult,
    fail_fast: bool = True,
) -> None:
    discovered: set[int] = set()

    def process_object(name: str, obj: Any) -> None:
        if id(obj) in discovered:
            return
        discovered.add(id(obj))

        docstring = inspect.getdoc(obj)
        if docstring:
            tests = extract_docstring_tests(docstring, mode=mode)
            if tests:
                stats["total"] += 1
                globals_copy = dict(mod.__dict__)
                try:
                    run_test_blocks(tests, globals_copy)
                    stats["passed"] += 1
                except AsciiDocTestFailure as e:
                    label = f"[{name}]"
                    if fail_fast:
                        raise AsciiDocTestFailure(f"{label} {e}") from None
                    stats["failed"] += 1
                    detail: TestFailureDetail = {
                        "lineno": 0,
                        "got": "",
                        "want": "",
                        "name": label,
                        "message": str(e),
                    }
                    stats["failures"].append(detail)

    process_object(mod.__name__, mod)

    def walk_class(cls: type, prefix: str) -> None:
        process_object(prefix, cls)
        for sub_name, sub_member in inspect.getmembers(cls):
            if inspect.isclass(sub_member):
                if getattr(sub_member, "__module__", None) == mod.__name__:
                    walk_class(sub_member, f"{prefix}.{sub_name}")
            elif inspect.isroutine(sub_member):
                process_object(f"{prefix}.{sub_name}", sub_member)

    for attr_name, member in inspect.getmembers(mod):
        if hasattr(member, "__module__") and member.__module__ != mod.__name__:
            continue
        if inspect.isclass(member):
            walk_class(member, f"{mod.__name__}.{attr_name}")
        elif inspect.isroutine(member):
            process_object(f"{mod.__name__}.{attr_name}", member)
