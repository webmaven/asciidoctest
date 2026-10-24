from asciidoctest.docstring_extractor import (
    TestFailureDetail,
    TestSuiteResult,
    DocstringTestSummary,
    extract_and_run_docstring_tests,
    run_adoc_tests,
)
from asciidoctest.runner import AsciiDocTestFailure
from asciidoctest.unittest_integration import DocFileSuite, DocTestSuite

test_docstrings = extract_and_run_docstring_tests

__all__ = [
    "AsciiDocTestFailure",
    "DocFileSuite",
    "DocTestSuite",
    "run_adoc_tests",
    "extract_and_run_docstring_tests",
    "test_docstrings",
    "TestSuiteResult",
    "DocstringTestSummary",
    "TestFailureDetail",
]
