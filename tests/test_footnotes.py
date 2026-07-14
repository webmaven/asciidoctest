import pytest
import textwrap
from asciidoctest.parser import parse_adoc_tests
from asciidoctest.runner import run_test_blocks

def test_footnotes_parsing_and_execution():
    # Construct an AsciiDoc document with anonymous and named footnotes,
    # as well as standard interactive and non-interactive python test blocks.
    content = textwrap.dedent("""\
        = Footnotes Test Document
        
        This is some text with an anonymous footnote footnote:[This is an anonymous footnote.].
        Here is another reference to a named footnote footnoteref:[fn1, This is a named footnote.].
        And here is a second reference to the same named footnote footnoteref:[fn1].
        
        [source,python,test]
        ----
        >>> x = "footnote tested"
        >>> x
        'footnote tested'
        ----
        
        [source,python,test]
        ----
        assert x == "footnote tested"
        ----
        """)
        
    # Verify that the parser extracts both blocks perfectly under the upgraded asciidoctrine
    blocks = parse_adoc_tests(content, mode="explicit")
    assert len(blocks) == 2
    
    # Run the test blocks to confirm seamless sequential execution
    shared_globals = {}
    run_test_blocks(blocks, shared_globals)
    assert shared_globals.get("x") == "footnote tested"
