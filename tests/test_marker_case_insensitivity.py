"""Regression tests for issue #9: marker detection must be case-insensitive."""

from asciidoctest.parser import (
    block_has_reset_marker,
    block_has_shared_marker,
    block_has_test_marker,
)

try:
    from tests.test_scoping import MockBlock
except ImportError:
    from test_scoping import MockBlock


def test_uppercase_positional_marker_detected():
    b = MockBlock("pass", attributes={"positional": ["source", "python", "TEST"]})
    assert block_has_test_marker(b) is True


def test_mixedcase_role_detected():
    b = MockBlock("pass", attributes={"role": "custom Reset other"})
    assert block_has_reset_marker(b) is True


def test_uppercase_shared_role_detected():
    b = MockBlock("pass", attributes={"role": "SHARED"})
    assert block_has_shared_marker(b) is True


def test_lowercase_default_still_works():
    b = MockBlock("pass", attributes={"role": "reset"})
    assert block_has_reset_marker(b) is True


def test_partial_word_not_matched():
    b = MockBlock("pass", attributes={"role": "testing"})
    assert block_has_test_marker(b) is False


def test_unmarked_block_still_negative():
    b = MockBlock("pass", attributes={})
    assert block_has_test_marker(b) is False
    assert block_has_shared_marker(b) is False
    assert block_has_reset_marker(b) is False
