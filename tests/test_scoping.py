import textwrap

from asciidoctest.parser import (
    block_get_shared_context,
    block_has_reset_marker,
    parse_adoc_tests,
)
from asciidoctest.runner import run_test_blocks


class MockBlock:
    def __init__(self, content, is_interactive=False, line_number=1, attributes=None):
        self.content = content
        self.is_interactive = is_interactive
        self.line_number = line_number
        self.attributes = attributes or {}


def test_explicit_reset_marker():
    blocks = [
        MockBlock("a = 10", attributes={"shared": "true"}),
        MockBlock("assert a == 10", attributes={"shared": "true"}),
        MockBlock("b = 20", attributes={"reset": "true", "shared": "true"}),
        MockBlock(
            "assert 'a' not in globals() and b == 20", attributes={"shared": "true"}
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert "a" not in shared_globals
    assert shared_globals.get("b") == 20


def test_named_context_scopes():
    blocks = [
        MockBlock("x = 100", attributes={"shared": "ctx_a"}),
        MockBlock("y = 200", attributes={"shared": "ctx_b"}),
        MockBlock(
            "assert x == 100 and 'y' not in globals()", attributes={"shared": "ctx_a"}
        ),
        MockBlock(
            "assert y == 200 and 'x' not in globals()", attributes={"shared": "ctx_b"}
        ),
        MockBlock(
            "assert 'x' not in globals() and 'y' not in globals()",
            attributes={"shared": "true"},
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_named_context_ephemeral_test():
    blocks = [
        MockBlock("val = 'persistent'", attributes={"shared": "db_ctx"}),
        MockBlock(
            "assert val == 'persistent'\nval = 'mutated'\n",
            attributes={"shared": "db_ctx", "test": "true"},
        ),
        MockBlock("assert val == 'persistent'", attributes={"shared": "db_ctx"}),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_parse_named_context_and_reset_from_adoc():
    content = textwrap.dedent("""\
        = Document

        [source,python,shared="auth_flow"]
        ----
        token = "secret123"
        ----

        [source,python,shared="auth_flow"]
        ----
        assert token == "secret123"
        ----

        [source,python,reset]
        ----
        z = 99
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 3
    assert block_get_shared_context(blocks[0]) == "auth_flow"
    assert block_has_reset_marker(blocks[2]) is True


def test_interactive_named_context_and_reset():
    blocks = [
        MockBlock(
            ">>> val = 42\n>>> val\n42",
            is_interactive=True,
            attributes={"shared": "interactive_ctx"},
        ),
        MockBlock(
            ">>> val + 1\n43",
            is_interactive=True,
            attributes={"shared": "interactive_ctx"},
        ),
        MockBlock(
            ">>> val = 100\n>>> val\n100",
            is_interactive=True,
            attributes={"reset": "true", "shared": "interactive_ctx"},
        ),
        MockBlock(
            ">>> val\n100",
            is_interactive=True,
            attributes={"shared": "interactive_ctx"},
        ),
    ]
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert "val" not in shared_globals


def test_reset_marker_variations():
    b_role = MockBlock("pass", attributes={"role": "reset"})
    b_multi_role = MockBlock("pass", attributes={"role": "custom reset other"})
    b_pos = MockBlock("pass", attributes={"positional": ["source", "python", "reset"]})
    b_attr = MockBlock("pass", attributes={"reset": "true"})
    b_plain = MockBlock("pass", attributes={})

    assert block_has_reset_marker(b_role) is True
    assert block_has_reset_marker(b_multi_role) is True
    assert block_has_reset_marker(b_pos) is True
    assert block_has_reset_marker(b_attr) is True
    assert block_has_reset_marker(b_plain) is False


def test_shared_none_is_not_a_named_context():
    """shared="none" must not create a context called "none" — it should return None."""
    b = MockBlock("pass", attributes={"shared": "none"})
    assert block_get_shared_context(b) is None


def test_shared_reset_is_not_a_named_context():
    """shared="reset" must not create a context called "reset" — it should return None."""
    b = MockBlock("pass", attributes={"shared": "reset"})
    assert block_get_shared_context(b) is None


def test_shared_none_uppercase_is_not_a_named_context():
    """shared="None" (mixed case) must also return None."""
    b = MockBlock("pass", attributes={"shared": "None"})
    assert block_get_shared_context(b) is None


def test_shared_none_does_not_pollute_named_context_namespace():
    """A block with shared="none" should participate in the *default* shared namespace,
    not create a separate 'none' context."""
    blocks = [
        MockBlock("x = 42", attributes={"shared": "true"}),
        # shared="none" should fall through to default shared — NOT a named context
        MockBlock("assert x == 42", attributes={"shared": "none"}),
    ]
    shared_globals: dict[str, object] = {}
    run_test_blocks(blocks, shared_globals)
    # x should still be accessible from the default shared context
    assert shared_globals.get("x") == 42
