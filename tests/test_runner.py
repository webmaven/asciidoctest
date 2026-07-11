import pytest
import textwrap
from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import run_test_blocks, AsciiDocTestFailure

# 1. Test Parsing/Extraction Modes
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
        [.test]
        [source,python]
        ----
        z = 3
        ----
        """)
    # By default, parse_adoc_tests should be in explicit mode (mode="explicit")
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 2
    assert "y = 2" in blocks[0].content
    assert "z = 3" in blocks[1].content


def test_parse_eager_mode():
    content = textwrap.dedent("""\
        = Sample Document
        
        This block has no test marker:
        [source,python]
        ----
        x = 1
        ----
        
        This block has test marker:
        [source,python,test]
        ----
        y = 2
        ----
        """)
    # In eager mode, all python blocks should be parsed
    blocks = parse_adoc_tests(content, mode="eager")
    assert len(blocks) == 2
    assert "x = 1" in blocks[0].content
    assert "y = 2" in blocks[1].content


# 2. Test Interactive Block Execution
def test_execute_interactive_success():
    content = textwrap.dedent("""\
        >>> 1 + 1
        2
        >>> print("hello")
        hello
        """)
    # In our parser, blocks have attributes (like language, is_interactive, etc.)
    # For unit testing the runner, we can mock or construct simple block objects.
    class MockBlock:
        def __init__(self, content, is_interactive=True, line_number=1):
            self.content = content
            self.is_interactive = is_interactive
            self.line_number = line_number

    blocks = [MockBlock(content, is_interactive=True)]
    # run_test_blocks should execute the blocks and return success without raising exceptions
    globals_dict = {}
    run_test_blocks(blocks, globals_dict)
    assert "1 + 1" not in globals_dict  # interactive sessions usually don't bleed local vars unless stored, or do they?
    # Actually, in doctest, interactive executions run in a local scope/globals dict.
    # Let's verify that a global defined in an interactive block is stored.
    blocks_state = [
        MockBlock(">>> x = 42\n", is_interactive=True),
        MockBlock(">>> x\n42\n", is_interactive=True),
    ]
    shared_globals = {}
    run_test_blocks(blocks_state, shared_globals)
    assert shared_globals.get("x") == 42


def test_execute_interactive_failure():
    class MockBlock:
        def __init__(self, content, is_interactive=True, line_number=10):
            self.content = content
            self.is_interactive = is_interactive
            self.line_number = line_number

    blocks = [MockBlock(">>> 1 + 1\n5\n", is_interactive=True)]
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        run_test_blocks(blocks, {})
    assert "Expected: 5" in str(exc_info.value) or "Expected:\n    5" in str(exc_info.value)
    assert "line 10" in str(exc_info.value)


# 3. Test Non-Interactive Block Execution (Script Mode)
def test_execute_non_interactive_success():
    class MockBlock:
        def __init__(self, content, is_interactive=False, line_number=1):
            self.content = content
            self.is_interactive = is_interactive
            self.line_number = line_number

    blocks = [
        MockBlock("y = [1, 2, 3]\nassert len(y) == 3\n", is_interactive=False)
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert shared_globals.get("y") == [1, 2, 3]


def test_execute_non_interactive_failure():
    class MockBlock:
        def __init__(self, content, is_interactive=False, line_number=5):
            self.content = content
            self.is_interactive = is_interactive
            self.line_number = line_number

    blocks = [MockBlock("x = 10\nassert x == 20\n", is_interactive=False)]
    with pytest.raises(AsciiDocTestFailure) as exc_info:
        run_test_blocks(blocks, {})
    assert "AssertionError" in str(exc_info.value)
    assert "line 5" in str(exc_info.value)


# 4. Test State Sharing & Namespace Isolation
def test_state_sharing_across_blocks():
    class MockBlock:
        def __init__(self, content, is_interactive=False, line_number=1):
            self.content = content
            self.is_interactive = is_interactive
            self.line_number = line_number

    blocks = [
        MockBlock("a = 100", is_interactive=False),
        MockBlock("b = a + 50", is_interactive=False),
        MockBlock(">>> b\n150", is_interactive=True),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert shared_globals.get("a") == 100
    assert shared_globals.get("b") == 150
