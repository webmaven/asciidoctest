import textwrap
import types

import pytest

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

            def method_b(self):
                """
                [source,python,test]
                ----
                m = MyClass(10)
                assert m.method_b() == 20
                ----
                """
                return self.val * 2
    ''')
    exec(mod_code, mod.__dict__)

    results = extract_and_run_docstring_tests(mod, mode="explicit")
    assert results["total"] == 3
    assert results["passed"] == 3
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


def test_extract_and_run_docstring_tests_from_directory(tmp_path):
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    (pkg_dir / "mod_a.py").write_text(
        textwrap.dedent('''\
        def foo():
            """
            [source,python,test]
            ----
            assert foo() == 1
            ----
            """
            return 1
    '''),
        encoding="utf-8",
    )
    (pkg_dir / "mod_b.py").write_text(
        textwrap.dedent('''\
        def bar():
            """
            [source,python,test]
            ----
            assert bar() == 2
            ----
            """
            return 2
    '''),
        encoding="utf-8",
    )

    results = extract_and_run_docstring_tests(pkg_dir, mode="explicit")
    assert results["total"] == 2
    assert results["passed"] == 2


def test_extract_and_run_docstring_tests_from_module_name_string():
    import sys

    mod_name = "test_custom_named_mod"
    mod = types.ModuleType(mod_name)
    mod_code = textwrap.dedent('''\
        def greeting(name):
            """
            [source,python,test]
            ----
            assert greeting("World") == "Hello, World"
            ----
            """
            return f"Hello, {name}"
    ''')
    exec(mod_code, mod.__dict__)
    sys.modules[mod_name] = mod
    try:
        results = extract_and_run_docstring_tests(mod_name, mode="explicit")
        assert results["total"] == 1
        assert results["passed"] == 1
    finally:
        sys.modules.pop(mod_name, None)


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

    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(py_file, mode="explicit")
    msg = str(exc_info.value)
    assert str(py_file.resolve()) in msg or str(py_file) in msg
    assert "broken" in msg


def test_extract_and_run_docstring_tests_module_function_failure_context():
    mod = types.ModuleType("test_mod_func_fail")
    mod_code = textwrap.dedent('''\
        def failing_routine():
            """
            [source,python,test]
            ----
            assert False
            ----
            """
            pass
    ''')
    exec(mod_code, mod.__dict__)

    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(mod, mode="explicit")
    msg = str(exc_info.value)
    assert "[test_mod_func_fail.failing_routine]" in msg


def test_extract_and_run_docstring_tests_class_method_failure_context():
    mod = types.ModuleType("test_mod_method_fail")
    mod_code = textwrap.dedent('''\
        class Calculator:
            def bad_method(self):
                """
                [source,python,test]
                ----
                assert 2 + 2 == 5
                ----
                """
                pass
    ''')
    exec(mod_code, mod.__dict__)

    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(mod, mode="explicit")
    msg = str(exc_info.value)
    assert "[test_mod_method_fail.Calculator.bad_method]" in msg


def test_extract_and_run_docstring_tests_class_docstring_failure_context():
    mod = types.ModuleType("test_mod_class_fail")
    mod_code = textwrap.dedent('''\
        class BrokenService:
            """
            [source,python,test]
            ----
            assert 1 == 0
            ----
            """
            pass
    ''')
    exec(mod_code, mod.__dict__)

    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(mod, mode="explicit")
    msg = str(exc_info.value)
    assert "[test_mod_class_fail.BrokenService]" in msg


def test_extract_and_run_docstring_tests_invalid_input():
    with pytest.raises(ValueError):
        extract_and_run_docstring_tests(12345)
