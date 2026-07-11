import pytest
import textwrap

def test_adoc_collection_explicit_mode(pytester):
    # Create an .adoc file with one marked test and one unmarked
    adoc_content = textwrap.dedent("""\
        = Sample Adoc
        
        This block is unmarked and should be skipped in explicit mode:
        [source,python]
        ----
        x = 100
        assert x == 200
        ----
        
        This block is marked and should be executed:
        [source,python,test]
        ----
        y = 42
        assert y == 42
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    # Run pytest. By default it should run in explicit mode
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1, failed=0, skipped=0)


def test_adoc_collection_eager_mode(pytester):
    # Create an .adoc file with one marked test and one unmarked
    adoc_content = textwrap.dedent("""\
        = Sample Adoc
        
        This block has no test marker:
        [source,python]
        ----
        x = 100
        assert x == 200
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    # Run pytest in eager mode (via cli option)
    result = pytester.runpytest("-v", "--asciidoctest-mode=eager")
    # It should run the unmarked block, which has an assertion failure
    result.assert_outcomes(passed=0, failed=1, skipped=0)
    assert "AssertionError" in result.stdout.str()


def test_python_docstring_collection(pytester):
    # Create a Python file with an AsciiDoc docstring doctest
    py_content = textwrap.dedent("""\
        def add(a, b):
            \"\"\"
            Sum two numbers in AsciiDoc.
            
            [source,python,test]
            ----
            >>> add(3, 4)
            7
            ----
            \"\"\"
            return a + b
        """)
    pytester.makepyfile(module=py_content)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1, failed=0)


def test_adoc_failure_reporting(pytester):
    adoc_content = textwrap.dedent("""\
        = Doc
        
        [source,python,test]
        ----
        >>> 1 + 1
        99
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=0, failed=1)
    stdout = result.stdout.str()
    assert "Test block failure at line 3" in stdout
    assert "Expected:" in stdout
    assert "99" in stdout
    assert "Got:" in stdout
    assert "2" in stdout
