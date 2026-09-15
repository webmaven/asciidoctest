"""Tests for the public programmatic API: run_adoc_tests, extract_and_run_docstring_tests
with fail_fast support, and TypedDict result types (Issues #4 and #20)."""

import pathlib
import textwrap

import pytest

from asciidoctest import (
    AsciiDocTestFailure,
    TestFailureDetail,
    TestSuiteResult,
    extract_and_run_docstring_tests,
    run_adoc_tests,
)


# ---------------------------------------------------------------------------
# TypedDict structural tests
# ---------------------------------------------------------------------------


def test_test_suite_result_is_typed_dict_with_failures_key(tmp_path: pathlib.Path) -> None:
    """TestSuiteResult always includes a 'failures' list."""
    py = tmp_path / "ok.py"
    py.write_text(
        textwrap.dedent('''\
        def f():
            """
            [source,python,test]
            ----
            assert 1 == 1
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )
    result = extract_and_run_docstring_tests(py)
    assert "failures" in result
    assert isinstance(result["failures"], list)
    assert result["passed"] == 1
    assert result["total"] == 1
    assert result["failed"] == 0


# ---------------------------------------------------------------------------
# extract_and_run_docstring_tests: fail_fast=False collects all failures
# ---------------------------------------------------------------------------


def test_extract_fail_fast_false_collects_all_failures(tmp_path: pathlib.Path) -> None:
    """fail_fast=False must collect every failure, not stop at the first."""
    py_file = tmp_path / "multi_fail.py"
    py_file.write_text(
        textwrap.dedent('''\
        def block_one():
            """
            [source,python,test]
            ----
            assert 1 == 2
            ----
            """
            pass

        def block_two():
            """
            [source,python,test]
            ----
            assert 3 == 4
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )
    result = extract_and_run_docstring_tests(py_file, fail_fast=False)
    assert result["failed"] == 2
    assert result["total"] == 2
    assert result["passed"] == 0
    assert len(result["failures"]) == 2


def test_extract_fail_fast_false_returns_typed_dict(tmp_path: pathlib.Path) -> None:
    """Return value must be a proper TestSuiteResult with all required keys."""
    py_file = tmp_path / "one_fail.py"
    py_file.write_text(
        textwrap.dedent('''\
        def bad():
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
    result = extract_and_run_docstring_tests(py_file, fail_fast=False)
    # All TestSuiteResult keys must be present
    assert "total" in result
    assert "passed" in result
    assert "failed" in result
    assert "failures" in result
    # Each failure entry must have the TestFailureDetail keys
    assert len(result["failures"]) == 1
    detail = result["failures"][0]
    assert "lineno" in detail
    assert "got" in detail
    assert "want" in detail
    assert "name" in detail
    assert "message" in detail


def test_extract_fail_fast_false_partial_pass(tmp_path: pathlib.Path) -> None:
    """fail_fast=False counts passing blocks correctly even alongside failures."""
    py_file = tmp_path / "mixed.py"
    py_file.write_text(
        textwrap.dedent('''\
        def good():
            """
            [source,python,test]
            ----
            assert 1 == 1
            ----
            """
            pass

        def bad():
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
    result = extract_and_run_docstring_tests(py_file, fail_fast=False)
    assert result["total"] == 2
    assert result["passed"] == 1
    assert result["failed"] == 1
    assert len(result["failures"]) == 1


# ---------------------------------------------------------------------------
# extract_and_run_docstring_tests: fail_fast=True raises on first failure
# ---------------------------------------------------------------------------


def test_extract_fail_fast_true_raises_on_first(tmp_path: pathlib.Path) -> None:
    """fail_fast=True (default) must raise AsciiDocTestFailure immediately."""
    py_file = tmp_path / "early_fail.py"
    py_file.write_text(
        textwrap.dedent('''\
        def block_one():
            """
            [source,python,test]
            ----
            assert 1 == 2
            ----
            """
            pass

        def block_two():
            """
            [source,python,test]
            ----
            assert 3 == 4
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )
    with pytest.raises(AsciiDocTestFailure):
        extract_and_run_docstring_tests(py_file, fail_fast=True)


def test_extract_fail_fast_default_is_true(tmp_path: pathlib.Path) -> None:
    """Default fail_fast behaviour must raise, not return a result."""
    py_file = tmp_path / "default_fail.py"
    py_file.write_text(
        textwrap.dedent('''\
        def broken():
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
    with pytest.raises(AsciiDocTestFailure):
        extract_and_run_docstring_tests(py_file)


# ---------------------------------------------------------------------------
# test_docstrings alias
# ---------------------------------------------------------------------------


def test_docstrings_alias_is_same_function() -> None:
    """test_docstrings must be the exact same object as extract_and_run_docstring_tests."""
    from asciidoctest import test_docstrings  # noqa: PLC0415

    assert test_docstrings is extract_and_run_docstring_tests


# ---------------------------------------------------------------------------
# run_adoc_tests: .adoc file
# ---------------------------------------------------------------------------


def test_run_adoc_tests_from_adoc_file(tmp_path: pathlib.Path) -> None:
    adoc = tmp_path / "test.adoc"
    adoc.write_text(
        "= Doc\n\n[source,python,test]\n----\nassert 1 == 1\n----\n",
        encoding="utf-8",
    )
    result = run_adoc_tests(adoc)
    assert result["total"] == 1
    assert result["passed"] == 1
    assert result["failed"] == 0


def test_run_adoc_tests_setup_globs(tmp_path: pathlib.Path) -> None:
    adoc = tmp_path / "globs.adoc"
    adoc.write_text(
        "= Doc\n\n[source,python,test]\n----\nassert ENGINE == 'test'\n----\n",
        encoding="utf-8",
    )
    result = run_adoc_tests(adoc, setup_globs={"ENGINE": "test"})
    assert result["passed"] == 1


def test_run_adoc_tests_from_py_file(tmp_path: pathlib.Path) -> None:
    """run_adoc_tests routes .py files through docstring extraction."""
    py = tmp_path / "mod.py"
    py.write_text(
        textwrap.dedent('''\
        def f():
            """
            [source,python,test]
            ----
            assert 1 == 1
            ----
            """
            pass
        '''),
        encoding="utf-8",
    )
    result = run_adoc_tests(py)
    assert result["passed"] == 1


def test_run_adoc_tests_fail_fast_false_adoc(tmp_path: pathlib.Path) -> None:
    """fail_fast=False on .adoc collects all block failures."""
    adoc = tmp_path / "multi.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = D

        [source,python,test]
        ----
        assert 1 == 2
        ----

        [source,python,test]
        ----
        assert 3 == 4
        ----
        """),
        encoding="utf-8",
    )
    result = run_adoc_tests(adoc, fail_fast=False)
    assert result["failed"] == 2
    assert result["total"] == 2


def test_run_adoc_tests_fail_fast_true_raises(tmp_path: pathlib.Path) -> None:
    """fail_fast=True on .adoc raises AsciiDocTestFailure immediately."""
    adoc = tmp_path / "fail.adoc"
    adoc.write_text(
        "= D\n\n[source,python,test]\n----\nassert 1 == 2\n----\n",
        encoding="utf-8",
    )
    with pytest.raises(AsciiDocTestFailure):
        run_adoc_tests(adoc, fail_fast=True)


def test_run_adoc_tests_returns_typed_dict_keys(tmp_path: pathlib.Path) -> None:
    """run_adoc_tests result always contains all four TestSuiteResult keys."""
    adoc = tmp_path / "keys.adoc"
    adoc.write_text(
        "= D\n\n[source,python,test]\n----\nassert True\n----\n",
        encoding="utf-8",
    )
    result = run_adoc_tests(adoc)
    assert "total" in result
    assert "passed" in result
    assert "failed" in result
    assert "failures" in result


def test_run_adoc_tests_from_adoc_string_content(tmp_path: pathlib.Path) -> None:
    """run_adoc_tests treats a non-existent path as raw AsciiDoc content."""
    raw = "= D\n\n[source,python,test]\n----\nassert 2 + 2 == 4\n----\n"
    result = run_adoc_tests(raw)
    assert result["passed"] == 1


# ---------------------------------------------------------------------------
# __init__.py exports
# ---------------------------------------------------------------------------


def test_init_exports_run_adoc_tests() -> None:
    import asciidoctest

    assert hasattr(asciidoctest, "run_adoc_tests")
    assert hasattr(asciidoctest, "test_docstrings")
    assert hasattr(asciidoctest, "TestSuiteResult")
    assert hasattr(asciidoctest, "TestFailureDetail")
    for name in [
        "AsciiDocTestFailure",
        "DocFileSuite",
        "DocTestSuite",
        "run_adoc_tests",
        "extract_and_run_docstring_tests",
        "test_docstrings",
        "TestSuiteResult",
        "TestFailureDetail",
    ]:
        assert name in asciidoctest.__all__, f"{name!r} missing from __all__"
