from typing import Any, List
from asciidoctrine.lark_parser import parse_to_ast
from asciidocstring.visitors import TestBlockExtractorVisitor, TestBlock

class SafeTestBlockExtractorVisitor(TestBlockExtractorVisitor):
    """
    A robust subclass of TestBlockExtractorVisitor that safely handles raw strings
    or other non-Node elements encountered during generic AST traversal.
    """
    def visit(self, node: Any, **kwargs: Any) -> Any:
        if isinstance(node, str) or not hasattr(node, "name"):
            return None
        return super().visit(node, **kwargs)

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
    visitor = SafeTestBlockExtractorVisitor(target_language="python", requires_test_marker=requires_test_marker)
    return visitor.extract(ast)
