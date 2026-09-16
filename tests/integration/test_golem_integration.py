"""Golem-style integration tests exercising the programmatic API end-to-end.

These tests verify that ``run_adoc_tests`` and
``extract_and_run_docstring_tests`` work correctly in integration scenarios
typical of Golem-style docstring testing workflows: shared contexts,
fail-fast behaviour, module collision isolation, and graceful handling of
missing ``include::`` directives.

Issue #21.
"""

from __future__ import annotations

import pathlib
import textwrap

import pytest

from asciidoctest import (
    AsciiDocTestFailure,
    run_adoc_tests,
)

# ---------------------------------------------------------------------------
# Test 1: Module docstrings via the programmatic API
# ---------------------------------------------------------------------------


def test_module_docstrings_via_programmatic_api(tmp_path: pathlib.Path) -> None:
    """A .py file with AsciiDoc docstring tests passes via ``run_adoc_tests``."""
    py_file = tmp_path / "calculator.py"
    py_file.write_text(
        textwrap.dedent('''\
        def add(a: int, b: int) -> int:
            """
            Add two numbers.

            [source,python,test]
            ----
            assert add(1, 1) == 2
            ----
            """
            return a + b

        def multiply(x: int, y: int) -> int:
            """
            Multiply two numbers.

            [source,python,test]
            ----
            assert multiply(3, 4) == 12
            ----
            """
            return x * y
        '''),
        encoding="utf-8",
    )
    result = run_adoc_tests(py_file)
    assert result["total"] == 2, f"Expected 2 test blocks, got {result['total']}"
    assert result["passed"] == result["total"]
    assert result["failed"] == 0


# ---------------------------------------------------------------------------
# Test 2: setup_globs injected into AsciiDoc test blocks
# ---------------------------------------------------------------------------


def test_setup_globs_injected_into_adoc(tmp_path: pathlib.Path) -> None:
    """``setup_globs`` values are visible inside every test block."""
    adoc = tmp_path / "engine.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = Engine Config

        [source,python,test]
        ----
        assert ENGINE == "dag"
        ----

        [source,python,test]
        ----
        assert ENGINE.upper() == "DAG"
        ----
        """),
        encoding="utf-8",
    )
    result = run_adoc_tests(adoc, setup_globs={"ENGINE": "dag"})
    assert result["passed"] == 2
    assert result["failed"] == 0


# ---------------------------------------------------------------------------
# Test 3: fail_fast halts at first failure / collects all failures
# ---------------------------------------------------------------------------


def test_fail_fast_halts_at_first_failure(tmp_path: pathlib.Path) -> None:
    """fail_fast=True raises immediately; fail_fast=False collects all."""
    adoc = tmp_path / "two_failures.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = Failures

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

    # fail_fast=True: raises on the very first failing block
    with pytest.raises(AsciiDocTestFailure):
        run_adoc_tests(adoc, fail_fast=True)

    # fail_fast=False: collects both failures without raising
    result = run_adoc_tests(adoc, fail_fast=False)
    assert result["failed"] == 2
    assert result["total"] == 2
    assert result["passed"] == 0
    assert len(result["failures"]) == 2


# ---------------------------------------------------------------------------
# Test 4: Same-stem file collision is isolated
# ---------------------------------------------------------------------------


def test_same_stem_collision_isolated(tmp_path: pathlib.Path) -> None:
    """Two dirs each with an ``__init__.py`` having different docstring tests
    both pass — module names don't collide (Issue #8 regression guard)."""
    pkg_a = tmp_path / "pkg_a"
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text(
        textwrap.dedent('''\
        """
        [source,python,test]
        ----
        assert 1 + 1 == 2
        ----
        """
        '''),
        encoding="utf-8",
    )

    pkg_b = tmp_path / "pkg_b"
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text(
        textwrap.dedent('''\
        """
        [source,python,test]
        ----
        assert 2 + 2 == 4
        ----
        """
        '''),
        encoding="utf-8",
    )

    result_a = run_adoc_tests(pkg_a / "__init__.py")
    result_b = run_adoc_tests(pkg_b / "__init__.py")

    assert result_a["passed"] == 1, f"pkg_a failed: {result_a}"
    assert result_b["passed"] == 1, f"pkg_b failed: {result_b}"

    # Also exercise the directory mode which walks both
    result_dir = run_adoc_tests(tmp_path)
    assert result_dir["passed"] == 2
    assert result_dir["failed"] == 0


# ---------------------------------------------------------------------------
# Test 5: Line numbers present in failure details
# ---------------------------------------------------------------------------


def test_line_numbers_present_in_failures(tmp_path: pathlib.Path) -> None:
    """Failure messages include line-number context."""
    adoc = tmp_path / "lineno.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = Line Test

        [source,python,test]
        ----
        assert 1 == 2
        ----
        """),
        encoding="utf-8",
    )
    result = run_adoc_tests(adoc, fail_fast=False)
    assert result["failed"] == 1
    assert len(result["failures"]) == 1
    detail = result["failures"][0]
    # The failure message should contain "line" to indicate location context
    assert "line" in detail["message"].lower(), (
        f"Expected 'line' in failure message, got: {detail['message']!r}"
    )


# ---------------------------------------------------------------------------
# Test 6: include:: directives gracefully ignored by default
# ---------------------------------------------------------------------------


def test_include_directives_gracefully_ignored(tmp_path: pathlib.Path) -> None:
    """`include::missing.adoc[]` is silently ignored when
    ``preprocess_directives`` defaults to ``False``."""
    adoc = tmp_path / "with_include.adoc"
    adoc.write_text(
        textwrap.dedent("""\
        = Document with Include

        include::missing.adoc[]

        [source,python,test]
        ----
        x = 42
        assert x == 42
        ----
        """),
        encoding="utf-8",
    )
    # Should not raise — include is passively ignored
    result = run_adoc_tests(adoc)
    assert result["passed"] == 1
    assert result["failed"] == 0
