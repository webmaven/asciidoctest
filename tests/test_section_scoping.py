import textwrap

from asciidoctest.parser import block_get_shared_context, parse_adoc_tests
from asciidoctest.runner import run_test_blocks


class MockBlock:
    def __init__(self, content, attributes=None):
        self.content = content
        self.attributes = attributes or {}


def test_section_boundary_resets_shared_state():
    content = textwrap.dedent("""\
        = API Documentation

        == class ClassA

        [source,python,shared]
        ----
        client = "Client A Instance"
        ----

        [source,python,shared]
        ----
        assert client == "Client A Instance"
        ----

        == class ClassB

        [source,python,shared]
        ----
        # Crossing the Section boundary from ClassA to ClassB should reset shared_globals
        assert 'client' not in globals()
        client = "Client B Instance"
        ----

        [source,python,shared]
        ----
        assert client == "Client B Instance"
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 4
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_nested_sections_retain_shared_state():
    content = textwrap.dedent("""\
        = API Documentation

        == class ClassA

        [source,python,shared]
        ----
        client = "Client A"
        ----

        === method foo

        [source,python,shared]
        ----
        assert client == "Client A"
        client = "Client A Modified"
        ----

        === method bar

        [source,python,shared]
        ----
        assert client == "Client A Modified"
        ----

        == class ClassB

        [source,python,shared]
        ----
        assert 'client' not in globals()
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 4
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_section_scoping_with_named_contexts():
    content = textwrap.dedent("""\
        = API Documentation

        == Section 1

        [source,python,shared="my_ctx"]
        ----
        data = [1, 2, 3]
        ----

        == Section 2

        [source,python,shared="my_ctx"]
        ----
        assert 'data' not in globals()
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 2
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_section_id_annotation():
    content = textwrap.dedent("""\
        = API Documentation

        [source,python,test]
        ----
        x = 1
        ----

        == Section A

        [source,python,test]
        ----
        y = 2
        ----

        === Sub-section A1

        [source,python,test]
        ----
        z = 3
        ----

        == Section B

        [source,python,test]
        ----
        w = 4
        ----
        """)
    blocks = parse_adoc_tests(content)
    assert len(blocks) == 4
    # Block before any section has section_id 0
    assert blocks[0].attributes.get("__section_id__") == 0
    # Block in Section A has section_id 1
    assert blocks[1].attributes.get("__section_id__") == 1
    # Block in Sub-section A1 is inside Section A (level 2 <= 1 is False) -> section_id 1
    assert blocks[2].attributes.get("__section_id__") == 1
    # Block in Section B has section_id 2
    assert blocks[3].attributes.get("__section_id__") == 2


def test_falsy_shared_context_values():
    assert (
        block_get_shared_context(MockBlock("", attributes={"shared": "false"})) is None
    )
    assert block_get_shared_context(MockBlock("", attributes={"shared": "0"})) is None
    assert block_get_shared_context(MockBlock("", attributes={"shared": "no"})) is None
    assert (
        block_get_shared_context(MockBlock("", attributes={"shared": "true"})) is None
    )
    assert block_get_shared_context(MockBlock("", attributes={"shared": "1"})) is None
    assert (
        block_get_shared_context(MockBlock("", attributes={"shared": "custom_name"}))
        == "custom_name"
    )
