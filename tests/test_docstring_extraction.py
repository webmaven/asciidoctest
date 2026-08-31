import pathlib
import sys
import textwrap
import types

import pytest

from asciidoctest import extract_and_run_docstring_tests
from asciidoctest.runner import AsciiDocTestFailure


def test_extract_and_run_docstring_tests_from_module_object():
    mod = types.ModuleType("test_sample_mod")
    mod.__doc__ = textwrap.dedent("""\
        Module docstring with doctests.

        [source,python,test]
        ----
        >>> 10 * 10
        100
        ----
    """)
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

        async def async_func(y):
            """
            [source,python,test]
            ----
            >>> y = 42
            >>> y
            42
            ----
            """
            return y

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

            class NestedClass:
                """
                [source,python,test]
                ----
                >>> 3 + 3
                6
                ----
                """
                def nested_method(self):
                    """
                    [source,python,test]
                    ----
                    >>> 7 + 7
                    14
                    ----
                    """
                    return 14
    ''')
    exec(mod_code, mod.__dict__)

    results = extract_and_run_docstring_tests(mod, mode="explicit")
    assert results["total"] == 7
    assert results["passed"] == 7
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

        class ClsOne:
            """
            [source,python,shared]
            ----
            class_var = "from_cls_one"
            ----
            """
            pass

        class ClsTwo:
            """
            [source,python,shared]
            ----
            assert 'class_var' not in globals()
            ----
            """
            def method(self):
                """
                [source,python,shared]
                ----
                assert 'class_var' not in globals()
                ----
                """
                pass
    ''')
    exec(mod_code, mod.__dict__)

    results = extract_and_run_docstring_tests(mod, mode="explicit")
    assert results["passed"] == 5
    assert results["failed"] == 0


def test_extract_and_run_docstring_tests_from_py_file(tmp_path: pathlib.Path):
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        textwrap.dedent('''\
        """
        Module docstring.

        [source,python,test]
        ----
        >>> 2 + 2
        4
        ----
        """

        def double(n):
            """
            [source,python,test]
            ----
            assert double(4) == 8
            ----
            """
            return n * 2

        async def async_triple(n):
            """
            [source,python,test]
            ----
            >>> 3 * 3
            9
            ----
            """
            return n * 3

        class Calculator:
            """
            [source,python,test]
            ----
            c = Calculator()
            assert c is not None
            ----
            """
            class Helper:
                def add(self, a, b):
                    """
                    [source,python,test]
                    ----
                    assert Calculator.Helper().add(2, 3) == 5
                    ----
                    """
                    return a + b
    '''),
        encoding="utf-8",
    )

    results = extract_and_run_docstring_tests(py_file, mode="explicit")
    assert results["total"] == 5
    assert results["passed"] == 5
    assert results["failed"] == 0


def test_extract_and_run_docstring_tests_from_directory(tmp_path: pathlib.Path):
    pkg_dir = tmp_path / "mypkg"
    pkg_dir.mkdir()
    sub_dir = pkg_dir / "subdir"
    sub_dir.mkdir()

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
    (sub_dir / "mod_b.py").write_text(
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


def test_extract_and_run_docstring_tests_failure_raises(tmp_path: pathlib.Path):
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


def test_extract_and_run_docstring_tests_file_module_docstring_failure_context(
    tmp_path: pathlib.Path,
):
    py_file = tmp_path / "mod_doc_fail.py"
    py_file.write_text(
        textwrap.dedent('''\
        """
        [source,python,test]
        ----
        assert 1 == 99
        ----
        """
        '''),
        encoding="utf-8",
    )
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(py_file, mode="explicit")
    msg = str(exc_info.value)
    assert "<module>" in msg


def test_extract_and_run_docstring_tests_file_nested_method_failure_context(
    tmp_path: pathlib.Path,
):
    py_file = tmp_path / "nested_fail.py"
    py_file.write_text(
        textwrap.dedent('''\
        class Outer:
            class Inner:
                def failing_method(self):
                    """
                    [source,python,test]
                    ----
                    assert False
                    ----
                    """
                    pass
        '''),
        encoding="utf-8",
    )
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(py_file, mode="explicit")
    msg = str(exc_info.value)
    assert "Outer.Inner.failing_method" in msg


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


def test_extract_and_run_docstring_tests_module_class_method_failure_context():
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


def test_extract_and_run_docstring_tests_module_nested_class_method_failure_context():
    mod = types.ModuleType("test_mod_nested_fail")
    mod_code = textwrap.dedent('''\
        class Outer:
            class Inner:
                def bad_nested_method(self):
                    """
                    [source,python,test]
                    ----
                    assert 1 + 1 == 3
                    ----
                    """
                    pass
    ''')
    exec(mod_code, mod.__dict__)

    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(mod, mode="explicit")
    msg = str(exc_info.value)
    assert "[test_mod_nested_fail.Outer.Inner.bad_nested_method]" in msg


def test_extract_and_run_docstring_tests_module_docstring_failure_context():
    mod = types.ModuleType("test_mod_module_fail")
    mod.__doc__ = textwrap.dedent("""\
        [source,python,test]
        ----
        assert "a" == "b"
        ----
    """)

    with pytest.raises(AsciiDocTestFailure) as exc_info:
        extract_and_run_docstring_tests(mod, mode="explicit")
    msg = str(exc_info.value)
    assert "[test_mod_module_fail]" in msg


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
        extract_and_run_docstring_tests(12345)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        extract_and_run_docstring_tests(None)  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        extract_and_run_docstring_tests("non_existent_module_xyz_123_456")


def test_extract_and_run_docstring_tests_non_python_file(tmp_path: pathlib.Path):
    txt_file = tmp_path / "notes.txt"
    txt_file.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_and_run_docstring_tests(txt_file)


def test_extract_and_run_docstring_tests_empty_docstrings(tmp_path: pathlib.Path):
    py_file = tmp_path / "empty.py"
    py_file.write_text(
        textwrap.dedent('''\
        """
        """
        def no_tests():
            """Just regular documentation."""
            pass

        class EmptyClass:
            pass
    '''),
        encoding="utf-8",
    )
    results = extract_and_run_docstring_tests(py_file, mode="explicit")
    assert results == {"total": 0, "passed": 0, "failed": 0}


def test_extract_and_run_docstring_tests_syntax_error_file(tmp_path: pathlib.Path):
    py_file = tmp_path / "bad_syntax.py"
    py_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")
    results = extract_and_run_docstring_tests(py_file, mode="explicit")
    assert results == {"total": 0, "passed": 0, "failed": 0}


def test_extract_and_run_docstring_tests_eager_mode(tmp_path: pathlib.Path):
    py_file = tmp_path / "eager_mod.py"
    py_file.write_text(
        textwrap.dedent('''\
        def eager_func():
            """
            [source,python]
            ----
            assert 10 > 5
            ----
            """
            pass
    '''),
        encoding="utf-8",
    )
    # Default explicit mode ignores [source,python] without 'test'
    res_explicit = extract_and_run_docstring_tests(py_file, mode="explicit")
    assert res_explicit["total"] == 0

    # Eager mode extracts and runs it
    res_eager = extract_and_run_docstring_tests(py_file, mode="eager")
    assert res_eager["total"] == 1
    assert res_eager["passed"] == 1


def test_extract_and_run_docstring_tests_module_runtime_error(tmp_path: pathlib.Path):
    py_file = tmp_path / "runtime_err.py"
    py_file.write_text(
        textwrap.dedent('''\
        def func():
            """
            [source,python,test]
            ----
            assert True
            ----
            """
            pass

        raise RuntimeError("Crash on import")
    '''),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError) as exc_info:
        extract_and_run_docstring_tests(py_file, mode="explicit")
    assert "Crash on import" in str(exc_info.value)
