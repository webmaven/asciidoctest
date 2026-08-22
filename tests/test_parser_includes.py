import textwrap
import pytest
from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import run_test_blocks


def test_parse_adoc_with_missing_illustrative_include():
    content = textwrap.dedent("""\
        = Document with Illustrative Include

        include::non_existent_file_illustrative.adoc[]

        [source,python,test]
        ----
        x = 10
        assert x == 10
        ----
        """)
    # Should not raise PreprocessorError
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 1
    assert "assert x == 10" in blocks[0].content

    # Execute blocks
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)


def test_parse_adoc_with_custom_preprocess_directives_flag():
    content = textwrap.dedent("""\
        = Document

        [source,python,test]
        ----
        y = 20
        assert y == 20
        ----
        """)
    blocks = parse_adoc_tests(content, mode="explicit", preprocess_directives=False)
    assert len(blocks) == 1
