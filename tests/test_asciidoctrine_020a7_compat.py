import textwrap

from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import run_test_blocks


def test_list_item_with_hanging_continuation_and_doctest():
    """Verify that contiguous indented lines in list items do not break listing block doctests."""
    content = textwrap.dedent("""\
        = List Continuation Document

        * First list item principal text
          continuation line immediately following item
        +
        [source,python,test]
        ----
        val = 42
        assert val == 42
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 1
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_code_block_with_escaped_delimiters_and_macros():
    """Verify that backslash-escaped delimiters inside docs or code blocks are tolerated without AST syntax breakage."""
    content = textwrap.dedent("""\
        = Escaped Delimiters Document

        Here is an escaped delimiter \\*not_bold* and \\`not_code\\`.

        [source,python,test]
        ----
        message = r"Delimiters like \\*bold* and \\xref:target[] are safe"
        assert "safe" in message
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 1
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_dot_ordered_list_before_doctest_block():
    """Verify dot-ordered list items preceding source blocks do not collide with block title matching."""
    content = textwrap.dedent("""\
        = Dot Ordered List Document

        . First ordered step
        . Second ordered step

        [source,python,test]
        ----
        step_count = 2
        assert step_count == 2
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 1
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
