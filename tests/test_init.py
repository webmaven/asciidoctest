"""Tests for top-level package exports and __init__.py definitions in asciidoctest."""

import inspect

import asciidoctest
from asciidoctest import (
    AsciiDocTestFailure,
    DocFileSuite,
    DocTestSuite,
    extract_and_run_docstring_tests,
)
from asciidoctest.docstring_extractor import (
    extract_and_run_docstring_tests as _orig_extract_and_run,
)
from asciidoctest.runner import AsciiDocTestFailure as _orig_AsciiDocTestFailure
from asciidoctest.unittest_integration import (
    DocFileSuite as _orig_DocFileSuite,
)
from asciidoctest.unittest_integration import (
    DocTestSuite as _orig_DocTestSuite,
)


def test_all_attribute_contents() -> None:
    """Verify __all__ is defined and contains all expected public symbols."""
    expected_exports = [
        "AsciiDocTestFailure",
        "DocFileSuite",
        "DocTestSuite",
        "extract_and_run_docstring_tests",
    ]
    assert hasattr(asciidoctest, "__all__")
    assert isinstance(asciidoctest.__all__, list)
    assert asciidoctest.__all__ == expected_exports


def test_import_identity() -> None:
    """Verify symbols imported from top-level asciidoctest match originating modules."""
    assert AsciiDocTestFailure is _orig_AsciiDocTestFailure
    assert DocFileSuite is _orig_DocFileSuite
    assert DocTestSuite is _orig_DocTestSuite
    assert extract_and_run_docstring_tests is _orig_extract_and_run


def test_module_attributes_accessible() -> None:
    """Verify all items in __all__ are accessible via getattr on asciidoctest."""
    for name in asciidoctest.__all__:
        assert hasattr(asciidoctest, name)
        obj = getattr(asciidoctest, name)
        assert obj is not None


def test_exported_callables_and_types() -> None:
    """Verify types and callable signatures of exported symbols."""
    assert inspect.isclass(asciidoctest.AsciiDocTestFailure)
    assert issubclass(asciidoctest.AsciiDocTestFailure, Exception)

    assert callable(asciidoctest.DocFileSuite)
    assert callable(asciidoctest.DocTestSuite)
    assert callable(asciidoctest.extract_and_run_docstring_tests)
    assert inspect.isfunction(asciidoctest.extract_and_run_docstring_tests)
