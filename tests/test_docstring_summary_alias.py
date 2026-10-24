"""Regression tests for issue #14: DocstringTestSummary TypedDict alias."""

import asciidoctest
from asciidoctest import DocstringTestSummary, TestSuiteResult, extract_and_run_docstring_tests


def test_alias_identity():
    assert DocstringTestSummary is TestSuiteResult


def test_exported_in_all():
    assert "DocstringTestSummary" in asciidoctest.__all__


def test_return_type_annotation():
    hints = __import__("typing").get_type_hints(extract_and_run_docstring_tests)
    assert hints["return"] is TestSuiteResult
