import importlib.util
import inspect
import os
import pathlib
import sys
import types
from typing import Any

from asciidoctest.parser import extract_docstring_tests, find_docstrings_in_py_file
from asciidoctest.runner import AsciiDocTestFailure, run_test_blocks


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

    if isinstance(source_path_or_module, (str, pathlib.Path)):
        path = pathlib.Path(source_path_or_module).resolve()
        if path.is_file() and path.suffix == ".py":
            _run_tests_on_py_file(path, mode=mode, stats=stats)
        elif path.is_dir():
            for py_file in sorted(path.rglob("*.py")):
                _run_tests_on_py_file(py_file, mode=mode, stats=stats)
        else:
            raise ValueError(f"Invalid source path or module: {source_path_or_module}")
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

    for name, _lineno, docstring in docstrings:
        tests = extract_docstring_tests(docstring, mode=mode)
        if tests:
            stats["total"] += 1
            globals_copy = dict(module.__dict__)
            try:
                run_test_blocks(tests, globals_copy)
            except AsciiDocTestFailure as e:
                raise AsciiDocTestFailure(f"[{path}:{name}] {e}") from None
            stats["passed"] += 1


def _run_tests_on_module(
    mod: types.ModuleType, mode: str, stats: dict[str, Any]
) -> None:
    discovered = set()

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
                except AsciiDocTestFailure as e:
                    raise AsciiDocTestFailure(f"[{name}] {e}") from None
                stats["passed"] += 1

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
