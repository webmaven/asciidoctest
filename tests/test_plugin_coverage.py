def test_plugin_unparseable_asciidoc_collection(pytester):
    # Create file with invalid/unparseable adoc structure to trigger collection Exception
    # (By mocking or passing unclosed block structure that triggers ValueError in parse_adoc_tests)
    # Actually, we can trigger ValueError during collection if we have a file that fails.
    # Let's mock parse_adoc_tests inside collection to raise an error! This is 100% deterministic and robust.
    adoc = pytester.path / "invalid.adoc"
    adoc.write_text("some content", encoding="utf-8")

    # We can pass a flag or mock via a custom plugin or test. But wait!
    # In asciidoctest/pytest_plugin.py line 75:
    # "Failed to parse AsciiDoc file ...: {e}"
    # What if we mock the parser function during the pytest session?
    # Actually, since we register the plugin dynamically, let's write a conftest that mocks `parse_adoc_tests`!
    pytester.makeconftest("""
        from unittest.mock import patch
        import pytest
        
        # Mock the parser function during collection to raise an error
        patcher = patch("asciidoctest.pytest_plugin.parse_adoc_tests", side_effect=ValueError("Mock parser failure"))
        patcher.start()
    """)

    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*Failed to parse AsciiDoc file*Mock parser failure*"])


def test_plugin_invalid_python_syntax_and_import_errors(pytester):
    # 1. Python file with syntax error to trigger find_docstrings SyntaxError exception block
    pytester.makepyfile(
        invalid_syntax="""\
        this is completely invalid python syntax!!!
        """
    )

    # 2. Python file with docstring but top-level import error to trigger loader execution runtime exception
    pytester.makepyfile(
        module_with_import_error="""\
        '''
        [source,python,test]
        ----
        >>> True
        True
        ----
        '''
        raise ValueError("module top-level execution error")
        """
    )

    # 3. Python file with unparseable docstring syntax to trigger parsing exception pass block
    pytester.makepyfile(
        unparseable_docstring="""\
        '''
        [source,python
        ----
        mismatched brackets
        ----
        '''
        def dummy():
            pass
        """
    )

    result = pytester.runpytest("-v")
    # invalid_syntax.py should be skipped for docstrings with no tests collected.
    # unparseable_docstring.py should bypass parsing exception gracefully.
    # module_with_import_error.py should collect and fail during runtest execution of the docstring.
    result.stdout.fnmatch_lines(
        [
            "*RuntimeError: Error executing module module_with_import_error: module top-level execution error*"
        ]
    )


def test_plugin_repr_non_custom_failure(pytester):
    # Create a docstring test that raises a generic ValueError (which is NOT an AsciiDocTestFailure)
    # to trigger the standard repr_failure fallback
    pytester.makepyfile(
        generic_failure="""\
        '''
        [source,python,test]
        ----
        >>> raise ValueError("generic value error")
        ----
        '''
        """
    )

    result = pytester.runpytest("-v")
    result.stdout.fnmatch_lines(["*ValueError: generic value error*"])
