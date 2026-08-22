import ast
from typing import Any

import asciidocstring
from asciidocstring.visitors import TestBlock, TestBlockExtractorVisitor
from asciidoctrine.lark_parser import parse_to_ast


class SafeTestBlockExtractorVisitor(TestBlockExtractorVisitor):
    """
    A robust subclass of TestBlockExtractorVisitor that safely handles raw strings
    or other non-Node elements encountered during generic AST traversal, and tracks
    top-level Section boundaries.
    """

    def __init__(self, target_language: str, requires_test_marker: bool):
        super().__init__(target_language, requires_test_marker)
        self._current_section_id = 0
        self._section_counter = 0

    def extract(self, node: Any) -> list[TestBlock]:
        self._current_section_id = 0
        self._section_counter = 0
        return super().extract(node)

    def visit(self, node: Any, **kwargs: Any) -> Any:
        if isinstance(node, str) or not hasattr(node, "name"):
            return None

        if getattr(node, "name", "") == "section":
            level = getattr(node, "level", 1)
            if level <= 1:
                self._section_counter += 1
                prev_section_id = self._current_section_id
                self._current_section_id = self._section_counter
                result = super().visit(node, **kwargs)
                self._current_section_id = prev_section_id
                return result

        return super().visit(node, **kwargs)

    def visit_listing(self, node: Any) -> None:
        count_before = len(self.extracted_tests)
        super().visit_listing(node)
        if len(self.extracted_tests) > count_before:
            block = self.extracted_tests[-1]
            if getattr(block, "attributes", None) is None:
                block.attributes = {}
            block.attributes["__section_id__"] = self._current_section_id


def block_has_test_marker(block: Any) -> bool:
    """
    Inspects a block's attributes, roles, and positional parameters
    to determine if it has been explicitly marked as a 'test' block.
    """
    attrs = getattr(block, "attributes", {}) or {}
    return (
        "test" in attrs
        or attrs.get("test") == "true"
        or attrs.get("role") == "test"
        or "test" in attrs.get("positional", [])
        or ("test" in str(attrs.get("role", "")).split())
    )


def block_has_shared_marker(block: Any) -> bool:
    """
    Inspects a block's attributes, roles, and positional parameters
    to determine if it has been explicitly marked as a 'shared' block.
    """
    attrs = getattr(block, "attributes", {}) or {}
    return (
        "shared" in attrs
        or attrs.get("shared") == "true"
        or attrs.get("role") == "shared"
        or "shared" in attrs.get("positional", [])
        or ("shared" in str(attrs.get("role", "")).split())
    )


def block_has_reset_marker(block: Any) -> bool:
    """
    Inspects a block's attributes, roles, and positional parameters
    to determine if it has been marked with a 'reset' directive.
    """
    attrs = getattr(block, "attributes", {}) or {}
    return (
        "reset" in attrs
        or attrs.get("reset") == "true"
        or attrs.get("role") == "reset"
        or "reset" in attrs.get("positional", [])
        or ("reset" in str(attrs.get("role", "")).split())
    )


def block_get_shared_context(block: Any) -> str | None:
    """
    Returns the named shared context identifier if specified (e.g. shared="context_name"),
    or None if it uses default shared context or is not shared.
    """
    attrs = getattr(block, "attributes", {}) or {}
    shared_val = attrs.get("shared")
    if shared_val and str(shared_val).lower() not in (
        "true",
        "1",
        "yes",
        "false",
        "0",
        "no",
    ):
        return str(shared_val)
    return None


def parse_adoc_tests(
    content: str, mode: str = "explicit", preprocess_directives: bool = False
) -> list[TestBlock]:
    """
    Parses AsciiDoc source string and extracts python test blocks under
    a unified, symmetric safety-first design.

    Rule 1 (Default): If no attributes/markers are specified, the listing is skipped
                      (unless in 'eager' mode, which behaves like 'test').
    Rule 2 ('test'): Executable but completely isolated ({}) and ephemeral.
    Rule 3 ('shared'): Executable and completely read-write and persistent.
    Rule 4 ('shared, test'): Executable with an ephemeral copy of shared state.

    Constraint: 'eager' mode DOES NOT work if ANY block in the document has
                explicit attributes or roles of either 'test' or 'shared'.
    """
    try:
        ast = parse_to_ast(content, preprocess_directives=preprocess_directives)
    except Exception as e:
        raise ValueError(f"AsciiDoc Parse Error: {e}") from e

    # Always extract all blocks to inspect their explicit attributes/roles
    visitor = SafeTestBlockExtractorVisitor(
        target_language="python", requires_test_marker=False
    )
    all_blocks = visitor.extract(ast)

    # Helper to check if a block has explicit 'test', 'shared', or 'reset' markers
    def has_explicit_markers(block: Any) -> bool:
        return (
            block_has_test_marker(block)
            or block_has_shared_marker(block)
            or block_has_reset_marker(block)
        )

    any_explicit = any(has_explicit_markers(b) for b in all_blocks)

    if any_explicit:
        # Eager mode is bypassed/disabled when any block has explicit markers.
        # Only return the explicitly marked blocks.
        return [b for b in all_blocks if has_explicit_markers(b)]
    else:
        # If no explicit markers are present, eager mode runs all blocks as default 'test' blocks.
        if mode == "eager":
            return all_blocks
        return []


def extract_docstring_tests(docstring: str, mode: str = "explicit") -> list[Any]:
    """
    Parses a Python docstring and extracts its test blocks, honoring
    the exact same eager-mode safety-first constraints as parse_adoc_tests.
    """
    try:
        doc_doc = asciidocstring.parse(docstring)
    except Exception:
        return []

    # Always extract all python blocks first
    all_blocks = doc_doc.extract_tests(language="python", requires_test_marker=False)

    # Helper to check if a block has explicit 'test', 'shared', or 'reset' markers
    def has_explicit_markers(block: Any) -> bool:
        return (
            block_has_test_marker(block)
            or block_has_shared_marker(block)
            or block_has_reset_marker(block)
        )

    any_explicit = any(has_explicit_markers(b) for b in all_blocks)

    if any_explicit:
        # Eager mode is bypassed/disabled. Only return the explicitly marked blocks.
        return [b for b in all_blocks if has_explicit_markers(b)]
    else:
        # If no explicit markers are present, eager mode runs all blocks as default 'test' blocks.
        if mode == "eager":
            return all_blocks
        return []


def find_docstrings_in_py_file(path) -> list[tuple[str, int, str]]:
    """Statically parse a Python file and return all docstrings with metadata."""
    content = path.read_text("utf-8")
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError):
        return []

    docstrings = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            docstring = ast.get_docstring(node)
            if docstring:
                lineno = getattr(node, "lineno", 1)
                name = node.name if hasattr(node, "name") else "<module>"
                docstrings.append((name, lineno, docstring))
    return docstrings
