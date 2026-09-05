import textwrap


def test_split_sections_disabled_by_default(pytester):
    adoc_content = textwrap.dedent("""\
        = Sample Guide

        == Installation
        [source,python,test]
        ----
        x = 1
        assert x == 1
        ----

        == Usage
        [source,python,test]
        ----
        y = 2
        assert y == 2
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1, failed=0)
    stdout = result.stdout.str()
    assert "sample.adoc::asciidoctest PASSED" in stdout


def test_split_sections_enabled_via_cli_flag(pytester):
    adoc_content = textwrap.dedent("""\
        = Sample Guide

        == Installation
        [source,python,test]
        ----
        x = 1
        assert x == 1
        ----

        == Usage
        [source,python,test]
        ----
        y = 2
        assert y == 2
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    result = pytester.runpytest("-v", "--asciidoctest-split-sections")
    result.assert_outcomes(passed=2, failed=0)
    stdout = result.stdout.str()
    assert "sample.adoc::Installation::asciidoctest_block_1 PASSED" in stdout
    assert "sample.adoc::Usage::asciidoctest_block_2 PASSED" in stdout


def test_split_sections_pytest_k_filter(pytester):
    adoc_content = textwrap.dedent("""\
        = Sample Guide

        == Installation
        [source,python,test]
        ----
        x = 1
        assert x == 1
        ----

        == Usage
        [source,python,test]
        ----
        y = 2
        assert y == 2
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    result = pytester.runpytest("-v", "--asciidoctest-split-sections", "-k", "Usage")
    result.assert_outcomes(passed=1, failed=0)
    stdout = result.stdout.str()
    assert "sample.adoc::Usage::asciidoctest_block_2 PASSED" in stdout
    assert "Installation" not in stdout or "deselected" in stdout


def test_split_sections_enabled_via_ini_config(pytester):
    pytester.makeini("""\
        [pytest]
        asciidoctest_split_sections = true
        """)
    adoc_content = textwrap.dedent("""\
        = Sample Guide

        == Getting Started
        [source,python,test]
        ----
        assert True
        ----
        """)
    pytester.makefile(".adoc", sample=adoc_content)
    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1, failed=0)
    stdout = result.stdout.str()
    assert "sample.adoc::Getting_Started::asciidoctest_block_1 PASSED" in stdout
