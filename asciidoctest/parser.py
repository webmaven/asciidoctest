from typing import List
from asciidoctrine.lark_parser import parse_to_ast
from asciidocstring.visitors import TestBlockExtractorVisitor, TestBlock

def parse_adoc_tests(content: str, mode: str = "explicit") -> List[TestBlock]:
    """
    Parses AsciiDoc source string and extracts python test blocks.
    
    If mode is 'explicit', only extracts blocks marked with role 'test'
    or attribute 'test'.
    If mode is 'eager', extracts all python source blocks.
    """
    try:
        ast = parse_to_ast(content)
    except Exception as e:
        raise ValueError(f"AsciiDoc Parse Error: {e}") from e
        
    requires_test_marker = (mode == "explicit")
    visitor = TestBlockExtractorVisitor(target_language="python", requires_test_marker=requires_test_marker)
    return visitor.extract(ast)
