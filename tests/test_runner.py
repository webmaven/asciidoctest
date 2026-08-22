import textwrap

import pytest

from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import AsciiDocTestFailure, run_test_blocks


class MockBlock:
    def __init__(self, content, is_interactive=False, line_number=1, attributes=None):
        self.content = content
        self.is_interactive = is_interactive
        self.line_number = line_number
        self.attributes = attributes or {}


# 1. Test Parsing/Extraction Modes & Eager Mode Bypass
def test_parse_explicit_mode():
    content = textwrap.dedent("""\
        = Sample Document
        
        This block should be skipped:
        [source,python]
        ----
        x = 1
        ----
        
        This block should be run:
        [source,python,test]
        ----
        y = 2
        ----
        
        This block should also be run:
        [source,python,shared]
        ----
        z = 3
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 2
    assert "y = 2" in blocks[0].content
    assert "z = 3" in blocks[1].content


def test_parse_explicit_mode_no_markers_returns_empty():
    content = textwrap.dedent("""\
        [source,python]
        ----
        x = 1
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit")
    assert blocks == []


def test_parse_eager_mode_active():
    content = textwrap.dedent("""\
        = Sample Document
        
        This block has no test marker:
        [source,python]
        ----
        x = 1
        ----
        
        This block also has no test marker:
        [source,python]
        ----
        y = 2
        ----
        """)
    # Since there are NO explicit markers anywhere, eager mode extracts all blocks
    blocks = parse_adoc_tests(content, mode="eager")
    assert len(blocks) == 2
    assert "x = 1" in blocks[0].content
    assert "y = 2" in blocks[1].content


def test_parse_eager_mode_disabled_by_explicit_markers():
    content = textwrap.dedent("""\
        = Sample Document
        
        This block has no test marker and should be skipped because there is an explicit block elsewhere:
        [source,python]
        ----
        x = 1
        ----
        
        This block has an explicit test marker:
        [source,python,test]
        ----
        y = 2
        ----
        """)
    # Since there is an explicit marker ("test"), eager mode falls back to explicit and skips the first block
    blocks = parse_adoc_tests(content, mode="eager")
    assert len(blocks) == 1
    assert "y = 2" in blocks[0].content


# 2. Test execution of the four semantic cases: Case A, B, C/D
def test_case_c_test_only_is_isolated_and_ephemeral():
    # 'test' blocks run in complete isolation ({})
    blocks = [
        MockBlock("a = 100", is_interactive=False, attributes={"test": "true"}),
        # Since the first block ran in complete isolation, 'a' is not defined here
        MockBlock(
            "assert 'a' not in globals()",
            is_interactive=False,
            attributes={"test": "true"},
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert shared_globals == {}


def test_case_b_shared_only_is_read_write_and_persistent():
    # 'shared' blocks run in persistent, read-write shared globals
    blocks = [
        MockBlock("a = 200", is_interactive=False, attributes={"shared": "true"}),
        MockBlock("b = a + 50", is_interactive=False, attributes={"shared": "true"}),
        MockBlock(">>> b\n250\n", is_interactive=True, attributes={"shared": "true"}),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert shared_globals.get("a") == 200
    assert shared_globals.get("b") == 250


def test_case_a_shared_and_test_is_ephemeral_copy():
    # 'shared, test' blocks get an ephemeral copy of the state which is discarded afterwards
    blocks = [
        # Setup preceding state
        MockBlock("a = 500", is_interactive=False, attributes={"shared": "true"}),
        # This block reads 'a' but its mutations are discarded
        MockBlock(
            "assert a == 500\nb = a + 100\n",
            is_interactive=False,
            attributes={"shared": "true", "test": "true"},
        ),
        # Confirm that 'b' was NOT written back to shared_globals
        MockBlock(
            "assert 'b' not in globals()",
            is_interactive=False,
            attributes={"shared": "true"},
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert shared_globals.get("a") == 500
    assert "b" not in shared_globals


def test_interactive_failure_reporting():
    blocks = [
        MockBlock(
            ">>> 1 + 1\n5\n",
            is_interactive=True,
            line_number=10,
            attributes={"test": "true"},
        )
    ]
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        run_test_blocks(blocks, {})
    assert "Expected: 5" in str(exc_info.value) or "Expected:\n    5" in str(
        exc_info.value
    )
    assert "line 10" in str(exc_info.value)


def test_non_interactive_failure_reporting():
    blocks = [
        MockBlock(
            "x = 10\nassert x == 20\n",
            is_interactive=False,
            line_number=5,
            attributes={"test": "true"},
        )
    ]
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        run_test_blocks(blocks, {})
    assert "AssertionError" in str(exc_info.value)
    assert "line 5" in str(exc_info.value)


def test_parse_invalid_asciidoc_error():
    from unittest.mock import patch

    with patch(
        "asciidoctest.parser.parse_to_ast", side_effect=Exception("Lark Exception")
    ):
        with pytest.raises(ValueError) as exc_info:
            parse_adoc_tests("some adoc content")
    assert "AsciiDoc Parse Error: Lark Exception" in str(exc_info.value)


def test_interactive_unexpected_exception():
    blocks = [
        MockBlock(">>> 1 / 0\n", is_interactive=True, attributes={"test": "true"})
    ]
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        run_test_blocks(blocks, {})
    assert "Unexpected Exception" in str(exc_info.value)
    assert "ZeroDivisionError" in str(exc_info.value)


def test_non_interactive_generic_exception():
    blocks = [
        MockBlock(
            "raise TypeError('custom error')",
            is_interactive=False,
            line_number=10,
            attributes={"test": "true"},
        )
    ]
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        run_test_blocks(blocks, {})
    assert "Exception raised in non-interactive block at line 10" in str(exc_info.value)
    assert "TypeError: custom error" in str(exc_info.value)


def test_safe_visitor_ignores_non_nodes():
    from asciidoctest.parser import SafeTestBlockExtractorVisitor

    visitor = SafeTestBlockExtractorVisitor(
        target_language="python", requires_test_marker=False
    )

    # Passing a raw string or an object without 'name' attribute should be safely ignored and not raise any AttributeError
    res_str = visitor.visit("raw string child element")
    assert res_str is None

    class MockElement:
        pass

    res_obj = visitor.visit(MockElement())
    assert res_obj is None


def test_extract_docstring_tests_unparseable_graceful():
    from unittest.mock import patch

    from asciidoctest.parser import extract_docstring_tests

    with patch("asciidocstring.parse", side_effect=Exception("unparseable")):
        blocks = extract_docstring_tests("some invalid docstring content")
        assert blocks == []
