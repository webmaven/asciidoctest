"""Regression tests for Issue #8: module name collision in pytest docstring collector.

The bug: DocstringTestItem.runtest() used ``self.path.stem`` as the module name,
meaning two files named ``utils.py`` in different directories would both register
as ``sys.modules['utils']``, with the second overwriting the first.

The fix introduces a unique path-derived name like
``_asciidoctest_pkg_a_utils`` and cleans it up in a ``finally`` block.

These tests verify:
1. The unique module name is generated (not the bare stem).
2. The module is removed from sys.modules after runtest() completes.
3. Multiple files with the same stem can run without colliding.
"""

import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Direct unit tests on DocstringTestItem.runtest() internals
# ---------------------------------------------------------------------------


def _make_mock_item(tmp_path: Path, rel_subpath: str, content: str) -> object:
    """Create a minimal DocstringTestItem-like object for testing runtest()."""

    from asciidoctest.parser import extract_docstring_tests
    from asciidoctest.pytest_plugin import DocstringTestItem

    file_path = tmp_path / rel_subpath
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    class _FakeParent:
        """Minimal stand-in for a PythonDocstringFile collector."""

        class config:
            rootpath = tmp_path
            pluginmanager = None

            @staticmethod
            def getoption(name: str, default: object = None) -> object:
                return default

            @staticmethod
            def getini(name: str) -> object:
                return "explicit"

        path = file_path
        session = None

    # Parse the docstring directly from the written file
    import ast

    tree = ast.parse(content)
    docstring: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            docstring = ast.get_docstring(node)
            if docstring:
                break

    if docstring is None:
        raise ValueError("No docstring found in content")

    blocks = extract_docstring_tests(docstring, mode="explicit")
    item = object.__new__(DocstringTestItem)
    item.name = "fn_docstring"
    item.path = file_path
    item.lineno = 0
    item.blocks = blocks
    item.config = _FakeParent.config
    item._fixtureinfo = None
    return item


def test_runtest_does_not_leave_bare_stem_in_sys_modules(tmp_path):
    """runtest() must not pollute sys.modules with the bare file stem."""
    content = textwrap.dedent("""\
        VALUE = 99

        def fn():
            '''
            [source,python,test]
            ----
            assert VALUE == 99
            ----
            '''
            pass
        """)

    from asciidoctest.pytest_plugin import DocstringTestItem

    file_path = tmp_path / "sub" / "mymod.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)

    from asciidoctest.parser import extract_docstring_tests

    blocks = extract_docstring_tests(
        "'''\n[source,python,test]\n----\nassert VALUE == 99\n----\n'''",
        mode="explicit",
    )

    # Build a minimal item by hand
    class _FakeConfig:
        rootpath = tmp_path

    item = object.__new__(DocstringTestItem)
    item.name = "fn_docstring"
    item.path = file_path
    item.lineno = 0
    item.blocks = blocks
    item.config = _FakeConfig()
    item._fixtureinfo = None

    assert "mymod" not in sys.modules, "Pre-condition: 'mymod' not yet in sys.modules"

    item.runtest()

    # After runtest() completes, the bare stem must be gone.
    assert "mymod" not in sys.modules, (
        "Issue #8: sys.modules['mymod'] was left behind after runtest(). "
        "Use a unique, path-derived name and clean up in a finally block."
    )


def test_runtest_uses_unique_name_not_bare_stem(tmp_path):
    """The module registered during runtest() must use a unique, path-derived key.

    The fix uses a name like ``_asciidoctest_sub_mymod`` derived from the file's
    path relative to rootdir, ensuring different files with the same stem get
    different sys.modules keys.
    """
    content = textwrap.dedent("""\
        VALUE = 7

        def fn():
            '''
            [source,python,test]
            ----
            assert VALUE == 7
            ----
            '''
            pass
        """)

    from asciidoctest.parser import extract_docstring_tests
    from asciidoctest.pytest_plugin import DocstringTestItem

    file_path = tmp_path / "pkg_a" / "mymod.py"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)

    blocks = extract_docstring_tests(
        "'''\n[source,python,test]\n----\nassert VALUE == 7\n----\n'''",
        mode="explicit",
    )

    class _FakeConfig:
        rootpath = tmp_path

    item = object.__new__(DocstringTestItem)
    item.name = "fn_docstring"
    item.path = file_path
    item.lineno = 0
    item.blocks = blocks
    item.config = _FakeConfig()
    item._fixtureinfo = None

    # Snapshot sys.modules before; capture what's added during runtest()
    before_keys = set(sys.modules.keys())

    item.runtest()

    after_keys = set(sys.modules.keys())
    added_keys = after_keys - before_keys

    # No bare stem ('mymod') should have been added
    assert "mymod" not in added_keys, (
        f"Issue #8: bare stem 'mymod' was registered in sys.modules. "
        f"Added keys: {added_keys}"
    )

    # No _asciidoctest_ prefixed keys should linger (they should be cleaned up)
    asciidoctest_keys = [k for k in added_keys if k.startswith("_asciidoctest_")]
    assert not asciidoctest_keys, (
        f"Issue #8: _asciidoctest_-prefixed keys not cleaned up: {asciidoctest_keys}"
    )


def test_two_same_stem_files_no_sys_modules_conflict(tmp_path):
    """Two files named utils.py in different dirs must not overwrite each other in sys.modules.

    This simulates two successive DocstringTestItem.runtest() calls in the same process
    (exactly what pytest does during a full test run).
    """
    content_a = textwrap.dedent("""\
        VALUE = "a"

        def fn():
            '''
            [source,python,test]
            ----
            assert VALUE == "a"
            ----
            '''
            pass
        """)
    content_b = textwrap.dedent("""\
        VALUE = "b"

        def fn():
            '''
            [source,python,test]
            ----
            assert VALUE == "b"
            ----
            '''
            pass
        """)

    from asciidoctest.parser import extract_docstring_tests
    from asciidoctest.pytest_plugin import DocstringTestItem

    def make_item(subdir: str, content: str) -> DocstringTestItem:
        file_path = tmp_path / subdir / "utils.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        blocks = extract_docstring_tests(
            f"'''\n[source,python,test]\n----\nassert VALUE == \"{subdir[4]}\"\n----\n'''",
            mode="explicit",
        )

        class _FakeConfig:
            rootpath = tmp_path

        item = object.__new__(DocstringTestItem)
        item.name = "fn_docstring"
        item.path = file_path
        item.lineno = 0
        item.blocks = blocks
        item.config = _FakeConfig()
        item._fixtureinfo = None
        return item  # type: ignore[return-value]

    item_a = make_item("pkg_a", content_a)
    item_b = make_item("pkg_b", content_b)

    assert "utils" not in sys.modules

    # Both runtest() calls must succeed (no collision)
    item_a.runtest()  # passes if VALUE == "a"
    item_b.runtest()  # passes if VALUE == "b" (would fail if it loaded "a"'s module)

    # Neither should pollute sys.modules after completing
    assert "utils" not in sys.modules, (
        "Issue #8: sys.modules['utils'] was polluted after running two same-stemmed files."
    )
